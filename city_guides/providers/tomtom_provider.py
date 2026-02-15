"""TomTom provider for tourist attractions and POIs.

Uses TomTom Search API which has a generous free tier:
- 2,500 requests/day for Search API
- No credit card required for free tier
- Good global coverage for tourist attractions

Get API key at: https://developer.tomtom.com/
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
import os

TOMTOM_SEARCH_URL = "https://api.tomtom.com/search/2/search/.json"

# Tourist attraction categories
ATTRACTION_CATEGORIES = {
    "museum": "7302",  # Museums
    "art_gallery": "7317",  # Art galleries
    "historic": "7318",  # Historic sites/monuments
    "castle": "7368",  # Castles
    "church": "7309",  # Churches/cathedrals
    "temple": "7308",  # Temples
    "theatre": "7310",  # Theatres/concert halls
    "park": "9362",  # Parks/gardens
    "zoo": "7373",  # Zoos/aquariums
    "viewpoint": "7380",  # Viewpoints
    "tourist_attraction": "7389",  # Tourist attractions (general)
}


async def discover_tourist_attractions(
    city: str,
    limit: int = 10,
    session: Optional[aiohttp.ClientSession] = None
) -> List[Dict[str, Any]]:
    """Discover tourist attractions using TomTom Search API.
    
    Args:
        city: City name (e.g., "Bucharest", "Paris")
        limit: Maximum results to return
        session: Optional aiohttp session
        
    Returns:
        List of attraction dictionaries
    """
    api_key = os.environ.get("TOMTOM_API_KEY")
    if not api_key:
        print("[TOMTOM] No API key configured - set TOMTOM_API_KEY env var")
        return []
    
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True
    
    try:
        attractions = []
        
        # Search for multiple attraction types
        categories_to_search = [
            ATTRACTION_CATEGORIES["tourist_attraction"],
            ATTRACTION_CATEGORIES["museum"],
            ATTRACTION_CATEGORIES["historic"],
            ATTRACTION_CATEGORIES["castle"],
            ATTRACTION_CATEGORIES["park"],
        ]
        
        for category in categories_to_search:
            if len(attractions) >= limit:
                break
            
            results = await _search_pois(city, category, limit - len(attractions), api_key, session)
            attractions.extend(results)
        
        # Deduplicate by name
        seen = set()
        unique = []
        for a in attractions:
            name = a.get("name", "").lower()
            if name and name not in seen:
                seen.add(name)
                unique.append(a)
        
        print(f"[TOMTOM] Found {len(unique)} attractions for {city}")
        return unique[:limit]
        
    except Exception as e:
        print(f"[TOMTOM] Error discovering attractions: {e}")
        return []
    finally:
        if close_session:
            await session.close()


async def _search_pois(
    city: str,
    category: str,
    limit: int,
    api_key: str,
    session: aiohttp.ClientSession
) -> List[Dict]:
    """Search POIs using TomTom API."""
    params = {
        "key": api_key,
        "query": f"{city}",
        "categorySet": category,
        "limit": min(limit, 20),
        "countrySet": "RO,FR,IT,ES,DE,UK,AT,NL,BE,CH,PL,CZ,HU,BG,GR,TR,US,CA,AU,NZ,JP,KR,CN,TH,VN,SG,MY,ID,PH,IN,BR,MX,AR,CL,PE,CO,ZA,EG,MA,TN",  # Major tourist countries
        "language": "en-US",
    }
    
    try:
        # TomTom API uses search endpoint with query parameter
        params = {
            "key": api_key,
            "query": f"{category} in {city}",
            "limit": min(limit, 20),
            "countrySet": "RO,FR,IT,ES,DE,UK,AT,NL,BE,CH,PL,CZ,HU,BG,GR,TR,US,CA,AU,NZ,JP,KR,CN,TH,VN,SG,MY,ID,PH,IN,BR,MX,AR,CL,PE,CO,ZA,EG,MA,TN",
            "language": "en-US",
        }
        
        async with session.get(
            TOMTOM_SEARCH_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            if response.status != 200:
                text = await response.text()
                print(f"[TOMTOM] HTTP {response.status}: {text[:100]}")
                return []
            
            data = await response.json()
            results = data.get("results", [])
            
            formatted = []
            for r in results:
                poi = r.get("poi", {})
                position = r.get("position", {})
                
                if not poi or not position:
                    continue
                
                venue = {
                    "id": f"tomtom_{r.get('id', '')}",
                    "name": poi.get("name", ""),
                    "address": poi.get("address", {}).get("freeformAddress", f"📍 {city}"),
                    "description": f"{poi.get('categories', ['Tourist Attraction'])[0]} in {city}",
                    "lat": position.get("lat"),
                    "lon": position.get("lon"),
                    "source": "tomtom",
                    "quality_score": 0.85,
                    "phone": poi.get("phone"),
                    "url": poi.get("url"),
                    "categories": poi.get("categories", []),
                }
                
                # Skip generic hotels/businesses
                name = venue["name"].lower()
                if any(kw in name for kw in ["hotel", "motel", "hostel", "inn"]):
                    continue
                
                formatted.append(venue)
            
            return formatted
            
    except asyncio.TimeoutError:
        print("[TOMTOM] Query timeout")
        return []
    except Exception as e:
        print(f"[TOMTOM] Query error: {e}")
        return []


# Synchronous wrapper
def discover_tourist_attractions_sync(city: str, limit: int = 10) -> List[Dict[str, Any]]:
    return asyncio.run(discover_tourist_attractions(city, limit))
