import os
import json
import requests
import datetime
import threading
import os
import json
import requests
import datetime
import threading
import shutil
from pathlib import Path
from urllib.parse import urlparse
import re

_CACHE_FILE = Path(__file__).resolve().parents[1] / "data" / "banner_cache.json"
_CACHE_LOCK = threading.Lock()
_BANNERS_DIR = Path(__file__).resolve().parents[1] / "static" / "banners"


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


def _slugify(s):
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "city"


def _ensure_banners_dir():
    try:
        _BANNERS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _ext_from_url(url):
    try:
        p = urlparse(url)
        _, ext = os.path.splitext(p.path)
        ext = ext.lower()
        if ext in (".jpg", ".jpeg", ".png", ".webp"):
            return ext
    except Exception:
        pass
    return ".jpg"


def fetch_banner_from_wikipedia(city):
    """Best-effort: fetch article thumbnail from Wikipedia (returns remote url and attribution)"""
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "prop": "pageimages",
            "titles": city,
            "format": "json",
            "redirects": 1,
            "pithumbsize": 2000,
        }
        r = requests.get(
            url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
        )
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for p in pages.values():
            thumb = p.get("thumbnail", {}).get("source")
            if thumb:
                pageid = p.get("pageid")
                pageurl = (
                    f"https://en.wikipedia.org/?curid={pageid}"
                    if pageid
                    else "https://en.wikipedia.org/"
                )
                return {
                    "remote_url": thumb,
                    "attribution": f"Image via Wikimedia/Wikipedia ({pageurl})",
                }
    except Exception:
        pass

    # Fallback strategy: try searching for skyline / aerial images related to the city
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        search_queries = [
            f"{city} skyline",
            f"{city} city skyline",
            f"{city} skyline aerial",
            f"{city} skyline at night",
            f"{city} panorama",
            city,
        ]
        for q in search_queries:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": q,
                "format": "json",
                "srlimit": 5,
            }
            r = requests.get(
                search_url,
                params=params,
                headers={"User-Agent": "TravelLand/1.0"},
                timeout=8,
            )
            r.raise_for_status()
            results = r.json().get("query", {}).get("search", [])
            titles = [r.get("title") for r in results if r.get("title")]
            if not titles:
                continue
            # Request thumbnails for the candidate titles
            params2 = {
                "action": "query",
                "prop": "pageimages",
                "titles": "|".join(titles[:5]),
                "format": "json",
                "pithumbsize": 2000,
                "redirects": 1,
            }
            r2 = requests.get(
                search_url,
                params=params2,
                headers={"User-Agent": "TravelLand/1.0"},
                timeout=8,
            )
            r2.raise_for_status()
            data2 = r2.json()
            pages2 = data2.get("query", {}).get("pages", {})
            for p2 in pages2.values():
                thumb = p2.get("thumbnail", {}).get("source")
                if thumb:
                    pageid = p2.get("pageid")
                    pageurl = (
                        f"https://en.wikipedia.org/?curid={pageid}"
                        if pageid
                        else "https://en.wikipedia.org/"
                    )
                    return {
                        "remote_url": thumb,
                        "attribution": f"Image via Wikimedia/Wikipedia ({pageurl})",
                    }
    except Exception:
        pass

    return None


def _download_image(url, dest_path):
    tmp = dest_path.with_suffix(dest_path.suffix + ".tmp")
    try:
        with requests.get(
            url, stream=True, headers={"User-Agent": "TravelLand/1.0"}, timeout=12
        ) as r:
            r.raise_for_status()
            _ensure_banners_dir()
            with tmp.open("wb") as f:
                shutil.copyfileobj(r.raw, f)
        tmp.replace(dest_path)
        return True
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        return False


def get_banner_for_city(city):
    """Return banner info for a city.

    Behavior is configurable via environment variable `BANNER_STORE_LOCAL`:
      - '1' (store locally under `static/banners/` and return a local `/static` URL)
      - any other value (default): return the remote Wikimedia URL directly and do not store the file locally.

    Cached metadata is kept in `data/banner_cache.json` either way; TTL (days) is controlled by BANNER_CACHE_TTL_DAYS.
    """
    if not city:
        return None
    key = city.strip().lower()
    ttl = int(os.getenv("BANNER_CACHE_TTL_DAYS", "7"))
    store_local = os.getenv("BANNER_STORE_LOCAL", "0") == "1"

    with _CACHE_LOCK:
        c = _load_cache()
        rec = c.get(key)
        if (
            rec
            and rec.get("generated_at")
            and not _is_expired(rec.get("generated_at"), ttl)
        ):
            # If we stored a local filename previously and local storage is enabled, prefer it
            if store_local and rec.get("local_filename"):
                local_fn = rec.get("local_filename")
                local_path = _BANNERS_DIR / local_fn
                if local_path.exists():
                    return {
                        "url": f"/static/banners/{local_fn}",
                        "attribution": rec.get("attribution"),
                    }
            # Otherwise, if we have a remote_url cached, return it
            if rec.get("remote_url"):
                return {
                    "url": rec.get("remote_url"),
                    "attribution": rec.get("attribution"),
                }

    # Fetch remote thumbnail metadata
    val = fetch_banner_from_wikipedia(city)
    if not val:
        return None

    remote_url = val.get("remote_url")
    attribution = val.get("attribution")

    # If caller doesn't want local storage, cache remote_url and return it
    if not store_local:
        with _CACHE_LOCK:
            c = _load_cache()
            c[key] = {
                "remote_url": remote_url,
                "attribution": attribution,
                "generated_at": datetime.datetime.utcnow().isoformat(),
            }
            _write_cache(c)
        return {"url": remote_url, "attribution": attribution}

    # Otherwise, download and store locally under static/banners
    slug = _slugify(city)
    ext = _ext_from_url(remote_url)
    filename = f"{slug}{ext}"
    dest_path = _BANNERS_DIR / filename

    # If file exists and is recent enough, reuse
    if dest_path.exists():
        try:
            mtime = datetime.datetime.utcfromtimestamp(dest_path.stat().st_mtime)
            if (datetime.datetime.utcnow() - mtime).days < ttl:
                with _CACHE_LOCK:
                    c = _load_cache()
                    c[key] = {
                        "local_filename": filename,
                        "attribution": attribution,
                        "generated_at": datetime.datetime.utcnow().isoformat(),
                        "remote_url": remote_url,
                    }
                    _write_cache(c)
                return {
                    "url": f"/static/banners/{filename}",
                    "attribution": attribution,
                }
        except Exception:
            pass

    ok = _download_image(remote_url, dest_path)
    if not ok:
        # fallback to returning remote URL
        with _CACHE_LOCK:
            c = _load_cache()
            c[key] = {
                "remote_url": remote_url,
                "attribution": attribution,
                "generated_at": datetime.datetime.utcnow().isoformat(),
            }
            _write_cache(c)
        return {"url": remote_url, "attribution": attribution}

    with _CACHE_LOCK:
        c = _load_cache()
        c[key] = {
            "local_filename": filename,
            "attribution": attribution,
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "remote_url": remote_url,
        }
        _write_cache(c)

    return {"url": f"/static/banners/{filename}", "attribution": attribution}
