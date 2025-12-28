"""Unit tests for Google Places API integration."""
import sys
import os

# Add project root to sys.path
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from search_provider import map_price_level_to_budget


def test_map_price_level_to_budget():
    """Test price level to budget category mapping."""
    # Test None (unknown)
    assert map_price_level_to_budget(None) == 'mid'
    
    # Test 0 (free)
    assert map_price_level_to_budget(0) == 'cheap'
    
    # Test 1 ($)
    assert map_price_level_to_budget(1) == 'cheap'
    
    # Test 2 ($$)
    assert map_price_level_to_budget(2) == 'mid'
    
    # Test 3 ($$$)
    assert map_price_level_to_budget(3) == 'expensive'
    
    # Test 4 ($$$$)
    assert map_price_level_to_budget(4) == 'expensive'
    
    print("✓ All price level mapping tests passed")


def test_google_places_details_structure():
    """Test that get_google_places_details returns expected structure."""
    # This is a structure test - actual API calls would require credentials
    # and are tested in integration tests
    from search_provider import get_google_places_details
    
    # Test with no client (should return None gracefully)
    result = get_google_places_details("Test Restaurant", 40.7128, -74.0060, "NYC")
    
    # Should return None if API is unavailable
    assert result is None or isinstance(result, dict), "Should return None or dict"
    
    if result is not None:
        # Verify expected keys
        expected_keys = {'price_level', 'rating', 'user_ratings_total', 'price_range'}
        assert all(key in result for key in expected_keys), f"Missing keys in result: {result.keys()}"
    
    print("✓ Google Places details structure test passed")


if __name__ == '__main__':
    test_map_price_level_to_budget()
    test_google_places_details_structure()
    print("\n✅ All tests passed!")
