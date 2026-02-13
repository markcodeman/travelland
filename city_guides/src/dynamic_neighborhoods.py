"""
Dynamic neighborhood fetcher using Overpass API
No hardcoded lists - works for ANY city globally
"""
import aiohttp
from typing import List, Dict, Optional
import logging
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache for seed data to avoid repeated file reads
_SEED_DATA_CACHE: Optional[Dict[str, List[Dict]]] = None

# Configuration constants
SEED_DATA_DIR = os.getenv('NEIGHBORHOOD_SEED_DIR', None)  # Allow override via env var
EXCLUDE_FILES = ['cache', 'seeded_cities']  # Files/patterns to exclude from seed data loading

async def fetch_neighborhoods_dynamic(city: str, lat: float, lon: float, radius: int = 5000) -> List[Dict]:
    """
    Dynamically fetch neighborhoods for ANY city using Overpass API
    No hardcoded lists - works for ANY city globally
    Optimized for speed with reduced radius and simplified query
    
    Args:
        city: City name
        lat: Latitude
        lon: Longitude  
        radius: Search radius in meters (default 5km for faster queries, 8km for large cities)
    
    Returns:
        List of neighborhood dicts with name, description, type
    """
    if not lat or not lon:
        return []
    
    # Adjust radius based on city size (smaller radius = faster query)
    # Use 5km default, but can be overridden
    search_radius = radius
    
    # Simplified Overpass API query for faster response - limit to 10 results
    overpass_query = f"""
    [out:json][timeout:10];
    (
      // Find neighborhoods, districts, and suburbs only - limited count
      node["place"~"^(quarter|suburb|neighbourhood|district)$"](around:{search_radius},{lat},{lon});
    );
    out center tags 10;
    """
    
    # Try multiple Overpass API endpoints for better reliability
    overpass_endpoints = [
        'https://overpass-api.de/api/interpreter',
        'https://overpass.kumi.systems/api/interpreter',
        'https://overpass.openstreetmap.fr/api/interpreter'
    ]
    
    for endpoint in overpass_endpoints:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    data={'data': overpass_query},
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        elements = data.get('elements', [])
                        break
                    else:
                        logger.warning(f"Overpass API {endpoint} returned {response.status} for {city}")
                        continue
        except Exception as e:
            logger.warning(f"Overpass API {endpoint} failed for {city}: {e}")
            continue
    else:
        logger.warning(f"All Overpass API endpoints failed for {city}")
        return []
                
    neighborhoods = []
    seen_names = set()
    
    for elem in elements:
        tags = elem.get('tags', {})
        name = tags.get('name')
        
        # Skip if no name or already seen
        if not name or name.lower() in seen_names:
            continue
        
        # Skip if name contains city name (avoid duplicates)
        if city.lower() in name.lower() and name.lower() != city.lower():
            continue
        
        seen_names.add(name.lower())
        
        # Determine type from tags
        place_type = tags.get('place', 'quarter')
        boundary = tags.get('boundary')
        
        # Create description based on type
        if place_type == 'suburb':
            description = f"Suburb of {city}"
            type_cat = 'residential'
        elif place_type == 'quarter' or place_type == 'neighbourhood':
            description = f"Neighborhood in {city}"
            type_cat = 'culture'
        elif boundary == 'administrative':
            description = f"District in {city}"
            type_cat = 'culture'
        else:
            description = f"Area in {city}"
            type_cat = 'culture'
        
        # Add wikidata description if available
        if 'wikipedia' in tags:
            description += " - See Wikipedia for more info"
        
        neighborhoods.append({
            'name': name,
            'description': description,
            'type': type_cat,
            'lat': elem.get('lat') or elem.get('center', {}).get('lat'),
            'lon': elem.get('lon') or elem.get('center', {}).get('lon')
        })
    
    # Sort by relevance (closer to city center first if we had distance calc)
    # For now, just return top 15
    return neighborhoods[:15]


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
                timeout=aiohttp.ClientTimeout(total=15)
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
    
    # Last resort: Generate generic neighborhoods based on city center
    logger.warning(f"No neighborhoods found for {city}, generating generic areas")
    return generate_generic_neighborhoods(city, lat, lon)


def load_seed_neighborhoods(city: str) -> List[Dict]:
    """
    Load neighborhood data from JSON seed files in city_guides/data/
    Searches recursively through all JSON files for matching city
    Returns list of neighborhood dicts or empty list if not found
    """
    global _SEED_DATA_CACHE
    
    # Build cache on first call
    if _SEED_DATA_CACHE is None:
        _SEED_DATA_CACHE = {}
        
        # Allow override via environment variable for testing
        if SEED_DATA_DIR:
            data_dir = Path(SEED_DATA_DIR)
        else:
            data_dir = Path(__file__).parent.parent / 'data'
        
        if not data_dir.exists():
            logger.warning(f"Seed data directory not found: {data_dir}")
            return []
        
        # Recursively find all JSON files
        for json_file in data_dir.rglob('*.json'):
            # Skip files matching exclusion patterns
            if any(pattern in json_file.name.lower() for pattern in EXCLUDE_FILES):
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
    if len(_SEED_DATA_CACHE) < 500:  # Only do partial matching for small caches
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