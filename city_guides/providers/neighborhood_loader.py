"""Neighborhood loading and discovery for TravelLand.
Handles seeded neighborhood data and OSM neighborhood queries.
"""

from typing import Optional, Union, List, Dict
import logging
import aiohttp
import json
from pathlib import Path
import re

from .utils import get_session

def load_seeded_neighborhoods(city: str) -> Optional[List[Dict]]:
    """Load seeded neighborhoods for a city if available, filtered to major divisions.

    Normalizes incoming `city` so values like "Bucharest, Romania" will still
    match a seed file named `bucharest.json`.
    """
    # Normalize input: strip trailing country/token (e.g. "City, Country" -> "City")
    base_city = city.split(',')[0].strip() if city else ''
    city_slug = base_city.lower().replace(' ', '_')
    seed_dir = Path(__file__).parent.parent / 'data' / 'seeded_neighborhoods'
    
    if not seed_dir.exists() or not seed_dir.is_dir():
        logging.warning(f"Seeded neighborhood directory not found: {seed_dir}")
        return None
        
    # Try to find by country, but for now, search all subdirs
    for country_dir in seed_dir.iterdir():
        if country_dir.is_dir():
            seed_file = country_dir / f"{city_slug}.json"
            if seed_file.exists():
                try:
                    with seed_file.open('r', encoding='utf-8') as f:
                        data = json.load(f)
                    neighborhoods = data.get('neighborhoods', [])
                    # Filter to major administrative divisions (wards/districts)
                    suburbs = [n for n in neighborhoods if n.get('tags', {}).get('place') == 'suburb']
                    neighbourhoods = [n for n in neighborhoods if n.get('tags', {}).get('place') == 'neighbourhood']
                    if len(suburbs) >= 10:
                        filtered = suburbs[:100]  # Cap at 100 even for suburbs
                    else:
                        # Include neighbourhoods, but cap total at 100 to avoid overwhelming UI
                        max_neighbourhoods = 100 - len(suburbs)
                        filtered = suburbs + neighbourhoods[:max_neighbourhoods]
                    return filtered if filtered else neighborhoods  # Fallback to all if no matches
                except Exception:
                    pass
    return None

async def fetch_neighborhoods_enhanced(
    city: str,
    lang: str = "en",
    session: Optional[aiohttp.ClientSession] = None,
) -> List[Dict]:
    """Fetch neighborhoods using enhanced OSM queries with better filtering."""
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        # First try to get city area
        area_query = f"""
        [out:json][timeout:25];
        area["name"~"{re.escape(city)}"]["admin_level"~"4|6|8|9"]["boundary"="administrative"];
        out ids;
        """
        async with session.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": area_query},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            areas = [elem for elem in data.get("elements", []) if elem.get("type") == "area"]
            if not areas:
                return []

        # Use the first area found
        area_id = areas[0]["id"]
        area_ref = f"area({area_id})"

        # Query for neighborhoods within the area
        query = f"""
        [out:json][timeout:25];
        {area_ref};
        (
          node["place"~"suburb|neighbourhood"]["name"](area);
          way["place"~"suburb|neighbourhood"]["name"](area);
          relation["place"~"suburb|neighbourhood"]["name"](area);
        );
        out center meta;
        """

        async with session.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        # Process results
        neighborhoods = []
        seen_names = set()
        for elem in data.get("elements", []):
            name = elem.get("tags", {}).get("name")
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            # Get center coordinates
            if elem.get("type") == "node":
                lat, lon = elem.get("lat"), elem.get("lon")
            elif elem.get("center"):
                lat, lon = elem["center"]["lat"], elem["center"]["lon"]
            else:
                continue

            neighborhoods.append({
                "id": f"{elem['type']}/{elem['id']}",
                "name": name,
                "name_local": name,
                "slug": name.lower().replace(' ', '-').replace('/', '-'),
                "center": {"lat": lat, "lon": lon},
                "bbox": None,
                "source": "osm",
                "tags": elem.get("tags", {})
            })

        return neighborhoods[:100]  # Cap at 100

    except Exception as e:
        logging.error(f"Error in fetch_neighborhoods_enhanced: {e}")
        return []
    finally:
        if own:
            await session.__aexit__(None, None, None)

async def async_get_neighborhoods(city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None, lang: str = "en", session: Optional[aiohttp.ClientSession] = None):
    """Best-effort neighborhood lookup using OSM place tags within the city area or a bbox.
    Returns list of dicts: {id, name, slug, center, bbox, source}
    """
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        # Check for seeded neighborhoods first
        if city:
            seeded = load_seeded_neighborhoods(city)
            if seeded:
                return seeded

        area_id = None
        # Only use Nominatim if we don't have coordinates
        if city and not (lat and lon):
            # Try to find an administrative relation for the named city/municipality.
            # This is more reliable than searching for nodes/ways.
            nominatim_url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": city,
                "format": "json",
                "limit": 5,
                "dedupe": 1,
                "addressdetails": 1,
                "extratags": 1,
                "namedetails": 1,
            }
            async with session.get(nominatim_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                results = await resp.json()
                # Find the best administrative area
                for result in results:
                    if result.get("osm_type") == "relation" and result.get("class") == "boundary":
                        area_id = result.get("osm_id")
                        break
                if not area_id:
                    # Fallback to any result
                    if results:
                        area_id = results[0].get("osm_id")

        if area_id:
            area_ref = f"area({area_id})"
        elif lat and lon:
            # Use bbox around coordinates
            bbox_size = 0.05  # ~5km
            area_ref = f"({lat - bbox_size},{lon - bbox_size},{lat + bbox_size},{lon + bbox_size})"
        else:
            return []

        # Query for neighborhoods
        query = f"""
        [out:json][timeout:25];
        {area_ref};
        (
          node["place"~"suburb|neighbourhood"]["name"];
          way["place"~"suburb|neighbourhood"]["name"];
          relation["place"~"suburb|neighbourhood"]["name"];
        );
        out center meta;
        """

        async with session.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        # Process results
        neighborhoods = []
        seen_names = set()
        for elem in data.get("elements", []):
            name = elem.get("tags", {}).get("name")
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            # Get center coordinates
            if elem.get("type") == "node":
                lat, lon = elem.get("lat"), elem.get("lon")
            elif elem.get("center"):
                lat, lon = elem["center"]["lat"], elem["center"]["lon"]
            else:
                continue

            neighborhoods.append({
                "id": f"{elem['type']}/{elem['id']}",
                "name": name,
                "name_local": name,
                "slug": name.lower().replace(' ', '-').replace('/', '-'),
                "center": {"lat": lat, "lon": lon},
                "bbox": None,
                "source": "osm",
                "tags": elem.get("tags", {})
            })

        # Filter to major divisions and cap at 100
        suburbs = [n for n in neighborhoods if n.get('tags', {}).get('place') == 'suburb']
        neighbourhoods = [n for n in neighborhoods if n.get('tags', {}).get('place') == 'neighbourhood']
        if len(suburbs) >= 10:
            filtered = suburbs[:100]
        else:
            max_neighbourhoods = 100 - len(suburbs)
            filtered = suburbs + neighbourhoods[:max_neighbourhoods]

        return filtered[:100] if filtered else neighborhoods[:100]

    except Exception as e:
        logging.error(f"Error in async_get_neighborhoods: {e}")
        return []
    finally:
        if own:
            await session.__aexit__(None, None, None)