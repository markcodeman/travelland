import pytest
import json
from city_guides.src import app as quart_app_module


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def ping(self):
        return True

    async def incrby(self, key, amount):
        self.store[key] = int(self.store.get(key, 0)) + amount

    async def lpush(self, key, value):
        self.store.setdefault(key, []).insert(0, float(value))

    async def ltrim(self, key, start, stop):
        if key in self.store:
            self.store[key] = self.store[key][start:stop+1]

    async def keys(self, pattern):
        if pattern == 'metrics:counter:*':
            return [k for k in self.store.keys() if k.startswith('metrics:counter:')]
        if pattern == 'metrics:lat:*':
            return [k for k in self.store.keys() if k.startswith('metrics:lat:')]
        return []

    async def get(self, key):
        return self.store.get(key)

    async def lrange(self, key, start, stop):
        return self.store.get(key, [])[start:stop+1]


@pytest.mark.asyncio
async def test_metrics_endpoint(monkeypatch):
    fake_redis = FakeRedis()
    # Ensure the app startup will pick up our fake redis (patch aioredis.from_url)
    monkeypatch.setattr(quart_app_module.aioredis, 'from_url', lambda url: fake_redis)

    # instrument some metrics via the helpers
    from city_guides.src.metrics import increment, observe_latency
    await increment('test.counter', 2)
    await observe_latency('test.latency', 100.0)
    await observe_latency('test.latency', 120.0)

    # call endpoint
    async with quart_app_module.app.test_app() as test_app:
        async with test_app.test_client() as client:
            resp = await client.get('/metrics/json')
            assert resp.status_code == 200
            data = await resp.get_json()
            assert data['counters'].get('test.counter') == 2
            assert 'test.latency' in data['latencies']
            assert data['latencies']['test.latency']['count'] == 2
