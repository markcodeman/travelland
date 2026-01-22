"""Seed local cache of POIs for cities using Overpass (OpenStreetMap).

This script writes JSON files to `data/places_cache/<city_slug>.json` with
metadata and a list of normalized venues. It is safe to run offline and
intentionally avoids calling paid APIs.

Usage:
  python scripts/seed_osm.py --city "Guadalajara" --limit 200

You can seed multiple cities by repeating or scripting over a list.
"""
import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from slugify import slugify

# Import local provider
from city_guides.providers import overpass_provider

CACHE_DIR = Path(__file__).resolve().parents[1] / 'data' / 'places_cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def normalize_poi(poi: Dict, city: str) -> Dict:
    """Normalize Overpass POI dict into our cached venue format."""
    amenity = poi.get('amenity', '')
    tags = poi.get('tags', '')
    tags_dict = dict(tag.split('=', 1) for tag in tags.split(', ') if '=' in tag)
    cuisine = tags_dict.get('cuisine', '').replace(';', ', ')
    brand = tags_dict.get('brand', '')
    if cuisine:
        desc = f"{cuisine.title()} restaurant"
        if brand:
            desc = f"{brand} - {desc}"
    else:
        desc = f"Restaurant ({amenity})"
        if brand:
            desc = f"{brand} - {desc}"
    address = poi.get('address', '').strip() or None
    v_budget = 'mid'
    price_range = '$$'
    if amenity in ['fast_food', 'cafe', 'food_court']:
        v_budget = 'cheap'
        price_range = '$'
    elif amenity in ['bar', 'pub']:
        v_budget = 'mid'
        price_range = '$$'

    return {
        'id': poi.get('osm_id', ''),
        'city': city,
        'name': poi.get('name', 'Unknown'),
        'budget': v_budget,
        'price_range': price_range,
        'description': desc,
        'tags': tags,
        'address': address,
        'latitude': poi.get('lat', 0),
        'longitude': poi.get('lon', 0),
        'website': poi.get('website', ''),
        'osm_url': poi.get('osm_url', ''),
        'amenity': amenity,
        'provider': 'osm'
    }


def seed_city(city: str, limit: int = 200) -> Path:
    """Fetch POIs via Overpass and write cache file. Returns path to file."""
    print(f"Seeding city: {city} (limit={limit})")
    pois = overpass_provider.discover_restaurants(city, limit=limit)
    print(f"Fetched {len(pois)} POIs from Overpass")
    normalized = [normalize_poi(p, city) for p in pois]

    metadata = {
        'city': city,
        'seeded_at': datetime.utcnow().isoformat() + 'Z',
        'source': 'overpass_osm',
        'count': len(normalized)
    }

    slug = slugify(city)
    out_path = CACHE_DIR / f"{slug}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'meta': metadata, 'venues': normalized}, f, ensure_ascii=False, indent=2)
    print(f"Wrote cache to {out_path} ({out_path.stat().st_size} bytes)")
    return out_path


def main():
    parser = argparse.ArgumentParser(description='Seed OSM places cache')
    parser.add_argument('--city', '-c', required=True, help='City name to seed (e.g., "Guadalajara")')
    parser.add_argument('--limit', '-l', type=int, default=200, help='Max POIs to fetch')
    args = parser.parse_args()
    seed_city(args.city, limit=args.limit)


if __name__ == '__main__':
    main()
