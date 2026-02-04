import json
from pathlib import Path

SEED = Path(__file__).resolve().parents[1] / 'city_guides' / 'data' / 'seeded_cities.json'


def test_seed_file_exists_and_counts():
    assert SEED.exists(), f"Seed file missing at {SEED}"
    data = json.loads(SEED.read_text())
    assert 'cities' in data
    assert data.get('count', None) == len(data['cities'])
    assert data.get('count', 0) >= 500, "Expected at least 500 seeded cities"


def test_seed_schema():
    data = json.loads(SEED.read_text())
    for c in data['cities']:
        assert 'name' in c and isinstance(c['name'], str) and c['name']
        assert 'countryCode' in c and isinstance(c['countryCode'], str)
        assert 'lat' in c
        assert 'lon' in c
        assert c.get('source') == 'seed'
