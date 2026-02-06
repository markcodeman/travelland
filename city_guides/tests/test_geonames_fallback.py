
import pytest

import city_guides.overpass_provider as overpass_provider


@pytest.mark.asyncio
async def test_geonames_fallback(monkeypatch):
    # ensure Overpass endpoints are skipped
    monkeypatch.setattr(overpass_provider, 'OVERPASS_URLS', [])

    # fake geonames provider
    async def fake_geonames(city=None, lat=None, lon=None, session=None, max_rows=None):
        return [{"id": "geonames/42", "name": "Fakehood", "slug": "fakehood", "center": {"lat": 1.0, "lon": 2.0}, "bbox": None, "source": "geonames"}]

    # set env to signal geonames is available
    monkeypatch.setenv('GEONAMES_USERNAME', 'fakeuser')
    import city_guides.geonames_provider as geonames_provider
    monkeypatch.setattr(geonames_provider, 'async_get_neighborhoods_geonames', fake_geonames)

    res = await overpass_provider.async_get_neighborhoods(city='Nowhere')
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]['source'] == 'geonames'
    assert res[0]['name'] == 'Fakehood'
