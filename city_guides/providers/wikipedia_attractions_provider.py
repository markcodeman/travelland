"""Wikipedia Tourist Attractions Provider

Fetches tourist attractions from Wikipedia categories using the MediaWiki API.
Category pattern: "Category:Tourist attractions in {City}"

This provides high-quality, human-curated tourist attraction lists.
"""
import aiohttp
import asyncio
from typing import List, Dict, Optional
import logging
from bs4 import BeautifulSoup
from urllib.parse import unquote

# local helper (uses our cached REST/action fallback)
from city_guides.providers.wikipedia_provider import async_fetch_wikipedia_section

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"


async def discover_tourist_attractions(city: str, limit: int = 20, session: aiohttp.ClientSession = None) -> List[Dict]:
    """Discover tourist attractions via Wikipedia.

    Priority order:
      1. Extract named attractions from the city's **Tourism** section (fast + curated)
      2. Wikipedia category "Tourist attractions in {city}"
      3. Fallback search (existing behavior)

    This reduces reliance on external geocoding by using MediaWiki `coordinates` when
    available, and keeps Nominatim as a last-resort fallback.
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    try:
        # create a larger candidate pool than the requested return limit
        candidate_fetch_limit = max(limit * 5, 50)
        candidates: List[Dict] = []

        # 1) Try to extract attractions from the city's Tourism section (human-curated list)
        try:
            html = await async_fetch_wikipedia_section(city, 'Tourism', lang='en')
            if html:
                titles = _extract_titles_from_section_html(html)
                BLACKLIST = {"Wayback Machine", "Internet Archive", "Archive.org"}
                # limit how many titles we attempt to resolve
                for t in titles[:candidate_fetch_limit]:
                    if t in BLACKLIST:
                        continue
                    page_info = await _fetch_page_extract(session, t)
                    # Heuristic filter: require a non-empty extract and some locality/tourism keywords
                    if not page_info or not page_info.get('extract'):
                        continue
                    extract_low = page_info['extract'].lower()
                    city_tok = city.split(',')[0].strip().lower()
                    keywords = ['museum', 'bridge', 'mosque', 'fortress', 'castle', 'tower', 'park', 'church', 'monument', 'old town', 'historic', 'ruin']
                    if city_tok not in extract_low and not any(k in extract_low for k in keywords) and not page_info.get('lat'):
                        # likely a non-local/reference page — skip
                        continue
                    candidates.append(page_info)
                    if len(candidates) >= candidate_fetch_limit:
                        break
        except Exception:
            # Non-fatal; fall back to category approach below
            pass

        # 2) If not enough candidates from section, fall back to category members
        if len(candidates) < limit:
            # Try different category name variations
            category_variations = [
                f"Tourist attractions in {city}",
                f"Tourist attractions in {city.replace(' ', '_')}",
                f"Visitor attractions in {city}",
                f"Landmarks in {city}",
            ]
            for category in category_variations:
                pages = await _fetch_category_members(session, category, candidate_fetch_limit)
                for p in pages:
                    if p['title'] not in {c['title'] for c in candidates}:
                        candidates.append(p)
                    if len(candidates) >= candidate_fetch_limit:
                        break

        # 3) Final fallback: search if still empty or to fill the candidate pool
        if len(candidates) < candidate_fetch_limit:
            more = await _fallback_attraction_search(session, city, candidate_fetch_limit)
            for p in more:
                if p['title'] not in {c['title'] for c in candidates}:
                    candidates.append(p)
                if len(candidates) >= candidate_fetch_limit:
                    break

        # Score and prioritize candidate pages so specific attractions come first
        def _score_page(p: Dict) -> int:
            s = 0
            title = (p.get('title') or '').lower()
            extract = (p.get('extract') or '').lower()
            city_tok = city.split(',')[0].strip().lower()

            # strong preference for items with coordinates
            if p.get('lat') is not None:
                s += 300
            # strong boost when the extract explicitly mentions the city
            if city_tok and city_tok in extract:
                s += 150
            # keywords indicative of attractions (big boost)
            for kw, val in [('bridge', 220), ('museum', 180), ('church', 120), ('monument', 120), ('waterfall', 160), ('tower', 140), ('fortress', 140), ('castle', 140), ('old town', 160)]:
                if kw in extract or kw in title:
                    s += val
            # aggressive penalization for list/overview/regional pages
            if title.startswith('list of') or 'list of' in title or title.startswith('tourism in') or title.startswith('economy of') or 'canton' in title:
                s -= 500
            # penalize very short extracts (likely disambiguation or stub)
            if len(extract) < 50:
                s -= 50
            # slight boost for longer, focused pages
            if len(extract) > 120:
                s += 10
            return s

        candidates_sorted = sorted(candidates, key=_score_page, reverse=True)

        # Normalize candidates to attraction POI format, prefer MediaWiki coordinates when present
        attractions = []
        seen_titles = set()
        for page in candidates_sorted[: max(limit * 3, 50)]:
            title = page.get('title')
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            # Enrich page data with coordinates/thumbnail if missing
            lat = page.get('lat')
            lon = page.get('lon')
            thumb = page.get('thumbnail')
            if (lat is None or lon is None or not thumb) and title:
                extra = await _fetch_page_extract(session, title)
                if extra:
                    lat = lat or extra.get('lat')
                    lon = lon or extra.get('lon')
                    thumb = thumb or extra.get('thumbnail')
                    # prefer existing extract but fill if missing
                    if not page.get('extract') and extra.get('extract'):
                        page['extract'] = extra.get('extract')

            # If coordinates still missing, try Nominatim geocode (last resort)
            if lat is None or lon is None:
                lat, lon = await _geocode_attraction(session, title, city)

            # Determine tags based on content analysis
            tags = ["wikipedia", "tourism", "attraction"]
            extract = page.get('extract', '').lower()
            title_lower = title.lower()
            
            # Historic sites
            historic_keywords = ['historic', 'monument', 'castle', 'fort', 'palace', 'heritage', 
                               'archaeological', 'ruins', 'temple', 'church', 'cathedral', 'abbey',
                               'landmark', 'memorial', 'statue', 'fountain', 'bridge', 'tower',
                               'museum', 'old town']
            if any(kw in extract or kw in title_lower for kw in historic_keywords):
                tags.append("historic")
            
            # Museums
            if 'museum' in extract or 'museum' in title_lower:
                tags.append("museum")
            
            # Parks and nature
            if any(kw in extract for kw in ['park', 'garden', 'nature', 'forest', 'mountain']):
                tags.append("park")
            
            # Religious sites
            if any(kw in extract or kw in title_lower for kw in ['church', 'temple', 'mosque', 'cathedral', 'abbey', 'synagogue']):
                tags.append("religious")
            
            # Entertainment
            if any(kw in extract for kw in ['theater', 'cinema', 'concert', 'performance', 'entertainment']):
                tags.append("entertainment")

            attractions.append({
                "name": title,
                "address": f"{title}, {city}",
                "lat": lat,
                "lon": lon,
                "place_id": f"wikipedia_{page.get('pageid')}",
                "tags": ",".join(tags),
                "source": "wikipedia",
                "description": page.get('extract', ''),
                "thumbnail": thumb
            })

            if len(attractions) >= limit:
                break

        return attractions[:limit]

    except Exception as e:
        logging.warning(f"Wikipedia attractions provider failed: {e}")
        return []
    finally:
        if own_session:
            await session.close()


async def _fallback_attraction_search(session: aiohttp.ClientSession, city: str, limit: int = 10) -> List[Dict]:
    """Fallback method for cities without Wikipedia attraction categories.

    Tries to find attractions by searching for pages related to the city and tourism.
    """
    try:
        # Search for pages containing the city name and tourism-related terms
        search_terms = [
            f'"{city}" tourism',
            f'"{city}" attractions', 
            f'"{city}" landmarks',
            f'"{city}" sites'
        ]
        
        all_results = []
        for term in search_terms:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": term,
                "srlimit": str(min(limit, 20)),
                "format": "json",
                "origin": "*",
            }
            
            headers = {
                "User-Agent": "TravelLand/1.0 (https://travelland.app; contact@travelland.app)"
            }
            
            async with session.get(WIKIPEDIA_API_URL, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("query", {}).get("search", [])
                    
                    # Convert search results to page format similar to category members
                    for result in results:
                        # Skip if it's the main city page itself
                        if result['title'].lower() == city.lower():
                            continue
                            
                        all_results.append({
                            'title': result['title'],
                            'pageid': result['pageid'],
                            'extract': result.get('snippet', '').replace('<span class="searchmatch">', '').replace('</span>', ''),
                        })
        
        # Remove duplicates
        seen_titles = set()
        unique_results = []
        for result in all_results:
            if result['title'] not in seen_titles:
                seen_titles.add(result['title'])
                unique_results.append(result)
        
        print(f"[WIKIPEDIA_FALLBACK] Found {len(unique_results)} potential attractions for {city}")
        return unique_results[:limit]
        
    except Exception as e:
        print(f"[WIKIPEDIA_FALLBACK] Fallback search failed: {e}")
        return []


# ---- Helper: extract linked page titles from a rendered Wikipedia section HTML ----

def _extract_titles_from_section_html(html: str) -> List[str]:
    """Parse rendered section HTML and return a list of internal page titles.

    Strategy:
      - Prefer anchors in lists (<ul>/<ol>) directly under the section
      - Fall back to anchors inside paragraphs
      - Normalize '/wiki/...' href to page title
    """
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
        titles = []

        # 1) Anchors inside lists first
        for ul in soup.find_all(['ul', 'ol']):
            for a in ul.find_all('a', href=True):
                href = a['href']
                title = None
                if href.startswith('/wiki/') and not href.startswith('/wiki/File:'):
                    title = unquote(href.split('/wiki/')[1])
                elif href.startswith('https://en.wikipedia.org/wiki/') and not 'File:' in href:
                    title = unquote(href.split('https://en.wikipedia.org/wiki/')[1])
                if title:
                    title = title.replace('_', ' ')
                    if title not in titles:
                        titles.append(title)
            if len(titles) >= 50:
                break

        # 2) If none found, fall back to paragraph anchors
        if not titles:
            for p in soup.find_all('p'):
                for a in p.find_all('a', href=True):
                    href = a['href']
                    title = None
                    if href.startswith('/wiki/') and not href.startswith('/wiki/File:'):
                        title = unquote(href.split('/wiki/')[1])
                    elif href.startswith('https://en.wikipedia.org/wiki/') and not 'File:' in href:
                        title = unquote(href.split('https://en.wikipedia.org/wiki/')[1])
                    if title:
                        title = title.replace('_', ' ')
                        if title not in titles:
                            titles.append(title)
                if len(titles) >= 50:
                    break

        return titles
    except Exception:
        return []


async def _fetch_category_members(session: aiohttp.ClientSession, category: str, limit: int = 50) -> List[Dict]:
    """Fetch pages from a Wikipedia category."""
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmlimit": str(min(limit, 50)),
        "format": "json",
        "origin": "*",
    }
    
    headers = {
        "User-Agent": "TravelLand/1.0 (https://travelland.app; contact@travelland.app)"
    }
    
    try:
        async with session.get(WIKIPEDIA_API_URL, params=params, headers=headers, timeout=10) as response:
            if response.status != 200:
                print(f"[WIKIPEDIA_ATTRACTIONS] HTTP {response.status} for category {category}")
                return []
            
            data = await response.json()
            members = data.get('query', {}).get('categorymembers', [])
            
            # Fetch extracts for each page
            pages = []
            for member in members:
                if member.get('ns') == 0:  # Main namespace only
                    page_info = await _fetch_page_extract(session, member['title'])
                    if page_info:
                        pages.append(page_info)
            
            return pages
            
    except Exception as e:
        print(f"[WIKIPEDIA_ATTRACTIONS] Error fetching category {category}: {e}")
        return []


async def _fetch_page_extract(session: aiohttp.ClientSession, title: str) -> Optional[Dict]:
    """Fetch page extract, coordinates and thumbnail from Wikipedia (single call).

    Returns dict with keys: title, pageid, extract, lat, lon, thumbnail
    """
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|pageprops|coordinates|pageimages",
        "exintro": "1",
        "exsentences": "2",
        "explaintext": "1",
        "piprop": "thumbnail",
        "pithumbsize": "400",
        "format": "json",
        "origin": "*",
    }

    headers = {
        "User-Agent": "TravelLand/1.0 (https://travelland.app; contact@travelland.app)"
    }

    try:
        async with session.get(WIKIPEDIA_API_URL, params=params, headers=headers, timeout=10) as response:
            if response.status != 200:
                return None

            data = await response.json()
            pages = data.get('query', {}).get('pages', {})

            for page_id, page_data in pages.items():
                if page_id == '-1':
                    continue
                coords = page_data.get('coordinates')
                lat = lon = None
                if coords and isinstance(coords, list) and len(coords) > 0:
                    lat = float(coords[0].get('lat'))
                    lon = float(coords[0].get('lon'))

                thumb = None
                thumbnail_info = page_data.get('thumbnail') or {}
                if thumbnail_info:
                    thumb = thumbnail_info.get('source')

                return {
                    'title': page_data.get('title', title),
                    'pageid': page_id,
                    'extract': page_data.get('extract', ''),
                    'lat': lat,
                    'lon': lon,
                    'thumbnail': thumb,
                }

            return None

    except Exception as e:
        print(f"[WIKIPEDIA_ATTRACTIONS] Error fetching page {title}: {e}")
        return None


async def _geocode_attraction(session: aiohttp.ClientSession, attraction_name: str, city: str) -> tuple:
    """Simple geocoding using Nominatim for Wikipedia attractions."""
    try:
        query = f"{attraction_name}, {city}"
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
        }
        headers = {
            "User-Agent": "TravelLand/1.0 (tourist attractions geocoding)"
        }
        
        async with session.get(url, params=params, headers=headers, timeout=10) as response:
            if response.status != 200:
                return None, None
            
            # Handle brotli encoding that Nominatim sometimes returns
            response_text = await response.text()
            try:
                import json
                data = json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback: try to decode as UTF-8 if JSON parsing fails
                try:
                    data = json.loads(response_text.encode('latin1').decode('utf-8'))
                except:
                    print(f"[WIKIPEDIA_ATTRACTIONS] Failed to decode Nominatim response")
                    return None, None
            if data and len(data) > 0:
                return float(data[0]['lat']), float(data[0]['lon'])
            
            return None, None
            
    except Exception as e:
        print(f"[WIKIPEDIA_ATTRACTIONS] Geocoding error for {attraction_name}: {e}")
        return None, None
