import json
from pathlib import Path

SEED = Path(__file__).resolve().parents[1] / 'city_guides' / 'data' / 'seeded_cities.json'


def test_seed_last_updated_is_timezone_aware():
    assert SEED.exists(), "seed file missing"
    data = json.loads(SEED.read_text())
    last = data.get('last_updated')
    assert last is not None, "last_updated missing"
    # ISO format with timezone info (should include 'Z' or +/-)
    assert ('Z' in last) or ('+' in last) or ('-' in last), "last_updated should include timezone info"
