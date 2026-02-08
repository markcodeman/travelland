"""
Chat routes: RAG-powered chat endpoint with Marco AI
"""
import os
import time
import json
import hashlib
import re
import random
from quart import Blueprint, request, jsonify

from city_guides.src.metrics import increment, observe_latency
from city_guides.src.marco_response_enhancer import should_call_groq, analyze_user_intent

bp = Blueprint('chat', __name__)


@bp.route("/api/chat/rag", methods=["POST"])
async def api_chat_rag():
    """
    RAG chat endpoint: Accepts a user query, runs DDGS web search, synthesizes an answer with Groq, and returns a unified AI response.
    Request JSON: {"query": "...", "engine": "google" (optional), "max_results": 8 (optional), "city": "...", "lat": ..., "lon": ...}
    Response JSON: {"answer": "..."}
    """
    try:
        from city_guides.src.app import app, redis_client, recommender, ddgs_search
        from city_guides.src.routes.search import fetch_city_wikipedia
        
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
                    selected_fact = random.choice(facts)
                    answer = f"Here's an interesting fact about {city}: {selected_fact}"
                    return jsonify({"answer": answer})
            except Exception as e:
                app.logger.debug(f'Fun facts lookup failed for {city}: {e}')
                # Continue to normal flow if seeded data not available
        
        # Compute a cache key for this query+city and try Redis cache to avoid repeating long work
        cache_key = None
        try:
            if redis_client:
                ck_input = f"{query}|{city}|{state}|{country}|{lat}|{lon}"
                cache_key = "rag:" + hashlib.sha256(ck_input.encode('utf-8')).hexdigest()
                cached = await redis_client.get(cache_key)
                if cached:
                    app.logger.info('RAG cache hit for key %s', cache_key)
                    try:
                        # metrics: cache hit
                        await increment('rag.cache_hit')
                    except Exception:
                        pass
                    try:
                        cached_parsed = json.loads(cached)
                        return jsonify(cached_parsed)
                    except Exception:
                        app.logger.debug('Failed to parse cached RAG response for %s', cache_key)
        except Exception:
            app.logger.exception('Redis cache lookup failed')

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
        # Cache the result for repeated queries to improve latency on hot paths
        try:
            if redis_client and cache_key:
                ttl = int(os.getenv('RAG_CACHE_TTL', 60 * 60 * 6))  # default 6 hours
                await redis_client.setex(cache_key, ttl, json.dumps(result_payload))
                app.logger.info('Cached RAG response %s (ttl=%s)', cache_key, ttl)
        except Exception:
            app.logger.exception('Failed to cache RAG response')

        return jsonify(result_payload)
    except Exception as e:
        from city_guides.src.app import app
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


def register(app):
    """Register chat blueprint with app"""
    app.register_blueprint(bp)
