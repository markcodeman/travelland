import aiohttp
import re
from bs4 import BeautifulSoup
from typing import Optional

WIKI_API_URL = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"

async def fetch_wikipedia_summary(title: str, lang: str = "en", city: Optional[str] = None, country: Optional[str] = None, debug_logs: Optional[list] = None) -> Optional[str]:
    """Fetch summary for a Wikipedia page title.
    Handles disambiguation by trying city, country format."""
    headers = {'User-Agent': 'TravelLand/1.0 (Educational; contact@example.com)'}
    
    # Try multiple variations to avoid disambiguation pages
    search_variations = []
    
    # Primary: City, Country
    if country:
        search_variations.append(f"{title}, {country}")
    
    # Secondary: Just city name
    search_variations.append(title)
    
    # Tertiary: City (Country)
    if country:
        search_variations.append(f"{title} ({country})")
    
    for search_title in search_variations:
        slug = re.sub(r"\s+", "_", search_title)
        url = WIKI_API_URL.format(lang=lang, title=slug)
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        extract = data.get("extract")
                        
                        # Check if this is a disambiguation page
                        if extract and not looks_like_disambiguation(extract):
                            if debug_logs:
                                debug_logs.append(f"[WIKI] Found valid summary for '{search_title}'")
                            return extract
                        elif extract:
                            if debug_logs:
                                debug_logs.append(f"[WIKI] Skipping disambiguation for '{search_title}'")
                            
                    # Continue to next variation
            except Exception as e:
                if debug_logs:
                    debug_logs.append(f"[WIKI] Error fetching '{search_title}': {e}")
                continue
    
    # If all variations failed, try English as fallback
    if lang != "en":
        return await fetch_wikipedia_summary(title, "en", city, country, debug_logs)
    
    return None


def looks_like_disambiguation(text: str) -> bool:
    """Check if text is from a disambiguation page."""
    if not text:
        return True
    
    low = text.lower()
    disambig_markers = [
        'may refer to', 'may also refer', 'the spanish word for', 'is the name of',
        'is a surname', 'disambiguation', 'may be', 'may also be', 'may denote',
        'see also', 'for other uses', 'this article is about', 'for the'
    ]
    
    # Check first 100 characters for disambiguation markers
    text_start = low[:200]
    for marker in disambig_markers:
        if marker in text_start:
            return True
    
    # Check if it looks like a list of different things
    if low.count(',') >= 3 and 'may refer' in low[:300]:
        return True
    
    return False

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
