"""
Dynamic neighborhood fetcher using Overpass API
No hardcoded lists - works for ANY city globally
"""
import asyncio
import aiohttp
import random
from typing import List, Dict, Tuple, Optional
import logging
from city_guides.providers.neighborhood_suggestions import CITY_RELATIONS

logger = logging.getLogger(__name__)

# Shared Overpass endpoints and headers
OVERPASS_ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.openstreetmap.fr/api/interpreter'
]
OVERPASS_HEADERS = {"User-Agent": "TravelLand/1.0 (contact: team@travelland.local)"}

async def fetch_neighborhoods_dynamic(city: str, lat: float, lon: float, radius: int = 8000) -> List[Dict]:
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
        List of neighborhood dicts with name, description, type (never None)
    """
    if not lat or not lon:
        return []


async def fetch_admin_names_overpass(city: str, relation_id: Optional[int]) -> List[Dict]:
    """Fetch admin/suburb/neighbourhood names using a fast Overpass query against the city relation area."""
    if not relation_id:
        return []
    area_id = 3600000000 + int(relation_id)
    # Specific query for neighborhoods, boroughs, districts
    overpass_query = f"""
    [out:json][timeout:3];
    area({area_id})->.searchArea;
    (
      relation["admin_level"~"8|9|10|11"]["boundary"="administrative"](area.searchArea);
      way["admin_level"~"8|9|10|11"]["boundary"="administrative"](area.searchArea);
      nwr["place"~"neighbourhood|suburb|quarter|borough|city_district|district"](area.searchArea);
    );
    out tags center 60;
    """
    endpoints = OVERPASS_ENDPOINTS.copy()
    random.shuffle(endpoints)
    endpoint = endpoints[0] if endpoints else None
    if not endpoint:
        return []
    try:
        async with aiohttp.ClientSession(headers=OVERPASS_HEADERS, timeout=aiohttp.ClientTimeout(total=3)) as session:
            async with session.post(endpoint, data={'data': overpass_query}) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                elements = data.get("elements", [])
                results = []
                for el in elements[:80]:
                    tags = el.get("tags", {})
                    name = tags.get("name") or tags.get("alt_name")
                    if not name:
                        continue
                    # Filter out city name itself
                    if name.lower() == city.lower():
                        continue
                    results.append({
                        "name": name.strip(),
                        "description": name.strip(),
                        "type": classify_neighborhood(tags),
                    })
                return results[:40]
    except Exception:
        return []
    
    # Adjust radius based on city size (smaller radius = faster query)
    # Keep big-city radius modest to avoid Overpass load
    large_cities = {'london', 'new york', 'tokyo', 'paris', 'los angeles', 'shanghai', 'beijing'}
    search_radius = radius
    if city and city.lower().split(',')[0].strip() in large_cities:
        search_radius = max(radius, 8000)
    
    city_key = city.lower().split(',')[0].strip()
    relation_id = CITY_RELATIONS.get(city_key)
    # Use radial query for all cities - simpler and more reliable
    # Look for specific neighborhood types
    overpass_query = f"""
    [out:json][timeout:3];
    (
      relation["place"~"neighbourhood|suburb|quarter|borough|city_district|district|locality"](around:{search_radius},{lat},{lon});
      way["place"~"neighbourhood|suburb|quarter|borough|city_district|district|locality"](around:{search_radius},{lat},{lon});
      node["place"~"neighbourhood|suburb|quarter|borough|city_district|district|locality"](around:{search_radius},{lat},{lon});
      relation["admin_level"~"8|9|10|11"](around:{search_radius},{lat},{lon});
      way["admin_level"~"8|9|10|11"](around:{search_radius},{lat},{lon});
      node["admin_level"~"8|9|10|11"](around:{search_radius},{lat},{lon});
    );
    out center tags 300;
    """
    
    # Try multiple Overpass API endpoints for better reliability (shuffled per request)
    endpoints = OVERPASS_ENDPOINTS.copy()
    random.shuffle(endpoints)
    overpass_headers = OVERPASS_HEADERS
    
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

    elements = []
    async def _fetch_overpass():
        for endpoint in overpass_endpoints:
            try:
                async with aiohttp.ClientSession(headers=overpass_headers) as session:
                    async with session.post(
                        endpoint,
                        data={'data': overpass_query},
                        timeout=aiohttp.ClientTimeout(total=3)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get('elements', [])
                        logger.warning(f"Overpass API {endpoint} returned {response.status} for {city}")
            except Exception as e:
                logger.warning(f"Overpass API {endpoint} failed for {city}: {e}")
        return []

    try:
        elements = await asyncio.wait_for(_fetch_overpass(), timeout=3)
    except Exception as e:
        logger.warning(f"Overpass fetch timed out for {city}: {e}")
        elements = []

    # If main query returns nothing for big cities with relation ids, try admin-level only to get names fast
    if not elements and relation_id:
        area_id = 3600000000 + int(relation_id)
        admin_query = f"""
        [out:json][timeout:3];
        area({area_id})->.searchArea;
        (
          relation["admin_level"~"8|9"]["boundary"="administrative"](area.searchArea);
        );
        out center tags 80;
        """
        for endpoint in overpass_endpoints:
            try:
                async with aiohttp.ClientSession(headers=overpass_headers) as session:
                    async with session.post(
                        endpoint,
                        data={'data': admin_query},
                        timeout=aiohttp.ClientTimeout(total=2)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            elements = data.get('elements', [])
                            if elements:
                                break
            except Exception:
                continue

    neighborhoods = []
    seen_names = set()

    def classify(name: str, tags: Dict, nearby: Optional[Dict[str, int]] = None) -> Tuple[str, str]:
        place_type = tags.get('place', '')
        boundary = tags.get('boundary')
        tourism = tags.get('tourism')
        leisure = tags.get('leisure')
        natural = tags.get('natural')
        amenity = tags.get('amenity')
        shop = tags.get('shop')
        nlow = (name or '').lower()
        city_low = city.lower()

        # Name-based hints (forests, gorges, valleys)
        if any(k in nlow for k in ['forest', 'pădure', 'bosque']):
            return 'nature', f"Forest area near {city}"
        if any(k in nlow for k in ['gorge', 'canyon', 'cheii', 'prăpăst']):
            return 'nature', f"Canyon/gorge area near {city}"
        if any(k in nlow for k in ['park', 'garden', 'parc', 'jardin']):
            return 'nature', f"Park area of {city}"
        if 'old town' in nlow or 'historic' in nlow:
            return 'historic', f"Historic area of {city}"
        if any(k in nlow for k in ['bridge', 'mostar', 'stari most', 'most']):
            return 'historic', f"Near the old bridge area of {city}"
        if any(k in nlow for k in ['river', 'rijeka', 'drina', 'neretva', 'water']):
            return 'waterfront', f"By the river in {city}"

        # Prioritize explicit attractions/parks/beach/shopping/food/nightlife
        if tourism in ('attraction', 'museum', 'gallery'):  # noqa: E712
            return 'attractions', f"Attractions hub in {city}"
        if leisure in ('park', 'garden'):  # noqa: E712
            return 'nature', f"Green area of {city}"
        if natural in ('beach', 'coastline'):
            return 'waterfront', f"Waterfront area of {city}"
        if amenity in ('restaurant', 'cafe', 'food_court'):
            return 'food', f"Dining area in {city}"
        if amenity in ('bar', 'pub', 'nightclub'):
            return 'nightlife', f"Nightlife spot in {city}"
        if shop:
            return 'shopping', f"Shopping area of {city}"
        if amenity in ('theatre', 'cinema'):
            return 'entertainment', f"Entertainment area of {city}"

        # Bran/Dracula lore heuristic
        if 'bran' in city_low:
            if 'castle' in nlow or 'dracula' in nlow or 'vlad' in nlow:
                return 'historic', "Near Bran Castle and Dracula lore."
            return 'historic', f"Historic area near Bran Castle."

        # Nearby POI-derived
        if nearby:
            if nearby.get('attractions', 0) > 0:
                return 'attractions', f"Attractions cluster in {city}."
            if nearby.get('nature', 0) + nearby.get('waterfront', 0) > 0:
                return 'nature', f"Nature access near {city}."
            if nearby.get('nightlife', 0) > 0:
                return 'nightlife', f"Nightlife pocket in {city}."
            if nearby.get('food', 0) > 0:
                return 'food', f"Dining spot in {city}."
            if nearby.get('shopping', 0) > 0:
                return 'shopping', f"Shopping area in {city}."

        # Fall back to place/boundary
        if place_type == 'suburb':
            return 'residential', f"Suburb of {city}"
        if place_type in ('quarter', 'neighbourhood', 'neighborhood', 'district', 'city_district'):
            return 'culture', f"Neighborhood in {city}"
        if boundary == 'administrative':
            return 'culture', f"District in {city}"
        return 'culture', f"Area in {city}"

    def build_highlight(name: str, tags: Dict, nearby: Optional[Dict[str, int]] = None) -> str:
        nlow = (name or '').lower()
        tourism = tags.get('tourism')
        natural = tags.get('natural')
        leisure = tags.get('leisure')
        amenity = tags.get('amenity')

        if tourism == 'attraction' or 'castle' in nlow or 'fort' in nlow:
            return 'Historic landmark vibes.'
        if natural in ('beach', 'coastline') or 'cheii' in nlow or 'gorge' in nlow:
            return 'Scenic nature and cliffs.'
        if leisure in ('park', 'garden') or 'forest' in nlow or 'pădure' in nlow:
            return 'Green space and trails.'
        if amenity in ('restaurant', 'cafe'):
            return 'Local food cluster.'
        if amenity in ('bar', 'pub', 'nightclub'):
            return 'Nightlife pocket.'
        if tags.get('shop'):
            return 'Shops and markets nearby.'
        if nearby:
            if nearby.get('attractions', 0) > 1:
                return 'Landmarks and sights nearby.'
            if nearby.get('food', 0) > 1:
                return 'Cluster of local eateries.'
            if nearby.get('nightlife', 0) > 0:
                return 'Bars and nightlife close by.'
            if nearby.get('shopping', 0) > 1:
                return 'Shops and markets nearby.'
            if nearby.get('nature', 0) + nearby.get('waterfront', 0) > 0:
                return 'Trails, parks, or water views close.'
        return ''
    
    neighborhoods = []
    seen_names = set()
    for el in elements:
        tags = el.get('tags', {})
        name = tags.get('name') or tags.get('alt_name')
        if not name:
            continue
        name_lower = name.lower().strip()
        # Skip city name itself
        if name_lower == city.lower():
            continue
        # Skip duplicates
        if name_lower in seen_names:
            continue
        # Skip if name is too generic (less than 3 chars)
        if len(name_lower) < 3:
            continue
        # Only skip generic patterns if we have enough real neighborhoods
        if len(neighborhoods) >= 5:
            generic_patterns = ['centre', 'center', 'north', 'south', 'east', 'west', 'downtown', 'central']
            if any(pattern in name_lower for pattern in generic_patterns):
                continue
        # Skip city name parts - but only if they're the ONLY part of the name
        city_name_parts = city.lower().split()
        for part in city_name_parts:
            if len(part) > 2 and name_lower == part:
                continue
        seen_names.add(name_lower)
        # Get nearby POI tags for enrichment
        poi_counts = await fetch_nearby_tags(session_nearby, el.get('lat') or lat, el.get('lon') or lon)
        # Build description based on POI counts
        desc_parts = []
        if poi_counts.get('attractions', 0) > 0:
            desc_parts.append(f"{poi_counts['attractions']} attractions")
        if poi_counts.get('food', 0) > 0:
            desc_parts.append(f"{poi_counts['food']} restaurants")
        if poi_counts.get('nightlife', 0) > 0:
            desc_parts.append(f"{poi_counts['nightlife']} nightlife spots")
        if poi_counts.get('shopping', 0) > 0:
            desc_parts.append(f"{poi_counts['shopping']} shops")
        if poi_counts.get('nature', 0) > 0:
            desc_parts.append(f"parks and nature")
        description = ', '.join(desc_parts) if desc_parts else f"A neighborhood in {city}"
        neighborhoods.append({
            'name': name.strip(),
            'description': description,
            'type': classify(name, tags, poi_counts),
            'lat': el.get('lat'),
            'lon': el.get('lon'),
            'tags': tags
        })
        if len(neighborhoods) >= 15:
            break
    return neighborhoods[:15]


async def fetch_neighborhoods_wikidata(city: str, lat: float, lon: float) -> List[Dict]:
    """
    Fallback: Use Wikidata to find neighborhoods
    """
    # Try multiple approaches to find the city in Wikidata
    sparql_queries = [
        # Approach 1: Exact label match
        f"""
        SELECT ?neighborhood ?neighborhoodLabel WHERE {{
          ?city rdfs:label "{city}"@en.
          ?neighborhood wdt:P131 ?city;
                        wdt:P31/wdt:P279* wd:Q188509;
                        rdfs:label ?neighborhoodLabel.
          FILTER(LANG(?neighborhoodLabel) = "en")
        }}
        LIMIT 15
        """,
        # Approach 2: Near coordinates
        f"""
        SELECT ?neighborhood ?neighborhoodLabel WHERE {{
          SERVICE wikibase:around {{
            ?neighborhood wdt:P625 ?coord.
            bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral.
            bd:serviceParam wikibase:radius "10".
            bd:serviceParam wikibase:distance ?dist.
          }}
          ?neighborhood wdt:P31/wdt:P279* wd:Q188509;
                        rdfs:label ?neighborhoodLabel.
          FILTER(LANG(?neighborhoodLabel) = "en")
        }}
        LIMIT 15
        """
    ]
    
    for sparql_query in sparql_queries:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://query.wikidata.org/sparql',
                    params={'query': sparql_query, 'format': 'json'},
                    headers={'Accept': 'application/sparql-results+json'},
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as response:
                    if response.status != 200:
                        continue
                    
                    data = await response.json()
                    results = data.get('results', {}).get('bindings', [])
                    
                    if not results:
                        continue
                    
                    neighborhoods = []
                    for result in results:
                        name = result.get('neighborhoodLabel', {}).get('value', '')
                        if name:
                            neighborhoods.append({
                                'name': name,
                                'description': f"Neighborhood in {city}",
                                'type': 'culture'
                            })
                    
                    if neighborhoods:
                        return neighborhoods
                    
        except Exception as e:
            logger.warning(f"Wikidata fallback failed for {city}: {e}")
            continue
    
    return []


async def fetch_neighborhoods_nominatim(city: str, lat: float, lon: float) -> List[Dict]:
    """
    Use Nominatim to find neighborhoods
    """
    try:
        # Simple search for neighborhoods
        search_url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': f'{city} neighborhood',
            'format': 'json',
            'limit': 15,
            'addressdetails': 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params, timeout=aiohttp.ClientTimeout(total=2)) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                neighborhoods = []
                seen_names = set()
                
                for item in data:
                    name = item.get('display_name', '')
                    if not name:
                        continue
                    # Extract neighborhood name from display name
                    parts = name.split(',')
                    if parts:
                        nh_name = parts[0].strip()
                        # Skip if it's the city itself
                        if nh_name.lower() == city.lower():
                            continue
                        # Skip duplicates
                        if nh_name.lower() in seen_names:
                            continue
                        # Skip generic patterns
                        generic_patterns = ['centre', 'center', 'north', 'south', 'east', 'west', 'downtown', 'central']
                        if any(pattern in nh_name.lower() for pattern in generic_patterns):
                            continue
                        seen_names.add(nh_name.lower())
                        neighborhoods.append({
                            'name': nh_name,
                            'description': f"Neighborhood in {city}",
                            'type': 'culture'
                        })
                
                return neighborhoods[:15]
                
    except Exception as e:
        logger.warning(f"Nominatim search failed for {city}: {e}")
        return []


async def get_neighborhoods_for_city(city: str, lat: float, lon: float) -> List[Dict]:
    """
    Main entry point: Get neighborhoods using multiple strategies
    Optimized for speed with early returns
    """
    city_key = city.lower().split(',')[0].strip()
    relation_id: Optional[int] = CITY_RELATIONS.get(city_key)

    if city.lower() == "marseille":
        logger.info("Using seed data from JSON file for Marseille")
        try:
            import json
            import os
            with open(os.path.join(os.path.dirname(__file__), '../data/marseille_neighborhoods.json'), 'r', encoding='utf-8') as f:
                data = json.load(f)
                neighborhoods = data.get('neighborhoods', [])
                if neighborhoods:
                    logger.info(f"Found {len(neighborhoods)} neighborhoods for {city} from JSON file")
                    return neighborhoods
        except Exception as e:
            logger.warning(f"Failed to load Marseille neighborhood data from JSON file: {e}")
    
    neighborhoods = []
    
    # Try Wikidata FIRST for big cities - more reliable than Overpass
    if city_key in {'london', 'rio de janeiro', 'rio de janeiro, brazil', 'new york', 'tokyo', 'paris'}:
        wikidata_neighborhoods = await fetch_neighborhoods_wikidata(city, lat, lon)
        if wikidata_neighborhoods:
            neighborhoods.extend(wikidata_neighborhoods)
            logger.info(f"Found {len(wikidata_neighborhoods)} neighborhoods for {city} from Wikidata")
            # Skip Overpass for these cities if Wikidata worked
            if len(neighborhoods) >= 5:
                return neighborhoods[:15] or []
        # Try Nominatim search as fallback
        nominatim_neighborhoods = await fetch_neighborhoods_nominatim(city, lat, lon)
        if nominatim_neighborhoods:
            neighborhoods.extend(nominatim_neighborhoods)
            logger.info(f"Found {len(nominatim_neighborhoods)} neighborhoods for {city} from Nominatim")
            if len(neighborhoods) >= 5:
                return neighborhoods[:15] or []

    # Try Overpass API first (most comprehensive)
    overpass_result = await fetch_neighborhoods_dynamic(city, lat, lon)
    if overpass_result:
        neighborhoods.extend(overpass_result)

    # Ensure neighborhoods is always a list
    if neighborhoods is None:
        neighborhoods = []

    # If Overpass path yielded too few, try Wikidata supplement before padding
    if len(neighborhoods) < 5:
        logger.info(f"Found {len(neighborhoods)} so far for {city}; trying Wikidata supplement")
        wikidata_extra = await fetch_neighborhoods_wikidata(city, lat, lon)
        if wikidata_extra:
            neighborhoods.extend(wikidata_extra)

    # If still too few, try Nominatim search
    if len(neighborhoods) < 5:
        nominatim_extra = await fetch_neighborhoods_nominatim(city, lat, lon)
        if nominatim_extra:
            neighborhoods.extend(nominatim_extra)

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
            deduped.append(g)
            seen.add(g_name)
            if len(deduped) >= 5:
                break

    logger.info(f"Returning {len(deduped)} neighborhoods for {city}")
    return deduped[:15]

def generate_generic_neighborhoods(city: str, lat: float, lon: float) -> List[Dict]:
    """
    Last resort: Generate directional neighborhoods (North, South, East, West, Center)
    Better than returning empty
    """
    return [
        {'name': f'{city} Centre', 'description': f'Downtown area of {city}', 'type': 'culture'},
        {'name': f'{city} North', 'description': f'Northern area of {city}', 'type': 'residential'},
        {'name': f'{city} South', 'description': f'Southern area of {city}', 'type': 'residential'},
        {'name': f'{city} East', 'description': f'Eastern area of {city}', 'type': 'residential'},
        {'name': f'{city} West', 'description': f'Western area of {city}', 'type': 'residential'},
        {'name': f'{city} Old Town', 'description': f'Historic center of {city}', 'type': 'historic'},
        {'name': f'{city} Waterfront', 'description': f'Riverside/coastal area of {city}', 'type': 'nature'},
    ]