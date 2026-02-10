import aiohttp
from aiohttp import ClientTimeout


async def duckduckgo_search(query, max_results=10):
    """Fallback search using DuckDuckGo instant answers API."""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        results = []
        seen = set()

        # Add instant answer if available
        if data.get("AbstractText"):
            title = data.get("Heading", "Instant Answer")
            url = data.get("AbstractURL", "")
            snippet = data.get("AbstractText", "")
            if url and snippet:
                key = url
                if key not in seen:
                    seen.add(key)
                    results.append(
                        {"title": title, "url": url, "snippet": snippet})

        # Add related topics
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict):
                title = (
                    topic.get("Text", "").split(" - ")[0]
                    if " - " in topic.get("Text", "")
                    else topic.get("Text", "")
                )
                url = topic.get("FirstURL", "")
                snippet = topic.get("Text", "")
                if url and title and snippet:
                    key = url
                    if key not in seen:
                        seen.add(key)
                        results.append(
                            {"title": title, "url": url, "snippet": snippet})
                        if len(results) >= max_results:
                            break

        return results[:max_results]
    except Exception:
        return []
