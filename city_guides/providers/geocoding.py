import json
import os
import re
from pathlib import Path
from typing import Optional

import aiohttp

from .utils import get_session


async def geocode_city(city: str, country: str = ''):
    """Resolve a city name to (lat, lon).

     Strategy (in order):
     1. Local lookup in `data/city_info_*.json` files shipped with the project.
     2. External provider(s) selected by environment variables (GEOAPIFY_API_KEY,
        OPENCAGE_API_KEY, LOCATIONIQ_KEY) in that order.
     3. As a last resort, fall back to Nominatim (kept for compatibility).

    This makes geocoding more reliable and allows operators to provide paid API keys.
    """
    if not city:
        return None

    query = city
    if country:
        query = f"{city}, {country}"

    # 1) Local data lookup
    try:
        data_dir = Path(__file__).parent.parent / "data"
        slug = re.sub(r"[^a-z0-9]+", "_", city.lower()).strip("_")
        candidate = data_dir / f"city_info_{slug}.json"
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    # prefer top-level lat/lon, else try transport.center
                    lat = j.get("lat") or (j.get("transport") or {}).get("center", {}).get("lat")
                    lon = j.get("lon") or (j.get("transport") or {}).get("center", {}).get("lon")
                    if lat and lon:
                        return {"lat": float(lat), "lon": float(lon), "display_name": j.get("display_name") or j.get("name") or city}
            except Exception:
                pass

        # also attempt a best-effort scan of city_info_*.json to match by name
        for p in data_dir.glob("city_info_*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    j = json.load(f)
                    name = (j.get("city") or j.get("city_display") or "").lower()
                    if name and name == city.lower():
                        lat = j.get("lat") or (j.get("transport") or {}).get("center", {}).get("lat")
                        lon = j.get("lon") or (j.get("transport") or {}).get("center", {}).get("lon")
                        if lat and lon:
                            return {"lat": float(lat), "lon": float(lon), "display_name": j.get("display_name") or j.get("name") or city}
            except Exception:
                continue
    except Exception:
        pass

    # Helper to try an external provider
    async def try_provider(url, params=None, headers=None, extract_latlon=None):
        try:
            async with get_session() as session:
                async with session.get(url, params=params, headers=(headers or {}), timeout=aiohttp.ClientTimeout(total=10)) as resp:  # type: ignore
                    if resp.status != 200:
                        return None, None
                    data = await resp.json()
                    if not extract_latlon:
                        return None, None
                    return extract_latlon(data)
        except Exception:
            return None, None

    # 2) Geoapify (preferred when key present)
    geoapify_key = os.getenv("GEOAPIFY_API_KEY")
    if geoapify_key:
        url = "https://api.geoapify.com/v1/geocode/search"
        params = {"text": city, "apiKey": geoapify_key, "limit": 1}
        lat, lon = await try_provider(url, params=params, extract_latlon=lambda d: (
            (d.get("features")[0].get("properties").get("lat"), d.get("features")[0].get("properties").get("lon"))
        ) if d.get("features") else (None, None))
        if lat and lon:
            return {"lat": float(lat), "lon": float(lon), "display_name": city}

    # 3) OpenCage
    opencage_key = os.getenv("OPENCAGE_API_KEY")
    if opencage_key:
        url = "https://api.opencagedata.com/geocode/v1/json"
        params = {"q": city, "key": opencage_key, "limit": 1}
        lat, lon = await try_provider(url, params=params, extract_latlon=lambda d: (d["results"][0]["geometry"]["lat"], d["results"][0]["geometry"]["lng"]) if d.get("results") else (None, None))
        if lat and lon:
            return {"lat": float(lat), "lon": float(lon), "display_name": city}

    # 4) LocationIQ
    locationiq_key = os.getenv("LOCATIONIQ_KEY") or os.getenv("LOCATIONIQ_TOKEN")
    if locationiq_key:
        url = "https://us1.locationiq.com/v1/search.php"
        params = {"key": locationiq_key, "q": city, "format": "json", "limit": 1}
        lat, lon = await try_provider(url, params=params, extract_latlon=lambda d: (float(d[0]["lat"]), float(d[0]["lon"])) if isinstance(d, list) and d else (None, None))
        if lat and lon:
            return {"lat": float(lat), "lon": float(lon), "display_name": city}

    # 5) Last-resort: Nominatim (leave as fallback but deprioritised)
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": city, "format": "json", "limit": 1}
        headers = {"User-Agent": "city-guides-app", "Accept-Language": "en"}
        async with get_session() as session:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    print(f"geocode_city nominatim HTTP {resp.status}")
                resp.raise_for_status()
                data = await resp.json()
                if data:
                    return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"]), "display_name": data[0]["display_name"]}
    except Exception as e:
        print(f"geocode_city fallback nominatim failed: {e}")

    return None


async def reverse_geocode(lat, lon):
    """Get address from coordinates using Nominatim reverse geocoding."""
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"lat": lat, "lon": lon, "format": "json", "zoom": 18}
    try:
        async with get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:  # type: ignore
                if resp.status != 200:
                    print(f"[DEBUG geocoding.py] reverse_geocode HTTP error: {resp.status}")
                resp.raise_for_status()
                data = await resp.json()
                if data and "display_name" in data:
                    return data["display_name"]
    except Exception as e:
        print(f"[DEBUG geocoding.py] reverse_geocode Exception: {e}")
        return None
    return None