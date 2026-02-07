import asyncio
import sys

sys.path.insert(0, '/home/markcodeman/CascadeProjects/travelland-neighborhood')

from city_guides.src.app import geocode_city
from city_guides.src.dynamic_neighborhoods import get_neighborhoods_for_city

async def test_marseille_neighborhoods():
    city = "London"  # Change this to test different cities
    print(f"Testing {city} neighborhoods...")
    
    # Geocode the city
    geo = await geocode_city(city)
    if not geo:
        print(f"Error: Could not geocode {city}")
        return
    
    lat = geo.get('lat')
    lon = geo.get('lon')
    print(f"{city} coordinates: {lat}, {lon}")
    
    # Get neighborhoods
    neighborhoods = await get_neighborhoods_for_city(city, lat, lon)
    print(f"\nFound {len(neighborhoods)} neighborhoods:")
    for hood in neighborhoods:
        print(f"\n- {hood['name']} ({hood['type']}):")
        print(f"  {hood['description']}")

if __name__ == "__main__":
    asyncio.run(test_marseille_neighborhoods())