import sys
import os

# Add the city-guides directory to the path
sys.path.append(os.path.join(os.getcwd(), "city-guides"))

import multi_provider


def test_count():
    city = "Chesapeake VA"
    cuisine = "sushi"
    print(f"Searching for {cuisine} in {city} (Local Only)...")
    results = multi_provider.discover_restaurants(
        city, cuisine=cuisine, limit=100, local_only=True
    )
    print(f"Total results: {len(results)}")
    for i, r in enumerate(results[:10]):
        print(f"{i+1}. {r['name']} ({r['provider']}) - {r.get('website')}")


if __name__ == "__main__":
    test_count()
