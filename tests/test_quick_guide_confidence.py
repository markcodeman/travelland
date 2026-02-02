import pytest
import asyncio
from city_guides.providers.utils import http_post

BASE = 'http://localhost:5010'

@pytest.mark.parametrize('city,neighborhood', [
    ('Ensenada, Mexico', 'Magueyes'),
    ('Ensenada, Mexico', 'Phoenix Acres Trailer Park'),
    ('Guadalajara, Mexico', 'Santa Tere'),
])
def test_low_confidence_neighborhoods_return_minimal(city, neighborhood):
    async def make_request():
        resp_data, error = await http_post(BASE + '/generate_quick_guide', json_data={'city': city, 'neighborhood': neighborhood}, timeout=10)
        if error:
            pytest.skip('Backend not available')
        assert resp_data.get('confidence') == 'low'
        assert resp_data.get('quick_guide') == f"{neighborhood} is a neighborhood in {city}."
    
    asyncio.run(make_request())


def test_analco_is_medium_confidence():
    async def make_request():
        resp_data, error = await http_post(BASE + '/generate_quick_guide', json_data={'city': 'Guadalajara, Mexico', 'neighborhood': 'Analco'}, timeout=10)
        if error:
            pytest.skip('Backend not available')
        assert resp_data.get('confidence') in ('medium','high')
        assert len(resp_data.get('quick_guide','')) > 40
    
    asyncio.run(make_request())


def test_copacabana_is_high_confidence():
    async def make_request():
        resp_data, error = await http_post(BASE + '/generate_quick_guide', json_data={'city': 'Rio de Janeiro', 'neighborhood': 'Copacabana'}, timeout=10)
        if error:
            pytest.skip('Backend not available')
        assert resp_data.get('confidence') == 'high'
        assert 'beach' in resp_data.get('quick_guide','').lower()
    
    asyncio.run(make_request())