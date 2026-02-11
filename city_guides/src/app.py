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
from city_guides.config import config
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

aiohttp_session: aiohttp.ClientSession | None = None

# Global async clients
aiohttp_session: aiohttp.ClientSession | None = None
redis_client: aioredis.Redis | None = None

# Attach active_searches to app context to avoid global mutable state
app.active_searches = {}

# Configuration constants
CACHE_TTL_NEIGHBORHOOD = config.get_int("CACHE_TTL_NEIGHBORHOOD", 3600)  # 1 hour
CACHE_TTL_RAG = config.get_int("CACHE_TTL_RAG", 1800)  # 30 minutes
CACHE_TTL_SEARCH = config.get_int("CACHE_TTL_SEARCH", 1800)  # 30 minutes
CACHE_TTL_TELEPORT = config.get_int("CACHE_TTL_TELEPORT", 86400)  # 24 hours
DDGS_CONCURRENCY = config.get_int("DDGS_CONCURRENCY", 5)
DDGS_TIMEOUT = config.get_int("DDGS_TIMEOUT", 5)
DEFAULT_PREWARM_CITIES = os.getenv("DEFAULT_PREWARM_CITIES", "").split(",") if os.getenv("DEFAULT_PREWARM_CITIES") else []
DEFAULT_PREWARM_QUERIES = os.getenv("DEFAULT_PREWARM_QUERIES", "").split(",") if os.getenv("DEFAULT_PREWARM_QUERIES") else []
DISABLE_PREWARM = os.getenv("DISABLE_PREWARM", "false").lower() == "true"
GEOCODING_TIMEOUT = config.get_int("GEOCODING_TIMEOUT", 10)
GROQ_TIMEOUT = config.get_int("GROQ_TIMEOUT", 30)
POPULAR_CITIES = os.getenv("POPULAR_CITIES", "").split(",") if os.getenv("POPULAR_CITIES") else []
PREWARM_RAG_CONCURRENCY = config.get_int("PREWARM_RAG_CONCURRENCY", 3)
VERBOSE_OPEN_HOURS = os.getenv("VERBOSE_OPEN_HOURS", "false").lower() == "true"
# Constants
PREWARM_TTL = CACHE_TTL_SEARCH
PREWARM_RAG_TOP_N = config.get_int('PREWARM_RAG_TOP_N', 50)

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


# ==============================================================================
# ROUTES EXTRACTED TO BLUEPRINT MODULES
# ==============================================================================
# All 26 route handlers have been extracted to modular blueprints in:
# city_guides/src/routes/
#
# Route registration happens via: register_routes(app) at line ~1200
# See ROUTE_EXTRACTION_COMPLETE.md for full details
# ==============================================================================

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
        redis_client = aioredis.from_url(config.redis_url)
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
    return {"GROQ_ENABLED": bool(config.groq_api_key)}

# --- Core Routes ---

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
        sem = asyncio.Semaphore(config.get_int('PREWARM_RAG_CONCURRENCY', 4))

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
                                        await redis_client.expire(ck, config.get_int('RAG_CACHE_TTL', 60 * 60 * 6))
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
                            ttl = config.get_int('RAG_CACHE_TTL', 60 * 60 * 6)
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

# Import and register routes from routes module
from city_guides.src.routes import register_routes  # noqa: E402
register_routes(app)

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