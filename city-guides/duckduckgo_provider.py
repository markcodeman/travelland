import time
import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

CACHE_DIR = Path(__file__).parent / '.cache' / 'ddg'
CACHE_TTL = 60 * 60 * 24 # 24 hours

def _get_cache(query: str):
    h = hashlib.sha256(query.encode('utf-8')).hexdigest()
    p = CACHE_DIR / f"{h}.json"
    if p.exists():
        try:
            m = p.stat().st_mtime
            if time.time() - m < CACHE_TTL:
                with p.open('r') as f:
                    return json.load(f)
        except Exception:
            pass
    return None

def _set_cache(query: str, results):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256(query.encode('utf-8')).hexdigest()
        p = CACHE_DIR / f"{h}.json"
        with p.open('w') as f:
            json.dump(results, f)
    except Exception:
        pass

def discover_restaurants(city: str, limit: int = 200, cuisine: str = None) -> List[Dict]:
    """Search for restaurants using DuckDuckGo (highly stable with cache)."""
    cuisine_str = cuisine or 'local'
    # Medium queries list
    queries = [
        f"{cuisine_str} restaurants in {city} local gems",
        f"best {cuisine_str} {city} independent eateries",
        f"locally owned {cuisine_str} {city} authentic",
        f"hidden gem {cuisine_str} {city} reviews",
        f"hole in the wall {cuisine_str} {city}",
        f"family owned {cuisine_str} {city}"
    ]
    all_results = []
    seen_urls = set()
    
    try:
        from overpass_provider import _singularize
    except ImportError:
        def _singularize(w): return w.rstrip('s')

    for query in queries:
        # Try cache first
        cached = _get_cache(query)
        records = []
        if cached is not None:
            records = cached
        else:
            try:
                with DDGS() as ddgs:
                    records = list(ddgs.text(query, max_results=50))
                    _set_cache(query, records)
                    # Small sleep to avoid instant blocking if we do multiple misses
                    time.sleep(1)
            except Exception as e:
                print(f"DuckDuckGo error on query '{query}': {e}")
                continue
        
        for r in records:
            url = r.get('href', '')
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Loosened: Allow more sites, only skip the most obvious non-restaurant ones
            if any(x in url.lower() for x in [
                'tripadvisor', 'yelp.com', 'foursquare', 'timeout', 'eater', 
                'foodmapus', 'seamless', 'grubhub', 'ubereats', 'tiktok', 
                'youtube', 'pinterest', 'twitter', 'reddit', 'yellowpages', 
                'opentable', 'manta.com', 'glassdoor', 'indeed', 'linkedin', 
                'zippia', 'wikipedia.org', 'weather', 'news', 'press', 'zillow',
                'realtor.com', 'redfin', 'apartments.com', 'homes.com', 'trulia'
            ]):
                continue
            
            title = r.get('title', '')
            snippet = r.get('body', '')
            
            # Clean up name from title
            name = title.split('|')[0].split('-')[0].split('—')[0].split('·')[0].strip()
            if not name or len(name) < 2:
                continue
            
            # Loosened neighborhood/city check
            city_base = city.split(',')[0].strip().lower()
            context_text = (title + snippet + url).lower()
            if city_base not in context_text and 'virginia' not in context_text:
                continue
            
            name_low = name.lower()
            # Filters for titles that are clearly NOT venue names
            if any(x in name_low for x in [
                'best', 'top 10', 'top 5', 'top 20', 'guide', 'how to', 
                'where to', 'hidden gems', 'jobs', 'hiring', 'map of', 
                'things to do', 'welcome to', 'homes for sale', 'apartments',
                'real estate', 'for sale', 'houses for', 'condos', 'listings',
                'search result', 'weather', 'news', 'events', 'family fun',
                'tripadvisor', 'yelp', 'everything you need'
            ]):
                continue

            # Skip results where the name is just the city or state
            if name_low == city_base or name_low == 'virginia' or len(name) < 3:
                continue

            # Keyword match for cuisine (slightly tighter)
            if cuisine:
                search_txt = f"{name_low} {snippet.lower()}"
                try:
                    c_sing = _singularize(cuisine)
                except Exception:
                    c_sing = cuisine
                
                # Match if cuisine is mentioned OR if it's a very clear restaurant mention
                if cuisine.lower() not in search_txt and c_sing.lower() not in search_txt:
                    # If cuisine is specified, we really want to see it in the text.
                    # We only allow a bypass if the word "restaurant" is prominent AND it's a general search.
                    if 'restaurant' not in search_txt or len(cuisine) > 3: 
                        continue
                
            all_results.append({
                'name': name,
                'address': f"Found via Web Search",
                'description': snippet[:250],
                'website': url,
                'osm_url': url,
                'provider': 'web',
                'budget': 'cheap',
                'price_range': '$',
                'amenity': 'restaurant'
            })
            
            if len(all_results) >= limit:
                break

    return all_results[:limit]
