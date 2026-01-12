import requests


def test_neighborhoods():
    """Simple integration test that queries the running server for neighborhoods.
    Run with the development server running (e.g., `hypercorn app:app -b 127.0.0.1:5010`).
    """
    url = "http://127.0.0.1:5010/neighborhoods?city=Lisbon"
    try:
        r = requests.get(url, timeout=30)
        print("Status:", r.status_code)
        print("Body:", r.text[:1000])
    except Exception as e:
        print("Error contacting server:", e)
