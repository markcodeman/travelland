# DDGS (duckduckgo_search) provider for TravelLand
# Supports Google, Brave, Yahoo, Yandex, DuckDuckGo
# No API key required, 100% free

from ddgs import DDGS

async def ddgs_search(query, engine="google", max_results=10):
    """
    Search the web using DDGS (supports: google, brave, yahoo, yandex, duckduckgo)
    Returns a list of dicts with 'title', 'href', 'body' keys.
    """
    results = []
    # DDGS is not async, so run in thread
    from concurrent.futures import ThreadPoolExecutor
    import asyncio
    loop = asyncio.get_event_loop()
    def _search():
        with DDGS() as ddgs:
            return list(ddgs.text(query, region="wt-wt", safesearch="off", timelimit=None, max_results=max_results, backend=engine))
    results = await loop.run_in_executor(ThreadPoolExecutor(), _search)
    return results

"""
Usage:
from city_guides.providers.ddgs_provider import ddgs_search
results = await ddgs_search("Tlaquepaque Jalisco travel", engine="google")
"""
