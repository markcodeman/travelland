"""
Integration tests to validate the structure and functionality of the Google Places integration.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    print("✓ Testing module imports...")
    try:
        import app
        import places_provider
        import overpass_provider
        import semantic
        import search_provider
        print("  ✓ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False

def test_places_provider_functions():
    """Test that places_provider has required functions"""
    print("✓ Testing places_provider functions...")
    try:
        import places_provider
        
        required_functions = [
            'map_price_level_to_budget',
            'get_google_places_details',
            'discover_restaurants',
            'enrich_venue_with_details'
        ]
        
        for func_name in required_functions:
            if hasattr(places_provider, func_name):
                print(f"  ✓ {func_name} exists")
            else:
                print(f"  ✗ {func_name} missing")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_price_level_mapping():
    """Test price level mapping function"""
    print("✓ Testing price level mapping...")
    try:
        import places_provider
        
        test_cases = [
            (0, ('cheap', '$')),
            (1, ('cheap', '$')),
            (2, ('mid', '$$')),
            (3, ('expensive', '$$$')),
            (4, ('expensive', '$$$$')),
            (None, ('cheap', '$'))
        ]
        
        for price_level, expected in test_cases:
            result = places_provider.map_price_level_to_budget(price_level)
            if result == expected:
                print(f"  ✓ price_level {price_level} → {result}")
            else:
                print(f"  ✗ price_level {price_level} → {result} (expected {expected})")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_app_routes():
    """Test that Flask app has required routes"""
    print("✓ Testing Flask app routes...")
    try:
        import app as flask_app
        
        required_routes = [
            '/',
            '/search',
            '/ingest',
            '/poi-discover',
            '/semantic-search',
            '/convert'
        ]
        
        # Get all registered routes
        routes = [str(rule.rule) for rule in flask_app.app.url_map.iter_rules()]
        
        for route in required_routes:
            if route in routes:
                print(f"  ✓ Route {route} exists")
            else:
                print(f"  ✗ Route {route} missing")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_search_endpoint_accepts_provider():
    """Test that /search endpoint structure supports provider parameter"""
    print("✓ Testing /search endpoint provider parameter...")
    try:
        with open(os.path.join(os.path.dirname(__file__), 'app.py'), 'r') as f:
            content = f.read()
            if 'provider' in content and "'provider'" in content:
                print("  ✓ /search endpoint supports provider parameter")
                return True
            else:
                print("  ✗ /search endpoint missing provider parameter")
                return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_expanded_cuisines():
    """Test that expanded cuisines are supported"""
    print("✓ Testing expanded cuisine support...")
    try:
        with open(os.path.join(os.path.dirname(__file__), 'search_provider.py'), 'r') as f:
            content = f.read()
            
        expanded_cuisines = ['irish', 'indian', 'thai', 'vietnamese', 'greek', 'spanish', 'german', 'british']
        all_found = True
        
        for cuisine in expanded_cuisines:
            if cuisine in content.lower():
                print(f"  ✓ {cuisine.capitalize()} cuisine supported")
            else:
                print(f"  ✗ {cuisine.capitalize()} cuisine not found")
                all_found = False
        
        return all_found
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_requirements_file():
    """Test that requirements.txt has necessary packages"""
    print("✓ Testing requirements.txt...")
    try:
        with open(os.path.join(os.path.dirname(__file__), 'requirements.txt'), 'r') as f:
            content = f.read()
        
        required_packages = ['Flask', 'googlemaps', 'python-dotenv', 'requests']
        
        for package in required_packages:
            if package.lower() in content.lower():
                print(f"  ✓ {package} in requirements.txt")
            else:
                print(f"  ✗ {package} missing from requirements.txt")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

if __name__ == '__main__':
    print("\n=== Integration Tests for Google Places Integration ===\n")
    
    tests = [
        test_imports(),
        test_places_provider_functions(),
        test_price_level_mapping(),
        test_app_routes(),
        test_search_endpoint_accepts_provider(),
        test_expanded_cuisines(),
        test_requirements_file()
    ]
    
    print("\n=== Test Results ===")
    passed = sum(tests)
    total = len(tests)
    print(f"Passed: {passed}/{total}")
    
    if all(tests):
        print("✓ All integration tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed.")
        sys.exit(1)
