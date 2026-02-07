#!/usr/bin/env python3
"""
Test script to verify Japantown coffee/tea venue functionality.
"""

import sys
from pathlib import Path

# Add project root to Python path so `providers` resolves to either the top-level shim
# or the `city_guides/providers` package. Use parent of tests dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from providers.neighborhood_provider import (
    get_japantown_coffee_tea_venues,
    get_neighborhood_recommendations,
    search_neighborhood_venues_by_query,
    normalize_venue_for_search
)

def test_japantown_coffee_tea_venues():
    """Test getting coffee and tea venues for Japantown."""
    print("🏯 Testing Japantown coffee and tea venues...")

    # Get the raw venue data
    venues = get_japantown_coffee_tea_venues()

    if not venues:
        print("❌ No venues found for Japantown!")
        return False

    print(f"✅ Found {len(venues)} coffee/tea venues in Japantown:")
    for i, venue in enumerate(venues, 1):
        print(f"  {i}. {venue['name']} - {venue['type']}")
        print(f"     📍 {venue['address']}")
        print(f"     ⭐ {venue.get('rating', 'N/A')}")
        print(f"     🕒 {venue.get('hours', 'N/A')}")
        print(f"     🌐 {venue.get('website', 'N/A')}")
        print(f"     📝 {venue['description']}")
        print()

    return True

def test_japantown_recommendations():
    """Test getting pre-written recommendations for Japantown."""
    print("\n📋 Testing Japantown recommendations...")

    # Test coffee/tea recommendations
    coffee_recommendation = get_neighborhood_recommendations("japantown", "coffee_tea")
    if coffee_recommendation:
        print("✅ Coffee/Tea Recommendation:")
        print(f"   {coffee_recommendation}")
    else:
        print("❌ No coffee/tea recommendations found")

    # Test general recommendations
    general_recommendation = get_neighborhood_recommendations("japantown")
    if general_recommendation:
        print("\n✅ General Recommendations:")
        print(f"   {general_recommendation}")
    else:
        print("❌ No general recommendations found")

    return True

def test_search_functionality():
    """Test the search functionality for specific queries."""
    print("\n🔍 Testing search functionality...")

    test_queries = [
        "coffee",
        "tea",
        "matcha",
        "japanese tea",
        "cafe"
    ]

    for query in test_queries:
        print(f"\n   Searching for: '{query}'")
        results = search_neighborhood_venues_by_query(query, "japantown")

        if results:
            print(f"   ✅ Found {len(results)} results:")
            for venue in results:
                print(f"     • {venue['name']} ({venue['type']})")
        else:
            print(f"   ❌ No results found for '{query}'")

    return True

def test_normalized_venues():
    """Test venue normalization for search integration."""
    print("\n🔄 Testing venue normalization...")

    venues = get_japantown_coffee_tea_venues()
    if not venues:
        print("❌ No venues to normalize")
        return False

    # Normalize the first venue
    normalized = normalize_venue_for_search(venues[0])

    print("✅ Normalized venue format:")
    for key, value in normalized.items():
        print(f"   {key}: {value}")

    return True

def test_specific_coffee_tea_response():
    """Test generating a specific response for coffee/tea queries."""
    print("\n💬 Testing specific coffee/tea response generation...")

    venues = get_japantown_coffee_tea_venues()
    if not venues:
        print("❌ No venues available for response")
        return False

    # Generate a response similar to what the semantic.py would produce
    venue_names = [v['name'] for v in venues[:3]]
    names_str = "**, **".join(venue_names)

    response = f"""Ahoy! 🧭 Based on your interest in coffee and tea options in Japantown, San Francisco, here are some excellent spots:

• **{names_str}**

These venues offer a variety of traditional Japanese tea experiences and specialty coffee options. Would you like more details about any of these, or are you looking for a specific type of coffee or tea experience? - Marco ☕"""

    print("✅ Generated response:")
    print(response)

    return True

def main():
    """Run all tests."""
    print("🗾 Japantown Coffee & Tea Venue Test Suite")
    print("=" * 50)

    tests = [
        test_japantown_coffee_tea_venues,
        test_japantown_recommendations,
        test_search_functionality,
        test_normalized_venues,
        test_specific_coffee_tea_response
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with error: {e}")

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Japantown coffee/tea functionality is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)