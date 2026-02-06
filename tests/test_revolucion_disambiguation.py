import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from city_guides.src.neighborhood_disambiguator import NeighborhoodDisambiguator
import requests


def test_canonicalize_revolucion():
    c = NeighborhoodDisambiguator.canonicalize('Revolucion', 'Tlaquepaque')
    assert c == 'Revolución'


def test_generate_quick_guide_revolucion_is_neighborhood():
    # This is an integration test that requires the backend running on localhost:5010
    url = 'http://localhost:5010/generate_quick_guide'
    payload = {'city': 'Tlaquepaque, Mexico', 'neighborhood': 'Revolucion'}
    resp = requests.post(url, json=payload, timeout=10)
    assert resp.status_code == 200
    j = resp.json()
    q = (j.get('quick_guide') or '').lower()
    # Should mention the neighborhood (accent-insensitive) and not be a disambiguation sentence
    assert 'revolucion' in q or 'revolución' in q
    assert 'may refer to' not in q and 'the spanish word for' not in q and 'may also refer' not in q
