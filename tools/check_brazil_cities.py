#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from city_guides.src.persistence import _search_impl

SEED_PATH = ROOT / 'data' / 'seeded_cities.json'

def load_seeded():
    if not SEED_PATH.exists():
        print('seeded_cities.json not found at', SEED_PATH)
        return []
    data = json.loads(SEED_PATH.read_text())
    return data.get('cities', [])


def check_city(city_entry):
    name = city_entry.get('name')
    country = city_entry.get('country') or city_entry.get('countryCode') or ''
    print(f'Checking: {name} ({country})')
    payload = {'query': name, 'limit': 10}
    try:
        res = _search_impl(payload)
    except Exception as e:
        return {'city': name, 'error': str(e)}

    quick = (res.get('quick_guide') or '').strip()
    quick_len = len(quick)
    venues = res.get('venues', []) or []
    return {
        'city': name,
        'country': country,
        'quick_len': quick_len,
        'has_quick': quick_len > 100,
        'venues_found': len(venues),
        'venues_sample': [v.get('name') for v in venues[:5]],
        'debug_info': res.get('debug_info', {})
    }


def main():
    cities = load_seeded()
    brazil = [c for c in cities if (c.get('countryCode') or c.get('country') or '').upper() in ('BR','BRA','BRAZIL')]
    if not brazil:
        # fallback: include any city with country name containing 'Brazil'
        brazil = [c for c in cities if 'brazil' in (c.get('country','') or '').lower()]

    print(f'Found {len(brazil)} seeded cities for Brazil')
    results = []
    for c in brazil:
        r = check_city(c)
        results.append(r)

    out = {'checked': len(results), 'results': results}
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
