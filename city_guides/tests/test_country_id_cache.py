import asyncio
import json

import pytest

import city_guides.src.app as app


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value


class FakeSession:
    class Resp:
        def __init__(self, status, payload):
            self.status = status
            self._payload = payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return self._payload

    def __init__(self, payload):
        self.payload = payload

    def get(self, url, params=None, timeout=None):
        return FakeSession.Resp(200, self.payload)


@pytest.mark.asyncio
async def test_country_id_cached_in_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(app, 'redis_client', fake)

    # Simulate GeoNames returning a geonameId
    payload = {'geonames': [{'geonameId': 4444}]}
    session = FakeSession(payload)

    cid = await app._get_country_geoname_id('MX', session)
    assert cid == 4444
    # Ensure Redis got the value set
    key = 'geonames:country_id:MX'
    assert key in fake.store
    assert str(fake.store[key]) == '4444'

    # Subsequent call should use Redis and return same value without calling remote (session still works)
    fake2 = FakeRedis()
    fake2.store[key] = '4444'
    monkeypatch.setattr(app, 'redis_client', fake2)
    cid2 = await app._get_country_geoname_id('MX', session)
    assert cid2 == 4444


@pytest.mark.asyncio
async def test_negative_lookup_cached(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(app, 'redis_client', fake)

    # Simulate GeoNames returning no results
    payload = {'geonames': []}
    session = FakeSession(payload)

    cid = await app._get_country_geoname_id('ZZ', session)
    assert cid is None
    key = 'geonames:country_id:ZZ'
    assert key in fake.store
    assert fake.store[key] == 'null'

    # Subsequent call should return None from Redis
    fake2 = FakeRedis()
    fake2.store[key] = 'null'
    monkeypatch.setattr(app, 'redis_client', fake2)
    cid2 = await app._get_country_geoname_id('ZZ', session)
    assert cid2 is None
