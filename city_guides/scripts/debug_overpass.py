from city_guides.providers import overpass_provider
import requests
import json

bbox = overpass_provider.geocode_city("Paris")
if not bbox:
    print("Geocoding failed")
    exit()

south, west, north, east = bbox
bbox_str = f"{south},{west},{north},{east}"
q = f'[out:json][timeout:25];(node["amenity"~"restaurant"]({bbox_str}););out center;'
print(f"Query: {q}")

headers = {"User-Agent": "CityGuides/1.0"}
r = requests.post(
    "https://overpass-api.de/api/interpreter", data={"data": q}, headers=headers
)
print(f"Status: {r.status_code}")
j = r.json()
elements = j.get("elements", [])
print(f"Elements found: {len(elements)}")
if elements:
    print(f"First element: {json.dumps(elements[0], indent=2)}")
