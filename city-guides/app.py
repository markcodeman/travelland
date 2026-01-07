
from flask import Flask, render_template, request, jsonify
import json
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
import logging
import requests

_here = os.path.dirname(__file__)
# load local .env placed inside the city-guides folder (keeps keys out of repo root)
load_dotenv(dotenv_path=os.path.join(_here, '.env'))

import semantic
import overpass_provider
from overpass_provider import _singularize
import multi_provider

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder='static', template_folder='templates')

# Expose whether Groq API key is configured to templates
@app.context_processor
def inject_feature_flags():
    return {
        'GROQ_ENABLED': bool(os.getenv('GROQ_API_KEY'))
    }
def geocode_city(city):
    """Geocode a city name to (lat, lon) using Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city, "format": "json", "limit": 1}
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": "city-guides-app"}, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"Geocoding failed: {e}")
    return None, None

@app.route('/weather', methods=['POST'])
def weather():
    payload = request.json or {}
    city = (payload.get('city') or '').strip()
    lat = payload.get('lat')
    lon = payload.get('lon')
    if not (lat and lon):
        if not city:
            return jsonify({'error': 'city or lat/lon required'}), 400
        lat, lon = geocode_city(city)
        if not (lat and lon):
            return jsonify({'error': 'geocode_failed'}), 400
    try:
        # Open-Meteo API: https://open-meteo.com/en/docs
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "temperature_unit": "celsius",
            "windspeed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto"
        }
        resp = requests.get(url, params=params, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        weather = data.get("current_weather", {})
        return jsonify({
            "lat": lat,
            "lon": lon,
            "city": city,
            "weather": weather
        })
    except Exception as e:
        print(f"Weather fetch failed: {e}")
        return jsonify({'error': 'weather_fetch_failed', 'details': str(e)}), 500


def _compute_open_now(lat, lon, opening_hours_str):
    logging.debug(f"Computing open status for lat={lat}, lon={lon}, opening_hours_str='{opening_hours_str}'")
    """Best-effort server-side opening_hours check.
    - Tries to resolve timezone from lat/lon using timezonefinder if available.
    - Supports simple OSM opening_hours patterns like '24/7' and 'Mo-Sa 09:00-18:00'; Su 10:00-16:00'.
    Returns (is_open: bool|None, next_change_iso: str|None)
    """
    if not opening_hours_str:
        logging.debug("No opening_hours_str provided. Returning (None, None).")
        return (None, None)

    s = opening_hours_str.strip()
    if not s:
        logging.debug("Empty opening_hours_str. Returning (None, None).")
        return (None, None)

    # Quick common check
    if '24/7' in s or '24h' in s or '24 hr' in s.lower():
        logging.debug("Detected 24/7 hours. Returning (True, None).")
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
    # explicit override via FLASK_TZ (useful on hosts like Render that run in UTC).
    if not tzname:
        tz_env = os.getenv('FLASK_TZ') or os.getenv('DEFAULT_TZ')
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

    logging.debug(f"Parsed timezone: {tzname}")
    logging.debug(f"Current datetime: {now}")

    # Map short day names to weekday numbers
    days_map = {'mo':0,'tu':1,'we':2,'th':3,'fr':4,'sa':5,'su':6}

    # Split alternatives by ';'
    parts = [p.strip() for p in s.split(';') if p.strip()]

    def parse_time(tstr):
        try:
            hh, mm = tstr.split(':')
            return time(int(hh), int(mm))
        except Exception:
            return None

    todays_matches = []
    for p in parts:
        # Example: 'Mo-Sa 09:00-18:00' or 'Su 10:00-16:00' or '09:00-18:00'
        tok = p.split()
        if len(tok) == 1 and '-' in tok[0] and ':' in tok[0]:
            # time only, applies every day
            days = list(range(0,7))
            times = tok[0]
        elif len(tok) >= 2:
            daypart = tok[0]
            times = tok[1]
            days = []
            if '-' in daypart:
                a,b = daypart.split('-')
                a = a.lower()[:2]
                b = b.lower()[:2]
                if a in days_map and b in days_map:
                    ra = days_map[a]
                    rb = days_map[b]
                    if ra <= rb:
                        days = list(range(ra, rb+1))
                    else:
                        days = list(range(ra,7)) + list(range(0,rb+1))
            else:
                # single day or comma-separated
                for d in daypart.split(','):
                    d = d.strip().lower()[:2]
                    if d in days_map:
                        days.append(days_map[d])
        else:
            continue

        if isinstance(times, str) and '-' in times:
            t1s,t2s = times.split('-',1)
            t1 = parse_time(t1s)
            t2 = parse_time(t2s)
            if t1 and t2:
                if now.weekday() in days:
                    todays_matches.append((t1, t2))

    logging.debug(f"Today's matches: {todays_matches}")

    # Check if current time falls in any range
    for (t1, t2) in todays_matches:
        logging.debug(f"Checking time range: {t1} - {t2}")
        dt = now.time()
        if t1 <= dt <= t2:
            logging.debug("Current time falls within range. Returning (True, None).")
            return (True, None)
        # Handle overnight ranges (e.g., 18:00-02:00)
        elif t1 > t2:
            # range spans midnight
            if dt >= t1 or dt <= t2:
                logging.debug("Current time falls within overnight range. Returning (True, None).")
                return (True, None)

    logging.debug("No matching time range found. Returning (False, None).")
    return (False, None)


def _humanize_opening_hours(opening_hours_str):
    """Return a user-friendly hours string in 12-hour format if possible."""
    if not opening_hours_str:
        return None
    import re
    from datetime import time

    def fmt(tstr):
        try:
            hh, mm = tstr.split(':')
            t = time(int(hh), int(mm))
            return t.strftime('%I:%M %p').lstrip('0').replace(' 0', ' ')
        except Exception:
            return tstr

    pretty_parts = []
    for part in opening_hours_str.split(';'):
        part = part.strip()
        if not part:
            continue
        # replace ranges like 10:00-22:30 with 10:00 AM–10:30 PM
        part = re.sub(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})',
                      lambda m: f"{fmt(m.group(1))}–{fmt(m.group(2))}",
                      part)
        pretty_parts.append(part)
    return '; '.join(pretty_parts) if pretty_parts else None

@app.route('/')
def index():
    phone = "tel:+1-757-755-7505"  # Replace with dynamic value if needed
    return render_template('index.html', phone=phone)

@app.route('/transport')
def transport():
    city = request.args.get('city', 'the city')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    return render_template('transport.html', city=city, lat=lat, lon=lon)

@app.route('/search', methods=['POST'])
def search():
    payload = request.json or {}
    city = (payload.get('city') or '').strip()
    user_lat = payload.get('user_lat')
    user_lon = payload.get('user_lon')
    budget = (payload.get('budget') or '').strip().lower()
    q = (payload.get('q') or '').strip().lower()
    local_only = payload.get('localOnly', False)
    
    print(f"SEARCH REQUEST: city='{city}', q='{q}', budget='{budget}', local_only={local_only}")

    # normalized singular form of query for plural handling
    try:
        q_norm = overpass_provider._singularize(q)
    except Exception:
        q_norm = q

    results = []
    if city:
        try:
            # Orchestrate providers (OSM, OpenTripMap) and merge results
            cuisine_param = q_norm if q_norm else None
            pois = multi_provider.discover_restaurants(city, cuisine=cuisine_param or '', limit=200, local_only=local_only)
            
            # Apply optional substring filtering only when we didn't pass a cuisine hint
            matched_pois = []
            for poi in pois:
                # If we passed the query through to the provider as a cuisine/name hint,
                # the provider already applied name/tag matching. Only apply the extra
                # substring filter when we didn't pass a cuisine hint.
                if q and not cuisine_param:
                    combined = ' '.join([str(poi.get(k,'')) for k in ('name','tags')]).lower()
                    # match either the raw query or a normalized singular form
                    try:
                        q_sing = overpass_provider._singularize(q)
                    except Exception:
                        q_sing = q
                    if (q not in combined) and (q_sing not in combined):
                        continue
                matched_pois.append(poi)

            # Now map matched_pois to venues
            for poi in matched_pois:
                amenity = poi.get('amenity', '')
                v_budget = poi.get('budget')
                price_range = poi.get('price_range')
                
                if not v_budget:
                    v_budget = 'mid'
                    price_range = '$$'
                    # heuristic for OSM
                    tags_lower = poi.get('tags','').lower()
                    if amenity in ['fast_food', 'cafe', 'food_court'] or 'cuisine=fast_food' in tags_lower or 'cost=cheap' in tags_lower:
                        v_budget = 'cheap'
                        price_range = '$'

                if budget and budget != 'any' and v_budget != budget:
                    continue

                # Use provided description if available, else derive from tags
                desc = poi.get('description')
                tags_str = poi.get('tags', '').lower()
                if not desc:
                    tags_dict = dict(tag.split('=', 1) for tag in poi.get('tags', '').split(', ') if '=' in tag)
                    cuisine = tags_dict.get('cuisine', '').replace(';', ', ')
                    brand = tags_dict.get('brand', '')

                    features = []
                    if 'outdoor_seating=yes' in tags_str: features.append("outdoor seating")
                    if 'wheelchair=yes' in tags_str: features.append("accessible")
                    if 'takeaway=yes' in tags_str: features.append("takeaway available")
                    if 'delivery=yes' in tags_str: features.append("delivery")
                    if 'opening_hours' in tags_dict: features.append("listed hours")
                    
                    feature_text = f" with {', '.join(features)}" if features else ""
                    hours = tags_dict.get('opening_hours', '').strip()
                    if not hours:
                        hours = None

                    if cuisine:
                        desc = f"{cuisine.title()} restaurant{feature_text}"
                        if brand:
                            desc = f"{brand} - {desc}"
                    else:
                        desc = f"Restaurant ({amenity}){feature_text}" if amenity else f"Local venue{feature_text}"
                        if brand:
                            desc = f"{brand} - {desc}"
                    
                    # Ensure hours are valid before displaying
                    hours = tags_dict.get('opening_hours', '').strip()
                    if hours:
                        pretty_hours = _humanize_opening_hours(hours) or hours
                        desc += f". Hours: {pretty_hours}"
                    else:
                        logging.debug("No valid hours found. Skipping hours display.")

                address = poi.get('address', '').strip()
                if not address:
                    address = None

                # Extract phone and rating if available from tags or other providers
                tags_dict = dict(tag.split('=', 1) for tag in poi.get('tags', '').split(', ') if '=' in tag)
                phone = tags_dict.get('phone') or tags_dict.get('contact:phone')
                if phone:
                    phone = f"tel:{phone}"
                rating = poi.get('rating')
                hours = tags_dict.get('opening_hours') or tags_dict.get('hours') or ''
                pretty_hours = _humanize_opening_hours(hours) if hours else None
                try:
                    is_open, next_change = _compute_open_now(poi.get('lat'), poi.get('lon'), hours)
                except Exception:
                    is_open, next_change = (None, None)

                venue = {
                    'id': poi.get('osm_id', poi.get('id', '')),
                    'city': city,
                    'name': poi.get('name', 'Unknown'),
                    'budget': v_budget,
                    'price_range': price_range,
                    'description': desc,
                    'tags': poi.get('tags', ''),
                    'address': address,
                    'latitude': poi.get('lat', 0),
                    'longitude': poi.get('lon', 0),
                    'website': poi.get('website', ''),
                    'osm_url': poi.get('osm_url', ''),
                    'amenity': amenity,
                    'provider': poi.get('provider', 'osm'),
                    'phone': phone,
                    'rating': rating,
                    'opening_hours': hours,
                    'opening_hours_pretty': pretty_hours,
                    'open_now': is_open,
                    'next_change': next_change
                }
                results.append(venue)
        except Exception as e:
            print(f"Error fetching real-time data: {e}")

    print(f"SEARCH RESULTS: found {len(results)} venues")
    # If the client provided a lat/lon (from Nominatim selection), sort by distance
    try:
        if user_lat and user_lon and results:
            def haversine_km(lat1, lon1, lat2, lon2):
                from math import radians, sin, cos, asin, sqrt
                lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
                dlat = radians(lat2 - lat1)
                dlon = radians(lon2 - lon1)
                a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a))
                return 6371.0 * c

            for v in results:
                try:
                    v['distance_km'] = round(haversine_km(user_lat, user_lon, v.get('latitude', 0), v.get('longitude', 0)), 2)
                except Exception:
                    v['distance_km'] = None
            results.sort(key=lambda x: x.get('distance_km') if x.get('distance_km') is not None else 1e9)
    except Exception:
        pass
    return jsonify({'count': len(results), 'venues': results})


@app.route('/ingest', methods=['POST'])
def ingest():
    payload = request.json or {}
    urls = payload.get('urls') or []
    if isinstance(urls, str):
        urls = [urls]
    # basic validation: allow only http/https
    valid = []
    for u in urls:
        try:
            p = urlparse(u)
            if p.scheme in ('http', 'https'):
                valid.append(u)
        except Exception:
            continue
    if not valid:
        return jsonify({'error': 'no valid urls provided'}), 400
    n = semantic.ingest_urls(valid)
    return jsonify({'indexed_chunks': n, 'urls': valid})



@app.route('/poi-discover', methods=['POST'])
def poi_discover():
    payload = request.json or {}
    city = payload.get('city') or payload.get('location') or ''
    if not city:
        return jsonify({'error': 'city required'}), 400
    # discover via orchestrated providers (OSM + Places)
    try:
        candidates = multi_provider.discover_restaurants(city, limit=200)
    except Exception as e:
        return jsonify({'error': 'discover_failed', 'details': str(e)}), 500
    return jsonify({'count': len(candidates), 'candidates': candidates})

@app.route('/semantic-search', methods=['POST'])
def ai_reason():
    print("AI REASON ROUTE CALLED")
    payload = request.json or {}
    q = payload.get('q', '').strip()
    city = payload.get('city', '').strip()  # optional
    mode = payload.get('mode', 'explorer')  # default to explorer
    venues = payload.get('venues', [])      #venues from UI context
    if not q:
        return jsonify({'error': 'query required'}), 400
    weather = payload.get('weather')
    try:
        answer = semantic.search_and_reason(q, city if city else None, mode, context_venues=venues, weather=weather)
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/convert', methods=['POST'])
def convert_currency():
    payload = request.json or {}
    amount = float(payload.get('amount', 0))
    from_curr = payload.get('from', 'USD')
    to_curr = payload.get('to', 'EUR')
    try:
        result = semantic.convert_currency(amount, from_curr, to_curr)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/version', methods=['GET'])
def version():
    """Return deployed commit and presence of key environment variables for debugging."""
    import subprocess, os
    commit = None
    try:
        commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=os.path.dirname(__file__)).decode().strip()
    except Exception:
        commit = os.getenv('GIT_COMMIT') or 'unknown'

    env_flags = {
        'OPENTRIPMAP_KEY_set': bool(os.getenv('OPENTRIPMAP_KEY')),
        'GROQ_API_KEY_set': bool(os.getenv('GROQ_API_KEY')),
        'SEARX_INSTANCES_set': bool(os.getenv('SEARX_INSTANCES'))
    }
    return jsonify({'commit': commit, 'env': env_flags})


@app.route('/tools/currency', methods=['GET'])
def tools_currency():
    return render_template('convert.html')

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    app.run(host="0.0.0.0", port=port)
