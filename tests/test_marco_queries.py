#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from city_guides.src.semantic import (
    build_mandatory_venues_prompt,
)

import json


def load_sample_venues(limit: int = 8):
    data_file = ROOT / 'data' / 'venues.json'
    if not data_file.exists():
        # fallback to small hardcoded list
        return [
            {"name": "Blue Bottle Coffee", "type": "cafe", "features": ["dark roasts", "outdoor seating"]},
            {"name": "Philz Coffee", "type": "cafe", "features": ["custom blends", "quick service"]},
            {"name": "Sunset Diner", "type": "restaurant", "features": ["cheap", "family-friendly"]},
            {"name": "Accessible Park Museum", "type": "attraction", "features": ["wheelchair accessible"]},
        ]

    try:
        with open(data_file, 'r', encoding='utf-8') as fh:
            all_venues = json.load(fh)
    except Exception:
        return []

    out = []
    for v in all_venues:
        if len(out) >= limit:
            break
        # Normalize fields; be defensive about keys
        name = v.get('name') or v.get('title') or v.get('venue_name') or "Unknown"
        vtype = v.get('type') or v.get('category') or 'place'
        features = []
        # try common fields for features
        for key in ('tags', 'features', 'attributes'):
            if key in v and isinstance(v[key], list):
                features.extend([str(x) for x in v[key]])
        out.append({"name": name, "type": vtype, "features": features})
    return out


SAMPLE_VENUES = load_sample_venues(limit=8)

WEATHER = {"temperature_c": 22, "weathercode": 0}
NEIGHBORHOODS = [{"name": "Downtown"}, {"name": "Old Town"}]

QUERIES = [
    "best dark roast coffee nearby",
    "family-friendly restaurants with outdoor seating",
    "cheap lunch options under $10",
    "wheelchair accessible attractions close to me",
    "quiet cozy cafes for remote work",
]


def main():
    for q in QUERIES:
        print("\n--- QUERY:\n", q)
        # Use mandatory venues prompt to force venue-based recommendations
        prompt = build_mandatory_venues_prompt(q, city="San Francisco", venues=SAMPLE_VENUES, weather=WEATHER, neighborhoods=NEIGHBORHOODS)
        # Print first 400 chars of prompt for brevity
        print(prompt[:400])
        print("...\n(venues count):", len(SAMPLE_VENUES))


if __name__ == '__main__':
    main()
