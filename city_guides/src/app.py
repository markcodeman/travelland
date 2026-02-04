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
    levenshtein_distance,
    find_best_match
)
from city_guides.src.services.learning import (
    _location_weights,
    get_location_weight,
    increment_location_weight,
    detect_hemisphere_from_searches
)
from city_guides.src.services.pixabay import pixabay_service
from city_guides.src.dynamic_neighborhoods import get_neighborhoods_for_city

"""
Refactored TravelLand app.py with modular structure
"""

from quart import Quart, request, jsonify, render_template
from quart_cors import cors
import os
import sys
import asyncio
import aiohttp
import json
import hashlib
import re
import time
import requests
from pathlib import Path
from redis import asyncio as aioredis
import logging

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modules
from city_guides.src.persistence import (
    build_search_cache_key,
    ensure_bbox,
    format_venue,
    determine_budget,
    determine_price_range,
    generate_description,
    format_venue_for_display,
    _humanize_opening_hours,
    _compute_open_now,
    calculate_search_radius,
    get_country_for_city,
    get_provider_links,
    shorten_place,
    get_currency_for_country,
    get_currency_name,
    get_cost_estimates,
    fetch_safety_section,
    fetch_us_state_advisory,
    get_weather,
    _fetch_image_from_website,
    _is_relevant_wikimedia_image,
    _persist_quick_guide
)
from city_guides.src.validation import validate_neighborhood
from city_guides.src.enrichment import get_neighborhood_enrichment
from city_guides.providers import multi_provider
from city_guides.providers.geocoding import geocode_city, reverse_geocode
from city_guides.providers.overpass_provider import async_geocode_city
from city_guides.providers.utils import get_session
from city_guides.src.semantic import semantic
from city_guides.src.geo_enrichment import enrich_neighborhood
from city_guides.src.synthesis_enhancer import SynthesisEnhancer
from city_guides.src.snippet_filters import looks_like_ddgs_disambiguation_text
from city_guides.src.neighborhood_disambiguator import NeighborhoodDisambiguator

# Create Quart app instance at the very top so it is always defined before any route decorators
app = Quart(__name__, static_folder="/home/markm/TravelLand/city_guides/static", static_url_path='', template_folder="/home/markm/TravelLand/city_guides/templates")

# Configure CORS
cors(app, allow_origin=["http://localhost:5174", "https://travelland-w0ny.onrender.com"], allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Cleanup Pixabay service on app shutdown
@app.before_serving
async def startup():
    """Initialize services on startup"""
    pass

@app.after_serving
async def shutdown():
    """Clean up services on shutdown"""
    await pixabay_service.close()

# Global async clients
aiohttp_session: aiohttp.ClientSession | None = None
redis_client: aioredis.Redis | None = None

# Track active long-running searches (search_id -> metadata)
active_searches = {}

# Constants
CACHE_TTL_TELEPORT = int(os.getenv("CACHE_TTL_TELEPORT", "86400"))  # 24 hours
VERBOSE_OPEN_HOURS = os.getenv("VERBOSE_OPEN_HOURS", "false").lower() == "true"
DEFAULT_PREWARM_CITIES = os.getenv("SEARCH_PREWARM_CITIES", "London,Paris")
PREWARM_QUERIES = [q.strip() for q in os.getenv("SEARCH_PREWARM_QUERIES", "Top food").split(",") if q.strip()]
PREWARM_TTL = int(os.getenv("SEARCH_PREWARM_TTL", "3600"))
NEIGHBORHOOD_CACHE_TTL = int(os.getenv("NEIGHBORHOOD_CACHE_TTL", 60 * 60 * 24 * 7))  # 7 days
PREWARM_RAG_TOP_N = int(os.getenv('PREWARM_RAG_TOP_N', '50'))
POPULAR_CITIES = [c.strip() for c in os.getenv("POPULAR_CITIES", "London,Paris,New York,Tokyo,Rome,Barcelona,Bruges,Hallstatt,Chefchaouen,Ravello,Colmar,Sintra,Ghent,Annecy,Kotor,Cesky Krumlov,Rothenburg,Positano").split(",") if c.strip()]
DISABLE_PREWARM = True  # os.getenv("DISABLE_PREWARM", "false").lower() == "true"


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

    async def _fetch_for_title(title: str):
        slug = title.replace(' ', '_')
        summary = await fetch_wikipedia_summary(title, lang="en", city=city)
        if summary:
            return summary.strip(), f"https://en.wikipedia.org/wiki/{slug}"
        return None

    # Try direct titles first
    for title in _candidates():
        try:
            result = await _fetch_for_title(title)
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
                async with session.get("https://en.wikipedia.org/w/api.php", params=params, timeout=6) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    if isinstance(data, list) and len(data) >= 2 and data[1]:
                        best_title = data[1][0]
                        try:
                            result = await _fetch_for_title(best_title)
                            if result:
                                return result
                        except Exception:
                            app.logger.exception('OpenSearch Wikipedia summary failed for %s via %s', city, best_title)
    except Exception:
        app.logger.exception('Wikipedia open search failed for %s', city)

    return None

# DDGS provider import is optional at module import time (tests may not have ddgs installed)
try:
    from city_guides.providers.ddgs_provider import ddgs_search as _ddgs_provider_search

    async def ddgs_search(*args, **kwargs):
        return await _ddgs_provider_search(*args, **kwargs)

    app.logger.info('DDGS provider enabled for neighborhood search')
except Exception as ddgs_import_err:

    async def ddgs_search(*args, **kwargs):
        app.logger.warning('DDGS provider unavailable (%s); returning empty results', ddgs_import_err)
        return []

    app.logger.debug('DDGS provider not available at module import time; falling back to empty search results')

from city_guides.groq.traveland_rag import recommender

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
            requested_max = int(data.get("max_results", 3))
        except Exception:
            requested_max = 3
        DEFAULT_DDGS_MAX = int(os.getenv('DDGS_MAX_RESULTS', '3'))
        max_results = min(requested_max, DEFAULT_DDGS_MAX)
        DEFAULT_DDGS_TIMEOUT = float(os.getenv('DDGS_TIMEOUT', '5'))
        city = data.get("city", "")
        state = data.get("state", "")
        country = data.get("country", "")
        lat = data.get("lat")
        lon = data.get("lon")
        if not query:
            return jsonify({"error": "Missing query"}), 400

        full_query = query
        # Compute a cache key for this query+city and try Redis cache to avoid repeating long work
        try:
            cache_key = None
            if redis_client:
                ck_input = f"{query}|{city}|{state}|{country}|{lat}|{lon}"
                cache_key = "rag:" + hashlib.sha256(ck_input.encode('utf-8')).hexdigest()
                cached = await redis_client.get(cache_key)
                if cached:
                    app.logger.info('RAG cache hit for key %s', cache_key)
                    try:
                        cached_parsed = json.loads(cached)
                        return jsonify(cached_parsed)
                    except Exception:
                        app.logger.debug('Failed to parse cached RAG response for %s', cache_key)
        except Exception:
            app.logger.exception('Redis cache lookup failed')

        # If lat/lon provided, use them to fetch venues
        if lat and lon:
            # Reverse geocode to get city if not provided
            if not city:
                city_name = await reverse_geocode(lat, lon)
                if city_name:
                    city = city_name
            # Fetch venues for the coordinates
            # Fetch venues for the coordinates using reverse geocoded city
            venues = await multi_provider.async_discover_pois(city, poi_type="all", limit=10)
            # Add venue context to the query
            venue_context = "\n\nNearby venues: " + ", ".join([v['name'] for v in venues]) if venues else ""
            full_query += venue_context
        elif city:
            # Geocode the city to get coordinates
            geocoded = await geocode_city(city)
            if geocoded:
                lat = geocoded.get('lat')
                lon = geocoded.get('lon')
                if lat and lon:
                    venues = await multi_provider.async_discover_pois(city, poi_type="all", limit=10)
                    venue_context = "\n\nNearby venues: " + ", ".join([v['name'] for v in venues]) if venues else ""
                    full_query += venue_context

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
        system_prompt = (
            "You are Marco, a travel AI assistant. Given a user query and a set of recent web search snippets, synthesize a helpful, accurate, and up-to-date answer. "
            "Never mention your sources or that you used web search. Respond as a unified expert, not a search engine."
        )
        location_fragment = f" in {city}" if city else ""
        user_prompt = f"User query: {query}{location_fragment}\n\nRelevant web snippets:\n{context_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Call Groq via recommender (direct call_groq_chat) with a shorter timeout to keep UX snappy
        GROQ_TIMEOUT = int(os.getenv('GROQ_CHAT_TIMEOUT', '10'))
        groq_resp = recommender.call_groq_chat(messages, timeout=GROQ_TIMEOUT)
        if not groq_resp:
            return jsonify({"error": "Groq API call failed"}), 502
        try:
            answer = groq_resp["choices"][0]["message"]["content"]
        except Exception:
            answer = None
        if not answer:
            return jsonify({"error": "No answer generated"}), 502

        result_payload = {"answer": answer.strip()}
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
    global aiohttp_session, redis_client
    aiohttp_session = aiohttp.ClientSession(headers={"User-Agent": "city-guides-async"})
    try:
        redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        await redis_client.ping()  # type: ignore
        app.logger.info("✅ Redis connected")
        if DEFAULT_PREWARM_CITIES and PREWARM_QUERIES:
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
    if aiohttp_session:
        await aiohttp_session.close()
    if redis_client:
        await redis_client.close()

@app.context_processor
def inject_feature_flags():
    return {"GROQ_ENABLED": bool(os.getenv("GROQ_API_KEY"))}

# --- Core Routes ---

@app.route("/<path:path>", methods=["GET"])
async def catch_all(path):
    # Serve React app for client-side routing
    if path.startswith("api/") or path.startswith("static/"):
        # Let Quart handle API and static routes normally
        from quart import abort
        abort(404)
    return await app.send_static_file("index.html")

@app.route("/weather", methods=["POST"])
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

@app.route("/neighborhoods", methods=["GET"])
async def get_neighborhoods():
    """Get neighborhoods for a city or location.
    Query params: city, lat, lon, lang
    Returns: { cached: bool, neighborhoods: [] }
    """
    city = request.args.get("city")
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    lang = request.args.get("lang", "en")

    # If city-only query, resolve to coordinates first to avoid ambiguous city names (e.g. Athens, GA)
    geocoded = False
    if city and not (lat and lon):
        try:
            geo = await geocode_city(city)
            if geo and geo.get("lat") is not None and geo.get("lon") is not None:
                lat = str(geo["lat"])
                lon = str(geo["lon"])
                geocoded = True
        except Exception:
            app.logger.exception("geocode_city failed for neighborhoods: %s", city)

    # Create slug for caching
    if lat and lon:
        slug = f"{lat}_{lon}"
    else:
        return jsonify({"error": "city or lat/lon required"}), 400

    cache_key = f"neighborhoods:{slug}:{lang}"

    # try redis cache (treat empty arrays as cache-miss to allow fallbacks)
    if redis_client:
        try:
            raw = await redis_client.get(cache_key)
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list) and len(parsed) == 0:
                        # empty neighborhoods: treat as cache miss to allow geocode fallback
                        app.logger.debug("Empty cached neighborhoods for %s; treating as miss", cache_key)
                    else:
                        # Ensure bbox even for cached data
                        parsed = [ensure_bbox(n) for n in parsed]
                        return jsonify({"cached": True, "neighborhoods": parsed})
                except Exception:
                    # fall through to re-fetch if cached value is corrupted
                    app.logger.debug("Failed to parse cached neighborhoods for %s; refetching", cache_key)
        except Exception:
            app.logger.exception("redis get failed for neighborhoods")

    # fetch from provider
    try:
        data = await multi_provider.async_get_neighborhoods(
            city=city or None,
            lat=float(lat) if lat else None,
            lon=float(lon) if lon else None,
            lang=lang,
            session=aiohttp_session,
        )
    except Exception:
        app.logger.exception("neighborhoods fetch failed")
        data = []

    # If provider returned nothing for a city-only query and we still don't have coords, try geocoding
    if (not data) and city and not (lat and lon) and not geocoded:
        try:
            app.logger.debug("No neighborhoods for '%s', attempting geocode fallback", city)
            result = await geocode_city(city)
            if result:
                g_lat = result['lat']
                g_lon = result['lon']
                try:
                    data = await multi_provider.async_get_neighborhoods(city=None, lat=g_lat, lon=g_lon, lang=lang, session=aiohttp_session)
                    if data:
                        app.logger.info("Geocode fallback succeeded for '%s' -> %s,%s (%d items)", city, g_lat, g_lon, len(data))
                except Exception:
                    app.logger.exception("neighborhoods fetch failed on geocode fallback for %s", city)
        except Exception:
            app.logger.exception("geocode fallback failed for %s", city)

    # store in redis
    if redis_client:
        try:
            await redis_client.set(cache_key, json.dumps(data), ex=NEIGHBORHOOD_CACHE_TTL)
        except Exception:
            app.logger.exception("redis set failed for neighborhoods")

    # Ensure all neighborhoods have bbox
    data = [ensure_bbox(n) for n in data]

    return jsonify({"cached": False, "neighborhoods": data})

@app.route('/reverse_lookup', methods=['POST'])
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
    try:
        from city_guides.providers.overpass_provider import geoapify_reverse_geocode_raw, async_reverse_geocode
        props = await geoapify_reverse_geocode_raw(float(lat), float(lon), session=aiohttp_session)
        if props:
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
    except Exception:
        app.logger.exception('geoapify_reverse_geocode_raw failed or not available')

    # Fallback to older Nominatim-based reverse geocode (formatted string parsing)
    if not addr:
        try:
            from city_guides.providers.overpass_provider import async_reverse_geocode
            addr = await async_reverse_geocode(float(lat), float(lon), session=aiohttp_session)
            raw_nominatim = addr
            app.logger.debug('async_reverse_geocode returned: %s', addr)
        except Exception:
            app.logger.exception('async_reverse_geocode failed')
            addr = None

        if addr:
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
            from city_guides.providers.overpass_provider import geoapify_reverse_geocode_raw, async_reverse_geocode
            props = await geoapify_reverse_geocode_raw(lat, lon, session=aiohttp_session)
            if not props:
                props = None
                addr = await async_reverse_geocode(lat, lon, session=aiohttp_session)
            else:
                addr = props.get('formatted') or ''
        except Exception:
            addr = await async_reverse_geocode(lat, lon, session=aiohttp_session)
            props = None
        out['details']['reverse'] = {'display_name': addr, 'props': bool(props)}

        # Neighborhoods
        try:
            nb = await multi_provider.async_get_neighborhoods(city=None, lat=lat, lon=lon, lang='en', session=aiohttp_session)
            out['details']['neighborhoods_count'] = len(nb)
        except Exception as e:
            out['details']['neighborhoods_error'] = str(e)
            out['details']['neighborhoods_count'] = 0

        # If reverse lookup or neighborhoods returned anything, consider smoke OK
        if (addr and addr.strip()) or out['details'].get('neighborhoods_count', 0) > 0:
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
    except Exception as e:
        app.logger.exception('Failed to get countries')
        return jsonify([])

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
            
            async with session.get(country_url, params=country_params, timeout=10) as resp:
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
                
                async with session.get(children_url, params=children_params, timeout=10) as children_resp:
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
                    
    except Exception as e:
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
            
            async with session.get(cities_url, params=cities_params, timeout=10) as resp:
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
                
    except Exception as e:
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
        async with aiohttp_session.get(f"http://localhost:5010/neighborhoods?city={city_name}&lang=en") as resp:
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
    except Exception as e:
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
        from .fun_fact_tracker import track_fun_fact
        
        # Fun facts database for major cities
        fun_facts = {
            'paris': [
                "The Eiffel Tower was originally intended to be a temporary structure for the 1889 World's Fair and was almost torn down in 1909!",
                "Paris has the highest density of bakeries in the world - there are over 1,200 bakeries in the city!",
                "The Louvre is the world's largest art museum and a former royal palace that took 800 years to complete.",
                "Parisians consume around 16 million baguettes every day - that's about half a baguette per person!",
                "The Paris Métro is one of the densest subway systems in the world, with 245 stations within 86.9 km²."
            ],
            'london': [
                "The Tower of London houses ravens, and there's a legend that if the ravens leave, the kingdom will fall!",
                "London has over 170 museums, including the British Museum which is free to visit.",
                "The London Underground is the world's oldest underground railway system, opening in 1863.",
                "Big Ben is actually the name of the bell, not the clock tower - the tower is called Elizabeth Tower.",
                "London has more than 8 million trees, making it one of the greenest major cities in the world."
            ],
            'new york': [
                "New York City has over 800 languages spoken, making it the most linguistically diverse city in the world!",
                "The Statue of Liberty was a gift from France and was shipped in 214 crates across the Atlantic Ocean.",
                "NYC has over 1,000 parks, with Central Park being the most famous at 843 acres.",
                "The New York City subway system has 472 stations, more than any other metro system in the world.",
                "Times Square was originally called Longacre Square and was renamed in 1904 after the New York Times moved there."
            ],
            'tokyo': [
                "Tokyo's Shibuya Crossing is the busiest pedestrian crossing in the world, with up to 3,000 people crossing at once!",
                "Tokyo has more Michelin-starred restaurants than any other city in the world.",
                "The Tokyo Skytree is the second tallest structure in the world at 634 meters tall.",
                "Tokyo's train system is the busiest in the world, with over 40 million passengers daily.",
                "Tokyo was originally called Edo until 1868 when it was renamed Tokyo, meaning 'Eastern Capital'."
            ],
            'shanghai': [
                "Shanghai has the world's longest metro system at 803 km, longer than London's Underground!",
                "The Shanghai Tower is the second tallest building in the world at 632 meters tall.",
                "Shanghai has more skyscrapers than any other city in the world - over 1,300 buildings taller than 150 meters!",
                "The Bund waterfront area features 52 buildings of various architectural styles, earning it the nickname 'museum of international architecture'.",
                "Shanghai's Maglev train is the fastest commercial train in the world, reaching speeds of 431 km/h."
            ],
            'barcelona': [
                "Barcelona's Sagrada Familia has been under construction since 1882 and is still not completed!",
                "Barcelona has 9 UNESCO World Heritage Sites, the most of any city in Spain.",
                "The city has 4.5 km of beaches within its city limits, making it the only major European city with beaches.",
                "Barcelona's Park Güell was originally a failed housing development project that Gaudí turned into a public park.",
                "The city has over 20,000 orange trees, and locals make fresh orange juice from them in winter!"
            ],
            'rome': [
                "Rome has more fountains than any other city in the world - over 2,000 fountains!",
                "The Colosseum could hold 50,000-80,000 spectators and had a retractable awning for shade.",
                "Rome's Trevi Fountain collects about €3,000 in coins every day, which are donated to charity.",
                "The Vatican City is the smallest country in the world, only 0.44 km² with a population of about 800.",
                "Rome's Pantheon has the largest unreinforced concrete dome in the world, still the world's largest after 2,000 years!"
            ],
            'berlin': [
                "Berlin has more bridges than Venice - around 1,700 bridges compared to Venice's 400!",
                "The Berlin Wall fell on November 9, 1989, and people started chipping away at it with hammers.",
                "Berlin's Museum Island has 5 museums and is a UNESCO World Heritage Site.",
                "The city has more than 2,500 parks and green spaces, making it one of Europe's greenest capitals.",
                "Berlin's TV Tower is 368 meters tall and has a revolving restaurant that makes one full rotation every hour."
            ],
            'amsterdam': [
                "Amsterdam has more canals than Venice and more bridges than any other city in the world!",
                "The city has over 1 million bicycles, which is more than the number of residents.",
                "Amsterdam's canal houses are leaning because they were built on wooden poles that sank unevenly.",
                "The Anne Frank House receives over 1.2 million visitors per year but can only accommodate 512 at a time.",
                "Amsterdam has more museums per square meter than any other city in the world."
            ],
            'sydney': [
                "The Sydney Harbour Bridge is the widest long-span steel-arch bridge in the world at 48.8 meters wide.",
                "Sydney Opera House took 14 years to build and was designed by Danish architect Jørn Utzon.",
                "Sydney has over 100 beaches, including the famous Bondi Beach which is 1 km long.",
                "The city's Royal Botanic Gardens are the oldest scientific institution in Australia, established in 1816.",
                "Sydney hosted the 2000 Olympics and is the only city to have hosted the Olympics twice (1932 and 2000)."
            ],
            'dubai': [
                "Dubai has the world's tallest building, the Burj Khalifa at 828 meters tall.",
                "The city has no income tax and no personal income tax, making it attractive to expatriates.",
                "Dubai's police force uses supercars like Lamborghinis and Ferraris as patrol cars!",
                "The city has the world's largest shopping mall by total area, the Dubai Mall.",
                "Dubai has man-made islands including the Palm Jumeirah, which can be seen from space."
            ],
            'singapore': [
                "Singapore is the only country that is also a city-state!",
                "The city has the world's first night safari, opened in 1971.",
                "Singapore's Changi Airport has been voted the world's best airport for over 20 consecutive years.",
                "The city has over 5.6 million trees, earning it the nickname 'Garden City'.",
                "Singapore's famous 'Gardens by the Bay' has supertrees that are 50 meters tall and act as vertical gardens."
            ],
            'bangkok': [
                "Bangkok's full ceremonial name is the longest city name in the world at 169 characters!",
                "The city has over 400 temples, more than any other city in the world.",
                "Bangkok's traffic is so bad that the city has helicopter taxis for the wealthy!",
                "The city's Chatuchak Weekend Market is the world's largest weekend market with over 15,000 stalls.",
                "Bangkok's Skytrain is the only metro system in Thailand and carries over 700,000 passengers daily."
            ],
            'mumbai': [
                "Mumbai has the most expensive real estate in the world - a single square foot can cost over $10,000!",
                "The city's local trains carry over 7.5 million passengers daily, more than the entire population of Switzerland.",
                "Mumbai's Dharavi slum is the largest in Asia and has an estimated annual turnover of $1 billion.",
                "The city has the world's largest open-air laundry, the Dhobi Ghat, where thousands of clothes are washed daily.",
                "Mumbai's 'Victoria Terminus' is a UNESCO World Heritage Site and the headquarters of India's railway network."
            ],
            'los angeles': [
                "LA has more cars than people - there are about 8.5 million vehicles for 4 million residents!",
                "Hollywood was originally called Hollywoodland and the sign was built in 1923 to advertise a housing development.",
                "LA has the largest number of museums per capita in the US, with over 841 museums.",
                "The city has more than 300 days of sunshine per year, earning it the nickname 'City of Angels'.",
                "LA's freeway system is the most extensive in the world, with over 850 miles of freeways."
            ],
            'toronto': [
                "Toronto has more high-rise buildings than any other city in North America except New York.",
                "The city has over 800 restaurants on just one street - Yonge Street!",
                "Toronto's PATH system is the largest underground shopping complex in the world with 29 km of tunnels.",
                "The city has more than 1,500 parks and is one of the greenest cities in North America.",
                "Toronto's CN Tower was the world's tallest free-standing structure until 2007 and still has the world's longest metal staircase."
            ],
            'mexico city': [
                "Mexico City is built on a lake bed and sinks about 10 inches each year!",
                "The city has more museums than any other city in the world - over 170 museums.",
                "Mexico City's metro system has 195 stations and is the second largest in North America.",
                "The city's Zócalo square is the largest city square in Latin America.",
                "Mexico City was built on top of the Aztec capital Tenochtitlan, which was built on an island in a lake."
            ],
            'rio de janeiro': [
                "Rio's Christ the Redeemer statue is struck by lightning 3-5 times per year!",
                "The city has over 50 km of beaches, including the famous Copacabana and Ipanema.",
                "Rio's Carnival is the world's largest carnival, attracting over 2 million people daily.",
                "The city has more than 500 fountains, earning it the nickname 'City of Fountains'.",
                "Rio's Sugarloaf Mountain got its name because it looked like concentrated sugar loaves to Portuguese settlers."
            ],
            'cairo': [
                "Cairo is the only city in the world that has ancient monuments still standing in the middle of a modern city!",
                "The city has more than 500 registered mosques, some dating back over 1,000 years.",
                "Cairo's Khan el-Khalili market has been operating continuously since the 14th century.",
                "The city's traffic lights are often just suggestions - drivers follow their own rules!",
                "Cairo has the world's oldest university, Al-Azhar University, founded in 970 AD."
            ],
            'istanbul': [
                "Istanbul is the only city in the world located on two continents - Europe and Asia!",
                "The city's Grand Bazaar has been operating continuously since 1461 and has over 4,000 shops.",
                "Istanbul has more than 3,000 mosques, including the famous Blue Mosque with over 20,000 blue tiles.",
                "The city was the capital of three different empires: Roman, Byzantine, and Ottoman.",
                "Istanbul's Hagia Sophia was the world's largest cathedral for nearly 1,000 years and is now a museum."
            ],
            'lyon': [
                "Lyon is known as the gastronomic capital of France with over 4,000 restaurants!",
                "The city has more than 400 hidden passages called 'traboules' dating back to the 4th century.",
                "Lyon's Festival of Lights attracts over 2 million visitors every December.",
                "The city is home to the oldest opera house in France, built in 1756.",
                "Lyon was the birthplace of cinema, invented by the Lumière brothers in 1895."
            ],
            'marseille': [
                "Marseille is the oldest city in France, founded by Greek sailors around 600 BC!",
                "The city has over 40 km of coastline with more than 20 beaches.",
                "Marseille's port is the largest in France and one of the busiest in the Mediterranean.",
                "The city's famous basilica, Notre-Dame de la Garde, stands 154 meters above sea level.",
                "Marseille is the only French city to have won the UEFA Champions League trophy."
            ],
            'nice': [
                "Nice has over 300 days of sunshine per year, making it one of the sunniest cities in France!",
                "The famous Promenade des Anglais is 7 km long and took over 100 years to complete.",
                "Nice's Carnival is one of the largest in the world, attracting over 1 million visitors.",
                "The city was founded by the Greeks around 350 BC and named after Nike, the goddess of victory.",
                "Nice has the largest Russian Orthodox cathedral outside Russia, built in 1912."
            ],
            'bordeaux': [
                "Bordeaux is home to over 7,000 wine producers in the surrounding region!",
                "The city's Place de la Bourse features the largest reflecting pool in the world, covering 3,450 square meters.",
                "Bordeaux has the longest shopping street in Europe, Rue Sainte-Catherine, at 1.2 km.",
                "The city has more than 350 registered historic monuments.",
                "Bordeaux's wine has been produced since the 8th century, spanning over 1,200 years."
            ],
            'lille': [
                "Lille's Christmas market is one of the largest in France with over 80 chalets!",
                "The city was European Capital of Culture in 2004.",
                "Lille's famous waffles called 'gaufres' have been made since the 18th century.",
                "The city is home to the largest university in France with over 100,000 students.",
                "Lille's Belfry is 104 meters tall and offers views of Belgium on clear days."
            ],
            'toulouse': [
                "Toulouse is known as 'La Ville Rose' (The Pink City) due to its distinctive terracotta bricks!",
                "The city is the European capital of the aerospace industry and home to Airbus headquarters.",
                "Toulouse has over 250,000 students, making it one of the youngest cities in Europe.",
                "The city's Capitole building has been the seat of local government for over 800 years.",
                "Toulouse's Canal du Midi, built in 1681, is a UNESCO World Heritage site."
            ],
            'nantes': [
                "Nantes was the birthplace of Jules Verne, author of 'Around the World in 80 Days'!",
                "The city's famous mechanical elephant stands 12 meters tall and can carry 50 passengers.",
                "Nantes was named the most livable city in Europe by Time magazine in 2004.",
                "The city has over 100 km of cycling paths throughout the urban area.",
                "Nantes' Château des Ducs de Bretagne was the residence of the Dukes of Brittany for 300 years."
            ],
            'montpellier': [
                "Montpellier is the fastest-growing city in France with over 40% population increase since 1990!",
                "The city is home to the oldest medical school in the world still in operation, founded in 1220.",
                "Montpellier has over 300 days of sunshine per year.",
                "The city's historic center is one of the largest pedestrian zones in Europe.",
                "Montpellier's Place de la Comédie is called 'l'Oeuf' (the Egg) because of its oval shape."
            ],
            'lisbon': [
                "Lisbon is built on seven steep hills, creating spectacular viewpoints throughout the city!",
                "The city's iconic yellow trams have been operating since 1873.",
                "Lisbon's Vasco da Gama Bridge is the longest in Europe at 17.2 km.",
                "The city survived one of the most powerful earthquakes in European history in 1755.",
                "Lisbon's Oceanarium is the largest indoor aquarium in Europe."
            ],
            'prague': [
                "Prague's astronomical clock, built in 1410, is the oldest working medieval clock in the world!",
                "The city has over 500 spires and towers, earning it the nickname 'City of a Hundred Spires'.",
                "Prague Castle is the largest ancient castle complex in the world, covering 70,000 square meters.",
                "The Charles Bridge has 30 baroque statues and has stood since 1357.",
                "Prague's Jewish Cemetery has over 12,000 tombstones stacked in 12 layers due to lack of space."
            ],
            'schiltigheim': [
                "Schiltigheim is known as the 'City of Brewers' and was once home to Europe's largest beer producers!",
                "The Fischer brewery moved to Schiltigheim in 1854 specifically because of the superior water quality.",
                "Heineken closed all three major Schiltigheim breweries: Fischer (2009), Schutzenberger (2006), and Adelshoffen (2000).",
                "The street leading to the Schutzenberger brewery was called 'Rue Perle' - Pearl Street.",
                "First mentioned in 1265, Schiltigheim's brewing tradition dates back over 750 years."
            ],
            'ghent': [
                "Ghent has over 70,000 bikes for 260,000 residents - making it the bike capital of Belgium!",
                "The famous Gentse Feesten festival attracts over 2 million visitors for 10 days of street parties.",
                "Gravensteen Castle sits in the middle of the city - students once conquered it (not an army)!",
                "Ghent was once the second largest city in Europe after Paris, bigger than London or Cologne.",
                "The city's dragon statue on the bell tower actually spits fire on special occasions."
            ],
            'matera': [
                "Matera's cave dwellings (Sassi) have been inhabited for 9,000 years - the oldest in Europe!",
                "The city was called the 'Shame of Italy' in the 1950s and 15,000 cave residents were evacuated.",
                "Mel Gibson filmed 'The Passion of the Christ' in Matera, using it as a stand-in for ancient Jerusalem.",
                "Matera became a UNESCO World Heritage site in 1993 and European Capital of Culture in 2019.",
                "Families once lived in single-room caves with their livestock - heating came from manure!"
            ],
            'ljubljana': [
                "Ljubljana is protected by dragons - the symbol appears everywhere including the famous Dragon Bridge!",
                "It's one of the smallest capital cities in Europe with only 280,000 residents.",
                "The Dragon Bridge was the first in Slovenia to be paved with asphalt in 1901.",
                "Ljubljana was named European Green Capital in 2016 - its city center is car-free.",
                "Legend says the city was founded by the Greek hero Jason who slew a dragon here."
            ],
            'bergamo': [
                "Bergamo is two cities in one - Città Alta (Upper Town) and Città Bassa (Lower Town)!",
                "The city's Venetian walls are 6km long and became a UNESCO World Heritage Site in 2017.",
                "Bergamo was part of the Venetian Republic for over 250 years - they built the massive defensive walls.",
                "The upper town sits on a hill and can only be reached by funicular or steep stairs!",
                "Bergamo is called the 'City of a Thousand' due to its many medieval towers and buildings."
            ],
            'mostar': [
                "Mostar's Stari Most (Old Bridge) stood for 427 years before being destroyed in 1993 and rebuilt in 2004.",
                "Every summer, brave divers leap 24 meters from the bridge into the Neretva River - a tradition over 400 years old!",
                "The bridge was built by Ottoman architect Mimar Hayruddin in just 9 years (1557-1566).",
                "Mostar was named after the bridge keepers ('mostari') who guarded the crossing.",
                "The bridge's unique design uses a single stone arch - it was the largest of its kind when built."
            ],
            'aveiro': [
                "Aveiro is called the 'Venice of Portugal' with colorful canals and traditional Moliceiro boats!",
                "The city's salt pans have been producing salt for over 1,000 years using ancient methods.",
                "Aveiro is Portugal's Art Nouveau capital with over 200 decorated buildings from the early 1900s.",
                "The colorful Moliceiro boats were originally used to transport salt from the salt pans.",
                "Aveiro's famous 'ovos moles' (sweet eggs) are a local delicacy made from sugar and egg yolks."
            ],
            'valparaíso': [
                "Valparaíso is built on 42 steep hills and has 15 historic funicular elevators dating back to the 1800s!",
                "The city is Chile's street art capital - colorful murals cover nearly every wall in the historic center.",
                "Pablo Neruda called Valparaíso 'the city that never finishes being built'.",
                "The city's labyrinth of streets and staircases inspired the song 'Valparaíso' by Rodrigo 'Fresita' González.",
                "Valparaíso was Chile's main port until the Panama Canal opened - now it's a UNESCO World Heritage site."
            ],
            'oaxaca': [
                "Oaxaca is the birthplace of corn cultivation - maize was first domesticated here 9,000 years ago!",
                "The state speaks 16 indigenous languages - the most linguistically diverse in Mexico.",
                "Oaxaca is the mezcal capital of the world with over 600 brands of the agave spirit.",
                "The city's Day of the Dead celebrations are considered the most authentic in all of Mexico.",
                "Oaxaca's seven mole sauces are so complex they take days to prepare and contain 30+ ingredients each."
            ],
            'guanajuato': [
                "Guanajuato has a network of underground tunnels that were once used to transport silver during the mining boom.",
                "The city's Mummy Museum displays naturally mummified bodies - one of the strangest museums in the world!",
                "Guanajuato's Callejón del Beso (Alley of the Kiss) is so narrow that couples on opposite balconies can kiss across it.",
                "The city was built in a narrow canyon with houses climbing up the steep canyon walls.",
                "Guanajuato has 3,200 'callejones' (narrow alleys) that can only be accessed on foot."
            ],
            'george town': [
                "George Town is Malaysia's street food capital with UNESCO calling it a 'gastronomical paradise'!",
                "The city is a UNESCO World Heritage Site with over 1,700 heritage buildings from the 18th-20th centuries.",
                "George Town's hawker centers serve over 100 different dishes - you can eat something different every day for months!",
                "The city has unique 'kopi tiam' (coffee shops) that have been social gathering places for over 100 years.",
                "George Town's Clan Jetties are wooden houses on stilts over the water, built by Chinese immigrants in the 19th century."
            ],
            'stuttgart': [
                "Stuttgart is the 'cradle of the automobile' - Karl Benz and Gottlieb Daimler invented the automobile here in 1887!",
                "The city has unique 'Stäffele' (steep stairways) - over 400 flights of stairs built for vineyard workers on hilly terrain.",
                "Stuttgart has Europe's second-largest collection of mineral springs, producing 250 million liters of therapeutic water daily.",
                "Unlike most German cities, Stuttgart is famous for wine, not beer - vineyards exist within the city limits!",
                "The Cannstatter Volksfest is Germany's second-largest beer festival, rivaling Munich's Oktoberfest."
            ],
            'antofagasta': [
                "Antofagasta was once part of Bolivia until 1879 when Chile captured it during the War of the Pacific!",
                "The city's name means 'great view' in the Quechua language - referring to its coastal desert location.",
                "Antofagasta is home to La Portada, a 43-meter high natural arch that's Chile's most iconic coastal landmark.",
                "The city grew rich from the 1866 nitrate boom and now exports more copper than any other Chilean port!",
                "Antofagasta sits in the Atacama Desert - the driest place on Earth with some areas never recording rain!"
            ],
            'strasbourg': [
                "Strasbourg is called the 'European Capital' - it hosts the European Parliament, Council of Europe, and European Court of Human Rights!",
                "The city's Notre-Dame Cathedral was the world's tallest building from 1647 to 1874 - it's 142 meters high!",
                "Strasbourg's Christmas market is the oldest in Europe, dating back to 1570 and attracting 2 million visitors annually.",
                "The city is bilingual - both French and Alsatian (a German dialect) are commonly spoken on the streets.",
                "Strasbourg's Grande Île (historic center) was the first entire city center to become a UNESCO World Heritage site in 1988!"
            ],
            'ruse': [
                "Ruse is Bulgaria's largest river port on the Danube, connecting Bulgaria to Romania via the Friendship Bridge!",
                "The city is called 'Little Vienna' for its stunning Baroque and Neo-Renaissance architecture from the 19th century.",
                "Ruse and the Romanian city Giurgiu across the Danube were once a single settlement in the Middle Ages!",
                "The city became a major trade center in the 17th century, linking Central Europe with the Balkans.",
                "Ruse was the first Bulgarian city with electric street lighting and the first with a Bulgarian-language theater!"
            ],
            'zamboanga': [
                "Zamboanga is called the 'City of Flowers' and is known for its unique Spanish-style architecture in the Philippines!",
                "The city speaks Chavacano - a Spanish-based creole language that's one of the world's few Spanish creoles!",
                "Fort Pilar, built in 1635, is a 400-year-old Spanish fortress that still guards the city's harbor!",
                "Zamboanga was once the capital of the short-lived Republic of Zamboanga in 1899!",
                "The city is nicknamed 'Asia's Latin City' due to its Hispanic culture and Spanish-influenced heritage."
            ],
            'ibarra': [
                "Ibarra is called the 'White City' because most buildings have colonial whitewashed architecture!",
                "The city invented helados de paila - handmade ice cream made in bronze pans using ice from Imbabura Volcano!",
                "Ibarra sits at 7,300 feet in the Andes Mountains and was founded in 1606 by Spanish conquistadors!",
                "The famous 'Tren de la Libertad' train ride from Ibarra offers spectacular views of the Andean highlands!",
                "Ibarra is the capital of Ecuador's Imbabura province, home to the famous Otavalo indigenous markets."
            ],
            'santa cruz': [
                "Santa Cruz is Bolivia's largest city by population, surpassing the administrative capital La Paz!",
                "The city sits at only 400 meters above sea level in the Amazon basin, making it much hotter than highland Bolivian cities!",
                "Santa Cruz is Bolivia's economic powerhouse, producing soybean oil, refined sugar, and wood products!",
                "The city was founded in 1561 by Spanish explorer Ñuflo de Chavez and is named after the Holy Cross!",
                "Santa Cruz experiences a tropical climate with year-round warm temperatures, unlike the cold Andes cities!"
            ],
            'davao': [
                "Davao is the Philippines' largest city by land area - bigger than the entire Metro Manila combined!",
                "Mount Apo, the Philippines' highest mountain at 2,954 meters, is visible from most parts of Davao!",
                "Davao is called the 'Durian Capital' of the Philippines - the pungent 'king of fruits' grows abundantly here!",
                "The city hosts the Kadayawan Festival, celebrating the harvest of 10 indigenous tribes with colorful street dances!",
                "Davao is home to the Philippine Eagle Center, protecting one of the world's rarest eagles found only in the Philippines!"
            ],
            'san pedro': [
                "San Pedro is Paraguay's cattle capital - the department produces half of the country's beef!",
                "The city sits on the banks of the Paraguay River, which forms the border with Brazil!",
                "San Pedro is known as the 'Granero del Paraguay' (Granary of Paraguay) due to its vast agricultural production!",
                "The department is the largest in Paraguay's Oriental Region, dedicated mostly to agriculture and forestry!",
                "San Pedro's economy relies on soybeans, wheat, and cattle - making it Paraguay's agricultural powerhouse!"
            ],
            'aba': [
                "Aba is Nigeria's commercial hub, famous for the Ariaria International Market - one of Africa's largest markets!",
                "The city is called 'Japan of Africa' for its thriving manufacturing and textile industries!",
                "Aba is renowned for its skilled craftsmen who create everything from shoes to electronics!",
                "The city played a crucial role in Nigeria's independence movement and was a center of anti-colonial resistance!",
                "Aba's Ariaria Market attracts traders from across West and Central Africa - it's a true commercial melting pot!"
            ],
            'victoria': [
                "Victoria is one of the world's smallest capitals - the entire city has only 2 traffic lights!",
                "The capital of Seychelles was founded by British colonists in 1814 on Mahé Island!",
                "Victoria is home to the Sir Selwyn Selwyn-Clarke Market, famous for its fresh fish and exotic fruits!",
                "The city's clock tower is a miniature replica of London's Big Ben - a gift from the British Empire!",
                "Victoria serves as the gateway to Seychelles' 115 paradise islands and stunning coral reefs!"
            ],
            'bharatpur': [
                "Bharatpur is home to Keoladeo National Park - a UNESCO World Heritage Site with over 370 bird species!",
                "The park was once a royal hunting ground for the Maharajas of Bharatpur who built dykes to attract waterfowl!",
                "Bharatpur is called the 'Eastern Gateway to Rajasthan' and was founded by Maharaja Suraj Mal in 1733!",
                "The city's Lohagarh Fort (Iron Fort) was considered one of the strongest in India and never conquered!",
                "Bharatpur hosts thousands of migratory birds from Siberia and Central Asia every winter!"
            ],
            'balaka': [
                "Balaka is home to one of Malawi's most impressive Catholic cathedrals - the St. Louis Montfort Catholic Parish!",
                "The town serves as an important religious center with both Christian and Muslim communities!",
                "Balaka is located in Malawi's Southern Region and is known for its missionary heritage!",
                "The town is home to Montfort Media, which publishes books and magazines for all of Africa!",
                "Balaka's Chapel of Reconciliation is a symbol of unity between different religious communities in Malawi!"
            ],
            'chiba': [
                "Chiba is home to the Chiba Urban Monorail - the world's longest suspended monorail system!",
                "The city hosts Makuhari Messe, one of Japan's largest convention centers and concert venues!",
                "Chiba is just 40 minutes from Tokyo and serves as a major industrial and technological hub!",
                "The city is famous for its anime and manga industry - many studios are located in Chiba Prefecture!",
                "Chiba Port is one of Japan's busiest maritime cargo hubs, handling millions of containers annually!"
            ],
            'cartagena': [
                "Cartagena's colonial walled city and fortress are a UNESCO World Heritage Site since 1984!",
                "The city took almost 200 years to build its walls - completed in 1796 to defend against pirates!",
                "Cartagena was one of the most important Caribbean ports during the Spanish colonial empire!",
                "The city's colorful Getsemaní neighborhood is famous for its street art and vibrant nightlife!",
                "Cartagena's Castillo San Felipe de Barajas is the largest Spanish fort in the Americas!"
            ],
            'modena': [
                "Modena is the birthplace of traditional balsamic vinegar - aged for at least 12 years in wooden barrels!",
                "The city is home to Ferrari, Maserati, and is the heart of Italy's 'Motor Valley'!",
                "Modena is the culinary capital of Emilia-Romagna, producing Parmigiano-Reggiano and prosciutto!",
                "Opera legend Luciano Pavarotti was born in Modena and called it his beloved hometown!",
                "Modena's cathedral and Torre della Ghirlandina are UNESCO World Heritage Sites!"
            ],
            'bago': [
                "Bago was the capital of the Hanthawaddy Kingdom from 1369 to 1635 in ancient Myanmar!",
                "The city is home to the Shwemawdaw Pagoda - taller than Yangon's famous Shwedagon Pagoda!",
                "Bago boasts the world's largest reclining Buddha at 55 meters long and 16 meters high!",
                "The city was an important Buddhist center with over 1,000 monasteries during its golden age!",
                "Bago's Kanbawzathadi Palace was rebuilt to showcase the glory of Myanmar's ancient kingdoms!"
            ],
            'encarnacion': [
                "Encarnación is called the 'Pearl of the South' and is Paraguay's summer capital!",
                "The city sits on the Paraná River, forming the border with Argentina across from Encarnación's twin city!",
                "Encarnación is famous for its Carnaval celebrations - the largest in Paraguay with Brazilian-style samba!",
                "The city was completely rebuilt in the 1980s after the Yacyretá Dam flooded the original town!",
                "Encarnación is Paraguay's youngest and most modern city, with wide boulevards and beautiful beaches!"
            ],
            'manta': [
                "Manta is Ecuador's tuna fishing capital - claiming to be the world's largest tuna processing hub!",
                "The city was once famous for exporting Panama hats before becoming a major commercial port!",
                "Manta ships processed tuna to Europe and the United States, making it Ecuador's most important Pacific port!",
                "The city is a popular beach destination with beautiful Pacific coastline and vibrant seafood culture!",
                "Manta is home to Universidad Laica Eloy Alfaro, one of Ecuador's largest and most traditional universities!"
            ],
            'salto': [
                "Salto is Uruguay's second-largest city and was founded in 1756 as a military settlement!",
                "The Salto Grande Hydroelectric Dam provides 70% of Uruguay's electricity and 10% of Argentina's!",
                "The city sits on the eastern banks of the Uruguay River, 260 miles from Montevideo!",
                "Salto is famous for its paper mills and hydroelectric power generation!",
                "The city is one of Uruguay's oldest settlements and a major industrial center!"
            ],
            'varna': [
                "Varna is Bulgaria's third-largest city and has been considered a health resort for over 100 years!",
                "The city is home to Golden Sands - one of Bulgaria's most famous Black Sea beach resorts!",
                "Varna's Sea Garden is a massive park along the Black Sea coast with beautiful beaches and cafes!",
                "The city is Bulgaria's naval base and an important port on the Black Sea!",
                "Varna has been inhabited for over 6,000 years, making it one of Europe's oldest continuously inhabited cities!"
            ],
            'kinabalu': [
                "Kinabalu is home to Mount Kinabalu - Malaysia's highest peak at 4,095 meters and the third-highest island peak on Earth!",
                "The mountain contains an estimated 5,000 plant species and is a UNESCO World Heritage Site!",
                "Kinabalu Park is designated as a center of plant diversity for Southeast Asia!",
                "The nearby town of Kundasang is often compared to Swiss Alpine villages for its spectacular mountain scenery!",
                "Mount Kinabalu is sacred to the local Dusun people, who call it 'Aki Nabalu' (Revered Place of the Dead)!"
            ],
            'cuenca': [
                "Cuenca is a UNESCO World Heritage Site famous for its well-preserved colonial Spanish architecture!",
                "The city is called the 'Athens of Ecuador' for its rich cultural heritage and numerous universities!",
                "Cuenca's historic center has cobblestone streets, domed churches, and traditional colonial buildings!",
                "The city is famous for its Panama hat production - the finest quality hats come from the Cuenca region!",
                "Cuenca sits at 2,560 meters in the Andes and is Ecuador's third-largest city!"
            ],
            'santa fe': [
                "Santa Fe is one of Argentina's oldest cities, founded in 1573 and serving as a provincial capital!",
                "The city sits at the confluence of the Salado and Paraná rivers, making it an important inland port!",
                "Santa Fe is known as the 'Cradle of the Argentine Constitution' - the 1853 constitution was signed here!",
                "The city has a rich colonial heritage with well-preserved Spanish architecture and historic churches!",
                "Santa Fe is famous for its traditional Argentine cuisine, particularly its river fish dishes!"
            ],
            'saitama': [
                "Saitama is home to the Omiya Bonsai Village - considered the 'Bonsai Capital' of the world!",
                "The city was formed in 2001 by merging three cities: Omiya, Urawa, and Yono!",
                "Saitama is a major railway hub with Omiya Station being one of Japan's busiest shinkansen transfer points!",
                "The Japan Mint Museum moved from Tokyo to Saitama, showcasing the history of Japanese currency!",
                "Saitama is just northwest of Tokyo and serves as a major commuter city for the capital!"
            ],
            'loja': [
                "Loja is called the 'Music Capital of Ecuador' for its rich musical traditions and conservatories!",
                "The city borders Podocarpus National Park - a massive cloud-forest reserve with incredible biodiversity!",
                "Loja was founded in 1548 by Spanish captain Alonso de Mercadillo and rebuilt after being destroyed!",
                "The city sits at the junction of the Zamora and Malacatos rivers in the southern Andes!",
                "Loja is famous for its traditional Ecuadorian music, particularly the pasillo and sanjuanito genres!"
            ],
            'trujillo': [
                "Trujillo is home to Chan Chan - the world's largest mud-brick city and capital of the ancient Chimú kingdom!",
                "The city is called the 'City of Eternal Spring' for its pleasant year-round climate!",
                "Trujillo was founded in 1534 by Spanish conquistador Francisco Pizarro, making it one of Peru's oldest colonial cities!",
                "The nearby Huaca del Sol is the largest adobe pyramid in the Americas, built with 140 million mud bricks!",
                "Trujillo is the birthplace of the Marinera dance - Peru's national dance representing coastal culture!"
            ],
            'tanga': [
                "Tanga was Tanzania's chief port for sisal export - once called 'white gold' for its economic importance!",
                "The city has many German colonial buildings from the 1890s when Germany modernized the port facilities!",
                "Tanga-Moshi railway, built during German colonial rule, stimulated agricultural development in the region!",
                "The city has a semi-colonial atmosphere with wide streets full of cyclists and motorbikes!",
                "Tanga experienced great development under German rule, becoming one of East Africa's most modern ports!"
            ],
            'ambato': [
                "Ambato is called the 'City of Flowers and Fruits' for its vibrant gardens and fruit production!",
                "The city is carved into the side of Cerro Casigana mountain with views of snow-capped volcanoes!",
                "Ambato is known as the 'Cradle of the Three Juanes' for three famous Ecuadorian writers born here!",
                "The city hosts the famous 'Fiesta de las Frutas y las Flores' (Fruits and Flowers Festival) annually!",
                "Ambato was rebuilt after a 1949 earthquake and is now a major commercial center in the Andes!"
            ],
            'labasa': [
                "Labasa is home to one of Fiji's four sugar mills - the Labasa Mill processes sugarcane from northern Vanua Levu!",
                "The city is located on Vanua Levu, Fiji's second-largest island, and is the main commercial hub of the north!",
                "Labasa's sugar mill was erected in 1890 from a dismantled mill brought from Queensland, Australia!",
                "The city has a large Indo-Fijian population due to the historical sugar cane industry!",
                "Labasa serves as the referral center for northern Fiji with its major hospital and medical facilities!"
            ],
            'zomba': [
                "Zomba was Malawi's first capital city and remained so until 1974 when Lilongwe took over!",
                "The city is home to Chancellor College - the oldest and most prestigious college of the University of Malawi!",
                "Zomba is famous for its British colonial architecture and location at the base of the dramatic Zomba Plateau!",
                "The Parliament remained in Zomba until 1994, making it the political center for 20 years after the capital moved!",
                "Zomba is known as the 'University City' of Malawi due to its educational institutions and student population!"
            ],
            'klang': [
                "Klang is one of Malaysia's oldest cities and was the capital of Selangor until 1974!",
                "The city is a Royal city with the Sultan of Selangor's official palace located here!",
                "Klang was the site of the famous Klang War in 1868, a significant conflict in Malaysian history!",
                "The city is home to Port Klang - Malaysia's largest port by cargo volume and gateway to international trade!",
                "Klang has a vibrant Little India district and the distinctive red-and-white colonial-era fire station!"
            ],
            'moshi': [
                "Moshi is the gateway to Mount Kilimanjaro - Africa's highest peak at 5,895 meters!",
                "The city's name means 'smoke' in Swahili, referring to the mist that circles Mount Kilimanjaro!",
                "Moshi was established by German colonists in the 1890s as a military encampment and coffee production center!",
                "The city is surrounded by coffee plantations and is Tanzania's major coffee-growing region!",
                "Moshi has a dry climate and lower altitude, making it the perfect base for Kilimanjaro climbers!"
            ]
        }
        
        # Normalize city name
        city_lower = city.lower().strip()
        
        # If city not in hardcoded list, fetch interesting facts
        if city_lower not in fun_facts:
            try:
                # Try DDGS for fun facts first
                try:
                    from city_guides.providers.ddgs_provider import ddgs_search
                    ddgs_results = await ddgs_search(f"interesting facts about {city}", max_results=5, timeout=float(os.getenv('DDGS_TIMEOUT','5')))
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
            city_facts = fun_facts[city_lower]
        
        # Select a random fun fact
        import random
        selected_fact = random.choice(city_facts)
        
        # Track the fact quality
        source = "hardcoded" if city_lower in fun_facts else "dynamic"
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
    Get smart neighborhood suggestions for ANY city using dynamic API calls.
    No hardcoded lists - works for all cities globally.
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

        # Get coordinates for the city
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
            'category': category
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

@app.route('/geocode', methods=['POST'])
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
        
    except Exception as e:
        app.logger.exception('Geocoding failed')
        return jsonify({'error': 'geocode_failed'}), 500

@app.route("/search", methods=["POST"])
async def search():
    """Search for venues and places in a city"""
    print(f"[SEARCH ROUTE] Search request received")
    payload = await request.get_json(silent=True) or {}
    print(f"[SEARCH ROUTE] Payload: {payload}")
    
    # Lightweight heuristic to decide whether to cache this search (focuses on food/top queries)
    city = (payload.get("query") or "").strip()
    q = (payload.get("category") or payload.get("intent") or "").strip().lower()
    neighborhood = payload.get("neighborhood")
    state_name = (payload.get("state") or payload.get("stateName") or "").strip()
    country_name = (payload.get("country") or payload.get("countryName") or "").strip()
    should_cache = False  # disabled for testing
    
    if not city:
        return jsonify({"error": "city required"}), 400
    
    try:
        # Use the search implementation from routes
        from .routes import _search_impl
        result = await asyncio.to_thread(_search_impl, payload)

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

@app.route('/synthesize', methods=['POST'])
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

@app.route('/generate_quick_guide', methods=['POST'])
async def generate_quick_guide(skip_cache=False, disable_quality_check=False):
    """Generate a neighborhood quick_guide using Wikipedia and local data-first heuristics.
    POST payload: { city: "City Name", neighborhood: "Neighborhood Name" }
    Returns: { quick_guide: str, source: 'cache'|'wikipedia'|'data-first', cached: bool, source_url?: str }
    """
    payload = await request.get_json(silent=True) or {}
    city = (payload.get('city') or '').strip()
    neighborhood = (payload.get('neighborhood') or '').strip()
    if not city or not neighborhood:
        return jsonify({'error': 'city and neighborhood required'}), 400

    def slug(s):
        return re.sub(r'[^a-z0-9_-]', '_', s.lower().replace(' ', '_'))

    cache_dir = Path(__file__).parent / 'data' / 'neighborhood_quick_guides' / slug(city)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / (slug(neighborhood) + '.json')

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
                            if enrichment and (enrichment.get('text') or (enrichment.get('pois') and len(enrichment.get('pois'))>0)):
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
    except Exception as e:
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
                        res = await ddgs_search(q, engine="google", max_results=3, timeout=float(os.getenv('DDGS_TIMEOUT','5')))
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
                        results = await ddgs_search(q, engine="google", max_results=3, timeout=float(os.getenv('DDGS_TIMEOUT','5')))
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
        wiki_data = await wikipedia_neighborhood_provider.get_neighborhood_data(city, neighborhood, aiohttp_session)
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
                if enrichment and (enrichment.get('text') or (enrichment.get('pois') and len(enrichment.get('pois')) > 0)):
                    synthesized = build_enriched_quick_guide(neighborhood, city, enrichment)
                    source = 'geo-enriched'
                    confidence = 'medium'
                else:
                    # Only use fallback if we don't already have synthesized content
                    if not synthesized or source != 'synthesized':
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
            async with aiohttp_session.get(
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
                        mapillary_images.append({
                            'id': None,
                            'url': a.get('url'),
                            'provider': a.get('provider'),
                            'attribution': SynthesisEnhancer.create_attribution(a.get('provider'), a.get('url')),
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
        async with aiohttp_session.get(url, params=coerced, timeout=aiohttp.ClientTimeout(total=10)) as resp:  # type: ignore
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
    if not redis_client or not DEFAULT_PREWARM_CITIES or not PREWARM_QUERIES:
        return
    sem = asyncio.Semaphore(2)
    async def limited(city, query):
        async with sem:
            await prewarm_search_cache_entry(city, query)
            try:
                await prewarm_neighborhood(city)
            except Exception:
                pass

    tasks = [limited(city, query) for city in DEFAULT_PREWARM_CITIES for query in PREWARM_QUERIES]
    if tasks:
        app.logger.info("Starting prewarm for %d popular searches", len(tasks))
        await asyncio.gather(*tasks)


async def prewarm_rag_responses(top_n: int = None):
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
        queries = PREWARM_QUERIES or ["Top food"]
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
                            existing = await redis_client.get(ck)
                            if existing:
                                await redis_client.expire(ck, int(os.getenv('RAG_CACHE_TTL', 60 * 60 * 6)))
                                continue
                        except Exception:
                            pass
                        # Call our internal endpoint to generate answer
                        payload = {"query": q, "engine": "google", "max_results": 3, "city": city_name}
                        try:
                            async with aiohttp_session.post(f"http://localhost:5010/api/chat/rag", json=payload, timeout=15) as resp:
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
            await redis_client.expire(cache_key, NEIGHBORHOOD_CACHE_TTL)
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
            await redis_client.set(cache_key, json.dumps(neighborhoods), ex=NEIGHBORHOOD_CACHE_TTL)
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
            async with session.get(url, params=params, timeout=10) as resp:
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
                    response = recommender.call_groq_chat(messages, timeout=10)
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
        
    except Exception as e:
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
            
            async with session.get("http://api.geonames.org/searchJSON", params=params, timeout=10) as response:
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
                    
                    if not city_name or not country_name:
                        continue
                    
                    # Get emoji for country
                    country_emoji = ""
                    try:
                        if country_code:
                            # Convert country code to emoji
                            emoji = "".join([chr(ord(c) + 127397) for c in country_code.upper()])
                            country_emoji = emoji
                    except Exception:
                        pass
                    
                    suggestions.append({
                        "city": city_name,
                        "country": country_name,
                        "emoji": country_emoji,
                        "geonameId": geoname.get("geonameId"),
                        "lat": geoname.get("lat"),
                        "lng": geoname.get("lng"),
                        "population": geoname.get("population"),
                        "source": "geonames"
                    })
                
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
                f"https://api.unsplash.com/search/photos",
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
        app.logger.error(f'Query was: {query}')
        app.logger.error(f'Unsplash key configured: {bool(os.getenv("UNSPLASH_KEY"))}')
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
        
    except Exception as e:
        app.logger.exception('Failed to log suggestion success')
        return jsonify({'error': 'logging_failed'}), 500

# Simple in-memory learning storage (could be moved to database)
_location_weights = {}

def get_location_weight(location):
    """Get learning weight for a location"""
    return _location_weights.get(location.lower(), 1.0)

def increment_location_weight(location):
    """Increment weight for successful location"""
    key = location.lower()
    _location_weights[key] = _location_weights.get(key, 1.0) + 0.1

# Import and register routes from routes module
from city_guides.src.routes import register_routes
register_routes(app)

if __name__ == "__main__":
    # Load environment variables from .env file manually
    env_file = Path("/home/markm/TravelLand/.env")
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