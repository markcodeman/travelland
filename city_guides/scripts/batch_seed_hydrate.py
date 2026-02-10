#!/usr/bin/env python3
"""Batch hydrate neighborhood seeds for a list of cities/countries."""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from city_guides.providers.overpass_provider import async_get_neighborhoods
from city_guides.providers.utils import get_session

import argparse

parser = argparse.ArgumentParser(description="Batch hydrate neighborhood seeds.")
parser.add_argument('--input', required=True, help='Input file (plain text, one city per line, optionally country:city)')
parser.add_argument('--output', default=str(ROOT / 'city_guides' / 'data' / 'seeded_neighborhoods'), help='Output directory')
parser.add_argument('--lang', default='en', help='Language for Overpass queries')
args = parser.parse_args()

async def hydrate():
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    cities = []
    with open(args.input, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if ':' in line:
                country, city = line.split(':', 1)
                cities.append((country.strip(), city.strip()))
            else:
                cities.append(('unknown', line.strip()))

    async with get_session() as session:
        for country, city in cities:
            print(f"Hydrating: {country}:{city}")
            neighborhoods = await async_get_neighborhoods(city=city, lang=args.lang, session=session)
            country_dir = out_dir / country.lower()
            country_dir.mkdir(parents=True, exist_ok=True)
            out_file = country_dir / f"{city.lower().replace(' ', '_')}.json"
            payload = {
                "city": city,
                "country": country,
                "source": "overpass",
                "last_updated": int(time.time()),
                "neighborhoods": neighborhoods,
            }
            with out_file.open('w', encoding='utf-8') as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            print(f"Wrote {out_file} with {len(neighborhoods)} neighborhoods")

if __name__ == '__main__':
    asyncio.run(hydrate())
