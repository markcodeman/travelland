import json
import asyncio

import pytest

import city_guides.app as app


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def expire(self, key, ex):
        return True


@pytest.mark.asyncio
async def test_prewarm_popular_neighborhoods(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(app, 'redis_client', fake)

    # monkeypatch POPULAR_CITIES to a short list
    monkeypatch.setattr(app, 'POPULAR_CITIES', ['Test City'])

    async def fake_async_get_neighborhoods(city=None, lang='en', session=None):
        return [{"id": "relation/1", "name": "Fakehood", "slug": "fakehood", "center": {"lat": 1.0, "lon": 2.0}, "bbox": None, "source": "osm"}]

    # patch the provider used by prewarm_neighborhoods
    monkeypatch.setattr('city_guides.multi_provider.async_get_neighborhoods', fake_async_get_neighborhoods)

    # run the background prewarm worker
    await app.prewarm_neighborhoods()

    key = 'neighborhoods:test_city:en'
    assert key in fake.store
    data = json.loads(fake.store[key])
    assert isinstance(data, list)
    assert data[0]['name'] == 'Fakehood'
