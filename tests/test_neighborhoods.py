import asyncio
import sys

sys.path.insert(0, '/home/markcodeman/CascadeProjects/travelland/city_guides')

from city_guides.src.app import geocode_city
from city_guides.src.dynamic_neighborhoods import get_neighborhoods_for_city

async def test_marseille_neighborhoods():
    print("Testing Marseille neighborhoods...")
    
    # Geocode Marseille
    geo = await geocode_city("Marseille")
    if not geo:
        print("Error: Could not geocode Marseille")
        return
    
    lat = geo.get('lat')
    lon = geo.get('lon')
    print(f"Marseille coordinates: {lat}, {lon}")
    
    # Get neighborhoods
    neighborhoods = await get_neighborhoods_for_city("Marseille", lat, lon)
    print(f"\nFound {len(neighborhoods)} neighborhoods:")
    for hood in neighborhoods:
        print(f"- {hood['name']} ({hood['type']}): {hood['description']}")

if __name__ == "__main__":
    asyncio.run(test_marseille_neighborhoods())