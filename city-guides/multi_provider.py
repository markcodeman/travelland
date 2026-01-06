import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import re
from typing import List, Dict

import overpass_provider
import places_provider


def _norm_name(name: str) -> str:
    if not name:
        return ''
    s = name.lower()
    s = re.sub(r"[^a-z0-9 ]+", ' ', s)
    s = re.sub(r"\s+", ' ', s).strip()
    return s


def _haversine_meters(lat1, lon1, lat2, lon2):
    # returns distance in meters
    if None in (lat1, lon1, lat2, lon2):
        return 1e9
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _normalize_osm_entry(e: Dict) -> Dict:
    # e expected from overpass_provider.discover_restaurants
    return {
        'id': e.get('osm_id') or e.get('id') or '',
        'name': e.get('name') or e.get('tags','').split('=')[-1] if e.get('tags') else 'Unknown',
        'lat': float(e.get('lat') or e.get('latitude') or 0),
        'lon': float(e.get('lon') or e.get('longitude') or 0),
        'osm_url': e.get('osm_url',''),
        'tags': e.get('tags',''),
        'website': e.get('website',''),
        'provider': 'osm',
        'raw': e,
    }


def _normalize_places_entry(e: Dict) -> Dict:
    # places_provider returns different keys
    return {
        'id': e.get('place_id') or e.get('id') or '',
        'name': e.get('name') or 'Unknown',
        'lat': float(e.get('latitude') or e.get('lat') or 0),
        'lon': float(e.get('longitude') or e.get('lon') or 0),
        'osm_url': e.get('osm_url',''),
        'tags': e.get('tags',''),
        'website': e.get('website',''),
        'provider': 'google_places' if places_provider.gmaps else 'places',
        'rating': e.get('rating'),
        'user_ratings_total': e.get('user_ratings_total', 0),
        'raw': e,
    }


def discover_restaurants(city: str, cuisine: str = None, limit: int = 100) -> List[Dict]:
    """Orchestrate multiple providers concurrently, normalize, dedupe, and rank results.

    Returns list of unified entries with at least keys: id,name,lat,lon,osm_url,provider,raw
    """
    results = []

    calls = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        # Overpass (OSM)
        calls.append(ex.submit(overpass_provider.discover_restaurants, city, limit, cuisine))
        # Google Places / places_provider (if available)
        try:
            calls.append(ex.submit(places_provider.discover_restaurants, city, limit, cuisine))
        except Exception:
            pass

        # gather
        for fut in as_completed(calls):
            try:
                r = fut.result()
                if not r:
                    continue
                # detect source by inspecting elements
                if isinstance(r, list) and r and (r[0].get('place_id') or r[0].get('rating')):
                    # likely places_provider
                    for e in r:
                        results.append(_normalize_places_entry(e))
                else:
                    for e in r:
                        # overpass entries may already be normalized or raw mapping
                        # ensure fields exist
                        if 'osm_url' in e or 'tags' in e:
                            results.append(_normalize_osm_entry(e))
                        else:
                            results.append(_normalize_places_entry(e))
            except Exception:
                continue

    # Deduplicate by osm_url, then by name+proximity
    deduped = []
    seen_urls = set()
    for entry in results:
        url = (entry.get('osm_url') or '').strip()
        if url:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            deduped.append(entry)
            continue
        # otherwise compare by normalized name and proximity
        name_norm = _norm_name(entry.get('name',''))
        merged = False
        for e2 in deduped:
            if _norm_name(e2.get('name','')) == name_norm:
                d = _haversine_meters(entry.get('lat',0), entry.get('lon',0), e2.get('lat',0), e2.get('lon',0))
                if d < 100:  # within 100 meters
                    # prefer entry with rating or from google_places
                    pref = e2
                    if entry.get('provider') == 'google_places' or (entry.get('rating') or 0) > (e2.get('rating') or 0):
                        # replace
                        deduped.remove(e2)
                        deduped.append(entry)
                    merged = True
                    break
        if not merged:
            deduped.append(entry)

    # Simple ranking: prefer entries with rating, then google_places, then by presence of website
    def _score(e):
        score = 0
        score += (e.get('rating') or 0) * 10
        if e.get('provider') == 'google_places':
            score += 5
        if e.get('website'):
            score += 2
        return score

    deduped.sort(key=_score, reverse=True)
    # limit
    return deduped[:limit]
