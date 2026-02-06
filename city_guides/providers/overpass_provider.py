
"""Canonical Overpass provider implementation.
This file is the canonical implementation — DO NOT create another top-level
`city_guides/overpass_provider.py` file with duplicated implementation.
Before adding any new provider files, search the repository for existing modules
(e.g., `overpass_provider.py`) and prefer adding code to `city_guides/providers/`.
If you must create a top-level shim for compatibility, add a small shim that
re-exports the implementation (see `city_guides/overpass_provider.py` for an example).
"""
from typing import Optional, Union, List, Dict
import logging

import aiohttp
import time
import os
import json
import hashlib
from pathlib import Path
import asyncio
import re

from .utils import get_session

def normalize_city_name(city: Optional[str]) -> Optional[str]:
    if not city:
        return city
    # Map known problematic names to OSM-friendly names
    city = city.strip()
    # Example: 'City of London, United Kingdom' -> 'London'
    if city.lower().startswith("city of london"):
        return "London"
    # Remove country if present
    if "," in city:
        city = city.split(",")[0].strip()
    return city


# Ensure city_guides is importable for submodule imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Geoapify endpoints
GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
GEOAPIFY_REVERSE_URL = "https://api.geoapify.com/v1/geocode/reverse"

def get_geoapify_key() -> Optional[str]:
    return os.getenv("GEOAPIFY_API_KEY")

async def geoapify_geocode_city(city: str, session: Optional[aiohttp.ClientSession] = None):
    city = normalize_city_name(city)
    api_key = get_geoapify_key()
    if not api_key:
        return None
    params = {"text": city, "format": "json", "apiKey": api_key, "limit": 1}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    if session is None:
        async with get_session() as session:
            return await _geoapify_geocode_city_impl(city, params, headers, session)
    else:
        return await _geoapify_geocode_city_impl(city, params, headers, session)


async def _geoapify_geocode_city_impl(city: str, params, headers, session):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(GEOAPIFY_GEOCODE_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                return None
            j = await r.json()
            results = j.get("results", [])
            if not results:
                return None
            result = results[0]
            bbox_dict = result.get("bbox")
            if bbox_dict:
                # Geoapify bbox: {'lon1': minlon, 'lat1': minlat, 'lon2': maxlon, 'lat2': maxlat}
                minlon = bbox_dict.get("lon1")
                minlat = bbox_dict.get("lat1")
                maxlon = bbox_dict.get("lon2")
                maxlat = bbox_dict.get("lat2")
                if all(x is not None for x in [minlon, minlat, maxlon, maxlat]):
                    # Return bbox in (west, south, east, north) order to match geocode_city/discover_pois
                    return (minlon, minlat, maxlon, maxlat)
            # fallback: use lat/lon with small buffer (ensure ordering: west, south, east, north)
            # 'result' is the geocoding result dict
            lat = result.get("lat") if isinstance(result, dict) else None
            lon = result.get("lon") if isinstance(result, dict) else None
            try:
                if lat is not None:
                    lat = float(lat)
                if lon is not None:
                    lon = float(lon)
            except Exception:
                lat = None
                lon = None
            if lat is not None and lon is not None:
                buf = 0.05
                return (lon-buf, lat-buf, lon+buf, lat+buf)
            return None
    except Exception:
        return None

async def geoapify_reverse_geocode(lat, lon, session: Optional[aiohttp.ClientSession] = None):
    api_key = get_geoapify_key()
    if not api_key:
        return ""
    params = {"lat": lat, "lon": lon, "format": "json", "apiKey": api_key}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    if session is None:
        async with get_session() as session:
            return await _geoapify_reverse_geocode_impl(params, headers, session)
    else:
        return await _geoapify_reverse_geocode_impl(params, headers, session)


async def _geoapify_reverse_geocode_impl(params, headers, session):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(GEOAPIFY_REVERSE_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                return ""
            j = await r.json()
            features = j.get("features", [])
            if not features:
                return ""
            prop = features[0].get("properties", {})
            addr = prop.get("formatted", "")
            return addr
    except Exception:
        return ""

# --- GEOAPIFY POI SEARCH ---
GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"

# Enhanced neighborhood fetching with disambiguation (Nominatim is used last as a fallback)
from city_guides.src.neighborhood_disambiguator import NeighborhoodDisambiguator

async def fetch_neighborhoods_enhanced(
    city: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    session: Optional[aiohttp.ClientSession] = None
) -> List[Dict]:
    """
    Enhanced neighborhood fetching with disambiguation for problematic cases
    Nominatim is used as a LAST resort when other sources don't provide good results.
    """
    logger = logging.getLogger(__name__)
    neighborhoods = []

    # 1) Try reverse-geocode (Geoapify) when coordinates available (prefered)
    if lat and lon:
        try:
            geoapify_data = await geoapify_reverse_geocode(lat, lon, session)
            if geoapify_data:
                parts = [p.strip() for p in geoapify_data.split(',') if p.strip()]
                for part in parts:
                    if len(part) > 3:
                        neighborhoods.append({
                            'name': part,
                            'display_name': part,
                            'source': 'geoapify'
                        })
        except Exception as e:
            logger.debug(f"Geoapify reverse geocode failed: {e}")

    # 2) Optionally other providers could be added here (OpenTripMap, Overpass heuristics)
    # (left intentionally minimal to avoid changing existing flow)

    # 3) As a last resort, try Nominatim by city name (only if we have no decent candidates)
    if not neighborhoods and city:
        try:
            url = f"{NOMINATIM_URL}?q={city}&format=json&addressdetails=1&limit=50"
            headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
            if session is None:
                async with get_session() as session:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                        if r.status == 200:
                            data = await r.json()
                            for item in data:
                                addr = item.get('address', {})
                                for key in ['suburb', 'neighbourhood', 'quarter', 'district']:
                                    if key in addr:
                                        neighborhoods.append({
                                            'name': addr[key],
                                            'display_name': addr[key],
                                            'source': 'nominatim'
                                        })
            else:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        data = await r.json()
                        for item in data:
                            addr = item.get('address', {})
                            for key in ['suburb', 'neighbourhood', 'quarter', 'district']:
                                if key in addr:
                                    neighborhoods.append({
                                        'name': addr[key],
                                        'display_name': addr[key],
                                        'source': 'nominatim'
                                    })
        except Exception as e:
            logger.debug(f"Nominatim neighborhood fetch failed: {e}")

    # Apply disambiguation and deduplication
    disambiguator = NeighborhoodDisambiguator()
    names = [n.get('name') or n.get('display_name') for n in neighborhoods]
    names = [n for n in names if n]
    unique_names = disambiguator.deduplicate_neighborhoods(names, city)

    ranked = []
    for name in unique_names:
        is_valid, confidence, canonical = disambiguator.validate_neighborhood(name, city)
        ranked.append({
            'name': canonical or name,
            'display_name': canonical or name,
            'label': canonical or name,
            'id': canonical or name,
            'confidence': confidence,
            'is_valid': is_valid
        })

    ranked.sort(key=lambda x: x['confidence'], reverse=True)
    filtered = [n for n in ranked if n['confidence'] >= 0.6]

    logger.info(f"Neighborhoods for {city}: {len(neighborhoods)} raw → {len(unique_names)} unique → {len(filtered)} high-confidence")

    return filtered


# Mapping from our normalized poi_type keys to Geoapify 'categories' strings.
# This provides broader, more specific category coverage for common poi_type values.
GEOAPIFY_CATEGORIES = {
    "restaurant": "catering.restaurant,catering.cafe,catering.fast_food",
    "coffee": "catering.cafe,catering.coffee_shop",
    "park": "leisure.park,leisure.garden,leisure.nature_reserve",
    "historic": "building.historic,heritage.historic",
    "museum": "entertainment.museum,entertainment.art_gallery",
    "market": "commercial.marketplace",
    "transport": "transport",
    "family": "leisure.playground,leisure.amusement_arcade,leisure.miniature_golf",
    "event": "entertainment.theatre,entertainment.cinema,entertainment.arts_centre",
    "hotel": "accommodation.hotel,accommodation.hostel",
    "shopping": "commercial.shopping_mall,commercial.retail",
    "nightlife": "catering.bar,catering.pub",
    "local": "tourism.attraction",
    "hidden": "tourism.attraction",
}

async def geoapify_discover_pois(
    bbox: Optional[Union[list[float], tuple[float, float, float, float]]],
    kinds: Optional[str] = None,
    poi_type: Optional[str] = None,
    limit: int = 200,
    session: Optional[aiohttp.ClientSession] = None,
) -> list[dict]:
    """Discover POIs using Geoapify Places API, normalized to Overpass-like output.
    If `kinds` is not provided, a best-effort mapping from `poi_type` to Geoapify
    categories will be used via the `GEOAPIFY_CATEGORIES` constant."""
    api_key = get_geoapify_key()
    if not api_key:
        print("[DEBUG] Geoapify API key missing!")
    if not bbox or len(bbox) != 4:
        print(f"[DEBUG] Invalid bbox for geoapify_discover_pois: {bbox}")
    if not api_key or not bbox or len(bbox) != 4:
        return []
    # bbox format: (west, south, east, north)
    west, south, east, north = bbox
    # Prepare pagination-aware requests: Geoapify enforces max limit=500 per request.
    requested_limit = int(limit)
    per_request_max = 500
    params_base = {
        "filter": f"rect:{west},{south},{east},{north}",
        "apiKey": api_key,
        "format": "json",
    }
    if kinds:
        params_base["categories"] = kinds
    else:
        # Use explicit mapping for poi_type when available, otherwise fall back to a broad default
        if poi_type and poi_type in GEOAPIFY_CATEGORIES:
            params_base["categories"] = GEOAPIFY_CATEGORIES[poi_type]
        else:
            params_base["categories"] = ",".join([
                "tourism","catering","entertainment","leisure","commercial","healthcare","education"
            ])

    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    if session is None:
        async with get_session() as session:
            return await _geoapify_discover_pois_impl(bbox, requested_limit, per_request_max, params_base, headers, session)
    else:
        return await _geoapify_discover_pois_impl(bbox, requested_limit, per_request_max, params_base, headers, session)


async def _geoapify_discover_pois_impl(bbox, requested_limit, per_request_max, params_base, headers, session):
    out = []
    own = False
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        offset = 0
        remaining = requested_limit
        while remaining > 0:
            per_request = per_request_max if remaining > per_request_max else remaining
            params = params_base.copy()
            params["limit"] = str(per_request)
            if offset:
                params["offset"] = str(offset)

            async with session.get(GEOAPIFY_PLACES_URL, params=params, headers=headers, timeout=timeout) as r:
                if r.status != 200:
                    print(f"[DEBUG] Geoapify HTTP error: status={r.status} url={r.url}")
                    if own:
                        await session.close()
                    return out
                j = await r.json()
                features = j.get("features", [])
                if not features:
                    # no more results
                    break
                for feat in features:
                    prop = feat.get("properties", {})
                    name = prop.get("name") or prop.get("address_line1") or "Unnamed"
                    lat = prop.get("lat")
                    lon = prop.get("lon")
                    # Use robust address normalization
                    address = normalize_address(prop)
                    # Skip venues without valid readable addresses
                    if not is_valid_address(address):
                        print(f"[DEBUG] Skipping venue '{name}' - no valid address (coords: {lat}, {lon})")
                        continue
                    website = prop.get("website")
                    kinds_str = prop.get("categories", "")
                    osm_url = prop.get("datasource", {}).get("url")
                    entry = {
                        "osm_id": prop.get("place_id"),
                        "name": name,
                        "website": website,
                        "osm_url": osm_url,
                        "amenity": kinds_str,
                        "address": address,
                        "lat": lat,
                        "lon": lon,
                        "tags": kinds_str,
                        "source": "geoapify",
                        "provider": "geoapify",
                    }
                    out.append(entry)

                fetched = len(features)
                # advance offset and remaining
                offset += fetched
                remaining -= fetched
                if fetched < per_request:
                    # fewer results than requested; end pagination
                    break

        # return up to the originally requested limit
        return out[:requested_limit]
    except Exception as e:
        print(f"[DEBUG] Exception in geoapify_discover_pois: {e}")
        return out

def normalize_address(prop: dict) -> Optional[str]:
    """
    Construct a human-readable address from Geoapify properties.
    Falls back through multiple strategies to ensure we never return None/empty.
    Returns None only if no address components are available.
    """
    if not isinstance(prop, dict):
        return None
    
    # Strategy 1: Use pre-formatted address if available
    formatted = prop.get("formatted")
    if formatted and len(formatted.strip()) > 5:  # Ensure it's not just a number
        return formatted.strip()
    
    # Strategy 2: Use address_line1
    addr_line1 = prop.get("address_line1")
    if addr_line1 and len(addr_line1.strip()) > 3:
        return addr_line1.strip()
    
    # Strategy 3: Build from components
    parts = []
    
    # Street + house number
    street = prop.get("street")
    housenumber = prop.get("housenumber")
    if street and housenumber:
        parts.append(f"{street} {housenumber}")
    elif street:
        parts.append(street)
    elif housenumber:
        parts.append(f"{housenumber}")
    
    # District/Suburb/Neighborhood
    district = prop.get("district") or prop.get("suburb") or prop.get("neighbourhood")
    if district and district not in parts:
        parts.append(district)
    
    # City
    city = prop.get("city")
    if city and city not in parts:
        parts.append(city)
    
    # Postcode
    postcode = prop.get("postcode")
    if postcode:
        parts.append(postcode)
    
    # Country
    country = prop.get("country")
    if country and len(parts) > 0:
        parts.append(country)
    
    if len(parts) >= 2:  # Need at least street-level + city-level
        return ", ".join(parts)
    
    # Strategy 4: Last resort - use name + district/city
    name = prop.get("name")
    if name and district:
        return f"{name}, {district}"
    if name and city:
        return f"{name}, {city}"
    
    return None


def is_valid_address(address: Optional[str]) -> bool:
    """
    Validate that an address is readable and not just coordinates.
    Rejects coordinate-only strings and very short addresses.
    """
    if not address:
        return False
    
    addr = str(address).strip()
    
    # Reject if too short
    if len(addr) < 5:
        return False
    
    # Extract just the address part (remove emoji and prefixes)
    # Remove common prefixes that might be added
    cleaned = addr
    for prefix in ['📍', '📍 ', 'Approximate location:', 'Location:', 'Address:']:
        cleaned = cleaned.replace(prefix, '').strip()
    
    # Reject if it looks like coordinates (contains lat/lon pattern)
    # Pattern: two numbers separated by comma, possibly with decimals
    coord_pattern = r'^\s*-?\d+\.?\d*\s*,\s*-?\d+\.?\d*\s*$'
    if _re.match(coord_pattern, cleaned):
        return False
    
    # Must contain at least one letter (not just numbers/symbols)
    if not _re.search(r'[a-zA-Z]', cleaned):
        return False
    
    return True


# Move re import to top level for performance
import re as _re

# --- OPENTRIPMAP POI SEARCH ---
OPENTRIPMAP_API_URL = "https://api.opentripmap.com/0.1/en/places/bbox"

def get_opentripmap_key() -> Optional[str]:
    return os.getenv("OPENTRIPMAP_KEY")

async def opentripmap_discover_pois(
    bbox: Optional[Union[list[float], tuple[float, float, float, float]]],
    kinds: Optional[str] = None,
    limit: int = 200,
    session: Optional[aiohttp.ClientSession] = None,
) -> list[dict]:
    """Discover POIs using Opentripmap API, normalized to Overpass-like output."""
    api_key = get_opentripmap_key()
    if not api_key:
        print("[DEBUG] Opentripmap API key missing!")
    if not bbox or len(bbox) != 4:
        print(f"[DEBUG] Invalid bbox for opentripmap_discover_pois: {bbox}")
    if not api_key or not bbox or len(bbox) != 4:
        return []
    # bbox format: (west, south, east, north)
    west, south, east, north = bbox
    params = {
        "lon_min": west,
        "lat_min": south,
        "lon_max": east,
        "lat_max": north,
        "apikey": api_key,
        "limit": str(limit),
        "format": "json",
    }
    if kinds:
        params["kinds"] = kinds
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    if session is None:
        async with get_session() as session:
            return await _opentripmap_discover_pois_impl(params, headers, session)
    else:
        return await _opentripmap_discover_pois_impl(params, headers, session)


async def _opentripmap_discover_pois_impl(params, headers, session):
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with session.get(OPENTRIPMAP_API_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                print(f"[DEBUG] Opentripmap HTTP error: status={r.status} url={r.url}")
                return []
            j = await r.json()
            features = j.get("features", []) if isinstance(j, dict) else j
            out = []
            for feat in features:
                prop = feat.get("properties", feat)  # sometimes flat
                name = prop.get("name") or prop.get("address_line1") or "Unnamed"
                lat = prop.get("lat") or prop.get("point", {}).get("lat") or prop.get("geometry", {}).get("coordinates", [None, None])[1]
                lon = prop.get("lon") or prop.get("point", {}).get("lon") or prop.get("geometry", {}).get("coordinates", [None, None])[0]
                address = prop.get("address") or prop.get("address_line1")
                website = prop.get("url") or prop.get("website")
                kinds_str = prop.get("kinds", "")
                xid = prop.get("xid") or prop.get("id")
                osm_url = f"https://opentripmap.com/en/card/{xid}" if xid else None
                entry = {
                    "osm_id": xid,
                    "name": name,
                    "website": website,
                    "osm_url": osm_url,
                    "amenity": kinds_str,
                    "address": address,
                    "lat": lat,
                    "lon": lon,
                    "tags": kinds_str,
                    "source": "opentripmap",
                    "provider": "opentripmap",
                }
                out.append(entry)
            return out
    except Exception as e:
        print(f"[DEBUG] Exception in opentripmap_discover_pois: {e}")
        return []


# Expanded list of public Overpass API endpoints for global, robust failover
OVERPASS_URLS = [
    "https://overpass.osm.jp/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Mock data for fallback when all external providers fail
# Used to ensure the application still provides results for testing/demo
MOCK_POI_DATA = {
    "restaurant": [
        {"name": "The Golden Fork", "amenity": "restaurant", "cuisine": "italian"},
        {"name": "Café Central", "amenity": "cafe", "cuisine": "coffee_shop"},
        {"name": "Spice Garden", "amenity": "restaurant", "cuisine": "indian"},
        {"name": "The Local Pub", "amenity": "pub", "cuisine": "british"},
        {"name": "Sushi Master", "amenity": "restaurant", "cuisine": "japanese"},
    ],
    "historic": [
        {"name": "Historic Monument", "tourism": "attraction", "historic": "monument"},
        {"name": "Old Town Hall", "tourism": "attraction", "historic": "building"},
        {"name": "City Museum", "tourism": "museum", "historic": "museum"},
        {"name": "Ancient Castle", "tourism": "attraction", "historic": "castle"},
        {"name": "Memorial Square", "tourism": "attraction", "historic": "memorial"},
    ],
    "museum": [
        {"name": "Art Museum", "tourism": "museum", "museum": "art"},
        {"name": "History Museum", "tourism": "museum", "museum": "history"},
        {"name": "Science Center", "tourism": "museum", "museum": "science"},
    ],
    "park": [
        {"name": "Central Park", "leisure": "park", "park": "public"},
        {"name": "Botanical Gardens", "leisure": "park", "park": "botanical"},
        {"name": "River Walk", "leisure": "park", "park": "riverside"},
    ],
    "market": [
        {"name": "Central Market", "amenity": "marketplace", "shop": "market"},
        {"name": "Farmers Market", "amenity": "marketplace", "shop": "farm"},
        {"name": "Flea Market", "amenity": "marketplace", "shop": "second_hand"},
    ],
    "coffee": [
        {"name": "Morning Brew", "amenity": "cafe", "cuisine": "coffee_shop"},
        {"name": "The Daily Grind", "amenity": "cafe", "cuisine": "coffee_shop"},
        {"name": "Espresso Bar", "amenity": "cafe", "cuisine": "coffee_shop"},
    ],
}


async def reverse_geocode(lat, lon, session: Optional[aiohttp.ClientSession] = None):
    # Cache reverse geocodes to minimize API calls
    cache_dir = Path(__file__).parent / ".cache" / "nominatim"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    cache_key = f"{lat:.6f},{lon:.6f}"
    cache_file = cache_dir / f"{hashlib.md5(cache_key.encode()).hexdigest()}.json"
    if cache_file.exists():
        try:
            with cache_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    if session is None:
        async with get_session() as session:
            return await _reverse_geocode_impl(url, headers, cache_file, lat, lon, session)
    else:
        return await _reverse_geocode_impl(url, headers, cache_file, lat, lon, session)


async def _reverse_geocode_impl(url, headers, cache_file, lat, lon, session):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(url, headers=headers, timeout=timeout) as r:
            if r.status == 200:
                j = await r.json()
                addr = j.get("display_name", "")
                try:
                    cache_file.write_text(json.dumps(addr), encoding="utf-8")
                except Exception:
                    pass
                return addr
    except Exception:
        pass
    # Fallback to Geoapify
    addr = await geoapify_reverse_geocode(lat, lon, session=session)
    try:
        cache_file.write_text(json.dumps(addr), encoding="utf-8")
    except Exception:
        pass
    return addr


async def async_reverse_geocode(lat, lon, session: Optional[aiohttp.ClientSession] = None):
    cache_dir = Path(__file__).parent / ".cache" / "nominatim"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    cache_key = f"{lat:.6f},{lon:.6f}"
    cache_file = cache_dir / f"{hashlib.md5(cache_key.encode()).hexdigest()}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    if session is None:
        async with get_session() as session:
            return await _async_reverse_geocode_impl(url, headers, cache_file, session)
    else:
        return await _async_reverse_geocode_impl(url, headers, cache_file, session)


async def _async_reverse_geocode_impl(url, headers, cache_file, session):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(url, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                return ""
            j = await r.json()
            addr = j.get("display_name", "")
            try:
                cache_file.write_text(json.dumps(addr), encoding="utf-8")
            except Exception:
                pass
            return addr
    except Exception:
        return ""


async def geocode_city(city: str, session: Optional[aiohttp.ClientSession] = None):
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    if session is None:
        async with get_session() as session:
            return await _geocode_city_impl(city, params, headers, session)
    else:
        return await _geocode_city_impl(city, params, headers, session)


async def _geocode_city_impl(city, params, headers, session):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status == 200:
                j = await r.json()
                if j:
                    entry = j[0]
                    bbox = entry.get("boundingbox")
                    if bbox and len(bbox) == 4:
                        south, north, west, east = (
                            float(bbox[0]),
                            float(bbox[1]),
                            float(bbox[2]),
                            float(bbox[3]),
                        )
                        return (west, south, east, north)
    except Exception:
        pass
    
    # Fallback to Geoapify
    bbox = await geoapify_geocode_city(city, session=session)
    if bbox:
        return bbox
    
    # Hardcoded fallback for common cities when external services are unavailable
    # Format: (west, south, east, north)
    CITY_FALLBACKS = {
        "london": (-0.51, 51.28, 0.33, 51.69),
        "paris": (2.22, 48.82, 2.47, 48.90),
        "new york": (-74.26, 40.47, -73.70, 40.92),
        "tokyo": (139.56, 35.53, 139.92, 35.82),
        "rome": (12.37, 41.80, 12.59, 42.00),
        "barcelona": (2.05, 41.32, 2.23, 41.47),
        "madrid": (-3.83, 40.31, -3.56, 40.56),
        "berlin": (13.23, 52.40, 13.60, 52.63),
        "amsterdam": (4.72, 52.27, 5.08, 52.43),
        "dublin": (-6.39, 53.29, -6.11, 53.41),
        "lisbon": (-9.23, 38.69, -9.09, 38.80),
        "prague": (14.32, 50.00, 14.60, 50.14),
        "vienna": (16.18, 48.12, 16.57, 48.32),
        "budapest": (19.00, 47.42, 19.15, 47.56),
        "athens": (23.65, 37.92, 23.80, 38.05),
        "istanbul": (28.85, 40.96, 29.10, 41.14),
        "moscow": (37.32, 55.58, 37.89, 55.92),
        "stockholm": (17.87, 59.27, 18.15, 59.40),
        "copenhagen": (12.45, 55.62, 12.65, 55.72),
        "oslo": (10.61, 59.88, 10.85, 59.96),
        "helsinki": (24.78, 60.13, 25.10, 60.24),
        "sydney": (151.01, -33.95, 151.34, -33.79),
        "melbourne": (144.87, -37.90, 145.04, -37.73),
        "singapore": (103.61, 1.22, 104.04, 1.47),
        "hong kong": (113.99, 22.23, 114.38, 22.51),
        "seoul": (126.76, 37.43, 127.18, 37.70),
        "mumbai": (72.77, 18.89, 72.98, 19.27),
        "delhi": (77.05, 28.49, 77.34, 28.76),
        "bangkok": (100.46, 13.65, 100.64, 13.83),
        "dubai": (55.13, 25.06, 55.50, 25.36),
        "cairo": (31.13, 29.95, 31.47, 30.13),
        "johannesburg": (27.90, -26.27, 28.18, -26.08),
        "rio de janeiro": (-43.79, -23.08, -43.11, -22.75),
        "buenos aires": (-58.53, -34.71, -58.33, -34.52),
        "mexico city": (-99.36, 19.25, -99.00, 19.59),
        "toronto": (-79.64, 43.58, -79.12, 43.85),
        "vancouver": (-123.27, 49.20, -122.98, 49.32),
        "chicago": (-87.94, 41.64, -87.52, 42.02),
        "los angeles": (-118.67, 33.70, -118.16, 34.34),
        "san francisco": (-122.52, 37.70, -122.35, 37.81),
        "seattle": (-122.44, 47.49, -122.24, 47.73),
        "miami": (-80.32, 25.71, -80.12, 25.85),
        "boston": (-71.19, 42.23, -71.00, 42.40),
    }
    
    # Normalize city name for exact or prefix lookup
    city_normalized = city.lower().strip()
    # First try exact match
    if city_normalized in CITY_FALLBACKS:
        return CITY_FALLBACKS[city_normalized]
    # Then try prefix match (handles "London, UK" matching "london")
    for city_key, city_bbox in CITY_FALLBACKS.items():
        if city_normalized.startswith(city_key + ",") or city_normalized.startswith(city_key + " "):
            return city_bbox
    
    return None


async def async_geocode_city(city: str, session: Optional[aiohttp.ClientSession] = None):
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    if session is None:
        async with get_session() as session:
            return await _async_geocode_city_impl(params, headers, session)
    else:
        return await _async_geocode_city_impl(params, headers, session)


async def _async_geocode_city_impl(params, headers, session):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                return None
            j = await r.json()
            if not j:
                return None
            entry = j[0]
            bbox = entry.get("boundingbox")
            if bbox and len(bbox) == 4:
                south, north, west, east = (
                    float(bbox[0]),
                    float(bbox[1]),
                    float(bbox[2]),
                    float(bbox[3]),
                )
                return (west, south, east, north)
            return None
    except Exception:
        return None


async def async_get_neighborhoods(city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None, lang: str = "en", session: Optional[aiohttp.ClientSession] = None):
    """Best-effort neighborhood lookup using OSM place tags within the city area or a bbox.

    Returns list of dicts: {id, name, slug, center, bbox, source}
    """
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        area_id = None
        # Only use Nominatim if we don't have coordinates
        if city and not (lat and lon):
            # Try to find an administrative relation for the named city/municipality.
            params = {"q": city, "format": "json", "limit": 10, "addressdetails": 1}
            headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": lang}
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
                    if r.status == 200:
                        j = await r.json()
                        if j:
                            # Prefer an explicit relation result (administrative boundary)
                            relation_candidate = None
                            for res in j:
                                try:
                                    if res.get("osm_type") == "relation" and res.get("osm_id"):
                                        relation_candidate = res
                                        break
                                except Exception:
                                    continue

                            # If none found, try to locate an administrative/boundary-type result
                            if not relation_candidate:
                                for res in j:
                                    try:
                                        cls = (res.get("class") or "").lower()
                                        typ = (res.get("type") or "").lower()
                                        if (cls == "boundary" and typ == "administrative") or (typ == "administrative"):
                                            if res.get("osm_type") == "relation" and res.get("osm_id"):
                                                relation_candidate = res
                                                break
                                    except Exception:
                                        continue

                            if relation_candidate and relation_candidate.get("osm_id"):
                                try:
                                    area_id = 3600000000 + int(relation_candidate["osm_id"])  # relation -> area id
                                except Exception:
                                    area_id = None
            except Exception:
                pass

        # build query
        if area_id:
            # For major cities, also search for admin_level=8 (boroughs/districts) in addition to place tags
            q = f"""
                [out:json][timeout:25];
                area({area_id})->.cityArea;
                (
                  relation["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.cityArea);
                  way["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.cityArea);
                  node["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.cityArea);
                  relation["admin_level"="8"]["boundary"="administrative"](area.cityArea);
                );
                out center tags;
            """
        else:
            # Use provided coordinates or fallback to bbox
            if lat and lon:
                # Use around() query with provided coordinates
                radius = float(os.getenv("NEIGHBORHOOD_DEFAULT_BUFFER_KM", 8.0))
                q = f"""
                    [out:json][timeout:25];
                    (
                      relation["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](around:{radius*1000},{lat},{lon});
                      way["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](around:{radius*1000},{lat},{lon});
                      node["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](around:{radius*1000},{lat},{lon});
                    );
                    out center tags;
                """
            else:
                # Fallback to bbox query (only when no lat/lon provided)
                bbox_str = None
                if city:
                    bb = await async_geocode_city(city, session=session)
                    if bb:
                        # async_geocode_city returns (west, south, east, north)
                        west, south, east, north = bb
                        bbox_str = f"{south},{west},{north},{east}"

                if not bbox_str:
                    return []

                q = f"""
                    [out:json][timeout:25];
                    (
                      relation["place"~"neighbourhood|suburb|quarter|city_district|district|locality"]({bbox_str});
                      way["place"~"neighbourhood|suburb|quarter|city_district|district|locality"]({bbox_str});
                      node["place"~"neighbourhood|suburb|quarter|city_district|district|locality"]({bbox_str});
                    );
                    out center tags;
                """

        # call overpass endpoints
        results = []
        for url in OVERPASS_URLS:
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with session.post(url, data={"data": q}, timeout=timeout) as resp:
                    if resp.status != 200:
                        continue
                    j = await resp.json()
                    elements = j.get("elements", [])
                    if elements and not results:
                        # Only append once per successful Overpass response to avoid duplicates across endpoints
                        results.extend([
                            {
                                "id": f"{el.get('type')}/{el.get('id')}",
                                "name": el.get("tags", {}).get("name:en") or el.get("tags", {}).get("name"),
                                "name_local": el.get("tags", {}).get("name"),
                                "slug": re.sub(r"[^a-z0-9]+", "_", (el.get("tags", {}).get("name:en") or el.get("tags", {}).get("name") or "").lower()).strip("_"),
                                "center": ({"lat": el["center"]["lat"], "lon": el["center"]["lon"]} if "center" in el else ({"lat": el.get("lat"), "lon": el.get("lon")} if ("lat" in el and "lon" in el) else None)),
                                "bbox": (el.get("bounds") or el.get("bbox") if el.get("type") == "relation" else None) or ( [ (el["center"]["lon"] - 0.01), (el["center"]["lat"] - 0.01), (el["center"]["lon"] + 0.01), (el["center"]["lat"] + 0.01) ] if "center" in el else None),
                                "source": "osm",
                                "tags": el.get("tags", {}),
                            }
                            for el in elements if el.get("tags", {}).get("name")
                        ])
            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

        # Always attempt GeoNames fallback if configured; merge into results or return geonames-only
        geonames_user = os.getenv("GEONAMES_USERNAME")
        if geonames_user:
            try:
                import geonames_provider
                geores = await geonames_provider.async_get_neighborhoods_geonames(
                    city=city, lat=lat, lon=lon, session=session
                )
                if geores:
                    if not results:
                        return geores
                    # merge unique geonames entries by slug, name, or proximity
                    def _is_near(a_center, b_center, thresh_deg=0.02):
                        if not a_center or not b_center:
                            return False
                        try:
                            return (
                                abs(float(a_center.get("lat", 0)) - float(b_center.get("lat", 0))) <= thresh_deg
                                and abs(float(a_center.get("lon", 0)) - float(b_center.get("lon", 0))) <= thresh_deg
                            )
                        except Exception:
                            return False

                    existing = list(results)
                    slugs = set(r.get("slug") for r in existing if r.get("slug"))
                    names = set((r.get("name") or "").lower() for r in existing)
                    for g in geores:
                        gslug = g.get("slug")
                        gname = (g.get("name") or "").lower()
                        gcenter = g.get("center")
                        duplicate = False
                        if (gslug and gslug in slugs) or (gname and gname in names):
                            duplicate = True
                        else:
                            for r in existing:
                                if _is_near(r.get("center"), gcenter):
                                    duplicate = True
                                    break
                        if not duplicate:
                            results.append(g)
            except Exception:
                pass

        # As an extra safety, if we have coordinates and GeoNames configured, call findNearbyPlaceName
        # directly and append any entries not already present. This ensures small localities (e.g., Las Liebres)
        # are included even when other fallbacks miss them.
        geonames_user = os.getenv("GEONAMES_USERNAME")
        if geonames_user and lat and lon:
            try:
                gparams = {"username": geonames_user, "lat": lat, "lng": lon, "radius": int(os.getenv("GEONAMES_RADIUS_KM", "20")), "maxRows": int(os.getenv("GEONAMES_MAX_ROWS", "20"))}
                # Use a fresh session for GeoNames to avoid potential session-level blocking
                async with get_session() as gsession:
                    async with gsession.get("http://api.geonames.org/findNearbyPlaceNameJSON", params=gparams, timeout=aiohttp.ClientTimeout(total=10)) as gr:
                        if gr.status == 200:
                            gj = await gr.json()
                            gentries = []
                            for g in gj.get("geonames", []):
                                name = g.get("name") or g.get("toponymName")
                                if not name:
                                    continue
                                geoid = g.get("geonameId")
                                latv = g.get("lat")
                                lonv = g.get("lng") or g.get("lon")
                                center = None
                                try:
                                    if latv and lonv:
                                        center = {"lat": float(latv), "lon": float(lonv)}
                                except Exception:
                                    center = None
                                bbox = None
                                if "north" in g or "south" in g:
                                    try:
                                        bbox = [float(g.get("west")), float(g.get("south")), float(g.get("east")), float(g.get("north"))]
                                    except Exception:
                                        bbox = None
                                gentries.append({
                                    "id": f"geonames/{geoid}",
                                    "name": name,
                                    "slug": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
                                    "center": center,
                                    "bbox": bbox,
                                    "source": "geonames",
                                })

                            # merge any that are not duplicates
                            existing = list(results)
                            slugs = set(r.get("slug") for r in existing if r.get("slug"))
                            names = set((r.get("name") or "").lower() for r in existing)
                            def _is_near(a_center, b_center, thresh_deg=0.02):
                                if not a_center or not b_center:
                                    return False
                                try:
                                    return (
                                        abs(float(a_center.get("lat", 0)) - float(b_center.get("lat", 0))) <= thresh_deg
                                        and abs(float(a_center.get("lon", 0)) - float(b_center.get("lon", 0))) <= thresh_deg
                                    )
                                except Exception:
                                    return False

                            for g in gentries:
                                gslug = g.get("slug")
                                gname = (g.get("name") or "").lower()
                                gcenter = g.get("center")
                                duplicate = False
                                if (gslug and gslug in slugs) or (gname and gname in names):
                                    duplicate = True
                                else:
                                    for r in existing:
                                        if _is_near(r.get("center"), gcenter):
                                            duplicate = True
                                            break
                                if not duplicate:
                                    results.append(g)
            except Exception:
                pass

        return results

    finally:
        if own:
            await session.close()


def _singularize(word: str) -> str:
    w = (word or "").lower().strip()
    if w.endswith("ies") and len(w) > 3:
        return w[:-3] + "y"
    if w.endswith("'s"):
        w = w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


# Expanded list of known chain restaurants to exclude for "Local Only" filter
CHAIN_KEYWORDS = [
    "chipotle",
    "qdoba",
    "taco bell",
    "moe's",
    "baja fresh",
    "del taco",
    "rubio's",
    "mexican grill",
    "taco time",
    "jack in the box",
    "mcdonald's",
    "burger king",
    "wendy's",
    "subway",
    "starbucks",
    "dunkin'",
    "kfc",
    "pizza hut",
    "domino's",
    "papa john's",
    "little caesars",
    "applebee's",
    "chili's",
    "tgif",
    "olive garden",
    "red lobster",
    "outback",
    "panera",
    "five guys",
    "smashburger",
    "shake shack",
    "culver's",
    "in-n-out",
    "sonic",
    "arbys",
    "hardee's",
    "carl's jr",
    "white castle",
    "steak n shake",
    "buffalo wild wings",
    "denny's",
    "ihop",
    "waffle house",
    "cracker barrel",
    "cheesecake factory",
    "panda express",
    "pf changs",
    "pei wei",
    "jason's deli",
    "firehouse subs",
    "jersey mike's",
    "jimmy john's",
    "potbelly",
    "quiznos",
    "mcallister's",
    "zaxby's",
    "canes",
    "raising cane's",
    "popeyes",
    "church's",
    "wingstop",
    "dairy queen",
    "a&w",
    "fuddruckers",
    "johnny rockets",
    "red robin",
    "ruby tuesday",
    "bj's",
    "yard house",
    "cheddar's",
    "bob evans",
    "perkins",
    "hooters",
    "texas roadhouse",
    "longhorn",
    "maggiano's",
    "carrabba's",
    "bonefish",
    "p.f. chang's",
    "papa murphy's",
    "cicis",
    "chuck e. cheese",
    "mod pizza",
    "blaze pizza",
    "marcos pizza",
    "hungry howies",
    "round table pizza",
    "jet's pizza",
    "village inn",
    "steak'n shake",
    "portillo's",
    "whataburger",
    "bojangles",
    "biscuitville",
    "bob evans",
    "friendly's",
    "perkins",
    "huddle house",
    "taco bueno",
    "taco john's",
    "fazoli's",
    "captain d's",
    "long john silver's",
    "boston market",
    "sweetgreen",
    "dig inn",
    "chopt",
    "salata",
    "tropical smoothie",
    "smoothie king",
    "jamba juice",
    "cold stone",
    "baskin robbins",
    "ben & jerry's",
    "dq grill",
    "freddy's",
    "jollibee",
    "habit burger",
    "bubba's 33",
    "steak 'n shake",
    "twin peaks",
    "hooters",
    "logans roadhouse",
    "golden corral",
    "old country buffet",
    "shoney's",
    "jolly bee",
    "habit grill",
    "elevation burger",
    "bgr the burger joint",
    "fatburger",
    "steak n shake",
    "bobby's burger palace",
    "burgerfi",
    "wayback burgers",
    "mooyah",
    "cheaphard",
    "mcdonalds",
    "burgerking",
    "wendys",
    "popeye's",
    "kiddie",
    "pf chang's",
    "magnolia",
    "cheesecake",
    "pf changs",
    "magento",
    "cava",
    "honeygrow",
    "sweetgreen",
    "mezza",
    "zoes kitchen",
    "tazikis",
    "garbanzo",
    "pita pit",
    "hummus",
    "falafel",
]



async def discover_restaurants(
    city: Optional[str] = None,
    bbox: Optional[Union[list[float], tuple[float, float, float, float]]] = None,
    limit: int = 200,
    cuisine: Optional[str] = None,
    local_only: bool = False,
    neighborhood: Optional[str] = None,
    session: Optional[aiohttp.ClientSession] = None,
) -> list[dict]:
    """Discover restaurant POIs for a city or neighborhood using Nominatim + Overpass.
    
    Args:
        city: City name
        bbox: Bounding box (west, south, east, north)
        limit: Max results
        cuisine: Cuisine type filter
        local_only: Exclude chains
        neighborhood: Neighborhood name to geocode (e.g., "Soho, London")
    """
    orig_city = city
    city = normalize_city_name(city)
    print(f"[OVERPASS DEBUG] discover_restaurants called with city={city} (original: {orig_city}), bbox={bbox}, neighborhood={neighborhood}, limit={limit}")
    
    # Store original bbox for filtering later
    filter_bbox = bbox
    
    # If bbox is not provided, geocode neighborhood or city
    if bbox is None:
        if neighborhood:
            bbox = await geocode_city(neighborhood, session=session)
            print(f"[DEBUG discover_restaurants] Geocoded neighborhood to bbox={bbox}")
        elif city:
            bbox = await geocode_city(city, session=session)
            print(f"[OVERPASS DEBUG] Geocoded city to bbox={bbox}")
        else:
            print("[DEBUG discover_restaurants] No city, neighborhood, or bbox, returning empty")
            return []
    # Validate bbox is a tuple/list of 4 numbers
    if not (isinstance(bbox, (tuple, list)) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox)):
        print("[OVERPASS DEBUG] Invalid bbox format, returning empty")
        return []
    
    # bbox format: (west, south, east, north) - unpack and convert to Overpass format
    west, south, east, north = bbox
    bbox_str = f"{south},{west},{north},{east}"  # Overpass expects (south, west, north, east)
    amenity_filter = '["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court"]'
    q = f"[out:json][timeout:60];(node{amenity_filter}({bbox_str});way{amenity_filter}({bbox_str});relation{amenity_filter}({bbox_str}););out center;"
    # --- DEBUG/LOGGING: Log Overpass QL query and bbox for troubleshooting ---
    print(f"[OVERPASS DEBUG] Using bbox: {bbox}")
    print(f"[OVERPASS DEBUG] Overpass QL query: {q}")


    # ---- CACHING & RATE LIMIT -------------------------------------------------
    CACHE_TTL = int(os.environ.get("OVERPASS_CACHE_TTL", 60 * 60 * 6))
    RATE_LIMIT_SECONDS = float(os.environ.get("OVERPASS_MIN_INTERVAL", 5.0))

    cache_dir = Path(__file__).parent / ".cache" / "overpass"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    def _cache_path_for_query(qstr: str) -> Path:
        h = hashlib.sha256(qstr.encode("utf-8")).hexdigest()
        return cache_dir / f"{h}.json"

    def _read_cache(qstr: str, allow_expired=False):
        """Read cache, optionally returning expired data if allow_expired=True"""
        p = _cache_path_for_query(qstr)
        if not p.exists():
            return None
        try:
            m = p.stat().st_mtime
            age = time.time() - m
            if age > CACHE_TTL and not allow_expired:
                return None
            with p.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
                if age > CACHE_TTL:
                    print(f"[Overpass CACHE] Using expired cache ({age/3600:.1f}h old)")
                return data
        except Exception:
            return None

    def _write_cache(qstr: str, data):
        p = _cache_path_for_query(qstr)
        try:
            with p.open("w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except Exception:
            pass

    rate_file = cache_dir / "last_request_ts"

    def _ensure_rate_limit():
        try:
            last = float(rate_file.read_text()) if rate_file.exists() else 0.0
        except Exception:
            last = 0.0
        now = time.time()
        wait = RATE_LIMIT_SECONDS - (now - last)
        if wait > 0:
            time.sleep(wait)
        try:
            rate_file.write_text(str(time.time()))
        except Exception:
            pass


    headers = {"User-Agent": "CityGuides/1.0"}
    cached = _read_cache(q, allow_expired=False)
    if cached is not None:
        try:
            j = cached
        except Exception:
            j = None
    else:
        import subprocess
        j = None
        # Try subprocess/curl as primary
        for base_url in OVERPASS_URLS:
            try:
                print(f"[Overpass CURL Primary] Trying curl for {base_url}")
                curl_cmd = [
                    "curl", "-sS", "-X", "POST", base_url,
                    "-H", "Content-Type: application/x-www-form-urlencoded",
                    "--data-urlencode", f"data={q}"
                ]
                try:
                    result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
                except subprocess.TimeoutExpired as te:
                    print(f"[Overpass CURL Primary] Subprocess timeout expired: {te}")
                    continue
                except Exception as e:
                    print(f"[Overpass CURL Primary] Subprocess exception: {e}")
                    continue
                if result.returncode == 0 and result.stdout:
                    try:
                        j = json.loads(result.stdout)
                        _write_cache(q, j)
                        print(f"[Overpass CURL Primary] Success for {base_url}")
                        break
                    except Exception as e:
                        print(f"[Overpass CURL Primary] JSON decode error: {e}")
                        continue
                else:
                    print(f"[Overpass CURL Primary] curl failed: {result.stderr}")
            except Exception as e:
                print(f"[Overpass CURL Primary] Exception: {e}")
                continue
        # If curl fails, try aiohttp as backup
        if j is None:
            for base_url in OVERPASS_URLS:
                try:
                    _ensure_rate_limit()
                    attempts = int(os.environ.get("OVERPASS_RETRIES", 2))
                    for attempt in range(1, attempts + 1):
                        try:
                            own_session = False
                            if session is None:
                                session = aiohttp.ClientSession()
                                own_session = True
                            timeout = aiohttp.ClientTimeout(total=int(os.environ.get("OVERPASS_TIMEOUT", 20)))
                            async with session.post(base_url, data={"data": q}, headers=headers, timeout=timeout) as r:
                                if r.status != 200:
                                    try:
                                        text = await r.text()
                                        if text.strip().startswith("<"):
                                            print(f"[Overpass ERROR XML] {text[:200]}...")
                                    except Exception:
                                        pass
                                    if own_session:
                                        await session.close()
                                    continue
                                try:
                                    j = await r.json()
                                except Exception:
                                    text = await r.text()
                                    print(f"[Overpass ERROR Non-JSON] {text[:200]}...")
                                    if own_session:
                                        await session.close()
                                    continue
                                _write_cache(q, j)
                                if own_session:
                                    await session.close()
                                break
                        except Exception:
                            if attempt < attempts:
                                time.sleep(1 * attempt)
                            else:
                                raise
                    if j is not None:
                        break
                except Exception:
                    continue
        # If all curl and aiohttp requests failed, try to use expired cache as fallback
        if j is None:
            print("[Overpass] All curl and aiohttp requests failed, trying expired cache...")
            expired_cache = _read_cache(q, allow_expired=True)
            if expired_cache is not None:
                j = expired_cache
            elif filter_bbox is not None:
                # Try to find any cached file that covers the requested bbox
                print("[Overpass] No cached data for bbox, searching all cache files...")
                f_west, f_south, f_east, f_north = filter_bbox
                try:
                    # Iterate through all cache files
                    for cache_file in cache_dir.glob("*.json"):
                        try:
                            # Check if cache file is not too old (allow up to 7 days)
                            age = time.time() - cache_file.stat().st_mtime
                            if age > 60 * 60 * 24 * 7:  # 7 days
                                continue
                            with cache_file.open("r", encoding="utf-8") as fh:
                                cached_data = json.load(fh)
                                elements = cached_data.get("elements", [])
                                if not elements:
                                    continue
                                # Sample first 50 elements to check bbox coverage
                                sample = elements[:50]
                                lats = []
                                lons = []
                                for el in sample:
                                    if el.get("type") == "node":
                                        lat, lon = el.get("lat"), el.get("lon")
                                    else:
                                        center = el.get("center")
                                        if center:
                                            lat, lon = center.get("lat"), center.get("lon")
                                        else:
                                            continue
                                    if lat and lon:
                                        lats.append(lat)
                                        lons.append(lon)
                                if lats and lons:
                                    # Check if this cache covers the requested bbox
                                    cache_south, cache_north = min(lats), max(lats)
                                    cache_west, cache_east = min(lons), max(lons)
                                    # Check for overlap
                                    overlaps = (
                                        cache_south <= f_north and cache_north >= f_south and
                                        cache_west <= f_east and cache_east >= f_west
                                    )
                                    if overlaps:
                                        print(f"[Overpass] Found cache covering bbox ({cache_south:.2f},{cache_west:.2f},{cache_north:.2f},{cache_east:.2f}), age {age/3600:.1f}h")
                                        j = cached_data
                                        break
                        except Exception:
                            continue
                    if j is None:
                        print(f"[Overpass] No suitable cached data found covering bbox={filter_bbox}")
                except Exception as e:
                    print(f"[Overpass] Error searching cache files: {e}")
            if j is None:
                return []

    if j is None:
        print("[DEBUG discover_restaurants] No JSON response after all attempts, returning empty")
        return []
    elements = j.get("elements", [])
    print(f"[DEBUG discover_restaurants] Got {len(elements)} elements from Overpass")
    elements = elements[:200]
    skip_reverse = len(elements) > 50
    out = []
    cuisine_token = _singularize(cuisine) if cuisine else None

    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("operator") or "Unnamed"
        if el["type"] == "node":
            lat = el.get("lat")
            lon = el.get("lon")
        else:
            center = el.get("center")
            if center:
                lat = center["lat"]
                lon = center["lon"]
            else:
                continue
        address = (
            tags.get("addr:full")
            or f"{tags.get('addr:housenumber','')} {tags.get('addr:street','')} {tags.get('addr:city','')} {tags.get('addr:postcode','')}".strip()
        )
        if not address:
            if skip_reverse:
                address = f"{lat}, {lon}"
            else:
                address = await reverse_geocode(lat, lon, session=session) or f"{lat}, {lon}"

        name_lower = name.lower()
        if local_only and any(chain.lower() in name_lower for chain in CHAIN_KEYWORDS):
            continue

        tags_str = ", ".join([f"{k}={v}" for k, v in tags.items()])
        searchable = " ".join([name_lower, tags_str.lower()])
        if cuisine_token:
            cuisine_tag = (tags.get("cuisine") or "").lower()
            match_in_tags = cuisine_token in searchable
            match_in_cuisine = cuisine_token in cuisine_tag
            match_reverse = cuisine_tag and _singularize(cuisine_tag) in cuisine_token
            if not (match_in_tags or match_in_cuisine or match_reverse):
                continue
        website = tags.get("website") or tags.get("contact:website")
        osm_type = el.get("type")
        osm_id = el.get("id")
        osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        entry = {
            "osm_id": osm_id,
            "name": name,
            "website": website,
            "osm_url": osm_url,
            "amenity": tags.get("amenity", ""),
            "cost": tags.get("cost", ""),
            "address": address,
            "lat": lat,
            "lon": lon,
            "tags": tags_str,
        }
        out.append(entry)

    def sort_key(entry):
        amenity = entry["amenity"]
        cost = entry["cost"]
        amenity_score = {"fast_food": 1, "cafe": 2, "restaurant": 3}.get(amenity, 4)
        cost_score = {"cheap": 1, "moderate": 2, "expensive": 3}.get(
            cost.lower() if cost else "", 2
        )
        return (amenity_score, cost_score)

    out.sort(key=sort_key)
    
    # Filter by original bbox if we used city-level cache
    if filter_bbox is not None and filter_bbox != bbox:
        f_west, f_south, f_east, f_north = filter_bbox
        filtered_out = []
        for entry in out:
            lat, lon = entry.get("lat"), entry.get("lon")
            if lat is not None and lon is not None:
                if f_south <= lat <= f_north and f_west <= lon <= f_east:
                    filtered_out.append(entry)
        print(f"[DEBUG discover_restaurants] Filtered from {len(out)} to {len(filtered_out)} POIs using bbox={filter_bbox}")
        out = filtered_out
    
    print(f"[DEBUG discover_restaurants] Returning {len(out)} POIs after filtering")
    return out


async def async_discover_restaurants(city: Optional[str] = None, limit: int = 200, cuisine: Optional[str] = None, local_only: bool = False, bbox: Optional[Union[list[float], tuple[float, float, float, float]]] = None, session: Optional[aiohttp.ClientSession] = None):
    # Use async wrapper to call async_discover_pois
    res = await async_discover_pois(city, "restaurant", limit, local_only, bbox, session=session)
    if not res and city:
        # Try area-based Overpass query if bbox returns nothing
        # Get OSM relation id for city
        import logging
        params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
        headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
        own = False
        if session is None:
            session = aiohttp.ClientSession()
            own = True
        area_id = None
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
                if r.status == 200:
                    j = await r.json()
                    if j and j[0].get("osm_type") == "relation" and j[0].get("osm_id"):
                        area_id = 3600000000 + int(j[0]["osm_id"])
        except Exception:
            pass
        if area_id:
            # Build broader Overpass area query: include all amenities, tourism, and leisure
            q = f"""
            [out:json][timeout:60];
            area({area_id})->.searchArea;
            (
              node["amenity"](area.searchArea);
              way["amenity"](area.searchArea);
              relation["amenity"](area.searchArea);
              node["tourism"](area.searchArea);
              way["tourism"](area.searchArea);
              relation["tourism"](area.searchArea);
              node["leisure"](area.searchArea);
              way["leisure"](area.searchArea);
              relation["leisure"](area.searchArea);
            );
            out center;
            """
            logging.warning(f"[Overpass] Area fallback query for {city}: {q}")
            for base_url in OVERPASS_URLS:
                try:
                    timeout = aiohttp.ClientTimeout(total=30)
                    async with session.post(base_url, data={"data": q}, timeout=timeout) as resp:
                        logging.warning(f"[Overpass] Area fallback POST {base_url} status={resp.status}")
                        if resp.status == 200:
                            j = await resp.json()
                            elements = j.get("elements", [])
                            logging.warning(f"[Overpass] Area fallback returned {len(elements)} elements for {city}")
                            out = []
                            for el in elements:
                                tags = el.get("tags") or {}
                                name = tags.get("name") or tags.get("operator") or "Unnamed"
                                if el["type"] == "node":
                                    lat = el.get("lat")
                                    lon = el.get("lon")
                                else:
                                    center = el.get("center")
                                    if center:
                                        lat = center["lat"]
                                        lon = center["lon"]
                                    else:
                                        continue
                                address = tags.get("addr:full") or f"{tags.get('addr:housenumber','')} {tags.get('addr:street','')} {tags.get('addr:city','')} {tags.get('addr:postcode','')}",
                                entry = {
                                    "osm_id": el.get("id"),
                                    "name": name,
                                    "website": tags.get("website") or tags.get("contact:website"),
                                    "osm_url": f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
                                    "amenity": tags.get("amenity", ""),
                                    "cost": tags.get("cost", ""),
                                    "address": address,
                                    "lat": lat,
                                    "lon": lon,
                                    "tags": ", ".join([f"{k}={v}" for k, v in tags.items()]),
                                }
                                out.append(entry)
                            if out:
                                res = out
                                break
                        else:
                            logging.warning(f"[Overpass] Area fallback non-200 status: {resp.status}")
                    # Log any exceptions
                except Exception as e:
                    logging.warning(f"[Overpass] Area fallback error: {e}")
                    continue
        if own:
            await session.close()
    return res


async def discover_pois(city: Optional[str] = None, poi_type: str = "restaurant", limit: int = 200, local_only: bool = False, bbox: Optional[Union[list[float], tuple[float, float, float, float]]] = None, neighborhood: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None, name_query: Optional[str] = None):
    """Discover POIs of various types for a city using Nominatim + Overpass.
    If bbox is provided, use it directly. If neighborhood is provided, geocode it.
    Otherwise, geocode the city.

    Args:
        city: City name to search in
        poi_type: Type of POI ("restaurant", "historic", "museum", "park", etc.)
        limit: Maximum results to return
        local_only: Filter out chains (only applies to restaurants)
        bbox: Optional bounding box (west, south, east, north)
        neighborhood: Optional neighborhood name to geocode (e.g., "Soho, London", "Chelsea")
        name_query: Optional name query to filter by (e.g., "taco")

    Returns list of candidates with OSM data.
    """
    # --- Unified POI discovery: Overpass, Geoapify, Opentripmap ---
    if bbox is None:
        # Try neighborhood first, then city
        if neighborhood:
            bbox = await geocode_city(neighborhood, session=session)
        elif city:
            bbox = await geocode_city(city, session=session)
        else:
            return []
    if not (isinstance(bbox, (tuple, list)) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox)):
        return []

    # Map POI type to provider-specific categories/kinds
    poi_type_map = {
        "restaurant": {
            "geoapify": "catering.restaurant,catering.cafe,catering.fast_food,catering.food_court,bar,pub",
            "opentripmap": "restaurants,cafes,fast_food,food_court,bar,pub",
        },
        "historic": {
            "geoapify": "historic",
            "opentripmap": "historic",
        },
        "museum": {
            "geoapify": "entertainment.museum",
            "opentripmap": "museums",
        },
        "park": {
            "geoapify": "leisure.park",
            "opentripmap": "parks",
        },
        "market": {
            "geoapify": "commercial.marketplace",
            "opentripmap": "marketplaces",
        },
        "transport": {
            "geoapify": "transport",
            "opentripmap": "public_transport,airports,railway_stations,subway_stations,bus_stations,ferry_terminals",
        },
        "family": {
            "geoapify": "leisure.playground,leisure.amusement_arcade,leisure.miniature_golf",
            "opentripmap": "playgrounds,amusement_arcades,miniature_golf",
        },
        "event": {
            "geoapify": "entertainment.theatre,entertainment.cinema,entertainment.arts_centre,community_centre",
            "opentripmap": "theatres,cinemas,arts_centres,community_centres",
        },
        "local": {
            "geoapify": "tourism.attraction",
            "opentripmap": "attractions",
        },
        "hidden": {
            "geoapify": "tourism.attraction",
            "opentripmap": "attractions",
        },
        "coffee": {
            "geoapify": "catering.cafe,catering.coffee_shop",
            "opentripmap": "cafes,coffee_shops",
        },
    }
    geoapify_kinds = poi_type_map.get(poi_type, {}).get("geoapify")
    opentripmap_kinds = poi_type_map.get(poi_type, {}).get("opentripmap")


    # Run all providers in parallel (Overpass, Geoapify, Opentripmap)
    tasks = []

    # Overpass - use the core async function that does direct Overpass queries
    tasks.append(async_discover_pois(city, poi_type, limit, local_only, bbox, session=session, name_query=name_query))

    # Geoapify - always call with specific kinds if available, otherwise use defaults
    tasks.append(geoapify_discover_pois(bbox, kinds=geoapify_kinds, poi_type=poi_type, limit=limit, session=session))

    # Opentripmap
    if opentripmap_kinds:
        try:
            import importlib
            otm_provider = None
            try:
                from city_guides import opentripmap_provider as otm_provider
            except ImportError:
                # Try relative import if running as script
                try:
                    otm_provider = importlib.import_module("opentripmap_provider")
                except Exception:
                    otm_provider = None
            if otm_provider:
                tasks.append(otm_provider.discover_pois(city, kinds=opentripmap_kinds, limit=limit, session=session))
        except Exception as e:
            print(f"[DEBUG] Could not add opentripmap: {e}")
            pass

    # Add Wikivoyage summary as a POI if available
    async def fetch_wikivoyage_poi(city_name, session=None):
        try:
            import importlib
            fetch_wikivoyage_summary = None
            try:
                from .london_provider import fetch_wikivoyage_summary
            except ImportError:
                try:
                    mod = importlib.import_module("providers.london_provider")
                    fetch_wikivoyage_summary = getattr(mod, "fetch_wikivoyage_summary", None)
                except Exception:
                    fetch_wikivoyage_summary = None
            if not fetch_wikivoyage_summary:
                return None
            summary = await fetch_wikivoyage_summary(city_name, session=session)
            if summary and summary.strip():
                return {
                    "name": f"Wikivoyage: {city_name}",
                    "address": city_name,
                    "lat": None,
                    "lon": None,
                    "website": f"https://en.wikivoyage.org/wiki/{city_name.replace(' ', '_')}",
                    "osm_url": f"https://en.wikivoyage.org/wiki/{city_name.replace(' ', '_')}",
                    "tags": "wikivoyage,guide,summary",
                    "source": "wikivoyage",
                    "summary": summary,
                }
        except Exception:
            return None
        return None

    if city:
        tasks.append(fetch_wikivoyage_poi(city, session=session))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_pois = []
    for res in results:
        if isinstance(res, list):
            all_pois.extend(res)
        elif isinstance(res, dict):
            all_pois.append(res)

    # Deduplicate by (name, lat, lon)
    seen = set()
    deduped = []
    for poi in all_pois:
        key = (poi.get("name"), poi.get("lat"), poi.get("lon"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(poi)


    # Enrich with Mapillary images if token is set
    try:
        if os.getenv("MAPILLARY_TOKEN") and deduped:
            import importlib
            mapillary_provider = None
            try:
                import city_guides.mapillary_provider as mapillary_provider
            except ImportError:
                try:
                    mapillary_provider = importlib.import_module("mapillary_provider")
                except Exception:
                    mapillary_provider = None
            if mapillary_provider:
                await mapillary_provider.async_enrich_venues(deduped, session=session, radius_m=50, limit=3)
    except Exception:
        pass

    return deduped[:limit]


async def async_discover_pois(city: Optional[str] = None, poi_type: str = "restaurant", limit: int = 200, local_only: bool = False, bbox: Optional[Union[list[float], tuple[float, float, float, float]]] = None, session: Optional[aiohttp.ClientSession] = None, name_query: Optional[str] = None):
    print(f"[async_discover_pois] Called with city={city}, bbox={bbox}, poi_type={poi_type}")
    # Store original bbox for filtering later
    filter_bbox = bbox

    # Ensure we have an aiohttp session to use; create/close our own if not provided
    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True

    try:
        if bbox is None:
            if city is None:
                print("[async_discover_pois] No city or bbox, returning empty")
                if own_session:
                    try:
                        await session.close()
                    except Exception:
                        pass
                return []
            bbox = await async_geocode_city(city, session=session)
            print(f"[async_discover_pois] Geocoded to bbox={bbox}")
        if not bbox:
            print("[async_discover_pois] bbox is falsy, returning empty")
            if own_session:
                try:
                    await session.close()
                except Exception:
                    pass
            return []
    except Exception:
        if own_session:
            try:
                await session.close()
            except Exception:
                pass
        raise

    # Check if we should use around() query instead of bbox for better local discovery
    # Use around() for small areas (neighborhoods) or when we have a specific name query
    west, south, east, north = bbox
    bbox_width = abs(east - west)
    bbox_height = abs(north - south)

    # If bbox is small (likely a neighborhood) or we have a name_query, use around() query
    use_around_query = (bbox_width < 0.1 and bbox_height < 0.1) or name_query is not None

    if use_around_query:
        # Calculate center point and radius for around() query
        center_lat = (south + north) / 2
        center_lon = (west + east) / 2
        # Calculate radius in meters (approximate)
        radius_m = max(
            int(bbox_width * 111320 * 0.5),  # ~111km per degree latitude
            int(bbox_height * 111320 * 0.5)
        )
        # Cap radius to reasonable limits
        radius_m = min(max(radius_m, 500), 5000)

        print(f"[async_discover_pois] Using around() query with center=({center_lat}, {center_lon}), radius={radius_m}m")

        # Map poi_type to category filters
        category_filters = {
            "restaurant": '["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court"]',
            "bar": '["amenity"~"bar|pub|nightclub|biergarten"]',
            "coffee": '["amenity"~"cafe|coffee_shop"]',
            "historic": '["historic"]',
            "museum": '["tourism"~"museum|gallery"]["amenity"~"museum"]',
            "park": '["leisure"~"park|garden"]',
            "market": '["amenity"~"marketplace"]',
            "shopping": '["shop"]["amenity"~"marketplace|shopping_center"]',
            "transport": '["amenity"~"bus_station|ferry_terminal"]["railway"~"station"]',
        }

        base_filter = category_filters.get(poi_type, '["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court"]')
        if name_query:
            # Add name filter - case insensitive regex
            name_filter = f'["name"~"{name_query}",i]'
            base_filter += name_filter

        # Build around() query
        query = f"[out:json][timeout:25];(node{base_filter}(around:{radius_m},{center_lat},{center_lon});way{base_filter}(around:{radius_m},{center_lat},{center_lon});relation{base_filter}(around:{radius_m},{center_lat},{center_lon}););out center;"

        # Execute query directly
        result_data = None
        # Try each base URL with retries and backoff to mitigate transient timeouts
        for base_url in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]:
            attempts = 3
            for attempt in range(1, attempts + 1):
                try:
                    # increase timeout on subsequent attempts
                    tot = 30 + (attempt - 1) * 15
                    timeout = aiohttp.ClientTimeout(total=tot)
                    async with session.post(base_url, data={"data": query}, timeout=timeout) as resp:
                        if resp.status == 200:
                            result_data = await resp.json()
                            break
                        else:
                            print(f"[Overpass] {base_url} status={resp.status} (attempt {attempt})")
                except Exception as e:
                    print(f"[Overpass] Error with {base_url} attempt {attempt}: {e}")
                    # small backoff before retrying
                    try:
                        await asyncio.sleep(attempt * 0.5)
                    except Exception:
                        pass
                    continue
            if result_data:
                break
        if not result_data:
            print("[async_discover_pois] No Overpass data returned for around() query")
            if own_session:
                try:
                    await session.close()
                except Exception:
                    pass
            return []

        elements = result_data.get("elements", [])
        print(f"[async_discover_pois] Got {len(elements)} elements from around() query")

    else:
        # Original bbox-based query logic
        # bbox format: (west, south, east, north) - unpack and convert to Overpass format
        west, south, east, north = bbox
        bbox_str = f"{south},{west},{north},{east}"  # Overpass expects (south, west, north, east)
        print(f"[async_discover_pois] Using bbox_str={bbox_str}")

        poi_queries = {
            "restaurant": '["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court"]',
            "bar": '["amenity"~"bar|pub|nightclub|biergarten|wine_bar|cocktail_bar"]',
            "shopping": '["shop"]["amenity"~"marketplace|shopping_center"]',
            "historic": '["tourism"="attraction"]',
            "museum": '["tourism"="museum"]',
            "park": '["leisure"="park"]',
            "market": '["amenity"="marketplace"]',
            "transport": '["amenity"~"bus_station|train_station|subway_entrance|ferry_terminal|airport"]',
            "family": '["leisure"~"playground|amusement_arcade|miniature_golf"]',
            "event": '["amenity"~"theatre|cinema|arts_centre|community_centre"]',
            "local": '["tourism"~"attraction"]',
            "hidden": '["tourism"~"attraction"]',
            "coffee": '["amenity"~"cafe|coffee_shop"]',
        }

        amenity_filter = poi_queries.get(poi_type, poi_queries["restaurant"])
        if name_query:
            # Add name filter - case insensitive regex
            name_filter = f'["name"~"{name_query}",i]'
            amenity_filter += name_filter
        q = f"[out:json][timeout:60];(node{amenity_filter}({bbox_str});way{amenity_filter}({bbox_str});relation{amenity_filter}({bbox_str}););out center;"

        CACHE_TTL = int(os.environ.get("OVERPASS_CACHE_TTL", 60 * 60 * 6))
        RATE_LIMIT_SECONDS = float(os.environ.get("OVERPASS_MIN_INTERVAL", 5.0))

        cache_dir = Path(__file__).parent / ".cache" / "overpass"
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        def _cache_path_for_query(qstr: str) -> Path:
            h = hashlib.sha256(qstr.encode("utf-8")).hexdigest()
            return cache_dir / f"{h}.json"

        async def _read_cache(qstr: str):
            p = _cache_path_for_query(qstr)
            if not p.exists():
                return None
            try:
                m = p.stat().st_mtime
                age = time.time() - m
                if age > CACHE_TTL:
                    return None
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None

        async def _write_cache(qstr: str, data):
            p = _cache_path_for_query(qstr)
            try:
                p.write_text(json.dumps(data), encoding="utf-8")
            except Exception:
                pass

        rate_file = cache_dir / "last_request_ts"

        async def _ensure_rate_limit():
            try:
                last = float(rate_file.read_text()) if rate_file.exists() else 0.0
            except Exception:
                last = 0.0
            now = time.time()
            wait = RATE_LIMIT_SECONDS - (now - last)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                rate_file.write_text(str(time.time()))
            except Exception:
                pass

        # Use aiohttp to query Overpass
        result_data = None
        # Try each base URL with retries/backoff (helps with intermittent Overpass failures)
        for base_url in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]:
            attempts = 3
            for attempt in range(1, attempts + 1):
                try:
                    tot = 60 + (attempt - 1) * 15
                    timeout = aiohttp.ClientTimeout(total=tot)
                    async with session.post(base_url, data={"data": q}, timeout=timeout) as resp:
                        if resp.status == 200:
                            result_data = await resp.json()
                            break
                        else:
                            print(f"[Overpass] {base_url} status={resp.status} (attempt {attempt})")
                except Exception as e:
                    print(f"[Overpass] Error with {base_url} attempt {attempt}: {e}")
                    try:
                        await asyncio.sleep(attempt * 0.5)
                    except Exception:
                        pass
                    continue
            if result_data:
                break
        if not result_data:
            print(f"[async_discover_pois] No Overpass data returned for poi_type={poi_type}")
            if own_session:
                try:
                    await session.close()
                except Exception:
                    pass
            return []

        elements = result_data.get("elements", [])
        print(f"[async_discover_pois] Got {len(elements)} elements from Overpass")

    # Continue with shared processing logic for both query types
    print("[async_discover_pois] Raw Overpass response:", str(elements)[:1000])
    elements = elements[:200]
    skip_reverse = len(elements) > 50
    out = []

    cuisine_token = _singularize(None) if None else None

    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("operator") or "Unnamed"
        if poi_type == "historic" and name == "Unnamed":
            better_name = None
            if tags.get("inscription"):
                inscription = tags["inscription"].strip()
                better_name = inscription[:50] + ("..." if len(inscription) > 50 else "")
            elif tags.get("description"):
                desc = tags["description"].strip()
                better_name = desc[:50] + ("..." if len(desc) > 50 else "")
            elif tags.get("memorial"):
                memorial_type = tags["memorial"].replace("_", " ").title()
                if tags.get("wikidata"):
                    better_name = f"{memorial_type} Memorial"
                else:
                    better_name = memorial_type
            elif tags.get("historic"):
                historic_type = tags["historic"].replace("_", " ").title()
                better_name = historic_type

            if better_name:
                name = better_name

        if name == "Unnamed":
            if poi_type == "coffee":
                name = "Coffee Shop"
            elif poi_type == "restaurant" and tags.get("amenity") == "cafe":
                name = "Cafe"

        if name == "Unnamed" and not any(tags.get(k) for k in ["inscription", "description", "memorial", "wikidata"]):
            continue

        if el["type"] == "node":
            lat = el.get("lat")
            lon = el.get("lon")
        else:
            center = el.get("center")
            if center:
                lat = center["lat"]
                lon = center["lon"]
            else:
                continue

        address = (
            tags.get("addr:full")
            or f"{tags.get('addr:housenumber','')} {tags.get('addr:street','')} {tags.get('addr:city','')} {tags.get('addr:postcode','')}".strip()
        )
        if not address:
            if skip_reverse:
                address = f"{lat}, {lon}"
            else:
                address = await async_reverse_geocode(lat, lon, session=session) or f"{lat}, {lon}"

        if poi_type == "restaurant" and local_only:
            name_lower = name.lower()
            if any(chain.lower() in name_lower for chain in CHAIN_KEYWORDS):
                continue

        website = tags.get("website") or tags.get("contact:website")
        osm_type = el.get("type")
        osm_id = el.get("id")
        osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        tags_str = ", ".join([f"{k}={v}" for k, v in tags.items()])

        entry = {
            "osm_id": osm_id,
            "name": name,
            "website": website,
            "osm_url": osm_url,
            "amenity": tags.get("amenity", ""),
            "historic": tags.get("historic", ""),
            "tourism": tags.get("tourism", ""),
            "leisure": tags.get("leisure", ""),
            "cost": tags.get("cost", ""),
            "address": address,
            "lat": lat,
            "lon": lon,
            "tags": tags_str,
            "provider": "overpass",
        }
        out.append(entry)

    def sort_key(entry):
        name = entry.get("name", "")
        historic_type = entry.get("historic", "")
        name_score = 0 if name == "Unnamed" else 1
        type_priority = {
            "monument": 10, "castle": 9, "palace": 8, "church": 7, "cathedral": 7,
            "temple": 6, "mosque": 6, "museum": 5, "fort": 4, "tower": 3,
            "ruins": 2, "archaeological_site": 2, "memorial": 1
        }.get(historic_type, 0)
        return (-name_score, -type_priority, len(name))

    out.sort(key=sort_key, reverse=True)
    
    # Filter by original bbox if we used city-level cache
    if filter_bbox is not None and filter_bbox != bbox:
        f_west, f_south, f_east, f_north = filter_bbox
        filtered_out = []
        for entry in out:
            lat, lon = entry.get("lat"), entry.get("lon")
            if lat is not None and lon is not None:
                if f_south <= lat <= f_north and f_west <= lon <= f_east:
                    filtered_out.append(entry)
        print(f"[async_discover_pois] Filtered from {len(out)} to {len(filtered_out)} POIs using bbox={filter_bbox}")
        out = filtered_out
    
    if own_session:
        try:
            await session.close()
        except Exception:
            pass
    return out[:limit]


async def get_nearby_venues(lat, lon, venue_type="restaurant", radius=500, limit=50):
    """Get venues using proximity-based queries instead of bbox"""
    
    # Try progressively smaller radii if the initial query fails
    radii_to_try = [radius]
    if radius > 200:
        radii_to_try.extend([max(radius // 2, 200), 200])
    
    for attempt_radius in radii_to_try:
        try:
            result = await _get_nearby_venues_single_query(lat, lon, venue_type, attempt_radius, limit)
            if result:  # If we got results, return them
                return result
        except Exception as e:
            print(f"Venue query failed for radius {attempt_radius}m: {e}")
            continue
    
    # If all attempts failed, return empty list
    return []


async def _get_nearby_venues_single_query(lat, lon, venue_type, radius, limit):
    """Internal function to perform a single venue query"""

    # Map user-friendly types to OSM tags
    type_mapping = {
        "restaurant": {"amenity": ["restaurant", "food_court"]},
        "coffee": {"amenity": ["cafe", "coffee_shop"], "shop": ["coffee", "tea"]},
        "bar": {"amenity": ["bar", "pub", "nightclub"]},
        "fast_food": {"amenity": ["fast_food"]},
        "general": {"amenity": ["restaurant", "cafe", "bar", "fast_food"]}
    }

    # Build query based on venue type
    venue_config = type_mapping.get(venue_type, type_mapping["general"])

    query_parts = []
    for tag_type, values in venue_config.items():
        for value in values:
            query_parts.append(f'node["{tag_type}"="{value}"](around:{radius},{lat},{lon});')
            query_parts.append(f'way["{tag_type}"="{value}"](around:{radius},{lat},{lon});')

    joined_parts = "\n        ".join(query_parts)
    query = f"""
    [out:json][timeout:25];
    (
        {joined_parts}
    );
    out;
    """
    async with get_session() as session:
        async with session.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status != 200:
                raise Exception(f"API returned status {resp.status}")
            data = await resp.json()
            return process_venue_results(data.get("elements", []), limit)


def process_venue_results(elements, limit=50):
    """Process and rank venue results"""
    venues = []

    for element in elements:
        try:
            # Extract coordinates
            lat = element.get('lat')
            lon = element.get('lon')
            if not lat and 'center' in element:
                lat = element['center'].get('lat')
                lon = element['center'].get('lon')

            if not lat or not lon:
                continue

            tags = element.get('tags', {})
            name = tags.get('name', '').strip()
            if not name:
                continue  # Skip venues without names

            # Calculate quality score
            score = calculate_venue_quality(tags)

            venue = {
                'id': f"osm:{element.get('type')}/{element.get('id')}",
                'name': name,
                'lat': float(lat),
                'lon': float(lon),
                'type': determine_venue_type(tags),
                'tags': tags,
                'quality_score': score,
                'address': tags.get('addr:street'),
                'website': tags.get('website'),
                'phone': tags.get('phone'),
                'opening_hours': tags.get('opening_hours'),
                'cuisine': tags.get('cuisine'),
                'osm_url': f"https://www.openstreetmap.org/{element.get('type')}/{element.get('id')}",
            }
            venues.append(venue)
        except Exception:
            continue

    # Sort by quality score and limit results
    venues.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
    return venues[:limit]


def calculate_venue_quality(tags):
    """Calculate venue quality based on available information"""
    score = 0

    # Basic completeness
    if tags.get('name'): score += 10
    if tags.get('opening_hours'): score += 5
    if tags.get('website') or tags.get('contact:website'): score += 3
    if tags.get('phone') or tags.get('contact:phone'): score += 2
    if tags.get('cuisine'): score += 3

    # Premium indicators
    if tags.get('outdoor_seating') == 'yes': score += 2
    if tags.get('wheelchair') == 'yes': score += 2
    if tags.get('takeaway') == 'yes': score += 1

    return score


def determine_venue_type(tags):
    """Determine the primary type of venue"""
    amenity = tags.get('amenity', '')
    shop = tags.get('shop', '')

    if amenity in ['restaurant', 'fast_food']:
        return 'restaurant'
    elif amenity in ['cafe', 'coffee_shop']:
        return 'coffee'
    elif amenity in ['bar', 'pub', 'nightclub']:
        return 'bar'
    elif shop in ['coffee', 'tea']:
        return 'coffee'
    else:
        return 'venue'
        return 'venue'