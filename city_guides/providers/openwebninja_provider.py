import os
import aiohttp

OPENWEBNINJA_API_KEY = os.getenv("OPENWEBNINJA_API_KEY", "YOUR_OPENWEBNINJA_API_KEY")
API_URL = "https://real-time-web-search.p.rapidapi.com/search"

async def openwebninja_search(query, page=1, limit=10):
    headers = {
        "X-RapidAPI-Key": OPENWEBNINJA_API_KEY,
        "X-RapidAPI-Host": "real-time-web-search.p.rapidapi.com",
    }
    params = {
        "query": query,
        "limit": limit,
        "page": page,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, headers=headers, params=params, timeout=15) as resp:
            resp.raise_for_status()
            return await resp.json()

"""
Usage:
from city_guides.providers.openwebninja_provider import openwebninja_search
results = await openwebninja_search("Tlaquepaque Jalisco travel")
"""
