"""
Dynamic neighborhood fetcher using Overpass API
No hardcoded lists - works for ANY city globally
"""
import aiohttp
from typing import List, Dict, Optional
import logging
import json
import os
import random
from pathlib import Path

logger = logging.getLogger(__name__)

# Shared Overpass endpoints
overpass_endpoints = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.openstreetmap.fr/api/interpreter'
]

# Simple tag classifier used by multiple helpers
def classify_neighborhood(tags: Dict) -> str:
    place_type = (tags or {}).get('place', '')
    if place_type in ('suburb', 'residential'): return 'residential'
    if place_type in ('neighbourhood', 'neighborhood', 'quarter', 'district', 'city_district'): return 'culture'
    return 'culture'


async def fetch_nearby_tags(session: aiohttp.ClientSession, lat: float, lon: float) -> Dict[str, int]:
    """Fetch nearby POI tags to infer character."""
    nearby_query = f"""
    [out:json][timeout:6];
    (
      node["tourism"](around:600,{lat},{lon});
      node["amenity"~"restaurant|cafe|bar|pub|nightclub|theatre|cinema|marketplace"](around:600,{lat},{lon});
      node["leisure"~"park|garden|sports_centre|stadium"](around:600,{lat},{lon});
      node["natural"~"water|beach|coastline|cliff|wood|forest"](around:600,{lat},{lon});
      node["shop"](around:500,{lat},{lon});
    );
    out tags 20;
    """
    counts = {'attractions': 0, 'food': 0, 'nightlife': 0, 'shopping': 0, 'nature': 0, 'entertainment': 0, 'waterfront': 0}
    try:
        async with session.post(overpass_endpoints[0], data={'data': nearby_query}, timeout=aiohttp.ClientTimeout(total=6)) as resp:
            if resp.status != 200:
                return counts
            data = await resp.json()
            for el in data.get('elements', [])[:25]:
                t = el.get('tags', {})
                tour = t.get('tourism')
                amen = t.get('amenity')
                leis = t.get('leisure')
                nat = t.get('natural')
                shop = t.get('shop')
                if tour in ('attraction', 'museum', 'gallery', 'viewpoint'):
                    counts['attractions'] += 1
                if amen in ('restaurant', 'cafe', 'food_court'):
                    counts['food'] += 1
                if amen in ('bar', 'pub', 'nightclub'):
                    counts['nightlife'] += 1
                if amen in ('theatre', 'cinema'):
                    counts['entertainment'] += 1
                if shop:
                    counts['shopping'] += 1
                if leis in ('park', 'garden', 'sports_centre', 'stadium'):
                    counts['nature'] += 1
                if nat in ('beach', 'coastline', 'cliff', 'water'):
                    counts['waterfront'] += 1
                if nat in ('wood', 'forest'):
                    counts['nature'] += 1
    except Exception:
        return counts
    return counts

# Cache for seed data to avoid repeated file reads
_SEED_DATA_CACHE: Optional[Dict[str, List[Dict]]] = None

# Configuration constants
SEED_DATA_DIR = os.getenv('NEIGHBORHOOD_SEED_DIR', None)  # Allow override via env var
EXCLUDE_FILES = ['cache', 'seeded_cities']  # Files/patterns to exclude from seed data loading
PARTIAL_MATCH_THRESHOLD = 500  # Only do partial matching for caches smaller than this

async def fetch_neighborhoods_dynamic(city: str, lat: float, lon: float, radius: int = 5000) -> List[Dict]:
    """Dynamically fetch neighborhoods for ANY city using Overpass API."""
    if not lat or not lon:
        return []

    search_radius = radius
    overpass_query = f"""
    [out:json][timeout:10];
    (
      node["place"~"neighbourhood|suburb|quarter|district|city_district"](around:{search_radius},{lat},{lon});
      way["place"~"neighbourhood|suburb|quarter|district|city_district"](around:{search_radius},{lat},{lon});
      relation["place"~"neighbourhood|suburb|quarter|district|city_district"](around:{search_radius},{lat},{lon});
    );
    out center tags 60;
    """

    endpoints = overpass_endpoints.copy()
    random.shuffle(endpoints)
    elements: List[Dict] = []

    for endpoint in endpoints:
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "TravelLand/1.0 (contact: team@travelland.local)"}) as session:
                async with session.post(endpoint, data={'data': overpass_query}, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    elements = data.get('elements', [])
                    break
        except Exception as e:
            logger.warning(f"Overpass API {endpoint} failed for {city}: {e}")

    neighborhoods: List[Dict] = []
    seen = set()
    for el in elements[:60]:
        tags = el.get('tags', {})
        name = tags.get('name') or tags.get('alt_name')
        if not name:
            continue
        norm = name.strip().lower()
        if norm in seen:
            continue
        seen.add(norm)
        ntype = classify_neighborhood(tags)
        description = tags.get('description') or f"Neighborhood in {city}"
        lat_c = el.get('lat') or el.get('center', {}).get('lat')
        lon_c = el.get('lon') or el.get('center', {}).get('lon')
        neighborhoods.append({
            'name': name.strip(),
            'description': description,
            'type': ntype,
            'lat': lat_c,
            'lon': lon_c,
            'tags': tags
        })

    return neighborhoods


async def fetch_admin_names_overpass(city: str, relation_id: Optional[int]) -> List[Dict]:
    """Fetch admin/suburb/neighbourhood names using a fast Overpass query against the city relation area."""
    if not relation_id:
        return []
    area_id = 3600000000 + int(relation_id)
    overpass_query = f"""
    [out:json][timeout:2];
    area({area_id})->.searchArea;
    (
      nwr["place"~"neighbourhood|suburb|quarter|borough"](area.searchArea);
      way["admin_level"~"8|9|10"](area.searchArea);
      relation["admin_level"~"8|9|10"](area.searchArea);
    );
    out tags center 30;
    """
    headers = {"User-Agent": "TravelLand/1.0 (contact: team@travelland.local)"}
    endpoints = overpass_endpoints.copy()
    random.shuffle(endpoints)
    endpoint = endpoints[0] if endpoints else None
    if not endpoint:
        return []
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=2)) as session:
            async with session.post(endpoint, data={'data': overpass_query}) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                elements = data.get("elements", [])
                results = []
                for el in elements[:60]:
                    name = el.get("tags", {}).get("name") or el.get("tags", {}).get("alt_name")
                    if not name:
                        continue
                    results.append({
                        "name": name.strip(),
                        "description": name.strip(),
                        "type": classify_neighborhood(el.get("tags", {})),
                    })
                return results[:30]
    except Exception:
        return []
    
    # Adjust radius based on city size (smaller radius = faster query)
    # Use 5km default, but can be overridden
    search_radius = radius
    
    city_key = city.lower().split(',')[0].strip()
    relation_id = CITY_RELATIONS.get(city_key)
    if relation_id:
        area_id = 3600000000 + int(relation_id)
        overpass_query = f"""
        [out:json][timeout:15];
        area({area_id})->.searchArea;
        (
          relation["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.searchArea);
          way["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.searchArea);
          node["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.searchArea);
          relation["admin_level"~"8|9"]["boundary"="administrative"](area.searchArea);
        );
        out center tags 80;
        """
    else:
        overpass_query = f"""
        [out:json][timeout:15];
        (
          relation["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](around:{search_radius},{lat},{lon});
          way["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](around:{search_radius},{lat},{lon});
          node["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](around:{search_radius},{lat},{lon});
        );
        out center tags 50;
        """
    
    # Try multiple Overpass API endpoints for better reliability (shuffled per request)
    overpass_endpoints = [
        'https://overpass-api.de/api/interpreter',
        'https://overpass.kumi.systems/api/interpreter',
        'https://overpass.openstreetmap.fr/api/interpreter'
    ]


def load_seed_neighborhoods(city: str) -> List[Dict]:
    """Load neighborhood data from seed JSON files (supports multiple schemas)."""
    global _SEED_DATA_CACHE

    # Build cache on first call
    if _SEED_DATA_CACHE is None:
        _SEED_DATA_CACHE = {}

        data_dir = Path(SEED_DATA_DIR) if SEED_DATA_DIR else Path(__file__).parent.parent / 'data'
        if not data_dir.exists():
            logger.warning(f"Seed data directory not found: {data_dir}")
            return []

        for json_file in data_dir.rglob('*.json'):
            file_stem = json_file.stem.lower()
            if any(pattern == file_stem or pattern in json_file.name.lower() for pattern in EXCLUDE_FILES):
                continue
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if not isinstance(data, dict):
                    continue

                # Schema 1: {"cities": {"City": [..]}}
                cities = data.get('cities')
                if isinstance(cities, dict):
                    for city_name, neighborhoods in cities.items():
                        if isinstance(neighborhoods, list) and neighborhoods:
                            _SEED_DATA_CACHE[city_name.lower().strip()] = neighborhoods
                    continue

                # Schema 2: {"city": "Name", "neighborhoods": [...]}
                if 'city' in data and 'neighborhoods' in data:
                    neighborhoods = data.get('neighborhoods')
                    if isinstance(neighborhoods, list) and neighborhoods:
                        _SEED_DATA_CACHE[str(data['city']).lower().strip()] = neighborhoods
            except Exception as e:
                logger.debug(f"Could not load seed data from {json_file}: {e}")

        logger.info(f"Loaded seed data for {len(_SEED_DATA_CACHE)} cities")

    city_key = city.lower().strip()
    if city_key in _SEED_DATA_CACHE:
        return _SEED_DATA_CACHE[city_key]

    if len(_SEED_DATA_CACHE) < PARTIAL_MATCH_THRESHOLD:
        for cached_city, neighborhoods in _SEED_DATA_CACHE.items():
            if city_key in cached_city or cached_city in city_key:
                logger.debug(f"Partial match: '{city_key}' matched '{cached_city}'")
                return neighborhoods

    return []


async def fetch_neighborhoods_wikidata(city: str, lat: float, lon: float) -> List[Dict]:
    """
    Fallback: Use Wikidata to find neighborhoods
    """
    # SPARQL query to find neighborhoods of a city
    sparql_query = f"""
    SELECT ?neighborhood ?neighborhoodLabel WHERE {{
      ?city wdt:P31 wd:Q515;  # instance of city
            rdfs:label "{city}"@en;
            wdt:P625 ?coord.
      ?neighborhood wdt:P131 ?city;
                    wdt:P31/wdt:P279* wd:Q188509;  # instance/subclass of neighborhood
                    rdfs:label ?neighborhoodLabel.
      FILTER(LANG(?neighborhoodLabel) = "en")
    }}
    LIMIT 15
    """
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://query.wikidata.org/sparql',
                params={'query': sparql_query, 'format': 'json'},
                headers={'Accept': 'application/sparql-results+json'},
                timeout=aiohttp.ClientTimeout(total=3)
            ) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                results = data.get('results', {}).get('bindings', [])
                
                neighborhoods = []
                for result in results:
                    name = result.get('neighborhoodLabel', {}).get('value', '')
                    if name:
                        neighborhoods.append({
                            'name': name,
                            'description': f"Neighborhood in {city}",
                            'type': 'culture'
                        })
                
                return neighborhoods
                
    except Exception as e:
        logger.warning(f"Wikidata fallback failed for {city}: {e}")
        return []


async def fetch_admin_names_nominatim(city: str, relation_id: Optional[int]) -> List[Dict]:
    """Fetch admin-8/9 names via Nominatim as a lightweight fallback."""
    if not relation_id:
        return []
    try:
        params = {
            "format": "json",
            "polygon_geojson": 0,
            "addressdetails": 0,
            "extratags": 1,
            "limit": 50,
            "q": city,
        }
        headers = {"User-Agent": "TravelLand/1.0 (contact: team@travelland.local)"}
        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=2)) as session:
            async with session.get("https://nominatim.openstreetmap.org/search", params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results = []
                for item in data:
                    if item.get("osm_type") == "relation" and item.get("osm_id"):
                        # skip the city itself
                        if int(item["osm_id"]) == relation_id:
                            continue
                        name = item.get("display_name", "").split(",")[0].strip()
                        if name:
                            results.append({"name": name, "description": name, "type": "culture"})
                return results[:10]
    except Exception as e:
        logger.debug(f"Nominatim admin fetch failed for {city}: {e}")
        return []


async def get_neighborhoods_for_city(city: str, lat: float, lon: float) -> List[Dict]:
    """
    Main entry point: Get neighborhoods using multiple strategies
    Optimized for speed with early returns
    Priority:
    1. Seed data from JSON files (comprehensive, curated data)
    2. Overpass API (real-time OSM data)
    3. Wikidata (structured knowledge base)
    4. Neighborhood suggestions (legacy seed data)
    5. Generic fallback (last resort)
    """
    city_key = city.lower().strip()
    relation_id = None  # relation lookups not configured

    # First try: Load from comprehensive seed data files
    neighborhoods = load_seed_neighborhoods(city)
    if neighborhoods:
        logger.info(f"Found {len(neighborhoods)} neighborhoods for {city} from seed data")
        return neighborhoods
    
    # Second try: Overpass API (most comprehensive real-time data)
    neighborhoods = await fetch_neighborhoods_dynamic(city, lat, lon)
    if neighborhoods:
        logger.info(f"Found {len(neighborhoods)} neighborhoods for {city} via Overpass")
        return neighborhoods

    # Third try: Wikidata
    logger.info(f"Trying Wikidata fallback for {city}")
    neighborhoods = await fetch_neighborhoods_wikidata(city, lat, lon)
    if neighborhoods:
        logger.info(f"Found {len(neighborhoods)} neighborhoods for {city} via Wikidata")
        return neighborhoods

    # Fourth try: Legacy neighborhood suggestions (seed data in providers)
    logger.info(f"Trying neighborhood suggestions fallback for {city}")
    try:
        from city_guides.providers.neighborhood_suggestions import get_neighborhood_suggestions
        neighborhoods = get_neighborhood_suggestions(city)
        if neighborhoods:
            logger.info(f"Found {len(neighborhoods)} neighborhoods for {city} via suggestions")
            return neighborhoods
    except Exception as e:
        logger.warning(f"Neighborhood suggestions fallback failed: {e}")

    # For very large cities that trip Overpass limits, skip Overpass and use admin names + Wikidata
    big_city_skip_overpass = {'london', 'rio de janeiro', 'rio de janeiro, brazil', 'new york', 'tokyo', 'paris', 'los angeles', 'shanghai', 'beijing'}

    if city_key in big_city_skip_overpass:
        neighborhoods = []
        if relation_id:
            overpass_admin = await fetch_admin_names_overpass(city, int(relation_id))
            if overpass_admin:
                neighborhoods.extend(overpass_admin)
        if len(neighborhoods) < 5:
            wikidata_extra = await fetch_neighborhoods_wikidata(city, lat, lon)
            if wikidata_extra:
                neighborhoods.extend(wikidata_extra)
        if len(neighborhoods) < 5 and relation_id:
            admin_extra = await fetch_admin_names_nominatim(city, int(relation_id))
            if admin_extra:
                neighborhoods.extend(admin_extra)
    else:
        # Try Overpass API first (most comprehensive)
        neighborhoods = await fetch_neighborhoods_dynamic(city, lat, lon)

    # If Overpass path yielded too few, try Wikidata supplement before padding
    if len(neighborhoods) < 5:
        logger.info(f"Found {len(neighborhoods)} so far for {city}; trying Wikidata supplement")
        wikidata_extra = await fetch_neighborhoods_wikidata(city, lat, lon)
        if wikidata_extra:
            neighborhoods.extend(wikidata_extra)

    # If still too few and we have a relation id, fetch admin names via Nominatim
    if len(neighborhoods) < 5 and relation_id:
        admin_extra = await fetch_admin_names_nominatim(city, int(relation_id))
        if admin_extra:
            neighborhoods.extend(admin_extra)

    # Deduplicate by name (case-insensitive), preserve order
    seen = set()
    deduped = []
    for n in neighborhoods:
        name = (n.get('name') or '').strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        deduped.append(n)

    # Pad with generic directional neighborhoods to reach at least 5 unique entries
    if len(deduped) < 5:
        for g in generate_generic_neighborhoods(city, lat, lon):
            g_name = (g.get('name') or '').strip().lower()
            if not g_name or g_name in seen:
                continue
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle different JSON structures
                if isinstance(data, dict):
                    # Structure: {"cities": {"CityName": [neighborhoods]}}
                    cities = data.get('cities', {})
                    if isinstance(cities, dict):
                        for city_name, neighborhoods in cities.items():
                            if isinstance(neighborhoods, list) and len(neighborhoods) > 0:
                                # Normalize city names to lowercase for matching
                                city_key = city_name.lower().strip()
                                _SEED_DATA_CACHE[city_key] = neighborhoods
                                logger.debug(f"Loaded {len(neighborhoods)} neighborhoods for {city_name} from {json_file.name}")
            except Exception as e:
                logger.debug(f"Could not load seed data from {json_file}: {e}")
        
        logger.info(f"Loaded seed data for {len(_SEED_DATA_CACHE)} cities")
    
    # Look up city in cache (case-insensitive)
    city_key = city.lower().strip()
    
    # Try exact match first (O(1) lookup)
    if city_key in _SEED_DATA_CACHE:
        return _SEED_DATA_CACHE[city_key]
    
    # Try partial match only if exact match fails
    # Note: This is O(n) but only runs on cache miss, and n is limited (~50-100 cities)
    # For larger scale, consider implementing a prefix tree or fuzzy matching index
    if len(_SEED_DATA_CACHE) < PARTIAL_MATCH_THRESHOLD:  # Only do partial matching for small caches
        for cached_city, neighborhoods in _SEED_DATA_CACHE.items():
            if city_key in cached_city or cached_city in city_key:
                logger.debug(f"Partial match: '{city_key}' matched '{cached_city}'")
                return neighborhoods
    
    return []


def generate_generic_neighborhoods(city: str, lat: float, lon: float) -> List[Dict]:
    """
    Last resort: Generate directional neighborhoods
    Returns up to 20 generic areas based on common urban patterns
    Better than returning empty
    """
    return [
        {'name': f'{city} Centre', 'description': f'Downtown area of {city}', 'type': 'culture'},
        {'name': f'{city} Historic District', 'description': f'Historic center of {city}', 'type': 'historic'},
        {'name': f'{city} Old Town', 'description': f'Traditional old town area of {city}', 'type': 'historic'},
        {'name': f'{city} Waterfront', 'description': f'Riverside/coastal area of {city}', 'type': 'waterfront'},
        {'name': f'{city} North', 'description': f'Northern district of {city}', 'type': 'residential'},
        {'name': f'{city} South', 'description': f'Southern district of {city}', 'type': 'residential'},
        {'name': f'{city} East', 'description': f'Eastern district of {city}', 'type': 'residential'},
        {'name': f'{city} West', 'description': f'Western district of {city}', 'type': 'residential'},
        {'name': f'{city} Market District', 'description': f'Shopping and market area of {city}', 'type': 'market'},
        {'name': f'{city} Arts Quarter', 'description': f'Cultural and arts district of {city}', 'type': 'culture'},
        {'name': f'{city} Business District', 'description': f'Commercial center of {city}', 'type': 'modern'},
        {'name': f'{city} University Area', 'description': f'Academic district near universities in {city}', 'type': 'culture'},
        {'name': f'{city} Park Area', 'description': f'Green spaces and parks around {city}', 'type': 'nature'},
        {'name': f'{city} Riverside', 'description': f'Area along the river in {city}', 'type': 'waterfront'},
        {'name': f'{city} Heights', 'description': f'Elevated area with views in {city}', 'type': 'residential'},
        {'name': f'{city} Suburb', 'description': f'Suburban areas around {city}', 'type': 'residential'},
        {'name': f'{city} Shopping District', 'description': f'Main shopping area of {city}', 'type': 'shopping'},
        {'name': f'{city} Entertainment Quarter', 'description': f'Nightlife and entertainment hub of {city}', 'type': 'nightlife'},
        {'name': f'{city} Cultural Center', 'description': f'Museums and cultural venues in {city}', 'type': 'culture'},
        {'name': f'{city} Garden District', 'description': f'Residential area with green spaces in {city}', 'type': 'nature'},
    ]