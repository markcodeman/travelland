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

_CACHE_FILE = Path(__file__).resolve().parents[1] / 'data' / 'banner_cache.json'
_CACHE_LOCK = threading.Lock()
_BANNERS_DIR = Path(__file__).resolve().parents[1] / 'static' / 'banners'


def _load_cache():
    try:
        if not _CACHE_FILE.exists():
            return {}
        with _CACHE_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _write_cache(c):
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_FILE.with_suffix('.tmp')
        with tmp.open('w', encoding='utf-8') as f:
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
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s or 'city'


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
        if ext in ('.jpg', '.jpeg', '.png', '.webp'):
            return ext
    except Exception:
        pass
    return '.jpg'


def fetch_banner_from_wikipedia(city):
    """Best-effort: fetch article thumbnail from Wikipedia (returns remote url and attribution)
    """
    try:
        url = 'https://en.wikipedia.org/w/api.php'
        params = {
            'action': 'query',
            'prop': 'pageimages',
            'titles': city,
            'format': 'json',
            'redirects': 1,
            'pithumbsize': 2000
        }
        r = requests.get(url, params=params, headers={'User-Agent': 'TravelLand/1.0'}, timeout=8)
        r.raise_for_status()
        data = r.json()
        pages = data.get('query', {}).get('pages', {})
        for p in pages.values():
            thumb = p.get('thumbnail', {}).get('source')
            if thumb:
                pageid = p.get('pageid')
                pageurl = f'https://en.wikipedia.org/?curid={pageid}' if pageid else 'https://en.wikipedia.org/'
                return {'remote_url': thumb, 'attribution': f'Image via Wikimedia/Wikipedia ({pageurl})'}
    except Exception:
        return None
    return None


def _download_image(url, dest_path):
    tmp = dest_path.with_suffix(dest_path.suffix + '.tmp')
    try:
        with requests.get(url, stream=True, headers={'User-Agent': 'TravelLand/1.0'}, timeout=12) as r:
            r.raise_for_status()
            _ensure_banners_dir()
            with tmp.open('wb') as f:
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
    """Return {url, attribution} where url is a local /static path (best-effort).
    Caches results in data/banner_cache.json and stores files under static/banners/.
    TTL (days) controlled by BANNER_CACHE_TTL_DAYS env var.
    """
    if not city:
        return None
    key = city.strip().lower()
    ttl = int(os.getenv('BANNER_CACHE_TTL_DAYS', '7'))

    with _CACHE_LOCK:
        c = _load_cache()
        rec = c.get(key)
        # If we have a cached local filename and file exists and not expired, return it
        if rec and rec.get('generated_at') and not _is_expired(rec.get('generated_at'), ttl):
            local_fn = rec.get('local_filename')
            if local_fn:
                local_path = _BANNERS_DIR / local_fn
                if local_path.exists():
                    return {'url': f'/static/banners/{local_fn}', 'attribution': rec.get('attribution')}

    # Fetch remote thumbnail
    val = fetch_banner_from_wikipedia(city)
    if not val:
        return None

    remote_url = val.get('remote_url')
    attribution = val.get('attribution')

    # Download into static/banners/<slug><ext>
    slug = _slugify(city)
    ext = _ext_from_url(remote_url)
    filename = f"{slug}{ext}"
    dest_path = _BANNERS_DIR / filename

    # If file exists and is recent enough, reuse
    if dest_path.exists():
        # check mtime vs ttl
        try:
            mtime = datetime.datetime.utcfromtimestamp(dest_path.stat().st_mtime)
            if (datetime.datetime.utcnow() - mtime).days < ttl:
                # Update cache record and return
                with _CACHE_LOCK:
                    c = _load_cache()
                    c[key] = {'local_filename': filename, 'attribution': attribution, 'generated_at': datetime.datetime.utcnow().isoformat()}
                    _write_cache(c)
                return {'url': f'/static/banners/{filename}', 'attribution': attribution}
        except Exception:
            pass

    ok = _download_image(remote_url, dest_path)
    if not ok:
        return None

    # update cache
    with _CACHE_LOCK:
        c = _load_cache()
        c[key] = {'local_filename': filename, 'attribution': attribution, 'generated_at': datetime.datetime.utcnow().isoformat()}
        _write_cache(c)

    return {'url': f'/static/banners/{filename}', 'attribution': attribution}
