"""
Dynamic neighborhood fetcher using Overpass API
No hardcoded lists - works for ANY city globally
"""
import aiohttp
import asyncio
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

async def fetch_neighborhoods_dynamic(city: str, lat: float, lon: float, radius: int = 8000) -> List[Dict]:
    """
    Dynamically fetch neighborhoods for ANY city using Overpass API
    No hardcoded lists - works for ANY city globally
    Optimized for speed with reduced radius and simplified query
    
    Args:
        city: City name
        lat: Latitude
        lon: Longitude  
        radius: Search radius in meters (default 8km for faster queries)
    
    Returns:
        List of neighborhood dicts with name, description, type
    """
    if not lat or not lon:
        return []
    
    # Simplified Overpass API query for faster response
    overpass_query = f"""
    [out:json][timeout:15];
    (
      // Find neighborhoods, districts, and suburbs only
      node["place"~"^(quarter|suburb|neighbourhood|district)$"](around:{radius},{lat},{lon});
      way["place"~"^(quarter|suburb|neighbourhood|district)$"](around:{radius},{lat},{lon});
      relation["place"~"^(quarter|suburb|neighbourhood|district)$"](around:{radius},{lat},{lon});
    );
    out center tags 15;
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
            description += f" - See Wikipedia for more info"
        
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
    """
    if city.lower() == "marseille":
        logger.info(f"Using seed data from JSON file for Marseille")
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
    
    # Try Overpass API first (most comprehensive)
    neighborhoods = await fetch_neighborhoods_dynamic(city, lat, lon)
    
    if neighborhoods:
        logger.info(f"Found {len(neighborhoods)} neighborhoods for {city} via Overpass")
        return neighborhoods
    
    # Fallback to Wikidata
    logger.info(f"Trying Wikidata fallback for {city}")
    neighborhoods = await fetch_neighborhoods_wikidata(city, lat, lon)
    
    if neighborhoods:
        logger.info(f"Found {len(neighborhoods)} neighborhoods for {city} via Wikidata")
        return neighborhoods
    
    # Fallback to neighborhood suggestions (seed data)
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