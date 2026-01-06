import sys
import os
import requests
import json

def test_api_search():
    url = "http://127.0.0.1:5010/search"
    payload = {
        "city": "Chesapeake VA",
        "q": "sushi",
        "budget": "any",
        "localOnly": True
    }
    print(f"Testing search with payload: {payload}")
    try:
        r = requests.post(url, json=payload, timeout=30)
        print(f"Status Code: {r.status_code}")
        data = r.json()
        print(f"Count: {data.get('count')}")
        for i, v in enumerate(data.get('venues', [])[:5]):
            print(f"{i+1}. {v['name']} ({v['budget']}) - {v['provider']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api_search()
