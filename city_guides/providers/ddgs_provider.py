# DDGS (duckduckgo_search) provider for TravelLand
# Supports Google, Brave, Yahoo, Yandex, DuckDuckGo
# No API key required, 100% free

import os
from ddgs import DDGS

from city_guides.src.metrics import increment, MetricsStore

async def ddgs_search(query, engine="google", max_results=3, timeout=5, metrics_store: MetricsStore = None):
    """
    Search the web using DDGS (supports: google, brave, yahoo, yandex, duckduckgo).
    This function runs the blocking DDGS call in a thread and enforces an overall
    async timeout. It caps `max_results` to a small number to reduce latency.

    Params:
    - query: search text
    - engine: backend to use
    - max_results: maximum results to return (will be capped to a safe value)
    - timeout: maximum time in seconds to wait for the search

    Returns a list of dicts with 'title', 'href', 'body' keys.
    """
    results = []
    # Enforce a conservative cap to keep prompts small and searches fast
    try:
        max_results = int(max_results)
    except Exception:
        max_results = 3
    MAX_ALLOWED = int(os.getenv('DDGS_MAX_RESULTS', '3'))
    max_results = min(max_results, MAX_ALLOWED)

    # DDGS is not async, so run it in a thread; use asyncio.run_in_executor and wait_for
    from concurrent.futures import ThreadPoolExecutor
    import asyncio

    def _search():
        with DDGS() as ddgs:
            # pass timelimit to DDGS as an extra guard; it expects seconds (int)
            try:
                return list(ddgs.text(query, region="wt-wt", safesearch="off", timelimit=int(timeout), max_results=max_results, backend=engine))
            except Exception:
                return []

    loop = asyncio.get_running_loop()
    try:
        results = await asyncio.wait_for(loop.run_in_executor(ThreadPoolExecutor(), _search), timeout=timeout)
    except asyncio.TimeoutError:
        # Search timed out; return empty list to allow graceful fallback
        try:
            await increment('ddgs.timeout', metrics_store=metrics_store)
        except Exception:
            pass
        return []
    except Exception:
        try:
            await increment('ddgs.error', metrics_store=metrics_store)
        except Exception:
            pass
        return []
    return results

"""
Usage:
from city_guides.providers.ddgs_provider import ddgs_search
results = await ddgs_search("Tlaquepaque Jalisco travel", engine="google")
"""
