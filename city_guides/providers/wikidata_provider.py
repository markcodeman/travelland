"""Wikidata provider for tourist attractions and landmarks.

Uses Wikidata SPARQL endpoint to fetch structured tourist attraction data.
No API key required. Rate limits: reasonable for low-volume use.
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from urllib.parse import quote

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

# Simplified query to find tourist attractions by city name
# Uses P131 (located in the administrative territorial entity) with broader matching
TOURIST_ATTRACTIONS_QUERY = """
SELECT DISTINCT ?item ?itemLabel ?itemDescription ?coord ?image ?website
WHERE {{
  # Find the city by name - flexible matching
  ?city rdfs:label ?cityLabel .
  FILTER(LANG(?cityLabel) = "en")
  FILTER(CONTAINS(LCASE(?cityLabel), LCASE("{city_name}")))
  
  # City can be any type of populated place (Q515=city, Q1549591=big city, Q5119=capital)
  ?city wdt:P31 ?cityType .
  FILTER(?cityType IN (wd:Q515, wd:Q1549591, wd:Q5119, wd:Q15959509, wd:Q200250, wd:Q1066526))
  
  # Find attractions in this city (direct or via hierarchy)
  ?item wdt:P131 ?city .
  ?item wdt:P625 ?coord .
  
  # Must be a tourist attraction type
  {{ ?item wdt:P31 wd:Q570116 }}  # tourist attraction
  UNION {{ ?item wdt:P31 wd:Q33506 }}  # museum
  UNION {{ ?item wdt:P31 wd:Q811165 }}  # art gallery
  UNION {{ ?item wdt:P31 wd:Q16560 }}  # palace
  UNION {{ ?item wdt:P31 wd:Q23413 }}  # castle
  UNION {{ ?item wdt:P31 wd:Q243389 }}  # theatre
  UNION {{ ?item wdt:P31 wd:Q207694 }}  # park
  UNION {{ ?item wdt:P31 wd:Q4989906 }}  # monument
  
  # Get labels
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
    ?item rdfs:label ?itemLabel .
    ?item schema:description ?itemDescription .
  }}
  
  OPTIONAL {{ ?item wdt:P18 ?image }}
  OPTIONAL {{ ?item wdt:P856 ?website }}
}}
ORDER BY ?itemLabel
LIMIT {limit}
"""

# Query to find city Wikidata ID from name
CITY_LOOKUP_QUERY = """
SELECT DISTINCT ?city ?cityLabel ?population ?countryLabel
WHERE {
  ?city wdt:P31 wd:Q515 ;  # City
        rdfs:label ?cityLabel ;
        wdt:P1082 ?population .
  
  FILTER(LANG(?cityLabel) = "en")
  FILTER(CONTAINS(LCASE(?cityLabel), LCASE("{city_name}")))
  
  OPTIONAL { ?city wdt:P17 ?country }
  SERVICE wikibase:label { 
    bd:serviceParam wikibase:language "en" .
    ?country rdfs:label ?countryLabel .
  }
}
ORDER BY DESC(?population)
LIMIT 5
"""


async def discover_tourist_attractions(
    city: str,
    limit: int = 10,
    session: Optional[aiohttp.ClientSession] = None
) -> List[Dict[str, Any]]:
    """Discover tourist attractions using Wikidata SPARQL."""
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True
    
    try:
        # Parse city name and country for better disambiguation
        city_parts = city.split(',')
        city_clean = city_parts[0].strip()
        country_hint = city_parts[1].strip() if len(city_parts) > 1 else None

        # Use country hint in query if available
        if country_hint:
            # Enhanced query with country filtering
            query = f"""
            SELECT DISTINCT ?item ?itemLabel ?itemDescription ?coord ?image ?website
            WHERE {{
              # Find the city by name with country context
              ?city rdfs:label ?cityLabel .
              FILTER(LANG(?cityLabel) = "en")
              FILTER(CONTAINS(LCASE(?cityLabel), LCASE("{city_clean}")))

              # City can be any type of populated place
              ?city wdt:P31 ?cityType .
              FILTER(?cityType IN (wd:Q515, wd:Q1549591, wd:Q5119, wd:Q15959509, wd:Q200250, wd:Q1066526))

              # Use country for disambiguation (more flexible matching)
              ?city wdt:P17 ?country .
              ?country rdfs:label ?countryLabel .
              FILTER(LANG(?countryLabel) = "en")
              FILTER(REGEX(LCASE(?countryLabel), LCASE("{country_hint}")))

              # Find attractions in this city (direct or via administrative hierarchy)
              ?item wdt:P131* ?city .
              ?item wdt:P625 ?coord .

              # Must be a tourist attraction type (expanded list)
              {{
                ?item wdt:P31 ?attractionType .
                FILTER(?attractionType IN (
                  wd:Q570116,  # tourist attraction
                  wd:Q33506,   # museum
                  wd:Q811165,  # art gallery
                  wd:Q16560,   # palace
                  wd:Q23413,   # castle
                  wd:Q243389,  # theatre
                  wd:Q207694,  # park
                  wd:Q839954,  # archaeological site
                  wd:Q16970,   # church
                  wd:Q2977,    # cathedral
                  wd:Q32815,   # mosque
                  wd:Q44539,   # synagogue
                  wd:Q16917,   # temple
                  wd:Q1081138, # monument
                  wd:Q4989906, # memorial
                  wd:Q12518,   # tower
                  wd:Q22698,   # bridge
                  wd:Q12277,   # bridge (structure)
                  wd:Q11446,   # fort
                  wd:Q744913   # fortification
                ))
              }}

              # Get labels and optional data
              ?item rdfs:label ?itemLabel .
              FILTER(LANG(?itemLabel) = "en")

              OPTIONAL {{ ?item schema:description ?itemDescription . FILTER(LANG(?itemDescription) = "en") }}
              OPTIONAL {{ ?item wdt:P18 ?image }}
              OPTIONAL {{ ?item wdt:P856 ?website }}
            }}
            ORDER BY ?itemLabel
            LIMIT {min(limit, 15)}
            """
        else:
            # Original query without country filtering
            query = TOURIST_ATTRACTIONS_QUERY.format(
                city_name=city_clean.replace('"', '\\"'),
                limit=min(limit, 15)
            )

        attractions = await _execute_sparql(query, session)

        formatted = []
        for item in attractions:
            formatted_item = _format_wikidata_item(item, city)
            if formatted_item:
                formatted.append(formatted_item)

        print(f"[WIKIDATA] Found {len(formatted)} attractions for {city}" + (f" (country: {country_hint})" if country_hint else ""))
        return formatted[:limit]
        
    except Exception as e:
        print(f"[WIKIDATA] Error: {e}")
        return []
    finally:
        if close_session:
            await session.close()


async def _get_city_wikidata_id(city: str, session: aiohttp.ClientSession) -> Optional[str]:
    """Get Wikidata entity ID for a city name."""
    query = CITY_LOOKUP_QUERY.format(city_name=city.replace('"', '\\"'))
    
    results = await _execute_sparql(query, session)
    
    if results:
        # Take the first (most populous) match
        city_uri = results[0].get('city', {}).get('value', '')
        if city_uri:
            # Extract Q-number from URI
            city_id = city_uri.split('/')[-1]
            print(f"[WIKIDATA] Found city: {results[0].get('cityLabel', {}).get('value', city)} (ID: {city_id})")
            return city_id
    
    return None


async def _execute_sparql(query: str, session: aiohttp.ClientSession) -> List[Dict]:
    """Execute SPARQL query against Wikidata endpoint."""
    headers = {
        'Accept': 'application/sparql-results+json',
        'User-Agent': 'TravelLand/1.0 (research project)'
    }
    
    params = {'query': query}
    
    try:
        async with session.get(
            WIKIDATA_SPARQL_URL,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as response:
            if response.status != 200:
                text = await response.text()
                print(f"[WIKIDATA] SPARQL error {response.status}: {text[:200]}")
                return []
            
            data = await response.json()
            return data.get('results', {}).get('bindings', [])
            
    except asyncio.TimeoutError:
        print("[WIKIDATA] SPARQL query timeout")
        return []
    except Exception as e:
        print(f"[WIKIDATA] SPARQL query failed: {e}")
        return []


def _format_wikidata_item(item: Dict, city: str) -> Optional[Dict[str, Any]]:
    """Format Wikidata SPARQL result into venue dictionary."""
    try:
        # Extract coordinate string and parse lat/lon
        coord_val = item.get('coord', {}).get('value', '')
        lat, lon = _parse_wkt_coordinates(coord_val)
        
        if lat is None or lon is None:
            return None
        
        name = item.get('itemLabel', {}).get('value', '')
        if not name or name.startswith('Q'):  # Skip unnamed items
            return None
        
        description = item.get('itemDescription', {}).get('value', '')
        item_type = item.get('instanceLabel', {}).get('value', 'Tourist Attraction')
        
        # Build venue dict
        venue = {
            'id': item.get('item', {}).get('value', '').split('/')[-1],
            'name': name,
            'address': f"📍 {city}",
            'description': description or f"{item_type} in {city}",
            'lat': lat,
            'lon': lon,
            'venue_type': item_type,
            'source': 'wikidata',
            'quality_score': 0.8,  # Wikidata is generally high quality
        }
        
        # Add optional fields
        if 'image' in item:
            venue['image_url'] = item['image']['value']
        if 'website' in item:
            venue['website'] = item['website']['value']
        if 'article' in item:
            venue['wikipedia_url'] = item['article']['value']
        if 'commonsCategory' in item:
            venue['commons_category'] = item['commonsCategory']['value']
        
        return venue
        
    except Exception as e:
        print(f"[WIKIDATA] Error formatting item: {e}")
        return None


def _parse_wkt_coordinates(coord_str: str) -> tuple:
    """Parse WKT Point format: 'Point(26.1025 44.4268)'."""
    try:
        # Extract coordinates from Point(lon lat)
        match = coord_str.replace('Point(', '').replace(')', '').split()
        if len(match) >= 2:
            lon = float(match[0])
            lat = float(match[1])
            return (lat, lon)
    except (ValueError, IndexError) as e:
        print(f"[WIKIDATA] Failed to parse coordinates: {coord_str} - {e}")
    return (None, None)


# Synchronous wrapper for compatibility
def discover_tourist_attractions_sync(
    city: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Synchronous wrapper for discover_tourist_attractions."""
    return asyncio.run(discover_tourist_attractions(city, limit))
