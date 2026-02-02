import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from city_guides.src.neighborhood_disambiguator import NeighborhoodDisambiguator
from city_guides.providers.utils import http_post
import asyncio


def test_canonicalize_revolucion():
    c = NeighborhoodDisambiguator.canonicalize('Revolucion', 'Tlaquepaque')
    assert c == 'Revolución'


def test_generate_quick_guide_revolucion_is_neighborhood():
    # This is an integration test that requires the backend running on localhost:5010
    url = 'http://localhost:5010/generate_quick_guide'
    payload = {'city': 'Tlaquepaque, Mexico', 'neighborhood': 'Revolucion'}
    
    async def make_request():
        resp_data, error = await http_post(url, json_data=payload, timeout=10)
        assert error is None, f"Request failed: {error}"
        assert resp_data is not None, "No response data"
        q = (resp_data.get('quick_guide') or '').lower()
        # Should mention the neighborhood (accent-insensitive) and not be a disambiguation sentence
        assert 'revolucion' in q or 'revolución' in q
        assert 'may refer to' not in q and 'the spanish word for' not in q and 'may also refer' not in q
    
    asyncio.run(make_request())
