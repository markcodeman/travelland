"""
Location routes for TravelLand API
Handles countries, states, cities, neighborhoods, geocoding, and GeoNames search
"""

import os
import json
import re
from pathlib import Path
from quart import Blueprint, request, jsonify, current_app
from aiohttp import ClientTimeout
from city_guides.providers.geocoding import geocode_city
from city_guides.providers.utils import get_session
from city_guides.providers.overpass_provider import async_get_neighborhoods

locations_bp = Blueprint('locations', __name__)


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


@locations_bp.route('/api/countries')
async def api_countries():
    """Get list of countries for frontend dropdown"""
    try:
        countries = await _get_countries()
        return jsonify(countries)
    except Exception:
        current_app.logger.exception('Failed to get countries')
        return jsonify([])


@locations_bp.route('/api/neighborhoods/<country_code>')
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
        data_path = Path(__file__).parent.parent.parent / 'data' / f'{file_name}.json'
        if data_path.exists():
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data.get('cities', {}))
        return jsonify({})
    except Exception:
        current_app.logger.exception('Failed to load neighborhoods for %s', country_code)
        return jsonify({})


@locations_bp.route('/api/locations/states')
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
        current_app.logger.exception('Failed to fetch states from GeoNames')
        return jsonify([])


@locations_bp.route('/api/locations/cities')
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
            seed_path = Path(__file__).parent.parent.parent / 'data' / 'seeded_cities.json'
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
                current_app.logger.info('Serving %d unique cities from seeded_cities.json fallback', len(cities))
                return jsonify(cities)
        except Exception:
            current_app.logger.exception('Failed to load seeded cities fallback')
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
                    current_app.logger.warning('GeoNames returned status %d for %s/%s; trying seeded fallback', resp.status, country_code, state_code)
                    # try seeded fallback
                    seed_path = Path(__file__).parent.parent.parent / 'data' / 'seeded_cities.json'
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
                    current_app.logger.info('GeoNames returned no cities for %s/%s; falling back to seeded_cities.json', country_code, state_code)
                    seed_path = Path(__file__).parent.parent.parent / 'data' / 'seeded_cities.json'
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
        current_app.logger.exception('Failed to fetch cities from GeoNames')
        return jsonify([])


@locations_bp.route('/api/locations/neighborhoods')
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
        current_app.logger.exception('Failed to fetch neighborhoods')
        return jsonify([])


@locations_bp.route('/api/neighborhoods')
async def api_neighborhoods_query():
    """Get neighborhoods for a city or coordinates"""
    city = request.args.get('city', '').strip()
    lat = request.args.get('lat', '').strip()
    lon = request.args.get('lon', '').strip()
    lang = request.args.get('lang', 'en')
    
    if not city and not (lat and lon):
        return jsonify({'error': 'city or lat/lon required'}), 400
    
    try:
        async with get_session() as session:
            if city:
                neighborhoods = await async_get_neighborhoods(city=city, lang=lang, session=session)
            else:
                # For lat/lon, we need to get city first or handle differently
                # For now, return empty as lat/lon neighborhoods not implemented
                neighborhoods = []
            
            return jsonify({'neighborhoods': neighborhoods})
    except Exception:
        current_app.logger.exception('Failed to fetch neighborhoods')
        return jsonify({'neighborhoods': []})


@locations_bp.route('/api/geocode', methods=['POST'])
async def geocode():
    """Geocode a city/neighborhood to get coordinates"""
    payload = await request.get_json(silent=True) or {}
    raw_city = payload.get('city', '')
    raw_neighborhood = payload.get('neighborhood', '')
    city = raw_city.strip() if isinstance(raw_city, str) else ''
    neighborhood = raw_neighborhood.strip() if isinstance(raw_neighborhood, str) else ''
    
    if not city:
        return jsonify({'error': 'city required'}), 400
    
    try:
        # Resolve alias mappings (e.g., "Osaka North" -> "Kita Ward")
        try:
            aliases_path = Path(__file__).parent.parent.parent / 'data' / 'neighborhood_aliases.json'
            if aliases_path.exists():
                aliases = json.loads(aliases_path.read_text(encoding='utf-8') or '{}')
                city_key = city.split(',')[0].strip().lower()
                alias_key = neighborhood.strip().lower()
                city_aliases = aliases.get(city_key, {})
                if alias_key and city_aliases.get(alias_key):
                    neighborhood = city_aliases.get(alias_key)
        except Exception:
            # Don't fail geocoding on alias file read errors
            current_app.logger.debug('Failed to load neighborhood aliases')

        # Try to geocode city + neighborhood first, then city alone
        query = f"{neighborhood}, {city}" if neighborhood else city

        # Use candidate-aware geocoding to enforce importance thresholds (avoid tiny micro-localities)
        from city_guides.providers.geocoding import geocode_city_candidates

        IMPORTANCE_THRESHOLD = 0.17

        candidates = await geocode_city_candidates(query, limit=5)
        # Pick the first candidate meeting the importance threshold
        best = None
        for c in (candidates or []):
            try:
                if float(c.get('importance', 0) or 0) >= IMPORTANCE_THRESHOLD:
                    best = c
                    break
            except Exception:
                continue

        if best:
            return jsonify({
                'lat': best.get('lat'),
                'lon': best.get('lon'),
                'display_name': best.get('display_name')
            })

        # Fallback: try the legacy single-provider geocode (may return something without importance)
        result = await geocode_city(query)
        if not result:
            return jsonify({'error': 'geocode_failed'}), 400
        return jsonify(result)

    except Exception:
        current_app.logger.exception('Geocoding failed')
        return jsonify({'error': 'geocode_failed'}), 500


@locations_bp.route('/api/geonames-search', methods=['POST'])
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
                env_path = Path(__file__).parent.parent.parent.parent / ".env"
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
            current_app.logger.warning("GeoNames username not configured")
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
                    current_app.logger.error(f"GeoNames API error: {response.status}")
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
                    if re.match(r'^.+\s+\d{2}$', city_name):
                        current_app.logger.debug(f"Skipping postal district: {city_name}")
                        continue
                    
                    # Skip suburbs and small localities - tourists want major cities
                    # PPLX = section of populated place (suburb), PPLQ = abandoned place
                    if feature_code in ["PPLX", "PPLQ", "PPLH"]:
                        current_app.logger.debug(f"Skipping suburb/abandoned place: {city_name} ({feature_code})")
                        continue
                    
                    # Skip Lyon suburbs (communes in Lyon metro area) - tourists want Lyon
                    if country_code == "FR" and city_name in ["Villeurbanne", "Bron", "Vénissieux", "Saint-Priest", "Meyzieu", "Rillieux-la-Pape", "Décines-Charpieu"]:
                        current_app.logger.debug(f"Skipping Lyon suburb: {city_name}")
                        continue
                    
                    # Skip very small places (less than 50,000 people) unless it's a hardcoded destination.
                    # Treat missing/zero population as small and skip them as well.
                    try:
                        pop_val = int(population or 0)
                    except Exception:
                        pop_val = 0
                    if pop_val < 50000:
                        current_app.logger.debug(f"Skipping small place: {city_name} (pop: {population})")
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
        current_app.logger.exception(f'GeoNames search failed: {e}')
        return jsonify({'error': 'geonames_search_failed'}), 500


def register(app):
    """Register locations blueprint with the app"""
    app.register_blueprint(locations_bp)
