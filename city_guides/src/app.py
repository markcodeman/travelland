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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modules
from .routes import (
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
from .validation import validate_neighborhood
from .enrichment import get_neighborhood_enrichment
from city_guides.providers import multi_provider
from city_guides.providers.geocoding import geocode_city, reverse_geocode
from city_guides.providers.overpass_provider import async_geocode_city
from city_guides.providers.utils import get_session
from . import semantic
from .geo_enrichment import enrich_neighborhood
from .synthesis_enhancer import SynthesisEnhancer
from .snippet_filters import looks_like_ddgs_disambiguation_text
from .neighborhood_disambiguator import NeighborhoodDisambiguator

# Create Quart app instance at the very top so it is always defined before any route decorators
app = Quart(__name__, static_folder="/home/markm/TravelLand/city_guides/static", static_url_path='', template_folder="/home/markm/TravelLand/city_guides/templates")

# Configure CORS
cors(app, allow_origin="http://localhost:5174", allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

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
POPULAR_CITIES = [c.strip() for c in os.getenv("POPULAR_CITIES", "London,Paris,New York,Tokyo,Rome,Barcelona").split(",") if c.strip()]
DISABLE_PREWARM = True  # os.getenv("DISABLE_PREWARM", "false").lower() == "true"

# DDGS provider import is optional at module import time (tests may not have ddgs installed)
try:
    from city_guides.providers.ddgs_provider import ddgs_search
except Exception:
    ddgs_search = None
    app.logger.debug('DDGS provider not available at module import time; ddgs_search set to None')

from city_guides.groq.traveland_rag import recommender

# --- /recommend route for RAG recommender ---

@app.route("/api/chat/rag", methods=["POST"])
async def api_chat_rag():
    """
    RAG chat endpoint: Accepts a user query, runs DDGS web search, synthesizes an answer with Groq, and returns a unified AI response.
    Request JSON: {"query": "...", "engine": "google" (optional), "max_results": 8 (optional)}
    Response JSON: {"answer": "..."}
    """
    try:
        data = await request.get_json(force=True)
        query = (data.get("query") or "").strip()
        engine = data.get("engine", "google")
        max_results = int(data.get("max_results", 8))
        if not query:
            return jsonify({"error": "Missing query"}), 400

        # Run DDGS web search (async)
        web_results = await ddgs_search(query, engine=engine, max_results=max_results)
        # Prepare context for Groq
        context_snippets = []
        for r in web_results:
            # Only use title + body for context, never URLs
            snippet = f"{r.get('title','')}: {r.get('body','')}"
            context_snippets.append(snippet)
        context_text = "\n\n".join(context_snippets)

        # Compose Groq prompt (system + user)
        system_prompt = (
            "You are Marco, a travel AI assistant. Given a user query and a set of recent web search snippets, synthesize a helpful, accurate, and up-to-date answer. "
            "Never mention your sources or that you used web search. Respond as a unified expert, not a search engine."
        )
        user_prompt = f"User query: {query}\n\nRelevant web snippets:\n{context_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Call Groq via recommender (direct call_groq_chat)
        groq_resp = recommender.call_groq_chat(messages)
        if not groq_resp:
            return jsonify({"error": "Groq API call failed"}), 502
        try:
            answer = groq_resp["choices"][0]["message"]["content"]
        except Exception:
            answer = None
        if not answer:
            return jsonify({"error": "No answer generated"}), 502
        return jsonify({"answer": answer.strip()})
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

    # Create slug for caching
    if city:
        slug = re.sub(r"[^a-z0-9]+", "_", city.lower()).strip("_")[:64]
    elif lat and lon:
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
        data = await multi_provider.async_get_neighborhoods(city=city or None, lat=float(lat) if lat else None, lon=float(lon) if lon else None, lang=lang, session=aiohttp_session)
    except Exception:
        app.logger.exception("neighborhoods fetch failed")
        data = []

    # If provider returned nothing for a city-only query, try geocoding the city
    if (not data) and city and not (lat and lon):
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
        # Fallback to hardcoded data if no GeoNames username
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
                "maxRows": 50,
                "orderby": "population",
                "username": geonames_user
            }
            
            async with session.get(cities_url, params=cities_params, timeout=10) as resp:
                if resp.status != 200:
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

@app.route('/generate_quick_guide', methods=['POST'])
async def generate_quick_guide(skip_cache=False):
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
            # Add quality check before returning cache
            if 'quick_guide' in data and (re.match(r'^.+ is a neighborhood in .+\.$', data['quick_guide']) or data.get('confidence', 'low') == 'low'):
                cache_file.unlink(missing_ok=True)
                # Skip cache on retry to avoid infinite loop
                return await generate_quick_guide(skip_cache=True)
            resp = {
                'quick_guide': data.get('quick_guide'),
                'source': data.get('source', 'cache'),
                'cached': True,
                'source_url': data.get('source_url'),
            }
            if data.get('mapillary_images'):
                resp['mapillary_images'] = data.get('mapillary_images')
            if data.get('generated_at'):
                resp['generated_at'] = data.get('generated_at')

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
                        return jsonify(resp)
                    except Exception:
                        app.logger.exception('Failed to synthesize replacement for cached disambiguation (early)')
                        try:
                            cache_file.unlink()
                        except Exception:
                            pass
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
                else:
                    resp['confidence'] = cached_conf
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
            # If cached snippet passed sanity checks, but is low confidence, replace with minimal factual fallback
            if resp.get('confidence') == 'low' and src in ('synthesized', 'ddgs'):
                app.logger.info('Replacing cached low-confidence quick_guide for %s/%s with minimal factual fallback', city, neighborhood)
                try:
                    minimal = f"{neighborhood} is a neighborhood in {city}."
                    resp['quick_guide'] = minimal
                    resp['source'] = 'data-first'
                    resp['source_url'] = None
                    resp['confidence'] = 'low'
                    try:
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump({'quick_guide': resp['quick_guide'], 'source': resp['source'], 'generated_at': time.time(), 'source_url': None, 'confidence': resp['confidence']}, f, ensure_ascii=False, indent=2)
                    except Exception:
                        app.logger.exception('Failed to persist minimal replacement for cached low-confidence quick_guide')
                    return jsonify(resp)
                except Exception:
                    app.logger.exception('Failed to synthesize minimal fallback for cached low-confidence entry')
                    try:
                        cache_file.unlink()
                    except Exception:
                        pass
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

    # Try Wikipedia summary first using a relevance helper
    wiki_title_candidates = [f"{neighborhood}, {city}", f"{neighborhood}"]
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
        if city.lower() in extract_text or city.lower() in title_text:
            return True
        if neighborhood.lower() in extract_text or neighborhood.lower() in title_text:
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

    for title in wiki_title_candidates:
        try:
            safe_title = title.replace(' ', '_')
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{safe_title}"
            async with aiohttp_session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:  # type: ignore
                if resp.status == 200:
                    j = await resp.json()
                    is_rel = _page_is_relevant(j)
                    app.logger.debug("Wiki candidate '%s' returned title='%s' relevant=%s", title, (j.get('title') or '')[:200], is_rel)
                    if not is_rel:
                        app.logger.debug("Rejected wiki candidate '%s' as not relevant (title=%s)", title, (j.get('title') or ''))
                        continue
                    extract = j.get('extract') or j.get('description')
                    if extract:
                        wiki_summary = extract
                        wiki_url = j.get('content_urls', {}).get('desktop', {}).get('page') or j.get('canonical') or url
                        app.logger.info("Accepted wiki quick_guide from title '%s' for %s/%s", j.get('title'), city, neighborhood)
                        break
        except Exception:
            continue

    synthesized = None
    source = None
    source_url = None
    if wiki_summary:
        synthesized = f"{wiki_summary}"
        source = 'wikipedia'
        source_url = wiki_url

    # If Wikipedia didn't provide a good summary, prefer DDGS-derived synthesis when possible
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
                
            # Build specific queries with geographic context
            ddgs_queries = [
                f"{neighborhood} {city_name}{geographic_context} travel guide",
                f"{neighborhood} {city_name}{geographic_context} neighborhood information", 
                f"what is {neighborhood} {city_name}{geographic_context} like",
                f"{neighborhood} district {city_name}{geographic_context}",
                f"visit {neighborhood} {city_name}{geographic_context}",
            ]
            ddgs_results = []
            for q in ddgs_queries:
                try:
                    if not ddgs_search:
                        app.logger.debug('DDGS provider not available at runtime; skipping query %s', q)
                        continue
                    res = await ddgs_search(q, engine="google", max_results=6)
                    app.logger.debug('DDGS: query=%s got %d results', q, len(res) if res else 0)
                    if res:
                        ddgs_results.extend(res)
                except Exception as e:
                    app.logger.debug('DDGS query failed for %s: %s', q, e)
                    continue
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
                # Consider relevant if mentions neighborhood or city or contains travel keywords
                lower = txt.lower()
                if neighborhood.lower() in lower or city.lower() in lower or any(k in lower for k in ['travel', 'guide', 'colonia', 'neighborhood', 'transit', 'bus', 'train']):
                    relevant.append(r)
            # If no clearly relevant results, but we have ddgs hits, treat the top hits as possible candidates
            if not relevant and ddgs_results:
                app.logger.debug('No clearly relevant DDGS hits for %s/%s but using top search results', city, neighborhood)
                relevant = ddgs_results[:3]

            if relevant:
                app.logger.debug("DDGS candidates for %s/%s: %s", city, neighborhood, [ (r.get('title'), r.get('href') or r.get('url')) for r in relevant ])
                # Try to synthesize into concise English using the semantic module
                snippets = []
                for r in relevant[:6]:
                    title = (r.get('title') or '').strip()
                    body = (r.get('body') or '').strip()
                    href = r.get('href') or r.get('url') or ''
                    snippet = f"{title}: {body} ({href})" if title else f"{body} ({href})"
                    snippets.append(snippet)
                context_text = '\n\n'.join(snippets)
                
                # If no web snippets found, don't bother with DDGS synthesis - use fallback
                if not context_text.strip() or len(relevant) == 0:
                    app.logger.info(f"No web snippets found for {neighborhood}, {city} - skipping DDGS synthesis")
                    synthesized = None  # Will trigger fallback to SynthesisEnhancer
                else:
                    synth_prompt = (
                        f"Synthesize a concise (2-4 sentence) English quick guide for the neighborhood '{neighborhood}, {city}'. "
                        f"Use only the facts from the following web snippets; keep it travel-focused (type of area, notable features, transit/access, quick local tips). "
                        f"Answer in English.\n\nWeb snippets:\n{context_text}"
                    )
                    app.logger.info(f"DDGS synthesis prompt for {neighborhood}, {city}: {synth_prompt[:500]}...")
                    app.logger.info(f"Context text length: {len(context_text)}, Snippets count: {len(relevant)}")
                try:
                    # Only run DDGS synthesis if we have web snippets
                    if context_text.strip() and len(relevant) > 0:
                        resp = await semantic.search_and_reason(synth_prompt, city=city, mode='rational', session=aiohttp_session)
                        if isinstance(resp, dict):
                            resp_text = str(resp.get('answer') or resp.get('text') or '')
                        else:
                            resp_text = str(resp or '')
                        resp_text = resp_text.strip()
                        app.logger.debug("DDGS synthesis response for %s/%s: %s", city, neighborhood, resp_text[:200])
                        # Basic sanity check: length and mention of the city/neighborhood or travel keyword
                        if len(resp_text) >= 40 and (city.lower() in resp_text.lower() or neighborhood.lower() in resp_text.lower() or any(k in resp_text.lower() for k in ['travel', 'guide', 'transit', 'bus', 'train'])):
                            synthesized = resp_text
                            source = 'ddgs'
                            source_url = relevant[0].get('href') or relevant[0].get('url')
                    else:
                        # Skip DDGS synthesis when no snippets found
                        synthesized = None
                except Exception:
                    app.logger.exception('ddgs synthesis failed')

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
                        results = await ddgs_search(q, engine="google", max_results=5)
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
        if not synthesized:
            try:
                from city_guides.src.synthesis_enhancer import SynthesisEnhancer
                synthesized = SynthesisEnhancer.generate_neighborhood_paragraph(neighborhood, city)
                source = 'synthesized'
            except Exception:
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

    # Determine confidence level for the returned quick guide
    # - high: sourced from Wikipedia
    # - medium: DDGS-derived or synthesized with DDGS evidence
    # - low: synthesized with no supporting web/wiki evidence (fall back to minimal factual sentence)
    confidence = 'low'
    try:
        if source == 'wikipedia':
            confidence = 'high'
        elif source == 'ddgs':
            confidence = 'medium'
        elif source == 'synthesized':
            if isinstance(ddgs_results, list) and len(ddgs_results) > 0:
                confidence = 'medium'
            else:
                confidence = 'low'
    except Exception:
        confidence = 'low'

    # If confidence is low, attempt geo enrichment before returning minimal fallback
    if confidence == 'low':
        try:
            from city_guides.src.geo_enrichment import enrich_neighborhood, build_enriched_quick_guide
            enrichment = await enrich_neighborhood(city, neighborhood, session=aiohttp_session)
            if enrichment and (enrichment.get('text') or (enrichment.get('pois') and len(enrichment.get('pois')) > 0)):
                synthesized = build_enriched_quick_guide(neighborhood, city, enrichment)
                source = 'geo-enriched'
                confidence = 'medium'
            else:
                synthesized = f"{neighborhood} is a neighborhood in {city}."
                source = source or 'data-first'
        except Exception:
            synthesized = f"{neighborhood} is a neighborhood in {city}."
            source = source or 'data-first'

    out = {'quick_guide': synthesized, 'source': source or 'data-first', 'confidence': confidence, 'cached': False, 'generated_at': time.time(), 'source_url': source_url} 

    # Try to enrich quick guide with Mapillary thumbnails (if available)
    mapillary_images = []
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

def _search_impl(payload):
    """Core search implementation - moved to module level for reusability"""
    # This is a simplified version of the search logic
    # In a real implementation, this would contain the full search logic
    # but for brevity, we'll return a basic structure
    city = (payload.get("query") or "").strip()
    q = (payload.get("category") or "").strip().lower()
    
    # Basic validation
    if not city:
        return {"error": "City not found or invalid"}
    
    # Mock results for demonstration
    results = []
    if q and "food" in q:
        results = [
            {
                "id": "mock-restaurant-1",
                "name": "Local Eatery",
                "description": "Great local food",
                "budget": "cheap",
                "price_range": "$",
                "address": "123 Main St",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "provider": "mock"
            }
        ]
    
    return {
        "venues": results,
        "city": city,
        "partial": False,
        "debug_info": {"city": city, "query": q}
    }

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