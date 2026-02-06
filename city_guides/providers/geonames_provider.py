import os
import aiohttp
import re

from .utils import get_session

GEONAMES_USERNAME = os.getenv("GEONAMES_USERNAME")
GEONAMES_MAX_ROWS = int(os.getenv("GEONAMES_MAX_ROWS", "20"))


async def async_get_neighborhoods_geonames(city: str | None = None, lat: float | None = None, lon: float | None = None, max_rows: int | None = None, session: aiohttp.ClientSession = None):
    """Query GeoNames as a fallback for neighborhood-like places.

    Returns list of {id, name, slug, center, bbox, source}
    """
    # Ensure we have a GeoNames username — if it's not in the environment, try loading from a local .env
    username = GEONAMES_USERNAME or os.getenv("GEONAMES_USERNAME")
    if not username:
        try:
            # Try to read repository-level .env as a fallback (do not overwrite environment)
            env_path = Path(__file__).resolve().parents[1] / ".env"
            if env_path.exists():
                with env_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEONAMES_USERNAME="):
                            username = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
        except Exception:
            username = None
    if not username:
        return []
    if max_rows is None:
        max_rows = GEONAMES_MAX_ROWS

    # pass resolved username into impl via env so the implementation can access it via os.getenv
    os.environ.setdefault("GEONAMES_USERNAME", username)
    if session is None:
        async with get_session() as session:
            return await _async_get_neighborhoods_geonames_impl(city, lat, lon, max_rows, session)
    else:
        return await _async_get_neighborhoods_geonames_impl(city, lat, lon, max_rows, session)


async def _async_get_neighborhoods_geonames_impl(city, lat, lon, max_rows, session):
    # Prefer populated places (featureClass 'P') to capture small localities/neighborhoods
    # Start with a permissive query (no featureClass filter) to capture both administrative
    # and populated-place features; we'll narrow if needed.
    # Build params and choose appropriate GeoNames endpoint.
    if lat and lon:
        # Use findNearbyPlaceName for lat/lon lookups — it reliably returns nearby populated places.
        params = {"username": GEONAMES_USERNAME, "lat": lat, "lng": lon, "radius": int(os.getenv("GEONAMES_RADIUS_KM", "20")), "maxRows": max_rows}
        url = "http://api.geonames.org/findNearbyPlaceNameJSON"
    elif city:
        params = {"username": GEONAMES_USERNAME, "maxRows": max_rows, "q": city}
        url = "http://api.geonames.org/searchJSON"
    else:
        return []

    try:
        async with session.get(url, params=params, timeout=10) as resp:
            if resp.status != 200:
                return []
            j = await resp.json()
            geos = j.get("geonames", [])
            results = []
            for g in geos:
                name = g.get("name") or g.get("toponymName")
                if not name:
                    continue
                geoid = g.get("geonameId")
                latv = g.get("lat")
                lonv = g.get("lng") or g.get("lon")
                center = None
                if latv and lonv:
                    try:
                        center = {"lat": float(latv), "lon": float(lonv)}
                    except Exception:
                        center = None
                bbox = None
                # GeoNames sometimes provides bounding box via 'bbox' keys depending on the service
                for k in ("north", "south", "east", "west"):
                    if k in g:
                        bbox = {
                            "minlat": float(g.get("south", g.get("lat", 0))),
                            "minlon": float(g.get("west", g.get("lon", 0))),
                            "maxlat": float(g.get("north", g.get("lat", 0))),
                            "maxlon": float(g.get("east", g.get("lon", 0))),
                        }
                        break
                results.append({
                    "id": f"geonames/{geoid}",
                    "name": name,
                    "slug": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
                    "center": center,
                    "bbox": bbox,
                    "source": "geonames",
                })
            return results
    except Exception:
        return []
