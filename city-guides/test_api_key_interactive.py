#!/usr/bin/env python3
"""
Interactive API Key Tester for Google Places API
This script helps you test your actual Google Places API key with various scenarios.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_subheader(text):
    """Print a formatted subheader"""
    print(f"\n{text}")
    print("-" * 70)


def test_api_key_set():
    """Check if API key is set"""
    print_subheader("Step 1: Checking API Key Configuration")
    
    api_key = os.getenv('GOOGLE_PLACES_API_KEY')
    if not api_key:
        print("❌ GOOGLE_PLACES_API_KEY is not set")
        print("\nHow to fix:")
        print("1. Create a .env file in this directory")
        print("2. Add: GOOGLE_PLACES_API_KEY=your_actual_key_here")
        print("3. Or set it in your environment: export GOOGLE_PLACES_API_KEY=your_key")
        return False
    
    print(f"✓ GOOGLE_PLACES_API_KEY is set")
    print(f"  Key starts with: {api_key[:20]}..." if len(api_key) > 20 else f"  Key: {api_key}")
    return True


def test_geocoding(city="New York"):
    """Test geocoding API"""
    print_subheader(f"Step 2: Testing Geocoding API with '{city}'")
    
    try:
        import requests
        api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {'address': city, 'key': api_key}
        
        print(f"Sending request to Google Geocoding API...")
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        status = data.get('status')
        print(f"Response Status: {status}")
        
        if status == 'OK':
            location = data['results'][0]['geometry']['location']
            formatted = data['results'][0]['formatted_address']
            print(f"✓ Geocoding successful!")
            print(f"  Address: {formatted}")
            print(f"  Coordinates: {location['lat']}, {location['lng']}")
            return True, location
        else:
            print(f"❌ Geocoding failed")
            if 'error_message' in data:
                print(f"  Error: {data['error_message']}")
            print(f"\nCommon fixes:")
            print(f"  - REQUEST_DENIED: Enable 'Geocoding API' in Google Cloud Console")
            print(f"  - INVALID_REQUEST: Check your API key is correct")
            return False, None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False, None


def test_places_search(location, keyword="restaurant"):
    """Test Places API nearby search"""
    print_subheader(f"Step 3: Testing Places API (searching for '{keyword}')")
    
    try:
        import requests
        api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{location['lat']},{location['lng']}",
            'radius': 5000,
            'type': 'restaurant',
            'keyword': keyword,
            'key': api_key
        }
        
        print(f"Sending request to Google Places API...")
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        status = data.get('status')
        print(f"Response Status: {status}")
        
        if status == 'OK':
            results = data.get('results', [])
            print(f"✓ Places search successful!")
            print(f"  Found {len(results)} places")
            return True, results
        elif status == 'ZERO_RESULTS':
            print(f"⚠️  Search returned zero results (API is working but no places found)")
            return True, []
        else:
            print(f"❌ Places search failed")
            if 'error_message' in data:
                print(f"  Error: {data['error_message']}")
            print(f"\nCommon fixes:")
            print(f"  - REQUEST_DENIED: Enable 'Places API' in Google Cloud Console")
            print(f"  - OVER_QUERY_LIMIT: You've exceeded your quota, wait or upgrade")
            return False, None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False, None


def test_integration():
    """Test the complete integration"""
    print_subheader("Step 4: Testing Full Integration with places_provider.py")
    
    try:
        from places_provider import discover_restaurants_places
        
        print("Testing discover_restaurants_places('Paris', cuisine='italian', limit=5)...")
        results = discover_restaurants_places('Paris', cuisine='italian', limit=5)
        
        print(f"✓ Integration test successful!")
        print(f"  Retrieved {len(results)} restaurants")
        
        if results:
            print("\n  Sample restaurants:")
            for i, r in enumerate(results[:3], 1):
                rating_str = f"⭐ {r['rating']}/5" if r.get('rating') else "No rating"
                print(f"    {i}. {r['name']}")
                print(f"       {rating_str} | {r['budget']} ({r['price_range']})")
                print(f"       {r.get('address', 'No address')}")
        
        return True
        
    except ValueError as e:
        print(f"❌ Integration test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def display_sample_results(results):
    """Display sample results from Places API"""
    if not results or len(results) == 0:
        return
    
    print_subheader("Sample Results (First 5)")
    
    for i, place in enumerate(results[:5], 1):
        name = place.get('name', 'Unknown')
        rating = place.get('rating', 'N/A')
        user_ratings = place.get('user_ratings_total', 0)
        price_level = place.get('price_level', 'N/A')
        vicinity = place.get('vicinity', 'N/A')
        
        print(f"\n{i}. {name}")
        print(f"   Rating: ⭐ {rating}/5 ({user_ratings} reviews)")
        print(f"   Price Level: {price_level}")
        print(f"   Address: {vicinity}")


def interactive_test():
    """Run an interactive test session"""
    print_header("Interactive Google Places API Key Tester")
    print("\nThis script will test your Google Places API key through various scenarios.")
    print("Make sure you have:")
    print("  1. Created a Google Cloud Project")
    print("  2. Enabled 'Places API' and 'Geocoding API'")
    print("  3. Created an API Key")
    print("  4. Set GOOGLE_PLACES_API_KEY in your .env file")
    
    input("\nPress Enter to start testing...")
    
    # Test 1: Check API key
    if not test_api_key_set():
        return False
    
    # Test 2: Geocoding
    success, location = test_geocoding("New York")
    if not success or not location:
        print("\n⚠️  Geocoding failed. Cannot proceed with Places API test.")
        print("Please fix the issues above and try again.")
        return False
    
    # Test 3: Places API
    success, results = test_places_search(location, "restaurant")
    if not success:
        print("\n⚠️  Places API test failed.")
        print("Please fix the issues above and try again.")
        return False
    
    # Display sample results
    if results:
        display_sample_results(results)
    
    # Test 4: Integration test
    test_integration()
    
    # Final summary
    print_header("Test Summary")
    print("\n✓ All tests completed successfully!")
    print("\nYour API key is working correctly. You can now:")
    print("  1. Start the application: python app.py")
    print("  2. Check 'Use Google Places' in the UI")
    print("  3. Search for restaurants in any city")
    print("\nFor more testing scenarios, see TESTING_API_KEYS.md")
    
    return True


def quick_test_mode(city, cuisine=None):
    """Quick test mode for command line usage"""
    from places_provider import discover_restaurants_places
    
    print(f"Quick testing: {city}" + (f" ({cuisine})" if cuisine else ""))
    results = discover_restaurants_places(city, cuisine=cuisine, limit=10)
    
    print(f"\nFound {len(results)} restaurants:")
    for i, r in enumerate(results, 1):
        rating_str = f"⭐ {r['rating']}/5 ({r.get('user_ratings_total', 0)} reviews)" if r.get('rating') else "No rating"
        print(f"{i}. {r['name']} - {rating_str}")
        print(f"   {r['budget']} ({r['price_range']}) | {r.get('address', 'No address')}")


if __name__ == "__main__":
    # Check if command line arguments provided for quick test
    if len(sys.argv) > 1:
        city = sys.argv[1]
        cuisine = sys.argv[2] if len(sys.argv) > 2 else None
        try:
            quick_test_mode(city, cuisine)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        # Run interactive test
        try:
            success = interactive_test()
            sys.exit(0 if success else 1)
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user.")
            sys.exit(1)
        except Exception as e:
            print(f"\n\nUnexpected error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
