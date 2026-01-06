import time
from typing import List, Dict

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

def discover_restaurants(city: str, limit: int = 200, cuisine: str = None) -> List[Dict]:
    """Search for restaurants using DuckDuckGo (highly stable)."""
    cuisine_str = cuisine or 'local'
    # Expanded queries to maximize results
    queries = [
        f"{cuisine_str} restaurants in {city} local gems",
        f"best {cuisine_str} {city} independent eateries",
        f"{cuisine_str} joints {city} reviews",
        f"where to eat {cuisine_str} in {city}",
        f"independent burger joints {city} menus",
        f"local {cuisine_str} places {city} favorites",
        f"family owned {cuisine_str} {city}",
        f"locally owned {cuisine_str} {city}",
        f"small business {cuisine_str} {city}",
        f"authentic {cuisine_str} {city}",
        f"hole in the wall {cuisine_str} {city}",
        f"hidden gem {cuisine_str} {city}",
        f"{cuisine_str} diner {city}",
        f"{cuisine_str} grill {city} local",
        f"best kept secret {cuisine_str} {city}"
    ]
    results = []
    seen_urls = set()
    
    try:
        from overpass_provider import _singularize
    except ImportError:
        def _singularize(w): return w.rstrip('s')

    try:
        with DDGS() as ddgs:
            for query in queries:
                # Ask for a lot of results per query
                records = list(ddgs.text(query, max_results=100))
                
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
                        'zippia', 'wikipedia.org', 'weather', 'news', 'press'
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
                        'things to do', 'welcome to'
                    ]):
                        if len(name) > 50:
                            continue

                    # Keyword match for cuisine (very loose)
                    if cuisine:
                        search_txt = f"{name_low} {snippet.lower()}"
                        try:
                            c_sing = _singularize(cuisine)
                        except Exception:
                            c_sing = cuisine
                        
                        # Match if cuisine is mentioned OR if it's a general restaurant search
                        if cuisine.lower() not in search_txt and c_sing.lower() not in search_txt:
                            if 'restaurant' not in search_txt and 'food' not in search_txt:
                                continue
                        
                    results.append({
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
                
                if len(results) >= limit:
                    break
    except Exception as e:
        print(f"DuckDuckGo error: {e}")
        
    return results[:limit]
