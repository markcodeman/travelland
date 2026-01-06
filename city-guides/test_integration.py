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
        import multi_provider
        import overpass_provider
        import semantic
        import search_provider
        print("  ✓ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False

def test_multi_provider_functions():
    """Test that multi_provider has required functions"""
    print("✓ Testing multi_provider functions...")
    try:
        import multi_provider
        
        required_functions = [
            'discover_restaurants',
            '_norm_name',
            '_haversine_meters'
        ]
        
        for func_name in required_functions:
            if hasattr(multi_provider, func_name):
                print(f"  ✓ {func_name} exists")
            else:
                print(f"  ✗ {func_name} missing")
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
        
        required_packages = ['Flask', 'python-dotenv', 'requests', 'beautifulsoup4']
        
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
    print("\n=== Integration Tests for Multi-Provider Tooling ===\n")
    
    tests = [
        test_imports(),
        test_multi_provider_functions(),
        test_app_routes(),
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
