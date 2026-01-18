
from typing import Optional, Union
import aiohttp
import time
import os
import json
import hashlib
from pathlib import Path
from urllib.parse import urlencode
import asyncio
import re

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
from pathlib import Path
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
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(GEOAPIFY_GEOCODE_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                if own:
                    await session.close()
                return None
            j = await r.json()
            results = j.get("results", [])
            if not results:
                if own:
                    await session.close()
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
                    if own:
                        await session.close()
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
                if own:
                    await session.close()
                return (lon-buf, lat-buf, lon+buf, lat+buf)
            if own:
                await session.close()
            return None
    except Exception:
        if own:
            await session.close()
        return None

async def geoapify_reverse_geocode(lat, lon, session: Optional[aiohttp.ClientSession] = None):
    api_key = get_geoapify_key()
    if not api_key:
        return ""
    params = {"lat": lat, "lon": lon, "format": "json", "apiKey": api_key}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(GEOAPIFY_REVERSE_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                if own:
                    await session.close()
                return ""
            j = await r.json()
            features = j.get("features", [])
            if not features:
                if own:
                    await session.close()
                return ""
            prop = features[0].get("properties", {})
            addr = prop.get("formatted", "")
            if own:
                await session.close()
            return addr
    except Exception:
        if own:
            await session.close()
        return ""

# --- GEOAPIFY POI SEARCH ---
GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"

async def geoapify_discover_pois(
    bbox: Optional[Union[list[float], tuple[float, float, float, float]]],
    kinds: Optional[str] = None,
    limit: int = 200,
    session: Optional[aiohttp.ClientSession] = None,
) -> list[dict]:
    """Discover POIs using Geoapify Places API, normalized to Overpass-like output."""
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
        params_base["categories"] = "tourism,catering,entertainment,leisure,commercial,healthcare,education"

    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True

    out = []
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
                    address = prop.get("formatted") or prop.get("address_line1")
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
                    }
                    out.append(entry)

                fetched = len(features)
                # advance offset and remaining
                offset += fetched
                remaining -= fetched
                if fetched < per_request:
                    # fewer results than requested; end pagination
                    break

        if own:
            await session.close()
        # return up to the originally requested limit
        return out[:requested_limit]
    except Exception as e:
        print(f"[DEBUG] Exception in geoapify_discover_pois: {e}")
        if own:
            await session.close()
        return out

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
            own = False
            if session is None:
                session = await aiohttp.ClientSession().__aenter__()
                own = True
            try:
                timeout = aiohttp.ClientTimeout(total=15)
                async with session.get(OPENTRIPMAP_API_URL, params=params, headers=headers, timeout=timeout) as r:
                    if r.status != 200:
                        print(f"[DEBUG] Opentripmap HTTP error: status={r.status} url={r.url}")
                        if own:
                            await session.close()
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
                        }
                        out.append(entry)
                    if own:
                        await session.close()
                    return out
            except Exception as e:
                print(f"[DEBUG] Exception in opentripmap_discover_pois: {e}")
                if own:
                    await session.close()
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
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
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
                if own:
                    await session.close()
                return addr
    except Exception:
        pass
    # Fallback to Geoapify
    addr = await geoapify_reverse_geocode(lat, lon, session=session)
    try:
        cache_file.write_text(json.dumps(addr), encoding="utf-8")
    except Exception:
        pass
    if own:
        await session.close()
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
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(url, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                if own:
                    await session.close()
                return ""
            j = await r.json()
            addr = j.get("display_name", "")
            try:
                cache_file.write_text(json.dumps(addr), encoding="utf-8")
            except Exception:
                pass
            if own:
                await session.close()
            return addr
    except Exception:
        if own:
            await session.close()
        return ""


async def geocode_city(city: str, session: Optional[aiohttp.ClientSession] = None):
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
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
                        if own:
                            await session.close()
                        return (west, south, east, north)
    except Exception:
        pass
    
    # Fallback to Geoapify
    bbox = await geoapify_geocode_city(city, session=session)
    if bbox:
        if own:
            await session.close()
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
        if own:
            await session.close()
        return CITY_FALLBACKS[city_normalized]
    # Then try prefix match (handles "London, UK" matching "london")
    for city_key, city_bbox in CITY_FALLBACKS.items():
        if city_normalized.startswith(city_key + ",") or city_normalized.startswith(city_key + " "):
            if own:
                await session.close()
            return city_bbox
    
    if own:
        await session.close()
    return None


async def async_geocode_city(city: str, session: Optional[aiohttp.ClientSession] = None):
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                if own:
                    await session.close()
                return None
            j = await r.json()
            if not j:
                if own:
                    await session.close()
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
                if own:
                    await session.close()
                return (west, south, east, north)
            if own:
                await session.close()
            return None
    except Exception:
        if own:
            await session.close()
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
        if city:
            params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
            headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": lang}
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
                    if r.status == 200:
                        j = await r.json()
                        if j:
                            if j[0].get("osm_type") == "relation" and j[0].get("osm_id"):
                                area_id = 3600000000 + int(j[0]["osm_id"])  # relation -> area id
            except Exception:
                pass

        # build query
        if area_id:
            q = f"""
                [out:json][timeout:25];
                area({area_id})->.cityArea;
                (
                  relation["place"~"neighbourhood|suburb|quarter|city_district"](area.cityArea);
                  way["place"~"neighbourhood|suburb|quarter|city_district"](area.cityArea);
                  node["place"~"neighbourhood|suburb|quarter|city_district"](area.cityArea);
                );
                out center tags;
            """
        else:
            bbox_str = None
            if lat and lon:
                buf = float(os.getenv("NEIGHBORHOOD_DEFAULT_BUFFER_KM", 5.0)) / 111.0
                minlat, minlon, maxlat, maxlon = lat - buf, lon - buf, lat + buf, lon + buf
                bbox_str = f"{minlat},{minlon},{maxlat},{maxlon}"
            else:
                bb = await async_geocode_city(city or "", session=session)
                if bb:
                    south, west, north, east = bb
                    bbox_str = f"{south},{west},{north},{east}"

            if not bbox_str:
                return []

            q = f"""
                [out:json][timeout:25];
                (
                  relation["place"~"neighbourhood|suburb|quarter|city_district"]({bbox_str});
                  way["place"~"neighbourhood|suburb|quarter|city_district"]({bbox_str});
                  node["place"~"neighbourhood|suburb|quarter|city_district"]({bbox_str});
                );
                out center tags;
            """

        # call overpass endpoints
        for url in OVERPASS_URLS:
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with session.post(url, data={"data": q}, timeout=timeout) as resp:
                    if resp.status != 200:
                        continue
                    j = await resp.json()
                    elements = j.get("elements", [])
                    results = []
                    for el in elements:
                        name = el.get("tags", {}).get("name")
                        if not name:
                            continue
                        el_id = f"{el.get('type')}/{el.get('id')}"
                        bbox = None
                        if el.get("type") == "relation":
                            bbox = el.get("bounds") or el.get("bbox")
                        center = None
                        if "center" in el:
                            center = {"lat": el["center"]["lat"], "lon": el["center"]["lon"]}
                        elif "lat" in el and "lon" in el:
                            center = {"lat": el["lat"], "lon": el["lon"]}
                        # If bbox not available from bounds, generate from center with a buffer
                        if bbox is None and center:
                            # Create a bbox around the center point (0.01 degrees ≈ 1.1 km buffer)
                            buf = 0.01
                            bbox = [
                                center["lon"] - buf,  # west
                                center["lat"] - buf,  # south
                                center["lon"] + buf,  # east
                                center["lat"] + buf,  # north
                            ]
                        
                        results.append({
                            "id": el_id,
                            "name": name,
                            "slug": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
                            "center": center,
                            "bbox": bbox,
                            "source": "osm",
                        })
                    if results:
                        return results
            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

        # If Overpass produced no results, try GeoNames as a best-effort fallback
        geonames_user = os.getenv("GEONAMES_USERNAME")
        if geonames_user:
            try:
                # import lazily to avoid import-time cost when not used
                import geonames_provider
                geores = await geonames_provider.async_get_neighborhoods_geonames(
                    city=city, lat=lat, lon=lon, session=session
                )
                if geores:
                    return geores
            except Exception:
                pass

        return []

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
            print(f"[DEBUG discover_restaurants] No city, neighborhood, or bbox, returning empty")
            return []
    # Validate bbox is a tuple/list of 4 numbers
    if not (isinstance(bbox, (tuple, list)) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox)):
        print(f"[OVERPASS DEBUG] Invalid bbox format, returning empty")
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
        import shlex
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
                result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
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
                print(f"[Overpass] No cached data for bbox, searching all cache files...")
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
                        except Exception as e:
                            continue
                    if j is None:
                        print(f"[Overpass] No suitable cached data found covering bbox={filter_bbox}")
                except Exception as e:
                    print(f"[Overpass] Error searching cache files: {e}")
            if j is None:
                return []

    if j is None:
        print(f"[DEBUG discover_restaurants] No JSON response after all attempts, returning empty")
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


async def discover_pois(city: Optional[str] = None, poi_type: str = "restaurant", limit: int = 200, local_only: bool = False, bbox: Optional[Union[list[float], tuple[float, float, float, float]]] = None, neighborhood: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None):
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
    tasks.append(async_discover_pois(city, poi_type, limit, local_only, bbox, session=session))

    # Geoapify - always call with specific kinds if available, otherwise use defaults
    tasks.append(geoapify_discover_pois(bbox, kinds=geoapify_kinds, limit=limit, session=session))

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
                from city_guides.providers.london_provider import fetch_wikivoyage_summary
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


async def async_discover_pois(city: Optional[str] = None, poi_type: str = "restaurant", limit: int = 200, local_only: bool = False, bbox: Optional[Union[list[float], tuple[float, float, float, float]]] = None, session: Optional[aiohttp.ClientSession] = None):
    print(f"[async_discover_pois] Called with city={city}, bbox={bbox}, poi_type={poi_type}")
    # Store original bbox for filtering later
    filter_bbox = bbox
    
    if bbox is None:
        if city is None:
            print("[async_discover_pois] No city or bbox, returning empty")
            return []
        bbox = await async_geocode_city(city, session=session)
        print(f"[async_discover_pois] Geocoded to bbox={bbox}")
    if not bbox:
        print("[async_discover_pois] bbox is falsy, returning empty")
        return []
    # bbox format: (west, south, east, north) - unpack and convert to Overpass format
    west, south, east, north = bbox
    bbox_str = f"{south},{west},{north},{east}"  # Overpass expects (south, west, north, east)
    print(f"[async_discover_pois] Using bbox_str={bbox_str}")

    poi_queries = {
        "restaurant": '["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court"]',
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

    import overpy
    api = overpy.Overpass()
    try:
        # overpy is synchronous, so run in a thread to avoid blocking
        import concurrent.futures
        def run_query():
            return api.query(q)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await asyncio.get_event_loop().run_in_executor(executor, run_query)
    except Exception as e:
        print(f"[async_discover_pois] Overpy error: {e}")
        result = None

    elements = []
    if result:
        # Collect nodes, ways, and relations
        for node in result.nodes:
            elements.append({
                "type": "node",
                "id": node.id,
                "lat": float(node.lat),
                "lon": float(node.lon),
                "tags": node.tags
            })
        for way in result.ways:
            center_lat = float(way.center_lat) if way.center_lat else None
            center_lon = float(way.center_lon) if way.center_lon else None
            elements.append({
                "type": "way",
                "id": way.id,
                "center": {"lat": center_lat, "lon": center_lon},
                "tags": way.tags
            })
        for rel in result.relations:
            center_lat = float(rel.center_lat) if rel.center_lat else None
            center_lon = float(rel.center_lon) if rel.center_lon else None
            elements.append({
                "type": "relation",
                "id": rel.id,
                "center": {"lat": center_lat, "lon": center_lon},
                "tags": rel.tags
            })
    else:
        print(f"[async_discover_pois] No Overpass data returned for poi_type={poi_type}")
        return []

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
    
    return out[:limit]
