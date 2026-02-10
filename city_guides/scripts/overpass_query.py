#!/usr/bin/env python3
"""Utility script to query Overpass/OSM neighborhood names using the provider.

Usage:
  python city_guides/scripts/overpass_query.py --city "Osaka" --nocache
  python city_guides/scripts/overpass_query.py --city "Osaka" --out out.json

This script calls the existing `overpass_provider.async_get_neighborhoods` to
reuse the project's logic and prints JSON to stdout (or writes to a file).
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project package imports work (add repo root)
ROOT = Path(__file__).resolve().parents[2]
import sys as _sys
_sys.path.insert(0, str(ROOT))

from city_guides.providers import overpass_provider


async def _run(city: str | None, lat: float | None, lon: float | None, out: str | None):
    try:
        results = await overpass_provider.async_get_neighborhoods(city=city, lat=lat, lon=lon, lang="en")
    except Exception as e:
        print(f"[ERROR] Overpass query failed: {e}", file=sys.stderr)
        return 2

    if out:
        p = Path(out)
        p.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(f"Wrote {len(results)} entries to {p}")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--city", type=str, help="City name to query (e.g., 'Osaka')")
    p.add_argument("--lat", type=float, help="Latitude for coordinate-based lookup")
    p.add_argument("--lon", type=float, help="Longitude for coordinate-based lookup")
    p.add_argument("--out", type=str, help="Output file to write JSON results")
    args = p.parse_args()

    if not args.city and (args.lat is None or args.lon is None):
        p.error("Either --city or both --lat and --lon must be provided")

    rc = asyncio.run(_run(args.city, args.lat, args.lon, args.out))
    raise SystemExit(rc)


if __name__ == '__main__':
    main()
