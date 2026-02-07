#!/usr/bin/env python3
"""
Test category search across 20 lesser-known cities to verify fixes work globally.
"""

import requests
import json
from typing import Dict, List

BASE_URL = "http://localhost:5010"

# 20 lesser-known cities (not major tourist hubs like Paris, London, etc.)
CITIES = [
    "Tbilisi, Georgia",
    "Sofia, Bulgaria",
    "Zagreb, Croatia",
    "Skopje, North Macedonia",
    "Podgorica, Montenegro",
    "Sarajevo, Bosnia",
    "Ljubljana, Slovenia",
    "Kaunas, Lithuania",
    "Tartu, Estonia",
    "Riga, Latvia",
    "Cluj-Napoca, Romania",
    "Timisoara, Romania",
    "Bratislava, Slovakia",
    "Wroclaw, Poland",
    "Gdansk, Poland",
    "Krakow, Poland",
    "Plovdiv, Bulgaria",
    "Belgrade, Serbia",
    "Novi Sad, Serbia",
    "Valencia, Spain",
]

CATEGORIES = ["restaurants", "cafes", "hotels"]

def test_city_category(city: str, category: str) -> Dict:
    """Test the /search endpoint with a city and category."""
    try:
        payload = {
            "query": city,
            "category": category,
            "limit": 3
        }
        resp = requests.post(f"{BASE_URL}/search", json=payload, timeout=30)
        data = resp.json()
        
        venues = data.get("venues", [])
        return {
            "city": city,
            "category": category,
            "status_code": resp.status_code,
            "venues_found": len(venues),
            "has_quick_guide": bool(data.get("quick_guide")),
            "sample_venues": [f"{v.get('name', 'N/A')}: {v.get('venue_type', 'N/A')}" for v in venues[:2]]
        }
    except Exception as e:
        return {
            "city": city,
            "category": category,
            "status_code": 0,
            "venues_found": 0,
            "error": str(e)[:50]
        }

def main():
    print("=" * 100)
    print("20 LESSER-KNOWN CITIES CATEGORY TEST")
    print("=" * 100)
    print(f"\nBase URL: {BASE_URL}")
    print(f"Cities: {len(CITIES)}")
    print(f"Categories per city: {', '.join(CATEGORIES)}")
    print("\n" + "=" * 100)
    
    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/", timeout=5)
    except:
        print(f"\n⚠️  WARNING: Server not running at {BASE_URL}")
        print("Please start the server with: python city_guides/src/app.py")
        return
    
    results = []
    total_tests = len(CITIES) * len(CATEGORIES)
    completed = 0
    
    print(f"\n📊 TESTING {total_tests} COMBINATIONS...\n")
    print(f"{'City':<30} {'Category':<15} {'Status':<10} {'Venues':<8} {'Quick Guide':<12} {'Sample Venues'}")
    print("-" * 130)
    
    for city in CITIES:
        for category in CATEGORIES:
            result = test_city_category(city, category)
            results.append(result)
            completed += 1
            
            status = "✅" if result.get("status_code") == 200 else "❌"
            venues = result.get("venues_found", 0)
            guide = "Yes" if result.get("has_quick_guide") else "No"
            samples = " | ".join(result.get("sample_venues", []))[:60]
            
            print(f"{city:<30} {category:<15} {status:<10} {venues:<8} {guide:<12} {samples}")
    
    # Summary
    print("\n" + "=" * 100)
    print("📈 SUMMARY")
    print("=" * 100)
    
    passed = sum(1 for r in results if r.get("status_code") == 200)
    failed = total_tests - passed
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    
    # Cities with venues
    cities_with_venues = sum(1 for r in results if r.get("venues_found", 0) > 0)
    print(f"\nTests with venues found: {cities_with_venues}/{total_tests}")
    
    # Category breakdown
    print("\n📊 CATEGORY BREAKDOWN:")
    for cat in CATEGORIES:
        cat_results = [r for r in results if r["category"] == cat]
        cat_passed = sum(1 for r in cat_results if r.get("status_code") == 200)
        cat_venues = sum(r.get("venues_found", 0) for r in cat_results)
        print(f"  {cat:<15}: {cat_passed}/{len(cat_results)} passed, {cat_venues} total venues")
    
    # Failed cities
    failed_tests = [r for r in results if r.get("status_code") != 200]
    if failed_tests:
        print("\n❌ FAILED TESTS:")
        for r in failed_tests:
            error = r.get("error", "Unknown error")
            print(f"  - {r['city']} / {r['category']}: {error}")
    
    print("\n" + "=" * 100)

if __name__ == "__main__":
    main()
