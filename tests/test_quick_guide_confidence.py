import pytest
import requests

BASE = 'http://localhost:5010'

@pytest.mark.parametrize('city,neighborhood', [
    ('Ensenada, Mexico', 'Magueyes'),
    ('Ensenada, Mexico', 'Phoenix Acres Trailer Park'),
    ('Guadalajara, Mexico', 'Santa Tere'),
])
def test_low_confidence_neighborhoods_return_minimal(city, neighborhood):
    try:
        r = requests.post(BASE + '/generate_quick_guide', json={'city': city, 'neighborhood': neighborhood}, timeout=10)
        r.raise_for_status()
        j = r.json()
    except requests.RequestException:
        pytest.skip('Backend not available')
    assert j.get('confidence') == 'low'
    assert j.get('quick_guide') == f"{neighborhood} is a neighborhood in {city}."


def test_analco_is_medium_confidence():
    try:
        r = requests.post(BASE + '/generate_quick_guide', json={'city': 'Guadalajara, Mexico', 'neighborhood': 'Analco'}, timeout=10)
        r.raise_for_status()
        j = r.json()
    except requests.RequestException:
        pytest.skip('Backend not available')
    assert j.get('confidence') in ('medium','high')
    assert len(j.get('quick_guide','')) > 40


def test_copacabana_is_high_confidence():
    try:
        r = requests.post(BASE + '/generate_quick_guide', json={'city': 'Rio de Janeiro', 'neighborhood': 'Copacabana'}, timeout=10)
        r.raise_for_status()
        j = r.json()
    except requests.RequestException:
        pytest.skip('Backend not available')
    assert j.get('confidence') == 'high'
    assert 'beach' in j.get('quick_guide','').lower()