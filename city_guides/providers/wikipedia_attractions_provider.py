"""Wikipedia Tourist Attractions Provider

Fetches tourist attractions from Wikipedia categories using the MediaWiki API.
Category pattern: "Category:Tourist attractions in {City}"

This provides high-quality, human-curated tourist attraction lists.
"""
import aiohttp
import asyncio
from typing import List, Dict, Optional
import logging

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"


async def discover_tourist_attractions(city: str, limit: int = 20, session: aiohttp.ClientSession = None) -> List[Dict]:
    """Discover tourist attractions via Wikipedia categories.
    
    Queries the "Tourist attractions in {city}" category and returns
    pages as attractions with geocoding for coordinates.
    
    Args:
        city: City name (e.g., "Bucharest", "Paris")
        limit: Maximum number of attractions to return
        session: Optional aiohttp session to use
        
    Returns:
        List of attraction dicts with name, lat, lon, description, source
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()
    
    try:
        # Try different category name variations
        category_variations = [
            f"Tourist attractions in {city}",
            f"Tourist attractions in {city.replace(' ', '_')}",
            f"Visitor attractions in {city}",
            f"Landmarks in {city}",
        ]
        
        all_pages = []
        for category in category_variations:
            pages = await _fetch_category_members(session, category, limit)
            all_pages.extend(pages)
            if len(all_pages) >= limit:
                break
        
        # Remove duplicates by title
        seen = set()
        unique_pages = []
        for page in all_pages:
            if page['title'] not in seen:
                seen.add(page['title'])
                unique_pages.append(page)
        
        # Convert to attraction format with geocoding
        attractions = []
        for page in unique_pages[:limit]:
            # Try to geocode the attraction
            lat, lon = await _geocode_attraction(session, page['title'], city)
            
            attractions.append({
                "name": page['title'],
                "address": f"{page['title']}, {city}",
                "lat": lat,
                "lon": lon,
                "place_id": f"wikipedia_{page['pageid']}",
                "tags": "wikipedia,tourism,attraction",
                "source": "wikipedia_category",
                "description": page.get('extract', ''),
            })
        
        # If no category pages found, try fallback methods
        if not all_pages:
            print(f"[WIKIPEDIA_ATTRACTIONS] No category pages found for {city}, trying fallback methods")
            all_pages = await _fallback_attraction_search(session, city, limit)
        
        print(f"[WIKIPEDIA_ATTRACTIONS] Found {len(attractions)} attractions for {city}")
        return attractions
        
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
    """Fetch page extract and info from Wikipedia."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|pageprops",
        "exintro": "1",
        "exsentences": "2",
        "explaintext": "1",
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
                if page_id == '-1':  # Page not found
                    continue
                return {
                    'title': page_data.get('title', title),
                    'pageid': page_id,
                    'extract': page_data.get('extract', ''),
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
