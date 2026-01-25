# Test DDGS provider
# Usage: python3 tools/test_ddgs_provider.py
import asyncio
from city_guides.providers.ddgs_provider import ddgs_search

async def main():
    query = "Tlaquepaque Jalisco travel"
    try:
        results = await ddgs_search(query, engine="google", max_results=5)
        print("Results:")
        for i, item in enumerate(results, 1):
            print(f"{i}. {item.get('title')}\n{item.get('href')}\n{item.get('body')}\n")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
