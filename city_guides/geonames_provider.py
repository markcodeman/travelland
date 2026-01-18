import os
import aiohttp
import asyncio
import re

GEONAMES_USERNAME = os.getenv("GEONAMES_USERNAME")
GEONAMES_MAX_ROWS = int(os.getenv("GEONAMES_MAX_ROWS", "10"))


async def async_get_neighborhoods_geonames(city: str | None = None, lat: float | None = None, lon: float | None = None, max_rows: int | None = None, session: aiohttp.ClientSession = None):
    """Query GeoNames as a fallback for neighborhood-like places.

    Returns list of {id, name, slug, center, bbox, source}
    """
    if not GEONAMES_USERNAME:
        return []
    if max_rows is None:
        max_rows = GEONAMES_MAX_ROWS

    own = False
    if session is None:
        session = aiohttp.ClientSession()
        own = True

    try:
        params = {"username": GEONAMES_USERNAME, "maxRows": max_rows, "featureClass": "A"}  # administrative
        if city:
            params["q"] = city
        elif lat and lon:
            params["lat"] = lat
            params["lng"] = lon
            params["radius"] = 10  # km
        else:
            return []

        url = "http://api.geonames.org/searchJSON"
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
    finally:
        if own:
            await session.close()
