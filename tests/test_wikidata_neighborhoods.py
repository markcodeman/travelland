import asyncio
import sys

sys.path.insert(0, '/home/markcodeman/CascadeProjects/travelland/city_guides')

from city_guides.providers.geocoding import geocode_city
from city_guides.src.dynamic_neighborhoods import fetch_neighborhoods_wikidata

async def test_marseille_wikidata():
    print("Testing Wikidata neighborhoods for Marseille...")
    
    # Geocode Marseille
    geo = await geocode_city("Marseille")
    if not geo:
        print("Error: Could not geocode Marseille")
        return
    
    lat = geo.get('lat')
    lon = geo.get('lon')
    print(f"Marseille coordinates: {lat}, {lon}")
    
    # Get neighborhoods from Wikidata
    neighborhoods = await fetch_neighborhoods_wikidata("Marseille", lat, lon)
    print(f"\nFound {len(neighborhoods)} neighborhoods:")
    for hood in neighborhoods:
        print(f"- {hood['name']} ({hood['type']}): {hood['description']}")

if __name__ == "__main__":
    asyncio.run(test_marseille_wikidata())