import sys
import os
import json

# ensure project root is on sys.path so we can import app
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app


def post(client, payload):
    resp = client.post("/search", json=payload)
    data = resp.get_json()
    print(json.dumps(data, indent=2))
    return data


if __name__ == "__main__":
    with app.test_client() as c:
        print("ALL:")
        all_data = post(c, {"city": "NYC", "budget": "any", "q": ""})
        print("ALL count:", all_data.get("count"))
        print("\nCHEAP:")
        cheap_data = post(c, {"city": "NYC", "budget": "cheap", "q": ""})
        print("CHEAP count:", cheap_data.get("count"))
        print("\nSUSHI:")
        sushi_data = post(c, {"city": "NYC", "budget": "any", "q": "sushi"})
        print("SUSHI count:", sushi_data.get("count"))
        print("\nGET / (length of HTML bytes):")
        r = c.get("/")
        print(r.status_code, len(r.data))
