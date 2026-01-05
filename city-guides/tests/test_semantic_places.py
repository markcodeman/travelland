import semantic
import search_provider
import places_provider

class DummyResp:
    def __init__(self, status_code=500, text='error'):
        self.status_code = status_code
        self.text = text
    def json(self):
        return {}


def test_search_and_reason_includes_places_on_fallback(monkeypatch):
    # Mock searx to return no results
    monkeypatch.setattr(search_provider, 'searx_search', lambda q, max_results=8, city=None: [])

    # Provide multiple Places results
    mock_places = [
        {'name': f'Taco {i}', 'address': f'Addr {i}', 'rating': 4.0 + i * 0.1, 'place_id': f'pid{i}', 'osm_url': f'https://maps.example/taco{i}'} for i in range(6)
    ]
    monkeypatch.setattr(places_provider, 'discover_restaurants', lambda city, limit=5, cuisine=None: mock_places[:limit])

    # Mock Groq to fail
    monkeypatch.setattr(semantic, 'requests', type('R', (), {'post': lambda *a, **k: DummyResp(500, 'error')}))

    res = semantic.search_and_reason('best tacos', city='TestCity', mode='explorer')

    assert 'Taco 0' in res
    assert 'Safe travels and happy exploring! - Marco' in res


def test_prompt_sent_to_groq_includes_places(monkeypatch):
    # Make searx return a couple of stub results so prompt is built
    monkeypatch.setattr(search_provider, 'searx_search', lambda q, max_results=8, city=None: [
        {'title': 'Local Food Blog', 'url': 'https://example.com', 'snippet': 'Great tacos at X'}
    ])

    places = [{'name': 'Tacos Naranja', 'address': '20.6317,-103.4287', 'rating': None, 'place_id': 'abc123', 'osm_url': ''}]
    monkeypatch.setattr(places_provider, 'discover_restaurants', lambda city, limit=5, cuisine=None: places)

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured['json'] = json
        class R:
            status_code = 200
            def json(self):
                return {'choices': [{'message': {'content': 'Mocked Marco answer'}}]}
            text = 'OK'
        return R()

    monkeypatch.setattr(semantic, 'requests', type('R', (), {'post': fake_post}))

    resp = semantic.search_and_reason('best tacos', city='TestCity', mode='explorer')

    # Ensure the prompt sent to Groq contains the places context
    assert captured and 'Places Results (from Google Places)' in captured['json']['messages'][0]['content']
    assert 'Tacos Naranja' in captured['json']['messages'][0]['content']
    assert resp == 'Mocked Marco answer'

