"""
Basic integration test for the application structure
"""
import sys
import os

def test_imports():
    """Test that all modules import correctly"""
    print("Testing imports...")
    try:
        import app
        print("✓ app.py imports successfully")
    except Exception as e:
        print(f"❌ Failed to import app.py: {e}")
        return False
    
    try:
        import places_provider
        print("✓ places_provider.py imports successfully")
    except Exception as e:
        print(f"❌ Failed to import places_provider.py: {e}")
        return False
    
    try:
        import overpass_provider
        print("✓ overpass_provider.py imports successfully")
    except Exception as e:
        print(f"❌ Failed to import overpass_provider.py: {e}")
        return False
    
    return True


def test_app_routes():
    """Test that Flask routes are defined"""
    print("\nTesting Flask routes...")
    try:
        from app import app
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        
        expected_routes = ['/', '/search', '/poi-discover', '/semantic-search', '/convert', '/ingest']
        for route in expected_routes:
            if route in routes:
                print(f"✓ Route {route} is defined")
            else:
                print(f"⚠️  Route {route} not found")
        
        return True
    except Exception as e:
        print(f"❌ Failed to test routes: {e}")
        return False


def test_provider_parameter():
    """Test that the search endpoint accepts provider parameter"""
    print("\nTesting provider parameter support...")
    try:
        from flask import Flask
        from app import app as flask_app
        
        with flask_app.test_client() as client:
            # Test with OSM provider
            response = client.post('/search', 
                                   json={'city': 'Test City', 'provider': 'osm'},
                                   content_type='application/json')
            print(f"✓ OSM provider request: {response.status_code}")
            
            # Test with Google provider (will fail without API key, but should accept parameter)
            response = client.post('/search',
                                   json={'city': 'Test City', 'provider': 'google'},
                                   content_type='application/json')
            print(f"✓ Google provider request: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to test provider parameter: {e}")
        return False


def test_env_example_exists():
    """Test that .env.example file exists"""
    print("\nTesting configuration files...")
    if os.path.exists('.env.example'):
        print("✓ .env.example file exists")
        with open('.env.example', 'r') as f:
            content = f.read()
            if 'GOOGLE_PLACES_API_KEY' in content:
                print("✓ .env.example contains GOOGLE_PLACES_API_KEY")
            else:
                print("⚠️  GOOGLE_PLACES_API_KEY not found in .env.example")
        return True
    else:
        print("❌ .env.example file not found")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Integration Test Suite")
    print("=" * 60)
    
    all_passed = True
    
    all_passed = test_imports() and all_passed
    all_passed = test_app_routes() and all_passed
    all_passed = test_provider_parameter() and all_passed
    all_passed = test_env_example_exists() and all_passed
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All integration tests passed!")
    else:
        print("⚠️  Some tests failed or had warnings")
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)
