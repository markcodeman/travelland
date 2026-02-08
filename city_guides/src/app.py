#!/usr/bin/env python3
"""
Refactored TravelLand app.py with modular structure
"""

import sys
from pathlib import Path

# Add parent directory to path for imports (must be first)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Standard library imports
import os
import asyncio
import json
import hashlib
import re
import time

# Third-party imports
from quart import Quart, request, jsonify
from quart_cors import cors
import aiohttp
from aiohttp import ClientTimeout
from redis import asyncio as aioredis

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Now safe to import city_guides modules
try:
    from city_guides.providers.wikipedia_provider import fetch_wikipedia_summary
    WIKI_CITY_AVAILABLE = True
except Exception:
    fetch_wikipedia_summary = None
    WIKI_CITY_AVAILABLE = False

# Service imports
from city_guides.src.services.location import (
    city_mappings,
    region_mappings,
    levenshtein_distance
)
from city_guides.src.services.learning import (
    get_location_weight,
    increment_location_weight,
    detect_hemisphere_from_searches
)
from city_guides.src.services.pixabay import pixabay_service
from city_guides.src.dynamic_neighborhoods import get_neighborhoods_for_city

# Import modules
from city_guides.src.persistence import (
    build_search_cache_key,
    ensure_bbox,
    get_cost_estimates,
    _is_relevant_wikimedia_image,
    _persist_quick_guide
)
from city_guides.providers import multi_provider
from city_guides.providers.geocoding import geocode_city
from city_guides.providers.utils import get_session
# metrics helper (Redis-backed counters and latency samples)
from city_guides.src.metrics import increment, observe_latency, get_metrics as get_metrics_dict
from city_guides.src.marco_response_enhancer import should_call_groq, analyze_user_intent
from city_guides.src.neighborhood_disambiguator import NeighborhoodDisambiguator
from city_guides.src.data.seeded_facts import get_city_fun_facts
from city_guides.src.utils.seasonal import get_seasonal_destinations

# Use relative paths for deployment portability
PROJECT_ROOT = Path(__file__).parent.parent.parent
STATIC_FOLDER = PROJECT_ROOT / "city_guides" / "static"
TEMPLATE_FOLDER = PROJECT_ROOT / "city_guides" / "templates"

# Create Quart app instance at the very top so it is always defined before any route decorators
app = Quart(__name__, static_folder=str(STATIC_FOLDER), static_url_path='', template_folder=str(TEMPLATE_FOLDER))

# Configure CORS
cors(app, allow_origin=["http://localhost:5174", "https://travelland-w0ny.onrender.com"], allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Cleanup Pixabay service on app shutdown
async def cleanup_pixabay():
    """Clean up Pixabay service on shutdown"""
    await pixabay_service.close()

# Global async clients
aiohttp_session: aiohttp.ClientSession | None = None
redis_client: aioredis.Redis | None = None

# Track active long-running searches (search_id -> metadata)
active_searches = {}

# Configuration constants
CACHE_TTL_NEIGHBORHOOD = int(os.getenv("CACHE_TTL_NEIGHBORHOOD", "3600"))  # 1 hour
CACHE_TTL_RAG = int(os.getenv("CACHE_TTL_RAG", "1800"))  # 30 minutes
CACHE_TTL_SEARCH = int(os.getenv("CACHE_TTL_SEARCH", "1800"))  # 30 minutes
CACHE_TTL_TELEPORT = int(os.getenv("CACHE_TTL_TELEPORT", "86400"))  # 24 hours
DDGS_CONCURRENCY = int(os.getenv("DDGS_CONCURRENCY", "5"))
DDGS_TIMEOUT = int(os.getenv("DDGS_TIMEOUT", "5"))
DEFAULT_PREWARM_CITIES = os.getenv("DEFAULT_PREWARM_CITIES", "").split(",") if os.getenv("DEFAULT_PREWARM_CITIES") else []
DEFAULT_PREWARM_QUERIES = os.getenv("DEFAULT_PREWARM_QUERIES", "").split(",") if os.getenv("DEFAULT_PREWARM_QUERIES") else []
DISABLE_PREWARM = os.getenv("DISABLE_PREWARM", "false").lower() == "true"
GEOCODING_TIMEOUT = int(os.getenv("GEOCODING_TIMEOUT", "10"))
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "30"))
POPULAR_CITIES = os.getenv("POPULAR_CITIES", "").split(",") if os.getenv("POPULAR_CITIES") else []
PREWARM_RAG_CONCURRENCY = int(os.getenv("PREWARM_RAG_CONCURRENCY", "3"))
VERBOSE_OPEN_HOURS = os.getenv("VERBOSE_OPEN_HOURS", "false").lower() == "true"
# Constants
PREWARM_TTL = CACHE_TTL_SEARCH
PREWARM_RAG_TOP_N = int(os.getenv('PREWARM_RAG_TOP_N', '50'))

# US State Icons - State-specific symbols instead of limited flag emojis
US_STATE_ICONS = {
    'Alabama': '🏛️', 'Alaska': '🏔️', 'Arizona': '🌵', 'Arkansas': '🌲',
    'California': '🌴', 'Colorado': '🏔️', 'Connecticut': '⚓', 'Delaware': '🦢',
    'Florida': '🏖️', 'Georgia': '🍑', 'Hawaii': '🌺', 'Idaho': '🥔',
    'Illinois': '🏛️', 'Indiana': '🏀', 'Iowa': '🌽', 'Kansas': '🌾',
    'Kentucky': '🥃', 'Louisiana': '🎷', 'Maine': '🦞', 'Maryland': '🦀',
    'Massachusetts': '⚓', 'Michigan': '🍒', 'Minnesota': '🏒', 'Mississippi': '🦈',
    'Missouri': '🏛️', 'Montana': '🐻', 'Nebraska': '🌽', 'Nevada': '🎰',
    'New Hampshire': '🏔️', 'New Jersey': '🍔', 'New Mexico': '🌶️', 'New York': '🗽',
    'North Carolina': '🍑', 'North Dakota': '🌾', 'Ohio': '🏛️', 'Oklahoma': '🌪️',
    'Oregon': '🌲', 'Pennsylvania': '🔔', 'Rhode Island': '⚓', 'South Carolina': '🍑',
    'South Dakota': '🏔️', 'Tennessee': '🎵', 'Texas': '🤠', 'Utah': '🏔️',
    'Vermont': '🍁', 'Virginia': '🏛️', 'Washington': '🍎', 'West Virginia': '🏔️',
    'Wisconsin': '🧀', 'Wyoming': '🐎', 'District of Columbia': '🏛️'
}

async def fetch_city_wikipedia(city: str, state: str | None = None, country: str | None = None) -> tuple[str, str] | None:
    """Return (summary, url) for the given city using Wikipedia."""
    if not (WIKI_CITY_AVAILABLE and city):
        return None

    def _candidates():
        base = city.strip()
        seen = set()
        for candidate in [
            base,
            f"{base}, {state}" if state else None,
            f"{base}, {country}" if country else None,
            f"{base}, {state}, {country}" if state and country else None,
        ]:
            if candidate:
                normalized = candidate.strip()
                if normalized.lower() not in seen:
                    seen.add(normalized.lower())
                    yield normalized

    async def _fetch_for_title(title: str, country: str | None = None):
        if not fetch_wikipedia_summary:
            return None
        slug = title.replace(' ', '_')
        summary = await fetch_wikipedia_summary(title, lang="en", city=city, country=country)
        if summary:
            return summary.strip(), f"https://en.wikipedia.org/wiki/{slug}"
        return None

    # Try direct titles first
    for title in _candidates():
        try:
            # Pass country for better disambiguation handling
            result = await _fetch_for_title(title, country)
            if result:
                return result
        except Exception:
            app.logger.exception('Direct Wikipedia summary fetch failed for %s via %s', city, title)

    # Fallback: use Wikipedia open search with candidates
    try:
        async with aiohttp.ClientSession() as session:
            for title in _candidates():
                params = {
                    "action": "opensearch",
                    "search": title,
                    "limit": 1,
                    "namespace": 0,
                    "format": "json",
                }
                async with session.get("https://en.wikipedia.org/w/api.php", params=params, timeout=ClientTimeout(total=6)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    if isinstance(data, list) and len(data) >= 2 and data[1]:
                        best_title = data[1][0]
                        try:
                            result = await _fetch_for_title(best_title, country)
                            if result:
                                return result
                        except Exception:
                            app.logger.exception('OpenSearch Wikipedia summary failed for %s via %s', city, best_title)
    except Exception:
        app.logger.exception('Wikipedia open search failed for %s', city)

    return None

# DDGS provider import is optional at module import time (tests may not have ddgs installed)
from typing import Callable, Awaitable, Any

ddgs_search: Callable[..., Awaitable[list[dict[str, Any]]]]
ddgs_import_err: str = "unknown error"
try:
    from city_guides.providers.ddgs_provider import ddgs_search as _ddgs_provider_search
    # Use the provider's async function directly
    ddgs_search = _ddgs_provider_search  # type: ignore[assignment]
    app.logger.info('DDGS provider enabled for neighborhood search')
except Exception as e:
    ddgs_import_err = str(e)
    async def _ddgs_stub(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        app.logger.warning('DDGS provider unavailable (%s); returning empty results', ddgs_import_err)
        return []

    ddgs_search = _ddgs_stub  # type: ignore[assignment]
    app.logger.debug('DDGS provider not available at module import time; falling back to empty search results')

from city_guides.groq.traveland_rag import recommender, TravelLandRecommender

# --- /recommend route for RAG recommender ---

@app.route("/api/chat/rag", methods=["POST"])
async def api_chat_rag():
    """
    RAG chat endpoint: Accepts a user query, runs DDGS web search, synthesizes an answer with Groq, and returns a unified AI response.
    Request JSON: {"query": "...", "engine": "google" (optional), "max_results": 8 (optional), "city": "...", "lat": ..., "lon": ...}
    Response JSON: {"answer": "..."}
    """
    try:
        data = await request.get_json(force=True)
        query = (data.get("query") or "").strip()
        engine = data.get("engine", "google")
        # Default to a small number of web snippets to improve latency and prompt size
        try:
            requested_max = int(data.get('max_results', 8))
        except Exception:
            requested_max = 8
        DEFAULT_DDGS_MAX = int(os.getenv('DDGS_MAX_RESULTS', '8'))
        max_results = min(requested_max, DEFAULT_DDGS_MAX)
        DEFAULT_DDGS_TIMEOUT = float(os.getenv('DDGS_TIMEOUT', '5'))
        city = data.get("city", "")
        state = data.get("state", "")
        country = data.get("country", "")
        lat = data.get("lat")
        lon = data.get("lon")
        if not query:
            return jsonify({"error": "Missing query"}), 400
        # Track request count
        try:
            await increment('rag.requests')
        except Exception:
            pass
        start_time = time.time()

        full_query = query
        
        # Check if user is asking for a fun fact - use seeded data first
        # Must have BOTH: (1) fact-seeking intent AND (2) specific fact keywords
        fact_intent_keywords = ['fact', 'trivia', 'did you know', 'something cool', 'something crazy', 
                                'something amazing', 'something unique', 'something weird', 'something special',
                                'cool thing', 'crazy thing', 'interesting thing']
        has_fact_intent = any(kw in query.lower() for kw in fact_intent_keywords)
        
        # Also check for direct fun fact patterns
        direct_patterns = ['fun fact', 'interesting fact', 'cool fact', 'crazy fact', 'amazing fact', 
                          'unique fact', 'weird fact', 'surprising fact']
        has_direct_pattern = any(kw in query.lower() for kw in direct_patterns)
        
        is_fun_fact_query = has_direct_pattern or (has_fact_intent and any(kw in query.lower() for kw in ['fact', 'thing', 'special']))
        if is_fun_fact_query and city:
            try:
                from city_guides.src.data.seeded_facts import get_city_fun_facts
                facts = get_city_fun_facts(city)
                if facts:
                    import random
                    selected_fact = random.choice(facts)
                    answer = f"Here's an interesting fact about {city}: {selected_fact}"
                    return jsonify({"answer": answer})
            except Exception as e:
                app.logger.debug(f'Fun facts lookup failed for {city}: {e}')
                # Continue to normal flow if seeded data not available
        
        # DISABLED FOR MARCO TESTING: No caching during development
        # Skip cache to ensure fresh responses and avoid query contamination
        cache_key = None
        cached = None
        
        # Compute a cache key for this query+city and try Redis cache to avoid repeating long work
        # cache_key = None
        # try:
        #     if redis_client:
        #         ck_input = f"{query}|{city}|{state}|{country}|{lat}|{lon}"
        #         cache_key = "rag:" + hashlib.sha256(ck_input.encode('utf-8')).hexdigest()
        #         cached = await redis_client.get(cache_key)
        #         if cached:
        #             app.logger.info('RAG cache hit for key %s', cache_key)
        #             try:
        #                 # metrics: cache hit
        #                 await increment('rag.cache_hit')
        #             except Exception:
        #                 pass
        #             try:
        #                 cached_parsed = json.loads(cached)
        #                 return jsonify(cached_parsed)
        #             except Exception:
        #                 app.logger.debug('Failed to parse cached RAG response for %s', cache_key)
        # except Exception:
        #     app.logger.exception('Redis cache lookup failed')

        # Skip venue fetching for speed - web search + Groq is sufficient
        venues = []

        context_snippets = []

        # Run DDGS web search (async) with the full_query
        web_results = []
        try:
            web_results = await ddgs_search(full_query, engine=engine, max_results=max_results, timeout=DEFAULT_DDGS_TIMEOUT)
        except Exception:
            app.logger.exception('DDGS search failed for %s', full_query)

        for r in web_results or []:
            # Only use title + body for context, never URLs
            snippet = f"{r.get('title','')}: {r.get('body','')}"
            if snippet.strip():
                context_snippets.append(snippet)

        # Fallback context when DDGS is unavailable or empty
        if not context_snippets and city:
            try:
                wiki_result = await fetch_city_wikipedia(city, state or None, country or None)
            except Exception:
                wiki_result = None
                app.logger.exception('Wikipedia fallback fetch failed for %s', city)
            if wiki_result:
                summary, wiki_url = wiki_result
                context_snippets.append(f"{city} overview: {summary}")
                context_snippets.append(f"Reference: {wiki_url}")
        if not context_snippets:
            context_snippets.append(
                f"No live web snippets available. Base the answer on trustworthy travel expertise for {city or 'the requested destination'} and general knowledge."
            )

        context_text = "\n\n".join(context_snippets)

        # Compose Groq prompt (system + user)
        # Get neighborhood from query if present (e.g., "Tell me about X in Neighborhood, City" or "in la Vila de Gràcia, Barcelona")
        neighborhood_from_query = None
        if city and ',' in query:
            # Try to extract neighborhood from various patterns
            patterns = [
                rf'in\s+([^,]+),\s*{re.escape(city)}',  # "in La Vila de Gràcia, Barcelona"
                rf'about\s+([^,]+),\s*{re.escape(city)}',  # "about Music Heritage in Gràcia, Barcelona"
                rf'([^,]+),\s*{re.escape(city)}',  # "Gràcia, Barcelona"
            ]
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    candidate = match.group(1).strip()
                    # Don't capture the query subject (e.g., "Music Heritage") as neighborhood
                    # Heuristic: if it contains multiple words and looks like a topic, skip
                    skip_keywords = ['music', 'heritage', 'food', 'tours', 'sites', 'restaurants', 'things', 'places', 'what', 'where', 'how']
                    if any(kw in candidate.lower() for kw in skip_keywords):
                        continue
                    neighborhood_from_query = candidate
                    break
        
        # Also try to extract from "in [Neighborhood]" patterns without city comma
        if not neighborhood_from_query:
            # Pattern: "in la Vila de Gràcia" or "in Gràcia" (Catalan/Spanish neighborhoods often have articles)
            match = re.search(r'in\s+(la\s+|el\s+|les\s+|els\s+)?([^,]+?)(?:\s+in|\s+near|\s+area)?\s*$', query, re.IGNORECASE)
            if match:
                article = match.group(1) or ''
                neighborhood_from_query = (article + match.group(2)).strip()
        
        system_prompt = (
            "You are Marco, a travel AI assistant. Given a user query and web search snippets, provide helpful, accurate travel information. "
            "CRITICAL RULES - VIOLATION IS NOT ALLOWED:\n"
            "1. This is a conversation - use previous messages for context and answer follow-up questions.\n"
            "2. When users ask vague questions like 'do you have a link?' or 'where is it?', refer to the most recent place you mentioned.\n"
            "3. CLARIFYING QUESTIONS - ONLY when user uses pronouns like 'they', 'it', 'this', 'that' without clear context. "
            "DON'T ask clarifying questions for clear requests like 'Tell me about historic sites in Luminy' - just answer!\n"
            "4. STAY ON TOPIC - answer about the SPECIFIC place requested, not generic alternatives.\n"
            "5. NEIGHBORHOOD FOCUS IS MANDATORY: When user mentions a neighborhood (e.g., 'la Vila de Gràcia, Barcelona', 'Le Marais, Paris'), "
            "   you MUST focus ONLY on that neighborhood. ZERO generic city information allowed.\n"
            "6. ABSOLUTE PROHIBITION: Never provide city-wide overview when a neighborhood is specified. "
            "   If you lack neighborhood-specific info, say 'I don't have specific information about [neighborhood]' rather than giving generic city info.\n"
            "7. Google Maps format: [Place Name](https://www.google.com/maps/search/?api=1&query=Place+Name+City) "
            "   - Text in [brackets], URL in (parentheses), short URL with place+city only.\n"
            "8. Always use full place names for auto-linking. Never say 'I don't have a link' - provide Maps search link instead.\n"
            "9. Never mention sources or web search usage.\n"
            "10. GEOGRAPHIC ACCURACY: Verify coastal vs inland before mentioning beaches."
        )
        
        # Build location context with neighborhood if available
        location_parts = []
        if neighborhood_from_query:
            location_parts.append(neighborhood_from_query)
        if city:
            location_parts.append(city)
        location_fragment = f" in {', '.join(location_parts)}" if location_parts else ""
        
        user_prompt = f"User query: {query}{location_fragment}\n\nRelevant web snippets:\n{context_text}"

        # Build messages array with conversation history if provided
        conversation_history = data.get('history', [])
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        # Add conversation history (up to last 6 messages to stay within token limits)
        if conversation_history and isinstance(conversation_history, list):
            for msg in conversation_history[-6:]:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    messages.append({"role": msg['role'], "content": msg['content']})
        
        # Add current user query
        messages.append({"role": "user", "content": user_prompt})

        # Analyze user intent and determine if we should call Groq
        intent = analyze_user_intent(query, venues or [])
        should_use_groq = should_call_groq({"quality_score": 0.5}, intent)  # Default quality score

        # Call Groq via recommender (6s timeout for Flash Gordon speed)
        GROQ_TIMEOUT = int(os.getenv('GROQ_CHAT_TIMEOUT', '6'))
        groq_resp = None
        if should_use_groq:
            groq_resp = await recommender.call_groq_chat(messages, timeout=GROQ_TIMEOUT)
            if not groq_resp:
                # record groq failure
                try:
                    await increment('rag.groq_fail')
                except Exception:
                    pass
                return jsonify({"error": "Groq API call failed"}), 502
            try:
                answer = groq_resp["choices"][0]["message"]["content"]
            except Exception:
                answer = None
            if not answer:
                try:
                    await increment('rag.no_answer')
                except Exception:
                    pass
                return jsonify({"error": "No answer generated"}), 502
        else:
            # If we shouldn't call Groq, use a simple fallback answer
            answer = f"I found some information about {city}. Let me know what specific details you're looking for!"

        result_payload = {"answer": answer.strip()}
        # record latency
        try:
            elapsed = (time.time() - start_time) * 1000.0
            await observe_latency('rag.latency_ms', elapsed)
        except Exception:
            pass
        # DISABLED FOR MARCO TESTING: No cache storage during development
        # Cache the result for repeated queries to improve latency on hot paths
        # try:
        #     if redis_client and cache_key:
        #         ttl = int(os.getenv('RAG_CACHE_TTL', 60 * 60 * 6))  # default 6 hours
        #         await redis_client.setex(cache_key, ttl, json.dumps(result_payload))
        #         app.logger.info('Cached RAG response %s (ttl=%s)', cache_key, ttl)
        # except Exception:
        #     app.logger.exception('Failed to cache RAG response')

        return jsonify(result_payload)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

# Simple CORS support for development: allow frontend dev server to call API
@app.after_request
async def _add_cors_headers(response):
    try:
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    except Exception:
        pass
    return response

@app.before_request
async def _handle_options_preflight():
    # Respond to OPTIONS preflight requests with the proper CORS headers.
    if request.method == 'OPTIONS':
        from quart import make_response
        resp = await make_response(('', 204))
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return resp

@app.before_serving
async def startup():
    global aiohttp_session, redis_client, recommender
    aiohttp_session = aiohttp.ClientSession(headers={"User-Agent": "city-guides-async"})
    # Update recommender with shared session for connection reuse
    recommender = TravelLandRecommender(session=aiohttp_session)
    try:
        redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        await redis_client.ping()  # type: ignore
        app.logger.info("✅ Redis connected")
        if DEFAULT_PREWARM_CITIES and DEFAULT_PREWARM_QUERIES:
            asyncio.create_task(prewarm_popular_searches())
        # start background prewarm of neighborhood lists for popular cities
        try:
            if redis_client and POPULAR_CITIES and not DISABLE_PREWARM:
                asyncio.create_task(prewarm_neighborhoods())
        except Exception:
            app.logger.exception('starting prewarm_neighborhoods failed')
        # start background prewarm of RAG responses for top seeded cities
        try:
            if redis_client and not DISABLE_PREWARM:
                asyncio.create_task(prewarm_rag_responses())
        except Exception:
            app.logger.exception('starting prewarm_rag_responses failed')
        
        # Set redis client for simple_categories
        try:
            from city_guides.src.simple_categories import redis_client as simple_redis_client
            simple_redis_client = redis_client
        except ImportError:
            pass
    except Exception:
        redis_client = None
        app.logger.warning("Redis not available; running without cache")

@app.after_serving
async def shutdown():
    global aiohttp_session, redis_client
    # Cleanup Pixabay service
    try:
        await cleanup_pixabay()
    except Exception:
        pass
    # Cleanup aiohttp and redis
    if aiohttp_session:
        await aiohttp_session.close()
    if redis_client:
        # Some test fakes or third-party clients may not provide an async close
        # method. Call it if available and await if it returns a coroutine.
        close_fn = getattr(redis_client, 'close', None)
        if callable(close_fn):
            try:
                maybe_coro = close_fn()
                if asyncio.iscoroutine(maybe_coro):
                    await maybe_coro
            except Exception:
                app.logger.exception('error closing redis client')

@app.context_processor
def inject_feature_flags():
    return {"GROQ_ENABLED": bool(os.getenv("GROQ_API_KEY"))}

# --- Core Routes ---

@app.route("/", methods=["GET"])
async def index():
    """Serve the React app at root"""
    return await app.send_static_file("index.html")

@app.route("/admin", methods=["GET"])
async def admin_dashboard():
    """Simple admin dashboard for backend visualization"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TravelLand Backend Admin</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
            .status { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
            .status-card { background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; }
            .status-card h3 { margin: 0 0 10px 0; color: #495057; }
            .status-ok { border-left-color: #28a745; }
            .status-error { border-left-color: #dc3545; }
            .api-list { list-style: none; padding: 0; }
            .api-list li { background: #e9ecef; margin: 5px 0; padding: 10px; border-radius: 3px; }
            .api-list a { text-decoration: none; color: #007bff; font-weight: bold; }
            .api-list a:hover { text-decoration: underline; }
            .test-form { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }
            .test-form input, .test-form textarea, .test-form button { margin: 5px; padding: 8px; border: 1px solid #ddd; border-radius: 3px; }
            .test-form button { background: #007bff; color: white; cursor: pointer; }
            .test-form button:hover { background: #0056b3; }
            .test-form button.clear { background: #6c757d; }
            .test-form button.clear:hover { background: #545b62; }
            .test-form button.refresh { background: #28a745; }
            .test-form button.refresh:hover { background: #1e7e34; }
            .response { background: #f8f9fa; padding: 10px; border-radius: 3px; margin: 10px 0; white-space: pre-wrap; font-family: monospace; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 TravelLand Backend Admin</h1>
            
            <div class="status">
                <div class="status-card status-ok">
                    <h3>🟢 Server Status</h3>
                    <p>Backend is running</p>
                    <p>Port: 5010</p>
                </div>
                <div class="status-card">
                    <h3>🔑 API Keys</h3>
                    <p>GROQ: """ + ("✅ Configured" if os.getenv("GROQ_API_KEY") else "❌ Missing") + """</p>
                    <p>Redis: """ + ("✅ Connected" if redis_client else "❌ Not connected") + """</p>
                </div>
                <div class="status-card">
                    <h3>🧠 Marco Memory</h3>
                    <p>History: ❌ Disabled (testing)</p>
                    <p>Cache: ❌ Disabled (testing)</p>
                </div>
            </div>

            <h2>📡 API Endpoints</h2>
            <ul class="api-list">
                <li><a href="/api/health" target="_blank">GET /api/health</a> - Health check</li>
                <li><a href="#test-search">POST /api/search</a> - Venue search (test below)</li>
                <li><a href="#test-marco">POST /api/chat/rag</a> - Marco chat (test below)</li>
                <li><a href="#test-fun-fact">POST /api/fun-fact</a> - Fun facts (test below)</li>
                <li><a href="#test-weather">POST /api/weather</a> - Weather (test below)</li>
                <li><a href="#test-geocode">POST /api/geocode</a> - Geocoding (test below)</li>
                <li><a href="#test-poi">POST /api/poi-discovery</a> - POI discovery (test below)</li>
            </ul>

            <div class="test-form" id="test-mapping">
                <h2>🗺️ Quick Category Mapping Test</h2>
                <p>Test how categories map to POI types instantly</p>
                <form id="mapping-test">
                    <select id="mapping-category" style="width: 200px;">
                        <option value="">Select Category</option>
                        <option value="architecture">🏛️ Architecture</option>
                        <option value="restaurants">🍽️ Restaurants</option>
                        <option value="coffee">☕ Coffee</option>
                        <option value="parks">🌳 Parks</option>
                        <option value="museums">🎨 Museums</option>
                        <option value="historic">🏛️ Historic Sites</option>
                        <option value="tourism">🎯 Tourism</option>
                        <option value="design">✨ Design</option>
                        <option value="buildings">🏢 Buildings</option>
                    </select>
                    <button type="submit">Test Mapping</button>
                </form>
                <div id="mapping-result" style="margin-top: 10px; padding: 10px; background: #e9ecef; border-radius: 3px; display: none;"></div>
            </div>

            <div class="test-form" id="test-marco">
                <h2>🧪 Test Marco Chat</h2>
                <form id="marco-test">
                    <input type="text" id="city" placeholder="City (e.g., Barcelona)" style="width: 150px;">
                    <select id="marco-category" style="width: 150px;">
                        <option value="">Select Category</option>
                        <option value="architecture">🏛️ Architecture & Design</option>
                        <option value="restaurants">🍽️ Restaurants</option>
                        <option value="coffee">☕ Coffee Shops</option>
                        <option value="parks">🌳 Parks</option>
                        <option value="museums">🎨 Museums</option>
                        <option value="historic">🏛️ Historic Sites</option>
                        <option value="tourism">🎯 Things to Do</option>
                    </select>
                    <select id="marco-neighborhood" style="width: 150px;">
                        <option value="">City-wide (no neighborhood)</option>
                        <option value="" disabled>── Load neighborhoods first ──</option>
                    </select>
                    <button type="button" class="load-nh" onclick="loadMarcoNeighborhoods()">Load Neighborhoods</button>
                    <input type="text" id="query" placeholder="Query (auto-generated)" style="width: 300px;">
                    <button type="submit">🎭 Marco Chat</button>
                    <button type="button" class="clear" onclick="clearMarcoForm()">Clear</button>
                    <button type="button" class="refresh" onclick="refreshMarcoResponse()">Refresh</button>
                </form>
                <div id="marco-response" class="response" style="display:none;"></div>
            </div>

            <div class="test-form" id="test-search">
                <h2>🤖 Test Marco Search</h2>
                <form id="search-test">
                    <input type="text" id="search-city" placeholder="City (e.g., Barcelona)" style="width: 150px;">
                    <select id="search-category" style="width: 150px;">
                        <option value="">Select Category</option>
                        <option value="restaurant">🍽️ Restaurants</option>
                        <option value="coffee">☕ Coffee Shops</option>
                        <option value="park">🌳 Parks</option>
                        <option value="historic">🏛️ Historic Sites</option>
                        <option value="museum">🎨 Museums</option>
                        <option value="attractions">🎯 Attractions</option>
                        <option value="tourism">🏛️ Architecture & Tourism</option>
                        <option value="hotel">🏨 Hotels</option>
                        <option value="shopping">🛍️ Shopping</option>
                        <option value="nightlife">🌃 Nightlife</option>
                        <option value="event">🎭 Events</option>
                    </select>
                    <button type="submit">Search</button>
                    <button type="button" class="clear" onclick="clearSearchForm()">Clear</button>
                    <button type="button" class="refresh" onclick="refreshSearchResponse()">Refresh</button>
                </form>
                <div id="search-tools" style="margin: 10px 0; display: none;">
                    <button type="button" class="copy-debug" onclick="copySearchInfo()">📋 Copy Results</button>
                </div>
                <div id="search-response" class="response" style="display:none;"></div>
            </div>

            <div class="test-form" id="test-fun-fact">
                <h2>🎭 Test Fun Fact</h2>
                <form id="fun-fact-test">
                    <input type="text" id="fun-fact-city" placeholder="City (e.g., Barcelona)" style="width: 200px;">
                    <button type="submit">Get Fun Fact</button>
                    <button type="button" class="clear" onclick="clearFunFactForm()">Clear</button>
                    <button type="button" class="refresh" onclick="refreshFunFactResponse()">Refresh</button>
                </form>
                <div id="fun-fact-response" class="response" style="display:none;"></div>
            </div>

            <div class="test-form" id="test-weather">
                <h2>🌤️ Test Weather</h2>
                <form id="weather-test">
                    <input type="text" id="weather-city" placeholder="City (e.g., Barcelona)" style="width: 200px;">
                    <button type="submit">Get Weather</button>
                    <button type="button" class="clear" onclick="clearWeatherForm()">Clear</button>
                    <button type="button" class="refresh" onclick="refreshWeatherResponse()">Refresh</button>
                </form>
                <div id="weather-response" class="response" style="display:none;"></div>
            </div>

            <div class="test-form" id="test-geocode">
                <h2>📍 Test Geocode</h2>
                <form id="geocode-test">
                    <input type="text" id="geocode-location" placeholder="Location (e.g., Barcelona)" style="width: 200px;">
                    <button type="submit">Get Coordinates</button>
                    <button type="button" class="clear" onclick="clearGeocodeForm()">Clear</button>
                    <button type="button" class="refresh" onclick="refreshGeocodeResponse()">Refresh</button>
                </form>
                <div id="geocode-response" class="response" style="display:none;"></div>
            </div>

            <div class="test-form" id="test-guide">
                <h2>📖 Test City/Neighborhood Guide</h2>
                <form id="guide-test">
                    <input type="text" id="guide-city" placeholder="City (e.g., Barcelona)" style="width: 150px;">
                    <select id="guide-neighborhood" style="width: 150px;">
                        <option value="">City-wide guide (no neighborhood)</option>
                        <option value="" disabled>── Load neighborhoods first ──</option>
                    </select>
                    <button type="submit">Generate Guide</button>
                    <button type="button" class="clear" onclick="clearGuideForm()">Clear</button>
                    <button type="button" class="load-nh" onclick="loadGuideNeighborhoods()">Load Neighborhoods</button>
                </form>
                <div id="guide-tools" style="margin: 10px 0; display: none;">
                    <button type="button" class="copy-debug" onclick="copyGuideInfo()">📋 Copy Guide</button>
                </div>
                <div id="guide-response" class="response" style="display:none;"></div>
            </div>

            <div class="test-form" id="test-poi">
                <h2>🗺️ Test POI Discovery</h2>
                <form id="poi-test">
                    <input type="text" id="poi-city" placeholder="City (e.g., Barcelona)" style="width: 150px;">
                    <select id="poi-neighborhood" style="width: 150px;">
                        <option value="">All City (no neighborhood)</option>
                        <option value="" disabled>── Load neighborhoods first ──</option>
                    </select>
                    <select id="poi-type" style="width: 150px;">
                        <option value="">Select POI Type</option>
                        <option value="restaurant">🍽️ Restaurants</option>
                        <option value="coffee">☕ Coffee Shops</option>
                        <option value="park">🌳 Parks</option>
                        <option value="historic">🏛️ Historic Sites</option>
                        <option value="museum">🎨 Museums</option>
                        <option value="attractions">🎯 Attractions</option>
                        <option value="tourism">🏛️ Architecture & Tourism</option>
                        <option value="hotel">🏨 Hotels</option>
                        <option value="shopping">🛍️ Shopping</option>
                        <option value="nightlife">🌃 Nightlife</option>
                        <option value="event">🎭 Events</option>
                    </select>
                    <input type="number" id="poi-limit" placeholder="Limit" value="25" style="width: 80px;">
                    <button type="submit">Discover POIs</button>
                    <button type="button" class="clear" onclick="clearPOIForm()">Clear</button>
                    <button type="button" class="refresh" onclick="refreshPOIResponse()">Refresh</button>
                    <button type="button" class="load-nh" onclick="loadNeighborhoods()">Load Neighborhoods</button>
                </form>
                <div id="poi-tools" style="margin: 10px 0; display: none;">
                    <button type="button" class="copy-debug" onclick="copyDebugInfo()">📋 Copy Debug Info</button>
                    <button type="button" class="scan-dupes" onclick="scanForDuplicates()">🔍 Scan Duplicates</button>
                    <button type="button" class="scan-providers" onclick="scanProviders()">📊 Provider Breakdown</button>
                </div>
                <div id="poi-response" class="response" style="display:none;">
                    <pre id="poi-debug-content"></pre>
                </div>
            </div>
        </div>

        <script>
            // Clear and Refresh Functions
            function clearMarcoForm() {
                document.getElementById('city').value = '';
                document.getElementById('marco-category').value = '';
                document.getElementById('marco-neighborhood').innerHTML = '<option value="">City-wide (no neighborhood)</option><option value="" disabled>── Load neighborhoods first ──</option>';
                document.getElementById('query').value = '';
                document.getElementById('marco-response').style.display = 'none';
            }
            
            // Auto-generate query when category changes
            document.addEventListener('DOMContentLoaded', function() {
                const categorySelect = document.getElementById('marco-category');
                const cityInput = document.getElementById('city');
                const neighborhoodSelect = document.getElementById('marco-neighborhood');
                const queryInput = document.getElementById('query');
                
                function updateQuery() {
                    const city = cityInput.value;
                    const category = categorySelect.value;
                    const neighborhood = neighborhoodSelect.value;
                    
                    console.log(`🔧 Updating query: city="${city}", category="${category}", neighborhood="${neighborhood}"`);
                    
                    if (!city) {
                        queryInput.value = '';
                        return;
                    }
                    
                    if (!category) {
                        queryInput.value = `Tell me about ${city}`;
                        console.log(`📝 Generated query (no category): "${queryInput.value}"`);
                        return;
                    }
                    
                    const categoryMap = {
                        'architecture': 'Architecture & Design',
                        'restaurants': 'restaurants',
                        'coffee': 'coffee shops',
                        'parks': 'parks',
                        'museums': 'museums',
                        'historic': 'historic sites',
                        'tourism': 'things to do'
                    };
                    
                    let newQuery;
                    if (neighborhood) {
                        // Clean neighborhood name to avoid duplication
                        const cleanNeighborhood = neighborhood.replace(/,\s*.*$/, '').trim();
                        newQuery = `Tell me about ${categoryMap[category]} in ${cleanNeighborhood}, ${city}`;
                    } else {
                        newQuery = `Tell me about ${categoryMap[category]} in ${city}`;
                    }
                    
                    // Only update if different to prevent infinite loops
                    if (queryInput.value !== newQuery) {
                        queryInput.value = newQuery;
                        console.log(`📝 Generated query: "${newQuery}"`);
                    }
                }
                
                // Auto-load neighborhoods when category changes (if city is entered)
                categorySelect.addEventListener('change', async function() {
                    const city = cityInput.value;
                    const category = categorySelect.value;
                    
                    if (city && category) {
                        // Show loading state
                        neighborhoodSelect.innerHTML = '<option value="">Loading neighborhoods...</option>';
                        neighborhoodSelect.disabled = true;
                        
                        try {
                            await loadMarcoNeighborhoods();
                        } finally {
                            neighborhoodSelect.disabled = false;
                        }
                    }
                    updateQuery();
                });
                
                neighborhoodSelect.addEventListener('change', updateQuery);
                cityInput.addEventListener('input', function() {
                    // Clear neighborhoods when city changes
                    neighborhoodSelect.innerHTML = '<option value="">City-wide (no neighborhood)</option><option value="" disabled>── Load neighborhoods first ──</option>';
                    updateQuery();
                });
            });
            
            async function loadMarcoNeighborhoods() {
                const city = document.getElementById('city').value;
                const category = document.getElementById('marco-category').value;
                if (!city) {
                    alert('Please enter a city first');
                    return;
                }
                
                console.log(`🔍 Loading neighborhoods for Marco: city="${city}", category="${category}"`);
                
                try {
                    const response = await fetch(`/api/smart-neighborhoods?city=${encodeURIComponent(city)}`);
                    const data = await response.json();
                    
                    console.log('📊 Smart neighborhoods response:', data);
                    
                    if (data.neighborhoods && data.neighborhoods.length > 0) {
                        const select = document.getElementById('marco-neighborhood');
                        select.innerHTML = '<option value="">City-wide (no neighborhood)</option>';
                        
                        // Smart suggestions based on category
                        const categorySuggestions = {
                            'architecture': ['Gothic Quarter', 'El Born', 'Eixample', 'Gràcia'],
                            'restaurants': ['El Born', 'Gothic Quarter', 'Eixample', 'Poble Sec'],
                            'coffee': ['Gothic Quarter', 'El Born', 'Gràcia', 'Eixample'],
                            'museums': ['Gothic Quarter', 'Eixample', 'Montjuïc'],
                            'historic': ['Gothic Quarter', 'El Born', 'Barceloneta', 'Raval'],
                            'tourism': ['Gothic Quarter', 'El Born', 'Eixample', 'Barceloneta'],
                            'parks': ['Eixample', 'Gràcia', 'Park Güell area']
                        };
                        
                        // Get suggestions for this category
                        const suggestions = categorySuggestions[category] || [];
                        console.log(`🎯 Category suggestions for "${category}":`, suggestions);
                        
                        // Add suggested neighborhoods first
                        const suggestedNeighborhoods = [];
                        const otherNeighborhoods = [];
                        
                        data.neighborhoods.forEach(nh => {
                            const name = nh.name || nh;
                            if (suggestions.some(suggestion => name.toLowerCase().includes(suggestion.toLowerCase()))) {
                                suggestedNeighborhoods.push(nh);
                            } else {
                                otherNeighborhoods.push(nh);
                            }
                        });
                        
                        console.log(`✅ Found ${suggestedNeighborhoods.length} suggested, ${otherNeighborhoods.length} other neighborhoods`);
                        
                        // Add suggested neighborhoods with indicator
                        if (suggestedNeighborhoods.length > 0 && category) {
                            const optgroup = document.createElement('optgroup');
                            optgroup.label = `🎯 Suggested for ${category}`;
                            suggestedNeighborhoods.forEach(nh => {
                                const option = document.createElement('option');
                                option.value = nh.name || nh;
                                option.textContent = `⭐ ${nh.name || nh}`;
                                optgroup.appendChild(option);
                            });
                            select.appendChild(optgroup);
                        }
                        
                        // Add other neighborhoods
                        if (otherNeighborhoods.length > 0) {
                            const optgroup = document.createElement('optgroup');
                            optgroup.label = 'All neighborhoods';
                            otherNeighborhoods.forEach(nh => {
                                const option = document.createElement('option');
                                option.value = nh.name || nh;
                                option.textContent = nh.name || nh;
                                optgroup.appendChild(option);
                            });
                            select.appendChild(optgroup);
                        }
                        
                        console.log(`🎉 Successfully loaded ${data.neighborhoods.length} neighborhoods for Marco (${suggestedNeighborhoods.length} suggested for ${category})`);
                    } else {
                        console.log('❌ No neighborhoods found for Marco');
                        const select = document.getElementById('marco-neighborhood');
                        select.innerHTML = '<option value="">City-wide (no neighborhood)</option><option value="" disabled>── No neighborhoods found ──</option>';
                    }
                } catch (error) {
                    console.error('❌ Failed to load neighborhoods for Marco:', error);
                    const select = document.getElementById('marco-neighborhood');
                    select.innerHTML = '<option value="">City-wide (no neighborhood)</option><option value="" disabled>── Failed to load ──</option>';
                    alert('Failed to load neighborhoods');
                }
            }
            function refreshMarcoResponse() {
                const city = document.getElementById('city').value;
                const query = document.getElementById('query').value;
                if (city && query) {
                    document.getElementById('marco-test').dispatchEvent(new Event('submit'));
                }
            }
            
            function clearSearchForm() {
                document.getElementById('search-city').value = '';
                document.getElementById('search-category').value = '';
                document.getElementById('search-response').style.display = 'none';
            }
            function refreshSearchResponse() {
                const city = document.getElementById('search-city').value;
                const category = document.getElementById('search-category').value;
                if (city && category) {
                    document.getElementById('search-test').dispatchEvent(new Event('submit'));
                }
            }
            
            function clearFunFactForm() {
                document.getElementById('fun-fact-city').value = '';
                document.getElementById('fun-fact-response').style.display = 'none';
            }
            function refreshFunFactResponse() {
                const city = document.getElementById('fun-fact-city').value;
                if (city) {
                    document.getElementById('fun-fact-test').dispatchEvent(new Event('submit'));
                }
            }
            
            function clearWeatherForm() {
                document.getElementById('weather-city').value = '';
                document.getElementById('weather-response').style.display = 'none';
            }
            function refreshWeatherResponse() {
                const city = document.getElementById('weather-city').value;
                if (city) {
                    document.getElementById('weather-test').dispatchEvent(new Event('submit'));
                }
            }
            
            function clearGeocodeForm() {
                document.getElementById('geocode-location').value = '';
                document.getElementById('geocode-response').style.display = 'none';
            }
            function refreshGeocodeResponse() {
                const location = document.getElementById('geocode-location').value;
                if (location) {
                    document.getElementById('geocode-test').dispatchEvent(new Event('submit'));
                }
            }
            
            function clearPOIForm() {
                document.getElementById('poi-city').value = '';
                document.getElementById('poi-neighborhood').value = '';
                document.getElementById('poi-type').value = '';
                document.getElementById('poi-limit').value = '25';
                document.getElementById('poi-response').style.display = 'none';
                document.getElementById('poi-tools').style.display = 'none';
                document.getElementById('poi-neighborhood').innerHTML = '<option value="">All City (no neighborhood)</option><option value="" disabled>── Load neighborhoods first ──</option>';
            }
            
            function copyDebugInfo() {
                const debugContent = document.getElementById('poi-response').textContent;
                if (debugContent) {
                    navigator.clipboard.writeText(debugContent).then(() => {
                        // Show success feedback
                        const button = document.querySelector('.copy-debug');
                        const originalText = button.textContent;
                        button.textContent = '✅ Copied!';
                        button.style.background = '#4CAF50';
                        button.style.color = 'white';
                        
                        setTimeout(() => {
                            button.textContent = originalText;
                            button.style.background = '';
                            button.style.color = '';
                        }, 2000);
                    }).catch(err => {
                        console.error('Failed to copy debug info:', err);
                        alert('Failed to copy debug info');
                    });
                }
            }
            
            function scanForDuplicates() {
                const debugContent = document.getElementById('poi-response').textContent;
                if (!debugContent) {
                    alert('No debug content to scan. Run a POI search first.');
                    return;
                }
                
                try {
                    // Extract JSON from response (handle "Status: 200" prefix)
                    let jsonStr = debugContent;
                    if (debugContent.includes('Status:')) {
                        // Find the start of JSON (after status line and newlines)
                        const lines = debugContent.split('\\n');
                        let jsonStart = 0;
                        for (let i = 0; i < lines.length; i++) {
                            if (lines[i].trim().startsWith('{')) {
                                jsonStart = i;
                                break;
                            }
                        }
                        jsonStr = lines.slice(jsonStart).join('\\n');
                    }
                    
                    const data = JSON.parse(jsonStr);
                    const pois = data.pois || [];
                    
                    if (pois.length === 0) {
                        alert('No POIs found to scan for duplicates.');
                        return;
                    }
                    
                    // Find duplicates by name
                    const nameMap = {};
                    const duplicates = [];
                    
                    pois.forEach((poi, index) => {
                        const name = poi.name ? poi.name.toLowerCase().trim() : '';
                        if (name) {
                            if (nameMap[name]) {
                                nameMap[name].push({poi, index});
                            } else {
                                nameMap[name] = [{poi, index}];
                            }
                        }
                    });
                    
                    // Find actual duplicates
                    Object.entries(nameMap).forEach(([name, entries]) => {
                        if (entries.length > 1) {
                            duplicates.push({
                                name: name,
                                count: entries.length,
                                entries: entries
                            });
                        }
                    });
                    
                    if (duplicates.length === 0) {
                        alert('✅ No duplicates found! All ' + pois.length + ' POIs are unique.');
                    } else {
                        let report = '🚨 DUPLICATES FOUND:\\n\\n';
                        report += 'Total POIs: ' + pois.length + '\\n';
                        report += 'Duplicate groups: ' + duplicates.length + '\\n\\n';
                        
                        duplicates.forEach((dup, i) => {
                            report += (i+1) + '. \"' + dup.name + '\" (appears ' + dup.count + ' times)\\n';
                            dup.entries.forEach(entry => {
                                const provider = entry.poi.provider || 'unknown';
                                report += '   - ' + provider + ' (index ' + entry.index + ')\\n';
                            });
                            report += '\\n';
                        });
                        
                        alert(report);
                        console.log('Duplicate scan results:', duplicates);
                    }
                    
                } catch (error) {
                    alert('Error parsing debug content: ' + error.message);
                }
            }
            
            function scanProviders() {
                const debugContent = document.getElementById('poi-response').textContent;
                if (!debugContent) {
                    alert('No debug content to scan. Run a POI search first.');
                    return;
                }
                
                try {
                    // Extract JSON from response (handle "Status: 200" prefix)
                    let jsonStr = debugContent;
                    if (debugContent.includes('Status:')) {
                        // Find the start of JSON (after status line and newlines)
                        const lines = debugContent.split('\\n');
                        let jsonStart = 0;
                        for (let i = 0; i < lines.length; i++) {
                            if (lines[i].trim().startsWith('{')) {
                                jsonStart = i;
                                break;
                            }
                        }
                        jsonStr = lines.slice(jsonStart).join('\\n');
                    }
                    
                    const data = JSON.parse(jsonStr);
                    const pois = data.pois || [];
                    
                    if (pois.length === 0) {
                        alert('No POIs found to analyze providers.');
                        return;
                    }
                    
                    // Count by provider
                    const providerCounts = {};
                    const providerDetails = {};
                    
                    pois.forEach((poi, index) => {
                        const provider = poi.provider || 'unknown';
                        providerCounts[provider] = (providerCounts[provider] || 0) + 1;
                        
                        if (!providerDetails[provider]) {
                            providerDetails[provider] = [];
                        }
                        providerDetails[provider].push({
                            index: index,
                            name: poi.name || 'No name',
                            type: poi.type || 'No type'
                        });
                    });
                    
                    let report = '📊 PROVIDER BREAKDOWN:\\n\\n';
                    report += 'Total POIs: ' + pois.length + '\\n\\n';
                    
                    Object.entries(providerCounts).forEach(([provider, count]) => {
                        const percentage = ((count / pois.length) * 100).toFixed(1);
                        report += provider + ': ' + count + ' POIs (' + percentage + '%)\\n';
                        
                        // Show sample POIs from this provider
                        const samples = providerDetails[provider].slice(0, 3);
                        samples.forEach(sample => {
                            report += '  - ' + sample.name + ' (' + sample.type + ')\\n';
                        });
                        
                        if (providerDetails[provider].length > 3) {
                            report += '  ... and ' + (providerDetails[provider].length - 3) + ' more\\n';
                        }
                        report += '\\n';
                    });
                    
                    alert(report);
                    console.log('Provider breakdown:', providerCounts);
                    
                } catch (error) {
                    alert('Error parsing debug content: ' + error.message);
                }
            }
            function refreshPOIResponse() {
                const city = document.getElementById('poi-city').value;
                const neighborhood = document.getElementById('poi-neighborhood').value;
                const poiType = document.getElementById('poi-type').value;
                const limit = document.getElementById('poi-limit').value;
                if (city && poiType) {
                    document.getElementById('poi-test').dispatchEvent(new Event('submit'));
                }
            }
            
            async function loadNeighborhoods() {
                console.log('loadNeighborhoods() called');
                const city = document.getElementById('poi-city').value;
                console.log('City entered:', city);
                
                if (!city) {
                    console.log('No city entered, showing alert');
                    alert('Please enter a city first');
                    return;
                }
                
                const neighborhoodSelect = document.getElementById('poi-neighborhood');
                console.log('Neighborhood select element found:', neighborhoodSelect);
                
                neighborhoodSelect.innerHTML = '<option value="">Loading neighborhoods...</option>';
                console.log('Set loading state');
                
                try {
                    console.log('Fetching neighborhoods for city:', city);
                    const response = await fetch(`/api/smart-neighborhoods?city=${encodeURIComponent(city)}`);
                    console.log('Response status:', response.status);
                    
                    const data = await response.json();
                    console.log('Response data:', data);
                    
                    if (data.neighborhoods && data.neighborhoods.length > 0) {
                        console.log('Found neighborhoods:', data.neighborhoods.length);
                        let options = '<option value="">All City (no neighborhood)</option>';
                        data.neighborhoods.forEach(nh => {
                            console.log('Adding neighborhood:', nh.name);
                            options += `<option value="${nh.name}">${nh.name}</option>`;
                        });
                        neighborhoodSelect.innerHTML = options;
                        console.log('Updated dropdown with neighborhoods');
                    } else {
                        console.log('No neighborhoods found');
                        neighborhoodSelect.innerHTML = '<option value="">All City (no neighborhood)</option><option value="" disabled>── No neighborhoods found ──</option>';
                    }
                } catch (error) {
                    console.error('Failed to load neighborhoods:', error);
                    neighborhoodSelect.innerHTML = '<option value="">All City (no neighborhood)</option><option value="" disabled>── Failed to load ──</option>';
                }
            }

            // Quick Category Mapping Test
            document.getElementById('mapping-test').addEventListener('submit', (e) => {
                e.preventDefault();
                const category = document.getElementById('mapping-category').value;
                const resultDiv = document.getElementById('mapping-result');
                
                if (!category) {
                    resultDiv.style.display = 'none';
                    return;
                }
                
                // Category mapping (mirrors persistence.py)
                const categoryMapping = {
                    'architecture': { poiType: 'tourism', description: 'Architecture → Tourism (landmarks, historic buildings)' },
                    'restaurants': { poiType: 'restaurant', description: 'Restaurants → Restaurant (all dining)' },
                    'coffee': { poiType: 'cafe', description: 'Coffee → Cafe (coffee shops)' },
                    'parks': { poiType: 'park', description: 'Parks → Park (leisure areas)' },
                    'museums': { poiType: 'museum', description: 'Museums → Museum (cultural sites)' },
                    'historic': { poiType: 'historic', description: 'Historic → Historic (heritage sites)' },
                    'tourism': { poiType: 'tourism', description: 'Tourism → Tourism (attractions)' },
                    'design': { poiType: 'tourism', description: 'Design → Tourism (design landmarks)' },
                    'buildings': { poiType: 'tourism', description: 'Buildings → Tourism (architectural sites)' }
                };
                
                const mapping = categoryMapping[category];
                resultDiv.innerHTML = `
                    <strong>Category:</strong> "${category}"<br>
                    <strong>Maps to POI Type:</strong> "${mapping.poiType}"<br>
                    <em>${mapping.description}</em><br><br>
                    <button type="button" onclick="testMappedCategory('${category}', '${mapping.poiType}')" style="margin-right: 5px;">Test with POI Discovery</button>
                    <button type="button" onclick="testMarcoCategory('${category}')" style="margin-right: 5px;">Test with Marco Search</button>
                    <button type="button" onclick="testMarcoChat('${category}')" style="margin-right: 5px;">Test with Marco Chat</button>
                `;
                resultDiv.style.display = 'block';
            });
            
            function testMappedCategory(category, poiType) {
                // Get city from Marco Search form, fallback to POI Discovery city
                const searchCity = document.getElementById('search-city').value || document.getElementById('poi-city').value || 'barcelona';
                // Fill in POI Discovery form with mapped values
                document.getElementById('poi-city').value = searchCity;
                document.getElementById('poi-type').value = poiType;
                // Scroll to POI Discovery section
                document.getElementById('test-poi').scrollIntoView({ behavior: 'smooth' });
            }
            
            function testMarcoCategory(category) {
                // Get city and neighborhood from POI Discovery form, fallback to Marco Search city
                const searchCity = document.getElementById('poi-city').value || document.getElementById('search-city').value || 'barcelona';
                const searchNeighborhood = document.getElementById('poi-neighborhood').value || '';
                
                // Fill in Marco Search form with mapped values
                document.getElementById('search-city').value = searchCity;
                document.getElementById('search-category').value = category;
                // Scroll to Marco Search section
                document.getElementById('test-search').scrollIntoView({ behavior: 'smooth' });
            }
            
            function testMarcoChat(category) {
                // Get city and neighborhood from Marco Chat form first
                const searchCity = document.getElementById('city').value || document.getElementById('search-city').value || document.getElementById('poi-city').value || 'barcelona';
                const searchNeighborhood = document.getElementById('marco-neighborhood').value || document.getElementById('poi-neighborhood').value || '';
                
                // Fill in Marco Chat form with architecture-specific query
                const queryMap = {
                    'architecture': searchNeighborhood 
                        ? `Tell me about Architecture & Design in ${searchNeighborhood}, ${searchCity}`
                        : `Tell me about Architecture & Design in ${searchCity}`,
                    'restaurants': searchNeighborhood
                        ? `Best restaurants in ${searchNeighborhood}, ${searchCity}`
                        : `Best restaurants in ${searchCity}`,
                    'coffee': searchNeighborhood
                        ? `Find coffee shops in ${searchNeighborhood}, ${searchCity}`
                        : `Find coffee shops in ${searchCity}`,
                    'parks': searchNeighborhood
                        ? `What parks should I visit in ${searchNeighborhood}, ${searchCity}?`
                        : `What parks should I visit in ${searchCity}?`,
                    'museums': searchNeighborhood
                        ? `What museums should I visit in ${searchNeighborhood}, ${searchCity}?`
                        : `What museums should I visit in ${searchCity}?`,
                    'historic': searchNeighborhood
                        ? `Historic sites in ${searchNeighborhood}, ${searchCity}`
                        : `Historic sites in ${searchCity}`,
                    'tourism': searchNeighborhood
                        ? `Things to do in ${searchNeighborhood}, ${searchCity}`
                        : `Things to do in ${searchCity}`,
                    'design': searchNeighborhood
                        ? `Design and architecture in ${searchNeighborhood}, ${searchCity}`
                        : `Design and architecture in ${searchCity}`,
                    'buildings': searchNeighborhood
                        ? `Famous buildings in ${searchNeighborhood}, ${searchCity}`
                        : `Famous buildings in ${searchCity}`
                };
                
                document.getElementById('city').value = searchCity;
                document.getElementById('query').value = queryMap[category] || `Tell me about ${category} in ${searchNeighborhood ? searchNeighborhood + ', ' : ''}${searchCity}`;
                // Scroll to Marco Chat section
                document.getElementById('test-marco').scrollIntoView({ behavior: 'smooth' });
            }

            // Marco Chat Test with preset queries
            const presetQueries = [
                { query: "Tell me about Architecture & Design in El Born, Barcelona", desc: "Architecture" },
                { query: "Best restaurants in Barcelona", desc: "Restaurants" },
                { query: "Find coffee shops near me", desc: "Coffee" },
                { query: "What museums should I visit in Barcelona?", desc: "Museums" },
                { query: "Historic sites in Barcelona", desc: "Historic" },
                { query: "Things to do in Barcelona", desc: "Tourism" }
            ];
            
            // Add preset query buttons to Marco Chat
            const marcoForm = document.getElementById('marco-test');
            const presetDiv = document.createElement('div');
            presetDiv.style.margin = '10px 0';
            presetDiv.innerHTML = '<strong>Quick Tests:</strong> ' + 
                presetQueries.map((p, i) => `<button type="button" onclick="runPresetQuery(${i})" style="font-size: 12px; padding: 4px 8px; margin: 2px;">${p.desc}</button>`).join('');
            marcoForm.appendChild(presetDiv);
            
            function runPresetQuery(index) {
                const preset = presetQueries[index];
                // Use actual city and neighborhood from the form
                const city = document.getElementById('city').value;
                const neighborhood = document.getElementById('marco-neighborhood').value;
                
                if (!city) {
                    alert('Please enter a city first');
                    return;
                }
                
                // Set the category based on preset
                const categoryMap = {
                    'Architecture': 'architecture',
                    'Restaurants': 'restaurants',
                    'Coffee': 'coffee',
                    'Museums': 'museums',
                    'Historic': 'historic',
                    'Tourism': 'tourism'
                };
                
                const category = categoryMap[preset.desc];
                if (category) {
                    document.getElementById('marco-category').value = category;
                }
                
                // Trigger query update
                const event = new Event('change');
                document.getElementById('marco-category').dispatchEvent(event);
                
                // Submit the form
                document.getElementById('marco-test').dispatchEvent(new Event('submit'));
            }

            document.getElementById('marco-test').addEventListener('submit', async (e) => {
                e.preventDefault();
                const city = document.getElementById('city').value;
                const query = document.getElementById('query').value;
                const responseDiv = document.getElementById('marco-response');
                
                try {
                    responseDiv.style.display = 'block';
                    responseDiv.textContent = 'Testing...';
                    
                    const resp = await fetch('/api/chat/rag', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query, city, history: [] })
                    });
                    
                    const data = await resp.json();
                    const jsonText = 'Status: ' + resp.status + '\\n\\n' + JSON.stringify(data, null, 2);
                    responseDiv.textContent = jsonText;
                    
                    // Make Google Maps links clickable
                    setTimeout(() => {
                        const clickableText = jsonText.replace(
                            /(https:\/\/www\.google\.com\/maps\/search\/\?api=1&query=[^\s"]+)/g,
                            '<a href="$1" target="_blank" style="color: #007bff; text-decoration: underline; cursor: pointer;">📍 $1</a>'
                        );
                        responseDiv.innerHTML = '<pre style="white-space: pre-wrap; word-break: break-all;">' + clickableText.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/&lt;a href=/g, '<a href=').replace(/&lt;\/a&gt;/g, '</a>') + '</pre>';
                    }, 50);
                } catch (error) {
                    responseDiv.textContent = 'Error: ' + error.message;
                }
            });

function copyMarcoInfo() {
    const marcoContent = document.getElementById('marco-response').textContent;
    if (marcoContent) {
        navigator.clipboard.writeText(marcoContent).then(() => {
            const button = document.querySelector('#marco-tools .copy-debug');
            const originalText = button.textContent;
            button.textContent = '✅ Copied!';
            button.style.background = '#4CAF50';
            button.style.color = 'white';
            
            setTimeout(() => {
                button.textContent = originalText;
                button.style.background = '';
                button.style.color = '';
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy Marco info:', err);
            alert('Failed to copy Marco info');
        });
    }
}

            // Weather Test
            document.getElementById('weather-test').addEventListener('submit', async (e) => {
                e.preventDefault();
                const city = document.getElementById('weather-city').value;
                const responseDiv = document.getElementById('weather-response');
                
                try {
                    responseDiv.style.display = 'block';
                    responseDiv.textContent = 'Getting weather...';
                    
                    const resp = await fetch('/api/weather', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ city })
                    });
                    
                    const data = await resp.json();
                    const jsonText = 'Status: ' + resp.status + '\\n\\n' + JSON.stringify(data, null, 2);
                    responseDiv.textContent = jsonText;
                    
                    // Make Google Maps links clickable
                    setTimeout(() => {
                        const clickableText = jsonText.replace(
                            /(https:\/\/www\.google\.com\/maps\/search\/\?api=1&query=[^\s"]+)/g,
                            '<a href="$1" target="_blank" style="color: #007bff; text-decoration: underline; cursor: pointer;">📍 $1</a>'
                        );
                        responseDiv.innerHTML = '<pre style="white-space: pre-wrap; word-break: break-all;">' + clickableText.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/&lt;a href=/g, '<a href=').replace(/&lt;\/a&gt;/g, '</a>') + '</pre>';
                    }, 50);
                } catch (error) {
                    responseDiv.textContent = 'Error: ' + error.message;
                }
            });

            // Geocode Test
            document.getElementById('geocode-test').addEventListener('submit', async (e) => {
                e.preventDefault();
                const location = document.getElementById('geocode-location').value;
                const responseDiv = document.getElementById('geocode-response');
                
                try {
                    responseDiv.style.display = 'block';
                    responseDiv.textContent = 'Geocoding...';
                    
                    const resp = await fetch('/api/geocode', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: location })
                    });
                    
                    const data = await resp.json();
                    const jsonText = 'Status: ' + resp.status + '\\n\\n' + JSON.stringify(data, null, 2);
                    responseDiv.textContent = jsonText;
                    
                    // Make Google Maps links clickable
                    setTimeout(() => {
                        const clickableText = jsonText.replace(
                            /(https:\/\/www\.google\.com\/maps\/search\/\?api=1&query=[^\s"]+)/g,
                            '<a href="$1" target="_blank" style="color: #007bff; text-decoration: underline; cursor: pointer;">📍 $1</a>'
                        );
                        responseDiv.innerHTML = '<pre style="white-space: pre-wrap; word-break: break-all;">' + clickableText.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/&lt;a href=/g, '<a href=').replace(/&lt;\/a&gt;/g, '</a>') + '</pre>';
                    }, 50);
                } catch (error) {
                    responseDiv.textContent = 'Error: ' + error.message;
                }
            });

            // POI Discovery Test
            document.getElementById('poi-test').addEventListener('submit', async (e) => {
                e.preventDefault();
                const city = document.getElementById('poi-city').value;
                const neighborhood = document.getElementById('poi-neighborhood').value;
                const poiType = document.getElementById('poi-type').value;
                const limit = document.getElementById('poi-limit').value;
                const responseDiv = document.getElementById('poi-response');
                
                try {
                    responseDiv.style.display = 'block';
                    document.getElementById('poi-tools').style.display = 'block';
                    responseDiv.textContent = '[Discovering] POIs for ' + city + ' (' + (neighborhood || 'city-wide') + ') - Type: ' + poiType + ' - Limit: ' + limit;
                    responseDiv.textContent += '\\n[Category] Using POI type: ' + poiType;
                    
                    // Call real POI API with neighborhood support
                    const requestBody = { 
                        city, 
                        poi_type: poiType, 
                        limit: parseInt(limit) || 10 
                    };
                    
                    // Add neighborhood if provided
                    if (neighborhood && neighborhood.trim()) {
                        requestBody.neighborhood = neighborhood.trim();
                        responseDiv.textContent += '\\n[Neighborhood] ' + neighborhood;
                    }
                    
                    responseDiv.textContent += '\\n[API] Calling...';
                    
                    const resp = await fetch('/api/poi-discovery', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(requestBody)
                    });
                    
                    responseDiv.textContent += ' Status: ' + resp.status + ' - Processing response...';
                    
                    const data = await resp.json();
                    const debugContent = 'Status: ' + resp.status + '\\n\\n' + JSON.stringify(data, null, 2);
                    
                    // Display debug content directly in response div
                    responseDiv.textContent = debugContent;
                } catch (error) {
                    responseDiv.textContent = 'Error: ' + error.message + '\\n\\n' + error.stack;
                }
            });

            // City/Neighborhood Guide Test
            document.getElementById('guide-test').addEventListener('submit', async (e) => {
                e.preventDefault();
                const city = document.getElementById('guide-city').value;
                const neighborhood = document.getElementById('guide-neighborhood').value;
                const responseDiv = document.getElementById('guide-response');
                
                try {
                    responseDiv.style.display = 'block';
                    document.getElementById('guide-tools').style.display = 'block';
                    responseDiv.textContent = 'Generating guide for ' + city + (neighborhood ? ' / ' + neighborhood : '') + '...';
                    
                    const resp = await fetch('/api/generate_quick_guide', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ city, neighborhood })
                    });
                    
                    const data = await resp.json();
                    const jsonText = 'Status: ' + resp.status + '\\n\\n' + JSON.stringify(data, null, 2);
                    responseDiv.textContent = jsonText;
                    
                    // Make Google Maps links clickable
                    setTimeout(() => {
                        const clickableText = jsonText.replace(
                            /(https:\/\/www\.google\.com\/maps\/search\/\?api=1&query=[^\s"]+)/g,
                            '<a href="$1" target="_blank" style="color: #007bff; text-decoration: underline; cursor: pointer;">📍 $1</a>'
                        );
                        responseDiv.innerHTML = '<pre style="white-space: pre-wrap; word-break: break-all;">' + clickableText.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/&lt;a href=/g, '<a href=').replace(/&lt;\/a&gt;/g, '</a>') + '</pre>';
                    }, 50);
                } catch (error) {
                    responseDiv.textContent = 'Error: ' + error.message;
                }
            });
            
            function clearGuideForm() {
                document.getElementById('guide-city').value = '';
                document.getElementById('guide-neighborhood').innerHTML = '<option value="">City-wide guide (no neighborhood)</option><option value="" disabled>── Load neighborhoods first ──</option>';
                document.getElementById('guide-response').style.display = 'none';
                document.getElementById('guide-tools').style.display = 'none';
            }
            
            async function loadGuideNeighborhoods() {
                const city = document.getElementById('guide-city').value;
                if (!city) {
                    alert('Please enter a city first');
                    return;
                }
                
                try {
                    console.log('Loading neighborhoods for guide:', city);
                    const response = await fetch(`/api/smart-neighborhoods?city=${encodeURIComponent(city)}`);
                    const data = await response.json();
                    
                    if (data.neighborhoods && data.neighborhoods.length > 0) {
                        const select = document.getElementById('guide-neighborhood');
                        // Keep the first option
                        select.innerHTML = '<option value="">City-wide guide (no neighborhood)</option>';
                        
                        data.neighborhoods.forEach(nh => {
                            const option = document.createElement('option');
                            option.value = nh.name || nh;
                            option.textContent = nh.name || nh;
                            select.appendChild(option);
                        });
                        console.log(`Loaded ${data.neighborhoods.length} neighborhoods for guide`);
                    } else {
                        console.log('No neighborhoods found for guide');
                        alert('No neighborhoods found for this city');
                    }
                } catch (error) {
                    console.error('Failed to load neighborhoods for guide:', error);
                    alert('Failed to load neighborhoods');
                }
            }
            
            function copyGuideInfo() {
                const guideContent = document.getElementById('guide-response').textContent;
                if (guideContent) {
                    navigator.clipboard.writeText(guideContent).then(() => {
                        const button = document.querySelector('#guide-tools .copy-debug');
                        const originalText = button.textContent;
                        button.textContent = '✅ Copied!';
                        button.style.background = '#4CAF50';
                        button.style.color = 'white';
                        
                        setTimeout(() => {
                            button.textContent = originalText;
                            button.style.background = '';
                            button.style.color = '';
                        }, 2000);
                    }).catch(err => {
                        console.error('Failed to copy guide info:', err);
                        alert('Failed to copy guide info');
                    });
                }
            }
        </script>
    </body>
    </html>
    """

@app.route('/api/poi-discovery', methods=['POST'])
async def api_poi_discovery():
    """POI discovery endpoint for testing Points of Interest"""
    debug_info = []
    
    try:
        data = await request.get_json(force=True) or {}
        city = data.get('city', '').strip()
        neighborhood = data.get('neighborhood', '').strip()
        poi_type = data.get('poi_type', '').strip()
        limit = data.get('limit', 10)
        
        debug_info.append(f"🔍 Request: city='{city}', neighborhood='{neighborhood}', poi_type='{poi_type}', limit={limit}")
        
        if not city:
            debug_info.append("❌ Error: city required")
            return jsonify({"error": "city required", "debug": debug_info}), 400
        
        try:
            limit = int(limit)
        except Exception:
            limit = 25
            debug_info.append("⚠️ Invalid limit, using default: 25")
        
        # Import POI discovery functions
        debug_info.append("📦 Importing multi_provider...")
        from providers.multi_provider import async_discover_pois
        
        # Discover POIs using real API
        debug_info.append(f"🚀 Calling discover_pois for {city}...")
        
        # Handle neighborhood-specific search
        bbox = None
        if neighborhood:
            debug_info.append(f"🏘️ Neighborhood specified: {neighborhood}")
            try:
                # Try to geocode the neighborhood to get its bbox
                from providers.overpass_provider import geocode_city
                
                neighborhood_coords = await geocode_city(f"{neighborhood}, {city}")
                if neighborhood_coords:
                    # Overpass geocode_city returns bbox tuple: (min_lon, min_lat, max_lon, max_lat)
                    if isinstance(neighborhood_coords, tuple) and len(neighborhood_coords) == 4:
                        # Use the bbox directly from geocoding
                        bbox = neighborhood_coords
                        debug_info.append(f"📍 Using neighborhood bbox: {bbox}")
                        debug_info.append(f"🗺️ Neighborhood bbox from geocoding")
                    elif isinstance(neighborhood_coords, tuple) and len(neighborhood_coords) == 2:
                        # Handle lat/lon tuple format
                        nh_lat, nh_lon = neighborhood_coords
                        radius = 0.005  # ~500m radius
                        bbox = (
                            nh_lon - radius,  # min_lon
                            nh_lat - radius,  # min_lat  
                            nh_lon + radius,  # max_lon
                            nh_lat + radius   # max_lat
                        )
                        debug_info.append(f"📍 Using neighborhood bbox: {bbox}")
                        debug_info.append(f"🗺️ Neighborhood coords: {neighborhood_coords}")
                    else:
                        # Handle dictionary format
                        nh_lat = neighborhood_coords.get('lat')
                        nh_lon = neighborhood_coords.get('lon')
                        if nh_lat and nh_lon:
                            radius = 0.005  # ~500m radius
                            bbox = (
                                nh_lon - radius,  # min_lon
                                nh_lat - radius,  # min_lat  
                                nh_lon + radius,  # max_lon
                                nh_lat + radius   # max_lat
                            )
                            debug_info.append(f"📍 Using neighborhood bbox: {bbox}")
                            debug_info.append(f"🗺️ Neighborhood coords: {neighborhood_coords}")
                        else:
                            debug_info.append("⚠️ Neighborhood geocoded but missing coordinates")
                else:
                    debug_info.append(f"⚠️ Failed to geocode neighborhood: {neighborhood}")
                    debug_info.append("🌍 Falling back to city-wide search")
            except Exception as e:
                debug_info.append(f"⚠️ Neighborhood geocoding error: {e}")
                debug_info.append("🌍 Falling back to city-wide search")
        else:
            debug_info.append("🌍 City-wide search (no neighborhood specified)")
        
        # Capture provider debug info
        import sys
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            pois = await async_discover_pois(
                city=city,
                poi_type=poi_type or 'attractions',
                limit=limit,
                bbox=bbox
            )
        finally:
            sys.stdout = old_stdout
            provider_debug = captured_output.getvalue()
            if provider_debug:
                debug_info.append("📊 Provider debug:")
                for line in provider_debug.strip().split('\n')[:10]:  # Limit to 10 lines
                    if line.strip():
                        debug_info.append(f"   {line.strip()}")
        
        debug_info.append(f"✅ Found {len(pois)} POIs")
        
        if pois:
            debug_info.append(f"📋 Sample POI: {pois[0].get('name', 'Unknown')}")
        
        return jsonify({
            "city": city,
            "neighborhood": neighborhood if neighborhood else None,
            "poi_type": poi_type,
            "count": len(pois),
            "pois": pois[:limit],
            "debug": debug_info
        })
        
    except Exception as e:
        debug_info.append(f"💥 Error: {str(e)}")
        app.logger.exception('POI discovery failed')
        return jsonify({"error": "poi_discovery_failed", "details": str(e), "debug": debug_info}), 500

@app.route("/<path:path>", methods=["GET"])
async def catch_all(path):
    # Serve React app for client-side routing
    if path.startswith("api/") or path.startswith("static/"):
        # Let Quart handle API and static routes normally
        from quart import abort
        abort(404)
    return await app.send_static_file("index.html")

@app.route("/api/weather", methods=["POST"])
async def weather():
    payload = await request.get_json(silent=True) or {}
    city = (payload.get("city") or "").strip()
    lat = payload.get("lat")
    lon = payload.get("lon")
    if not (lat and lon):
        if not city:
            return jsonify({"error": "city or lat/lon required"}), 400
        result = await geocode_city(city)
        if not result:
            return jsonify({"error": "geocode_failed"}), 400
        lat = result['lat']
        lon = result['lon']
    weather = await get_weather_async(lat, lon)
    if weather is None:
        return jsonify({"error": "weather_fetch_failed"}), 500
    return jsonify({"lat": lat, "lon": lon, "city": city, "weather": weather})

# REMOVED: /api/neighborhoods endpoint 
# Use /api/smart-neighborhoods instead - it's superior:
# - Works for ANY city globally (no hardcoded lists)
# - Uses dynamic Overpass API calls  
# - Better error handling and fallbacks
# - More comprehensive neighborhood data

@app.route('/api/reverse_lookup', methods=['POST'])
async def reverse_lookup():
    """Reverse lookup coordinates to structured location info.
    POST payload: { lat: number, lon: number }
    Returns: { display_name, countryName, countryCode, stateName, cityName, neighborhoods: [] }
    """
    payload = await request.get_json(silent=True) or {}
    lat = payload.get('lat')
    lon = payload.get('lon')
    if lat is None or lon is None:
        return jsonify({'error': 'lat and lon required'}), 400

    # debug flag (opt-in) to return raw provider responses for troubleshooting
    debug_flag = (request.args.get('debug') == '1') or bool(payload.get('debug'))

    # Attempt structured reverse geocode (best-effort)
    addr = None
    country_code = None
    country_name = state_name = city_name = None
    raw_geoapify = None
    raw_nominatim = None

    # Prefer structured Geoapify response when available (gives country_code/state/city)
    geoapify_reverse_geocode_raw = None
    async_reverse_geocode = None
    try:
        import importlib
        mod = importlib.import_module('city_guides.providers.overpass_provider')
        geoapify_reverse_geocode_raw = getattr(mod, 'geoapify_reverse_geocode_raw', None)
        async_reverse_geocode = getattr(mod, 'async_reverse_geocode', None)
        if geoapify_reverse_geocode_raw and callable(geoapify_reverse_geocode_raw):
            result = geoapify_reverse_geocode_raw(float(lat), float(lon), session=aiohttp_session)
            # Check if result is a coroutine before awaiting
            if asyncio.iscoroutine(result):
                props = await result
            else:
                props = result
            if props and isinstance(props, dict):
                raw_geoapify = props
                app.logger.debug('geoapify_reverse_geocode_raw returned properties: %s', {k: props.get(k) for k in ['country_code','country','state','city']})
                addr = props.get('formatted') or props.get('address_line') or ''
                # Geoapify provides ISO country code as 'country_code' (lowercase) so normalize to upper
                cc = props.get('country_code') or props.get('countryCode')
                if cc:
                    country_code = cc.upper()
                # Try to get state and city from structured properties
                state_name = props.get('state') or props.get('state_district') or state_name
                city_name = props.get('city') or props.get('town') or props.get('village') or city_name
                country_name = props.get('country') or country_name
            else:
                app.logger.debug('geoapify_reverse_geocode_raw returned no properties')
        else:
            app.logger.debug('geoapify reverse geocode function not available')
    except (ImportError, AttributeError):
        app.logger.debug('geoapify_reverse_geocode_raw not available in overpass_provider')
    except Exception:
        app.logger.exception('geoapify reverse geocode lookup failed')

    # Fallback to older Nominatim-based reverse geocode (formatted string parsing)
    if not addr:
        try:
            # async_reverse_geocode may have been loaded above via importlib
            if not callable(async_reverse_geocode):
                import importlib
                mod = importlib.import_module('city_guides.providers.overpass_provider')
                async_reverse_geocode = getattr(mod, 'async_reverse_geocode', None)
            if callable(async_reverse_geocode):
                result = async_reverse_geocode(float(lat), float(lon), session=aiohttp_session)
                # Check if result is a coroutine before awaiting
                if asyncio.iscoroutine(result):
                    addr = await result
                else:
                    addr = result
                raw_nominatim = addr
                app.logger.debug('async_reverse_geocode returned: %s', addr)
            else:
                app.logger.debug('async_reverse_geocode not available')
        except (ImportError, AttributeError):
            app.logger.debug('async_reverse_geocode not available in overpass_provider')
            addr = None
        except Exception:
            app.logger.exception('async_reverse_geocode failed')
            addr = None

        if addr and isinstance(addr, str):
            parts = [p.strip() for p in addr.split(',') if p.strip()]
            if parts:
                country_name = parts[-1]
                if len(parts) >= 2:
                    state_name = parts[-2]
                if len(parts) >= 3:
                    city_name = parts[-3]
    # If we don't have an ISO country code from Geoapify, try to match by name (legacy)
    if not country_code:
        try:
            countries = await _get_countries()
            for c in countries:
                cname = (c.get('name') or '').lower()
                if country_name and (country_name.lower() in cname or cname in country_name.lower()):
                    country_code = c.get('code') or c.get('id')
                    break
        except Exception:
            app.logger.exception('_get_countries failed')

    # If we made no progress, return a helpful error for debugging
    if not addr and not country_code and not country_name:
        app.logger.warning('reverse_lookup failed to derive any location info for coords %s,%s', lat, lon)
        return jsonify({'error': 'reverse_lookup_failed', 'message': 'Could not determine location from coordinates'}), 502

    # Fetch nearby neighborhoods
    nb = []
    try:
        nb = await multi_provider.async_get_neighborhoods(city=None, lat=float(lat), lon=float(lon), lang='en', session=aiohttp_session)
    except Exception:
        app.logger.exception('neighborhoods lookup failed in reverse_lookup')
        nb = []

    # Normalize neighborhoods
    nb_norm = []
    for n in nb:
        try:
            nb_norm.append({'id': n.get('id') or n.get('name') or n.get('label'), 'name': n.get('name') or n.get('display_name') or n.get('label') or n.get('id')})
        except Exception:
            continue

    response = {
        'display_name': addr,
        'countryName': country_name,
        'countryCode': country_code,
        'stateName': state_name,
        'cityName': city_name,
        'neighborhoods': nb_norm
    }

    if debug_flag:
        response['debug'] = {
            'geoapify_props': raw_geoapify,
            'nominatim_addr': raw_nominatim
        }

    return jsonify(response)

@app.route('/healthz')
async def healthz():
    """Lightweight health endpoint returning component status."""
    status = {
        'app': 'ok',
        'time': time.time(),
        'ready': bool(aiohttp_session is not None),
        'redis': bool(redis_client is not None),
        'geoapify': bool(os.getenv('GEOAPIFY_API_KEY')),
        'geonames': bool(os.getenv('GEONAMES_USERNAME'))
    }
    return jsonify(status)

@app.route('/api/health')
async def api_health():
    """API health endpoint for admin dashboard."""
    status = {
        'app': 'ok',
        'time': time.time(),
        'ready': bool(aiohttp_session is not None),
        'redis': bool(redis_client is not None),
        'groq': bool(os.getenv('GROQ_API_KEY')),
        'geoapify': bool(os.getenv('GEOAPIFY_API_KEY')),
        'geonames': bool(os.getenv('GEONAMES_USERNAME'))
    }
    return jsonify(status)


@app.route('/metrics/json')
async def metrics_json():
    """Return simple JSON metrics (counters and latency summaries)"""
    try:
        metrics = await get_metrics_dict()
        return jsonify(metrics)
    except Exception:
        app.logger.exception('Failed to get metrics')
        return jsonify({'error': 'failed to fetch metrics'}), 500

@app.route('/smoke')
async def smoke():
    """Run a small end-to-end smoke check: reverse lookup + neighborhoods fetch.

    Returns JSON { ok: bool, details: {...} }
    """
    out = {'ok': False, 'details': {}}
    # pick a stable test coordinate (Tlaquepaque center as representative)
    lat = 20.58775
    lon = -103.30449
    try:
        # Reverse lookup
        try:
            import importlib
            mod = importlib.import_module('city_guides.providers.overpass_provider')
            geoapify_reverse_geocode_raw = getattr(mod, 'geoapify_reverse_geocode_raw', None)
            async_reverse_geocode = getattr(mod, 'async_reverse_geocode', None)
            
            addr = None
            props = None
            if geoapify_reverse_geocode_raw and callable(geoapify_reverse_geocode_raw):
                result = geoapify_reverse_geocode_raw(lat, lon, session=aiohttp_session)
                if asyncio.iscoroutine(result):
                    props = await result
                else:
                    props = result
                if props and isinstance(props, dict):
                    addr = props.get('formatted') or ''
            
            if not addr and async_reverse_geocode and callable(async_reverse_geocode):
                result = async_reverse_geocode(lat, lon, session=aiohttp_session)
                if asyncio.iscoroutine(result):
                    addr = await result
                else:
                    addr = result
        except Exception:
            addr = None
            props = None
        out['details']['reverse'] = {'display_name': addr or '', 'props': bool(props)}

        # Neighborhoods
        try:
            nb = await multi_provider.async_get_neighborhoods(city=None, lat=lat, lon=lon, lang='en', session=aiohttp_session)
            out['details']['neighborhoods_count'] = len(nb)
        except Exception as e:
            out['details']['neighborhoods_error'] = str(e)
            out['details']['neighborhoods_count'] = 0

        # If reverse lookup or neighborhoods returned anything, consider smoke OK
        if (addr and isinstance(addr, str) and addr.strip()) or out['details'].get('neighborhoods_count', 0) > 0:
            out['ok'] = True
    except Exception as e:
        out['details']['exception'] = str(e)
    return jsonify(out)

@app.route('/api/countries')
async def api_countries():
    """Get list of countries for frontend dropdown"""
    try:
        countries = await _get_countries()
        return jsonify(countries)
    except Exception:
        app.logger.exception('Failed to get countries')
        return jsonify([])

@app.route('/api/neighborhoods/<country_code>')
async def api_neighborhoods_country(country_code):
    """Get neighborhoods for all cities in a country from seed data"""
    try:
        # Map country codes to full names for seed files
        country_map = {
            'fr': 'france',
            'es': 'spain',
            'it': 'italy',
            'de': 'germany',
            'gb': 'uk',
            'us': 'usa',
        }
        file_name = country_map.get(country_code.lower(), country_code.lower())
        data_path = Path(__file__).parent.parent / 'data' / f'{file_name}.json'
        if data_path.exists():
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data.get('cities', {}))
        return jsonify({})
    except Exception:
        app.logger.exception('Failed to load neighborhoods for %s', country_code)
        return jsonify({})

@app.route('/api/locations/states')
async def api_states():
    """Get list of states/provinces for a country using GeoNames API"""
    country_code = request.args.get('countryCode', '')
    
    if not country_code:
        return jsonify([])
    
    geonames_user = os.getenv("GEONAMES_USERNAME")
    if not geonames_user:
        # Fallback to hardcoded data if no GeoNames username
        return jsonify([])
    
    try:
        # First, get the country's geonameId
        async with get_session() as session:
            # Get country info to find geonameId
            country_url = "http://api.geonames.org/searchJSON"
            country_params = {
                "q": country_code,
                "featureClass": "A",
                "featureCode": "PCLI",
                "maxRows": 5,  # Get more results to find the right one
                "username": geonames_user
            }
            
            async with session.get(country_url, params=country_params, timeout=ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return jsonify([])
                
                country_data = await resp.json()
                if not country_data.get('geonames'):
                    return jsonify([])
                
                # Find the exact country match
                country_geoname_id = None
                for country in country_data['geonames']:
                    # Check if this is the right country by country code or name
                    if (country.get('countryCode', '').upper() == country_code.upper() or 
                        country.get('name', '').lower() == country_code.lower()):
                        country_geoname_id = country['geonameId']
                        break
                
                if not country_geoname_id:
                    return jsonify([])
                
                # Get children (states/provinces) of the country
                children_url = "http://api.geonames.org/childrenJSON"
                children_params = {
                    "geonameId": country_geoname_id,
                    "featureClass": "A",
                    "maxRows": 100,
                    "username": geonames_user
                }
                
                async with session.get(children_url, params=children_params, timeout=ClientTimeout(total=10)) as children_resp:
                    if children_resp.status != 200:
                        return jsonify([])
                    
                    children_data = await children_resp.json()
                    
                    states = []
                    for child in children_data.get('geonames', []):
                        # Filter for administrative divisions (ADM1, ADM2)
                        if child.get('fcode') in ['ADM1', 'ADM2']:
                            states.append({
                                "code": child.get('adminCode1', child.get('adminCode2', '')),
                                "name": child.get('name', ''),
                                "geonameId": child.get('geonameId', '')
                            })
                    
                    return jsonify(states)
                    
    except Exception:
        app.logger.exception('Failed to fetch states from GeoNames')
        return jsonify([])

@app.route('/api/locations/cities')
async def api_cities():
    """Get list of cities for a country and state using GeoNames API"""
    country_code = request.args.get('countryCode', '')
    state_code = request.args.get('stateCode', '')
    
    if not country_code or not state_code:
        return jsonify([])
    
    geonames_user = os.getenv("GEONAMES_USERNAME")
    if not geonames_user:
        # Fallback to centralized seed file if no GeoNames username
        try:
            seed_path = Path(__file__).parent.parent / 'data' / 'seeded_cities.json'
            if seed_path.exists():
                seed = json.loads(seed_path.read_text())
                cities_data = seed.get('cities', [])
                # Filter by country and state if provided
                if country_code:
                    cities_data = [c for c in cities_data if (c.get('countryCode') or '').upper() == country_code.upper()]
                if state_code:
                    cities_data = [c for c in cities_data if (c.get('stateCode') or '').upper() == state_code.upper()]
                # Deduplicate by (name, countryCode, stateCode)
                seen = set()
                deduped = []
                for c in cities_data:
                    key = ((c.get('name') or '').strip().lower(), (c.get('countryCode') or '').upper(), (c.get('stateCode') or '').upper())
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped.append(c)
                cities = []
                for city in deduped:
                    cities.append({
                        "name": city.get('name',''),
                        "code": city.get('name',''),
                        "geonameId": city.get('geonameId',''),
                        "population": city.get('population', 0),
                        "lat": city.get('lat') or '',
                        "lng": city.get('lon') or city.get('lng') or ''
                    })
                app.logger.info('Serving %d unique cities from seeded_cities.json fallback', len(cities))
                return jsonify(cities)
        except Exception:
            app.logger.exception('Failed to load seeded cities fallback')
        return jsonify([])
    
    try:
        async with get_session() as session:
            # Search for cities in the state/province
            cities_url = "http://api.geonames.org/searchJSON"
            cities_params = {
                "country": country_code,
                "adminCode1": state_code,
                "featureClass": "P",  # Populated places
                "featureCode": "PPL",  # Populated place
                "maxRows": 500,
                "orderby": "population",
                "username": geonames_user
            }
            
            async with session.get(cities_url, params=cities_params, timeout=ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    app.logger.warning('GeoNames returned status %d for %s/%s; trying seeded fallback', resp.status, country_code, state_code)
                    # try seeded fallback
                    seed_path = Path(__file__).parent.parent / 'data' / 'seeded_cities.json'
                    if seed_path.exists():
                        seed = json.loads(seed_path.read_text())
                        cities_data = seed.get('cities', [])
                        if country_code:
                            cities_data = [c for c in cities_data if (c.get('countryCode') or '').upper() == country_code.upper()]
                        if state_code:
                            cities_data = [c for c in cities_data if (c.get('stateCode') or '').upper() == state_code.upper()]
                        # Deduplicate seeded cities
                        seen = set()
                        deduped = []
                        for c in cities_data:
                            key = ((c.get('name') or '').strip().lower(), (c.get('countryCode') or '').upper(), (c.get('stateCode') or '').upper())
                            if key in seen:
                                continue
                            seen.add(key)
                            deduped.append(c)
                        cities = [{
                            "name": c.get('name',''),
                            "code": c.get('name',''),
                            "geonameId": c.get('geonameId',''),
                            "population": c.get('population', 0),
                            "lat": c.get('lat') or '',
                            "lng": c.get('lon') or c.get('lng') or ''
                        } for c in deduped]
                        return jsonify(cities)
                    return jsonify([])
                
                cities_data = await resp.json()
                
                cities = []
                for city in cities_data.get('geonames', []):
                    cities.append({
                        "name": city.get('name', ''),
                        "code": city.get('name', ''),  # Use name as code for simplicity
                        "geonameId": city.get('geonameId', ''),
                        "population": city.get('population', 0),
                        "lat": city.get('lat', ''),
                        "lng": city.get('lng', '')
                    })
                
                # If GeoNames returned nothing, try seeded fallback
                if not cities:
                    app.logger.info('GeoNames returned no cities for %s/%s; falling back to seeded_cities.json', country_code, state_code)
                    seed_path = Path(__file__).parent.parent / 'data' / 'seeded_cities.json'
                    if seed_path.exists():
                        seed = json.loads(seed_path.read_text())
                        cities_data = seed.get('cities', [])
                        if country_code:
                            cities_data = [c for c in cities_data if (c.get('countryCode') or '').upper() == country_code.upper()]
                        if state_code:
                            cities_data = [c for c in cities_data if (c.get('stateCode') or '').upper() == state_code.upper()]
                        cities = [{
                            "name": c.get('name',''),
                            "code": c.get('name',''),
                            "geonameId": c.get('geonameId',''),
                            "population": c.get('population', 0),
                            "lat": c.get('lat') or '',
                            "lng": c.get('lon') or c.get('lng') or ''
                        } for c in cities_data]
                
                return jsonify(cities)
                
    except Exception:
        app.logger.exception('Failed to fetch cities from GeoNames')
        return jsonify([])

@app.route('/api/locations/neighborhoods')
async def api_neighborhoods():
    """Get neighborhoods for a city - wrapper around existing /neighborhoods endpoint"""
    country_code = request.args.get('countryCode', '')
    city_name = request.args.get('cityName', '')
    
    if not city_name:
        return jsonify([])
    
    # Call the existing neighborhoods endpoint
    try:
        # Use the existing /neighborhoods endpoint
        async with get_session() as session:
            async with session.get(f"http://localhost:5010/neighborhoods?city={city_name}&lang=en") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Transform the data to match expected format
                    if 'neighborhoods' in data:
                        neighborhoods = data['neighborhoods']
                        # Convert to simple format expected by frontend
                        simple_neighborhoods = []
                        for n in neighborhoods:
                            simple_neighborhoods.append({
                                'id': n.get('id', n.get('name', '')),
                                'name': n.get('name', ''),
                                'slug': n.get('slug', ''),
                                'center': n.get('center', {}),
                                'bbox': n.get('bbox', [])
                            })
                        return jsonify(simple_neighborhoods)
                    else:
                        return jsonify([])
                else:
                    return jsonify([])
    except Exception:
        app.logger.exception('Failed to fetch neighborhoods')
        return jsonify([])

@app.route('/api/fun-fact', methods=['POST'])
async def get_fun_fact():
    """Get a fun fact about a city"""
    try:
        payload = await request.get_json(silent=True) or {}
        city = payload.get('city', '').strip()
        
        if not city:
            return jsonify({'error': 'city required'}), 400
        
        # Import tracker
        from city_guides.src.fun_fact_tracker import track_fun_fact
        

        
        # Normalize city name but preserve spaces for multi-word cities
        import unicodedata
        normalized = unicodedata.normalize('NFKD', city.lower())
        # Keep alphanumeric and spaces, remove other punctuation
        city_lower = ''.join(c for c in normalized if c.isalnum() or c.isspace()).strip()
        
        # Initialize city_facts to prevent UnboundLocalError
        city_facts = []
        
        # Get seeded facts for this city
        seeded_facts = get_city_fun_facts(city_lower)
        
        # If city not in seeded list, fetch interesting facts
        if not seeded_facts:
            try:
                # Try DDGS for fun facts first
                try:
                    from city_guides.providers.ddgs_provider import ddgs_search
                    ddgs_results = await ddgs_search(f"interesting facts about {city}", max_results=5, timeout=int(os.getenv('DDGS_TIMEOUT','5')))
                    fun_facts_from_ddgs = []
                    for r in ddgs_results:
                        body = r.get('body', '')
                        # Look for sentences with numbers or superlatives
                        import re
                        sentences = re.split(r'(?<=[.!?])\s+', body)
                        for s in sentences:
                            if 50 < len(s) < 180 and re.search(r'\d|largest|oldest|first|only|famous|world', s.lower()):
                                if not re.match(r'^\w+ is a (city|town)', s.lower()):
                                    fun_facts_from_ddgs.append(s)
                    if fun_facts_from_ddgs:
                        city_facts = [fun_facts_from_ddgs[0]]
                    else:
                        raise Exception("No fun facts from DDGS")
                except:
                    # Fallback to Wikipedia
                    from city_guides.providers.wikipedia_provider import fetch_wikipedia_summary
                    wiki_text = await fetch_wikipedia_summary(city, lang="en")
                    if wiki_text:
                        import re
                        sentences = [s.strip() for s in wiki_text.split('.') if 40 < len(s.strip()) < 200]
                        # Skip boring definitions
                        filtered = [s for s in sentences if not re.match(r'^\w+ is a (city|town|commune)', s.lower())]
                        city_facts = [filtered[0] + '.' if filtered else sentences[1] + '.']
            except Exception as e:
                app.logger.warning(f"Failed to fetch Wikipedia fun fact for {city}: {e}")
                city_facts = [f"Explore {city.title()} and discover what makes it special!"]
        else:
            city_facts = seeded_facts
        
        # Select a random fun fact
        import random
        if not city_facts:
            city_facts = [f"Explore {city.title()} and discover what makes it special!"]
        selected_fact = random.choice(city_facts)
        
        # Track the fact quality
        source = "seeded" if seeded_facts else "dynamic"
        track_fun_fact(city, selected_fact, source)
        
        return jsonify({
            'city': city,
            'funFact': selected_fact
        })
        
    except Exception as e:
        app.logger.exception('Fun fact fetch failed')
        return jsonify({'error': 'Failed to fetch fun fact', 'details': str(e)}), 500


@app.route('/api/smart-neighborhoods', methods=['GET'])
async def api_smart_neighborhoods():
    """
    Get smart neighborhood suggestions for ANY city.
    First checks seed files, then falls back to Overpass API.
    Query params: city, category (optional)
    Returns: { is_large_city: bool, neighborhoods: [] }
    """
    city = request.args.get('city', '').strip()
    category = request.args.get('category', '').strip()
    
    if not city:
        return jsonify({'is_large_city': False, 'neighborhoods': []}), 400
    
    try:
        # Check cache first
        cache_key = f"smart_neighborhoods:{city.lower()}"
        if redis_client:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                app.logger.info(f"Cache hit for smart neighborhoods: {city}")
                return jsonify(json.loads(cached_data))

        # FIRST: Recursively scan all continent subdirectories for country seed files
        seed_neighborhoods = []
        data_path = Path(__file__).parent.parent / 'data'
        
        # Find all JSON files in data/ and its subdirectories
        for seed_file in data_path.rglob('*.json'):
            try:
                with open(seed_file, 'r', encoding='utf-8') as f:
                    seed_data = json.load(f)
                
                # Skip files that don't have proper neighborhood structure (like seeded_cities.json)
                if not isinstance(seed_data, dict) or 'cities' not in seed_data:
                    continue
                    
                cities = seed_data.get('cities', {})
                if not isinstance(cities, dict):
                    continue
                    
                city_key = next((k for k in cities.keys() if k.lower() == city.lower()), None)
                if city_key:
                    neighborhoods_data = cities[city_key]
                    # Validate that neighborhoods are objects with name/description, not strings (fun facts)
                    if neighborhoods_data and isinstance(neighborhoods_data, list) and len(neighborhoods_data) > 0:
                        first_item = neighborhoods_data[0]
                        if isinstance(first_item, dict) and 'name' in first_item:
                            seed_neighborhoods = neighborhoods_data
                            app.logger.info(f"Found {len(seed_neighborhoods)} neighborhoods in {seed_file.name} for {city}")
                            break  # Found the city, stop searching
            except Exception as e:
                app.logger.debug(f"Could not load {seed_file.name} for {city}: {e}")

        # If we have seed data, use it
        if seed_neighborhoods:
            response = {
                'is_large_city': True,
                'neighborhoods': seed_neighborhoods,
                'city': city,
                'category': category,
                'source': 'seed'
            }
            if redis_client:
                await redis_client.setex(cache_key, 3600, json.dumps(response))
            return jsonify(response)

        # FALLBACK: Get coordinates and fetch from Overpass API
        try:
            geo = await asyncio.wait_for(geocode_city(city), timeout=5.0)
        except asyncio.TimeoutError:
            app.logger.warning(f"Geocoding timeout for {city}")
            geo = None
        
        lat = geo.get('lat') if geo else None
        lon = geo.get('lon') if geo else None
        
        if lat is None or lon is None:
            app.logger.error(f"Could not geocode {city}")
            return jsonify({'is_large_city': False, 'neighborhoods': [], 'city': city, 'category': category}), 200
        
        # Fetch neighborhoods dynamically using Overpass API
        neighborhoods = await get_neighborhoods_for_city(city, lat, lon)
        
        response = {
            'is_large_city': len(neighborhoods) >= 3,
            'neighborhoods': neighborhoods,
            'city': city,
            'category': category,
            'source': 'overpass'
        }

        # Cache the response
        if redis_client:
            await redis_client.setex(cache_key, 3600, json.dumps(response))
            app.logger.info(f"Cached smart neighborhoods for {city}: {len(neighborhoods)} found")

        return jsonify(response)
        
    except Exception as e:
        app.logger.exception(f'Smart neighborhoods fetch failed for {city}')
        return jsonify({
            'is_large_city': False, 
            'neighborhoods': [],
            'city': city,
            'category': category,
            'error': str(e)
        }), 500

@app.route('/api/geocode', methods=['POST'])
async def geocode():
    """Geocode a city/neighborhood to get coordinates"""
    payload = await request.get_json(silent=True) or {}
    city = payload.get('city', '').strip()
    neighborhood = payload.get('neighborhood', '').strip()
    
    if not city:
        return jsonify({'error': 'city required'}), 400
    
    try:
        # Try to geocode city + neighborhood first, then city alone
        query = f"{neighborhood}, {city}" if neighborhood else city
        result = await geocode_city(query)
        
        if not result:
            return jsonify({'error': 'geocode_failed'}), 400
        
        return jsonify(result)
        
    except Exception:
        app.logger.exception('Geocoding failed')
        return jsonify({'error': 'geocode_failed'}), 500

@app.route("/search", methods=["POST"])
async def search():
    """Search for venues and places in a city"""
    print("[SEARCH ROUTE] Search request received")
    payload = await request.get_json(silent=True) or {}
    print(f"[SEARCH ROUTE] Payload: {payload}")
    
    # Normalize city name but preserve spaces for multi-word cities
    import unicodedata
    normalized = unicodedata.normalize('NFKD', (payload.get("query") or "").strip())
    # Keep alphanumeric and spaces, remove other punctuation
    city = ''.join(c for c in normalized if c.isalnum() or c.isspace()).strip()
    q = (payload.get("category") or payload.get("intent") or "").strip().lower()
    neighborhood = payload.get("neighborhood")
    state_name = (payload.get("state") or payload.get("stateName") or "").strip()
    country_name = (payload.get("country") or payload.get("countryName") or "").strip()
    should_cache = False  # disabled for testing
    
    if not city:
        return jsonify({"error": "city required"}), 400
    
    try:
        # Use the search implementation from persistence
        from persistence import _search_impl
        result = await asyncio.to_thread(_search_impl, payload)

        # Add categories to the search result
        if isinstance(result, dict):
            try:
                from .simple_categories import get_dynamic_categories
                categories = await get_dynamic_categories(city, state_name, country_name)
                result['categories'] = categories
            except Exception as e:
                import traceback
                app.logger.error(f'Failed to get categories for {city}: {e}')
                app.logger.error(traceback.format_exc())
                result['categories'] = []

        # Add fun facts from seeded data
        if isinstance(result, dict):
            try:
                seeded_facts = get_city_fun_facts(city)
                if seeded_facts:
                    import random
                    result['fun_facts'] = [random.choice(seeded_facts)]
                    result['fun_fact'] = result['fun_facts'][0]
            except Exception as e:
                app.logger.debug(f'Failed to get fun facts for {city}: {e}')

        # If no quick_guide/summary provided by upstream providers, supplement with Wikipedia summary
        if WIKI_CITY_AVAILABLE and isinstance(result, dict):
            has_quick = bool((result.get('quick_guide') or '').strip())
            has_summary = bool((result.get('summary') or '').strip())
            if not has_quick and not has_summary:
                try:
                    wiki_data = await fetch_city_wikipedia(city, state_name or None, country_name or None)
                    if wiki_data:
                        summary, url = wiki_data
                        result['quick_guide'] = summary
                        result['source'] = 'wikipedia'
                        result['cached'] = False
                        result['source_url'] = url
                except Exception:
                    app.logger.exception('Wikipedia city fallback failed for %s', city)

        if should_cache and redis_client:
            cache_key = build_search_cache_key(city, q, neighborhood)
            try:
                await redis_client.set(cache_key, json.dumps(result), ex=PREWARM_TTL)
                app.logger.info("Cached search result for %s/%s", city, q)
            except Exception:
                app.logger.exception("Failed to cache search result")
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.exception('Search failed')
        return jsonify({"error": "search_failed", "details": str(e)}), 500

@app.route('/api/synthesize', methods=['POST'])
async def synthesize():
    """Synthesize venues from search results using AI enhancement"""
    try:
        data = await request.get_json(silent=True) or {}
        search_result = data.get('search_result')
        
        if not search_result:
            return jsonify({'error': 'search_result required'}), 400
        
        # For now, return a simple synthesis based on available venues
        # In the future, this could use AI to enhance the venue data
        venues = search_result.get('venues', [])
        synthesized_venues = []
        
        for venue in venues[:10]:  # Limit to 10 venues
            synthesized_venue = {
                'id': venue.get('id'),
                'name': venue.get('name'),
                'address': venue.get('address'),
                'description': venue.get('description') or f'A popular {search_result.get("category", "spot")} in {search_result.get("city", "the city")}',
                'lat': venue.get('lat'),
                'lon': venue.get('lon'),
                'provider': venue.get('provider', 'osm'),
                'tags': venue.get('tags', {}),
                'enhanced_description': venue.get('description') or f'Great option for {search_result.get("category", "dining")} in the area'
            }
            synthesized_venues.append(synthesized_venue)
        
        return jsonify({
            'synthesized_venues': synthesized_venues,
            'total': len(synthesized_venues)
        })
        
    except Exception as e:
        app.logger.exception('Synthesis failed')
        return jsonify({'error': 'synthesis_failed', 'details': str(e)}), 500

@app.route('/api/generate_quick_guide', methods=['POST'])
async def generate_quick_guide(skip_cache=False, disable_quality_check=False):
    """Generate a neighborhood quick_guide using Wikipedia and local data-first heuristics.
    POST payload: { city: "City Name", neighborhood: "Neighborhood Name" }
    Returns: { quick_guide: str, source: 'cache'|'wikipedia'|'data-first', cached: bool, source_url?: str }
    """
    payload = await request.get_json(silent=True) or {}
    city = (payload.get('city') or '').strip()
    neighborhood = (payload.get('neighborhood') or '').strip()
    
    if not city:
        return jsonify({'error': 'city required'}), 400

    def slug(s):
        return re.sub(r'[^a-z0-9_-]', '_', s.lower().replace(' ', '_'))

    cache_dir = Path(__file__).parent / 'data' / 'neighborhood_quick_guides' / slug(city)
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Use different cache file for city-only vs neighborhood-specific guides
    if neighborhood:
        cache_file = cache_dir / (slug(neighborhood) + '.json')
    else:
        cache_file = cache_dir / '_city_guide.json'

    # Return cached if exists (unless skip_cache is True)
    if cache_file.exists() and not skip_cache:
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            resp = {
                'quick_guide': data.get('quick_guide'),
                'source': data.get('source', 'cache'),
                'cached': True,
                'source_url': data.get('source_url'),
            }
            if data.get('generated_at'):
                resp['generated_at'] = data.get('generated_at')

            # Skip cache quality check if disabled
            if not disable_quality_check:
                # EARLY: If raw cached content looks like DDGS disambiguation/promotional UI, replace before neutralization
                try:
                    from city_guides.src.snippet_filters import looks_like_ddgs_disambiguation_text
                    raw_q = data.get('quick_guide') or ''
                    src = data.get('source') or ''
                    if src in ('ddgs', 'synthesized') and (looks_like_ddgs_disambiguation_text(raw_q) or 'missing:' in raw_q.lower()):
                        app.logger.info('Replacing raw cached %s quick_guide for %s/%s due to disambiguation/promotional content (early replacement)', src, city, neighborhood)
                        try:
                            from city_guides.src.synthesis_enhancer import SynthesisEnhancer
                            new_para = SynthesisEnhancer.generate_neighborhood_paragraph(neighborhood, city)
                            resp['quick_guide'] = new_para
                            resp['source'] = 'synthesized'
                            resp['source_url'] = None
                            try:
                                with open(cache_file, 'w', encoding='utf-8') as f:
                                    json.dump({'quick_guide': resp['quick_guide'], 'source': resp['source'], 'generated_at': time.time(), 'source_url': None}, f, ensure_ascii=False, indent=2)
                            except Exception:
                                app.logger.exception('Failed to persist synthesized replacement for cached disambiguation (early)')
                        except Exception:
                            app.logger.exception('Failed to synthesize replacement for cached disambiguation (early)')
                            try:
                                cache_file.unlink()
                            except Exception:
                                pass
                        return jsonify(resp)
                except Exception:
                    app.logger.exception('Failed to validate raw cached quick_guide')

                # Neutralize cached quick_guide tone before returning (remove first-person/promotional voice)
                try:
                    from city_guides.src.synthesis_enhancer import SynthesisEnhancer
                    resp['quick_guide'] = SynthesisEnhancer.neutralize_tone(resp.get('quick_guide') or '', neighborhood=neighborhood, city=city, max_length=400)
                except Exception:
                    app.logger.exception('Failed to neutralize cached quick_guide')

                # If cached content is a simple 'X is a neighborhood in Y.' from data-first, try geo enrichment
                try:
                    if resp.get('source') == 'data-first' and re.match(r'^.+ is a neighborhood in .+\.$', (resp.get('quick_guide') or '')):
                        try:
                            from city_guides.src.geo_enrichment import enrich_neighborhood, build_enriched_quick_guide
                            enrichment = await enrich_neighborhood(city, neighborhood, session=aiohttp_session)
                            pois = enrichment.get('pois') if enrichment else None
                            if enrichment and (enrichment.get('text') or (pois is not None and len(pois) > 0)):
                                resp['quick_guide'] = build_enriched_quick_guide(neighborhood, city, enrichment)
                                resp['source'] = 'geo-enriched'
                                resp['confidence'] = 'medium'
                                try:
                                    with open(cache_file, 'w', encoding='utf-8') as f:
                                        json.dump({'quick_guide': resp['quick_guide'], 'source': resp['source'], 'generated_at': time.time(), 'source_url': None, 'confidence': resp['confidence']}, f, ensure_ascii=False, indent=2)
                                except Exception:
                                    app.logger.exception('Failed to persist geo-enriched replacement for cached entry')
                                return jsonify(resp)
                        except Exception:
                            app.logger.exception('Geo enrichment for cached entry failed')
                except Exception:
                    app.logger.exception('Failed to attempt geo-enrichment on cached quick_guide')

                # Compute confidence for cached snippet (backfill if missing)
                try:
                    cached_src = data.get('source') or ''
                    cached_conf = data.get('confidence')
                    if not cached_conf:
                        if cached_src == 'wikipedia':
                            resp['confidence'] = 'high'
                        elif cached_src == 'ddgs':
                            resp['confidence'] = 'medium'
                        elif cached_src == 'synthesized':
                            # conservative: synthesized cached snippets without recorded evidence are low confidence
                            resp['confidence'] = 'low'
                        else:
                            resp['confidence'] = 'low'
                except Exception:
                    resp['confidence'] = 'low' 

            # If cached content is a DDGS/synthesized hit that looks like a disambiguation or promotional snippet,
            # replace it immediately with a synthesized neutral paragraph and return that (avoid falling-through returns)
            from city_guides.src.snippet_filters import looks_like_ddgs_disambiguation_text
            src = data.get('source') or ''
            quick_text = resp.get('quick_guide') or ''
            if src in ('ddgs', 'synthesized') and (looks_like_ddgs_disambiguation_text(quick_text) or 'missing:' in quick_text.lower()):
                app.logger.info('Replacing cached %s quick_guide for %s/%s due to disambiguation/promotional content', src, city, neighborhood)
                try:
                    from city_guides.src.synthesis_enhancer import SynthesisEnhancer
                    new_para = SynthesisEnhancer.generate_neighborhood_paragraph(neighborhood, city)
                    resp['quick_guide'] = new_para
                    resp['source'] = 'synthesized'
                    resp['source_url'] = None
                    resp['confidence'] = 'low'
                    try:
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump({'quick_guide': resp['quick_guide'], 'source': resp['source'], 'generated_at': time.time(), 'source_url': None, 'confidence': resp['confidence']}, f, ensure_ascii=False, indent=2)
                    except Exception:
                        app.logger.exception('Failed to persist synthesized replacement for cached disambiguation')
                    return jsonify(resp)
                except Exception:
                    app.logger.exception('Failed to synthesize replacement for cached disambiguation')
                    try:
                        cache_file.unlink()
                    except Exception:
                        pass
                    # fall through to regeneration
            # Keep synthesized content even if low confidence - it's better than the basic fallback
            return jsonify(resp)

            # If the cached content is from Wikipedia, run a stricter relevance check
            try:
                if data.get('source') == 'wikipedia':
                    text = (data.get('quick_guide') or '').lower()
                    # Expanded blacklist of event/article keywords
                    blacklist = [
                        'fire', 'wildfire', 'hurricane', 'earthquake', 'storm', 'flood', 'tornado', 'volcano',
                        'massacre', 'riot', 'disaster', 'album', 'song', 'single', 'born', 'died', 'surname', 'battle'
                    ]
                    # Quick relevance: accept cached wikipedia if it mentions the city or neighborhood, or looks like a locality description
                    if city.lower() in text or neighborhood.lower() in text or any(k in text for k in ['neighborhood', 'neighbourhood', 'district', 'suburb', 'municipality', 'borough', 'locality']):
                        return jsonify(resp)
                    # If it looks like an event/article and doesn't mention the city/neighborhood, ignore cache and regenerate
                    if any(b in text for b in blacklist) and (city.lower() not in text and neighborhood.lower() not in text):
                        app.logger.info("Ignoring cached wikipedia quick_guide for %s/%s due to likely unrelated event/article", city, neighborhood)
                    else:
                        return jsonify(resp)
                else:
                    return jsonify(resp)
            except Exception:
                return jsonify(resp)
        except Exception:
            pass

    # Validate city/neighborhood combination using our disambiguator
    try:
        is_valid, confidence, suggested = NeighborhoodDisambiguator.validate_neighborhood(neighborhood, city)
        if not is_valid:
            app.logger.warning("City/neighborhood combination failed validation: %s/%s (confidence: %.2f)", city, neighborhood, confidence)
            # Fall back to synthesized content instead of Wikipedia search
            try:
                from city_guides.src.synthesis_enhancer import SynthesisEnhancer
                fallback_guide = SynthesisEnhancer.generate_neighborhood_paragraph(neighborhood, city)
                return jsonify({
                    'quick_guide': fallback_guide,
                    'source': 'synthesized',
                    'cached': False,
                    'source_url': None,
                    'confidence': 'low'
                })
            except Exception:
                return jsonify({
                    'quick_guide': f"{neighborhood} is a neighborhood in {city}.",
                    'source': 'data-first',
                    'cached': False,
                    'source_url': None,
                    'confidence': 'low'
                })
    except Exception:
        app.logger.exception("Failed to validate city/neighborhood combination")

    # SKIP Wikipedia for neighborhoods - go directly to synthesis
    # Wikipedia is unreliable for neighborhood content and often returns formal/dated info
    wiki_summary = None
    wiki_url = None

    def _looks_like_disambiguation_text(txt: str) -> bool:
        """Return True if the wiki extract looks like a disambiguation/listing page rather than a local description.
        Heuristics:
          - contains 'may refer to' or 'may also refer to' or starts with '<term> may refer to:'
          - contains multiple short comma-separated entries or many bullet-like lines
        """
        if not txt:
            return False
        low = txt.lower()
        if 'may refer to' in low or 'may also refer' in low or 'may be' in low:
            return True
        # Many short comma-separated segments suggests a list/disambig
        if low.count(',') >= 4 and len(low) < 800:
            parts = [p.strip() for p in low.split(',')]
            short_parts = [p for p in parts if len(p) < 60]
            if len(short_parts) >= 4:
                return True
        # multiple lines that look bullet-like
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        bullet_like = sum(1 for l in lines if l.startswith('*') or l.startswith('•') or (len(l.split()) < 6 and ',' in l))
        if bullet_like >= 3:
            return True
        return False

    def _page_is_relevant(j: dict) -> bool:
        """Return True if the Wikipedia page JSON `j` appears to describe the neighborhood or city.
        Heuristics:
          - skip disambiguation pages
          - reject pages that look like disambiguation/list pages
          - accept pages that mention the city or neighborhood in title or extract
          - accept pages that contain locality keywords like 'neighborhood', 'district', 'municipality'
        """
        if not j:
            return False
        if j.get('type') == 'disambiguation':
            return False
        title_text = (j.get('title') or '').lower()
        extract_text_raw = (j.get('extract') or j.get('description') or '')
        # Reject disambiguation-like extracts
        if _looks_like_disambiguation_text(extract_text_raw):
            app.logger.debug("Rejected wiki extract as disambiguation for title='%s'", title_text)
            return False
        extract_text = extract_text_raw.lower()
        if not extract_text and not title_text:
            return False
        locality_keywords = ['neighborhood', 'neighbourhood', 'district', 'suburb', 'municipality', 'borough', 'locality']
        event_keywords = ['fire', 'wildfire', 'hurricane', 'earthquake', 'storm', 'flood', 'tornado', 'volcano', 'massacre', 'riot', 'disaster', 'accident', 'attack']

        # If page mentions the city or neighborhood explicitly, consider it relevant
        # But be more strict when city is a country name to avoid wrong matches
        city_lower = city.lower()
        neighborhood_lower = neighborhood.lower()
        
        # Check if city is a country name (common countries)
        country_names = {'mexico', 'united states', 'canada', 'spain', 'france', 'germany', 'italy', 'uk', 'britain', 'australia', 'japan', 'china', 'india', 'brazil', 'argentina'}
        is_country = city_lower in country_names
        
        if is_country:
            # For country names, require both city AND neighborhood to be mentioned
            if (city_lower in extract_text or city_lower in title_text) and (neighborhood_lower in extract_text or neighborhood_lower in title_text):
                return True
        else:
            # For regular cities, either city or neighborhood mention is fine
            if city_lower in extract_text or city_lower in title_text:
                return True
                
        if neighborhood_lower in extract_text or neighborhood_lower in title_text:
            # Be careful: neighborhood may appear in the name of an event/article (e.g., "Las Conchas Fire").
            # If the page title combines neighborhood + an event keyword (e.g., "Las Conchas Fire"), reject it unless the page also mentions the city.
            if any(ev in title_text for ev in event_keywords):
                if city.lower() not in extract_text and city.lower() not in title_text:
                    app.logger.debug("Rejecting page with neighborhood in title but event-like content: %s", title_text)
                    return False
                else:
                    return True
            # Otherwise accept
            return True
        if any(k in extract_text for k in locality_keywords):
            return True
        return False

    # Delegate DDGS/web snippet filtering to a dedicated module to keep imports light for tests
    from city_guides.src.snippet_filters import looks_like_ddgs_disambiguation_text as _looks_like_ddgs_disambiguation_text

    # SKIP Wikipedia fetching for neighborhoods
    # Wikipedia is unreliable for neighborhood content and often returns formal/dated info

    synthesized = None
    source = None
    source_url = None
    # DDGS helper containers (initialized to avoid possibly-unbound warnings)
    ddgs_results = []
    ddgs_original = ''

    # Go directly to DDGS-derived synthesis for neighborhoods
    if not synthesized:
        try:
            # Build more specific DDGS queries with geographic context
            ddgs_queries = []
            
            # Add country/state context if available in city name
            geographic_context = ""
            if "," in city:
                # Extract country/state from "City, State" or "City, Country"
                parts = city.split(",", 1)
                city_name = parts[0].strip()
                context = parts[1].strip()
                geographic_context = f" {context}"
            else:
                city_name = city
                
            # Build specific queries with geographic context - include real estate sources
            # Keep DDGS queries small to control latency: pick a few high-value queries
            ddgs_queries = [
                f"{neighborhood} {city_name}{geographic_context} travel guide",
                f"{neighborhood} {city_name}{geographic_context} neighborhood information",
                f"what is {neighborhood} {city_name}{geographic_context} like",
                # Wikipedia query for factual checks
                f"{neighborhood} {city_name} Wikipedia",
            ]
            ddgs_results = []
            # Run DDGS queries concurrently with a small concurrency limit to reduce overall wall time
            sem = asyncio.Semaphore(int(os.getenv('DDGS_CONCURRENCY', '3')))
            async def _run_query(q):
                async with sem:
                    if not ddgs_search:
                        app.logger.debug('DDGS provider not available at runtime; skipping query %s', q)
                        return []
                    try:
                        res = await ddgs_search(q, engine="google", max_results=3, timeout=int(os.getenv('DDGS_TIMEOUT','5')))
                        app.logger.info('DDGS: query="%s" got %d results', q, len(res) if res else 0)
                        if res:
                            for i, r in enumerate(res[:3]):  # Log first 3 results
                                app.logger.info('DDGS result %d: title="%s" body="%s"', i, (r.get('title') or '')[:100], (r.get('body') or '')[:100])
                        return res or []
                    except Exception as e:
                        app.logger.debug('DDGS query failed for %s: %s', q, e)
                        return []

            tasks = [_run_query(q) for q in ddgs_queries]
            try:
                ddgs_lists = await asyncio.gather(*tasks)
                for res in ddgs_lists:
                    if res:
                        ddgs_results.extend(res)
            except Exception as e:
                app.logger.debug('Concurrent DDGS queries failed: %s', e)
                ddgs_results = []
            # Keep unique by href
            # Apply configurable DDGS domain blocklist (soft block) so we don't use noisy sites as final quick guides
            try:
                blocked_domains = [d.strip().lower() for d in os.getenv('BLOCKED_DDGS_DOMAINS', 'tripsavvy.com,tripadvisor.com').split(',') if d.strip()]
                from city_guides.src.snippet_filters import filter_ddgs_results
                allowed_results, blocked_results = filter_ddgs_results(ddgs_results, blocked_domains)
                if blocked_results:
                    app.logger.info('Blocked %d DDGS results for domains: %s', len(blocked_results), ','.join(sorted(set([ (r.get('href') or r.get('url') or '').split('/')[2] for r in blocked_results if (r.get('href') or r.get('url') )]))))
                ddgs_results = allowed_results
            except Exception:
                app.logger.exception('Failed to apply DDGS blocklist filter')
            seen = set()
            unique = []
            for r in ddgs_results:
                href = r.get('href') or r.get('url')
                if not href:
                    continue
                if href in seen:
                    continue
                seen.add(href)
                unique.append(r)
            ddgs_results = unique[:6]

            # Filter for results that likely mention the neighborhood/city
            relevant = []
            for r in ddgs_results:
                body = (r.get('body') or '') or (r.get('title') or '')
                txt = re.sub(r"\s+", ' ', (body or '')).strip()
                if not txt:
                    continue
                href = (r.get('href') or r.get('url') or '')
                # Skip known noisy hostnames (videos/social) by href
                if href and any(h in href.lower() for h in ['youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com']):
                    app.logger.debug('Filtered DDGS candidate by href (noisy host): %s', href)
                    continue
                # Filter out disambiguation/definition/promotional snippets
                if _looks_like_ddgs_disambiguation_text(txt):
                    app.logger.debug('Filtered DDGS candidate as disambiguation/promotional: %s', (r.get('title') or '')[:120])
                    continue
                # Consider relevant only if it specifically mentions the neighborhood AND provides substantial content
                lower = txt.lower()
                title_lower = (r.get('title') or '').lower()
                
                # Must mention the exact neighborhood name AND be contextually relevant
                mentions_neighborhood = neighborhood.lower() in lower or neighborhood.lower() in title_lower
                
                # Must be substantial, informative content about the actual neighborhood (not just any content with keywords)
                is_substantial = len(txt) >= 100 and any(phrase in lower for phrase in [
                    'neighborhood', 'area', 'district', 'located', 'residential', 'beach', 'attractions', 
                    'amenities', 'shops', 'restaurants', 'streets', 'community', 'town', 'municipality',
                    'baja california', 'tijuana', 'playas', 'near', 'proximity', 'primarily',
                    # Real estate indicators
                    'homes', 'properties', 'real estate', 'realtor', 'zillow', 'for sale',
                    'population', 'median', 'average', 'price', 'market'
                ]) and not any(irrelevant_topic in lower for irrelevant_topic in [
                    # Filter out architectural, art history, and definition topics
                    'architecture', 'architectural style', 'gothic architecture', 'gothic style',
                    'art period', 'art movement', 'historical period', 'medieval',
                    'definition', 'meaning of', 'what is', 'etymology', 'origin of the word',
                    'clothing brand', 'snack brand', 'food product', 'company', 'manufacturer',
                    'music genre', 'literary genre', 'film genre', 'book', 'novel', 'movie'
                ])
                
                # Filter out generic promotional/travel booking content, but allow real estate and Wikipedia
                is_generic_promo = any(keyword in lower for keyword in [
                    'uber', 'lyft', 'taxi', 'booking', 'reservation', 'schedule', 'app', 'download',
                    'guide to getting around', 'transportation service', 'ride sharing',
                    'ready to explore', 'discover must-see', 'fun things to do', 'planning a trip',
                    'where to stay', 'trip.com', 'booking.com', 'expedia'
                ])
                
                # Allow real estate and Wikipedia sources even if they sound promotional
                href = (r.get('href') or r.get('url') or '')
                is_good_source = any(domain in href.lower() for domain in [
                    'wikipedia.org', 'realtor.com', 'zillow.com', 'redfin.com', 'trulia.com',
                    'homes.com', 'loopnet.com', 'apartments.com', 'mls'
                ])
                
                if is_good_source:
                    is_generic_promo = False  # Override for good sources
                
                app.logger.info("DDGS filtering for %s/%s: mentions_neighborhood=%s, is_substantial=%s, is_generic_promo=%s", 
                              city, neighborhood, mentions_neighborhood, is_substantial, is_generic_promo)
                
                if mentions_neighborhood and is_substantial and not is_generic_promo:
                    relevant.append(r)
                else:
                    app.logger.info("Filtered DDGS result: %s", (r.get('title') or '')[:100])
            # If no clearly relevant results, but we have ddgs hits, treat the top hits as possible candidates
            if not relevant and ddgs_results:
                app.logger.debug('No clearly relevant DDGS hits for %s/%s but using top search results', city, neighborhood)
                relevant = ddgs_results[:3]

            if relevant:
                app.logger.debug("DDGS candidates for %s/%s: %s", city, neighborhood, [ (r.get('title'), r.get('href') or r.get('url')) for r in relevant ])
                
                # Try to use the best DDGS result directly if it's good enough
                best_result = relevant[0]
                title = (best_result.get('title') or '').strip()
                body = (best_result.get('body') or '').strip()
                
                # If the DDGS result looks good (mentions neighborhood/city and is substantial), use it directly
                combined_text = f"{title}. {body}" if title and body else (title or body)
                if (len(combined_text) >= 50 and 
                    (neighborhood.lower() in combined_text.lower() or city.lower() in combined_text.lower()) and
                    not _looks_like_ddgs_disambiguation_text(combined_text)):
                    # Add attribution for the source
                    source_domain = None
                    href = best_result.get('href') or best_result.get('url') or ''
                    if href:
                        try:
                            from urllib.parse import urlparse
                            source_domain = urlparse(href).netloc
                        except Exception:
                            source_domain = 'web source'
                    
                    # Allow more characters and add attribution
                    if source_domain:
                        synthesized = f"{combined_text[:800]} (Source: {source_domain})"
                    else:
                        synthesized = combined_text[:800]
                    source = 'ddgs'
                    source_url = href
                    app.logger.info("Used DDGS result directly for %s/%s with attribution", city, neighborhood)
                else:
                    # Fall back to synthesis if direct result isn't good enough
                    synthesized = None

                # If semantic synthesis failed or returned poor text, fall back to simple snippet composition
                if not synthesized:
                    def pick_sentences_from_text(txt):
                        if not txt:
                            return []
                        sents = re.split(r'(?<=[.!?])\s+', txt)
                        out = []
                        keywords = [neighborhood.lower(), city.lower(), 'bus', 'train', 'transit', 'colonia', 'neighborhood', 'pueblo', 'pueblo mágico', 'pueblo magico']
                        for s in sents:
                            low = s.lower()
                            if any(k in low for k in keywords):
                                out.append(s.strip())
                        if not out:
                            out = [s.strip() for s in sents[:2] if s.strip()]
                        return out

                    parts = []
                    for r in relevant[:4]:
                        text = (r.get('body') or '') or (r.get('title') or '')
                        text = re.sub(r"\s+", ' ', text).strip()
                        parts.extend(pick_sentences_from_text(text))

                    # deduplicate and limit
                    seen = set()
                    chosen = []
                    for p in parts:
                        if p in seen:
                            continue
                        seen.add(p)
                        chosen.append(p)
                        if len(chosen) >= 3:
                            break
                    if chosen:
                        synthesized = ' '.join(chosen)
                        # Ensure neighborhood name (eg. 'Las Conchas') is present; prefer sentence from original snippets if needed
                        try:
                            from city_guides.src.synthesis_enhancer import SynthesisEnhancer
                            original_combined = ' '.join([ (r.get('body') or '') for r in relevant[:4] ])
                            fallback = f"{neighborhood} is a neighborhood in {city}."
                            synthesized = SynthesisEnhancer.ensure_includes_term(synthesized, original_combined, neighborhood, fallback_sentence=fallback, max_length=400)
                        except Exception:
                            app.logger.exception('Failed to ensure neighborhood inclusion in DDGS fallback')
                        source = 'ddgs'
                        source_url = relevant[0].get('href') or relevant[0].get('url')
        except Exception:
            app.logger.exception('DDGS attempt failed for %s/%s', city, neighborhood)

    # If neither Wikipedia nor DDGS synthesized, fall back to city_info and simple template
    if not synthesized:
        try:
            data_dir = Path(__file__).parent.parent / 'data'
            for p in data_dir.glob('city_info_*'):
                name = p.name.lower()
                if slug(city) in name or city.lower().split(',')[0] in name:
                    try:
                        with open(p, 'r', encoding='utf-8') as f:
                            cj = json.load(f)
                        for key in ('quick_guide', 'quickGuide', 'summary', 'description'):
                            if key in cj and cj[key]:
                                txt = cj[key]
                                if neighborhood.lower() in txt.lower():
                                    parts = re.split(r'(?<=[.!?])\s+', txt)
                                    matched = [s for s in parts if neighborhood.lower() in s.lower()]
                                    if matched:
                                        synthesized = ' '.join(matched[:2])
                                        source = 'data-first'
                                        break
                                if not synthesized:
                                    synthesized = f"{neighborhood} is a neighborhood in {city}. {str(txt).strip()}"
                                    source = 'data-first'
                                    break
                    except Exception:
                        continue
                if synthesized:
                    break
        except Exception:
            synthesized = None

    if not synthesized:
        # Attempt DuckDuckGo (DDGS) as a fallback to fetch a travel-oriented summary when
        # Wikipedia and local data files don't provide a good match.
        try:
            ddgs_queries = [
                f"{neighborhood}, {city} travel guide",
                f"{neighborhood} {city} travel",
                f"{neighborhood} travel",
                f"{city} travel guide",
            ]
            ddgs_snippet = None
            ddgs_url = None
            if not ddgs_search:
                app.logger.debug('DDGS provider not available at runtime; skipping DDGS fallback for %s/%s', city, neighborhood)
            else:
                for q in ddgs_queries:
                    try:
                        results = await ddgs_search(q, engine="google", max_results=3, timeout=int(os.getenv('DDGS_TIMEOUT','5')))
                        for r in results:
                            body = (r.get('body') or '') or (r.get('title') or '')
                            text = re.sub(r'\s+', ' ', (body or '')).strip()
                            # Accept result if it's reasonably descriptive and mentions either neighborhood or city
                            if len(text) >= 60 and (city.lower() in text.lower() or neighborhood.lower() in text.lower() or q.lower().startswith(city.lower())):
                                ddgs_snippet = text
                                ddgs_original = (r.get('body') or r.get('title') or '')
                                ddgs_url = r.get('href')
                                break
                        if ddgs_snippet:
                            break
                    except Exception as e:
                        app.logger.debug('DDGS query failed for %s %s: %s', q, city, e)
                        continue
            if ddgs_snippet:
                # Reject noisy/harmful ddgs snippets by url or content
                href = ddgs_url or ''
                if href and any(h in href.lower() for h in ['youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com']):
                    app.logger.debug('Filtered ddgs_snippet by noisy host: %s', href)
                    ddgs_snippet = None
                elif _looks_like_ddgs_disambiguation_text(ddgs_snippet):
                    app.logger.debug('Filtered ddgs_snippet as disambiguation/promotional content: %s', ddgs_snippet[:120])
                    ddgs_snippet = None

            if ddgs_snippet:
                # Trim to a sensible length
                if len(ddgs_snippet) > 800:
                    ddgs_snippet = ddgs_snippet[:800].rsplit(' ', 1)[0] + '...'
                # Ensure neighborhood appears in the snippet (preserve 'Las'/'Los' articles etc.)
                try:
                    from city_guides.src.synthesis_enhancer import SynthesisEnhancer
                    fallback = f"{neighborhood} is a neighborhood in {city}."
                    ddgs_snippet = SynthesisEnhancer.ensure_includes_term(ddgs_snippet, ddgs_original, neighborhood, fallback_sentence=fallback, max_length=800)
                except Exception:
                    app.logger.exception('Failed to ensure neighborhood inclusion for ddgs snippet')
                # Stronger acceptance: ensure snippet mentions city or neighborhood (unless snippet title contains them)
                if city.lower() in ddgs_snippet.lower() or neighborhood.lower() in ddgs_snippet.lower() or (ddgs_url and (neighborhood.lower() in (ddgs_url or '').lower() or city.lower() in (ddgs_url or '').lower())):
                    synthesized = ddgs_snippet
                    source = 'ddgs'
                    source_url = ddgs_url
                else:
                    app.logger.debug('DDGS snippet rejected for %s/%s: does not mention city/neighborhood', city, neighborhood)
        except Exception:
            app.logger.exception("ddgs fallback failed for %s, %s", neighborhood, city)

        # Final generic fallback if nothing else matched: synthesize a better paragraph
        app.logger.info("Reached synthesis fallback for %s/%s, synthesized=%s", city, neighborhood, bool(synthesized))
        if not synthesized:
            try:
                # Add the parent directory to Python path to ensure import works
                parent_dir = str(Path(__file__).parent.parent)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                
                from city_guides.src.synthesis_enhancer import SynthesisEnhancer
                app.logger.info("About to call SynthesisEnhancer.generate_neighborhood_paragraph for %s/%s", city, neighborhood)
                synthesized = SynthesisEnhancer.generate_neighborhood_paragraph(neighborhood, city)
                source = 'synthesized'
                app.logger.info("Successfully generated synthesized paragraph for %s/%s: %s", city, neighborhood, synthesized[:100])
            except Exception as e:
                app.logger.exception("SynthesisEnhancer failed for %s/%s: %s", city, neighborhood, str(e))
                synthesized = f"{neighborhood} is a neighborhood in {city}."
                source = 'data-first'

    # Neutralize tone (convert first-person/promotional snippets to neutral travel-guide tone)
    try:
        from city_guides.src.synthesis_enhancer import SynthesisEnhancer
        synthesized = SynthesisEnhancer.neutralize_tone(synthesized or '', neighborhood=neighborhood, city=city, max_length=400)
    except Exception:
        app.logger.exception('Quick guide tone neutralization failed')

    # Defensive check: if the synthesized text still looks like a disambiguation/definition or promotional UI fragment,
    # replace with a safe neutral generic fallback so we never return list/disambig pages.
    try:
        from city_guides.src.snippet_filters import looks_like_ddgs_disambiguation_text
        if looks_like_ddgs_disambiguation_text(synthesized or '') or 'missing:' in (synthesized or '').lower():
            app.logger.info('Rejecting synthesized quick_guide for %s/%s as disambiguation/promotional content; using generic fallback', city, neighborhood)
            synthesized = f"{neighborhood} is a neighborhood in {city}."
            source = 'data-first'
    except Exception:
        app.logger.exception('Failed to validate synthesized quick_guide')

    # Enhance with Wikipedia neighborhood data if available
    wikipedia_enhancement = ""
    try:
        from city_guides.providers.wikipedia_neighborhood_provider import wikipedia_neighborhood_provider
        async with get_session(aiohttp_session) as session:
            wiki_data = await wikipedia_neighborhood_provider.get_neighborhood_data(city, neighborhood, session)
        if wiki_data:
            wiki_info = wikipedia_neighborhood_provider.extract_neighborhood_info(wiki_data)
            
            # Build enhancement from Wikipedia data
            enhancements = []
            
            if wiki_info.get('description'):
                # Use the Wikipedia description as the primary enhancement
                wikipedia_enhancement = wiki_info['description']
            else:
                # Fallback to basic info
                if wiki_info.get('coordinates'):
                    lat = wiki_info['coordinates'].get('lat')
                    lon = wiki_info['coordinates'].get('lon')
                    if lat and lon:
                        enhancements.append(f"Location: {lat}, {lon}")
                
                if wiki_info.get('name'):
                    enhancements.append(f"Official name: {wiki_info['name']}")
            
            if enhancements and not wikipedia_enhancement:
                wikipedia_enhancement = f" {' '.join(enhancements)}."
            
            if wikipedia_enhancement:
                app.logger.info(f"Wikipedia data found for {city}/{neighborhood}: {wikipedia_enhancement[:100]}")
    except Exception as e:
        app.logger.debug(f'Wikipedia neighborhood data fetch failed for {city}/{neighborhood}: {e}')

    # Enhance with Groq AI content if Wikipedia failed AND content is sparse
    groq_enhancement = ""
    if not wikipedia_enhancement and _is_content_sparse_or_low_quality(synthesized, neighborhood, city):
        try:
            from city_guides.providers.groq_neighborhood_provider import groq_neighborhood_provider
            groq_data = await groq_neighborhood_provider.generate_neighborhood_content(city, neighborhood, aiohttp_session)
            if groq_data:
                groq_info = groq_neighborhood_provider.extract_neighborhood_info(groq_data)
                
                if groq_info.get('description'):
                    groq_enhancement = groq_info['description']
                    app.logger.info(f"Groq enhanced sparse content for {city}/{neighborhood}: {groq_enhancement[:100]}")
        except Exception as e:
            app.logger.debug(f'Groq neighborhood generation failed for {city}/{neighborhood}: {e}')

    # Enhance with Teleport data if available (final fallback)
    teleport_enhancement = ""
    if not wikipedia_enhancement and not groq_enhancement:  # Only try Teleport if both Wikipedia and Groq failed
        try:
            cost_data = get_cost_estimates(city)
            if cost_data and len(cost_data) > 0:
                # Extract key metrics from Teleport data
                avg_costs = []
                for item in cost_data[:3]:  # Top 3 cost items
                    label = item.get('label', '')
                    value = item.get('value', '')
                    if label and value:
                        avg_costs.append(f"{label}: {value}")
                
                if avg_costs:
                    teleport_enhancement = f" Average costs include {', '.join(avg_costs[:2])}."
        except Exception:
            app.logger.debug('Teleport data fetch failed for %s', city)

    # Combine enhancement data with synthesized content
    enhancement_text = wikipedia_enhancement or groq_enhancement or teleport_enhancement
    if enhancement_text and synthesized:
        # Insert enhancement data after the first sentence
        sentences = re.split(r'(?<=[.!?])\s+', synthesized)
        if len(sentences) > 1:
            synthesized = f"{sentences[0]} {enhancement_text}{' '.join(sentences[1:])}"
        else:
            synthesized = f"{synthesized} {enhancement_text}"
        
        if wikipedia_enhancement:
            source = f"{source}+wikipedia"
            confidence = 'high'  # Wikipedia is high confidence
        elif groq_enhancement:
            source = f"{source}+groq"
            confidence = 'medium'  # Groq is medium confidence
        elif teleport_enhancement:
            source = f"{source}+teleport"
            confidence = 'medium'  # Upgrade confidence with Teleport data

    # Determine confidence level for the returned quick guide
    # - high: sourced from Wikipedia
    # - medium: DDGS-derived or synthesized with DDGS evidence or Groq/Teleport data
    # - low: synthesized with no supporting web/wiki evidence (fall back to minimal factual sentence)
    confidence = 'low'
    try:
        if source == 'wikipedia':
            confidence = 'high'
        elif source == 'synthesized+wikipedia':
            confidence = 'high'
        elif source == 'ddgs':
            confidence = 'medium'
        elif source == 'ddgs+wikipedia':
            confidence = 'high'
        elif source == 'synthesized+groq':
            confidence = 'medium'
        elif source == 'ddgs+groq':
            confidence = 'medium'
        elif source == 'synthesized+teleport':
            confidence = 'medium'
        elif source == 'ddgs+teleport':
            confidence = 'medium'
        elif source == 'synthesized':
            if isinstance(ddgs_results, list) and len(ddgs_results) > 0:
                confidence = 'medium'
            else:
                confidence = 'low'

        # If confidence is low, attempt geo enrichment to enhance existing content
        if confidence == 'low' and source != 'synthesized':
            try:
                from city_guides.src.geo_enrichment import enrich_neighborhood, build_enriched_quick_guide
                enrichment = await enrich_neighborhood(city, neighborhood, session=aiohttp_session)
                pois = enrichment.get('pois') if enrichment else None
                if enrichment and (enrichment.get('text') or (pois is not None and len(pois) > 0)):
                    synthesized = build_enriched_quick_guide(neighborhood, city, enrichment)
                    source = 'geo-enriched'
                    confidence = 'medium'
                else:
                    # Try POI discovery as fallback for better neighborhood knowledge
                    try:
                        from city_guides.providers.overpass_provider import geocode_city as overpass_geocode
                        from city_guides.providers.multi_provider import multi_provider
                        
                        # Get neighborhood coordinates
                        nb_coords = await overpass_geocode(f"{neighborhood}, {city}")
                        if nb_coords and isinstance(nb_coords, tuple) and len(nb_coords) == 4:
                            min_lon, min_lat, max_lon, max_lat = nb_coords
                            lat = (min_lat + max_lat) / 2
                            lon = (min_lon + max_lon) / 2
                            
                            # Discover POIs in the neighborhood
                            poi_results = await multi_provider.discover_pois(
                                lat=lat, lon=lon,
                                poi_type='tourism',  # General POIs
                                radius_m=1000,
                                limit=10,
                                session=aiohttp_session
                            )
                            
                            if poi_results and len(poi_results) > 0:
                                # Build quick guide from discovered POIs
                                poi_names = [p.get('name', '') for p in poi_results[:5] if p.get('name')]
                                poi_types = list(set([p.get('type', '').replace('_', ' ') for p in poi_results[:5] if p.get('type')]))
                                
                                if poi_names:
                                    poi_text = ', '.join(poi_names)
                                    type_text = ', '.join(poi_types[:3]) if poi_types else 'various places'
                                    
                                    synthesized = f"{neighborhood} is a neighborhood in {city}. It features {type_text} including {poi_text}. The area offers local amenities and attractions for visitors."
                                    source = 'poi-enriched'
                                    confidence = 'medium'
                                    
                                    # Update source_url with POI provider info
                                    provider_counts = {}
                                    for p in poi_results:
                                        prov = p.get('provider', 'unknown')
                                        provider_counts[prov] = provider_counts.get(prov, 0) + 1
                                    source_url = f"POI discovery: {dict(provider_counts)}"
                                
                    except Exception as poi_error:
                        app.logger.debug(f"POI discovery fallback failed for {city}/{neighborhood}: {poi_error}")
                    
                    # Only use basic fallback if POI discovery also failed
                    if not synthesized or source == 'data-first':
                        synthesized = f"{neighborhood} is a neighborhood in {city}."
                        source = source or 'data-first'
            except Exception:
                confidence = 'low'
    except Exception:
        confidence = 'low'

    out = {'quick_guide': synthesized, 'source': source or 'data-first', 'confidence': confidence, 'cached': False, 'generated_at': time.time(), 'source_url': source_url}

    # Try to enrich quick guide with Mapillary thumbnails (if available)
    mapillary_images = []
    
    # Try Pixabay first for high-quality images
    try:
        pixabay_key = os.getenv("PIXABAY_KEY")
        if pixabay_key:
            search_query = f"{neighborhood} {city}" if neighborhood else city
            async with get_session() as session:
                async with session.get(
                    "https://pixabay.com/api/",
                    params={
                        "key": pixabay_key,
                        "q": search_query,
                        "per_page": 3,
                        "image_type": "photo",
                        "orientation": "horizontal"
                    }
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for hit in data.get("hits", []):
                            mapillary_images.append({
                                "id": hit["id"],
                                "url": hit["webformatURL"],
                                "provider": "pixabay",
                                "attribution": f"Photo by {hit['user']} on Pixabay",
                                "source_url": hit["pageURL"]
                            })
                            app.logger.info(f"Added Pixabay image: {hit['pageURL']}")
    except Exception as e:
        app.logger.debug(f"Pixabay fetch failed: {e}")
    
    try:
        try:
            import city_guides.mapillary_provider as mapillary_provider  # type: ignore
        except Exception:
            mapillary_provider = None

        if mapillary_provider:
            # Try neighborhood+city first, then city fallback
            latlon = await geocode_city(f"{neighborhood}, {city}")
            if not latlon or not latlon.get("lat"):
                latlon = await geocode_city(city)
            if latlon and latlon.get("lat"):
                try:
                    imgs = await mapillary_provider.async_search_images_near(latlon["lat"], latlon["lon"], radius_m=400, limit=6, session=aiohttp_session)
                    for it in imgs:
                        mapillary_images.append({
                            'id': it.get('id'),
                            'url': it.get('url'),
                            'lat': it.get('lat'),
                            'lon': it.get('lon')
                        })
                except Exception:
                    app.logger.debug('mapillary image fetch failed for quick_guide')
    except Exception:
        pass

    # If no Mapillary images found, try a Wikimedia Commons fallback (best-effort)
    # Also, strip any inline 'Image via' lines from the quick_guide and move them to metadata
    try:
        from city_guides.src.synthesis_enhancer import SynthesisEnhancer
        cleaned_quick_guide, image_attributions = SynthesisEnhancer.extract_image_attributions(synthesized or '')
        synthesized = cleaned_quick_guide
    except Exception:
        image_attributions = []

    if not mapillary_images:
        try:
            import city_guides.providers.image_provider as image_provider
        except Exception:
            image_provider = None

        if image_provider:
            try:
                wik_img = None
                # Try neighborhood+city first
                try:
                    wik_img = await image_provider.fetch_banner_from_wikipedia(f"{neighborhood}, {city}")
                except Exception:
                    wik_img = None
                # Fallback to neighborhood alone
                if not wik_img:
                    try:
                        wik_img = await image_provider.fetch_banner_from_wikipedia(neighborhood)
                    except Exception:
                        wik_img = None
                # Fallback to city banner
                if not wik_img:
                    try:
                        wik_img = await image_provider.fetch_banner_from_wikipedia(city)
                    except Exception:
                        wik_img = None
                if wik_img and (wik_img.get('remote_url') or wik_img.get('url')):
                    if _is_relevant_wikimedia_image(wik_img, city, neighborhood):
                        remote = wik_img.get('remote_url') or wik_img.get('url')
                        attr = wik_img.get('attribution')
                        page_title = (wik_img.get('page_title') or '')
                        mapillary_images.append({
                            'id': None,
                            'url': remote,
                            'provider': 'wikimedia',
                            'attribution': attr,
                            'page_title': page_title,
                            'source_url': remote,
                        })
                    else:
                        app.logger.info('Skipping wikimedia image based on relevance heuristic: %s', wik_img.get('page_title') or wik_img.get('remote_url'))
                # include any attributions found in the quick_guide text as metadata (deduped)
                for a in image_attributions:
                    if not any((a.get('url') and a.get('url') == m.get('source_url')) for m in mapillary_images):
                        try:
                            from city_guides.src.synthesis_enhancer import SynthesisEnhancer as _SE
                            attr = _SE.create_attribution(a.get('provider'), a.get('url'))
                        except Exception:
                            attr = ''
                        mapillary_images.append({
                            'id': None,
                            'url': a.get('url'),
                            'provider': a.get('provider'),
                            'attribution': attr,
                            'source_url': a.get('url')
                        })
            except Exception:
                app.logger.debug('wikimedia fallback failed for quick_guide')

    out['mapillary_images'] = mapillary_images
    # Before writing cache, ensure we are not storing disambiguation/promotional snippets from DDGS
    try:
        from city_guides.src.snippet_filters import looks_like_ddgs_disambiguation_text
        if out.get('source') == 'ddgs' and looks_like_ddgs_disambiguation_text(out.get('quick_guide') or ''):
            app.logger.info('Not caching disambiguation/promotional ddgs quick_guide for %s/%s', city, neighborhood)
            # replace with synthesized neutral paragraph if available
            try:
                from city_guides.src.synthesis_enhancer import SynthesisEnhancer
                out['quick_guide'] = SynthesisEnhancer.generate_neighborhood_paragraph(neighborhood, city)
                out['source'] = 'synthesized'
                out['source_url'] = None
            except Exception:
                out['quick_guide'] = f"{neighborhood} is a neighborhood in {city}."
                out['source'] = 'data-first'

        # Neutralize tone for the quick_guide before persisting (ensure persisted copy is neutral)
        try:
            from city_guides.src.synthesis_enhancer import SynthesisEnhancer
            out['quick_guide'] = SynthesisEnhancer.neutralize_tone(out.get('quick_guide') or '', neighborhood=neighborhood, city=city)
        except Exception:
            app.logger.exception('Failed to neutralize quick_guide before persist')

        # Persist using module-level helper
        await _persist_quick_guide(out, city, neighborhood, cache_file)

    except Exception:
        app.logger.exception('failed to write quick_guide cache')

    resp = {'quick_guide': synthesized, 'source': source or 'data-first', 'confidence': confidence, 'cached': False, 'source_url': source_url}
    if mapillary_images:
        resp['mapillary_images'] = mapillary_images
    return jsonify(resp)

def _is_content_sparse_or_low_quality(content: str, neighborhood: str, city: str) -> bool:
    """Check if content lacks specifics and should trigger Groq/other enhancements."""
    if not content or len(content.strip()) < 50:
        return True

    content_lower = content.lower()

    generic_patterns = [
        f"{neighborhood.lower()} is a neighborhood in {city.lower()}",
        f"{neighborhood.lower()} is a neighborhood",
        "is a neighborhood in",
        "is located in",
        "is situated in",
        "is part of"
    ]
    if any(pattern in content_lower for pattern in generic_patterns):
        return True

    detail_indicators = [
        'market', 'shop', 'café', 'restaurant', 'beach', 'park', 'school',
        'hotel', 'museum', 'church', 'plaza', 'street', 'avenue',
        'transport', 'bus', 'taxi', 'metro', 'subway', 'train',
        'architecture', 'building', 'view', 'scenic', 'historic',
        'traditional', 'local', 'authentic', 'popular', 'famous'
    ]
    has_details = any(indicator in content_lower for indicator in detail_indicators)

    sentences = [s.strip() for s in content.split('.') if s.strip()]
    avg_sentence_length = sum(len(s) for s in sentences) / len(sentences) if sentences else 0

    return not has_details or avg_sentence_length < 15 or len(content.strip()) < 100

# --- Helper Functions ---

async def get_weather_async(lat, lon):
    if lat is None or lon is None:
        return None
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            # include current weather and today's sunrise/sunset (small payload)
            "current_weather": True,
            "daily": ",".join(["sunrise", "sunset"]),
            "temperature_unit": "celsius",
            "windspeed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto",
        }
        # coerce boolean params to strings
        coerced = {k: (str(v).lower() if isinstance(v, bool) else v) for k, v in params.items()}
        async with get_session() as session:
            async with session.get(url, params=coerced, timeout=ClientTimeout(total=10)) as resp:  # type: ignore
                if resp.status != 200:
                    print(f"[DEBUG app.py] get_weather_async HTTP error: {resp.status}")
                resp.raise_for_status()
                data = await resp.json()
                # return a compact payload containing current weather and today's daily fields
                return {
                    'current_weather': data.get('current_weather'),
                    'daily': data.get('daily'),
                    'timezone': data.get('timezone'),
                    'timezone_abbreviation': data.get('timezone_abbreviation'),
                    'utc_offset_seconds': data.get('utc_offset_seconds')
                }
    except Exception as e:
        print(f"[DEBUG app.py] get_weather_async Exception: {e}")
        return None

async def prewarm_popular_searches():
    if not redis_client or not DEFAULT_PREWARM_CITIES or not DEFAULT_PREWARM_QUERIES:
        return
    sem = asyncio.Semaphore(2)
    async def limited(city, query):
        async with sem:
            await prewarm_search_cache_entry(city, query)
            try:
                await prewarm_neighborhood(city)
            except Exception:
                pass

    tasks = [limited(city, query) for city in DEFAULT_PREWARM_CITIES for query in DEFAULT_PREWARM_QUERIES]
    if tasks:
        app.logger.info("Starting prewarm for %d popular searches", len(tasks))
        await asyncio.gather(*tasks)


async def prewarm_rag_responses(top_n: int | None = None):
    """Prewarm RAG responses for top N seeded cities using configured PREWARM_QUERIES.
    Stores responses in Redis with TTL `RAG_CACHE_TTL` (defaults to 6h via env).
    Best-effort and rate-limited to avoid overloading the Groq API.
    """
    if not redis_client:
        app.logger.info('Redis not available, skipping RAG prewarm')
        return
    try:
        seed_path = Path(__file__).parent.parent / 'data' / 'seeded_cities.json'
        if not seed_path.exists():
            app.logger.info('No seeded_cities.json found; skipping RAG prewarm')
            return
        data = json.loads(seed_path.read_text())
        cities = data.get('cities', [])
        if not cities:
            app.logger.info('No cities in seed; skipping RAG prewarm')
            return
        top_n = int(top_n or PREWARM_RAG_TOP_N)
        # Choose top N by population (descending)
        cities = sorted(cities, key=lambda c: int(c.get('population', 0) or 0), reverse=True)[:top_n]
        queries = DEFAULT_PREWARM_QUERIES or ["Top food"]
        sem = asyncio.Semaphore(int(os.getenv('PREWARM_RAG_CONCURRENCY', '4')))

        async def _warm_city(city_entry):
            async with sem:
                city_name = city_entry.get('name')
                lat = city_entry.get('lat')
                lon = city_entry.get('lon')
                for q in queries:
                    try:
                        # Build cache key consistent with runtime
                        ck_input = f"{q}|{city_name}|{''}|{city_entry.get('countryCode') or ''}|{lat or ''}|{lon or ''}"
                        ck = "rag:" + hashlib.sha256(ck_input.encode('utf-8')).hexdigest()
                        try:
                            existing = None
                            if redis_client:
                                try:
                                    existing = await redis_client.get(ck)
                                    if existing:
                                        await redis_client.expire(ck, int(os.getenv('RAG_CACHE_TTL', 60 * 60 * 6)))
                                        continue
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # Call our internal endpoint to generate answer
                        payload = {"query": q, "engine": "google", "max_results": 3, "city": city_name}
                        try:
                            async with get_session(aiohttp_session) as session:
                                async with session.post("http://localhost:5010/api/chat/rag", json=payload, timeout=ClientTimeout(total=15)) as resp:
                                    if resp.status != 200:
                                        app.logger.debug('Prewarm RAG failed for %s/%s: status %s', city_name, q, resp.status)
                                        continue
                                    data = await resp.json()
                        except Exception as exc:
                            app.logger.debug('Prewarm RAG http failed for %s/%s: %s', city_name, q, exc)
                            continue

                        if data and isinstance(data, dict):
                            ttl = int(os.getenv('RAG_CACHE_TTL', 60 * 60 * 6))
                            try:
                                if redis_client:
                                    await redis_client.setex(ck, ttl, json.dumps(data))
                                    app.logger.info('Prewarmed RAG for %s / %s', city_name, q)
                            except Exception as exc:
                                app.logger.debug('Failed to set RAG cache for %s/%s: %s', city_name, q, exc)
                    except Exception as exc:
                        app.logger.debug('Prewarm RAG exception for %s/%s: %s', city_name, q, exc)

        app.logger.info('Starting RAG prewarm for %d cities', len(cities))
        await asyncio.gather(*[_warm_city(c) for c in cities])
    except Exception:
        app.logger.exception('RAG prewarm failed')

async def prewarm_search_cache_entry(city: str, q: str):
    if not redis_client or not city or not q:
        return
    cache_key = build_search_cache_key(city, q)
    try:
        existing = await redis_client.get(cache_key)
        if existing:
            await redis_client.expire(cache_key, PREWARM_TTL)
            return
    except Exception:
        pass
    try:
        from .persistence import _search_impl
        result = await asyncio.to_thread(_search_impl, {"city": city, "q": q})
        if result:
            await redis_client.set(cache_key, json.dumps(result), ex=PREWARM_TTL)
            app.logger.info("Prewarmed search cache for %s / %s", city, q)
    except Exception as exc:
        app.logger.debug("Search prewarm failed for %s/%s: %s", city, q, exc)

async def prewarm_neighborhood(city: str, lang: str = "en"):
    """Fetch neighborhood lists for a city and store them in redis cache (best-effort)."""
    if not redis_client or not city:
        return
    slug = re.sub(r"[^a-z0-9]+", "_", city.lower())
    cache_key = f"neighborhoods:{slug}:{lang}"
    try:
        existing = await redis_client.get(cache_key)
        if existing:
            await redis_client.expire(cache_key, CACHE_TTL_NEIGHBORHOOD)
            return
    except Exception:
        pass
    try:
        # Prefer async provider and pass our shared session
        try:
            neighborhoods = await multi_provider.async_get_neighborhoods(city=city, lang=lang, session=aiohttp_session)
        except Exception:
            neighborhoods = []
        if neighborhoods:
            await redis_client.set(cache_key, json.dumps(neighborhoods), ex=CACHE_TTL_NEIGHBORHOOD)
            app.logger.info("Prewarmed neighborhoods for %s (%d items)", city, len(neighborhoods))
    except Exception as exc:
        app.logger.debug("Neighborhood prewarm failed for %s: %s", city, exc)

async def prewarm_neighborhoods():
    """Background task to cache popular city neighborhoods"""
    if DISABLE_PREWARM:
        return  # Skip in tests

    for city in POPULAR_CITIES:
        try:
            await prewarm_neighborhood(city)
            app.logger.info("✓ Prewarmed: %s", city)
        except Exception as e:
            app.logger.exception("Prewarm failed for %s: %s", city, e)
        try:
            await asyncio.sleep(float(os.getenv("NEIGHBORHOOD_PREWARM_PAUSE", 1.0)))
        except Exception:
            await asyncio.sleep(1.0)

# --- Utility Functions ---

async def _get_countries():
    """Get list of countries from GeoNames."""
    geonames_user = os.getenv("GEONAMES_USERNAME")
    if not geonames_user:
        # Fallback to comprehensive list of countries
        return [
            {"id": "US", "name": "United States", "code": "US"},
            {"id": "GB", "name": "United Kingdom", "code": "GB"},
            {"id": "CA", "name": "Canada", "code": "CA"},
            {"id": "AU", "name": "Australia", "code": "AU"},
            {"id": "DE", "name": "Germany", "code": "DE"},
            {"id": "FR", "name": "France", "code": "FR"},
            {"id": "IT", "name": "Italy", "code": "IT"},
            {"id": "ES", "name": "Spain", "code": "ES"},
            {"id": "NL", "name": "Netherlands", "code": "NL"},
            {"id": "BR", "name": "Brazil", "code": "BR"},
            {"id": "PT", "name": "Portugal", "code": "PT"},
            {"id": "JP", "name": "Japan", "code": "JP"},
            {"id": "MX", "name": "Mexico", "code": "MX"},
            {"id": "AR", "name": "Argentina", "code": "AR"},
            {"id": "ZA", "name": "South Africa", "code": "ZA"},
            {"id": "CN", "name": "China", "code": "CN"},
            {"id": "IN", "name": "India", "code": "IN"},
            {"id": "RU", "name": "Russia", "code": "RU"},
            {"id": "KR", "name": "South Korea", "code": "KR"},
            {"id": "SE", "name": "Sweden", "code": "SE"},
            {"id": "NO", "name": "Norway", "code": "NO"},
            {"id": "DK", "name": "Denmark", "code": "DK"},
            {"id": "FI", "name": "Finland", "code": "FI"},
            {"id": "PL", "name": "Poland", "code": "PL"},
            {"id": "TR", "name": "Turkey", "code": "TR"},
            {"id": "EG", "name": "Egypt", "code": "EG"},
            {"id": "TH", "name": "Thailand", "code": "TH"},
            {"id": "VN", "name": "Vietnam", "code": "VN"},
            {"id": "MY", "name": "Malaysia", "code": "MY"},
            {"id": "SG", "name": "Singapore", "code": "SG"},
            {"id": "NZ", "name": "New Zealand", "code": "NZ"},
            {"id": "CH", "name": "Switzerland", "code": "CH"},
            {"id": "AT", "name": "Austria", "code": "AT"},
            {"id": "BE", "name": "Belgium", "code": "BE"},
            {"id": "CZ", "name": "Czech Republic", "code": "CZ"},
            {"id": "GR", "name": "Greece", "code": "GR"},
            {"id": "HU", "name": "Hungary", "code": "HU"},
            {"id": "IE", "name": "Ireland", "code": "IE"},
            {"id": "IL", "name": "Israel", "code": "IL"},
            {"id": "LU", "name": "Luxembourg", "code": "LU"},
            {"id": "MT", "name": "Malta", "code": "MT"},
            {"id": "MC", "name": "Monaco", "code": "MC"},
            {"id": "MA", "name": "Morocco", "code": "MA"},
            {"id": "PE", "name": "Peru", "code": "PE"},
            {"id": "PH", "name": "Philippines", "code": "PH"},
            {"id": "RO", "name": "Romania", "code": "RO"},
            {"id": "SK", "name": "Slovakia", "code": "SK"},
            {"id": "SI", "name": "Slovenia", "code": "SI"},
            {"id": "TN", "name": "Tunisia", "code": "TN"},
            {"id": "UA", "name": "Ukraine", "code": "UA"},
            {"id": "UY", "name": "Uruguay", "code": "UY"},
            {"id": "VE", "name": "Venezuela", "code": "VE"},
        ]
    
    async with get_session() as session:
        try:
            url = "http://api.geonames.org/countryInfoJSON"
            params = {"username": geonames_user}
            async with session.get(url, params=params, timeout=ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                countries = []
                for country in data.get("geonames", []):
                    countries.append({
                        "id": country.get("countryCode"),
                        "name": country.get("countryName"),
                        "code": country.get("countryCode")
                    })
                return countries
        except Exception:
            return []

@app.route('/api/parse-dream', methods=['POST'])
async def parse_dream():
    """Parse natural language travel dreams into structured location data.
    Accepts queries like "Paris cafes", "Tokyo nightlife", "Barcelona beaches"
    Returns: { city, country, state, neighborhood, intent, confidence }
    """
    try:
        payload = await request.get_json(silent=True) or {}
        query = (payload.get('query') or '').strip()
        
        if not query:
            return jsonify({'error': 'query required'}), 400
        
        # Initialize result
        result = {
            'city': '',
            'country': '',
            'state': '',
            'neighborhood': '',
            'cityName': '',
            'countryName': '',
            'stateName': '',
            'neighborhoodName': '',
            'intent': '',
            'confidence': 'low'
        }
        
        # Common neighborhood mappings
        neighborhood_mappings = {
            'brooklyn': {'city': 'New York', 'neighborhood': 'Brooklyn', 'country': 'US', 'state': 'NY'},
            'manhattan': {'city': 'New York', 'neighborhood': 'Manhattan', 'country': 'US', 'state': 'NY'},
            'shoreditch': {'city': 'London', 'neighborhood': 'Shoreditch', 'country': 'GB'},
            'camden': {'city': 'London', 'neighborhood': 'Camden', 'country': 'GB'},
            'soho': {'city': 'London', 'neighborhood': 'Soho', 'country': 'GB'},
            'copacabana': {'city': 'Rio de Janeiro', 'neighborhood': 'Copacabana', 'country': 'BR', 'state': 'RJ'},
            'ipanema': {'city': 'Rio de Janeiro', 'neighborhood': 'Ipanema', 'country': 'BR', 'state': 'RJ'},
            'santa teresa': {'city': 'Rio de Janeiro', 'neighborhood': 'Santa Teresa', 'country': 'BR', 'state': 'RJ'},
            'leblon': {'city': 'Rio de Janeiro', 'neighborhood': 'Leblon', 'country': 'BR', 'state': 'RJ'},
            'alfama': {'city': 'Lisbon', 'neighborhood': 'Alfama', 'country': 'PT'},
            'baixa': {'city': 'Lisbon', 'neighborhood': 'Baixa', 'country': 'PT'},
            'chiado': {'city': 'Lisbon', 'neighborhood': 'Chiado', 'country': 'PT'},
            'bairro alto': {'city': 'Lisbon', 'neighborhood': 'Bairro Alto', 'country': 'PT'},
            'belém': {'city': 'Lisbon', 'neighborhood': 'Belém', 'country': 'PT'},
        }
        
        # Intent keywords
        intent_keywords = {
            'coffee': ['coffee', 'cafe', 'cafes', 'espresso', 'latte', 'cappuccino'],
            'nightlife': ['nightlife', 'bars', 'club', 'clubs', 'party', 'drinks', 'pub', 'pubs'],
            'beaches': ['beach', 'beaches', 'coast', 'shore', 'ocean', 'sea', 'sand'],
            'food': ['food', 'eat', 'restaurant', 'restaurants', 'dining', 'cuisine', 'dish'],
            'shopping': ['shop', 'shopping', 'mall', 'stores', 'boutique', 'market'],
            'culture': ['museum', 'museums', 'art', 'culture', 'gallery', 'historical', 'monument'],
            'nature': ['park', 'parks', 'nature', 'hiking', 'garden', 'outdoor'],
            'romance': ['romantic', 'romance', 'couples', 'date', 'sunset'],
            'adventure': ['adventure', 'adventurous', 'extreme', 'thrill'],
            'relaxation': ['relax', 'relaxing', 'spa', 'peaceful', 'quiet'],
        }
        
        # Parse the query
        query_lower = query.lower()
        
        # Dynamic fuzzy matching using Levenshtein distance
        def levenshtein_distance(s1, s2):
            """Calculate Levenshtein distance between two strings"""
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            
            if len(s2) == 0:
                return len(s1)
            
            previous_row = list(range(len(s2) + 1))
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            
            return previous_row[-1]
        
        def find_best_match(query, options, max_distance=2):
            """Find best fuzzy match from options"""
            best_match = None
            best_score = float('inf')
            
            for option in options:
                distance = levenshtein_distance(query, option)
                if distance <= max_distance and distance < best_score:
                    best_score = distance
                    best_match = option
            
            return best_match
        
        # Combine all searchable locations
        all_regions = list(region_mappings.keys())
        all_cities = list(city_mappings.keys())
        all_neighborhoods = list(neighborhood_mappings.keys())
        
        # Try fuzzy matching for regions first
        region_match = find_best_match(query_lower, all_regions)
        if region_match:
            mapping = region_mappings[region_match]
            result.update(mapping)
            result['cityName'] = mapping['city']
            result['countryName'] = mapping['countryName']
            if 'region' in mapping:
                result['region'] = mapping['region']
            result['confidence'] = 'medium'
        
        # Check for explicit neighborhoods first
        neighborhood_match = find_best_match(query_lower, all_neighborhoods)
        if neighborhood_match:
            hood_data = neighborhood_mappings[neighborhood_match]
            result.update(hood_data)
            result['neighborhoodName'] = hood_data['neighborhood']
            result['cityName'] = hood_data['city']
            result['confidence'] = 'high'
        
        # If no neighborhood found, check for cities
        if not result['city']:
            city_match = find_best_match(query_lower, all_cities)
            if city_match:
                city_data = city_mappings[city_match]
                result.update(city_data)
                result['cityName'] = city_data['city']
                result['confidence'] = 'high'
        
        # Extract intent
        detected_intent = []
        for intent, keywords in intent_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_intent.append(intent)
        
        if detected_intent:
            result['intent'] = ', '.join(detected_intent)
            # Boost confidence if we have both location and intent
            if result['city'] and result['confidence'] == 'high':
                result['confidence'] = 'very_high'
            elif result['city']:
                result['confidence'] = 'medium'
        
        # If no city found, try to extract using AI as fallback
        if not result['city']:
            try:
                # Use Groq for natural language parsing as fallback
                from city_guides.groq.traveland_rag import recommender
                if recommender.api_key:
                    messages = [
                        {"role": "system", "content": "Extract location information from travel queries. Return JSON with city, country, and optionally state/neighborhood. Be conservative - only return locations you're confident about."},
                        {"role": "user", "content": f"Extract location from: {query}"}
                    ]
                    response = await recommender.call_groq_chat(messages, timeout=10)
                    if response:
                        import json
                        parsed = json.loads(response["choices"][0]["message"]["content"])
                        if parsed.get('city'):
                            result.update(parsed)
                            result['cityName'] = parsed.get('city', '')
                            result['countryName'] = parsed.get('country', '')
                            result['stateName'] = parsed.get('state', '')
                            result['neighborhoodName'] = parsed.get('neighborhood', '')
                            result['confidence'] = 'medium'
            except Exception as e:
                app.logger.warning(f"AI parsing fallback failed: {e}")
        
        # Final fallback: try simple city name extraction
        if not result['city']:
            words = query.lower().split()
            # Check multi-word regions first
            query_lower = query.lower()
            for region_name, mapping in region_mappings.items():
                if region_name in query_lower:
                    result.update(mapping)
                    result['cityName'] = mapping['city']
                    result['countryName'] = mapping['countryName']
                    if 'region' in mapping:
                        result['region'] = mapping['region']
                    result['confidence'] = 'low'
                    break
            
            # If still no city, check single words
            if not result['city']:
                for word in words:
                    if word in city_mappings:
                        mapping = city_mappings[word]
                        result.update(mapping)
                        result['cityName'] = mapping['city']
                        result['countryName'] = mapping['countryName']
                        if 'stateName' in mapping:
                            result['stateName'] = mapping['stateName']
                        result['confidence'] = 'low'
                        break
        
        # Clean up result
        if not result['city']:
            return jsonify({'error': 'no_location_detected', 'query': query}), 400
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.exception('Dream parsing failed')
        return jsonify({'error': 'parsing_failed', 'details': str(e)}), 500

@app.route('/api/location-suggestions', methods=['POST'])
async def location_suggestions():
    """Provide location suggestions based on partial input with learning weights"""
    try:
        payload = await request.get_json(silent=True) or {}
        query = (payload.get('query') or '').strip().lower()
        
        if len(query) < 2:
            return jsonify({'suggestions': []})
        
        suggestions = []
        
        # Get all locations with their weights
        all_locations = []
        
        # Trending destinations 2025 (higher priority)
        trending_destinations = {
            'london': 3.0, 'barcelona': 3.0, 'bangkok': 3.0, 'paris': 3.0,
            'rome': 3.0, 'tokyo': 3.0, 'new york': 3.0, 'amsterdam': 3.0,
            'dubai': 3.0, 'singapore': 3.0, 'venice': 2.5, 'prague': 2.5,
            'madrid': 2.5, 'berlin': 2.5, 'vienna': 2.5, 'zurich': 2.5,
            'copenhagen': 2.5, 'stockholm': 2.5, 'oslo': 2.5, 'helsinki': 2.5,
            'warsaw': 2.5, 'athens': 2.5, 'dublin': 2.5, 'edinburgh': 2.5,
            'lisbon': 2.5, 'budapest': 2.5, 'istanbul': 2.5, 'cairo': 2.5,
            'mumbai': 2.5
        }
        
        # Seasonal recommendations (current month)
        from datetime import datetime
        current_month = datetime.now().month
        
        user_hemisphere = detect_hemisphere_from_searches()
        current_seasonal = get_seasonal_destinations(current_month, user_hemisphere)
        
        # Add cities with weights (base weight + trending bonus + seasonal bonus)
        for city, data in city_mappings.items():
            base_weight = get_location_weight(city)
            trending_bonus = trending_destinations.get(city, 1.0)
            seasonal_bonus = current_seasonal.get(city, 1.0)
            weight = base_weight * trending_bonus * seasonal_bonus
            if query in city or levenshtein_distance(query, city) <= 2:
                all_locations.append({
                    'display_name': data['city'],
                    'detail': data['countryName'],
                    'type': 'city',
                    'weight': weight,
                    'exact_match': query == city
                })
        
        # Add regions with weights
        for region, data in region_mappings.items():
            weight = get_location_weight(region)
            if query in region or levenshtein_distance(query, region) <= 2:
                all_locations.append({
                    'display_name': data['city'],
                    'detail': f"{data['countryName']} - {region}",
                    'type': 'region',
                    'weight': weight,
                    'exact_match': query == region
                })
        
        # Sort by weight and relevance
        all_locations.sort(key=lambda x: (not x['exact_match'], -x['weight'], len(x['display_name'])))
        
        # Return top 5 suggestions
        suggestions = all_locations[:5]
        
        return jsonify({'suggestions': suggestions})
        
    except Exception:
        app.logger.exception('Location suggestions failed')
        return jsonify({'error': 'suggestions_failed'}), 500

@app.route('/api/geonames-search', methods=['POST'])
async def geonames_search():
    """Search for any city using GeoNames API"""
    try:
        payload = await request.get_json(silent=True) or {}
        query = (payload.get('query') or '').strip()
        
        if len(query) < 2:
            return jsonify({'suggestions': []})
        
        # Get GeoNames username
        geonames_user = os.getenv("GEONAMES_USERNAME")
        if not geonames_user:
            # Try to read from .env file
            try:
                env_path = Path(__file__).parent.parent.parent / ".env"
                if env_path.exists():
                    with env_path.open("r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("GEONAMES_USERNAME="):
                                geonames_user = line.split("=", 1)[1].strip().strip('"').strip("'")
                                break
            except Exception:
                pass
        
        if not geonames_user:
            app.logger.warning("GeoNames username not configured")
            return jsonify({'suggestions': []})
        
        # Search GeoNames for cities
        async with get_session() as session:
            params = {
                "username": geonames_user,
                "q": query,
                "featureClass": "P",  # Populated places only
                "maxRows": 10,
                "style": "FULL"
            }
            
            async with session.get("http://api.geonames.org/searchJSON", params=params, timeout=ClientTimeout(total=10)) as response:
                if response.status != 200:
                    app.logger.error(f"GeoNames API error: {response.status}")
                    return jsonify({'suggestions': []})
                
                data = await response.json()
                suggestions = []
                
                for geoname in data.get("geonames", []):
                    # Extract city information
                    city_name = geoname.get("name", "")
                    country_name = geoname.get("countryName", "")
                    country_code = geoname.get("countryCode", "")
                    population = geoname.get("population", 0) or 0
                    feature_code = geoname.get("fcode", "")
                    
                    if not city_name or not country_name:
                        continue
                    
                    # Skip postal districts (arrondissements) - they look like "Lyon 03", "Paris 15"
                    import re
                    if re.match(r'^.+\s+\d{2}$', city_name):
                        app.logger.debug(f"Skipping postal district: {city_name}")
                        continue
                    
                    # Skip suburbs and small localities - tourists want major cities
                    # PPLX = section of populated place (suburb), PPLQ = abandoned place
                    if feature_code in ["PPLX", "PPLQ", "PPLH"]:
                        app.logger.debug(f"Skipping suburb/abandoned place: {city_name} ({feature_code})")
                        continue
                    
                    # Skip Lyon suburbs (communes in Lyon metro area) - tourists want Lyon
                    if country_code == "FR" and city_name in ["Villeurbanne", "Bron", "Vénissieux", "Saint-Priest", "Meyzieu", "Rillieux-la-Pape", "Décines-Charpieu"]:
                        app.logger.debug(f"Skipping Lyon suburb: {city_name}")
                        continue
                    
                    # Skip very small places (less than 50,000 people) unless it's a hardcoded destination
                    if population > 0 and population < 50000:
                        app.logger.debug(f"Skipping small place: {city_name} (pop: {population})")
                        continue
                    
                    # Get emoji for country
                    country_emoji = ""
                    try:
                        if country_code:
                            # Hardcoded map of country codes to flag emojis for reliability
                            country_emoji_map = {
                                'FR': '🇫🇷', 'JP': '🇯🇵', 'ES': '🇪🇸', 'GB': '🇬🇧', 'US': '🇺🇸',
                                'IT': '🇮🇹', 'DE': '🇩🇪', 'NL': '🇳🇱', 'PT': '🇵🇹', 'SE': '🇸🇪',
                                'NO': '🇳🇴', 'DK': '🇩🇰', 'IS': '🇮🇸', 'CA': '🇨🇦', 'AU': '🇦🇺',
                                'CN': '🇨🇳', 'IN': '🇮🇳', 'BR': '🇧🇷', 'AR': '🇦🇷', 'ZA': '🇿🇦',
                                'MX': '🇲🇽', 'AE': '🇦🇪', 'SG': '🇸🇬', 'HK': '🇭🇰', 'TH': '🇹🇭',
                                'KR': '🇰🇷', 'TW': '🇹🇼', 'MY': '🇲🇾', 'ID': '🇮🇩', 'PH': '🇵🇭',
                                'VN': '🇻🇳', 'TR': '🇹🇷', 'IL': '🇮🇱', 'EG': '🇪🇬', 'MA': '🇲🇦',
                                'SD': '🇸🇩', 'MR': '🇲🇷', 'DZ': '🇩🇿', 'LY': '🇱🇾', 'TN': '🇹🇳',
                                'NZ': '🇳🇿', 'CH': '🇨🇭', 'AT': '🇦🇹', 'BE': '🇧🇪', 'CZ': '🇨🇿',
                                'GR': '🇬🇷', 'HU': '🇭🇺', 'IE': '🇮🇪', 'PL': '🇵🇱', 'RO': '🇷🇴',
                                'SK': '🇸🇰', 'SI': '🇸🇮', 'UA': '🇺🇦', 'UY': '🇺🇾', 'VE': '🇻🇪',
                                'ME': '🇲🇪', 'RS': '🇷🇸', 'BA': '🇧🇦', 'AL': '🇦🇱', 'MK': '🇲🇰',
                                'UG': '🇺🇬', 'KE': '🇰🇪', 'TZ': '🇹🇿', 'GH': '🇬🇭', 'NG': '🇳🇬',
                                'CI': '🇨🇮', 'SN': '🇸🇳', 'ML': '🇲🇱', 'BF': '🇧🇫', 'NE': '🇳🇪',
                                'CM': '🇨🇲', 'CD': '🇨🇩', 'CG': '🇨🇬', 'GA': '🇬🇦', 'GQ': '🇬🇶',
                                'AO': '🇦🇴', 'ZM': '🇿🇲', 'MW': '🇲🇼', 'MZ': '🇲🇿', 'ZW': '🇿🇼',
                                'BW': '🇧🇼', 'NA': '🇳🇦', 'SZ': '🇸🇿', 'LS': '🇱🇸', 'LR': '🇱🇷',
                                'SL': '🇸🇱', 'GN': '🇬🇳', 'GW': '🇬🇼', 'CV': '🇨🇻', 'ST': '🇸🇹',
                                'ER': '🇪🇷', 'DJ': '🇩🇯', 'SO': '🇸🇴', 'ET': '🇪🇹', 'SS': '🇸🇸',
                                'TD': '🇹🇩', 'CF': '🇨🇫',
                                'SA': '🇸🇦', 'IQ': '🇮🇶', 'IR': '🇮🇷', 'AF': '🇦🇫', 'PK': '🇵🇰',
                                'BD': '🇧🇩', 'LK': '🇱🇰', 'MM': '🇲🇲', 'TH': '🇹🇭', 'KH': '🇰🇭',
                                'LA': '🇱🇦', 'VN': '🇻🇳', 'PH': '🇵🇭', 'MY': '🇲🇾', 'SG': '🇸🇬',
                                'ID': '🇮🇩', 'BN': '🇧🇳', 'TL': '🇹🇱', 'PG': '🇵🇬', 'FJ': '🇫🇯',
                                'SB': '🇸🇧', 'VU': '🇻🇺', 'NC': '🇳🇨', 'PF': '🇵🇫', 'WS': '🇼🇸',
                                'KI': '🇰🇮', 'TV': '🇹🇻', 'TO': '🇹🇴', 'NU': '🇳🇺', 'PW': '🇵🇼',
                                'FM': '🇫🇲', 'MH': '🇲🇭', 'MP': '🇲🇵', 'GU': '🇬🇺', 'AS': '🇦🇸',
                                'KY': '🇰🇾', 'BM': '🇧🇲', 'VG': '🇻🇬', 'AI': '🇦🇮', 'MS': '🇲🇸',
                                'TC': '🇹🇨', 'DO': '🇩🇴', 'HT': '🇭🇹', 'JM': '🇯🇲', 'BB': '🇧🇧',
                                'GD': '🇬🇩', 'TT': '🇹🇹', 'LC': '🇱🇨', 'VC': '🇻🇨', 'AG': '🇦🇬',
                                'DM': '🇩🇲', 'KN': '🇰🇳', 'BS': '🇧🇸', 'BZ': '🇧🇿', 'GT': '🇬🇹',
                                'SV': '🇸🇻', 'HN': '🇭🇳', 'NI': '🇳🇮', 'CR': '🇨🇷', 'PA': '🇵🇦',
                                'CO': '🇨🇴', 'VE': '🇻🇪', 'GY': '🇬🇾', 'SR': '🇸🇷', 'GF': '🇬🇫',
                                'PE': '🇵🇪', 'BO': '🇧🇴', 'PY': '🇵🇾', 'UY': '🇺🇾', 'CL': '🇨🇱',
                                'AR': '🇦🇷', 'EC': '🇪🇨', 'CU': '🇨🇺', 'PR': '🇵🇷', 'VI': '🇻🇮',
                                'GL': '🇬🇱', 'CA': '🇨🇦', 'US': '🇺🇸', 'MX': '🇲🇽'
                            }
                            country_emoji = country_emoji_map.get(country_code.upper(), '')
                    except Exception:
                        pass
                    
                    suggestions.append({
                        "city": city_name,
                        "country": country_name,
                        "emoji": country_emoji,
                        "geonameId": geoname.get("geonameId"),
                        "lat": geoname.get("lat"),
                        "lng": geoname.get("lng"),
                        "population": population,
                        "source": "geonames"
                    })
                
                # Sort by population (largest cities first) to prioritize major cities over suburbs
                suggestions.sort(key=lambda x: x.get("population", 0) or 0, reverse=True)
                
                return jsonify({'suggestions': suggestions})
        
    except Exception as e:
        app.logger.exception(f'GeoNames search failed: {e}')
        return jsonify({'error': 'geonames_search_failed'}), 500

@app.route('/api/unsplash-search', methods=['POST'])
async def unsplash_search():
    """Secure proxy for Unsplash API - hides API keys from frontend"""
    try:
        payload = await request.get_json(silent=True) or {}
        query = payload.get('query', '').strip()
        per_page = min(int(payload.get('per_page', 3)), 10)
        
        if not query:
            return jsonify({'photos': []})
        
        # Get Unsplash key from environment (never exposed to frontend)
        unsplash_key = os.getenv("UNSPLASH_KEY")
        if not unsplash_key:
            app.logger.warning("Unsplash key not configured")
            return jsonify({'photos': []})
        
        # Make secure request to Unsplash
        params = {
            'query': query,
            'per_page': per_page,
            'orientation': 'landscape',
            'content_filter': 'high',
            'order_by': 'relevant'
        }
        
        headers = {
            'Authorization': f'Client-ID {unsplash_key}',
            'Accept-Encoding': 'gzip, deflate',
            'User-Agent': 'TravelLand/1.0'
        }
        
        async with get_session() as session:
            async with session.get(
                "https://api.unsplash.com/search/photos",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    app.logger.error(f"Unsplash API error: {response.status}")
                    return jsonify({'photos': []})
                
                data = await response.json()
                
                # Transform response to only expose necessary data
                photos = []
                for photo in data.get('results', []):
                    photos.append({
                        'id': photo['id'],
                        'url': photo['urls']['regular'],
                        'thumb_url': photo['urls']['thumb'],
                        'description': photo.get('description', ''),
                        'alt_description': photo.get('alt_description', ''),
                        'user': {
                            'name': photo['user']['name'],
                            'username': photo['user']['username'],
                            'profile_url': photo['user']['links']['html']
                        },
                        'links': {
                            'unsplash': photo['links']['html']
                        }
                    })
                
                return jsonify({'photos': photos})
        
    except Exception as e:
        app.logger.exception(f'Unsplash proxy failed: {e}')
        app.logger.error('Query was: %s', locals().get('query'))
        app.logger.error('Unsplash key configured: %s', bool(os.getenv('UNSPLASH_KEY')))
        return jsonify({'error': 'unsplash_search_failed'}), 500

@app.route('/api/pixabay-search', methods=['POST'])
async def pixabay_search():
    """Secure proxy for Pixabay API - hides API keys from frontend"""
    try:
        payload = await request.get_json(silent=True) or {}
        query = payload.get('query', '').strip()
        per_page = min(int(payload.get('per_page', 3)), 20)
        
        if not query:
            return jsonify({'photos': []})
        
        # Get Pixabay key from environment (never exposed to frontend)
        pixabay_key = os.getenv("PIXABAY_KEY")
        if not pixabay_key:
            app.logger.warning("Pixabay key not configured")
            return jsonify({'photos': []})
        
        # Make secure request to Pixabay
        params = {
            'key': pixabay_key,
            'q': query,
            'per_page': per_page,
            'safesearch': 'true',
            'image_type': 'photo',
            'orientation': 'horizontal'
        }
        
        async with get_session() as session:
            async with session.get(
                "https://pixabay.com/api/",
                params=params,
                headers={'Accept-Encoding': 'gzip, deflate', 'User-Agent': 'TravelLand/1.0'},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    app.logger.error(f"Pixabay API error: {response.status}")
                    return jsonify({'photos': []})
                
                data = await response.json()
                
                # Transform response to only expose necessary data
                photos = []
                for hit in data.get('hits', []):
                    photos.append({
                        'id': hit['id'],
                        'url': hit['webformatURL'],
                        'thumb_url': hit['previewURL'],
                        'description': hit.get('tags', ''),
                        'user': hit.get('user', 'Pixabay User'),
                        'links': {
                            'pixabay': hit['pageURL']
                        }
                    })
                
                return jsonify({'photos': photos})
        
    except Exception as e:
        app.logger.exception(f'Pixabay proxy failed: {e}')
        return jsonify({'error': 'pixabay_search_failed'}), 500

@app.route('/api/log-suggestion-success', methods=['POST'])
async def log_suggestion_success():
    """Log successful suggestion usage for learning"""
    try:
        payload = await request.get_json(silent=True) or {}
        suggestion = payload.get('suggestion', '').strip().lower()
        
        if suggestion:
            increment_location_weight(suggestion)
        
        return jsonify({'success': True})
        
    except Exception:
        app.logger.exception('Failed to log suggestion success')
        return jsonify({'error': 'logging_failed'}), 500

# Import and register routes from routes module
from city_guides.src.routes import register_routes  # noqa: E402
register_routes(app)

# Register category routes for cache management
from city_guides.src.simple_categories import register_category_routes  # noqa: E402
register_category_routes(app)

if __name__ == "__main__":
    # Load environment variables from .env file manually
    env_file = PROJECT_ROOT / ".env"
    print(f"[DEBUG] Loading .env from {env_file}")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
    
    # Prefer standard env vars used by many hosts (Render/Heroku/etc.), but
    # default to 5010 to match project docs and avoid UI/port mismatches.
    port = int(os.getenv("PORT") or os.getenv("QUART_PORT") or 5010)
    app.run(host="0.0.0.0", port=port)