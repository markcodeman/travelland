#!/usr/bin/env python3
"""Refresh city POI cache from live APIs.

Regenerates seed data for cities using live API calls (TomTom, Wikidata, Overpass).
Run this periodically to keep cached data fresh.

Usage:
    python scripts/refresh_city_cache.py [city_name]
    python scripts/refresh_city_cache.py --all  # Refresh all cached cities
    python scripts/refresh_city_cache.py --list  # List cached cities
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from city_guides.providers.multi_provider import async_discover_pois
from city_guides.utils.city_poi_cache import (
    list_cached_cities, 
    get_cache_stats, 
    clear_city_cache
)


async def refresh_city(city: str, limit: int = 20):
    """Refresh cache for a single city."""
    print(f"\n[REFRESH] Refreshing cache for: {city}")
    print("-" * 50)
    
    # Discover POIs with live APIs
    pois = await async_discover_pois(
        city=city,
        poi_type="tourism",
        limit=limit,
        timeout=15.0
    )
    
    if pois:
        print(f"[REFRESH] ✓ Cached {len(pois)} POIs for {city}")
        # Print sample
        for poi in pois[:3]:
            print(f"  - {poi.get('name', 'Unknown')} ({poi.get('source', 'unknown')})")
        return True
    else:
        print(f"[REFRESH] ✗ No POIs found for {city}")
        return False


async def refresh_all_cities():
    """Refresh all cached cities."""
    cities = list_cached_cities()
    
    if not cities:
        print("[REFRESH] No cached cities found.")
        return
    
    print(f"[REFRESH] Found {len(cities)} cached cities: {', '.join(cities)}")
    
    success_count = 0
    for city in cities:
        if await refresh_city(city):
            success_count += 1
        await asyncio.sleep(1)  # Rate limiting
    
    print(f"\n[REFRESH] Completed: {success_count}/{len(cities)} cities refreshed")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCurrent cache stats:")
        stats = get_cache_stats()
        print(f"  Cities: {stats['total_cities']}")
        print(f"  Total POIs: {stats['total_pois']}")
        if stats['cities']:
            print("\n  Cached cities:")
            for city_info in stats['cities'][:10]:
                print(f"    - {city_info['city']}: {city_info['count']} POIs")
        return
    
    command = sys.argv[1]
    
    if command == "--list":
        cities = list_cached_cities()
        if cities:
            print(f"Cached cities ({len(cities)}):")
            for city in cities:
                print(f"  - {city}")
        else:
            print("No cached cities found.")
    
    elif command == "--all":
        asyncio.run(refresh_all_cities())
    
    elif command == "--clear":
        if len(sys.argv) < 3:
            print("Usage: --clear <city_name>")
            return
        city = sys.argv[2]
        if clear_city_cache(city):
            print(f"Cleared cache for {city}")
        else:
            print(f"No cache found for {city}")
    
    else:
        # Treat as city name
        city = command
        asyncio.run(refresh_city(city))


if __name__ == "__main__":
    main()
