#!/usr/bin/env python3
"""Test neighborhood search with multiple providers."""
import asyncio
import os
import sys

# Load env vars from .env file manually
env_file = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Add to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'city_guides'))

from city_guides.overpass_provider import discover_pois, async_get_neighborhoods

async def main():
    print("=" * 60)
    print("Testing Neighborhood Discovery & POI Search")
    print("=" * 60)
    
    # Test 1: Get neighborhoods for London
    print("\n[1] Fetching neighborhoods for London...")
    neighborhoods = await async_get_neighborhoods(city="London")
    print(f"    Found {len(neighborhoods)} neighborhoods")
    
    # Find Temple neighborhood
    temple = [n for n in neighborhoods if n['name'].lower() == 'temple']
    if temple:
        print(f"    ✓ Found Temple: {temple[0]}")
        bbox = temple[0].get('bbox')
        print(f"    bbox: {bbox}")
        
        # Test 2: Search for restaurants in Temple
        if bbox:
            print("\n[2] Searching for restaurants in Temple...")
            results = await discover_pois(
                city="London",
                poi_type="restaurant",
                bbox=bbox,
                limit=15
            )
            
            print(f"    Found {len(results)} restaurants")
            
            # Show breakdown by source
            sources = {}
            for r in results:
                src = r.get('source', 'unknown')
                sources[src] = sources.get(src, 0) + 1
            
            print(f"    Sources: {sources}")
            print("\n    Top 5 restaurants:")
            for i, r in enumerate(results[:5], 1):
                print(f"      {i}. {r.get('name')} ({r.get('source')})")
        else:
            print("    ✗ No bbox for Temple neighborhood")
    else:
        print("    ✗ Temple neighborhood not found")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
