import aiohttp
import re
from bs4 import BeautifulSoup
from typing import Optional

WIKI_API_URL = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{}"

async def fetch_wikipedia_summary(title: str, lang: str = "en", city: Optional[str] = None, debug_logs: Optional[list] = None) -> Optional[str]:
    """Fetch summary for a Wikipedia page title."""
    slug = re.sub(r"\s+", "_", title)
    url = WIKI_API_URL.format(slug, lang=lang)
    headers = {'User-Agent': 'TravelLand/1.0 (Educational; contact@example.com)'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                extract = data.get("extract")
                if extract:
                    return extract
            # If failed with given lang, try English
            if lang != "en":
                url = WIKI_API_URL.format(slug, lang="en")
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        extract = data.get("extract")
                        if extract:
                            return extract
    return None

async def fetch_wikipedia_full(title: str, lang: str = "en") -> Optional[dict]:
    """Fetch full HTML and parse sections for a Wikipedia page title."""
    slug = re.sub(r"\s+", "_", title)
    url = f"https://{lang}.wikipedia.org/wiki/{slug}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                sections = {}
                for h2 in soup.find_all("h2"):
                    section_title = h2.text.strip()
                    content = []
                    for sib in h2.find_next_siblings():
                        if sib.name == "h2":
                            break
                        if sib.name in ["p", "ul", "ol"]:
                            content.append(sib.get_text(" ", strip=True))
                    if content:
                        sections[section_title] = " ".join(content)
                return sections
    return None
