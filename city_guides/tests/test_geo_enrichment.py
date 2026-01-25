import asyncio

import pytest


def test_enrich_neighborhood_with_mocked_providers(monkeypatch):
    # Mock overpass_provider functions used by geo_enrichment
    async def fake_fetch_neighborhoods_enhanced(city):
        return [{'name': 'Las Nueve Esquinas', 'display_name': 'Las Nueve Esquinas'}]

    async def fake_geoapify_geocode_city(q, session=None):
        # return bbox (west, south, east, north)
        return (-103.3, 20.6, -103.2, 20.7)

    async def fake_geoapify_discover_pois(bbox, kinds=None, limit=10):
        return [
            {'name': 'Parque Central', 'amenity': 'park', 'lat': 20.65, 'lon': -103.25, 'source': 'geoapify'},
            {'name': 'Café Buenos', 'amenity': 'cafe', 'lat': 20.651, 'lon': -103.251, 'source': 'geoapify'},
        ]

    import city_guides.providers.overpass_provider as overpass
    monkeypatch.setattr(overpass, 'fetch_neighborhoods_enhanced', fake_fetch_neighborhoods_enhanced)
    monkeypatch.setattr(overpass, 'geoapify_geocode_city', fake_geoapify_geocode_city)
    monkeypatch.setattr(overpass, 'geoapify_discover_pois', fake_geoapify_discover_pois)

    from city_guides.src.geo_enrichment import enrich_neighborhood

    res = asyncio.run(enrich_neighborhood('Tlaquepaque, Mexico', 'Las Nueve Esquinas'))
    assert res is not None
    assert 'pois' in res and len(res['pois']) >= 1
    assert 'text' in res and 'Las Nueve Esquinas' in res['text']


def test_generate_quick_guide_geo_enriched(monkeypatch):
    # Patch the enrich_neighborhood to return a deterministic enrichment
    async def fake_enrich(city, neighborhood, session=None):
        return {
            'boundary': True,
            'bbox': (-103.3, 20.6, -103.2, 20.7),
            'pois': [{'name': 'Parque A', 'type': 'park', 'lat': 20.65, 'lon': -103.25, 'source': 'geoapify'}],
            'text': f"{neighborhood} is a neighborhood in {city}. Notable nearby: Parque A (park).",
        }

    monkeypatch.setattr('city_guides.src.geo_enrichment.enrich_neighborhood', fake_enrich)

    from city_guides.src.app import app as quart_app
    client = quart_app.test_client()
    resp = asyncio.run(client.post('/generate_quick_guide', json={'city': 'Tlaquepaque, Mexico', 'neighborhood': 'Centro Barranquitas'}))
    r = asyncio.run(resp.get_json())
    assert r is not None
    assert 'quick_guide' in r
    assert 'Parque A' in r['quick_guide']
    assert r.get('source') == 'geo-enriched'
    assert r.get('confidence') == 'medium'


def test_cached_generic_is_upgraded(monkeypatch, tmp_path):
    # Prepare a cached generic file
    # Write into the real data cache directory used by the app
    from pathlib import Path
    real_cache_dir = Path(__file__).resolve().parent.parent / 'src' / 'data' / 'neighborhood_quick_guides' / 'testcity'
    real_cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = real_cache_dir / 'las_cosa.json'
    cache_content = {'quick_guide': 'Las Cosa is a neighborhood in TestCity.', 'source': 'data-first'}
    cache_file.write_text(__import__('json').dumps(cache_content, ensure_ascii=False, indent=2), encoding='utf-8')
    # Ensure cleanup after test by removing file at the end
    try:
        if cache_file.exists():
            cache_file.unlink()
    except Exception:
        pass
    # Re-create file for the test
    cache_file.write_text(__import__('json').dumps(cache_content, ensure_ascii=False, indent=2), encoding='utf-8')

    # Monkeypatch file location resolution in app to use tmp_path by overriding slug(city) usage
    # We'll monkeypatch Path creation by replacing the cache_dir variable in the handler via monkeypatching the function

    async def fake_enrich(city, neighborhood, session=None):
        return {
            'boundary': True,
            'bbox': (-1, -1, 1, 1),
            'pois': [{'name': 'Parque Test', 'type': 'park', 'lat': 0.0, 'lon': 0.0, 'source': 'geoapify'}],
            'text': f"{neighborhood} is a neighborhood in {city}. Notable nearby: Parque Test (park).",
        }

    monkeypatch.setattr('city_guides.src.geo_enrichment.enrich_neighborhood', fake_enrich)

    # Monkeypatch Path creation in app to point to our tmp_path cache dir when city=='TestCity'
    import importlib
    app_module = importlib.import_module('city_guides.src.app')

    def fake_slug(s):
        return 'testcity' if 'TestCity' in s else importlib.import_module('re').sub(r'[^a-z0-9_-]', '_', s.lower().replace(' ', '_'))

    monkeypatch.setattr(app_module, 'slug', fake_slug, raising=False)

    from city_guides.src.app import app as quart_app
    client = quart_app.test_client()
    resp = asyncio.run(client.post('/generate_quick_guide', json={'city': 'TestCity', 'neighborhood': 'Las Cosa'}))
    r = asyncio.run(resp.get_json())
    assert r is not None
    assert r.get('source') == 'geo-enriched'
    assert 'Parque Test' in r.get('quick_guide')
    assert r.get('cached') is True