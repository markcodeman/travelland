import asyncio
import json
import types
import pytest
from city_guides.src import app as quart_app_module


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.set_calls = []

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value
        self.set_calls.append((key, ttl, value))

    async def expire(self, key, ttl):
        # no-op for test
        return True


class DummyResp:
    def __init__(self, status=200, payload=None):
        self.status = status
        self._payload = payload or {"answer": "prewarm"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.posts = []

    def post(self, url, json=None, timeout=None):
        self.posts.append((url, json, timeout))
        return DummyResp()


@pytest.mark.asyncio
async def test_prewarm_rag_sets_cache(monkeypatch, tmp_path):
    # Use a small seed file
    seed_path = quart_app_module.Path(quart_app_module.Path(__file__).parents[1] / 'city_guides' / 'data' / 'seeded_cities.json')
    assert seed_path.exists(), 'seed file missing for test'

    fake_redis = FakeRedis()
    fake_session = FakeSession()

    # Monkeypatch global redis_client and aiohttp_session
    monkeypatch.setattr(quart_app_module, 'redis_client', fake_redis)
    monkeypatch.setattr(quart_app_module, 'aiohttp_session', fake_session)

    # Run prewarm for top 1 city to keep it fast
    await quart_app_module.prewarm_rag_responses(top_n=1)

    # Verify at least one cache set occurred
    assert len(fake_redis.set_calls) > 0
    key, ttl, value = fake_redis.set_calls[0]
    assert key.startswith('rag:'), 'Cache key should start with rag:'
    parsed = json.loads(value)
    assert 'answer' in parsed
