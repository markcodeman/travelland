import os
import math
import asyncio
from typing import List, Dict, Optional
import aiohttp


def _meters_to_degree_lat(meters: float) -> float:
    # approx conversion: 1 deg lat ~ 111320 meters
    return meters / 111320.0


def _meters_to_degree_lon(meters: float, lat: float) -> float:
    # approx conversion for longitude degrees at given latitude
    return meters / (111320.0 * math.cos(math.radians(lat)) + 1e-9)


async def async_search_images_near(
    lat: float,
    lon: float,
    radius_m: int = 50,
    limit: int = 3,
    session: Optional[aiohttp.ClientSession] = None,
) -> List[Dict]:
    """Search Mapillary images within a small bbox around the point.

    Returns a list of dicts with keys: id, url, lat, lon, raw
    If MAPILLARY_TOKEN not set or request fails, returns empty list.
    """
    token = os.getenv("MAPILLARY_TOKEN")
    if not token:
        return []

    own_session = False
    if session is None:
        session = aiohttp.ClientSession(headers={"User-Agent": "city-guides-mapillary"})
        own_session = True
        print("[DEBUG mapillary] Created internal aiohttp session for async_search_images_near")

    try:
        # Build bbox around point
        dlat = _meters_to_degree_lat(radius_m)
        dlon = _meters_to_degree_lon(radius_m, lat)
        min_lat = lat - dlat
        max_lat = lat + dlat
        min_lon = lon - dlon
        max_lon = lon + dlon
        bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"

        url = "https://graph.mapillary.com/images"
        # request common thumbnail field names; Graph API accepts 'fields'
        fields = ["id", "thumb_1024_url", "thumb_512_url", "computed_geometry"]
        params = {
            "access_token": token,
            "bbox": bbox,
            "limit": str(limit),
            "fields": ",".join(fields),
        }

        async with session.get(url, params=params, timeout=10) as resp:
            if resp.status != 200:
                print(f"[DEBUG mapillary] async_search_images_near HTTP error: {resp.status}")
                if own_session:
                    await session.close()
                    print("[DEBUG mapillary] Closed internal aiohttp session after error")
                return []
            data = await resp.json()
            items = data.get("data") or data.get("images") or []
            out = []
            for it in items:
                geom = it.get("computed_geometry") or {}
                lat_i = None
                lon_i = None
                if isinstance(geom, dict):
                    c = geom.get("coordinates")
                    if isinstance(c, (list, tuple)) and len(c) >= 2:
                        lon_i, lat_i = float(c[0]), float(c[1])
                thumb = it.get("thumb_1024_url") or it.get("thumb_512_url") or it.get("thumb_url")
                if not thumb:
                    continue
                out.append({"id": it.get("id"), "url": thumb, "lat": lat_i, "lon": lon_i, "raw": it})
            if own_session:
                await session.close()
                print("[DEBUG mapillary] Closed internal aiohttp session after success")
            return out
    except Exception as e:
        print(f"[DEBUG mapillary] async_search_images_near Exception: {e}")
        if own_session:
            await session.close()
            print("[DEBUG mapillary] Closed internal aiohttp session after exception")
        return []


async def async_enrich_venues(
    venues: List[Dict], session: Optional[aiohttp.ClientSession] = None, radius_m: int = 50, limit: int = 3
) -> List[Dict]:
    """For each venue with lat/lon, fetch nearby Mapillary thumbnails and attach
    a `mapillary_images` list (may be empty).
    Modifies venue dicts in-place and also returns the list for convenience.
    """
    # Quick bail if no token
    if not os.getenv("MAPILLARY_TOKEN"):
        for v in venues:
            v.setdefault("mapillary_images", [])
        return venues

    # Use provided session if any; otherwise create one for all calls
    own_session = False
    import aiohttp as _aiohttp

    if session is None:
        session = _aiohttp.ClientSession(headers={"User-Agent": "city-guides-mapillary"})
        own_session = True
        print("[DEBUG mapillary] Created internal aiohttp session for async_enrich_venues")

    try:
        sem = asyncio.Semaphore(8)

        async def _enrich_one(v: Dict):
            lat = v.get("lat")
            lon = v.get("lon")
            v.setdefault("mapillary_images", [])
            if lat is None or lon is None:
                return
            async with sem:
                try:
                    imgs = await async_search_images_near(lat, lon, radius_m=radius_m, limit=limit, session=session)
                    v["mapillary_images"] = imgs
                except Exception:
                    v["mapillary_images"] = []

        await asyncio.gather(*[_enrich_one(v) for v in venues])
        return venues
    finally:
        if own_session:
            await session.close()
            print("[DEBUG mapillary] Closed internal aiohttp session after async_enrich_venues")
