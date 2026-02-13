"""
Guide routes module - Neighborhood and location guide endpoints
Extracted from app.py for modular organization
"""

import sys
from pathlib import Path
import os
import asyncio
import json
import hashlib
import re
import time
from typing import Callable, Awaitable, Any

from quart import Blueprint, request, jsonify, current_app as app
import aiohttp
from aiohttp import ClientTimeout

# Import missing dependencies
from city_guides.src.neighborhood_disambiguator import NeighborhoodDisambiguator
from city_guides.providers.ddgs_provider import ddgs_search

# Configuration constants
CACHE_TTL_SEARCH = int(os.getenv("CACHE_TTL_SEARCH", "1800"))  # 30 minutes
PREWARM_TTL = CACHE_TTL_SEARCH
DISABLE_PREWARM = os.getenv("DISABLE_PREWARM", "").lower() in ("1", "true", "yes")
POPULAR_CITIES = os.getenv("POPULAR_CITIES", "").split(",") if os.getenv("POPULAR_CITIES") else []

# Blueprint creation
guide = Blueprint('guide', __name__)

def register(app):
    """Register the guide blueprint with the app"""
    app.register_blueprint(guide)

# --- Route Handlers ---

@guide.route("/api/neighborhoods", methods=["GET"])
async def get_neighborhoods():
    """Get neighborhoods for a city or location.
    Query params: city, lat, lon, lang
    Returns: { cached: bool, neighborhoods: [] }
    """
    from city_guides.providers import multi_provider
    from city_guides.providers.geocoding import geocode_city
    from city_guides.src.persistence import ensure_bbox
    from city_guides.src.app import aiohttp_session, redis_client
    
    CACHE_TTL_NEIGHBORHOOD = int(os.getenv("CACHE_TTL_NEIGHBORHOOD", "3600"))
    
    city = request.args.get("city")
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    lang = request.args.get("lang", "en")

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

    if lat and lon:
        slug = f"{lat}_{lon}"
    else:
        return jsonify({"error": "city or lat/lon required"}), 400

    cache_key = f"neighborhoods:{slug}:{lang}"

    if redis_client:
        try:
            raw = await redis_client.get(cache_key)
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list) and len(parsed) == 0:
                        app.logger.debug("Empty cached neighborhoods for %s; treating as miss", cache_key)
                    else:
                        parsed = [ensure_bbox(n) for n in parsed]
                        return jsonify({"cached": True, "neighborhoods": parsed})
                except Exception:
                    app.logger.debug("Failed to parse cached neighborhoods for %s; refetching", cache_key)
        except Exception:
            app.logger.exception("redis get failed for neighborhoods")

    try:
        data = await asyncio.wait_for(
            multi_provider.async_get_neighborhoods(
                city=city or None,
                lat=float(lat) if lat else None,
                lon=float(lon) if lon else None,
                lang=lang,
                session=aiohttp_session,
            ),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        app.logger.warning(f"Neighborhoods fetch timeout for {city or lat+','+lon}")
        data = []
    except Exception:
        app.logger.exception("neighborhoods fetch failed")
        data = []

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

    if redis_client:
        try:
            await redis_client.set(cache_key, json.dumps(data), ex=CACHE_TTL_NEIGHBORHOOD)
        except Exception:
            app.logger.exception("redis set failed for neighborhoods")

    data = [ensure_bbox(n) for n in data]

    return jsonify({"cached": False, "neighborhoods": data})

@guide.route('/api/reverse_lookup', methods=['POST'])
async def reverse_lookup():
    """Reverse lookup coordinates to structured location info.
    POST payload: { lat: number, lon: number }
    Returns: { display_name, countryName, countryCode, stateName, cityName, neighborhoods: [] }
    """
    from city_guides.providers import multi_provider
    from city_guides.src.app import aiohttp_session
    
    payload = await request.get_json(silent=True) or {}
    lat = payload.get('lat')
    lon = payload.get('lon')
    if lat is None or lon is None:
        return jsonify({'error': 'lat and lon required'}), 400

    debug_flag = (request.args.get('debug') == '1') or bool(payload.get('debug'))

    addr = None
    country_code = None
    country_name = state_name = city_name = None
    raw_geoapify = None
    raw_nominatim = None

    geoapify_reverse_geocode_raw = None
    async_reverse_geocode = None
    try:
        import importlib
        mod = importlib.import_module('city_guides.providers.overpass_provider')
        geoapify_reverse_geocode_raw = getattr(mod, 'geoapify_reverse_geocode_raw', None)
        async_reverse_geocode = getattr(mod, 'async_reverse_geocode', None)
        if geoapify_reverse_geocode_raw and callable(geoapify_reverse_geocode_raw):
            result = geoapify_reverse_geocode_raw(float(lat), float(lon), session=aiohttp_session)
            if asyncio.iscoroutine(result):
                props = await result
            else:
                props = result
            if props and isinstance(props, dict):
                raw_geoapify = props
                app.logger.debug('geoapify_reverse_geocode_raw returned properties: %s', {k: props.get(k) for k in ['country_code','country','state','city']})
                addr = props.get('formatted') or props.get('address_line') or ''
                cc = props.get('country_code') or props.get('countryCode')
                if cc:
                    country_code = cc.upper()
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

    if not addr:
        try:
            if not callable(async_reverse_geocode):
                import importlib
                mod = importlib.import_module('city_guides.providers.overpass_provider')
                async_reverse_geocode = getattr(mod, 'async_reverse_geocode', None)
            if callable(async_reverse_geocode):
                result = async_reverse_geocode(float(lat), float(lon), session=aiohttp_session)
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

    if not addr and not country_code and not country_name:
        app.logger.warning('reverse_lookup failed to derive any location info for coords %s,%s', lat, lon)
        return jsonify({'error': 'reverse_lookup_failed', 'message': 'Could not determine location from coordinates'}), 502

    nb = []
    try:
        nb = await multi_provider.async_get_neighborhoods(city=None, lat=float(lat), lon=float(lon), lang='en', session=aiohttp_session)
    except Exception:
        app.logger.exception('neighborhoods lookup failed in reverse_lookup')
        nb = []

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

@guide.route('/api/smart-neighborhoods', methods=['GET'])
async def api_smart_neighborhoods():
    """
    Get smart neighborhood suggestions for ANY city.
    First checks seed files, then falls back to Overpass API.
    Returns top 24 neighborhoods enriched with Wikipedia descriptions.
    Query params: city, category (optional), enrich (optional, default=true)
    Returns: { is_large_city: bool, neighborhoods: [] }
    """
    from city_guides.providers.geocoding import geocode_city
    from city_guides.src.dynamic_neighborhoods import get_neighborhoods_for_city
    from city_guides.src.app import redis_client, aiohttp_session
    
    city = request.args.get('city', '').strip()
    category = request.args.get('category', '').strip()
    enrich = request.args.get('enrich', 'true').lower() != 'false'
    
    if not city:
        return jsonify({'is_large_city': False, 'neighborhoods': []}), 400
    
    try:
        cache_key = f"smart_neighborhoods:{city.lower()}:enriched"
        if redis_client:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                app.logger.info(f"Cache hit for smart neighborhoods: {city}")
                return jsonify(json.loads(cached_data))

        seed_neighborhoods = []
        data_path = Path(__file__).parent.parent.parent / 'data'
        large_city_skip = {'london', 'new york', 'tokyo', 'paris', 'los angeles', 'shanghai', 'beijing', 'rio de janeiro', 'rio de janeiro, brazil'}

        if city.lower().split(',')[0].strip() not in large_city_skip:
            for seed_file in data_path.rglob('*.json'):
                try:
                    with open(seed_file, 'r', encoding='utf-8') as f:
                        seed_data = json.load(f)

                    neighborhoods_data = None
                    if isinstance(seed_data, dict) and 'cities' in seed_data:
                        cities = seed_data.get('cities', {})
                        if isinstance(cities, dict):
                            city_key = next((k for k in cities.keys() if k.lower() == city.lower()), None)
                            if city_key:
                                neighborhoods_data = cities[city_key]
                    elif isinstance(seed_data, dict) and 'city' in seed_data and 'neighborhoods' in seed_data:
                        if seed_data.get('city', '').lower() == city.lower():
                            neighborhoods_data = seed_data.get('neighborhoods', [])

                    if neighborhoods_data and isinstance(neighborhoods_data, list) and len(neighborhoods_data) > 0:
                        first_item = neighborhoods_data[0]
                        if isinstance(first_item, dict) and 'name' in first_item:
                            seed_neighborhoods = neighborhoods_data
                            app.logger.info(f"Found {len(seed_neighborhoods)} neighborhoods in {seed_file.name} for {city}")
                            break
                except Exception as e:
                    app.logger.debug(f"Could not load {seed_file.name} for {city}: {e}")

        if seed_neighborhoods:
            # Filter to top 24 neighborhoods by population/wikipedia presence
            top_neighborhoods = _get_top_neighborhoods(seed_neighborhoods, limit=24)
            
            # Enrich with Wikipedia descriptions if requested
            if enrich:
                top_neighborhoods = await _enrich_neighborhoods_with_descriptions(
                    city, top_neighborhoods, aiohttp_session
                )
            
            response = {
                'is_large_city': True,
                'neighborhoods': top_neighborhoods,
                'city': city,
                'category': category,
                'source': 'seed',
                'total_available': len(seed_neighborhoods)
            }
            if redis_client:
                await redis_client.setex(cache_key, 3600, json.dumps(response))
            return jsonify(response)

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
        
        neighborhoods = await get_neighborhoods_for_city(city, lat, lon)
        
        # Enrich with Wikipedia descriptions if requested
        if enrich and neighborhoods:
            neighborhoods = await _enrich_neighborhoods_with_descriptions(
                city, neighborhoods, aiohttp_session
            )
        
        response = {
            'is_large_city': len(neighborhoods) >= 3,
            'neighborhoods': neighborhoods,
            'city': city,
            'category': category,
            'source': 'overpass'
        }

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


@guide.route('/api/generate_quick_guide', methods=['POST'])
async def generate_quick_guide(skip_cache=False, disable_quality_check=False):
    """Generate a neighborhood quick_guide using Wikipedia and local data-first heuristics.
    POST payload: { city: "City Name", neighborhood: "Neighborhood Name" }
    Returns: { quick_guide: str, source: 'cache'|'wikipedia'|'data-first', cached: bool, source_url?: str }
    """
    payload = await request.get_json(silent=True) or {}
    city = (payload.get('city') or '').strip()
    raw_neighborhood = payload.get('neighborhood') or ''
    neighborhood = raw_neighborhood.strip() if isinstance(raw_neighborhood, str) else ''
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
            # Fall back to synthesized content instead of Wikipedia
            # Use enhanced synthesis with structured content
            from city_guides.src.synthesis_enhancer import SynthesisEnhancer
            structured_content = SynthesisEnhancer.generate_neighborhood_content(neighborhood, city)
            
            resp = {
                'quick_guide': structured_content.get('tagline', ''),
                'tagline': structured_content.get('tagline', ''),
                'fun_fact': structured_content.get('fun_fact', ''),
                'exploration': structured_content.get('exploration', ''),
                'source': 'synthesized',
                'cached': False,
                'source_url': None,
                'confidence': 'low'
            }
            return jsonify(resp)
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
                app.logger.info("About to call SynthesisEnhancer.generate_neighborhood_content for %s/%s", city, neighborhood)
                content_dict = SynthesisEnhancer.generate_neighborhood_content(neighborhood, city)
                synthesized = f"{content_dict.get('tagline', '')} {content_dict.get('fun_fact', '')} {content_dict.get('exploration', '')}".strip()
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
                content_dict = SynthesisEnhancer.generate_neighborhood_content(neighborhood, city)
                out['quick_guide'] = f"{content_dict.get('tagline', '')} {content_dict.get('fun_fact', '')} {content_dict.get('exploration', '')}".strip()
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

    resp = {'quick_guide': out.get('quick_guide', synthesized), 'source': out.get('source', source or 'data-first'), 'confidence': out.get('confidence', confidence), 'cached': False, 'source_url': out.get('source_url', source_url)}
    if mapillary_images:
        resp['mapillary_images'] = mapillary_images
    return jsonify(resp)

async def _persist_quick_guide(data: dict, city: str, neighborhood: str, cache_file: Path):
    """Persist quick guide data to cache file."""
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        app.logger.debug('Persisted quick guide for %s/%s', city, neighborhood)
    except Exception as e:
        app.logger.exception('Failed to persist quick guide: %s', e)


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

def _get_top_neighborhoods(neighborhoods: list, limit: int = 24) -> list:
    """
    Filter to top neighborhoods by significance.
    Prioritizes: population > Wikipedia presence > place type (suburb > neighbourhood)
    """
    def score_neighborhood(n):
        score = 0
        tags = n.get('tags', {})
        
        # Population score (highest weight)
        pop = tags.get('population')
        if pop:
            try:
                score += min(int(pop) / 1000, 1000)  # Cap at 1000 points
            except (ValueError, TypeError):
                pass
        
        # Wikipedia presence bonus
        if tags.get('wikipedia') or tags.get('wikipedia:en'):
            score += 500
        
        # Wikidata presence bonus
        if tags.get('wikidata'):
            score += 200
        
        # Place type preference
        place = tags.get('place', '')
        if place == 'suburb':
            score += 300
        elif place == 'quarter':
            score += 250
        elif place == 'neighbourhood':
            score += 100
        elif place == 'city':
            score += 400
        
        return score
    
    # Sort by score descending
    sorted_neighborhoods = sorted(neighborhoods, key=score_neighborhood, reverse=True)
    
    # Return top N
    return sorted_neighborhoods[:limit]


def _generate_neighborhood_context(name: str, city: str, tags: dict) -> str:
    """Generate travel-relevant neighborhood description from available data."""
    population = tags.get('population', '')
    
    # Population-based descriptors
    pop_desc = ''
    if population:
        try:
            pop = int(population)
            if pop > 200000:
                pop_desc = 'A bustling, densely populated district'
            elif pop > 150000:
                pop_desc = 'A lively residential area'
            elif pop > 100000:
                pop_desc = 'A vibrant neighborhood'
            elif pop > 50000:
                pop_desc = 'A charming mid-sized community'
            else:
                pop_desc = 'A cozy, intimate neighborhood'
        except:
            pass
    
    # Name-based character hints (generalized)
    name_lower = name.lower()
    character_hints = []
    
    # Location-based hints
    if any(word in name_lower for word in ['east', 'eastern', 'higashi']):
        character_hints.append('in the eastern part of the city')
    if any(word in name_lower for word in ['west', 'western', 'nishi']):
        character_hints.append('in the western part of the city')
    if any(word in name_lower for word in ['north', 'northern', 'kita']):
        character_hints.append('in the northern part of the city')
    if any(word in name_lower for word in ['south', 'southern', 'minami']):
        character_hints.append('in the southern part of the city')
    if any(word in name_lower for word in ['central', 'center', 'chuo']):
        character_hints.append('at the heart of the city')
    if any(word in name_lower for word in ['bay', 'harbor', 'port', 'minato']):
        character_hints.append('near the waterfront and port area')
    if any(word in name_lower for word in ['river', 'gawa', 'kawa']):
        character_hints.append('along the river waterfront')
    
    # Feature-based hints from OSM tags
    if tags.get('amenity') == 'university' or 'university' in name_lower:
        character_hints.append('home to universities and student life')
    if tags.get('historic') == 'yes' or 'historic' in name_lower:
        character_hints.append('known for its historical significance')
    if tags.get('tourism') in ['attraction', 'museum'] or any(word in name_lower for word in ['museum', 'gallery', 'temple', 'shrine']):
        character_hints.append('featuring cultural and historical attractions')
    if 'business' in name_lower or tags.get('landuse') == 'commercial':
        character_hints.append('a business and commercial district')
    if 'residential' in name_lower or tags.get('landuse') == 'residential':
        character_hints.append('primarily residential with local amenities')
    if any(word in name_lower for word in ['park', 'garden', 'green']):
        character_hints.append('featuring parks and green spaces')
    if any(word in name_lower for word in ['market', 'shopping', 'mall']):
        character_hints.append('known for shopping and local markets')
    if any(word in name_lower for word in ['nightlife', 'entertainment']):
        character_hints.append('a hub for nightlife and entertainment')
    
    # Build description - combine population and character hints
    parts = []
    if pop_desc:
        parts.append(pop_desc)
    
    if character_hints:
        parts.append(', '.join(character_hints[:2]))  # Limit to 2 hints to keep it concise
    
    if parts:
        return '. '.join(parts) + '.'
    
    # Well-known neighborhood descriptions
    name_lower = name.lower()
    if 'copacabana' in name_lower and 'rio' in city.lower():
        return 'Famous for its four-kilometer beach, Copacabana is one of Rio\'s most iconic neighborhoods, known for its Art Deco architecture, vibrant nightlife, and the famous Copacabana Palace hotel.'
    if 'ipanema' in name_lower and 'rio' in city.lower():
        return 'An upscale beachfront neighborhood known for its beautiful beach, high-end shopping on Rua Garcia d\'Ávila, and as the birthplace of bossa nova music.'
    if 'santa teresa' in name_lower and 'rio' in city.lower():
        return 'A bohemian hillside neighborhood famous for its historic streetcar, colonial architecture, contemporary art galleries, and panoramic views of Rio.'
    if 'lapa' in name_lower and 'rio' in city.lower():
        return 'Rio\'s historic entertainment district, home to the Arcos da Lapa aqueduct, samba clubs, street parties, and the famous Escadaria Selarón.'
    if 'le marais' in name_lower and 'paris' in city.lower():
        return 'A historic district known for its medieval architecture, Jewish heritage, trendy boutiques, galleries, and vibrant LGBTQ+ scene.'
    if 'montmartre' in name_lower and 'paris' in city.lower():
        return 'The artist hill of Paris, home to the Sacré-Cœur Basilica, street artists, cabarets, and the famous Moulin Rouge.'
    if 'saint-germain' in name_lower and 'paris' in city.lower():
        return 'An intellectual and literary district famous for its cafés, bookstores, and association with existentialist philosophers.'
    if 'latin quarter' in name_lower and 'paris' in city.lower():
        return 'Paris\' oldest district, home to the Sorbonne University, historic churches, and a lively student atmosphere.'
    if 'champs-élysées' in name_lower and 'paris' in city.lower():
        return 'Paris\' most famous avenue, lined with luxury shops, theaters, and grand cafés, leading to the Arc de Triomphe.'
    
    # Generic fallbacks based on location patterns
    if any(word in name_lower for word in ['downtown', 'cbd', 'city center', 'centro']):
        return f'A bustling downtown district in {city}, featuring shopping, dining, business, and urban amenities.'
    if any(word in name_lower for word in ['suburb', 'outskirts']):
        return f'A suburban neighborhood in {city}, offering a quieter pace with good access to the city center.'
    if any(word in name_lower for word in ['old town', 'historic', 'colonial']):
        return f'A historic district in {city}, preserving traditional architecture and local culture.'
    if any(word in name_lower for word in ['beach', 'marina', 'waterfront']):
        return f'A waterfront neighborhood in {city}, offering beach access, seafood dining, and coastal atmosphere.'
    
    return f'A neighborhood in {city} with local character and amenities.'


async def _enrich_neighborhoods_with_descriptions(
    city: str, 
    neighborhoods: list, 
    aiohttp_session
) -> list:
    """
    Enrich neighborhoods with travel-relevant descriptions.
    Combines Wikipedia data with OSM metadata for engaging descriptions.
    """
    import aiohttp
    
    async def fetch_wiki_by_title(title: str) -> dict:
        """Fetch Wikipedia summary by exact page title."""
        try:
            if ':' in title:
                title = title.split(':', 1)[1]
            
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
            async with aiohttp_session.get(url, timeout=8) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return None
    
    async def enrich_single(neighborhood):
        name = neighborhood.get('name', '')
        if not name:
            return neighborhood
        
        # Skip if already has a non-generic description
        existing_desc = neighborhood.get('description', '')
        if existing_desc and not existing_desc.startswith('Neighborhood in ') and not existing_desc.startswith('A neighborhood in '):
            return neighborhood
        
        # For well-known neighborhoods, try Wikipedia even without tags
        name_lower = name.lower()
        wiki_title = None
        if 'copacabana' in name_lower and 'rio' in city.lower():
            wiki_title = 'Copacabana, Rio de Janeiro'
        elif 'ipanema' in name_lower and 'rio' in city.lower():
            wiki_title = 'Ipanema'
        elif 'santa teresa' in name_lower and 'rio' in city.lower():
            wiki_title = 'Santa Teresa (Rio de Janeiro)'
        elif 'lapa' in name_lower and 'rio' in city.lower():
            wiki_title = 'Lapa, Rio de Janeiro'
        elif 'leblon' in name_lower and 'rio' in city.lower():
            wiki_title = 'Leblon'
        elif 'le marais' in name_lower and 'paris' in city.lower():
            wiki_title = 'Le Marais'
        elif 'montmartre' in name_lower and 'paris' in city.lower():
            wiki_title = 'Montmartre'
        elif 'saint-germain' in name_lower and 'paris' in city.lower():
            wiki_title = 'Saint-Germain-des-Prés'
        elif 'latin quarter' in name_lower and 'paris' in city.lower():
            wiki_title = 'Latin Quarter, Paris'
        elif 'champs-élysées' in name_lower and 'paris' in city.lower():
            wiki_title = 'Champs-Élysées'
        
        try:
            neighborhood = neighborhood.copy()
            tags = neighborhood.get('tags', {})
            
            # Generate contextual description from OSM data
            context_desc = _generate_neighborhood_context(name, city, tags)
            
            # Try to get Wikipedia data for additional richness
            wiki_data = None
            if wiki_title:
                wiki_data = await fetch_wiki_by_title(wiki_title)
            else:
                wiki_ref = tags.get('wikipedia') or tags.get('wikipedia:en')
                if wiki_ref:
                    wiki_data = await fetch_wiki_by_title(wiki_ref)
            
            # Build final description
            description = context_desc
            
            # If we have wiki data, try to extract interesting facts (not just "is a ward")
            if wiki_data:
                extract = wiki_data.get('extract', '')
                # Look for mentions of attractions, features, or character
                interesting_keywords = [
                    'shrine', 'temple', 'park', 'museum', 'castle', 'tower', 'station',
                    'shopping', 'market', 'district', 'entertainment', 'dining', 'restaurant',
                    'historic', 'traditional', 'modern', 'business', 'residential',
                    'famous', 'popular', 'known', 'home to', 'features'
                ]
                
                # Extract sentences with interesting keywords
                sentences = extract.split('. ')
                interesting_sentences = []
                for sent in sentences[:3]:  # Check first 3 sentences
                    if any(kw in sent.lower() for kw in interesting_keywords):
                        # Skip generic "is a ward" sentences
                        if not any(phrase in sent.lower() for phrase in ['is one of', 'is a ward', 'make up the city']):
                            interesting_sentences.append(sent)
                
                if interesting_sentences:
                    # Use the first interesting sentence
                    interesting_part = interesting_sentences[0][:120]
                    if len(interesting_part) > 20:  # Make sure it's substantial
                        description = f"{context_desc} {interesting_part}."
                
                neighborhood['source'] = 'enriched'
                
                # Add coordinates if available
                coords = wiki_data.get('coordinates')
                if coords:
                    neighborhood['coordinates'] = {
                        'lat': coords.get('lat'),
                        'lon': coords.get('lon')
                    }
            
            neighborhood['description'] = description[:200] if len(description) > 200 else description
            return neighborhood
            
        except Exception as e:
            # Return original on error
            return neighborhood
    
    # Enrich concurrently with semaphore to limit concurrency
    sem = asyncio.Semaphore(5)
    
    async def enrich_with_limit(n):
        async with sem:
            return await enrich_single(n)
    
    tasks = [enrich_with_limit(n) for n in neighborhoods]
    enriched = await asyncio.gather(*tasks)
    
    return list(enriched)


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

