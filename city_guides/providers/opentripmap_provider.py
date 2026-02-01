import os
import time
import math
import aiohttp
from typing import List, Dict
import asyncio
import aiohttp

from city_guides.providers.overpass_provider import geocode_city

OPENTRIPMAP_KEY = os.getenv("OPENTRIPMAP_API_KEY") or os.getenv("OPENTRIPMAP_KEY")
BASE = "https://api.opentripmap.com/0.1/en/places"
# Prefer bbox endpoint for better spatial coverage and deterministic bounding
OPENTRIPMAP_API_URL = f"{BASE}/bbox"

# London-targeted category expansions (OTM works better with broader kinds for large cities)
# Valid OpenTripMap kinds: https://opentripmap.io/catalog
LONDON_OTM_CATEGORIES = {
    "restaurant": "restaurants",
    "historic": "historic",
    "museum": "museums",
    "park": "parks",
    "transport": "transport",
    "shopping": "shops",
    "entertainment": "amusements",
}


def _haversine_meters(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def expand_bbox_for_opentripmap(bbox, city_radius_km: float = 10.0):
    """Expand bbox to approximate city-level coverage for OpenTripMap.

    Args:
        bbox: (west, south, east, north)
        city_radius_km: radius in kilometers to expand around bbox center

    Returns:
        Expanded bbox tuple (west, south, east, north)
    """
    try:
        west, south, east, north = bbox
    except Exception:
        return bbox

    # Convert km to degrees (approx, conservative)
    km_per_degree = 111.0
    expansion_degrees = float(city_radius_km) / km_per_degree

    center_lon = (west + east) / 2.0
    center_lat = (south + north) / 2.0

    new_west = center_lon - expansion_degrees
    new_east = center_lon + expansion_degrees
    new_south = center_lat - expansion_degrees
    new_north = center_lat + expansion_degrees

    print(f"[DEBUG] Expanded bbox: {new_west:.4f}, {new_south:.4f} → {new_east:.4f}, {new_north:.4f} (±{expansion_degrees:.4f}°)")
    return (new_west, new_south, new_east, new_north)


async def discover_restaurants(city: str, limit: int = 50, cuisine: str = None, session: aiohttp.ClientSession = None) -> List[Dict]:
    """Discover POIs via OpenTripMap. Best-effort: requires OPENTRIPMAP_API_KEY in env.

    Returns list of dicts with keys: name,address,latitude,longitude,osm_url,place_id

    Note: The `city` argument may be either a city name string or a bbox tuple/list `(west, south, east, north)` to call the bbox endpoint directly.
    """
    if not OPENTRIPMAP_KEY:
        return []
    from city_guides.providers.overpass_provider import geocode_city
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True
        print("[DEBUG opentripmap] Created internal aiohttp session for discover_restaurants")
    else:
        own_session = False
    # Accept either a bbox tuple/list (west, south, east, north) or a city string
    if isinstance(city, (list, tuple)):
        bbox = city
    else:
        bbox = await geocode_city(city, session=session)
    if not bbox:
        if own_session:
            await session.close()
        return []
    west, south, east, north = bbox

    # Determine if this bbox is (likely) London and expand restaurant kinds if so
    center_lon = (west + east) / 2.0
    center_lat = (south + north) / 2.0
    is_london = False
    try:
        if isinstance(city, str) and "london" in city.lower():
            is_london = True
        elif 51.28 <= center_lat <= 51.7 and -0.51 <= center_lon <= 0.34:
            is_london = True
    except Exception:
        is_london = False

    kinds_to_use = LONDON_OTM_CATEGORIES.get("restaurant") if is_london else "restaurants"

    params = {
        "apikey": OPENTRIPMAP_KEY,
        "lon_min": west,
        "lat_min": south,
        "lon_max": east,
        "lat_max": north,
        "limit": limit,
        "kinds": kinds_to_use,
    }

    try:
        async with session.get(OPENTRIPMAP_API_URL, params=params, timeout=20) as r:
            if r.status != 200:
                print(f"[DEBUG opentripmap] discover_restaurants HTTP error: {r.status}")
                if own_session:
                    await session.close()
                    print("[DEBUG opentripmap] Closed internal aiohttp session after error")
                return []
            j = await r.json()
    except Exception as e:
        print(f"[DEBUG opentripmap] discover_restaurants Exception: {e}")
        if own_session:
            await session.close()
            print("[DEBUG opentripmap] Closed internal aiohttp session after exception")
        return []

    out = []
    for itm in j.get("features", [])[:limit]:
        props = itm.get("properties", {})
        xid = props.get("xid")
        name = props.get("name") or ""
        point = itm.get("geometry", {}).get("coordinates") or []
        lon2 = point[0] if len(point) > 0 else None
        lat2 = point[1] if len(point) > 1 else None

        # fetch details for richer info
        detail = {}
        if xid:
            try:
                async with session.get(f"{BASE}/xid/{xid}", params={"apikey": OPENTRIPMAP_KEY}, timeout=15) as dd:
                    if dd.status == 200:
                        detail = await dd.json()
                    else:
                        print(f"[DEBUG opentripmap] discover_restaurants detail HTTP error: {dd.status}")
                        detail = {}
            except Exception as e:
                print(f"[DEBUG opentripmap] discover_restaurants detail Exception: {e}")
                detail = {}
            await asyncio.sleep(0.05)

        address = detail.get("address", {})
        addr = ", ".join(
            [
                address.get(k, "")
                for k in ("road", "house_number", "city", "state", "country")
                if address.get(k)
            ]
        )
        osm_url = ""
        if detail.get("url"):
            osm_url = detail.get("url")

        entry = {
            "name": name,
            "address": addr,
            "latitude": lat2,
            "longitude": lon2,
            "place_id": xid or props.get("osm_id") or "",
            "osm_url": osm_url,
            "tags": (
                ", ".join(
                    [
                        f"{k}={v}"
                        for k, v in (detail.get("properties", {}) or {}).items()
                    ]
                )
                if detail.get("properties")
                else ""
            ),
            "rating": detail.get("rate") if detail.get("rate") else None,
            "provider": "opentripmap",
        }
        # optional simple cuisine match
        if cuisine:
            q = cuisine.lower()
            if q not in (name or "").lower() and q not in entry["tags"].lower():
                continue
        out.append(entry)

    if own_session:
        await session.close()
        print("[DEBUG opentripmap] Closed internal aiohttp session after success")
    return out


async def discover_pois(city: str, kinds: str = "restaurants", limit: int = 50, session: aiohttp.ClientSession = None) -> List[Dict]:
    """Discover POIs via OpenTripMap for different kinds of places.

    Args:
        city: City name to search in, or a bbox tuple/list `(west, south, east, north)` to call the bbox endpoint directly
        kinds: OpenTripMap kinds string (e.g., "historic", "museums", "parks")
        limit: Maximum results to return

    Returns list of dicts with keys: name,address,latitude,longitude,osm_url,place_id
    """
    if not OPENTRIPMAP_KEY:
        return []
    from overpass_provider import geocode_city
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True
        print("[DEBUG opentripmap] Created internal aiohttp session for discover_pois")
    else:
        own_session = False
    # Accept either a bbox tuple/list (west, south, east, north) or a city string
    if isinstance(city, (list, tuple)):
        bbox = city
    else:
        bbox = await geocode_city(city, session=session)
    if not bbox:
        return []
    west, south, east, north = bbox

    params = {
        "apikey": OPENTRIPMAP_KEY,
        "lon_min": west,
        "lat_min": south,
        "lon_max": east,
        "lat_max": north,
        "limit": limit,
        "kinds": kinds,
    }

    try:
        async with session.get(OPENTRIPMAP_API_URL, params=params, timeout=20) as r:
            if r.status != 200:
                print(f"[DEBUG opentripmap] discover_pois HTTP error: {r.status}")
                if own_session:
                    await session.close()
                    print("[DEBUG opentripmap] Closed internal aiohttp session after error")
                return []
            j = await r.json()
    except Exception as e:
        print(f"[DEBUG opentripmap] discover_pois Exception: {e}")
        if own_session:
            await session.close()
            print("[DEBUG opentripmap] Closed internal aiohttp session after exception")
        return []

    out = []
    for itm in j.get("features", [])[:limit]:
        props = itm.get("properties", {})
        xid = props.get("xid")
        name = props.get("name") or ""
        point = itm.get("geometry", {}).get("coordinates") or []
        lon2 = point[0] if len(point) > 0 else None
        lat2 = point[1] if len(point) > 1 else None

        # fetch details for richer info
        detail = {}
        if xid:
            try:
                async with session.get(f"{BASE}/xid/{xid}", params={"apikey": OPENTRIPMAP_KEY}, timeout=15) as dd:
                    if dd.status == 200:
                        detail = await dd.json()
                    else:
                        print(f"[DEBUG opentripmap] discover_pois detail HTTP error: {dd.status}")
                        detail = {}
            except Exception as e:
                print(f"[DEBUG opentripmap] discover_pois detail Exception: {e}")
                detail = {}
            await asyncio.sleep(0.05)

        address = detail.get("address", {})
        addr = ", ".join(
            [
                address.get(k, "")
                for k in ("road", "house_number", "city", "state", "country")
                if address.get(k)
            ]
        )
        osm_url = ""
        if detail.get("url"):
            osm_url = detail.get("url")

        entry = {
            "name": name,
            "address": addr,
            "latitude": lat2,
            "longitude": lon2,
            "place_id": xid or props.get("osm_id") or "",
            "osm_url": osm_url,
            "tags": (
                ", ".join(
                    [
                        f"{k}={v}"
                        for k, v in (detail.get("properties", {}) or {}).items()
                    ]
                )
                if detail.get("properties")
                else ""
            ),
            "rating": detail.get("rate") if detail.get("rate") else None,
            "provider": "opentripmap",
        }
        out.append(entry)

    if own_session:
        await session.close()
        print("[DEBUG opentripmap] Closed internal aiohttp session after success")
    return out


async def async_discover_pois(city: str, kinds: str = "restaurants", limit: int = 50, session: aiohttp.ClientSession = None) -> List[Dict]:
    print(f"[DEBUG opentripmap discover_pois] Called with city={city}, kinds={kinds}, API key present: {bool(OPENTRIPMAP_KEY)}")
    if not OPENTRIPMAP_KEY:
        print(f"[DEBUG opentripmap discover_pois] No API key, returning empty")
        return []
    # Accept either a bbox tuple/list (west, south, east, north) or a city string
    if isinstance(city, (list, tuple)):
        bbox = city
    else:
        bbox = await geocode_city(city, session=session)
    # Detailed bbox debug (requested)
    try:
        west, south, east, north = bbox
        print(f"[DEBUG] Opentripmap search:")
        print(f"  BBox: {west:.4f}, {south:.4f} → {east:.4f}, {north:.4f}")
        print(f"  Width: {east-west:.4f}° longitude")
        print(f"  Height: {north-south:.4f}° latitude")
        print(f"  Kinds: {kinds}")
    except Exception as e:
        print(f"[DEBUG] Opentripmap bbox debug failed: {e}")

    # Expand to city-level bbox for OpenTripMap queries to improve coverage
    try:
        expanded_bbox = expand_bbox_for_opentripmap(bbox)
        west, south, east, north = expanded_bbox
        print(f"[DEBUG] Using expanded bbox for Opentripmap: {west:.4f}, {south:.4f} → {east:.4f}, {north:.4f}")
    except Exception as e:
        print(f"[DEBUG] Failed to expand bbox, falling back to original: {e}")
        try:
            west, south, east, north = bbox
        except Exception:
            return []

    print(f"[DEBUG opentripmap discover_pois] Geocoded bbox: {west, south, east, north}")
    if not (west or south or east or north):
        return []

    # Map kinds to London-specific set when the bbox/city falls within London
    center_lon = (west + east) / 2.0
    center_lat = (south + north) / 2.0
    is_london = False
    try:
        if isinstance(city, str) and "london" in city.lower():
            is_london = True
        elif 51.28 <= center_lat <= 51.7 and -0.51 <= center_lon <= 0.34:
            is_london = True
    except Exception:
        is_london = False

    kinds_to_use = LONDON_OTM_CATEGORIES.get(kinds, kinds) if is_london else kinds

    params = {
        "apikey": OPENTRIPMAP_KEY,
        "lon_min": west,
        "lat_min": south,
        "lon_max": east,
        "lat_max": north,
        "limit": limit,
        "kinds": kinds_to_use,
    }

    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True

    try:
        print(f"[DEBUG opentripmap async_discover_pois] Requesting {OPENTRIPMAP_API_URL} with bbox params: {params}")
        async with session.get(OPENTRIPMAP_API_URL, params=params, timeout=20) as r:
            print(f"[DEBUG opentripmap async_discover_pois] HTTP status: {r.status}")
            if r.status != 200:
                try:
                    error_text = await r.text()
                    print(f"[DEBUG opentripmap async_discover_pois] Error response: {error_text[:200]}")
                except:
                    pass
                if own_session:
                    await session.close()
                return []
            j = await r.json()
            print(f"[DEBUG opentripmap async_discover_pois] Response features: {len(j.get('features', []))}")
    except Exception:
        if own_session:
            await session.close()
        return []

    out = []
    for itm in j.get("features", [])[:limit]:
        props = itm.get("properties", {})
        xid = props.get("xid")
        name = props.get("name") or ""
        point = itm.get("geometry", {}).get("coordinates") or []
        lon2 = point[0] if len(point) > 0 else None
        lat2 = point[1] if len(point) > 1 else None

        detail = {}
        if xid:
            try:
                async with session.get(f"{BASE}/xid/{xid}", params={"apikey": OPENTRIPMAP_KEY}, timeout=15) as dd:
                    if dd.status == 200:
                        detail = await dd.json()
                    else:
                        detail = {}
            except Exception:
                detail = {}
            await asyncio.sleep(0.05)

        address = detail.get("address", {})
        addr = ", ".join(
            [
                address.get(k, "")
                for k in ("road", "house_number", "city", "state", "country")
                if address.get(k)
            ]
        )
        osm_url = ""
        if detail.get("url"):
            osm_url = detail.get("url")

        entry = {
            "name": name,
            "address": addr,
            "latitude": lat2,
            "longitude": lon2,
            "place_id": xid or props.get("osm_id") or "",
            "osm_url": osm_url,
            "tags": (
                ", ".join(
                    [
                        f"{k}={v}"
                        for k, v in (detail.get("properties", {}) or {}).items()
                    ]
                )
                if detail.get("properties")
                else ""
            ),
            "rating": detail.get("rate") if detail.get("rate") else None,
            "provider": "opentripmap",
        }
        out.append(entry)

    if own_session:
        await session.close()
    return out


async def async_discover_restaurants(city: str, limit: int = 50, cuisine: str = None, session: aiohttp.ClientSession = None) -> List[Dict]:
    return await async_discover_pois(city, "restaurants", limit, session=session)


async def discover_restaurants(city: str, limit: int = 50, cuisine: str = None, session: aiohttp.ClientSession = None) -> List[Dict]:
    return await discover_pois(city, "restaurants", limit, session=session)
