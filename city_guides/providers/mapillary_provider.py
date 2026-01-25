import os
import math
import asyncio
from typing import List, Dict, Optional
import aiohttp
from pathlib import Path

# Load environment variables from .env file (same as app.py)
_env_paths = [
    Path(__file__).parent.parent / ".env",
    Path(__file__).parent.parent.parent / ".env", 
    Path("/home/markm/TravelLand/.env"),
]
for _env_file in _env_paths:
    if _env_file.exists():
        with open(_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
        break

# Updated with user-provided implementation

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


async def async_search_places(
    query: str,
    access_token: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> List[Dict]:
    """Search Mapillary places based on a query.

    Returns a list of dicts with keys: id, name, type, lat, lon
    If request fails, returns empty list.
    """
    own_session = False
    if session is None:
        session = aiohttp.ClientSession(headers={"User-Agent": "city-guides-mapillary"})
        own_session = True

    try:
        url = "https://api.mapillary.com/places"
        params = {
            "query": query,
            "access_token": access_token
        }

        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                print(f"[DEBUG mapillary] async_search_places HTTP error: {resp.status}")
                if own_session:
                    await session.close()
                    print("[DEBUG mapillary] Closed internal aiohttp session after error")
                return []
            data = await resp.json()
            items = data.get("data") or data.get("places") or []
            out = []
            for it in items:
                name = it.get("name", "")
                place_type = it.get("type", "")
                geom = it.get("geometry") or {}
                lat_i = None
                lon_i = None
                if isinstance(geom, dict):
                    c = geom.get("coordinates")
                    if isinstance(c, (list, tuple)) and len(c) >= 2:
                        lon_i, lat_i = float(c[0]), float(c[1])
                out.append({"id": it.get("id"), "name": name, "type": place_type, "lat": lat_i, "lon": lon_i})
            if own_session:
                await session.close()
                print("[DEBUG mapillary] Closed internal aiohttp session after success")
            return out
    except Exception as e:
        print(f"[DEBUG mapillary] async_search_places Exception: {e}")
        if own_session:
            await session.close()
            print("[DEBUG mapillary] Closed internal aiohttp session after exception")
        return []


# Helper utilities for bbox sizing and guarding Mapillary bbox limits
def _bbox_area(bbox: tuple) -> float:
    try:
        west, south, east, north = bbox
        return abs((east - west) * (north - south))
    except Exception:
        return 1.0


def _small_centered_bbox(bbox: tuple, max_area: float = 0.01) -> tuple:
    """Return a small bbox centered on the given bbox center with area <= max_area."""
    west, south, east, north = bbox
    lat = (south + north) / 2.0
    lon = (west + east) / 2.0
    # make a square bbox with side = sqrt(max_area)
    half = (max_area ** 0.5) / 2.0
    return (lon - half, lat - half, lon + half, lat + half)


async def async_discover_map_features(
    bbox: Optional[tuple] = None,
    object_values: Optional[str] = None,
    limit: int = 200,
    session: Optional[aiohttp.ClientSession] = None,
) -> List[Dict]:
    """Discover derived map features (points) from Mapillary's Graph API `/map_features`.

    Returns normalized entries with keys similar to other providers (osm_id, name, lat, lon, tags, source, raw).
    """
    token = os.getenv("MAPILLARY_TOKEN")
    if not token:
        return []
    if not bbox or len(bbox) != 4:
        return []

    # Enforce small bbox area requirement for map_features (doc: small bbox recommended)
    if _bbox_area(bbox) > 0.01:
        bbox = _small_centered_bbox(bbox)

    west, south, east, north = bbox
    bbox_str = f"{west},{south},{east},{north}"

    params = {
        "access_token": token,
        "bbox": bbox_str,
        "fields": "id,geometry,object_value",
        "limit": str(limit),
    }
    if object_values:
        params["object_values"] = object_values

    own_session = False
    if session is None:
        session = aiohttp.ClientSession(headers={"User-Agent": "city-guides-mapillary"})
        own_session = True

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with session.get("https://graph.mapillary.com/map_features", params=params, timeout=timeout) as r:
            if r.status != 200:
                return []
            j = await r.json()
            items = j.get("data", [])
            out = []
            for it in items:
                geom = it.get("geometry", {}) or {}
                coords = geom.get("coordinates") if isinstance(geom, dict) else None
                lon, lat = (None, None)
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    lon, lat = float(coords[0]), float(coords[1])
                out.append({
                    "osm_id": it.get("id"),
                    "name": it.get("object_value") or "map_feature",
                    "lat": lat,
                    "lon": lon,
                    "address": "",
                    "tags": it.get("object_value", ""),
                    "source": "mapillary-map_feature",
                    "raw": it,
                })
            return out
    except Exception:
        return []
    finally:
        if own_session:
            await session.close()


async def async_discover_images_in_bbox(
    bbox: Optional[tuple] = None,
    limit: int = 100,
    session: Optional[aiohttp.ClientSession] = None,
    fields: Optional[List[str]] = None,
) -> List[Dict]:
    """Discover Mapillary images within a small bbox and normalize into point-like entries.

    The Mapillary `/images` endpoint requires small bbox areas (<0.01 deg^2).
    Returns entries with source 'mapillary-image' and includes thumbnail urls when available.
    """
    token = os.getenv("MAPILLARY_TOKEN")
    if not token:
        return []
    if not bbox or len(bbox) != 4:
        return []

    if _bbox_area(bbox) > 0.01:
        bbox = _small_centered_bbox(bbox)

    if fields is None:
        fields = ["id", "computed_geometry", "thumb_1024_url", "thumb_512_url"]

    west, south, east, north = bbox
    bbox_str = f"{west},{south},{east},{north}"

    params = {
        "access_token": token,
        "bbox": bbox_str,
        "fields": ",".join(fields),
        "limit": str(limit),
    }

    own_session = False
    if session is None:
        session = aiohttp.ClientSession(headers={"User-Agent": "city-guides-mapillary"})
        own_session = True

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with session.get("https://graph.mapillary.com/images", params=params, timeout=timeout) as r:
            if r.status != 200:
                return []
            j = await r.json()
            items = j.get("data", [])
            out = []
            for it in items:
                geom = it.get("computed_geometry", {}) or {}
                coords = geom.get("coordinates") if isinstance(geom, dict) else None
                lon, lat = (None, None)
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    lon, lat = float(coords[0]), float(coords[1])
                thumb = it.get("thumb_1024_url") or it.get("thumb_512_url") or it.get("thumb_url")
                out.append({
                    "osm_id": it.get("id"),
                    "name": f"mapillary_image_{it.get('id')}",
                    "lat": lat,
                    "lon": lon,
                    "address": "",
                    "tags": "image",
                    "thumbnail": thumb,
                    "source": "mapillary-image",
                    "raw": it,
                })
            return out
    except Exception:
        return []
    finally:
        if own_session:
            await session.close()


async def async_discover_places(
    bbox: Optional[tuple] = None,
    poi_type: Optional[str] = None,
    limit: int = 100,
    session: Optional[aiohttp.ClientSession] = None,
) -> List[Dict]:
    """Unified Mapillary POI discovery that uses map_features and small-bbox images.

    This replaces the legacy `api.mapillary.com/places` usage which is unsupported.
    - Prefers `map_features` search (derived POI-like objects)
    - Falls back to small-bbox images search and returns image-derived points

    Returns normalized entries similar to other providers.
    """
    token = os.getenv("MAPILLARY_TOKEN")
    if not token:
        return []

    if not bbox or len(bbox) != 4:
        return []

    # Try map_features first
    try:
        features = await async_discover_map_features(bbox=bbox, object_values=None, limit=limit, session=session)
    except Exception:
        features = []

    # If map_features returned nothing, try images-derived points
    if not features:
        try:
            images = await async_discover_images_in_bbox(bbox=bbox, limit=limit, session=session)
        except Exception:
            images = []
        return images[:limit]

    return features[:limit]
