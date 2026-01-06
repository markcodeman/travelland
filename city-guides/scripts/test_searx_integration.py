import multi_provider
import json
import os

city = "Chesapeake VA"
cuisine = "burger"

print(f"--- Running orchestrated search for {city} ({cuisine}) ---")
print("Providers active: OSM, OpenTripMap, SearX")

results = multi_provider.discover_restaurants(city, cuisine=cuisine, local_only=True, limit=20)

print(f"\nTotal results found: {len(results)}")
for i, r in enumerate(results[:10]):
    print(f"{i+1}. {r['name']} - {r['price_range']} (Provider: {r['provider']})")
    print(f"   URL: {r.get('website') or r.get('osm_url')}")
