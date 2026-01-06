import sys
import os

# Add the city-guides directory to the path
sys.path.append(os.path.join(os.getcwd(), 'city-guides'))

from duckduckgo_provider import discover_restaurants

def test_ddg():
    city = "Chesapeake VA"
    cuisine = "burgers"
    print(f"Searching DDG for {cuisine} in {city}...")
    results = discover_restaurants(city, cuisine=cuisine, limit=100)
    print(f"DDG results: {len(results)}")
    for i, r in enumerate(results[:20]):
        print(f"{i+1}. {r['name']} - {r['website']}")

if __name__ == "__main__":
    test_ddg()
