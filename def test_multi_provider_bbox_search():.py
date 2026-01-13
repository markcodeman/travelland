def test_multi_provider_bbox_search():
    """Test multi_provider.discover_pois with a London neighborhood bbox"""
    print("✓ Testing multi_provider.discover_pois with bbox...")
    try:
        import multi_provider
        bbox = (-0.1200, 51.5300, -0.0900, 51.5500)  # Islington area
        results = multi_provider.discover_pois(
            city="London, United Kingdom",
            poi_type="restaurant",
            limit=5,
            bbox=bbox
        )
        print(f"  ✓ Got {len(results)} results")
        for r in results:
            print(f"    - {r.get('name')} ({r.get('lat')}, {r.get('lon')})")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False