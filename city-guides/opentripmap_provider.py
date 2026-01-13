import os
import time
import math
import aiohttp
from typing import List, Dict
import asyncio
import aiohttp

from overpass_provider import geocode_city

OPENTRIPMAP_KEY = os.getenv("OPENTRIPMAP_API_KEY") or os.getenv("OPENTRIPMAP_KEY")
BASE = "https://api.opentripmap.com/0.1/en/places"


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


async def discover_restaurants(city: str, limit: int = 50, cuisine: str = None, session: aiohttp.ClientSession = None) -> List[Dict]:
    """Discover POIs via OpenTripMap. Best-effort: requires OPENTRIPMAP_API_KEY in env.

    Returns list of dicts with keys: name,address,latitude,longitude,osm_url,place_id
    """
    if not OPENTRIPMAP_KEY:
        return []
    from overpass_provider import geocode_city
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True
    else:
        own_session = False
    bbox = await geocode_city(city, session=session)
    if not bbox:
        return []
    south, west, north, east = bbox
    lat = (south + north) / 2.0
    lon = (west + east) / 2.0
    # radius: half diagonal of bbox in meters, capped to 20000m
    d1 = _haversine_meters(lat, lon, north, west)
    d2 = _haversine_meters(lat, lon, south, east)
    radius = int(min(max(d1, d2) * 1.6, 20000)) or 5000

    params = {
        "apikey": OPENTRIPMAP_KEY,
        "radius": radius,
        "limit": limit,
        "lon": lon,
        "lat": lat,
        "kinds": "restaurants",
    }

    try:
        async with session.get(f"{BASE}/radius", params=params, timeout=20) as r:
            if r.status != 200:
                if own_session:
                    await session.close()
                return []
            j = await r.json()
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

        # fetch details for richer info
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
        }
        # optional simple cuisine match
        if cuisine:
            q = cuisine.lower()
            if q not in (name or "").lower() and q not in entry["tags"].lower():
                continue
        out.append(entry)

    return out


async def discover_pois(city: str, kinds: str = "restaurants", limit: int = 50, session: aiohttp.ClientSession = None) -> List[Dict]:
    """Discover POIs via OpenTripMap for different kinds of places.

    Args:
        city: City name to search in
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
    else:
        own_session = False
    bbox = await geocode_city(city, session=session)
    if not bbox:
        return []
    south, west, north, east = bbox
    lat = (south + north) / 2.0
    lon = (west + east) / 2.0
    # radius: half diagonal of bbox in meters, capped to 20000m
    d1 = _haversine_meters(lat, lon, north, west)
    d2 = _haversine_meters(lat, lon, south, east)
    radius = int(min(max(d1, d2) * 1.6, 20000)) or 5000

    params = {
        "apikey": OPENTRIPMAP_KEY,
        "radius": radius,
        "limit": limit,
        "lon": lon,
        "lat": lat,
        "kinds": kinds,
    }

    try:
        async with session.get(f"{BASE}/radius", params=params, timeout=20) as r:
            if r.status != 200:
                if own_session:
                    await session.close()
                return []
            j = await r.json()
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

        # fetch details for richer info
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
        }
        out.append(entry)

    return out


async def async_discover_pois(city: str, kinds: str = "restaurants", limit: int = 50, session: aiohttp.ClientSession = None) -> List[Dict]:
    print(f"[DEBUG opentripmap discover_pois] Called with city={city}, kinds={kinds}, API key present: {bool(OPENTRIPMAP_KEY)}")
    if not OPENTRIPMAP_KEY:
        print(f"[DEBUG opentripmap discover_pois] No API key, returning empty")
        return []
    bbox = geocode_city(city)
    print(f"[DEBUG opentripmap discover_pois] Geocoded bbox: {bbox}")
    if not bbox:
        return []
    south, west, north, east = bbox
    lat = (south + north) / 2.0
    lon = (west + east) / 2.0
    d1 = _haversine_meters(lat, lon, north, west)
    d2 = _haversine_meters(lat, lon, south, east)
    radius = int(min(max(d1, d2) * 1.6, 20000)) or 5000

    params = {
        "apikey": OPENTRIPMAP_KEY,
        "radius": radius,
        "limit": limit,
        "lon": lon,
        "lat": lat,
        "kinds": kinds,
    }

    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True

    try:
        print(f"[DEBUG opentripmap async_discover_pois] Requesting {BASE}/radius with params: radius={params['radius']}, lat={params['lat']}, lon={params['lon']}")
        async with session.get(f"{BASE}/radius", params=params, timeout=20) as r:
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
        }
        out.append(entry)

    if own_session:
        await session.close()
    return out


async def async_discover_restaurants(city: str, limit: int = 50, cuisine: str = None, session: aiohttp.ClientSession = None) -> List[Dict]:
    return await async_discover_pois(city, "restaurants", limit, session=session)


async def discover_restaurants(city: str, limit: int = 50, cuisine: str = None, session: aiohttp.ClientSession = None) -> List[Dict]:
    return await discover_pois(city, "restaurants", limit, session=session)
