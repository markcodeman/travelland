from quart import Quart

# Create Quart app instance at the very top so it is always defined before any route decorators
app = Quart(__name__, static_folder="/home/markm/TravelLand/city_guides/static", static_url_path='', template_folder="/home/markm/TravelLand/city_guides/templates")

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





# --- EARLY .env loader ---
import os
from pathlib import Path
_env_paths = [
    Path(__file__).parent / ".env",
    Path(__file__).parent.parent / ".env",
    Path("/home/markm/TravelLand/.env"),
]
for _env_file in _env_paths:
    if _env_file.exists():
        with open(_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
        break

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "groq"))
import traveland_rag  # type: ignore
import json
import hashlib
from urllib.parse import urlparse
from quart import Quart, render_template, request, jsonify
import asyncio
import aiohttp
from redis import asyncio as aioredis
import logging
import re
import time
import requests

# Load environment variables from .env file
# Get the directory where this script is running
script_dir = Path(__file__).parent
env_paths = [
    script_dir / ".env",
    script_dir.parent / ".env",
    Path("/home/markm/TravelLand/.env"),
]

_env_file_used = None
for env_file in env_paths:
    if env_file.exists():
        print(f"Loading .env from {env_file.resolve()}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
        _env_file_used = env_file
        # Verify key was loaded
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            print(f"✓ GROQ_API_KEY loaded successfully: {groq_key[:6]}... (length: {len(groq_key)})")
        else:
            print("✗ GROQ_API_KEY NOT FOUND in environment after .env load!")
        break
else:
    print("Warning: .env file not found in any expected location")

# Auto-update Groq model if deprecated (runs once at startup)
if os.getenv("GROQ_API_KEY") and _env_file_used:
    try:
        from groq import Groq
        current_model = os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")
        print(f"🔍 Checking Groq model availability: {current_model}", file=sys.stderr)
        sys.stderr.flush()
        
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Quick check: try to list models
        try:
            models_list = client.models.list()  # type: ignore
            available_models = [m.id for m in models_list.data]
            print(f"✓ Found {len(available_models)} available Groq models", file=sys.stderr)
        except AttributeError:
            available_models = [current_model]  # fallback
            print(f"⚠ Could not list models, using {current_model}", file=sys.stderr)
        sys.stderr.flush()
        
        # If current model not available, find a working one
        if current_model not in available_models:
            print(f"⚠ Model '{current_model}' is deprecated!", file=sys.stderr)
            sys.stderr.flush()
            fallback_models = [
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
                "llama-3.1-70b-versatile",
                "gemma-7b-it",
                "llama2-70b-4096",
            ]
            new_model = None
            for model in fallback_models:
                if model in available_models:
                    new_model = model
                    break
            
            if new_model and new_model != current_model:
                print(f"🔄 Updating GROQ_MODEL: {current_model} → {new_model}", file=sys.stderr)
                sys.stderr.flush()
                os.environ["GROQ_MODEL"] = new_model
                
                # Update .env file
                with open(_env_file_used) as f:
                    content = f.read()
                content = re.sub(
                    r'^GROQ_MODEL=.*$',
                    f'GROQ_MODEL={new_model}',
                    content,
                    flags=re.MULTILINE
                )
                with open(_env_file_used, 'w') as f:
                    f.write(content)
                print(f"✓ Updated GROQ_MODEL in {_env_file_used}")
    except Exception as e:
        print(f"ℹ Groq model check skipped: {e}")

# Ensure local module imports work when running under an ASGI server
_here = os.path.dirname(__file__)
_parent = os.path.dirname(_here)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

# Local providers are located in the same directory
from city_guides.providers import multi_provider
from city_guides.providers.geocoding import geocode_city, reverse_geocode
from city_guides.providers.overpass_provider import async_geocode_city
from city_guides.providers.utils import get_session
from . import semantic
# import synthesis  # TODO: synthesis.py not found

# Enable remote debugging only when explicitly requested via env var
if os.getenv("ENABLE_DEBUGPY", "0") == "1":
    try:
        import debugpy
        dbg_port = int(os.getenv("DEBUGPY_PORT", "5678"))
        debugpy.listen(("0.0.0.0", dbg_port))
        print(f"🐛 Debugpy listening on 0.0.0.0:{dbg_port}")
    except Exception as e:
        # Don't fail startup if debugpy cannot start in the environment
        print(f"⚠️ debugpy failed to start: {e}")

# ============ CONSTANTS ============
CACHE_TTL_TELEPORT = int(os.getenv("CACHE_TTL_TELEPORT", "86400"))  # 24 hours
VERBOSE_OPEN_HOURS = os.getenv("VERBOSE_OPEN_HOURS", "false").lower() == "true"

# Import local providers and utilities
try:
    from city_guides.providers import image_provider
except Exception:
    image_provider = None

try:
    from semantic import shorten_place
except ImportError:
    def shorten_place(city_name):
        """Fallback: shorten city name by taking first part before comma."""
        if not city_name:
            return city_name
        return city_name.split(',')[0].strip()



app = Quart(__name__, static_folder="/home/markm/TravelLand/city_guides/static", static_url_path='', template_folder="/home/markm/TravelLand/city_guides/templates")


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

# --- /recommend route for RAG recommender ---
from quart import request, jsonify
@app.route("/recommend", methods=["POST"])
async def recommend():
    """RAG-based venue recommendation endpoint"""
    payload = await request.get_json(silent=True) or {}
    city = payload.get("city")
    neighborhood = payload.get("neighborhood")
    q = payload.get("q")
    preferences = payload.get("preferences", {})
    candidates = payload.get("candidates", [])
    user_context = {
        "city": city,
        "neighborhood": neighborhood,
        "q": q,
        "preferences": preferences
    }
    # Optionally pass weather if present
    if "weather" in payload:
        user_context["weather"] = payload["weather"]
    # Call the RAG recommender
    try:
        recs = traveland_rag.recommend_venues_rag(user_context, candidates)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(recs)

# Global async clients
aiohttp_session: aiohttp.ClientSession | None = None
redis_client: aioredis.Redis | None = None

# Track active long-running searches (search_id -> metadata)
active_searches = {}

DEFAULT_PREWARM_CITIES = os.getenv("SEARCH_PREWARM_CITIES", "London,Paris")
PREWARM_QUERIES = [q.strip() for q in os.getenv("SEARCH_PREWARM_QUERIES", "Top food").split(",") if q.strip()]
PREWARM_TTL = int(os.getenv("SEARCH_PREWARM_TTL", "3600"))
RAW_PREWARM_CITIES = []  # [c.strip() for c in DEFAULT_PREWARM_CITIES.split(",") if c.strip()]
NEIGHBORHOOD_CACHE_TTL = int(os.getenv("NEIGHBORHOOD_CACHE_TTL", 60 * 60 * 24 * 7))  # 7 days
# Popular cities to prewarm neighborhoods for (background task)
POPULAR_CITIES = [c.strip() for c in os.getenv("POPULAR_CITIES", "London,Paris,New York,Tokyo,Rome,Barcelona").split(",") if c.strip()]
DISABLE_PREWARM = True  # os.getenv("DISABLE_PREWARM", "false").lower() == "true"


@app.before_serving
async def startup():
    global aiohttp_session, redis_client
    aiohttp_session = aiohttp.ClientSession(headers={"User-Agent": "city-guides-async"})
    try:
        redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        await redis_client.ping()  # type: ignore
        app.logger.info("✅ Redis connected")
        if RAW_PREWARM_CITIES and PREWARM_QUERIES:
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


def reverse_geocode_sync(lat, lon):
    """Sync version of reverse geocoding."""
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"lat": lat, "lon": lon, "format": "json", "zoom": 18}
    try:
        resp = requests.get(url, params=params, timeout=3)
        if resp.status_code != 200:
            print(f"[DEBUG app.py] reverse_geocode_sync HTTP error: {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()
        if data and "display_name" in data:
            return data["display_name"]
    except Exception as e:
        print(f"[DEBUG app.py] reverse_geocode_sync Exception: {e}")
        return None
    return None


def format_venue(venue):
    address = venue.get('address', '')
    
    # Don't use coordinates as display address
    if address and re.match(r'^-?\d+\.\d+,\s*-?\d+\.\d+$', address):
        venue['display_address'] = None
        venue['coordinates'] = address
    else:
        venue['display_address'] = address
    
    return venue


async def _persist_quick_guide(out_obj, city_name, neighborhood_name, file_path):
    """Persist quick_guide to the filesystem and (optionally) to Redis.
    This is extracted to module-level to make it directly testable."""
    try:
        from city_guides.src.snippet_filters import looks_like_ddgs_disambiguation_text
        if out_obj.get('source') == 'ddgs' and looks_like_ddgs_disambiguation_text(out_obj.get('quick_guide') or ''):
            app.logger.info('Not caching disambiguation/promotional ddgs quick_guide for %s/%s', city_name, neighborhood_name)
            # replace with synthesized neutral paragraph if available
            try:
                from city_guides.src.synthesis_enhancer import SynthesisEnhancer
                out_obj['quick_guide'] = SynthesisEnhancer.generate_neighborhood_paragraph(neighborhood_name, city_name)
                out_obj['source'] = 'synthesized'
                out_obj['source_url'] = None
                        out_obj['confidence'] = 'low'
                    except Exception:
                        out_obj['quick_guide'] = f"{neighborhood_name} is a neighborhood in {city_name}."
                        out_obj['source'] = 'data-first'
                        out_obj['confidence'] = 'low'
        try:
            app.logger.debug('redis_client value at cache write: %s', str(redis_client)[:200])
            if redis_client:
                redis_key = f"quick_guide:{re.sub(r'[^a-z0-9]+', '_', city_name.lower()).strip('_')}:{re.sub(r'[^a-z0-9]+', '_', neighborhood_name.lower()).strip('_')}"
                app.logger.debug('Writing quick_guide to redis key=%s', redis_key)
                await redis_client.set(redis_key, json.dumps(out_obj), ex=86400)
        except Exception:
            app.logger.exception('failed to write quick_guide to redis')

    except Exception:
        app.logger.exception('failed to write quick_guide cache')


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


def _is_relevant_wikimedia_image(wik_img: dict, city_name: str, neighborhood_name: str) -> bool:
    """Heuristic to decide if a Wikimedia banner image is relevant to the place (avoid portraits, performers, trophies).
    Module-level helper so it can be used from tests and other modules."""
    if not wik_img:
        return False
    page_title = (wik_img.get('page_title') or '')
    remote = (wik_img.get('remote_url') or wik_img.get('url') or '')
    lower_title = page_title.lower()
    lower_remote = remote.lower()
    bad_terms = ['trophy', 'portrait', 'headshot', 'award', 'cup', 'ceremony', 'medal', 'singer', 'performing', 'performer', 'concert', 'festival', 'band', 'photo', 'photograph', 'portrait']
    good_terms = ['skyline', 'panorama', 'view', 'street', 'market', 'plaza', 'park', 'bridge', 'neighborhood', 'colonia', 'architecture', 'building']
    # Detect obvious person/performer pages by title patterns or keywords
    is_bad = any(b in lower_title for b in bad_terms) or any(b in lower_remote for b in bad_terms)
    is_performer_name = False
    # If page title contains two capitalized words (likely a person's name) and doesn't mention the city, treat as performer-like
    if page_title and sum(1 for w in page_title.split() if w and w[0].isupper()) >= 2 and (city_name.lower() not in lower_title):
        is_performer_name = True
    is_good = any(g in lower_title for g in good_terms) or any(g in lower_remote for g in good_terms) or (city_name.lower() in lower_title)
    if (is_bad or is_performer_name) and not is_good:
        return False
    return True


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


def ensure_bbox(neighborhood):
    """Generate a bbox if neighborhood is a point without one."""
    if neighborhood.get('bbox'):
        return neighborhood
    
    center = neighborhood.get('center', {})
    lat = center.get('lat')
    lon = center.get('lon')
    
    if lat and lon:
        # Create ~2.5km radius bbox (roughly 0.025 degrees)
        radius = 0.025
        neighborhood['bbox'] = [
            float(lon) - radius,  # min_lon
            float(lat) - radius,  # min_lat
            float(lon) + radius,  # max_lon
            float(lat) + radius   # max_lat
        ]
        neighborhood['bbox_generated'] = True  # Flag for debugging
    
    return neighborhood


# Tolerant JSON parsing helper: strips common line comments (// and #) and tries to load JSON.
import re

def tolerant_parse_json_bytes(raw_bytes: bytes):
    """Best-effort parse of JSON payloads that may include // or # comments.

    This function strips whole-line comments and trailing // comments before attempting
    json.loads. It's intentionally conservative — it only removes comments that appear
    as whole-line or trailing after a value (not inside strings) using heuristics.
    """
    try:
        text = raw_bytes.decode('utf-8')
    except Exception:
        # fallback: attempt latin-1 decode
        text = raw_bytes.decode('latin-1')
    # Remove C-style // comments that are at line end or start
    text = re.sub(r"(?m)//.*$", "", text)
    # Remove shell-style # comments at line start or after whitespace
    text = re.sub(r"(?m)^[ \t]*#.*$", "", text)
    # Remove trailing comments after JSON values like: "key": "value"  # comment
    text = re.sub(r"(?m)(\"[^\"]*\"\s*[:,]?\s*[^,\n\r]+?)\s+#.*$", r"\1", text)
    # Remove any leftover blank lines caused by stripping
    # Attempt to load as JSON
    try:
        return json.loads(text)
    except Exception:
        # Last-resort: try to find a JSON object in the text using regex
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None


# Overpass helper: run a bbox-based query and normalize results
OVERPASS_URL = os.getenv("OVERPASS_URL") or "https://overpass-api.de/api/interpreter"

async def overpass_query_bbox(bbox, poi_type="restaurant", limit=50, session=None):
    """Query Overpass within bbox and return normalized venue dicts.
    bbox: [min_lon, min_lat, max_lon, max_lat]
    poi_type: 'restaurant'|'coffee' etc to bias the query
    """
    south, west, north, east = bbox[1], bbox[0], bbox[3], bbox[2]
    if poi_type == "coffee":
        query = f"""
[out:json][timeout:20];
(
  node["amenity"~"cafe|coffee_shop|bar"]({south},{west},{north},{east});
  way["amenity"~"cafe|bar"]({south},{west},{north},{east});
  node["shop"~"coffee|tea"]({south},{west},{north},{east});
);
out center {limit};
"""
    else:
        query = f"""
[out:json][timeout:25];
(
  node["amenity"~"cafe|restaurant|fast_food|bar"]({south},{west},{north},{east});
  way["amenity"~"cafe|restaurant|fast_food|bar"]({south},{west},{north},{east});
  relation["amenity"~"cafe|restaurant|fast_food|bar"]({south},{west},{north},{east});
  node["shop"="coffee"]({south},{west},{north},{east});
);
out center {limit};
"""
    sess = session or aiohttp_session
    if not sess:
        raise RuntimeError("No aiohttp session available for Overpass query")
    try:
        async with sess.post(OVERPASS_URL, data={"data": query}, timeout=aiohttp.ClientTimeout(total=15)) as resp:  # type: ignore
            if resp.status != 200:
                raise RuntimeError(f"Overpass returned status {resp.status}")
            data = await resp.json()
    except Exception as e:
        print(f"DEBUG: overpass_query_bbox failed: {e}")
        return []

    elems = data.get("elements", []) if isinstance(data, dict) else []
    out = []
    for e in elems:
        try:
            lat = e.get('lat')
            lon = e.get('lon')
            if not lat and 'center' in e:
                lat = e['center'].get('lat')
                lon = e['center'].get('lon')
            if not lat or not lon:
                continue
            tags = e.get('tags') or {}
            name = tags.get('name') or tags.get('amenity') or tags.get('shop') or ''
            venue = {
                'id': f"osm:{e.get('type')}/{e.get('id')}",
                'name': name,
                'lat': float(lat),
                'lon': float(lon),
                'tags': tags,
                'osm_url': f"https://www.openstreetmap.org/{e.get('type')}/{e.get('id')}",
                'provider': 'osm',
            }
            out.append(venue)
            if len(out) >= limit:
                break
        except Exception:
            continue
    return out


def calculate_search_radius(neighborhood_name, bbox):
    """Calculate appropriate search radius based on context"""
    if neighborhood_name:
        return 300  # Smaller radius for neighborhoods
    elif bbox:
        # Calculate radius based on bbox size
        bbox_width = abs(bbox[2] - bbox[0])
        bbox_height = abs(bbox[3] - bbox[1])
        avg_size = (bbox_width + bbox_height) / 2
        return min(int(avg_size * 50000), 800)  # Convert to meters, cap at 800m
    else:
        return 300  # Smaller default radius for cities to avoid timeouts


def format_venue_for_display(poi):
    """Format venue for frontend display"""
    address = poi.get('address', '')

    # Use coordinates only as fallback
    if address and re.match(r'^-?\d+\.\d+,\s*-?\d+\.\d+$', address):
        display_address = None
        coordinates = address
    else:
        display_address = address
        coordinates = f"{poi.get('lat')},{poi.get('lon')}"

    return {
        'id': poi.get('id'),
        'city': '',  # Will be set by caller
        'name': poi.get('name', 'Unknown'),
        'budget': determine_budget(poi.get('tags', {})),
        'price_range': determine_price_range(poi.get('tags', {})),
        'description': generate_description(poi),
        'tags': poi.get('tags', ''),
        'address': display_address,
        'latitude': poi.get('lat'),
        'longitude': poi.get('lon'),
        'website': poi.get('website', ''),
        'osm_url': poi.get('osm_url', ''),
        'amenity': poi.get('type'),
        'provider': 'osm',
        'phone': poi.get('phone'),
        'rating': None,  # OSM doesn't have ratings
        'opening_hours': poi.get('opening_hours'),
        'opening_hours_pretty': _humanize_opening_hours(poi.get('opening_hours')),
        'open_now': _compute_open_now(poi.get('lat'), poi.get('lon'), poi.get('opening_hours'))[0],
        'quality_score': poi.get('quality_score', 0),
    }


def determine_budget(tags):
    """Determine budget level from tags"""
    tags_lower = str(tags).lower()
    if 'fast_food' in tags_lower or 'cost=cheap' in tags_lower:
        return 'cheap'
    elif 'cuisine=fast_food' in tags_lower:
        return 'cheap'
    else:
        return 'mid'


def determine_price_range(tags):
    """Determine price range indicator"""
    budget = determine_budget(tags)
    return '$' if budget == 'cheap' else '$$'


def generate_description(poi):
    """Generate user-friendly description"""
    tags = poi.get('tags', {})
    features = []

    if tags.get('cuisine'):
        features.append(tags['cuisine'].title())
    if tags.get('outdoor_seating') == 'yes':
        features.append('outdoor seating')
    if tags.get('wheelchair') == 'yes':
        features.append('accessible')
    if tags.get('takeaway') == 'yes':
        features.append('takeaway available')

    feature_text = f" with {', '.join(features)}" if features else ""

    base_type = poi.get('type', 'venue').title()
    return f"{base_type}{feature_text}"


async def enhanced_auto_enrich_venues(q, city, neighborhoods, session=None, limit=8):
    """Enhanced venue enrichment with better OSM data"""
    try:
        q_low = (q or "").lower()

        neighborhood_name = None
        bbox = None
        use_city_bbox = False
        venue_keywords = ["food", "eat", "restaurant", "cuisine", "dining", "coffee", "tea", "bar", "pub", "cafe", "tacos", "pizza", "burger", "sushi", "italian", "chinese", "mexican", "thai", "indian", "french", "japanese", "korean", "vietnamese", "mediterranean", "american", "breakfast", "lunch", "dinner", "snacks", "dessert", "bakery", "ice cream", "nightlife", "club", "music", "live music", "dance", "theater", "cinema", "museum", "art", "gallery", "park", "beach", "shopping", "market", "mall", "boutique", "bookstore", "library"]
        is_venue_query = any(k in q_low for k in venue_keywords)
        name_query = None
        if is_venue_query:
            # Extract the first matching keyword as name_query
            for k in venue_keywords:
                if k in q_low:
                    name_query = k
                    break
        if is_venue_query:
            # For venue queries, use city bbox to get more results
            use_city_bbox = True
        elif neighborhoods and len(neighborhoods) > 0:
            nb0 = ensure_bbox(neighborhoods[0])
            neighborhood_name = nb0.get('name')
            bbox = nb0.get('bbox')

        should_enrich = False
        for k in ["nearby", "near", "near me", "nearby me", "nearby to", "close to", "closeby", "nearby?"]:
            if k in q_low:
                should_enrich = True
                break
        # Also enrich if neighborhood is explicitly mentioned in query
        if not should_enrich and neighborhood_name and neighborhood_name.lower() in q_low:
            should_enrich = True
        # Also enrich for venue-related queries (food, coffee, etc.)
        if not should_enrich and is_venue_query:
            should_enrich = True

        # Respect operator flag to disable auto-enrichment
        if os.getenv("AUTO_ENRICH", "1") == "0":
            return []
        if not should_enrich:
            return []

        # Set bbox for city if venue query
        if use_city_bbox:
            own_session = session is None
            if own_session:
                session = await get_session()
            try:
                bbox = await async_geocode_city(city, session=session)
            finally:
                if own_session:
                    await session.close()
                    session = None

        cache_key = None
        if redis_client:
            try:
                slug = re.sub(r"[^a-z0-9]+", "_", ((neighborhood_name or city or q) or "").lower()).strip("_")[:64]
                q_hash = hashlib.sha1((q or "").encode()).hexdigest()[:8]
                cache_key = f"enrich:{slug}:{q_hash}:{limit}"
                raw = await redis_client.get(cache_key)
                if raw:
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, list):
                            return parsed
                    except Exception:
                        pass
            except Exception:
                pass

        # Decide poi_type based on query keywords
        poi_type = "restaurant"
        if "coffee" in q_low or "cafe" in q_low:
            poi_type = "coffee"

        # Use the improved venue discovery
        candidates = []
        if bbox:
            center_lat = (bbox[1] + bbox[3]) / 2
            center_lon = (bbox[0] + bbox[2]) / 2

            from city_guides.providers.overpass_provider import get_nearby_venues

            # Get more detailed venue information
            venues = await get_nearby_venues(
                center_lat, center_lon,
                venue_type=poi_type,
                radius=400,  # Slightly larger radius for better context
                limit=limit * 2  # Get more to filter for quality
            )

            # Filter for quality venues
            quality_venues = []
            for venue in venues:
                score = venue.get('quality_score', 0)
                name = venue.get('name', '').strip()
                # Prefer venues with good names and decent scores
                if name and score >= 3 and len(name) > 2:
                    quality_venues.append(venue)
                if len(quality_venues) >= limit:
                    break

            candidates.extend(quality_venues)

        # Basic filtering: ensure lat/lon present and non-zero
        filtered = []
        for c in candidates:
            try:
                if c and float(c.get('lat', 0)) and float(c.get('lon', 0)):
                    filtered.append(c)
            except Exception:
                continue
        # dedupe by id and name
        out = []
        seen = set()
        for c in filtered:
            key = (c.get('id') or '') + '::' + (c.get('name') or '').lower()
            if key not in seen:
                seen.add(key)
                out.append(c)
            if len(out) >= limit:
                break

        # cache results
        if cache_key and redis_client and out:
            try:
                await redis_client.set(cache_key, json.dumps(out), ex=60 * 5)
            except Exception:
                pass

        return out
    except Exception as e:
        print(f"Enhanced auto-enrichment failed: {e}")
        return []


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


@app.route('/generate_quick_guide', methods=['POST'])
async def generate_quick_guide():
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

    # Return cached if exists
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
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
                    try:
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump({'quick_guide': resp['quick_guide'], 'source': resp['source'], 'generated_at': time.time(), 'source_url': None}, f, ensure_ascii=False, indent=2)
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
            # If cached snippet passed sanity checks, return it
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
            ddgs_queries = [
                f"{neighborhood} {city} travel",
                f"{neighborhood} {city} information",
                f"{neighborhood} {city} colonia",
                f"{city} {neighborhood}",
            ]
            ddgs_results = []
            for q in ddgs_queries:
                try:
                    res = await ddgs_search(q, engine="google", max_results=6)
                    print(f"DDGS: query={q} got {len(res) if res else 0} results")
                    if res:
                        ddgs_results.extend(res)
                except Exception as e:
                    print(f"DDGS query failed for {q}: {e}")
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
                synth_prompt = (
                    f"Synthesize a concise (2-4 sentence) English quick guide for the neighborhood '{neighborhood}, {city}'. "
                    f"Use only the facts from the following web snippets; keep it travel-focused (type of area, notable features, transit/access, quick local tips). "
                    f"Answer in English.\n\nWeb snippets:\n{context_text}"
                )
                try:
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
            from city_guides.providers.ddgs_provider import ddgs_search
            ddgs_queries = [
                f"{neighborhood}, {city} travel guide",
                f"{neighborhood} {city} travel",
                f"{neighborhood} travel",
                f"{city} travel guide",
            ]
            ddgs_snippet = None
            ddgs_url = None
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
                except Exception:
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

    # If confidence is low, return a minimal factual sentence to avoid generic fluff
    if confidence == 'low':
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

    if not mapillary_images and image_provider:
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

    resp = {'quick_guide': synthesized, 'source': source or 'data-first', 'cached': False, 'source_url': source_url}
    if mapillary_images:
        resp['mapillary_images'] = mapillary_images
    return jsonify(resp)


def get_country_for_city(city):
    """Return country name for a given city using Nominatim (best-effort)."""
    if not city:
        return None
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
        # Request results in English where possible to prefer ASCII country names
        headers = {"User-Agent": "city-guides-app", "Accept-Language": "en"}
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        if data:
            addr = data[0].get("address", {})
            country = addr.get("country")
            # prefer an ASCII/English country name when possible; Nominatim sometimes returns
            # the localized/native country name (e.g. '中国') which may not work with downstream
            # services. Use the display_name fallback to extract an English name if needed.
            if country:
                try:
                    # if country contains non-ascii characters, try to derive an English name
                    if any(ord(ch) > 127 for ch in country):
                        display = data[0].get("display_name", "") or ""
                        parts = [p.strip() for p in display.split(",") if p.strip()]
                        if parts:
                            # last part of display_name is usually the country in English
                            candidate = parts[-1]
                            if any(c.isalpha() for c in candidate):
                                return candidate
                except Exception:
                    pass
            # fallback to country or country_code
            return country or addr.get("country_code")
    except Exception:
        pass
    return None


def get_provider_links(city):
    """Return a small list of provider links for UI deep-links (best-effort).
    This lightweight helper avoids a hard dependency and provides useful quick links.
    """
    if not city:
        return []
    try:
        q = requests.utils.requote_uri(city)
    except Exception:
        q = city
    links = [
        {"name": "Google Maps", "url": f"https://www.google.com/maps/search/{q}"},
        {"name": "OpenStreetMap", "url": f"https://www.openstreetmap.org/search?query={q}"},
        {"name": "Wikivoyage", "url": f"https://en.wikivoyage.org/wiki/{city.replace(' ', '_')}"},
    ]
    return links


@app.route('/geocode', methods=['POST'])
async def geocode():
    """Simple geocode endpoint that returns lat/lon for a city or neighborhood.
    POST payload: { city: 'City Name', neighborhood?: 'Neighborhood Name' }
    Returns: { lat: float, lon: float, display_name: str } or 400 on failure
    """
    payload = await request.get_json(silent=True) or {}
    city = (payload.get('city') or '').strip()
    country = (payload.get('country') or '').strip()
    neighborhood = (payload.get('neighborhood') or '').strip()
    if not city:
        return jsonify({'error': 'city required'}), 400

    lat = None
    lon = None
    display_name = None
    # try neighborhood scoped first
    if neighborhood:
        result = await geocode_city(f"{neighborhood}, {city}", country)
        if result:
            lat = result['lat']
            lon = result['lon']
            display_name = result['display_name']
    if not lat:
        result = await geocode_city(city, country)
        if result:
            lat = result['lat']
            lon = result['lon']
            display_name = result['display_name']
    if not lat:
        return jsonify({'error': 'geocode_failed'}), 400

    # Build a Sanity-like document for richer downstream use
    try:
        slug_val = re.sub(r'[^a-z0-9]+', '-', (display_name or city).lower()).strip('-')
    except Exception:
        slug_val = re.sub(r'[^a-z0-9]+', '-', (city or '').lower()).strip('-')

    sanity_doc = {
        "_id": f"loc_{slug_val}",
        "_type": "location",
        "name": city or "",
        "neighborhood": neighborhood or "",
        "displayName": display_name or "",
        "slug": {"_type": "slug", "current": slug_val},
        "location": {"lat": float(lat), "lon": float(lon)}
    }

    # Next.js-friendly props wrapper (example for getStaticProps/getServerSideProps)
    next_props = {
        "props": {
            "location": sanity_doc,
            "coordinates": {"lat": float(lat), "lon": float(lon)},
            "displayName": display_name or ""
        },
        # revalidate can be used by Next.js ISR; keep short default
        "revalidate": 60
    }

    resp = {
        "lat": lat,
        "lon": lon,
        "display_name": display_name,
        "sanity": sanity_doc,
        "next": next_props
    }
    return jsonify(resp)


def get_currency_for_country(country):
    """Return the primary currency code (ISO 4217) for a given country name using restcountries API."""
    if not country:
        return None
    try:
        url = (
            f"https://restcountries.com/v3.1/name/{requests.utils.requote_uri(country)}"
        )
        resp = requests.get(
            url,
            params={"fields": "name,currencies"},
            headers={"User-Agent": "city-guides-app"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            # currencies is an object with codes as keys
            cur_obj = data[0].get("currencies") or {}
            if isinstance(cur_obj, dict) and cur_obj:
                # return first currency code
                for code in cur_obj.keys():
                    return code
    except Exception:
        pass
    return None


def get_currency_name(code):
    """Return a human-friendly currency name for an ISO 4217 code.
    Uses a small internal map and falls back to RestCountries lookup when possible.
    """
    if not code:
        return None
    code = code.strip().upper()
    names = {
        "USD": "US Dollar",
        "EUR": "Euro",
        "GBP": "Pound Sterling",
        "JPY": "Japanese Yen",
        "CAD": "Canadian Dollar",
        "AUD": "Australian Dollar",
        "MXN": "Mexican Peso",
        "CNY": "Chinese Yuan",
        "THB": "Thai Baht",
        "RUB": "Russian Ruble",
        "CUP": "Cuban Peso",
        "VES": "Venezuelan Bolívar",
        "KES": "Kenyan Shilling",
        "ZWL": "Zimbabwean Dollar",
        "PEN": "Peruvian Sol",
    }
    if code in names:
        return names[code]
    # try RestCountries API to resolve name
    try:
        url = f"https://restcountries.com/v3.1/currency/{requests.utils.requote_uri(code)}"
        resp = requests.get(
            url,
            params={"fields": "name,currencies"},
            headers={"User-Agent": "city-guides-app"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            cur_obj = data[0].get("currencies") or {}
            # currencies is dict mapping code -> {name, symbol}
            if isinstance(cur_obj, dict) and code in cur_obj:
                info = cur_obj.get(code)
                if isinstance(info, dict):
                    return info.get("name") or info.get("symbol") or code
    except Exception:
        pass
    return code


def _fetch_image_from_website(url):
    """Attempt to fetch an og:image or other image hint from a webpage.
    Returns absolute image URL or None.
    """
    try:
        headers = {"User-Agent": "TravelLand/1.0"}
        resp = requests.get(url, headers=headers, timeout=4)
        resp.raise_for_status()
        html = resp.text
        # look for og:image
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r'<meta[^>]+name=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
        if not m:
            m = re.search(
                r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
        if m:
            img = m.group(1)
            # make absolute if needed
            try:
                p = urlparse(img)
                if not p.scheme:
                    base = urlparse(url)
                    img = f"{base.scheme}://{base.netloc}{img if img.startswith('/') else '/' + img}"
            except Exception:
                pass
            return img
    except Exception:
        return None
    return None


def get_cost_estimates(city, ttl_seconds=None):
    """Fetch average local prices for a city using Teleport free API with caching and a small local fallback.

    Returns a list of dicts: [{'label': 'Coffee', 'value': 12.5}, ...]
    """
    if not city:
        return []

    if ttl_seconds is None:
        ttl_seconds = CACHE_TTL_TELEPORT

    try:
        cache_dir = Path(_here) / ".cache" / "teleport_prices"
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = re.sub(r"[^a-z0-9]+", "_", city.strip().lower())
        cache_file = cache_dir / f"{key}.json"
        # return cached if fresh
        if cache_file.exists():
            try:
                raw = json.loads(cache_file.read_text())
                if raw.get("ts") and time.time() - raw["ts"] < ttl_seconds:
                    return raw.get("data", [])
            except Exception:
                pass

        # Try Teleport search -> city item -> urban area -> prices
        base = "https://api.teleport.org"
        try:
            s = requests.get(
                f"{base}/api/cities/",
                params={"search": city, "limit": 5},
                timeout=6,
                headers={"User-Agent": "city-guides-app"},
            )
            s.raise_for_status()
            j = s.json()
            results = j.get("_embedded", {}).get("city:search-results", [])
            city_item_href = None
            for r in results:
                href = r.get("_links", {}).get("city:item", {}).get("href")
                if href:
                    city_item_href = href
                    break
            if not city_item_href:
                raise RuntimeError("no city item from teleport")

            ci = requests.get(
                city_item_href, timeout=6, headers={"User-Agent": "city-guides-app"}
            )
            ci.raise_for_status()
            ci_j = ci.json()
            urban_href = ci_j.get("_links", {}).get("city:urban_area", {}).get("href")
            if not urban_href:
                # no urban area -> no prices available
                raise RuntimeError("no urban area")

            prices_href = urban_href.rstrip("/") + "/prices/"
            p = requests.get(
                prices_href, timeout=6, headers={"User-Agent": "city-guides-app"}
            )
            p.raise_for_status()
            p_j = p.json()

            items = []
            # Teleport responses typically include 'categories' -> each has 'data' list of items
            for cat in p_j.get("categories", []):
                for d in cat.get("data", []):
                    label = d.get("label") or d.get("id")
                    # find a numeric price in common keys
                    val = None
                    for k in (
                        "usd_value",
                        "currency_dollar_adjusted",
                        "price",
                        "amount",
                        "value",
                    ):
                        if k in d and isinstance(d[k], (int, float)):
                            val = float(d[k])
                            break
                    # some Teleport payloads nest price under 'prices' or similar
                    if val is None:
                        # try nested structures
                        for kk in d.keys():
                            vvv = d.get(kk)
                            if isinstance(vvv, (int, float)):
                                val = float(vvv)
                                break
                    if label and val is not None:
                        items.append({"label": label, "value": round(val, 2)})

            # prefer a short curated subset (coffee, beer, meal, taxi, hotel)
            keywords = ["coffee", "beer", "meal", "taxi", "hotel", "apartment", "rent"]
            selected = []
            lower_seen = set()
            for k in keywords:
                for it in items:
                    if (
                        k in it["label"].lower()
                        and it["label"].lower() not in lower_seen
                    ):
                        selected.append(it)
                        lower_seen.add(it["label"].lower())
                        break
            # if not selected, take first N items
            if not selected:
                selected = items[:8]

            # save cache
            try:
                cache_file.write_text(json.dumps({"ts": time.time(), "data": selected}))
            except Exception:
                pass
            return selected
        except Exception as e:
            logging.debug(f"Teleport fetch failed: {e}")
            # fall through to local fallback

        # Local fallback map keyed by country (best-effort)
        try:
            country = get_country_for_city(city) or ""
        except Exception:
            country = ""
        fb = {
            "china": [
                {"label": "Coffee (cafe)", "value": 20.0},
                {"label": "Local beer (0.5L)", "value": 12.0},
                {"label": "Meal (mid-range)", "value": 70.0},
                {"label": "Taxi start (local)", "value": 10.0},
                {"label": "Hotel (1 night, mid)", "value": 350.0},
            ],
            "russia": [
                {"label": "Coffee (cafe)", "value": 200.0},
                {"label": "Local beer (0.5L)", "value": 150.0},
                {"label": "Meal (mid-range)", "value": 700.0},
                {"label": "Taxi start (local)", "value": 100.0},
                {"label": "Hotel (1 night, mid)", "value": 4000.0},
            ],
            "cuba": [
                {"label": "Coffee (cafe)", "value": 50.0},
                {"label": "Local beer (0.5L)", "value": 60.0},
                {"label": "Meal (mid-range)", "value": 200.0},
                {"label": "Taxi (short)", "value": 80.0},
                {"label": "Hotel (1 night, mid)", "value": 2500.0},
            ],
            "portugal": [
                {"label": "Coffee (cafe)", "value": 1.6},
                {"label": "Local beer (0.5L)", "value": 2.0},
                {"label": "Meal (mid-range)", "value": 12.0},
                {"label": "Taxi start (local)", "value": 3.0},
                {"label": "Hotel (1 night, mid)", "value": 80.0},
            ],
            "united states": [
                {"label": "Coffee (cafe)", "value": 3.5},
                {"label": "Local beer (0.5L)", "value": 5.0},
                {"label": "Meal (mid-range)", "value": 20.0},
                {"label": "Taxi start (local)", "value": 3.0},
                {"label": "Hotel (1 night, mid)", "value": 140.0},
            ],
            "united kingdom": [
                {"label": "Coffee (cafe)", "value": 2.8},
                {"label": "Local beer (0.5L)", "value": 4.0},
                {"label": "Meal (mid-range)", "value": 15.0},
                {"label": "Taxi start (local)", "value": 3.5},
                {"label": "Hotel (1 night, mid)", "value": 120.0},
            ],
            "thailand": [
                {"label": "Coffee (cafe)", "value": 50.0},
                {"label": "Local beer (0.5L)", "value": 60.0},
                {"label": "Meal (mid-range)", "value": 250.0},
                {"label": "Taxi start (local)", "value": 35.0},
                {"label": "Hotel (1 night, mid)", "value": 1200.0},
            ],
        }
        lookup = (country or "").strip().lower()
        # sometimes country is a code; attempt to match common names
        for k in fb.keys():
            if k in lookup:
                try:
                    cache_file.write_text(
                        json.dumps({"ts": time.time(), "data": fb[k]})
                    )
                except Exception:
                    pass
                return fb[k]
        # nothing found
        return []
    except Exception:
        return []


def fetch_us_state_advisory(country):
    """Best-effort fetch of US State Dept travel advisory for a country.
    Returns dict {url, summary} or None.
    """
    if not country:
        return None
    # construct slug
    slug = country.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    urls = [
        f"https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/{slug}.html",
        f"https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/2020/{slug}.html",
    ]
    for u in urls:
        try:
            resp = requests.get(u, headers={"User-Agent": "TravelLand/1.0"}, timeout=8)
            if resp.status_code != 200:
                continue
            html = resp.text
            # try meta description
            m = re.search(
                r'<meta\s+name="description"\s+content="([^"]+)"', html, flags=re.I
            )
            summary = None
            if m:
                summary = m.group(1).strip()
            else:
                # try to find first paragraph
                m2 = re.search(r"<p[^>]*>(.*?)</p>", html, flags=re.I | re.S)
                if m2:
                    summary = re.sub(r"<[^>]+>", "", m2.group(1)).strip()
            return {"url": u, "summary": summary}
        except Exception:
            continue
    return None


def fetch_safety_section(city):
    """Attempt to extract a 'Safety' or 'Crime' section from Wikivoyage or Wikipedia.
    Fallbacks:
      - parse sectioned content via action=parse and look for headings containing keywords
      - use plaintext extracts and search for paragraphs mentioning keywords
      - as last resort, ask semantic.search_and_reason to synthesise tips
    Returns a string (possibly empty).
    """
    if not city:
        return ""
    keywords = [
        "safety",
        "crime",
        "security",
        "safety and security",
        "crime and safety",
    ]
    # Try Wikivoyage first, then Wikipedia
    sites = [
        ("https://en.wikivoyage.org/w/api.php"),
        ("https://en.wikipedia.org/w/api.php"),
    ]
    for api in sites:
        try:
            # fetch sections list
            params = {
                "action": "parse",
                "page": city,
                "prop": "sections",
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                api, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            data = resp.json()
            secs = data.get("parse", {}).get("sections", [])
            for s in secs:
                line = (s.get("line") or "").lower()
                for kw in keywords:
                    if kw in line:
                        idx = s.get("index")
                        # fetch that section's HTML and strip tags
                        params2 = {
                            "action": "parse",
                            "page": city,
                            "prop": "text",
                            "section": idx,
                            "format": "json",
                            "redirects": 1,
                        }
                        resp2 = requests.get(
                            api,
                            params=params2,
                            headers={"User-Agent": "TravelLand/1.0"},
                            timeout=8,
                        )
                        resp2.raise_for_status()
                        html = (
                            resp2.json().get("parse", {}).get("text", {}).get("*", "")
                        )
                        text = re.sub(r"<[^>]+>", "", html).strip()
                        if text:
                            return _sanitize_safety_text(text)
        except Exception:
            # ignore and try next source
            continue

    # Try plaintext extracts and look for paragraphs mentioning keywords
    try:
        for api in sites:
            params = {
                "action": "query",
                "prop": "extracts",
                "explaintext": True,
                "titles": city,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                api, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                extract = p.get("extract", "") or ""
                lower = extract.lower()
                for kw in keywords:
                    if kw in lower:
                        # try to return the paragraph containing the keyword
                        parts = re.split(r"\n\s*\n", extract)
                        for part in parts:
                            if kw in part.lower():
                                return _sanitize_safety_text(part.strip())
    except Exception:
        pass

    # Last resort: synthesise safety tips via semantic module
    try:
        import asyncio
        q = f"Provide 5 concise crime and safety tips for travelers in {city}. Include common scams, areas to avoid, and nighttime safety."
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio  # type: ignore
            nest_asyncio.apply()
            res = loop.run_until_complete(semantic.search_and_reason(q, city, mode="explorer"))
        else:
            res = loop.run_until_complete(semantic.search_and_reason(q, city, mode="explorer"))
        if isinstance(res, dict):
            out = str(res.get("answer") or res.get("text") or res)
        else:
            out = str(res)
        return _sanitize_safety_text(out)
    except Exception:
        return []


def _sanitize_safety_text(raw):
    """Sanitize safety text: remove salutations/persona intros and return concise sentences (up to 5).
    Heuristics:
      - remove leading lines that look like greetings or 'As Marco' intros
      - split into sentences and find the first sentence that looks like advice (starts with a verb or contains 'be', 'avoid', "don't")
      - return up to 5 sentences starting from that point
    """
    if not raw:
        return []
    try:
        text = raw.strip()
        # remove common greetings at start
        text = re.sub(
            r"^(\s*(buon giorno|bonjour|hello|hi|dear|greetings)[^\n]*\n)+",
            "",
            text,
            flags=re.I,
        )
        # remove lines that mention 'Marco' as persona
        text = re.sub(r"(?im)^.*\bmarco\b.*$", "", text)
        # collapse multiple newlines
        text = re.sub(r"\n{2,}", "\n", text).strip()

        # split into sentences (rough)
        sentences = re.findall(r"[^\.\!\?]+[\.\!\?]+", text)
        if not sentences:
            # fallback to line splits
            sentences = [s.strip() for s in text.split("\n") if s.strip()]

        # find first advisory-like sentence
        advice_idx = 0
        adv_regex = re.compile(
            r"^(Be|Avoid|Don't|Do not|Keep|Watch|Stay|Avoiding|Use caution|Exercise|Carry|Keep)\b",
            re.I,
        )
        for i, s in enumerate(sentences):
            if adv_regex.search(s.strip()):
                advice_idx = i
                break

        # take up to 5 sentences from advice_idx; if advice_idx==0, still take first 5
        chosen = sentences[advice_idx : advice_idx + 5]
        # final cleanup: remove ordinal lists like '1.' at the start of a sentence
        clean = [re.sub(r"^\s*\d+\.\s*", "", s).strip() for s in chosen]
        return clean
    except Exception:
        return [raw[:1000]]





def get_weather(lat, lon):
    """Fetch current weather for given latitude and longitude using Open-Meteo API."""
    if not lat or not lon:
        return None
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "temperature_unit": "celsius",
            "windspeed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto",
        }
        resp = requests.get(url, params=params, timeout=6)
        resp.raise_for_status()
        data = resp.json().get("current_weather", {})
        return data
    except Exception:
        return None


def _compute_open_now(lat, lon, opening_hours_str):
    # Use a small local helper to avoid spamming debug logs unless explicitly enabled.
    def _ld(msg):
        if VERBOSE_OPEN_HOURS:
            logging.debug(msg)

    """Best-effort server-side opening_hours check.
    - Tries to resolve timezone from lat/lon using timezonefinder if available.
    - Supports simple OSM opening_hours patterns like '24/7' and 'Mo-Sa 09:00-18:00'; Su 10:00-16:00'.
    Returns (is_open: bool|None, next_change_iso: str|None)
    """
    if not opening_hours_str:
        _ld("No opening_hours_str provided. Returning (None, None).")
        return (None, None)

    s = opening_hours_str.strip()
    if not s:
        _ld("Empty opening_hours_str. Returning (None, None).")
        return (None, None)

    # Quick common check
    if "24/7" in s or "24h" in s or "24 hr" in s.lower():
        _ld("Detected 24/7 hours. Returning (True, None).")
        return (True, None)

    # Determine timezone (best-effort)
    tzname = None
    try:
        from timezonefinder import TimezoneFinder

        tf = TimezoneFinder()
        tzname = tf.timezone_at(lat=float(lat), lng=float(lon)) if lat and lon else None
    except Exception:
        tzname = None

        # If timezonefinder isn't available or didn't find a timezone, allow an
        # explicit override via DEFAULT_TZ (useful on hosts like Render that run in UTC).
        if not tzname:
            tz_env = os.getenv("DEFAULT_TZ")
            if tz_env:
                tzname = tz_env

    from datetime import datetime, time, timedelta

    try:
        from zoneinfo import ZoneInfo
    except Exception:
        ZoneInfo = None

    if tzname and ZoneInfo:
        try:
            now = datetime.now(ZoneInfo(tzname))
        except Exception:
            now = datetime.now()
    else:
        now = datetime.now()

    _ld(f"Parsed timezone: {tzname}")
    _ld(f"Current datetime: {now}")

    # Map short day names to weekday numbers
    days_map = {"mo": 0, "tu": 1, "we": 2, "th": 3, "fr": 4, "sa": 5, "su": 6}

    # Split alternatives by ';'
    parts = [p.strip() for p in s.split(";") if p.strip()]

    def parse_time(tstr):
        try:
            hh, mm = tstr.split(":")
            return time(int(hh), int(mm))
        except Exception:
            return None

    todays_matches = []
    for p in parts:
        # Example: 'Mo-Sa 09:00-18:00' or 'Su 10:00-16:00' or '09:00-18:00'
        tok = p.split()
        if len(tok) == 1 and "-" in tok[0] and ":" in tok[0]:
            # time only, applies every day
            days = list(range(0, 7))
            times = tok[0]
        elif len(tok) >= 2:
            daypart = tok[0]
            times = tok[1]
            days = []
            if "-" in daypart:
                a, b = daypart.split("-")
                a = a.lower()[:2]
                b = b.lower()[:2]
                if a in days_map and b in days_map:
                    ra = days_map[a]
                    rb = days_map[b]
                    if ra <= rb:
                        days = list(range(ra, rb + 1))
                    else:
                        days = list(range(ra, 7)) + list(range(0, rb + 1))
            else:
                # single day or comma-separated
                for d in daypart.split(","):
                    d = d.strip().lower()[:2]
                    if d in days_map:
                        days.append(days_map[d])
        else:
            continue

        if isinstance(times, str) and "-" in times:
            t1s, t2s = times.split("-", 1)
            t1 = parse_time(t1s)
            t2 = parse_time(t2s)
            if t1 and t2:
                if now.weekday() in days:
                    todays_matches.append((t1, t2))

    _ld(f"Today's matches: {todays_matches}")

    # Check if current time falls in any range
    for t1, t2 in todays_matches:
        _ld(f"Checking time range: {t1} - {t2}")
        dt = now.time()
        if t1 <= dt <= t2:
            _ld("Current time falls within range. Returning (True, None).")
            return (True, None)
        # Handle overnight ranges (e.g., 18:00-02:00)
        elif t1 > t2:
            # range spans midnight
            if dt >= t1 or dt <= t2:
                _ld(
                    "Current time falls within overnight range. Returning (True, None)."
                )
                return (True, None)

    _ld("No matching time range found. Returning (False, None).")
    return (False, None)


def _humanize_opening_hours(opening_hours_str):
    """Return a user-friendly hours string in 12-hour format if possible."""
    if not opening_hours_str:
        return None
    import re
    from datetime import time

    def fmt(tstr):
        try:
            hh, mm = tstr.split(":")
            t = time(int(hh), int(mm))
            return t.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")
        except Exception:
            return tstr

    pretty_parts = []
    for part in opening_hours_str.split(";"):
        part = part.strip()
        if not part:
            continue
        # replace ranges like 10:00-22:30 with 10:00 AM–10:30 PM
        part = re.sub(
            r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})",
            lambda m: f"{fmt(m.group(1))}–{fmt(m.group(2))}",
            part,
        )
        pretty_parts.append(part)
    return "; ".join(pretty_parts) if pretty_parts else None





@app.route("/transport")  # type: ignore
async def transport():
    city = request.args.get("city", "the city")
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    # fetch a banner image for the requested city (best-effort)
    try:
        if image_provider:
            banner = await image_provider.get_banner_for_city(city)
            banner_url = banner.get("url") if banner else None
            banner_attr = banner.get("attribution") if banner else None
        else:
            banner_url = None
            banner_attr = None
    except Exception:
        banner_url = None
        banner_attr = None
    # attempt to load any pre-generated transport JSON for this city
    data_dir = Path(__file__).resolve().parents[1] / "data"
    transport_payload = None
    try:
        for p in data_dir.glob("transport_*.json"):
            try:
                with p.open(encoding="utf-8") as f:
                    j = json.load(f)
                if city.lower() in (j.get("city") or "").lower():
                    transport_payload = j
                    break
            except Exception:
                continue
    except Exception:
        transport_payload = None

    # Quick guide via Wikivoyage (use transport payload if it already contains an extract)
    quick_guide = ""
    if transport_payload and transport_payload.get("wikivoyage_summary"):
        quick_guide = transport_payload.get("wikivoyage_summary")
    else:
        try:
            url = "https://en.wikivoyage.org/w/api.php"
            params = {
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": city,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                quick_guide = p.get("extract", "")
                break
        except Exception:
            quick_guide = ""
    # If Wikivoyage didn't have an extract, try Wikipedia as a fallback
    if not quick_guide:
        try:
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": city,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                quick_guide = p.get("extract", "")
                break
        except Exception:
            quick_guide = quick_guide or ""

    # If still no good quick_guide, or the wiki extract looks like an unrelated event/article,
    # try a DDGS (DuckDuckGo) search as a fallback to obtain travel-focused text about the city.
    try:
        should_try_ddgs = False
        if not quick_guide:
            should_try_ddgs = True
        else:
            lower_q = quick_guide.lower()
            blacklist = ['fire', 'wildfire', 'hurricane', 'earthquake', 'storm', 'album', 'song', 'single', 'born', 'died', 'surname']
            if any(b in lower_q for b in blacklist) and city.lower() not in lower_q:
                should_try_ddgs = True
        if should_try_ddgs:
            try:
                from city_guides.providers.ddgs_provider import ddgs_search
                results = await ddgs_search(f"{city} travel guide", engine="google", max_results=5)
                for r in results:
                    body = (r.get('body') or '') or (r.get('title') or '')
                    text = re.sub(r'\s+', ' ', (body or '')).strip()
                    if len(text) > 60:
                        quick_guide = text if len(text) <= 1000 else text[:1000].rsplit(' ', 1)[0] + '...'
                        break
            except Exception:
                app.logger.debug('ddgs lookup failed for city quick_guide', exc_info=True)
    except Exception:
        pass
    # Attempt to fetch a safety/crime section for server-side initial render
    try:
        initial_safety = fetch_safety_section(city) or []
    except Exception:
        initial_safety = []
    # Attempt to fetch US State Dept advisory for the city's country
    try:
        country = get_country_for_city(city)
        initial_us_advisory = fetch_us_state_advisory(country) if country else None
    except Exception:
        initial_us_advisory = None

    provider_links = (
        transport_payload.get("provider_links") if transport_payload else None
    ) or get_provider_links(city)

    city_display = shorten_place(city)
    return render_template(
        "transport.html",
        city=city,
        city_display=city_display,
        lat=lat,
        lon=lon,
        banner_url=banner_url,
        banner_attr=banner_attr,
        initial_quick_guide=quick_guide,
        initial_safety_tips=initial_safety,
        initial_us_advisory=initial_us_advisory,
        initial_provider_links=provider_links,
        initial_transport=transport_payload,
    )


@app.route("/api/transport")
async def api_transport():
    """Return a transport JSON for a requested city.
    Searches files named data/transport_*.json and matches by city substring if provided.
    """
    city_q_raw = (request.args.get("city") or "").strip()
    city_q = city_q_raw.lower()
    data_dir = Path(__file__).resolve().parents[1] / "data"
    files = sorted(data_dir.glob("transport_*.json"))
    payload = None
    for p in files:
        try:
            with p.open(encoding="utf-8") as f:
                j = json.load(f)
            # attach provider links if missing
            try:
                j["provider_links"] = j.get("provider_links") or get_provider_links(
                    j.get("city") or city_q_raw
                )
            except Exception:
                pass
            if city_q and city_q in (j.get("city") or "").lower():
                # attach a compact display name
                try:
                    j["city_display"] = shorten_place(j.get("city") or city_q_raw)
                except Exception:
                    j["city_display"] = j.get("city")
                return jsonify(j)
            if payload is None:
                payload = j
        except Exception:
            continue

    # If a specific city was requested but we didn't find a pre-generated file,
    # return a best-effort minimal payload using geocoding + Wikivoyage extract so
    # the frontend can at least deep-link to Google and show a local quick guide.
    if city_q:
        result = await geocode_city(city_q_raw)
        if result:
            lat = result['lat']
            lon = result['lon']
        quick = ""
        try:
            url = "https://en.wikivoyage.org/w/api.php"
            params = {
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": city_q_raw,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                quick = p.get("extract", "")
                break
        except Exception:
            quick = ""

        minimal = {
            "city": city_q_raw,
            "city_display": shorten_place(city_q_raw),
            "generated_at": None,
            "center": {"lat": lat, "lon": lon},
            "wikivoyage_summary": quick,
            "stops": [],
            "stops_count": 0,
            "provider_links": get_provider_links(city_q_raw),
        }
        return jsonify(minimal)

    if payload:
        return jsonify(payload)
    return jsonify({"error": "no_transport_data"}), 404


def _get_city_info(city):
    """Helper function to gather city info from various sources."""
    if not city:
        return {}

    # Clean city name for API calls (remove country suffix)
    title = city.split(",")[0].strip()

    # geocode best-effort
    lat, lon = None, None  # Removed async call causing 500 error

    # Attempt to reuse existing transport data if present
    data_dir = Path(__file__).resolve().parents[1] / "data"
    transport = None
    try:
        for p in data_dir.glob("transport_*.json"):
            try:
                with p.open(encoding="utf-8") as f:
                    j = json.load(f)
                if city.lower() in (j.get("city") or "").lower():
                    transport = j
                    break
            except Exception:
                continue
    except Exception:
        transport = None

    # Quick guide via Wikivoyage
    quick_guide = ""
    try:
        url = "https://en.wikivoyage.org/w/api.php"
        params = {
            "action": "query",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "titles": title,
            "format": "json",
            "redirects": 1,
        }
        resp = requests.get(
            url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        for p in pages.values():
            quick_guide = p.get("extract", "")
            break
    except Exception:
        quick_guide = ""

    # fallback to Wikipedia if Wikivoyage is empty
    if not quick_guide:
        try:
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": title,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                quick_guide = p.get("extract", "")
                break
        except Exception:
            quick_guide = quick_guide or ""

    # Marco recommendation via semantic module
    marco = None
    try:
        import asyncio
        q = f"How do I get around {city}? Name the primary transit app or website used by locals and give 3 quick survival tips."
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio  # type: ignore
            nest_asyncio.apply()
            marco = loop.run_until_complete(semantic.search_and_reason(q, city, mode="explorer"))
        else:
            marco = loop.run_until_complete(semantic.search_and_reason(q, city, mode="explorer"))
    except Exception:
        marco = None

    # Safety / crime tips (best-effort extraction) -> list of bullets
    try:
        safety_list = fetch_safety_section(city) or []
    except Exception:
        safety_list = []

    google_link = None
    if lat and lon:
        google_link = f"https://www.google.com/maps/@{lat},{lon},13z/data=!5m1!1e2"
    else:
        google_link = f"https://www.google.com/maps/search/{requests.utils.requote_uri(city + ' public transport')}/data=!5m1!1e2"

    # Country-level US State Dept advisory (best-effort)
    us_advisory = None
    try:
        country = get_country_for_city(city)
        if country:
            us_advisory = fetch_us_state_advisory(country)
    except Exception:
        us_advisory = None

    result = {
        "city": city,
        "city_display": shorten_place(city),
        "lat": lat,
        "lon": lon,
        "google_map": google_link,
        "quick_guide": quick_guide,
        "marco": marco,
        "safety_tips": safety_list,
        "us_state_advisory": us_advisory,
        "transport_available": bool(transport),
        "transport": transport,
        "provider_links": (transport.get("provider_links") if transport else None)
        or get_provider_links(city),
    }
    return result


@app.route("/api/city_info")
async def api_city_info():
    """Return quick info for any city: Marco recommendations, Google deep-link, quick guide.
    Falls back to transport JSON if available.
    """
    city = (request.args.get("city") or "").strip()
    if not city:
        return jsonify({"error": "city required"}), 400

    info = await asyncio.to_thread(_get_city_info, city)
    return jsonify(info)


@app.route("/api/locations/countries")
async def api_locations_countries():
    """Return list of countries for hierarchical location selection."""
    cache_key = "travelland:locations:countries:v3"
    
    # Try cache first
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return jsonify(json.loads(cached))
        except Exception:
            pass
    
    # Fetch from GeoNames
    countries = await _get_countries()
    
    # Cache result
    if redis_client and countries:
        try:
            await redis_client.set(cache_key, json.dumps(countries), ex=86400)  # 24 hours
        except Exception:
            pass
    
    return jsonify(countries)


@app.route("/api/locations/states")
async def api_locations_states():
    """Return list of states/provinces for a given country."""
    try:
        country_code = request.args.get("countryCode", "").strip()
        if not country_code:
            return jsonify({"error": "countryCode required"}), 400

        cache_key = f"travelland:locations:states:v2:{country_code}"

        # Try cache first
        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    return jsonify(json.loads(cached))
            except Exception:
                pass

        # Fetch from GeoNames
        states = await _get_states(country_code)

        # Cache result
        if redis_client and states:
            try:
                await redis_client.set(cache_key, json.dumps(states), ex=3600)  # 1 hour
            except Exception:
                pass

        return jsonify(states)
    except Exception as e:
        # Log full traceback to aid debugging and return JSON error to frontend
        app.logger.exception("Unhandled exception in api_locations_states")
        return jsonify({"error": "internal_server_error", "message": str(e)}), 500


@app.route("/api/locations/cities")
async def api_locations_cities():
    """Return list of cities for a given state/country."""
    country_code = request.args.get("countryCode", "").strip()
    state_code = request.args.get("stateCode", "").strip()
    
    if not country_code:
        return jsonify({"error": "countryCode required"}), 400
    
    cache_key = f"travelland:locations:cities:v2:{country_code}:{state_code or 'all'}"
    
    # Try cache first
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return jsonify(json.loads(cached))
        except Exception:
            pass
    
    # Fetch from GeoNames
    cities = await _get_cities(country_code, state_code)
    
    # Cache result
    if redis_client and cities:
        try:
            await redis_client.set(cache_key, json.dumps(cities), ex=3600)  # 1 hour
        except Exception:
            pass
    
    return jsonify(cities)


@app.route("/api/locations/neighborhoods")
async def api_locations_neighborhoods():
    """Return list of neighborhoods for a given city."""
    country_code = request.args.get("countryCode", "").strip()
    state_code = request.args.get("stateCode", "").strip()
    city_name = request.args.get("cityName", "").strip()
    
    if not country_code or not city_name:
        return jsonify({"error": "countryCode and cityName required"}), 400
    
    cache_key = f"travelland:locations:neighborhoods:v2:{country_code}:{state_code}:{city_name.lower()}"
    
    # Try cache first
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return jsonify(json.loads(cached))
        except Exception:
            pass
    
    # Fetch neighborhoods using existing logic
    neighborhoods = await _get_neighborhoods_for_city(city_name, country_code)
    
    # Cache result
    if redis_client and neighborhoods:
        try:
            await redis_client.set(cache_key, json.dumps(neighborhoods), ex=1800)  # 30 minutes
        except Exception:
            pass
    
    return jsonify(neighborhoods)


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


async def _get_states(country_code):
    """Get list of states/provinces for a country from GeoNames."""
    print(f"DEBUG: Fetching states for country_code: {country_code}")
    geonames_user = os.getenv("GEONAMES_USERNAME")
    if not geonames_user:
        # Fallback data for some countries
        fallback_states = {
            "US": [
                {"id": "AL", "name": "Alabama", "code": "AL"},
                {"id": "AK", "name": "Alaska", "code": "AK"},
                {"id": "AZ", "name": "Arizona", "code": "AZ"},
                {"id": "AR", "name": "Arkansas", "code": "AR"},
                {"id": "CA", "name": "California", "code": "CA"},
                {"id": "CO", "name": "Colorado", "code": "CO"},
                {"id": "CT", "name": "Connecticut", "code": "CT"},
                {"id": "DE", "name": "Delaware", "code": "DE"},
                {"id": "FL", "name": "Florida", "code": "FL"},
                {"id": "GA", "name": "Georgia", "code": "GA"},
                {"id": "HI", "name": "Hawaii", "code": "HI"},
                {"id": "ID", "name": "Idaho", "code": "ID"},
                {"id": "IL", "name": "Illinois", "code": "IL"},
                {"id": "IN", "name": "Indiana", "code": "IN"},
                {"id": "IA", "name": "Iowa", "code": "IA"},
                {"id": "KS", "name": "Kansas", "code": "KS"},
                {"id": "KY", "name": "Kentucky", "code": "KY"},
                {"id": "LA", "name": "Louisiana", "code": "LA"},
                {"id": "ME", "name": "Maine", "code": "ME"},
                {"id": "MD", "name": "Maryland", "code": "MD"},
                {"id": "MA", "name": "Massachusetts", "code": "MA"},
                {"id": "MI", "name": "Michigan", "code": "MI"},
                {"id": "MN", "name": "Minnesota", "code": "MN"},
                {"id": "MS", "name": "Mississippi", "code": "MS"},
                {"id": "MO", "name": "Missouri", "code": "MO"},
                {"id": "MT", "name": "Montana", "code": "MT"},
                {"id": "NE", "name": "Nebraska", "code": "NE"},
                {"id": "NV", "name": "Nevada", "code": "NV"},
                {"id": "NH", "name": "New Hampshire", "code": "NH"},
                {"id": "NJ", "name": "New Jersey", "code": "NJ"},
                {"id": "NM", "name": "New Mexico", "code": "NM"},
                {"id": "NY", "name": "New York", "code": "NY"},
                {"id": "NC", "name": "North Carolina", "code": "NC"},
                {"id": "ND", "name": "North Dakota", "code": "ND"},
                {"id": "OH", "name": "Ohio", "code": "OH"},
                {"id": "OK", "name": "Oklahoma", "code": "OK"},
                {"id": "OR", "name": "Oregon", "code": "OR"},
                {"id": "PA", "name": "Pennsylvania", "code": "PA"},
                {"id": "RI", "name": "Rhode Island", "code": "RI"},
                {"id": "SC", "name": "South Carolina", "code": "SC"},
                {"id": "SD", "name": "South Dakota", "code": "SD"},
                {"id": "TN", "name": "Tennessee", "code": "TN"},
                {"id": "TX", "name": "Texas", "code": "TX"},
                {"id": "UT", "name": "Utah", "code": "UT"},
                {"id": "VT", "name": "Vermont", "code": "VT"},
                {"id": "VA", "name": "Virginia", "code": "VA"},
                {"id": "WA", "name": "Washington", "code": "WA"},
                {"id": "WV", "name": "West Virginia", "code": "WV"},
                {"id": "WI", "name": "Wisconsin", "code": "WI"},
                {"id": "WY", "name": "Wyoming", "code": "WY"},
            ],
            "CA": [
                {"id": "ON", "name": "Ontario", "code": "ON"},
                {"id": "QC", "name": "Quebec", "code": "QC"},
                {"id": "BC", "name": "British Columbia", "code": "BC"},
                {"id": "AB", "name": "Alberta", "code": "AB"},
            ],
            "AU": [
                {"id": "NSW", "name": "New South Wales", "code": "NSW"},
                {"id": "VIC", "name": "Victoria", "code": "VIC"},
                {"id": "QLD", "name": "Queensland", "code": "QLD"},
            ],
        }
        return fallback_states.get(country_code, [])
    
    async with get_session() as session:
        try:
            # Use GeoNames children endpoint to get administrative divisions
            country_id = await _get_country_geoname_id(country_code, session)
            print(f"DEBUG: Country ID for {country_code}: {country_id}")
            if not country_id:
                return []
                
            url = "http://api.geonames.org/childrenJSON"
            params = {
                "username": geonames_user,
                "geonameId": country_id,
                "maxRows": 100
            }
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                states = []
                for item in data.get("geonames", []):
                    if item.get("fcode") in ["ADM1", "ADM1H"]:  # Administrative division level 1
                        states.append({
                            "id": item.get("adminCode1"),
                            "name": item.get("name"),
                            "code": item.get("adminCode1")
                        })
                print(f"DEBUG: Found {len(states)} states for {country_code}")
                return states
        except Exception:
            return []


async def _get_cities(country_code, state_code=None):
    """Get list of cities for a country/state from GeoNames."""
    geonames_user = os.getenv("GEONAMES_USERNAME")
    if not geonames_user:
        # Fallback data for some cities
        fallback_cities = {
            "US": {
                "CA": [
                    {"id": "los-angeles", "name": "Los Angeles", "code": "los-angeles"},
                    {"id": "san-francisco", "name": "San Francisco", "code": "san-francisco"},
                    {"id": "san-diego", "name": "San Diego", "code": "san-diego"},
                ],
                "NY": [
                    {"id": "new-york", "name": "New York", "code": "new-york"},
                    {"id": "buffalo", "name": "Buffalo", "code": "buffalo"},
                ],
            },
            "GB": [
                {"id": "london", "name": "London", "code": "london"},
                {"id": "manchester", "name": "Manchester", "code": "manchester"},
                {"id": "birmingham", "name": "Birmingham", "code": "birmingham"},
            ],
        }
        
        if state_code and country_code in fallback_cities:
            return fallback_cities[country_code].get(state_code, [])
        elif country_code in fallback_cities and not isinstance(fallback_cities[country_code], dict):
            return fallback_cities[country_code]
        else:
            return []
    
    async with get_session() as session:
        try:
            url = "http://api.geonames.org/searchJSON"
            params = {
                "username": geonames_user,
                "country": country_code,
                "featureClass": "P",  # Populated places
                "maxRows": 50,
                "orderby": "population"
            }
            if state_code:
                params["adminCode1"] = state_code
            
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                cities = []
                for item in data.get("geonames", []):
                    if item.get("population", 0) > 10000:  # Only cities with significant population
                        cities.append({
                            "id": str(item.get("geonameId")),
                            "name": item.get("name"),
                            "code": item.get("name").lower().replace(" ", "-")
                        })
                return cities
        except Exception:
            return []


async def _get_country_geoname_id(country_code, session):
    """Get GeoNames ID for a country code."""
    try:
        url = "http://api.geonames.org/countryInfoJSON"
        params = {"username": os.getenv("GEONAMES_USERNAME"), "country": country_code}
        async with session.get(url, params=params, timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                countries = data.get("geonames", [])
                if countries:
                    return countries[0].get("geonameId")
    except Exception:
        pass
    return None


async def _get_neighborhoods_for_city(city_name, country_code):
    """Get neighborhoods for a city using existing multi_provider logic."""
    try:
        # Special case for Tlaquepaque - use known coordinates
        if city_name.lower() == "tlaquepaque" and country_code == "MX":
            lat = 20.58775
            lon = -103.30449
        else:
            # First geocode the city to get lat/lon
            geocoded = await geocode_city(city_name, country_code)
            if not geocoded or not geocoded.get("lat") or not geocoded.get("lon"):
                app.logger.warning(f"Could not geocode city {city_name} in {country_code}")
                return []
            lat = geocoded["lat"]
            lon = geocoded["lon"]

        # Always fetch both OSM and GeoNames neighborhoods for these coordinates
        async with get_session() as session:
            neighborhoods_osm = await multi_provider.async_get_neighborhoods(
                city=None,
                lat=lat,
                lon=lon,
                lang="en",
                session=session
            )
            neighborhoods_geonames = []
            try:
                from city_guides.providers import geonames_provider
                neighborhoods_geonames = await geonames_provider.async_get_neighborhoods_geonames(
                    city=None, lat=lat, lon=lon, max_rows=100, session=session
                )
            except Exception as e:
                app.logger.warning(f"GeoNames fetch failed: {e}")

        # Merge and deduplicate by normalized name
        def norm(n):
            return n.get("name", "").strip().lower()
        all_nh = neighborhoods_osm + neighborhoods_geonames
        seen = set()
        formatted_neighborhoods = []
        for nh in all_nh:
            nname = norm(nh)
            if nname and nname not in seen:
                seen.add(nname)
                formatted_neighborhoods.append({
                    "id": nh.get("id", nh.get("name", "").lower().replace(" ", "-")),
                    "name": nh.get("name", ""),
                    "lat": nh.get("lat") or nh.get("center", {}).get("lat"),
                    "lon": nh.get("lon") or nh.get("center", {}).get("lon")
                })

        return formatted_neighborhoods
    except Exception as e:
        app.logger.warning(f"Error fetching neighborhoods for {city_name}: {e}")
        return []


def sync_get_nearby_venues(lat, lon, venue_type="restaurant", radius=500, limit=50):
    """Synchronous wrapper for the async get_nearby_venues function."""
    try:
        # Create a new event loop for this synchronous call
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from city_guides.providers.overpass_provider import get_nearby_venues
            result = loop.run_until_complete(get_nearby_venues(lat, lon, venue_type, radius, limit))
            return result
        finally:
            loop.close()
    except Exception as e:
        print(f"Error in sync_get_nearby_venues: {e}")
        return []


def build_search_cache_key(city: str, q: str, neighborhood: dict | None = None) -> str:
    nh_key = ""
    if neighborhood:
        nh_id = neighborhood.get("id", "")
        nh_key = f":{nh_id}"
    raw = f"search:{(city or '').strip().lower()}:{(q or '').strip().lower()}{nh_key}"
    return "travelland:" + hashlib.sha1(raw.encode()).hexdigest()


@app.route("/search", methods=["POST"])
async def search():
    print(f"[SEARCH ROUTE] Search request received")
    payload = await request.get_json(silent=True) or {}
    print(f"[SEARCH ROUTE] Payload: {payload}")
    # Lightweight heuristic to decide whether to cache this search (focus on food/top queries)
    city = (payload.get("query") or "").strip()
    q = (payload.get("category") or "").strip().lower()
    neighborhood = payload.get("neighborhood")
    should_cache = False  # disabled for testing

    cache_key = None
    cache_ttl = int(os.getenv("SEARCH_CACHE_TTL", "300"))
    if redis_client and should_cache and city and q:
        try:
            cache_key = build_search_cache_key(city, q, neighborhood)
            cached = await redis_client.get(cache_key)
            if cached:
                try:
                    # cached is bytes; decode if needed
                    if isinstance(cached, (bytes, bytearray)):
                        cached = cached.decode("utf-8")
                    return jsonify(json.loads(cached))
                except Exception:
                    # fall through to recompute if cache corrupted
                    app.logger.warning("Cache decode failed, recomputing search")
        except Exception:
            app.logger.debug("Redis cache lookup failed; continuing without cache")

    # Run the existing blocking search logic
    print(f"[SEARCH ROUTE] Calling _search_impl")
    result = _search_impl(payload)
    print(f"[SEARCH ROUTE] _search_impl returned result with {len(result.get('venues', []))} venues")

    # Store in cache for subsequent fast responses
    if redis_client and cache_key and result:
        try:
            await redis_client.set(cache_key, json.dumps(result), ex=cache_ttl)
        except Exception:
            app.logger.debug("Failed to set search cache")

    return jsonify(result)


def _search_impl(payload):
    print(f"[SEARCH DEBUG] _search_impl called with payload: {payload}")
    # This helper is the original synchronous implementation of the /search route.
    # It returns a plain dict suitable for JSONification.
    logging.debug(f"[SEARCH DEBUG] Incoming payload: {payload}")
    # from city_guides.overpass_provider import normalize_city_name, geocode_city
    city_input = (payload.get("query") or "").strip()
    # city = normalize_city_name(city_input)
    city = city_input  # temporary fallback
    if not city:
        return {"error": "City not found or invalid", "debug_info": {"city_input": city_input}}
    debug_info = {
        'city_input': city_input,
        'normalized_city': city,
        'neighborhood_name': None,
        'fallback_triggered': False,
        'neighborhood_bbox': None
    }
    # Respect client-requested result limit (default 10)
    try:
        limit = int(payload.get('limit', 10))
    except Exception:
        limit = 10
    user_lat = payload.get("user_lat")
    user_lon = payload.get("user_lon")
    budget = (payload.get("budget") or "").strip().lower()
    q = (payload.get("category") or "").strip().lower()
    neighborhood = payload.get("neighborhood")
    # If the input city is not the normalized city, treat it as a neighborhood and use parent city for search
    bbox = None
    neighborhood_name = None
    if isinstance(neighborhood, dict):
        neighborhood_name = neighborhood.get("name")
    elif isinstance(neighborhood, str):
        neighborhood_name = neighborhood
    if city_input.lower() != city.lower() and city:
        neighborhood_name = city_input
        debug_info['fallback_triggered'] = True
    debug_info['neighborhood_name'] = neighborhood_name
    bbox = None
    if neighborhood_name:
        nb_full = f"{neighborhood_name}, {city}"
        # Temporary: hardcode for Camden
        if neighborhood_name.lower() == "camden":
            nb_lat, nb_lon = 51.5414, -0.1462
            # Create a bbox around the neighborhood, ~10km radius
            delta = 0.1  # approx 10km
            bbox = [nb_lon - delta, nb_lat - delta, nb_lon + delta, nb_lat + delta]
            debug_info['neighborhood_bbox'] = bbox
        else:
            try:
                # Use synchronous HTTP call to our /geocode endpoint instead of asyncio.run
                # because _search_impl executes synchronously inside the app event loop.
                georesp = requests.post(
                    'http://localhost:5010/geocode',
                    json={'city': city, 'neighborhood': neighborhood_name},
                    timeout=6,
                )
                if georesp.ok:
                    gj = georesp.json()
                    nb_lat = gj.get('lat')
                    nb_lon = gj.get('lon')
                    if nb_lat and nb_lon:
                        # Create a bbox around the neighborhood, ~2km radius
                        delta = 0.02  # approx 2km
                        bbox = [nb_lon - delta, nb_lat - delta, nb_lon + delta, nb_lat + delta]
                        debug_info['neighborhood_bbox'] = bbox
                else:
                    logging.debug(f"Neighborhood geocode HTTP {georesp.status_code} for {nb_full}")
            except Exception as e:
                logging.debug(f"Failed to geocode neighborhood {neighborhood_name} via internal endpoint: {e}")

            # If /geocode failed, try a direct Nominatim lookup as a best-effort fallback
            if bbox is None:
                try:
                    url = 'https://nominatim.openstreetmap.org/search'
                    params = {'q': nb_full, 'format': 'json', 'limit': 1, 'accept-language': 'en'}
                    resp = requests.get(url, params=params, headers={'User-Agent': 'TravelLand/1.0'}, timeout=6)
                    resp.raise_for_status()
                    items = resp.json() or []
                    if items:
                        item = items[0]
                        nb_lat = float(item.get('lat'))
                        nb_lon = float(item.get('lon'))
                        delta = 0.02
                        bbox = [nb_lon - delta, nb_lat - delta, nb_lon + delta, nb_lat + delta]
                        debug_info['neighborhood_bbox'] = bbox
                        logging.debug(f"Nominatim geocoded neighborhood {neighborhood_name} to {nb_lat},{nb_lon}")
                except Exception as e:
                    logging.debug(f"Nominatim geocode fallback failed for {neighborhood_name}: {e}")
    logging.debug(f"[SEARCH DEBUG] (city-level) bbox set to: {bbox}, neighborhood_name: {neighborhood_name}, debug_info: {debug_info}")

    # For city-level searches (no neighborhood), geocode the city to create a bbox for providers that need it
    if bbox is None and city:
        print(f"[SEARCH DEBUG] City-level search detected, geocoding city: {city}")
        try:
            # Read local city data directly (synchronous)
            import json
            import re
            from pathlib import Path
            
            data_dir = Path(__file__).parent.parent / "data"
            slug = re.sub(r"[^a-z0-9]+", "_", city.lower()).strip("_")
            candidate = data_dir / f"city_info_{slug}.json"
            
            if candidate.exists():
                with open(candidate, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    city_lat = j.get("lat")
                    city_lon = j.get("lon")
                    if city_lat and city_lon:
                        # Create a bbox around the city, ~20km radius for city-level searches
                        delta = 0.2  # approx 20km
                        bbox = [city_lon - delta, city_lat - delta, city_lon + delta, city_lat + delta]
                        debug_info['city_bbox'] = bbox
                        print(f"[SEARCH DEBUG] Geocoded city {city} to bbox: {bbox} from local data")
            else:
                print(f"[SEARCH DEBUG] No local data file found for {city}: {candidate}")
        except Exception as e:
            print(f"[SEARCH DEBUG] Failed to geocode city {city} from local data: {e}")
    
    print(f"[SEARCH DEBUG] Final bbox before calling providers: {bbox}")
    import time

    t0 = time.time()
    results = []

    # Detect query intent
    food_keywords = [
        "food",
        "eat",
        "restaurant",
        "cuisine",
        "dining",
        "must eat",
        "must-try",
        "top food",
        "top eats",
        "best food",
        "food highlights",
        "coffee",
        "tea",
    ]
    historic_keywords = [
        "historic",
        "history",
        "museum",
        "monument",
        "landmark",
        "sight",
        "sites",
        "attraction",
        "castle",
        "palace",
        "temple",
        "church",
        "cathedral",
        "ruins",
        "archaeological",
        "heritage",
    ]
    currency_keywords = [
        "currency",
        "exchange",
        "money",
        "convert",
        "usd",
        "eur",
        "dollar",
        "euro",
        "pound",
        "yen",
        "peso",
        "baht",
        "rub",
        "shilling",
        "sol",
        "bolivar",
    ]
    transport_keywords = [
        "transport",
        "metro",
        "subway",
        "bus",
        "train",
        "transit",
        "taxi",
        "ride",
        "tram",
        "underground",
    ]
    is_food_query = any(kw in (q or "") for kw in food_keywords)
    is_historic_query = any(kw in (q or "") for kw in historic_keywords)
    is_currency_query = any(kw in (q or "") for kw in currency_keywords)
    is_transport_query = any(kw in (q or "") for kw in transport_keywords)

    city_info = None
    cost_estimates = []
    weather_data = None

    # Only fetch city_info and cost_estimates if needed
    if is_currency_query:
        # For currency queries, fetch cost estimates and currency info
        cost_estimates = get_cost_estimates(city)
        city_info = _get_city_info(city)  # may include transport/currency info
    elif is_transport_query:
        # For transport queries, fetch city_info (which includes transport)
        city_info = _get_city_info(city)
    elif is_food_query or is_historic_query:
        # For food/venue/historic queries, skip cost/currency/transport enrichments for speed
        pass
    else:
        # Default: fetch city_info for general queries
        city_info = _get_city_info(city)
    # Option to include web/Searx results (default: False)
    include_web = bool(payload.get("include_web", True))
    # Normalize query string for cuisine/food search
    q_norm = (q or "").strip().lower().replace("-", " ").replace("_", " ")
    # Determine whether to exclude obvious chains. If the client explicitly
    # sends local_only, honor it. Otherwise, treat "top/best/must" food queries
    # as a request for local gems.
    if "local_only" in payload:
        local_only = bool(payload.get("local_only"))
    else:
        local_only = any(
            kw in q_norm for kw in ["top", "best", "must", "hidden gem", "local gems"]
        )
    # Special handling for 'top food' queries: try to extract Wikivoyage highlights first
    # Broadened: treat any food-related query as a generic food search
    is_food_query = any(kw in (q or "") for kw in food_keywords)
    wikivoyage_texts = []
    t1 = time.time()
    print(f"[TIMING] After setup: {t1-t0:.2f}s")

    def fetch_wikivoyage_section(city_name, section_keywords, section_type, neighborhood=None):
            print(f"Fetching wikivoyage for city: {city_name}, keywords: {section_keywords}, neighborhood: {neighborhood}")
            # Strip country part for Wikivoyage lookup
            city_base = city_name.split(',')[0].strip()
            url = "https://en.wikivoyage.org/w/api.php"
            params = {
                "action": "parse",
                "page": city_base,
                "prop": "sections",
                "format": "json",
                "redirects": 1,
            }
            items = []
            logging.debug(f"Trying Wikivoyage {section_type} highlights for city: '{city_name}' (neighborhood: {neighborhood})")
            try:
                resp = requests.get(
                    url,
                    params=params,
                    headers={"User-Agent": "TravelLand/1.0"},
                    timeout=8,
                )
                resp.raise_for_status()
                data = resp.json()
                secs = data.get("parse", {}).get("sections", [])
                target_section_idx = None
                for s in secs:
                    line = (s.get("line") or "").lower()
                    print(f"Checking line: '{line}' with keywords {section_keywords}")
                    if any(line == kw.lower() for kw in section_keywords):
                        target_section_idx = s.get("index")
                        print(f"Matched! target_section_idx = {target_section_idx}")
                        break

                # If no exact 'Food' section found, try a broader scan of the full page
                def _extract_from_html(html, section_anchor=None):
                    highlights = re.findall(r"<li>(.*?)</li>", html, re.DOTALL)
                    if not highlights:
                        highlights = re.split(r"<br ?/?>|\n|</p>", html)

                    def clean_html(raw):
                        # Remove style tags and their content
                        raw = re.sub(r"<style[^>]*>.*?</style>", "", raw, flags=re.DOTALL | re.IGNORECASE)
                        # Remove script tags and their content
                        raw = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
                        # Remove all remaining HTML tags
                        raw = re.sub(r"<[^>]+>", "", raw)
                        # Clean up multiple spaces
                        raw = re.sub(r"\s+", " ", raw).strip()
                        return raw

                    cleaned = [clean_html(h) for h in highlights if clean_html(h)]
                    out = []
                    for h in cleaned:
                        # Only keep lines that mention likely food/drink keywords or neighborhood name
                        combined_check = (neighborhood or '') + ' ' + ' '.join(section_keywords)
                        if any(kw.lower() in h.lower() for kw in section_keywords) or (neighborhood and neighborhood.lower() in h.lower()) or any(kw.lower() in h.lower() for kw in ['coffee', 'cafe', 'tea', 'restaurant', 'pub', 'bar']):
                            wikivoyage_url = f"https://en.wikivoyage.org/wiki/{city_base}"
                            if section_keywords:
                                wikivoyage_url = wikivoyage_url + "#" + (section_keywords[0].replace(" ", "_").title())
                            out.append({"text": h, "wikivoyage_url": wikivoyage_url, "section": section_type})
                    return out

                print(f"DEBUG: section_keywords={section_keywords}, target_section_idx={target_section_idx}")

                if target_section_idx:
                    params2 = {
                        "action": "parse",
                        "page": city_base,
                        "prop": "text",
                        "section": target_section_idx,
                        "format": "json",
                        "redirects": 1,
                    }
                    resp2 = requests.get(
                        url,
                        params=params2,
                        headers={"User-Agent": "TravelLand/1.0"},
                        timeout=8,
                    )
                    resp2.raise_for_status()
                    html = resp2.json().get("parse", {}).get("text", {}).get("*", "")
                    items = _extract_from_html(html)
                else:
                    # Full page scan: fetch full HTML and attempt to find neighborhood-specific or keyword-rich lines
                    params2 = {
                        "action": "parse",
                        "page": city_base,
                        "prop": "text",
                        "format": "json",
                        "redirects": 1,
                    }
                    resp2 = requests.get(
                        url,
                        params=params2,
                        headers={"User-Agent": "TravelLand/1.0"},
                        timeout=8,
                    )
                    resp2.raise_for_status()
                    html = resp2.json().get("parse", {}).get("text", {}).get("*", "")
                    items = _extract_from_html(html)

            except Exception as e:
                logging.debug(f"Wikivoyage {section_type} highlights failed for {city_name}: {e}")
            return items

    # Determine provider timeout and start real venue discovery earlier so real POIs rank higher
    provider_timeout = None
    try:
        timeout_val = payload.get("timeout")
        if timeout_val:
            provider_timeout = float(timeout_val)
    except (ValueError, TypeError):
        provider_timeout = None
    if provider_timeout:
        provider_timeout = max(3.0, provider_timeout - 2.0)
    else:
        provider_timeout = 15.0  # Increased from 5.0 to allow time for all providers including Mapillary
    # If a neighborhood bbox is present, give providers more time to return localized results
    if neighborhood_name and bbox:
        provider_timeout = max(provider_timeout, 10.0)

    # Determine POI type based on query
    category_mapping = {
        "coffee & tea": "coffee",
        "hidden gems": "hidden",
        "public transport": "transport",
        "food": "restaurant",
        "nightlife": "restaurant",  # or specific
        "culture": "historic",
        "outdoors": "park",
        "shopping": "market",
        "history": "historic",
    }
    poi_type = category_mapping.get(q, "restaurant" if is_food_query else ("historic" if is_historic_query else "general"))

    # Fetch real venues and Wikivoyage highlights in parallel to avoid timeouts
    # Run provider-based discovery for any explicit category request (including Hidden gems)
    if q:
        t_real_start = time.time()

        # Enhanced venue discovery with improved proximity-based search
        if q and any(kw in q.lower() for kw in ['food', 'eat', 'restaurant', 'coffee', 'bar', 'cafe', 'taco', 'pizza', 'burger', 'sushi', 'asian', 'mexican', 'chinese', 'japanese', 'korean', 'italian', 'indian', 'thai', 'vietnamese', 'greek', 'spanish', 'german', 'british']):
            t_real_start = time.time()

            # Determine venue type and cuisine from query
            venue_type = "restaurant"
            cuisine = None
            q_lower = q.lower()
            
            # Map query keywords to venue types and cuisines
            if any(kw in q_lower for kw in ['coffee', 'cafe', 'tea', 'espresso', 'latte']):
                venue_type = "coffee"
            elif any(kw in q_lower for kw in ['bar', 'pub', 'nightlife', 'drinks', 'cocktail', 'beer', 'wine']):
                venue_type = "bar"
            elif any(kw in q_lower for kw in ['taco', 'mexican']):
                venue_type = "restaurant"
                cuisine = "mexican"
            elif any(kw in q_lower for kw in ['pizza', 'italian']):
                venue_type = "restaurant"
                cuisine = "italian"
            elif any(kw in q_lower for kw in ['sushi', 'japanese']):
                venue_type = "restaurant"
                cuisine = "japanese"
            elif any(kw in q_lower for kw in ['chinese', 'dim sum']):
                venue_type = "restaurant"
                cuisine = "chinese"
            elif any(kw in q_lower for kw in ['korean', 'bbq']):
                venue_type = "restaurant"
                cuisine = "korean"
            elif any(kw in q_lower for kw in ['asian', 'thai', 'vietnamese']):
                venue_type = "restaurant"
                cuisine = "asian"
            elif any(kw in q_lower for kw in ['burger', 'american']):
                venue_type = "restaurant"
                cuisine = "american"
            elif any(kw in q_lower for kw in ['french', 'crepe', 'crepes']):
                venue_type = "restaurant"
                cuisine = "french"
            elif any(kw in q_lower for kw in ['indian', 'curry']):
                venue_type = "restaurant"
                cuisine = "indian"
            elif any(kw in q_lower for kw in ['thai', 'pad thai']):
                venue_type = "restaurant"
                cuisine = "thai"
            elif any(kw in q_lower for kw in ['vietnamese', 'pho']):
                venue_type = "restaurant"
                cuisine = "vietnamese"
            elif any(kw in q_lower for kw in ['greek', 'mediterranean']):
                venue_type = "restaurant"
                cuisine = "greek"
            elif any(kw in q_lower for kw in ['spanish', 'tapas']):
                venue_type = "restaurant"
                cuisine = "spanish"
            elif any(kw in q_lower for kw in ['german', 'bratwurst']):
                venue_type = "restaurant"
                cuisine = "german"
            elif any(kw in q_lower for kw in ['british', 'fish and chips']):
                venue_type = "restaurant"
                cuisine = "british"

            # Get coordinates for search
            search_lat, search_lon = user_lat, user_lon

            # If we don't have explicit user coordinates, try to geocode the city to get a reasonable center
            if (search_lat is None or search_lon is None) and city:
                try:
                    georesp = requests.post(
                        'http://localhost:5010/geocode',
                        json={'city': city},
                        timeout=6,
                    )
                    if georesp.ok:
                        gj = georesp.json()
                        search_lat = gj.get('lat') or search_lat
                        search_lon = gj.get('lon') or search_lon
                except Exception:
                    # best-effort geocode failed — continue without coordinates
                    search_lat = search_lat
                    search_lon = search_lon

            # If neighborhood is provided, use its center
            if neighborhood_name and bbox:
                center_lat = (bbox[1] + bbox[3]) / 2
                center_lon = (bbox[0] + bbox[2]) / 2
                search_lat, search_lon = center_lat, center_lon

            # Use enhanced proximity-based search
            from city_guides.providers.overpass_provider import get_nearby_venues
            import asyncio
            pois = []
            # Execute proximity-based provider in a separate thread to avoid event loop conflicts
            from concurrent.futures import ThreadPoolExecutor, TimeoutError
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    fut = executor.submit(
                        lambda: asyncio.run(
                            get_nearby_venues(
                                search_lat,
                                search_lon,
                                venue_type=venue_type,
                                radius=calculate_search_radius(neighborhood_name, bbox),
                                limit=100,
                            )
                        )
                    )
                    pois = fut.result(timeout=provider_timeout + 2)
            except TimeoutError:
                print(f"Timeout while fetching nearby venues (timeout={provider_timeout + 2}s)")
                pois = []
            except Exception as e:
                print(f"Error in async get_nearby_venues: {e}")
                pois = []

            # Filter by cuisine if specified
            if cuisine and pois:
                filtered_pois = []
                for poi in pois:
                    poi_cuisine = (poi.get('cuisine', '') or '').lower()
                    if cuisine.lower() in poi_cuisine or poi_cuisine in cuisine.lower():
                        filtered_pois.append(poi)
                pois = filtered_pois

            # Process results
            results = []
            for poi in pois:
                venue = format_venue_for_display(poi)
                results.append(venue)

            t_real_end = time.time()
            print(f"[TIMING] Enhanced venue search: {t_real_end-t_real_start:.2f}s")
        else:
            # Original logic for non-food queries
            from concurrent.futures import ThreadPoolExecutor

            pois = []
            wikivoyage_texts = []
            wiki_keywords = []
            wiki_section = None
            if is_food_query:
                wiki_keywords = ["Eat", "Food", "Drink"]
                wiki_section = "food"
            elif is_historic_query:
                wiki_keywords = ["See"]
                wiki_section = "historic"

            with ThreadPoolExecutor(max_workers=2) as executor:
                provider_future = executor.submit(
                    multi_provider.discover_pois,
                    city,
                    poi_type=poi_type,
                    limit=100,
                    local_only=local_only if poi_type == "restaurant" else False,
                    timeout=provider_timeout,
                    bbox=bbox,  # Use neighborhood bbox if available
                    neighborhood=neighborhood_name  # Pass neighborhood name
                )
                wiki_future = None
                if include_web and wiki_keywords and not neighborhood_name:
                    wiki_future = executor.submit(fetch_wikivoyage_section, city, wiki_keywords, wiki_section)

                try:
                    pois = provider_future.result(timeout=provider_timeout)
                    print(f"[DEBUG] multi_provider returned {len(pois)} {poi_type} venues for city '{city}'")
                    partial = False
                except Exception as e:
                    import traceback
                    print(f"[ERROR] Failed to fetch real venues: {e}")
                    traceback.print_exc()
                    pois = []
                    partial = True

                if wiki_future:
                    try:
                        wikivoyage_texts = wiki_future.result(timeout=min(8.0, provider_timeout)) or []
                    except Exception as e:
                        import traceback
                        logging.debug(f"Wikivoyage fetch failed or timed out: {e}")
                        traceback.print_exc()
                        wikivoyage_texts = []

        # If neighborhood is provided, filter or rank venues by proximity to neighborhood center
        if neighborhood_name:
            # Prefer the bbox we already computed earlier (if any) otherwise attempt a synchronous geocode
            try:
                nb_bbox = debug_info.get('neighborhood_bbox') or bbox
                if nb_bbox is None:
                    try:
                        georesp = requests.post(
                            'http://localhost:5010/geocode',
                            json={'city': city, 'neighborhood': neighborhood_name},
                            timeout=6,
                        )
                        if georesp.ok:
                            gj = georesp.json()
                            nb_lat = gj.get('lat')
                            nb_lon = gj.get('lon')
                            if nb_lat and nb_lon:
                                delta = 0.02
                                nb_bbox = [nb_lon - delta, nb_lat - delta, nb_lon + delta, nb_lat + delta]
                                debug_info['neighborhood_bbox'] = nb_bbox
                    except Exception as e:
                        logging.debug(f"Synchronous neighborhood geocode failed: {e}")

                if nb_bbox is not None and len(nb_bbox) == 4:
                    min_lon, min_lat, max_lon, max_lat = nb_bbox  # type: ignore
                    center_lat = (min_lat + max_lat) / 2
                    center_lon = (min_lon + max_lon) / 2

                    def dist_km(venue):
                        lat = venue.get("lat") or venue.get("latitude")
                        lon = venue.get("lon") or venue.get("longitude")
                        if lat is None or lon is None:
                            return 1e9
                        from math import radians, sin, cos, asin, sqrt

                        lat1, lon1, lat2, lon2 = map(float, (center_lat, center_lon, lat, lon))
                        dlat = radians(lat2 - lat1)
                        dlon = radians(lon2 - lon1)
                        a = (
                            sin(dlat / 2) ** 2
                            + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
                        )
                        c = 2 * asin(sqrt(a))
                        return 6371.0 * c

                    pois = sorted(pois, key=dist_km)
                    logging.debug(f"[SEARCH DEBUG] Applied proximity filtering to neighborhood '{neighborhood_name}' with bbox {nb_bbox}")
                else:
                    logging.debug(f"[SEARCH DEBUG] Could not geocode neighborhood '{neighborhood_name}', skipping proximity filtering.")
            except Exception as e:
                logging.warning(f"[WARN] Could not geocode neighborhood '{neighborhood_name}': {e}")
                # fallback: no filtering

        reverse_count = 0
        for poi in (pois or [])[:20]:
            amenity = poi.get("amenity", "")

            # Normalize tags: some providers return a dict, others a string.
            raw_tags = poi.get("tags", "")
            if isinstance(raw_tags, dict):
                tags_text = ", ".join(f"{k}={v}" for k, v in raw_tags.items())
            else:
                tags_text = str(raw_tags or "")

            v_budget = poi.get("budget")
            price_range = poi.get("price_range")
            if not v_budget:
                v_budget = "mid"
                price_range = "$$"
                tags_lower = tags_text.lower()
                if (
                    amenity in ["fast_food", "cafe", "food_court"]
                    or "cuisine=fast_food" in tags_lower
                    or "cost=cheap" in tags_lower
                ):
                    v_budget = "cheap"
                    price_range = "$"
            if budget and budget != "any" and v_budget != budget:
                continue

            desc = poi.get("description")
            tags_str = tags_text.lower()
            if not desc:
                tags_dict = dict(
                    tag.split("=", 1)
                    for tag in tags_text.split(", ")
                    if "=" in tag
                )
                cuisine = tags_dict.get("cuisine", "").replace(";", ", ")
                brand = tags_dict.get("brand", "")
                features = []
                if "outdoor_seating=yes" in tags_str:
                    features.append("outdoor seating")
                if "wheelchair=yes" in tags_str:
                    features.append("accessible")
                if "takeaway=yes" in tags_str:
                    features.append("takeaway available")
                if "delivery=yes" in tags_dict:
                    features.append("delivery")
                if "opening_hours" in tags_dict:
                    features.append("listed hours")
                feature_text = f" with {', '.join(features)}" if features else ""

                if cuisine:
                    desc = f"{cuisine.title()} restaurant{feature_text}"
                    if brand:
                        desc = f"{brand} - {desc}"
                else:
                    desc = (
                        f"Restaurant ({amenity}){feature_text}"
                        if amenity
                        else f"Local venue{feature_text}"
                    )
                    if brand:
                        desc = f"{brand} - {desc}"

                hours_val = tags_dict.get("opening_hours", "").strip()
                if hours_val:
                    pretty_hours = _humanize_opening_hours(hours_val) or hours_val
                    desc += f". Hours: {pretty_hours}"
                else:
                    logging.debug("No valid hours found. Skipping hours display.")

            address = (poi.get("address") or "").strip() or None
            if (not address or re.match(r'^-?\d+\.\d+,\s*-?\d+\.\d+$', (address or "").strip())) and poi.get("lat") and poi.get("lon") and reverse_count < 20:
                address = reverse_geocode_sync(poi["lat"], poi["lon"])
                reverse_count += 1
            tags_dict = dict(
                tag.split("=", 1)
                for tag in tags_text.split(", ")
                if "=" in tag
            )
            phone = tags_dict.get("phone") or tags_dict.get("contact:phone")
            if phone:
                phone = f"tel:{phone}"

            rating = poi.get("rating")
            hours = tags_dict.get("opening_hours") or tags_dict.get("hours") or ""
            pretty_hours = _humanize_opening_hours(hours) if hours else None
            try:
                is_open, next_change = _compute_open_now(
                    poi.get("lat"), poi.get("lon"), hours
                )
            except Exception:
                is_open, next_change = (None, None)

            venue = {
                "id": poi.get("osm_id", poi.get("id", "")),
                "city": city,
                "name": poi.get("name", "Unknown"),
                "budget": v_budget,
                "price_range": price_range,
                "description": desc,
                "tags": poi.get("tags", ""),
                "address": address,
                "latitude": poi.get("lat", 0),
                "longitude": poi.get("lon", 0),
                "website": poi.get("website", ""),
                "osm_url": poi.get("osm_url", ""),
                "amenity": amenity,
                "provider": poi.get("provider", "osm"),
                "phone": phone,
                "rating": rating,
                "opening_hours": hours,
                "opening_hours_pretty": pretty_hours,
                "open_now": is_open,
                "next_change": next_change,
            }
            venue = format_venue(venue)
            results.append(venue)

        t_real_end = time.time()
        print(f"[TIMING] Real venue search: {t_real_end-t_real_start:.2f}s")

        # Debug: check what we have in results
        print(f"[DEBUG] Results list has {len(results)} items")
        for i, r in enumerate(results[:3]):  # Show first 3
            print(f"[DEBUG] Result {i}: name='{r.get('name')}', provider='{r.get('provider')}'")

        # If provider POIs exist, prefer them (OSM/real venues) and include Wikivoyage only as context
        if results:
            debug_info['venues_source'] = 'osm'
            print(f"[SEARCH] Returning {len(results)} OSM venues; including Wikivoyage as contextual highlights ({len(wikivoyage_texts)} items)")
        else:
            # Fallback to Wikivoyage items when no real POIs were found and neighborhood is provided
            if is_food_query and neighborhood_name and include_web:
                try:
                    print(f"[WIKIVOYAGE FALLBACK] No POIs from providers, attempting neighborhood wikivoyage extraction for '{neighborhood_name}'")
                    wiki_items = fetch_wikivoyage_section(city, ['eat', 'food', 'cafe', 'coffee', 'tea'], 'food', neighborhood_name)
                    for idx, wi in enumerate((wiki_items or [])[:12]):
                        # Attempt to extract a name and short description
                        text = wi.get('text', '')
                        # If the text contains a link-like name at start, use it, else use first sentence
                        name_match = re.match(r"\s*([^\-–—,:]+)[\-–—,:]\s*(.*)", text)
                        if name_match:
                            name = name_match.group(1).strip()
                            desc = name_match.group(2).strip()
                        else:
                            # Fallback: first 60 characters as name, rest as description
                            parts = text.split('.', 1)
                            name = parts[0][:60].strip()
                            desc = (parts[1].strip() if len(parts) > 1 else '').strip()
                        venue = {
                            'id': f"wikivoyage-{idx}",
                            'city': city,
                            'name': name or 'Local spot',
                            'budget': 'mid',
                            'price_range': '$$',
                            'description': desc or text,
                            'tags': 'wikivoyage',
                            'address': None,
                            'latitude': None,
                            'longitude': None,
                            'website': wi.get('wikivoyage_url'),
                            'osm_url': None,  # don't set OSM URL for wikivoyage-derived venues
                            'provider': 'wikivoyage',
                        }
                        results.append(format_venue(venue))
                    if results:
                        partial = True
                        debug_info['venues_source'] = 'wikivoyage_fallback'
                except Exception as e:
                    logging.debug(f"Wikivoyage neighborhood fallback failed: {e}")
            else:
                debug_info['venues_source'] = 'none'

    # Now fetch Wikivoyage highlights as descriptive guidance (not venues)
    # Always try to include a city-level WikiVoyage summary if available
    if city and include_web:
        # Section highlights for food/historic queries
        if is_food_query:
            wikivoyage_texts = fetch_wikivoyage_section(city, [
                "eat", "food", "cuisine", "dining", "restaurants", "must eat", "must-try"
            ], "food")
        elif is_historic_query:
            wikivoyage_texts = fetch_wikivoyage_section(city, [
                "see", "sight", "sights", "attractions", "historic", "landmarks", "monuments"
            ], "historic")
        # If no section highlights found, fetch city-level summary
        if not wikivoyage_texts:
            try:
                url = "https://en.wikivoyage.org/w/api.php"
                params = {
                    "action": "query",
                    "prop": "extracts",
                    "exintro": True,
                    "explaintext": True,
                    "titles": city.split(",")[0].strip(),
                    "format": "json",
                    "redirects": 1,
                }
                resp = requests.get(
                    url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
                )
                resp.raise_for_status()
                pages = resp.json().get("query", {}).get("pages", {})
                for p in pages.values():
                    summary = p.get("extract", "")
                    if summary:
                        wikivoyage_texts = [{"title": city.split(",")[0].strip(), "content": summary}]
                        break
            except Exception:
                pass

    t4 = time.time()
    print(f"[TIMING] Total (post-setup): {t4-t0:.2f}s")

    # Wikivoyage highlights are returned separately in `wikivoyage_texts`

    print(f"SEARCH RESULTS: found {len(results)} venues")
    try:
        if user_lat and user_lon and results:

            def haversine_km(lat1, lon1, lat2, lon2):
                from math import radians, sin, cos, asin, sqrt

                lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
                dlat = radians(lat2 - lat1)
                dlon = radians(lon2 - lon1)
                a = (
                    sin(dlat / 2) ** 2
                    + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
                )
                c = 2 * asin(sqrt(a))
                return 6371.0 * c

            for v in results:
                try:
                    v["distance_km"] = round(
                        haversine_km(
                            user_lat,
                            user_lon,
                            v.get("latitude", 0),
                            v.get("longitude", 0),
                        ),
                        2,
                    )
                except Exception:
                    v["distance_km"] = None
            results.sort(
                key=lambda x: (
                    x.get("distance_km") if x.get("distance_km") is not None else 1e9
                )
            )
    except Exception:
        pass

    # ensure partial is defined
    partial = locals().get("partial", False)

    # If the client requested web enrichment (include_web) try to populate images
    try:
        if include_web:
            # limit external fetches to avoid blocking too long
            max_fetch = 8
            fetched = 0
            for v in results:
                if fetched >= max_fetch:
                    break
                if v.get("image"):
                    continue
                # prefer website field
                website = v.get("website") or v.get("osm_url")
                if website:
                    img = _fetch_image_from_website(website)
                    if img:
                        v["image"] = img
                        fetched += 1
    except Exception:
        pass

    # Use a thread pool to fetch images for venues that have a website but no image
    # This is a good candidate for parallelization because it involves network I/O
    # and can be slow.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    venues_to_enrich = [v for v in results if v.get("website") and not v.get("image")]
    if venues_to_enrich:
        enriched_data = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_venue = {
                executor.submit(_fetch_image_from_website, v["website"]): v
                for v in venues_to_enrich
            }
            for future in as_completed(future_to_venue):
                venue = future_to_venue[future]
                try:
                    image_url = future.result()
                    if image_url:
                        enriched_data[venue["id"]] = {"image": image_url}
                except Exception as exc:
                    # Log errors but don't crash
                    logging.warning(
                        f"Image enrichment failed for {venue.get('website')}: {exc}"
                    )

        # Update venues with enriched data
        for venue in results:
            if venue["id"] in enriched_data:
                venue.update(enriched_data[venue["id"]])

    # Helper to decide whether a venue is an authoritative/candidate venue
    def is_real_venue(v):
        if not isinstance(v, dict):
            return False
        provider = v.get('provider', '').lower()
        name = v.get('name', '').strip()
        if provider in ("wikivoyage", "summary"):
            return False
        if not name or name.lower() in ("unknown", "unnamed", ""):
            return False
        return True

    # Whether we already have real venue candidates
    has_real_venue = any(is_real_venue(v) for v in results)

    # Optionally re-rank candidate venues using Groq RAG recommender if enabled and only when real venues exist
    use_groq = os.getenv("USE_GROQ_RAG", "false").lower() in ("1", "true", "yes")
    if use_groq and has_real_venue:
        try:
            from city_guides.groq.traveland_rag import recommend_venues_rag, recommender
            if recommender.api_key:
                candidates = results[:50]
                user_context = {"city": city, "neighborhood": neighborhood_name, "q": q, "preferences": {}}
                groq_recs = recommend_venues_rag(user_context, candidates)
                if groq_recs:
                    id_map = {c.get("id"): c for c in candidates if c.get("id")}
                    ordered = []
                    for r in groq_recs:
                        vid = r.get("id")
                        cand = id_map.get(vid)
                        if cand:
                            c = cand.copy()
                            c["groq_score"] = r.get("score")
                            c["groq_confidence"] = r.get("confidence")
                            c["groq_reason"] = r.get("reason")
                            c["groq_sources"] = r.get("sources", [])
                            ordered.append(c)
                    # Append remaining candidates after Groq-ranked ones
                    seen = set([v.get("id") for v in ordered])
                    for c in candidates:
                        if c.get("id") not in seen:
                            ordered.append(c)
                    results = ordered[:limit]
                    debug_info["groq_used"] = True
                    debug_info["groq_count"] = len(groq_recs)
                else:
                    debug_info["groq_used"] = False
            else:
                # No real GROQ key configured — support a developer mock if requested
                if os.getenv("FORCE_GROQ_MOCK", "false").lower() in ("1", "true", "yes"):
                    candidates = results[:50]
                    mock_recs = []
                    for c in candidates:
                        name = (c.get("name") or "").lower()
                        desc = (c.get("description") or "").lower()
                        score = 0.6
                        if q and q.lower() in name or q and q.lower() in desc:
                            score = 0.9
                        mock_recs.append({"id": c.get("id"), "score": score, "confidence": "medium", "reason": "mocked ranking"})
                    # Apply mock recs
                    id_map = {c.get("id"): c for c in candidates if c.get("id")}
                    ordered = []
                    for r in mock_recs:
                        vid = r.get("id")
                        cand = id_map.get(vid)
                        if cand:
                            c = cand.copy()
                            c["groq_score"] = r.get("score")
                            c["groq_confidence"] = r.get("confidence")
                            c["groq_reason"] = r.get("reason")
                            c["groq_sources"] = r.get("sources", [])
                            ordered.append(c)
                    seen = set([v.get("id") for v in ordered])
                    for c in candidates:
                        if c.get("id") not in seen:
                            ordered.append(c)
                    results = ordered[:limit]
                    debug_info["groq_used"] = "mock"
                    debug_info["groq_count"] = len(mock_recs)
                else:
                    debug_info["groq_used"] = False
        except Exception as e:
            debug_info["groq_error"] = str(e)

    has_real_venue = any(is_real_venue(v) for v in results)
    if not has_real_venue:
        fallback_city = city or payload.get('query') or ''
        fallback_name = f"See more on Google Maps"
        fallback_desc = "No venues found, but you can explore more options on Google Maps."
        fallback_url = f"https://www.google.com/maps/search/?api=1&query={fallback_city.replace(' ', '+')}"
        results = [{
            "id": "google-maps-fallback",
            "name": fallback_name,
            "address": fallback_city,
            "description": fallback_desc,
            "latitude": None,
            "longitude": None,
            "city": fallback_city,
            "provider": "fallback",
            "osm_url": fallback_url,
            "website": fallback_url,
            "image": None
        }]
    response_data = {
        "venues": results,
        "city": city,  # Always return normalized city name
        "city_info": city_info,
        "partial": partial,
        "weather": weather_data,
        "wikivoyage": wikivoyage_texts,
        "transport": get_provider_links(city),
        "costs": cost_estimates,
        "debug_info": debug_info,
    }
    return response_data


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


async def prewarm_popular_searches():
    if not redis_client or not RAW_PREWARM_CITIES or not PREWARM_QUERIES:
        return
    sem = asyncio.Semaphore(2)
    async def limited(city, query):
        async with sem:
            await prewarm_search_cache_entry(city, query)
            try:
                await prewarm_neighborhood(city)
            except Exception:
                pass

    tasks = [limited(city, query) for city in RAW_PREWARM_CITIES for query in PREWARM_QUERIES]
    if tasks:
        app.logger.info("Starting prewarm for %d popular searches", len(tasks))
        await asyncio.gather(*tasks)


async def prewarm_popular_neighborhoods():
    """Background worker to prewarm neighborhood lists for a short list of popular cities."""
    if not redis_client or not POPULAR_CITIES:
        return
    app.logger.info("Starting background neighborhood prewarm for %d cities", len(POPULAR_CITIES))
    for city in POPULAR_CITIES:
        try:
            # reuse prewarm helper which will set cache if results found
            await prewarm_neighborhood(city)
        except Exception:
            app.logger.exception("prewarm_neighborhood failed for %s", city)
        # be nice to remote APIs and avoid abrupt bursts
        try:
            await asyncio.sleep(float(os.getenv("NEIGHBORHOOD_PREWARM_PAUSE", 1.0)))
        except Exception:
            await asyncio.sleep(1.0)
    app.logger.info("Finished background neighborhood prewarm")
@app.route("/ingest", methods=["POST"])
async def ingest():
    payload = await request.get_json(silent=True) or {}
    urls = payload.get("urls") or []
    if isinstance(urls, str):
        urls = [urls]
    # basic validation: allow only http/https
    valid = []
    for u in urls:
        try:
            p = urlparse(u)
            if p.scheme in ("http", "https"):
                valid.append(u)
        except Exception:
            continue
    if not valid:
        return jsonify({"error": "no valid urls provided"}), 400
    # run blocking ingestion in thread
    n = await asyncio.to_thread(semantic.ingest_urls, valid)
    return jsonify({"indexed_chunks": n, "urls": valid})


@app.route("/poi-discover", methods=["POST"])
async def poi_discover():
    payload = await request.get_json(silent=True) or {}
    city = payload.get("city") or payload.get("location") or ""
    if not city:
        return jsonify({"error": "city required"}), 400
    # discover via orchestrated providers (OSM + Places) - run in thread
    try:
        timeout_val = float(payload.get("timeout", 12.0)) if payload.get("timeout") else 12.0
        # Prefer async provider if available
        try:
            candidates = await asyncio.wait_for(
                multi_provider.async_discover_restaurants(
                    city,
                    cuisine=None,
                    limit=200,
                    local_only=bool(payload.get("local_only", False)),
                    timeout=timeout_val,
                    session=aiohttp_session,
                ),
                timeout=timeout_val + 2,
            )
        except AttributeError:
            # Fallback to sync provider run in thread
            candidates = await asyncio.to_thread(
                multi_provider.discover_restaurants,
                city,
                limit=200,
                local_only=bool(payload.get("local_only", False)),
                timeout=timeout_val,
            )
    except Exception as e:
        return jsonify({"error": "discover_failed", "details": str(e)}), 500
    return jsonify({"count": len(candidates), "candidates": candidates})


@app.route("/claude-search", methods=["POST"])
async def claude_search():
    """Backend endpoint for Claude AI assistant via Puter.js"""
    payload = await request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    city = payload.get("city")
    neighborhood = payload.get("neighborhood")
    category = payload.get("category")
    venues = payload.get("venues", [])

    if not text:
        return jsonify({"error": "text required"}), 400

    try:
        # Build context for Claude
        context = []
        if city:
            context.append(f"Current city: {city}")
        if neighborhood:
            context.append(f"Current neighborhood: {neighborhood}")
        if category:
            context.append(f"Current category: {category}")
        if venues and len(venues) > 0:
            venue_names = [v.get("name", "") for v in venues[:3] if v.get("name")]
            if venue_names:
                context.append(f"Nearby venues: {', '.join(venue_names)}")

        prompt = f"{' '.join(context)}. User question: {text}" if context else text

        # Use Puter.js via JavaScript execution
        # This is a simple approach - in production you might want to use a more robust method
        # like a headless browser or a dedicated Puter API wrapper

        # For now, we'll simulate the response structure that Puter.js would return
        # In a real implementation, you would use a proper JavaScript execution environment

        # Simulated Claude response (replace with actual Puter.js call in production)
        simulated_response = f"Claude AI response: {prompt} - This is a simulated response from the backend integration."

        return jsonify({
            "response": simulated_response,
            "model": "claude-sonnet-4-5",
            "success": True
        })

    except Exception as e:
        return jsonify({
            "error": f"Claude backend failed: {str(e)}",
            "success": False
        }), 500


@app.route("/synthesize", methods=["POST"])
async def synthesize_route():
    """Synthesize search results using Groq (Marco). Accepts either a precomputed `search_result` in the body
    or the same payload that `/search` accepts and will run `_search_impl` to compute it.
    """
    payload = await request.get_json(silent=True) or {}

    # Accept `search_result` directly (preferred for deterministic testability)
    if "search_result" in payload:
        search_result = payload.get("search_result") or {}
    else:
        # Compute search result synchronously in a thread to avoid blocking the event loop
        search_result = await asyncio.to_thread(_search_impl, payload or {})

    # client = synthesis.SynthesisClient()
    # Run synthesis in a thread (synchronous client)
    # items, warnings = await asyncio.to_thread(client.synthesize, search_result)
    items, warnings = [], []  # Dummy for now

    return jsonify({
        "synthesized_venues": items,
        "warnings": warnings,
        "search_preview": {
            "venues_count": len(search_result.get("venues", [])),
            "debug_info": search_result.get("debug_info"),
        },
    })


@app.route("/convert", methods=["POST"])
async def convert_currency():
    payload = await request.get_json(silent=True) or {}
    amount = float(payload.get("amount", 0))
    from_curr = payload.get("from", "USD")
    to_curr = payload.get("to", "EUR")
    try:
        result = semantic.convert_currency(amount, from_curr, to_curr)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/marco-test", methods=["POST"])
async def marco_test():
    """Simple test endpoint for Marco conversation optimization.
    
    Accepts:
    - q: User query string
    - city: City name (optional)
    - venues: List of venue dicts (optional)
    - history: Conversation history string (optional)
    - weather: Weather data dict (optional)
    
    Returns:
    - answer: Marco's response
    - debug: Debug info about the prompt
    """
    import asyncio
    
    payload = await request.get_json(silent=True) or {}
    q = (payload.get("q") or "").strip()
    city = (payload.get("city") or "").strip()
    venues = payload.get("venues", [])
    history = payload.get("history", "")
    weather = payload.get("weather")
    
    if not q:
        return jsonify({"error": "Query 'q' is required"}), 400
    
    # Build conversation prompt
    messages = semantic.create_conversation_prompt(q, city, venues, weather, history)
    
    # Get API key
    key = os.getenv("GROQ_API_KEY")
    if not key:
        # Return a simple response without API call
        simple_response = f"I understand you're asking about '{q}' in {city or 'this area'}. "
        if venues:
            simple_response += create_simple_venue_response(venues, q)
        else:
            simple_response += "Try searching for specific venues first, and I can give you detailed recommendations!"
        return jsonify({
            "answer": simple_response,
            "debug": {
                "mode": "no_api_key",
                "query": q,
                "city": city,
                "venues_count": len(venues)
            }
        })
    
    # Call Groq API
    try:
        async with aiohttp_session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": messages,
                "max_tokens": 400,
                "temperature": 0.7,
            },
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                return jsonify({
                    "error": f"Groq API error: {response.status}",
                    "details": error_text
                }), 500
            
            data = await response.json()
            answer = data["choices"][0]["message"]["content"]
            
            return jsonify({
                "answer": answer.strip(),
                "debug": {
                    "mode": "groq",
                    "query": q,
                    "city": city,
                    "venues_count": len(venues),
                    "history_length": len(history),
                    "is_followup": semantic.ConversationMemory(history).should_reference_previous()
                }
            })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "answer": f"I encountered an issue answering about '{q}'. Please try again!"
        }), 500


def create_simple_venue_response(venues, query):
    """Create a simple response when no API key is available."""
    if not venues:
        return ""
    
    q_lower = query.lower()
    is_coffee = any(kw in q_lower for kw in ['coffee', 'cafe', 'espresso'])
    is_food = any(kw in q_lower for kw in ['food', 'restaurant', 'eat', 'dining'])
    is_dark = any(kw in q_lower for kw in ['dark', 'black', 'strong', 'bold'])
    
    recommendations = []
    for v in venues[:3]:
        name = v.get('name', 'Local spot')
        v_type = v.get('type', v.get('amenity', 'venue')).title()
        cuisine = v.get('cuisine') or v.get('tags', {}).get('cuisine', '')
        
        if cuisine:
            recommendations.append(f"• **{name}** ({cuisine} {v_type})")
        else:
            recommendations.append(f"• **{name}** ({v_type})")
    
    if recommendations:
        rec_text = "\n".join(recommendations)
        if is_coffee and is_dark:
            return f"\n\nBased on your interest in dark roast, here are my top picks:\n{rec_text}\n\nWould you like more details on any of these?"
        elif is_food:
            return f"\n\nHere are my top food recommendations:\n{rec_text}\n\nWhat sounds good to you?"
        else:
            return f"\n\nHere are some great spots:\n{rec_text}\n\nWould you like to know more about any of these?"
    
    return ""


@app.route("/version", methods=["GET"])
def version():
    """Return deployed commit and presence of key environment variables for debugging."""
    import subprocess, os

    commit = None
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=os.path.dirname(__file__)
            )
            .decode()
            .strip()
        )
    except Exception:
        commit = os.getenv("GIT_COMMIT") or "unknown"

    env_flags = {
        "OPENTRIPMAP_KEY_set": bool(os.getenv("OPENTRIPMAP_KEY")),
        "GROQ_API_KEY_set": bool(os.getenv("GROQ_API_KEY")),
        "SEARX_INSTANCES_set": bool(os.getenv("SEARX_INSTANCES")),
    }
    return jsonify({"commit": commit, "env": env_flags})


@app.route("/search_status/<search_id>", methods=["GET"])
def search_status(search_id):
    if search_id in active_searches:
        data = active_searches[search_id]
        return jsonify(data)
    return jsonify({"error": "Search not found"}), 404


@app.route("/tools/currency", methods=["GET"])
def tools_currency():
    # Optional city param to auto-detect local currency
    city = request.args.get("city")
    initial_currency = None
    initial_country = None
    if city:
        try:
            country = get_country_for_city(city)
            initial_country = country
            if country:
                cur = get_currency_for_country(country)
                initial_currency = cur
        except Exception:
            initial_currency = None
    initial_currency_name = None
    try:
        if initial_currency:
            initial_currency_name = get_currency_name(initial_currency)
    except Exception:
        initial_currency_name = None
    # Basic ATM tips (server-side) — short list
    atm_tips = [
        "Use bank-branded ATMs when possible — independent ATMs often charge higher fees.",
        "Check the fee and exchange rate shown on the ATM before accepting the transaction.",
        "Avoid ATMs in poorly lit or isolated areas, and prefer those inside banks or malls.",
        "For small purchases, consider using a card at shops to avoid ATM fees.",
    ]
    # Country-specific payment acceptance notes
    payment_notes_map = {
        "Cuba": [
            "Card acceptance in Cuba is limited; many places are cash-only.",
            "US bank cards and services like Zelle will not currently work — carry sufficient cash and local-denominated notes.",
            "Exchange currency at official casas de cambio or banks; avoid airport exchange desks with poor rates.",
        ],
        "Portugal": [
            "Some independent ATMs (Euronet) charge high fees and offer poor exchange rates.",
            "Prefer withdrawing from bank-branded ATMs to avoid dynamic fees.",
            "Check with your bank about international ATM fees and set a daily withdrawal limit accordingly.",
        ],
        "default": [
            "Check with your bank whether your card will work abroad and notify them before travel.",
            "Carry a small amount of local cash for markets/taxis where cards may not be accepted.",
            "Avoid dynamic currency conversion prompts on ATMs and receipts — choose local currency to get a fairer rate.",
        ],
    }
    # Expand with more country-specific notes
    payment_notes_map.update(
        {
            "Russia": [
                "Card networks and international payment services may be restricted; cash is often preferred.",
                "ATMs may charge higher fees; use bank-branded ATMs where possible.",
            ],
            "Venezuela": [
                "Severe cash and currency controls exist; exchange markets can be informal and risky.",
                "Use official exchange points where possible and avoid street exchangers.",
            ],
            "Myanmar": [
                "Card acceptance is limited outside major hotels; cash is necessary in many places.",
                "Carry small denominations and be aware of potential counterfeit notes.",
            ],
            "Nicaragua": [
                "US dollar cash is commonly accepted in tourist areas but local Córdoba is used widely; have both if possible.",
                "ATMs can be scarce outside cities.",
            ],
            "Kenya": [
                "Mobile money (M-Pesa) is widely used — many vendors accept it instead of cards.",
                "ATMs are available in cities; carry small cash in rural areas.",
            ],
            "Zimbabwe": [
                "Currency situation can be complex; cash and mobile payments may vary—check local guidance.",
                "Carry multiple payment methods if possible.",
            ],
            "Peru": [
                "Major cards are accepted in Lima and tourist areas; smaller towns may be cash-only.",
                "Avoid withdrawing large sums at once; prefer bank ATMs.",
            ],
        }
    )
    initial_payment_notes = None
    try:
        if initial_country:
            # prefer exact match, else default
            notes = (
                payment_notes_map.get(initial_country)
                or payment_notes_map.get(initial_country.split(",")[0])
                or payment_notes_map.get("default")
            )
        else:
            notes = payment_notes_map.get("default")
        initial_payment_notes = notes
    except Exception:
        initial_payment_notes = payment_notes_map.get("default")
    # Attempt to fetch average local prices (Teleport) for initial display
    try:
        initial_costs = get_cost_estimates(city) if city else []
    except Exception:
        initial_costs = []
    return render_template(
        "convert.html",
        initial_currency=initial_currency,
        initial_currency_name=initial_currency_name,
        initial_country=initial_country,
        initial_atm_tips=atm_tips,
        initial_payment_notes=initial_payment_notes,
        initial_costs=initial_costs,
    )


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
