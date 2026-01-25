# Test OpenWeb Ninja Real-Time Web Search API
# Usage: python3 tools/test_openwebninja_api.py
import asyncio
from city_guides.providers.openwebninja_provider import openwebninja_search

async def main():
    query = "Tlaquepaque Jalisco travel"
    try:
        results = await openwebninja_search(query)
        print("Results:")
        for i, item in enumerate(results.get("data", []), 1):
            print(f"{i}. {item.get('title')}\n{item.get('url')}\n{item.get('description')}\n")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
