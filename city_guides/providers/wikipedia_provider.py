
from typing import Optional
WIKIVOYAGE_API_URL = "https://{lang}.wikivoyage.org/api/rest_v1/page/summary/{title}"

async def fetch_wikivoyage_summary(title: str, lang: str = "en", city: Optional[str] = None, country: Optional[str] = None, debug_logs: Optional[list] = None) -> Optional[str]:
    """Fetch summary for a WikiVoyage page title. Handles disambiguation by trying city, country format."""
    headers = {'User-Agent': 'TravelLand/1.0 (Educational; contact@example.com)'}
    search_variations = []
    if country:
        search_variations.append(f"{title}, {country}")
    search_variations.append(title)
    if country:
        search_variations.append(f"{title} ({country})")
    for search_title in search_variations:
        slug = re.sub(r"\s+", "_", search_title)
        url = WIKIVOYAGE_API_URL.format(lang=lang, title=slug)
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        extract = data.get("extract")
                        if extract and not looks_like_disambiguation(extract):
                            if debug_logs:
                                debug_logs.append(f"[WIKIVOYAGE] Found valid summary for '{search_title}'")
                            return extract
                        elif extract:
                            if debug_logs:
                                debug_logs.append(f"[WIKIVOYAGE] Skipping disambiguation for '{search_title}'")
            except Exception as e:
                if debug_logs:
                    debug_logs.append(f"[WIKIVOYAGE] Error fetching '{search_title}': {e}")
    return None
import aiohttp
import re
import time
from bs4 import BeautifulSoup

WIKI_API_URL = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"

async def fetch_wikipedia_summary(title: str, lang: str = "en", city: Optional[str] = None, country: Optional[str] = None, debug_logs: Optional[list] = None) -> Optional[str]:
    """Fetch summary for a Wikipedia page title.
    Handles disambiguation by trying city, country format."""
    headers = {'User-Agent': 'TravelLand/1.0 (Educational; contact@example.com)'}
    
    # Normalize country names for Wikipedia
    country_normalizations = {
        'bosnia': 'Bosnia and Herzegovina',
        'czech republic': 'Czech Republic', 
        'czech': 'Czech Republic',
        'uk': 'United Kingdom',
        'usa': 'United States',
        'us': 'United States',
        'uae': 'United Arab Emirates',
        'south korea': 'South Korea',
        'north korea': 'North Korea'
    }
    
    normalized_country = country_normalizations.get(country.lower(), country) if country else None
    
    # Try multiple variations to avoid disambiguation pages
    search_variations = []
    # Primary: City, Country
    if normalized_country:
        search_variations.append(f"{title}, {normalized_country}")
    # Secondary: Just city name
    search_variations.append(title)
    # Tertiary: City (Country)
    if normalized_country:
        search_variations.append(f"{title} ({normalized_country})")
    for search_title in search_variations:
        slug = re.sub(r"\s+", "_", search_title)
        url = WIKI_API_URL.format(lang=lang, title=slug)
        if debug_logs is not None:
            debug_logs.append(f"[WIKI] Trying title: '{search_title}' (URL: {url})")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        extract = data.get("extract")
                        if debug_logs is not None:
                            debug_logs.append(f"[WIKI] Response for '{search_title}': {repr(extract)[:120]}")
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
        if debug_logs is not None:
            debug_logs.append(f"[WIKI] Retrying in English for '{title}'")
        return await fetch_wikipedia_summary(title, "en", city, country, debug_logs)
    if debug_logs is not None:
        debug_logs.append(f"[WIKI] No valid summary found for '{title}'")
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


# Lightweight, cached helper to fetch a specific section's rendered HTML using the
# REST "mobile-sections" endpoint. This is faster and more stable than full
# page-scraping for the common use-case of returning one named section.
_WIKI_SECTION_CACHE: dict = {}


def _normalize_wikipedia_section_html(html: str, lang: str = "en") -> str:
    """Normalize Wikipedia section HTML for safe, consistent app rendering.

    - Removes noisy elements like edit links and reference superscripts
    - Converts relative links/images to absolute Wikipedia URLs
    - Strips inline styles/classes so frontend scoped CSS can control appearance
    """
    if not html:
        return html

    soup = BeautifulSoup(html, "html.parser")

    # Remove noisy/meta elements
    for sel in [
        ".mw-editsection",
        "sup.reference",
        "span.reference",
        ".noprint",
        ".mw-empty-elt",
    ]:
        for node in soup.select(sel):
            node.decompose()

    for table in soup.find_all("table"):
        classes = set(table.get("class", []))
        if classes.intersection({"infobox", "navbox", "metadata", "sidebar", "vertical-navbox"}):
            table.decompose()

    # Normalize anchors
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        if href.startswith("#") or "action=edit" in href:
            a.unwrap()
            continue
        if href.startswith("//"):
            href = f"https:{href}"
        elif href.startswith("/wiki/") or href.startswith("/w/"):
            href = f"https://{lang}.wikipedia.org{href}"
        elif href.startswith("./"):
            href = f"https://{lang}.wikipedia.org/wiki/{href[2:]}"

        a["href"] = href
        a["target"] = "_blank"
        a["rel"] = "noreferrer noopener"

    # Normalize images
    for img in soup.find_all("img", src=True):
        src = (img.get("src") or "").strip()
        if src.startswith("//"):
            src = f"https:{src}"
        elif src.startswith("/"):
            src = f"https://{lang}.wikipedia.org{src}"
        img["src"] = src

    # Strip non-essential attributes to reduce inline visual mismatch
    allowed_attrs = {"href", "src", "alt", "title", "target", "rel"}
    for el in soup.find_all(True):
        if not el.attrs:
            continue
        el.attrs = {k: v for k, v in el.attrs.items() if k in allowed_attrs}

    return str(soup)


def _page_candidates(page: str) -> list[str]:
    """Generate canonical page candidates for section lookup.

    Example: "Bucharest, Romania" -> ["Bucharest, Romania", "Bucharest"]
    """
    base = (page or '').strip()
    if not base:
        return []

    candidates = [base]
    if ',' in base:
        city_only = base.split(',', 1)[0].strip()
        if city_only and city_only not in candidates:
            candidates.append(city_only)

    # de-duplicate while preserving order
    seen = set()
    ordered = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _section_candidates(section_title: str) -> list[str]:
    """Return section fallback candidates, ordered by priority."""
    base = (section_title or '').strip()
    if not base:
        return []

    low = base.lower()
    candidates = [base]

    # City pages often don't have a literal "Tourism" section but do have nearby equivalents.
    if low in {"tourism", "travel", "attractions", "visitor attractions"}:
        candidates.extend([
            "Tourism",
            "Attractions",
            "Landmarks",
            "Culture",
            "Architecture",
            "History",
        ])

    seen = set()
    ordered = []
    for c in candidates:
        k = c.lower().strip()
        if k and k not in seen:
            seen.add(k)
            ordered.append(c)
    return ordered


def _matches_section(line: str, anchor: str, target: str) -> bool:
    """Case-insensitive exact section match."""
    t = (target or '').strip().lower()
    if not t:
        return False
    l = (line or '').strip().lower()
    a = (anchor or '').strip().lower()

    return l == t or a == t

async def async_fetch_wikipedia_section(page: str, section_title: str, lang: str = "en", cache_ttl: int = 86400) -> Optional[str]:
    """Return rendered HTML for a named section (case-insensitive).

    - Uses REST API /page/mobile-sections/{title} to discover sections and
      returns the section's `text` (rendered HTML) when found.
    - Caches results in-process for `cache_ttl` seconds to speed repeat calls.
    """
    if not page or not section_title:
        return None

    page = page.strip()
    section_title = section_title.strip()
    slug = re.sub(r"\s+", "_", page)
    key = f"{lang}:{slug}:{section_title.lower()}"
    now = int(time.time())

    # Check in-process cache first
    entry = _WIKI_SECTION_CACHE.get(key)
    if entry and now - entry[0] < cache_ttl:
        return entry[1]

    # Try Redis (shared cache) if available
    try:
        from city_guides.src.app import redis_client
        if redis_client:
            try:
                val = await redis_client.get(f"wiki:section:{key}")
                if val:
                    html_val = val.decode() if isinstance(val, (bytes, bytearray)) else val
                    _WIKI_SECTION_CACHE[key] = (now, html_val)
                    return html_val
            except Exception:
                # ignore redis errors and continue to live fetch
                pass
    except Exception:
        pass

    page_targets = _page_candidates(page)
    section_targets = _section_candidates(section_title)

    # Try mobile-sections API first (per page candidate)
    headers = {"User-Agent": "TravelLand/1.0"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            for page_target in page_targets:
                page_slug = re.sub(r"\s+", "_", page_target)
                url = f"https://{lang}.wikipedia.org/api/rest_v1/page/mobile-sections/{page_slug}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        continue

                    data = await resp.json()
                    sections = data.get("sections", [])
                    for target in section_targets:
                        for s in sections:
                            if _matches_section(s.get("line", ""), s.get("anchor", ""), target):
                                html = _normalize_wikipedia_section_html(s.get("text") or "", lang=lang)
                                _WIKI_SECTION_CACHE[key] = (now, html)
                                try:
                                    from city_guides.src.app import redis_client
                                    if redis_client:
                                        await redis_client.set(f"wiki:section:{key}", html, ex=cache_ttl)
                                except Exception:
                                    pass
                                return html
    except Exception:
        pass

    # Fallback: use Action API to discover sections and parse by index
    api_url = f"https://{lang}.wikipedia.org/w/api.php"
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "TravelLand/1.0"}) as session:
            for page_target in page_targets:
                page_slug = re.sub(r"\s+", "_", page_target)
                params = {"action": "parse", "page": page_slug, "prop": "sections", "format": "json"}
                async with session.get(api_url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as aresp:
                    if aresp.status != 200:
                        continue

                    j = await aresp.json()
                    sections = j.get("parse", {}).get("sections", [])
                    found_index = None
                    for target in section_targets:
                        for s in sections:
                            if _matches_section(s.get("line", ""), s.get("anchor", ""), target):
                                found_index = s.get("index")
                                break
                        if found_index:
                            break

                    if not found_index:
                        continue

                    # Now fetch the parsed HTML for that section index
                    params2 = {"action": "parse", "page": page_slug, "section": found_index, "prop": "text", "format": "json"}
                    async with session.get(api_url, params=params2, timeout=aiohttp.ClientTimeout(total=8)) as sresp:
                        if sresp.status != 200:
                            continue
                        sjs = await sresp.json()
                        html = _normalize_wikipedia_section_html(
                            sjs.get("parse", {}).get("text", {}).get("*"),
                            lang=lang,
                        )
                        if html:
                            _WIKI_SECTION_CACHE[key] = (now, html)
                            try:
                                from city_guides.src.app import redis_client
                                if redis_client:
                                    await redis_client.set(f"wiki:section:{key}", html, ex=cache_ttl)
                            except Exception:
                                pass
                            return html
    except Exception:
        return None
    return None
