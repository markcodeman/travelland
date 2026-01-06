import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import re
from typing import List, Dict

import overpass_provider
try:
    import opentripmap_provider
except Exception:
    opentripmap_provider = None
try:
    import duckduckgo_provider
except Exception:
    duckduckgo_provider = None


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
        'name': e.get('name') or (e.get('tags','').split('=')[-1] if e.get('tags') else 'Unknown'),
        'lat': float(e.get('lat') or e.get('latitude') or 0),
        'lon': float(e.get('lon') or e.get('longitude') or 0),
        'osm_url': e.get('osm_url',''),
        'tags': e.get('tags',''),
        'website': e.get('website',''),
        'amenity': e.get('amenity',''),
        'provider': e.get('provider') or 'osm',
        'raw': e,
    }


def _normalize_generic_entry(e: Dict) -> Dict:
    """Handle entries from web or other mixed sources."""
    return {
        'id': e.get('id') or e.get('osm_id') or e.get('place_id') or '',
        'name': e.get('name') or 'Unknown',
        'lat': float(e.get('lat') or e.get('latitude') or 0),
        'lon': float(e.get('lon') or e.get('longitude') or 0),
        'osm_url': e.get('osm_url',''),
        'tags': e.get('tags',''),
        'website': e.get('website',''),
        'description': e.get('description',''),
        'amenity': e.get('amenity', 'restaurant'),
        'rating': e.get('rating'),
        'budget': e.get('budget'),
        'price_range': e.get('price_range'),
        'provider': e.get('provider') or 'web',
        'raw': e,
    }


def discover_restaurants(city: str, cuisine: str = None, limit: int = 100, local_only: bool = False) -> List[Dict]:
    """Orchestrate multiple providers concurrently, normalize, dedupe, and rank results.

    Returns list of unified entries with at least keys: id,name,lat,lon,osm_url,provider,raw
    """
    results = []

    calls = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        # Overpass (OSM)
        calls.append(ex.submit(overpass_provider.discover_restaurants, city, limit, cuisine, local_only))
        # OpenTripMap (optional)
        if opentripmap_provider:
            try:
                calls.append(ex.submit(opentripmap_provider.discover_restaurants, city, limit, cuisine))
            except Exception:
                pass
        # DuckDuckGo (optional)
        if duckduckgo_provider:
            try:
                calls.append(ex.submit(duckduckgo_provider.discover_restaurants, city, limit, cuisine))
            except Exception:
                pass

        # gather
        for fut in as_completed(calls):
            try:
                r = fut.result()
                if not r:
                    continue
                
                for e in r:
                    # check if already a provider and use generic if so
                    if e.get('provider') in ['web', 'opentripmap', 'google_places']:
                        entry = _normalize_generic_entry(e)
                    elif 'osm_url' in e or 'tags' in e:
                        entry = _normalize_osm_entry(e)
                    else:
                        entry = _normalize_generic_entry(e)

                    if local_only:
                        name_lower = entry['name'].lower()
                        if any(chain.lower() in name_lower for chain in overpass_provider.CHAIN_KEYWORDS):
                            continue
                    results.append(entry)
            except Exception:
                continue

    # Deduplicate by osm_url first, then by name+proximity
    deduped = []
    seen_urls = set()
    for entry in results:
        url = (entry.get('website') or entry.get('osm_url') or '').strip()
        if url and 'openstreetmap.org' not in url: # use real website for deduping if possible
            if url in seen_urls:
                continue
            seen_urls.add(url)
        
        # compare by normalized name
        name_norm = _norm_name(entry.get('name',''))
        merged = False
        for e2 in deduped:
            if _norm_name(e2.get('name','')) == name_norm:
                # If both have valid lat/lon, check proximity
                lat1, lon1 = entry.get('lat'), entry.get('lon')
                lat2, lon2 = e2.get('lat'), e2.get('lon')
                
                if lat1 and lon1 and lat2 and lon2:
                    d = _haversine_meters(lat1, lon1, lat2, lon2)
                    if d < 1000: # increased to 1km for web results
                        merged = True
                        break
                else: 
                    # If one or both lack spatial data, we only merge if the website matches too
                    # Or if the name is identical and we are willing to risk it.
                    # For web-only results, if URLs are different, keep them.
                    u1 = (entry.get('website') or entry.get('osm_url') or '').strip()
                    u2 = (e2.get('website') or e2.get('osm_url') or '').strip()
                    if u1 and u2 and u1 != u2:
                        continue # Different websites, likely different places
                    
                    merged = True
                    break
        if not merged:
            deduped.append(entry)

    # Ranking: prefer entries with webpage, then OSM (usually better data), then web
    def _score(e):
        score = 0
        if e.get('rating'): score += float(e['rating']) * 2
        if e.get('website'): score += 5
        if e.get('provider') == 'osm': score += 10
        if e.get('provider') == 'web': score += 2 # web results as backfill
        return score

    deduped.sort(key=_score, reverse=True)
    return deduped[:limit]
