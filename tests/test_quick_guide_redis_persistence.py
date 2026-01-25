import os
import sys
import pytest
import asyncio
import json
import re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import city_guides.src.app as appmod
app = appmod.app
from pathlib import Path

class FakeRedis:
    def __init__(self):
        self.store = {}
    async def set(self, key, value, ex=None):
        self.store[key] = (value, ex)

def test_quick_guide_written_to_redis(monkeypatch):
    async def _run():
        fake = FakeRedis()
        appmod.redis_client = fake
        # Ensure no cached file exists so code will run generation path and persist to redis
        import os, re
        def slug(s):
            return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')
        cache_path = Path('city_guides/src/data/neighborhood_quick_guides')/slug('Guadalajara, Mexico')/(slug('Analco')+'.json')
        try:
            if cache_path.exists():
                cache_path.unlink()
        except Exception:
            pass
        async with app.test_client() as client:
            resp = await client.post('/generate_quick_guide', json={'city':'Guadalajara, Mexico','neighborhood':'Analco'})
            assert resp.status_code == 200
            j = await resp.get_json()
            # key check
            slug_city = re.sub(r'[^a-z0-9]+', '_', 'Guadalajara, Mexico'.lower()).strip('_')
            slug_nb = re.sub(r'[^a-z0-9]+', '_', 'Analco'.lower()).strip('_')
            key = f"quick_guide:{slug_city}:{slug_nb}"
            # Give event loop a tick
            await asyncio.sleep(0.05)
            assert key in fake.store
            val, ex = fake.store[key]
            data = json.loads(val)
            assert 'quick_guide' in data
            assert data['source'] in ('synthesized', 'wikipedia', 'data-first', 'ddgs')
    asyncio.run(_run())
