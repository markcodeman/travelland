import aiohttp
import asyncio

# List of Overpass endpoints
OVERPASS_URLS = [
    "https://overpass.osm.jp/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Hampton Hill bbox: [51.4028442,-0.380081,51.4528442,-0.330081]
QUERY = '''[out:json][timeout:25];(
  node["amenity"~"restaurant|fast_food|cafe"](51.4028442,-0.380081,51.4528442,-0.330081);
  way["amenity"~"restaurant|fast_food|cafe"](51.4028442,-0.380081,51.4528442,-0.330081);
  relation["amenity"~"restaurant|fast_food|cafe"](51.4028442,-0.380081,51.4528442,-0.330081);
);
out center;
'''

async def test_all_endpoints():
    headers = {"User-Agent": "CityGuides/1.0"}
    for url in OVERPASS_URLS:
        print(f"\nTesting endpoint: {url}")
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, data={"data": QUERY}, headers=headers) as resp:
                    print(f"Status: {resp.status}")
                    try:
                        data = await resp.json()
                        print(f"Results: {len(data.get('elements', []))} elements")
                    except Exception:
                        text = await resp.text()
                        print(f"Non-JSON response: {text[:200]}...")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_all_endpoints())
