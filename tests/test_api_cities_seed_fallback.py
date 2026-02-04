import os
import asyncio
import json
import pytest
from city_guides.src.app import app as quart_app


@pytest.mark.asyncio
async def test_api_cities_uses_seed_when_geonames_missing(monkeypatch):
    # Ensure GEONAMES_USERNAME is unset
    monkeypatch.delenv('GEONAMES_USERNAME', raising=False)

    async with quart_app.test_app() as test_app:
        async with test_app.test_client() as client:
            resp = await client.get('/api/locations/cities?countryCode=FR&stateCode=11')
            assert resp.status_code == 200
            data = await resp.get_json()
            # Expect a non-empty list coming from seeded cities
            assert isinstance(data, list)
            assert len(data) > 0
            # Check that Paris is present
            names = [c.get('name','').lower() for c in data]
            assert any('paris' in n for n in names) or any('marseille' in n for n in names)
            # Ensure there are no duplicate names for the same country/state
            keys = set((c.get('name','').strip().lower(), (c.get('geonameId') or ''),) for c in data)
            assert len(keys) == len(data), 'Duplicate seeded cities returned'
