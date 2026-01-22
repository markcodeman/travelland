def test_multi_provider_bbox_search():
    """Test multi_provider.discover_pois with a London neighborhood bbox"""
    print("✓ Testing multi_provider.discover_pois with bbox...")
    try:
        from providers import multi_provider
        # Larger bbox: central London
        bbox = (-0.16, 51.48, -0.07, 51.54)  # Covers much of central London
        results = multi_provider.discover_pois(
            city="London, United Kingdom",
            poi_type="restaurant",
            limit=5,
            bbox=bbox
        )
        print(f"  ✓ Got {len(results)} results")
        for r in results:
            print(f"    - {r.get('name')} ({r.get('lat')}, {r.get('lon')})")
        assert results, "No venues returned for neighborhood bbox"
    except Exception as e:
        print(f"  ✗ Error: {e}")
        assert False, f"Exception occurred: {e}"
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
        from providers import multi_provider
        from providers import overpass_provider
        import semantic
        from providers import search_provider

        print("  ✓ All modules imported successfully")
        assert True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        assert False, f"Import error: {e}"


def test_multi_provider_functions():
    """Test that multi_provider has required functions"""
    print("✓ Testing multi_provider functions...")
    try:
        from providers import multi_provider

        required_functions = ["discover_restaurants", "_norm_name", "_haversine_meters"]

        for func_name in required_functions:
            if hasattr(multi_provider, func_name):
                print(f"  ✓ {func_name} exists")
            else:
                print(f"  ✗ {func_name} missing")
                assert False, f"{func_name} missing"

        assert True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        assert False, f"Exception: {e}"


def test_app_routes():
    """Test that Flask app has required routes"""
    print("✓ Testing Flask app routes...")
    try:
        import app as flask_app

        required_routes = [
            "/",
            "/search",
            "/ingest",
            "/poi-discover",
            "/semantic-search",
            "/convert",
        ]

        # Get all registered routes
        routes = [str(rule.rule) for rule in flask_app.app.url_map.iter_rules()]

        for route in required_routes:
            if route in routes:
                print(f"  ✓ Route {route} exists")
            else:
                print(f"  ✗ Route {route} missing")
                assert False, f"Route {route} missing"

        assert True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        assert False, f"Exception: {e}"


def test_search_endpoint_accepts_provider():
    """Test that /search endpoint structure supports provider parameter"""
    print("✓ Testing /search endpoint provider parameter...")
    try:
        with open(os.path.join(os.path.dirname(__file__), "../src/app.py"), "r") as f:
            content = f.read()
            if "provider" in content and "'provider'" in content:
                print("  ✓ /search endpoint supports provider parameter")
                assert True
            else:
                print("  ✗ /search endpoint missing provider parameter")
                assert False, "/search endpoint missing provider parameter"
    except Exception as e:
        print(f"  ✗ Error: {e}")
        assert False, f"Exception: {e}"


def test_expanded_cuisines():
    """Test that expanded cuisines are supported"""
    print("✓ Testing expanded cuisine support...")
    try:
        with open(
            os.path.join(os.path.dirname(__file__), "search_provider.py"), "r"
        ) as f:
            content = f.read()

        expanded_cuisines = [
            "irish",
            "indian",
            "thai",
            "vietnamese",
            "greek",
            "spanish",
            "german",
            "british",
        ]
        all_found = True

        for cuisine in expanded_cuisines:
            if cuisine in content.lower():
                print(f"  ✓ {cuisine.capitalize()} cuisine supported")
            else:
                print(f"  ✗ {cuisine.capitalize()} cuisine not found")
                all_found = False

        assert all_found, "Not all expanded cuisines found"
    except Exception as e:
        print(f"  ✗ Error: {e}")
        assert False, f"Exception: {e}"


def test_requirements_file():
    """Test that requirements.txt has necessary packages"""
    print("✓ Testing requirements.txt...")
    try:
        with open(
            os.path.join(os.path.dirname(__file__), "requirements.txt"), "r"
        ) as f:
            content = f.read()

        required_packages = ["Flask", "python-dotenv", "requests", "beautifulsoup4"]

        for package in required_packages:
            if package.lower() in content.lower():
                print(f"  ✓ {package} in requirements.txt")
            else:
                print(f"  ✗ {package} missing from requirements.txt")
                assert False, f"{package} missing from requirements.txt"

        assert True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        assert False, f"Exception: {e}"


if __name__ == "__main__":
    print("\n=== Integration Tests for Multi-Provider Tooling ===\n")

    tests = [
        test_imports(),
        test_multi_provider_functions(),
        test_app_routes(),
        test_expanded_cuisines(),
        test_requirements_file(),
        test_multi_provider_bbox_search(),
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
