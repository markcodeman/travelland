#!/usr/bin/env python3
"""
Test 100 cities for neighborhood API errors
"""
import asyncio
import aiohttp
import json

CITIES = [
    # Major global cities
    "New York", "London", "Paris", "Tokyo", "Dubai", "Singapore", "Barcelona", 
    "Rome", "Amsterdam", "Berlin", "Madrid", "Vienna", "Prague", "Milan",
    "Munich", "Brussels", "Zurich", "Stockholm", "Copenhagen", "Oslo",
    "Helsinki", "Dublin", "Edinburgh", "Lisbon", "Warsaw", "Budapest",
    "Bucharest", "Sofia", "Zagreb", "Belgrade", "Ljubljana", "Bratislava",
    "Tallinn", "Riga", "Vilnius", "Luxembourg", "Monaco", "Valletta",
    # US cities
    "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio",
    "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville", "Fort Worth",
    "Columbus", "Charlotte", "San Francisco", "Indianapolis", "Seattle", "Denver",
    "Washington", "Boston", "El Paso", "Nashville", "Detroit", "Oklahoma City",
    "Portland", "Las Vegas", "Louisville", "Baltimore", "Milwaukee", "Albuquerque",
    # Asian cities
    "Hong Kong", "Bangkok", "Seoul", "Kuala Lumpur", "Jakarta", "Manila",
    "Ho Chi Minh City", "Shanghai", "Beijing", "Mumbai", "Delhi", "Bangalore",
    "Chennai", "Hyderabad", "Pune", "Ahmedabad", "Kolkata", "Surat",
    # Other global cities
    "Sydney", "Melbourne", "Toronto", "Vancouver", "Montreal", "Calgary",
    "Ottawa", "Edmonton", "Quebec City", "Winnipeg", "Hamilton", "Kitchener",
    "London Ontario", "Victoria BC", "Halifax", "Oshawa", "Windsor",
    # European cities continued
    "Bordeaux", "Lyon", "Marseille", "Toulouse", "Nice", "Nantes",
    "Strasbourg", "Montpellier", "Lille", "Rennes", "Reims", "Toulon",
    "Le Havre", "Grenoble", "Dijon", "Angers", "Nîmes", "Villeurbanne"
]

async def test_city(session, city):
    """Test a single city"""
    try:
        async with session.get(
            'http://localhost:5010/api/smart-neighborhoods',
            params={'city': city, 'category': 'Food'},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            data = await response.json()
            neighborhoods = data.get('neighborhoods', [])
            return {
                'city': city,
                'status': response.status,
                'neighborhood_count': len(neighborhoods),
                'success': len(neighborhoods) > 0
            }
    except Exception as e:
        return {
            'city': city,
            'status': 0,
            'neighborhood_count': 0,
            'success': False,
            'error': str(e)
        }

async def main():
    print("Testing 100 cities for neighborhood API...\n")
    
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[test_city(session, c) for c in CITIES])
    
    # Analyze results
    success_count = sum(1 for r in results if r['success'])
    fail_count = len(CITIES) - success_count
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: {success_count}/{len(CITIES)} cities have neighborhoods")
    print(f"{'='*60}\n")
    
    if fail_count > 0:
        print("FAILED CITIES (no neighborhoods returned):")
        for r in results:
            if not r['success']:
                print(f"  ❌ {r['city']}: {r.get('error', 'No neighborhoods')}")
        print()
    
    # Save full results
    with open('/tmp/city_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("Full results saved to /tmp/city_test_results.json")

if __name__ == '__main__':
    asyncio.run(main())
