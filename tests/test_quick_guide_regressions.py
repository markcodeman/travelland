import re
import requests

NEIGHBOR_TESTS = [
    {'city': 'Guadalajara, Mexico', 'neighborhood': 'Las Conchas'},
    {'city': 'San Juan, Puerto Rico', 'neighborhood': 'La Perla'},
    {'city': 'Guadalajara, Mexico', 'neighborhood': 'Analco'},
    {'city': 'Mexico City, Mexico', 'neighborhood': 'La Merced'},
]


def is_disambig_text(s: str) -> bool:
    s = (s or '').lower()
    for p in ['may refer to', 'the spanish word for', 'may also refer', 'disambiguation', 'missing:']:
        if p in s:
            return True
    return False


def test_neighborhood_quick_guides_are_sane():
    url = 'http://localhost:5010/generate_quick_guide'
    for t in NEIGHBOR_TESTS:
        resp = requests.post(url, json={'city': t['city'], 'neighborhood': t['neighborhood']}, timeout=15)
        assert resp.status_code == 200
        j = resp.json()
        q = (j.get('quick_guide') or '').lower()
        assert t['neighborhood'].split(',')[0].lower() in q or re.sub(r'[^a-z0-9]+','',t['neighborhood'].lower()) in re.sub(r'[^a-z0-9]+','',q)
        assert not is_disambig_text(q)
        assert len(q) > 40
