"""Smart neighborhood suggestions for large cities - uses Nominatim + Overpass"""
from typing import List, Dict, Optional
import aiohttp
import asyncio

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# City relation IDs for major cities (OSM relation IDs)
CITY_RELATIONS = {
    "london": 175342,      # Greater London
    "paris": 71525,        # Paris
    "new york": 175221,    # New York City  
    "tokyo": 1543072,      # Tokyo
    "barcelona": 347950,   # Barcelona
    "rome": 41485,         # Rome
}

# Fallback seed data
CITY_SEEDS = {
    "london": ["Westminster", "Camden", "Kensington"],
    "paris": ["Le Marais", "Montmartre", "Saint-Germain-des-Prés"],
    "new york": ["Manhattan", "Brooklyn", "Queens"],
    "tokyo": ["Shibuya", "Shinjuku", "Harajuku"],
    "barcelona": ["Gothic Quarter", "El Born", "Gràcia"],
    "rome": ["Trastevere", "Monti", "Campo de' Fiori"],
}


async def _fetch_london_boroughs() -> List[Dict]:
    """Direct fetch for London's 32 boroughs using Nominatim + Overpass"""
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Find Greater London via Nominatim
            params = {"q": "Greater London, UK", "format": "json", "limit": 3}
            headers = {"User-Agent": "CityGuides/1.0"}
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
                if r.status != 200:
                    return []
                results = await r.json()
                
                area_id = None
                for res in results:
                    if res.get("osm_type") == "relation" and res.get("osm_id"):
                        area_id = 3600000000 + int(res["osm_id"])
                        print(f"[DEBUG] Found London area_id: {area_id}")
                        break
                
                if not area_id:
                    return []
                
                # Step 2: Query Overpass for boroughs
                query = f"""
                [out:json][timeout:30];
                area({area_id})->.searchArea;
                (
                  relation["admin_level"="8"]["boundary"="administrative"](area.searchArea);
                );
                out tags;
                """
                
                async with session.post(OVERPASS_URL, data={"data": query}, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                    print(f"[DEBUG] Overpass status: {resp.status}")
                    if resp.status == 200:
                        j = await resp.json()
                        elements = j.get("elements", [])
                        print(f"[DEBUG] Overpass returned {len(elements)} elements")
                        boroughs = []
                        for el in elements:
                            name = el.get("tags", {}).get("name", "")
                            print(f"[DEBUG] Found: {name}")
                            if name:
                                boroughs.append({
                                    "name": name,
                                    "description": name,
                                    "type": "borough"
                                })
                        return sorted(boroughs, key=lambda x: x["name"])
                    else:
                        text = await resp.text()
                        print(f"[DEBUG] Overpass error: {text[:200]}")
        except Exception as e:
            print(f"[DEBUG] London boroughs fetch failed: {e}")
            import traceback
            traceback.print_exc()
    return []


async def _fetch_neighborhoods_nominatim(city: str) -> List[Dict]:
    """Fetch neighborhoods using Nominatim + Overpass"""
    async with aiohttp.ClientSession() as session:
        # Step 1: Find city via Nominatim
        params = {"q": city, "format": "json", "limit": 5}
        headers = {"User-Agent": "CityGuides/1.0"}
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
                if r.status != 200:
                    return []
                results = await r.json()
                
                area_id = None
                for res in results:
                    if res.get("osm_type") == "relation" and res.get("osm_id"):
                        area_id = 3600000000 + int(res["osm_id"])
                        break
                
                if not area_id:
                    return []
                
                # Step 2: Query Overpass for neighborhoods and boroughs
                query = f"""
                [out:json][timeout:25];
                area({area_id})->.searchArea;
                (
                  relation["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.searchArea);
                  way["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.searchArea);
                  node["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.searchArea);
                  relation["admin_level"="8"]["boundary"="administrative"](area.searchArea);
                );
                out center tags;
                """
                
                async with session.post(OVERPASS_URL, data={"data": query}, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                    if resp.status != 200:
                        return []
                    j = await resp.json()
                    elements = j.get("elements", [])
                    
                    neighborhoods = []
                    seen = set()
                    for el in elements:
                        name = el.get("tags", {}).get("name", "")
                        if name and name.lower() not in seen:
                            seen.add(name.lower())
                            neighborhoods.append({
                                "name": name,
                                "description": name,
                                "type": "culture"
                            })
                    return neighborhoods
                    
        except Exception as e:
            print(f"[DEBUG] Nominatim fetch failed: {e}")
    return []


def get_neighborhood_suggestions(city: str, category: Optional[str] = None) -> List[Dict]:
    """
    Get neighborhood suggestions using Nominatim + Overpass.
    Falls back to seed data if provider returns empty.
    """
    city_key = city.lower().strip()
    if "," in city_key:
        city_key = city_key.split(",")[0].strip()
    
    # Special case: London - use direct borough fetch
    if city_key == "london":
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                boroughs = loop.run_until_complete(_fetch_london_boroughs())
                if len(boroughs) >= 32:
                    print(f"[DEBUG] London: returning {len(boroughs)} boroughs")
                    return boroughs[:32]
            finally:
                loop.close()
        except Exception as e:
            print(f"[DEBUG] London direct fetch failed: {e}")
    
    # General case: Nominatim + Overpass
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            neighborhoods = loop.run_until_complete(_fetch_neighborhoods_nominatim(city_key))
            if len(neighborhoods) >= 4:
                print(f"[DEBUG] {city_key}: returning {len(neighborhoods)} neighborhoods")
                return neighborhoods[:32]
        finally:
            loop.close()
    except Exception as e:
        print(f"[DEBUG] Nominatim+Overpass failed: {e}")
    
    # Fall back to seed data
    seeds = CITY_SEEDS.get(city_key, [])
    print(f"[DEBUG] {city_key}: falling back to {len(seeds)} seed neighborhoods")
    return [
        {"name": name, "description": f"Neighborhood in {city_key.title()}", "type": "culture"}
        for name in seeds
    ]


def is_large_city(city: str) -> bool:
    """Check if city is large enough to warrant neighborhood suggestions"""
    city_key = city.lower().strip()
    if "," in city_key:
        city_key = city_key.split(",")[0].strip()
    return city_key in CITY_SEEDS or city_key in CITY_RELATIONS


def get_neighborhood_bbox(city: str, neighborhood: str) -> Optional[tuple]:
    """Get bounding box for a specific neighborhood"""
    return None
