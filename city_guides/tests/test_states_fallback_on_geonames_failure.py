import asyncio

import pytest

from city_guides.src import app


@pytest.mark.asyncio
async def test_states_fallback_when_geonames_fails(monkeypatch):
    # Ensure GEONAMES_USERNAME is set (so code goes through GeoNames path)
    monkeypatch.setenv('GEONAMES_USERNAME', 'fakeuser')

    # Monkeypatch _get_country_geoname_id to simulate failure (returns None)
    async def fake_get_country_geoname_id(country_code, session):
        return None

    monkeypatch.setattr(app, '_get_country_geoname_id', fake_get_country_geoname_id)

    states = await app._get_states('MX')
    # Should fall back to the built-in list for MX
    assert isinstance(states, list)
    assert len(states) > 0
    assert any(s.get('code') == 'JC' or s.get('name') == 'Jalisco' for s in states)
