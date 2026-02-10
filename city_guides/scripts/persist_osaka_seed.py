#!/usr/bin/env python3
"""Fetch neighborhoods for Osaka via Overpass provider and persist as a seed file."""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from city_guides.providers.overpass_provider import async_get_neighborhoods
from city_guides.providers.utils import get_session


async def main():
    async with get_session() as session:
        neighborhoods = await async_get_neighborhoods(city="Osaka", lang="en", session=session)

    out_dir = ROOT / 'city_guides' / 'data' / 'seeded_neighborhoods' / 'jp'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / 'osaka.json'

    payload = {
        "city": "Osaka",
        "country": "JP",
        "source": "overpass",
        "last_updated": int(time.time()),
        "neighborhoods": neighborhoods,
    }

    with out_file.open('w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"Wrote {out_file} with {len(neighborhoods)} neighborhoods")


if __name__ == '__main__':
    asyncio.run(main())
