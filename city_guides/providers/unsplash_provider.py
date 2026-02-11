import os
import json
import aiohttp
import datetime
import threading
from pathlib import Path
from urllib.parse import urlencode

_CACHE_FILE = Path(__file__).resolve().parents[1] / "data" / "unsplash_cache.json"
_CACHE_LOCK = threading.Lock()

def _load_cache():
    try:
        if not _CACHE_FILE.exists():
            return {}
        with _CACHE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_cache(c):
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=2)
        tmp.replace(_CACHE_FILE)
    except Exception:
        pass

def _is_expired(iso_str, ttl_days):
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        return (datetime.datetime.utcnow() - dt).days >= ttl_days
    except Exception:
        return True

async def fetch_unsplash_image(query, session: aiohttp.ClientSession = None):
    """Fetch an image from Unsplash API with proper attribution and UTM tracking."""
    access_key = os.getenv("UNSPLASH_KEY")
    if not access_key:
        return None

    ttl = int(os.getenv("UNSPLASH_CACHE_TTL_DAYS", "7"))

    with _CACHE_LOCK:
        c = _load_cache()
        cached = c.get(query)
        if cached and cached.get("generated_at") and not _is_expired(cached.get("generated_at"), ttl):
            return cached

    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True

    try:
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "per_page": 1,
            "orientation": "landscape"
        }
        headers = {
            "Authorization": f"Client-ID {access_key}",
            "User-Agent": "TravelLand/1.0"
        }

        async with session.get(url, params=params, headers=headers, timeout=10) as r:
            if r.status != 200:
                return None
            data = await r.json()
            if not data.get("results"):
                return None

            photo = data["results"][0]
            image_url = photo["urls"]["regular"]
            photographer = photo["user"]["name"]
            photographer_username = photo["user"]["username"]
            photographer_url = photo["user"]["links"]["html"]

            # Add UTM tracking for attribution
            attribution_url = f"{photographer_url}?utm_source=travelland&utm_medium=referral"

            # Prepare download endpoint
            download_endpoint = photo["links"]["download_location"]
            download_url = f"{download_endpoint}?client_id={access_key}"

            result = {
                "image_url": image_url,
                "photographer": photographer,
                "photographer_username": photographer_username,
                "photographer_url": attribution_url,
                "download_url": download_url,
                "attribution_text": f"Photo by {photographer} on Unsplash"
            }

            with _CACHE_LOCK:
                c = _load_cache()
                c[query] = {
                    "data": result,
                    "generated_at": datetime.datetime.utcnow().isoformat()
                }
                _write_cache(c)

            return result
    finally:
        if own_session:
            await session.close()

async def trigger_unsplash_download(download_url, session: aiohttp.ClientSession = None):
    """Trigger a download request to Unsplash to increment the download counter."""
    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True

    try:
        headers = {
            "User-Agent": "TravelLand/1.0"
        }
        async with session.get(download_url, headers=headers, timeout=10) as r:
            return r.status == 200
    finally:
        if own_session:
            await session.close()