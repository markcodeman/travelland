import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
import json
import re
from pathlib import Path


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

    r=requests.post(url,json=payload,timeout=10)
    assert r.status_code==200
    j=r.json()
    q=j.get('quick_guide') or ''
    # Should not return the disambiguation text and should not have source 'ddgs'
    assert 'may refer to' not in q.lower()
    assert j.get('source') != 'ddgs'
    # Cache file should now contain the replaced synthesized paragraph
    data=json.loads(open(cache_file).read())
    assert 'may refer to' not in (data.get('quick_guide') or '').lower()
    assert data.get('source') in ('synthesized','data-first')
