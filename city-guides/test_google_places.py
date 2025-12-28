"""
Test script for Google Places API integration
"""
import os
from dotenv import load_dotenv

load_dotenv()

def test_google_places_api():
    """Test Google Places API integration"""
    from places_provider import discover_restaurants_places
    
    # Check if API key is set
    api_key = os.getenv('GOOGLE_PLACES_API_KEY')
    if not api_key:
        print("❌ GOOGLE_PLACES_API_KEY not set in environment")
        print("   Please set it in your .env file or Render.com environment variables")
        return False
    
    print("✓ GOOGLE_PLACES_API_KEY is set")
    
    # Test API call
    try:
        print("\nTesting Google Places API with query: New York, cuisine=italian")
        results = discover_restaurants_places("New York", cuisine="italian", limit=5)
        
        if not results:
            print("⚠️  No results returned (API key may be invalid or rate limited)")
            return False
        
        print(f"✓ Successfully retrieved {len(results)} restaurants")
        print("\nSample results:")
        for i, restaurant in enumerate(results[:3], 1):
            print(f"\n{i}. {restaurant['name']}")
            print(f"   Budget: {restaurant['budget']} ({restaurant['price_range']})")
            print(f"   Address: {restaurant.get('address', 'N/A')}")
            print(f"   Rating: {restaurant.get('rating', 'N/A')}/5")
            print(f"   Description: {restaurant.get('description', 'N/A')}")
        
        return True
        
    except ValueError as e:
        print(f"❌ Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Google Places API Integration Test")
    print("=" * 60)
    
    success = test_google_places_api()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ All tests passed!")
        print("\nYou can now use Google Places API in the application by:")
        print("1. Checking the 'Use Google Places' checkbox in the UI")
        print("2. Or sending 'provider: google' in the API request")
    else:
        print("❌ Tests failed - please check your API key and configuration")
    print("=" * 60)
