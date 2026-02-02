import os
import sys
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json, re
from pathlib import Path
from city_guides.providers.utils import http_post


def slug(s):
    return re.sub(r'[^a-z0-9_-]', '_', s.lower().replace(' ', '_'))


def test_cached_ddgs_disambig_is_replaced():
    url='http://localhost:5010/generate_quick_guide'
    payload={'city':'Tlaquepaque, Mexico','neighborhood':'Revolucion'}
    cache_dir=Path('city_guides/src/data/neighborhood_quick_guides')/slug(payload['city'])
    cache_dir.mkdir(parents=True,exist_ok=True)
    cache_file=cache_dir/(slug(payload['neighborhood'])+'.json')
    # Seed a known disambiguation ddgs cache
    cache_file.write_text(json.dumps({'quick_guide':'Revolución may refer to several things, including a festival and a surname','source':'ddgs','source_url':'https://example.com'},ensure_ascii=False))

    async def make_request():
        resp_data, error = await http_post(url, json_data=payload, timeout=10)
        assert error is None, f"Request failed: {error}"
        q = resp_data.get('quick_guide') or ''
        # Should not return the disambiguation text and should not have source 'ddgs'
        assert 'may refer to' not in q.lower()
        assert resp_data.get('source') != 'ddgs'
        # Cache file should now contain the replaced synthesized paragraph
        data = json.loads(open(cache_file).read())
        assert 'may refer to' not in data.get('quick_guide', '').lower()
        assert data.get('source') != 'ddgs'
    
    asyncio.run(make_request())
