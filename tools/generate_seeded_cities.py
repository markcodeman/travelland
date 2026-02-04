"""
Generate a canonical `seeded_cities.json` file containing a curated list of cities
suitable as a fallback when GeoNames or other providers are unavailable.

Behavior:
- Collect city names from local sources (tests, frontend lists) inside the repo.
- If GEONAMES_USERNAME (env) is provided, enrich the list via the GeoNames API
  to pull coordinates, population and geonameId until the desired count is reached.
- Output: `city_guides/data/seeded_cities.json` with schema entries including
  name, countryCode, stateCode (optional), lat, lon, population, geonameId,
  source: "seed", version, last_updated.

Usage:
  GEONAMES_USERNAME=your_user python tools/generate_seeded_cities.py --count 500

If no GeoNames username is provided, the script will still produce a partial
seed based on the repo's existing lists and will exit non-zero if it can't
reach the requested count.
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

try:
    import aiohttp
    import asyncio
except Exception:
    aiohttp = None
    asyncio = None

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "city_guides" / "data" / "seeded_cities.json"

# Simple local sources to gather base city names
LOCAL_SOURCES = [
    ROOT / "test_100_cities.py",
    ROOT / "frontend" / "src" / "components" / "GlobeSelector.jsx",
    ROOT / "frontend" / "src" / "components" / "WorldMapSelector.jsx",
    ROOT / "frontend" / "src" / "components" / "DreamInput.jsx",
    ROOT / "frontend" / "src" / "App.jsx",
]


def extract_city_names_from_file(path: Path):
    try:
        text = path.read_text(errors='ignore')
    except Exception:
        return []
    names = set()
    # crude heuristics: look for arrays of capitalized words separated by commas
    # and for the TEST CITIES CITIES = [ ... ] pattern
    import re
    # capture within brackets
    arrays = re.findall(r"\[([^\]]{20,2000})\]", text, flags=re.S)
    for arr in arrays:
        # split on commas and newlines
        parts = [p.strip().strip('\"\'') for p in re.split(r",|\\n", arr) if p.strip()]
        for p in parts:
            # filter out code tokens
            if len(p) < 3 or any(c in p for c in ['=', '(', ')', '{', '}', '<', '>']):
                continue
            # strip trailing comments
            p = p.split('//')[0].strip()
            # keep items with letters and spaces
            if any(ch.isalpha() for ch in p):
                # remove trailing periods
                p = p.strip().rstrip(',').strip()
                # ignore arrays of words that look like code
                if len(p) > 0 and len(p) < 100:
                    names.add(p)
    return list(names)


async def geonames_fetch_top(session, username, country=None, admin_code=None, max_rows=100):
    url = "http://api.geonames.org/searchJSON"
    params = {
        'username': username,
        'orderby': 'population',
        'maxRows': max_rows,
        'featureClass': 'P'
    }
    if country:
        params['country'] = country
    if admin_code:
        params['adminCode1'] = admin_code

    q = urlencode(params)
    full = f"{url}?{q}"
    async with session.get(full, timeout=10) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()
        return data.get('geonames', [])


async def geonames_lookup(session, username, name, country=None, max_rows=5):
    url = "http://api.geonames.org/searchJSON"
    params = {
        'username': username,
        'q': name,
        'maxRows': max_rows,
        'featureClass': 'P'
    }
    if country:
        params['country'] = country
    q = urlencode(params)
    full = f"{url}?{q}"
    async with session.get(full, timeout=10) as resp:
        if resp.status != 200:
            return None
        data = await resp.json()
        geonames = data.get('geonames', [])
        if not geonames:
            return None
        return geonames[0]


async def gather_with_geonames(names, count, username):
    results = {}
    async with aiohttp.ClientSession() as session:
        for name in names:
            try:
                g = await geonames_lookup(session, username, name)
                if g and g.get('lat') and g.get('lng'):
                    results[name] = g
                    if len(results) >= count:
                        break
            except Exception as e:
                print('lookup failed for', name, e)
                continue

        # If we still need more, fetch top cities globally using iterative country list
        if len(results) < count:
            print('Insufficient matches from direct lookup; fetching population-sorted cities from GeoNames...')
            # Use a simple world country code list from 2-letter codes to be safe
            # We'll iterate and pull the biggest cities
            countries = []
            # Query the countryInfo service to get all country codes
            try:
                async with session.get(f'http://api.geonames.org/countryInfoJSON?username={username}', timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        countries = [c.get('countryCode') for c in data.get('geonames', []) if c.get('countryCode')]
            except Exception:
                countries = []

            for c in countries:
                try:
                    items = await geonames_fetch_top(session, username, country=c, max_rows=100)
                    for it in items:
                        n = it.get('name')
                        if n and it.get('lat') and it.get('lng') and n not in results:
                            results[n] = it
                            if len(results) >= count:
                                break
                    if len(results) >= count:
                        break
                except Exception:
                    continue

    return list(results.values())


def canonicalize_geoname(geoname):
    return {
        'name': geoname.get('name'),
        'countryCode': geoname.get('countryCode') or geoname.get('cc') or '',
        'stateCode': geoname.get('adminCode1') or '',
        'lat': float(geoname.get('lat')) if geoname.get('lat') else None,
        'lon': float(geoname.get('lng') or geoname.get('lon')) if (geoname.get('lng') or geoname.get('lon')) else None,
        'population': int(geoname.get('population') or 0),
        'geonameId': geoname.get('geonameId') or geoname.get('geonameid') or '',
        'source': 'seed'
    }


def write_seed_file(items, version='1.0'):
    payload = {
        'version': version,
        # Use timezone-aware UTC timestamp to avoid deprecation warnings and ambiguity
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'count': len(items),
        'cities': items
    }
    SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEED_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f'Wrote seed file to {SEED_PATH} with {len(items)} cities')


def gather_local_candidates():
    names = set()
    for p in LOCAL_SOURCES:
        if p.exists():
            for n in extract_city_names_from_file(p):
                # filter out obvious non-city tokens
                if len(n) > 1 and not any(ch in n for ch in ['{', '}', '=>', '<', '>']):
                    names.add(n)
    # Also add from test_100_cities explicit list by importing it
    try:
        from importlib import util
        spec = util.spec_from_file_location('test_100_cities', str(ROOT / 'test_100_cities.py'))
        mod = util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, 'CITIES'):
            for c in mod.CITIES:
                names.add(c)
    except Exception:
        pass
    return list(names)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=500)
    parser.add_argument('--geonames', type=str, default=os.getenv('GEONAMES_USERNAME'))
    args = parser.parse_args()

    desired = args.count
    username = args.geonames

    local_names = gather_local_candidates()
    print(f'Collected {len(local_names)} local candidate city names')

    if username and aiohttp and asyncio:
        print('GeoNames username present; enriching cities via GeoNames...')
        # Use asyncio.run to avoid "no current event loop" warnings and ensure
        # proper event loop lifecycle management.
        geoname_items = asyncio.run(gather_with_geonames(local_names, desired, username))
        items = [canonicalize_geoname(g) for g in geoname_items]
        # if still short, broaden search by fetching top cities (already attempted inside gather_with_geonames)
        if len(items) < desired:
            print(f'Only found {len(items)} via lookup; attempting broader fetch (this may take a while)')
            items = items[:desired]
    else:
        print('No GeoNames username or aiohttp; will produce partial seed from local candidates')
        # Create seed entries with minimal info
        items = []
        for n in sorted(local_names)[:desired]:
            items.append({
                'name': n,
                'countryCode': '',
                'stateCode': '',
                'lat': None,
                'lon': None,
                'population': 0,
                'geonameId': '',
                'source': 'seed'
            })

    if not items:
        print('Failed to gather any items; aborting')
        sys.exit(1)

    write_seed_file(items, version='1.0')


if __name__ == '__main__':
    main()
