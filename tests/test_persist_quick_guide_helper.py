import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from city_guides.src import app as appmod
from pathlib import Path
import json


def test_persist_quick_guide_writes_redis_and_file(tmp_path, monkeypatch):
    async def _run():
        # Prepare out_obj
        out_obj = {'quick_guide': 'Analco is neat', 'source': 'synthesized', 'source_url': None}
        city = 'Guadalajara, Mexico'
        nb = 'Analco'
        file_path = tmp_path / 'analco.json'

        # Fake redis
        class FakeRedis:
            def __init__(self):
                self.store = {}
            async def set(self, key, value, ex=None):
                self.store[key] = (value, ex)
        fake = FakeRedis()
        appmod.redis_client = fake

        # Call helper
        await appmod._persist_quick_guide(out_obj, city, nb, str(file_path)) if hasattr(appmod, '_persist_quick_guide') else None

        # Check file written
        assert file_path.exists()
        data = json.loads(file_path.read_text())
        assert 'quick_guide' in data

        # Check redis written
        slug_city = 'guadalajara_mexico'
        slug_nb = 'analco'
        key = f'quick_guide:{slug_city}:{slug_nb}'
        await asyncio.sleep(0.05)
        assert key in fake.store
    asyncio.run(_run())
