import aiohttp
import re
from bs4 import BeautifulSoup

WIKI_API_URL = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{}"

import asyncio
import logging
import aiohttp
import re
from bs4 import BeautifulSoup

# Helper: Get Wikidata QID for a Wikipedia page
async def get_wikidata_qid(title: str, lang: str = "pt"):
    slug = re.sub(r"\s+", "_", title)
    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=pageprops&format=json&titles={slug}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                pages = data.get("query", {}).get("pages", {})
                for page in pages.values():
                    qid = page.get("pageprops", {}).get("wikibase_item")
                    if qid:
                        return qid
    return None

# Helper: Get English Wikipedia title from Wikidata QID
async def get_enwiki_title_from_qid(qid: str):
    url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&format=json&props=sitelinks"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                sitelinks = data.get("entities", {}).get(qid, {}).get("sitelinks", {})
                enwiki = sitelinks.get("enwiki", {})
                if enwiki:
                    return enwiki.get("title")
    return None


# Simple in-memory cache for translations
_translation_cache = {}

# Helper: Translate text (stub, replace with real translation if needed)
async def translate_to_english(text: str):
    if text in _translation_cache:
        return _translation_cache[text]
    # For now, just return the original text. Replace with real translation API if needed.
    translated = f"[PT] {text}"
    _translation_cache[text] = translated
    return translated

from typing import Optional

from typing import Optional

_last_wikipedia_debug = []

async def fetch_wikipedia_summary(title: str, lang: str = "pt", city: Optional[str] = None, debug_logs: Optional[list] = None):
    """Fetch summary for a Wikipedia page title, always prefetch and translate the Portuguese summary. If city does not match, add a warning note."""
    import logging
    logs = debug_logs if debug_logs is not None else []
    def log(msg):
        logs.append(msg)
        logging.debug(msg)
    slug = re.sub(r"\s+", "_", title)
    city_check = (city or "").strip().lower() if city else None
    log(f"[WikipediaProvider] fetch_wikipedia_summary: title='{title}', lang='{lang}', city='{city}'")
    # Always prefetch the Portuguese summary and start translation
    pt_url = WIKI_API_URL.format(slug, lang=lang)
    pt_summary = None
    pt_translation_task = None
    async with aiohttp.ClientSession() as session:
        async with session.get(pt_url) as resp:
            if resp.status == 200:
                data = await resp.json()
                pt_summary = data.get("extract")
                log(f"[WikipediaProvider] PT summary: {pt_summary}")
                if pt_summary:
                    pt_translation_task = asyncio.create_task(translate_to_english(pt_summary))
    # Try to get English summary via QID
    qid = await get_wikidata_qid(title, lang)
    log(f"[WikipediaProvider] QID for '{title}': {qid}")
    if qid:
        en_title = await get_enwiki_title_from_qid(qid)
        log(f"[WikipediaProvider] EN title from QID: {en_title}")
        if en_title:
            en_url = WIKI_API_URL.format(en_title, lang="en")
            log(f"[WikipediaProvider] Fetching EN summary for: {en_title} url: {en_url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(en_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        en_summary = data.get("extract")
                        log(f"[WikipediaProvider] EN summary: {en_summary}")
                        if en_summary:
                            if city_check and city_check not in en_summary.lower():
                                note = f"[Note: The Wikipedia page for '{title}' does not mention '{city}'. Showing the summary anyway:]\n{en_summary}"
                                log(f"[WikipediaProvider] Returning EN summary with note: {note}")
                                return note
                            log(f"[WikipediaProvider] Returning EN summary: {en_summary}")
                            return en_summary
    # If no English summary, use the translated Portuguese summary if available
    if pt_translation_task:
        translated = await pt_translation_task
        log(f"[WikipediaProvider] Translated PT summary: {translated}")
        if city_check and translated and city_check not in translated.lower():
            note = f"[Note: The Wikipedia page for '{title}' does not mention '{city}'. Showing the summary anyway:]\n{translated}"
            log(f"[WikipediaProvider] Returning translated PT summary with note: {note}")
            return note
        log(f"[WikipediaProvider] Returning translated PT summary: {translated}")
        return translated
    elif pt_summary:
        translated = await translate_to_english(pt_summary)
        log(f"[WikipediaProvider] Translated PT summary (no task): {translated}")
        if city_check and translated and city_check not in translated.lower():
            note = f"[Note: The Wikipedia page for '{title}' does not mention '{city}'. Showing the summary anyway:]\n{translated}"
            log(f"[WikipediaProvider] Returning translated PT summary with note: {note}")
            return note
        log(f"[WikipediaProvider] Returning translated PT summary (no task): {translated}")
        return translated
    log(f"[WikipediaProvider] No summary found for '{title}'")
    return None

async def fetch_wikipedia_full(title: str, lang: str = "pt"):
    """Fetch full HTML and parse sections for a Wikipedia page title."""
    import logging
    slug = re.sub(r"\s+", "_", title)
    url = f"https://{lang}.wikipedia.org/wiki/{slug}"
    logging.debug(f"[WikipediaProvider] Fetching full page for slug: {slug} url: {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            logging.debug(f"[WikipediaProvider] Response status: {resp.status}")
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
                logging.debug(f"[WikipediaProvider] Sections found: {list(sections.keys())}")
                return sections
            return None

# Example usage:
# summary = await fetch_wikipedia_summary("Bairro dos Ingleses")
# full = await fetch_wikipedia_full("Bairro dos Ingleses")
