import requests
import os
import re
import time
import random
from datetime import datetime
from urllib.parse import quote

try:
    import googlemaps
    GOOGLE_PLACES_AVAILABLE = True
except ImportError:
    GOOGLE_PLACES_AVAILABLE = False

OPENTRIPMAP_KEY = os.getenv('OPENTRIPMAP_KEY')
GOOGLE_PLACES_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')

# Initialize Google Maps client if available
gmaps_client = None
if GOOGLE_PLACES_AVAILABLE and GOOGLE_PLACES_API_KEY:
    try:
        gmaps_client = googlemaps.Client(key=GOOGLE_PLACES_API_KEY)
    except Exception:
        gmaps_client = None


def get_google_places_details(name, lat, lon, city):
    """Get venue details from Google Places API including price, rating, and reviews.
    
    Returns dict with keys: price_level, rating, user_ratings_total, price_range
    Returns None if API is unavailable or fails.
    """
    if not gmaps_client:
        return None
    
    try:
        # Search for the place by name and location
        query = f"{name}, {city}"
        places_result = gmaps_client.places(query=query, location=(lat, lon), radius=100)
        
        if not places_result.get('results'):
            return None
        
        # Get the first result (most relevant)
        place = places_result['results'][0]
        place_id = place.get('place_id')
        
        if not place_id:
            return None
        
        # Get detailed information including price level
        details = gmaps_client.place(place_id=place_id, fields=[
            'price_level', 'rating', 'user_ratings_total'
        ])
        
        if not details.get('result'):
            return None
        
        result = details['result']
        price_level = result.get('price_level')  # 0-4 scale
        rating = result.get('rating')  # 0-5 scale
        user_ratings_total = result.get('user_ratings_total', 0)
        
        # Map price_level to price range symbols
        price_range = '-'
        if price_level == 1:
            price_range = '$'
        elif price_level == 2:
            price_range = '$$'
        elif price_level == 3:
            price_range = '$$$'
        elif price_level == 4:
            price_range = '$$$$'
        
        return {
            'price_level': price_level,
            'rating': rating,
            'user_ratings_total': user_ratings_total,
            'price_range': price_range
        }
    except Exception as e:
        print(f"Error fetching Google Places details: {e}")
        return None


def map_price_level_to_budget(price_level):
    """Map Google Places price_level (1-4) to budget category.
    
    Price level 1 ($) → "cheap" (under $15)
    Price level 2 ($$) → "mid" ($15-30)
    Price level 3-4 ($$$/$$$) → "expensive" ($30+)
    """
    if price_level is None:
        return 'mid'  # Default to mid if unknown
    
    if price_level == 1:
        return 'cheap'
    elif price_level == 2:
        return 'mid'
    else:  # 3 or 4
        return 'expensive'


def get_restaurant_rating(name, city):
    """Get rating using Groq AI for restaurant recommendations."""
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    
    if not GROQ_API_KEY:
        return "Rating unavailable"
    
    prompt = f"What is the general customer rating (out of 5 stars) for {name} in {city}? Provide just the rating number, or 'Unknown' if not known."
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "mixtral-8x7b-32768", "messages": [{"role": "user", "content": prompt}], "max_tokens": 10}
        )
        if response.status_code == 200:
            rating = response.json()["choices"][0]["message"]["content"].strip()
            # Extract number
            match = re.search(r'(\d+\.?\d*)', rating)
            if match:
                return f"{match.group(1)}/5"
            return "Unknown"
        return "Rating unavailable"
    except Exception:
        return "Rating unavailable"

# Simple searxng-based search provider prototype
# Configure instances via SEARX_INSTANCES environment variable (comma-separated)
DEFAULT_INSTANCES = [
    # A broader default list of public searxng instances (may vary in availability)
    'https://searx.tiekoetter.com',
    'https://searx.org',
    'https://searx.be',
    'https://searx.space',
    'https://searx.eu',
    'https://searx.ng',
    'https://searx.fandom.com',
    'https://searx.science',
    'https://searx.sethforprivacy.com',
    'https://searx.fdf.org',
    'https://searx.disroot.org',
    'https://searx.kitsune.dev',
]

PRICE_RE = re.compile(r'(?:(?:\$|€|£|¥)\s?[0-9,]+(?:\.[0-9]+)?)|(?:[0-9,]+(?:\.[0-9]+)?\s?(?:USD|EUR|GBP|JPY))', re.IGNORECASE)

# Additional permissive numeric regex (captures numbers like '120/night', 'from 120', 'from $120')
NUM_RE = re.compile(r'(?:from\s*)?(?:\$|USD)?\s?([0-9]{1,3}(?:[0-9,]*)(?:\.[0-9]+)?)(?:\s*(?:/night|per night|a night|night))?', re.IGNORECASE)

def _get_instances_from_env():
    env = os.getenv('SEARX_INSTANCES')
    if not env:
        return DEFAULT_INSTANCES
    return [u.strip() for u in env.split(',') if u.strip()]

def _parse_price_from_text(text):
    if not text:
        return None, None
    # 1) Try exact currency symbol/code matches
    m = PRICE_RE.search(text)
    if m:
        s = m.group(0)
        # find amount and currency within the matched substring
        # e.g. '$120.50' or '120 USD'
        digits = re.search(r'([0-9,]+(?:\.[0-9]+)?)', s)
        code = re.search(r'(USD|EUR|GBP|JPY|\$|€|£|¥)', s, re.IGNORECASE)
        if digits:
            amt = float(digits.group(1).replace(',', ''))
            sym = code.group(0) if code else ''
            sym_map = {'$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY'}
            cur = sym_map.get(sym.upper(), sym.upper()) if sym else 'USD'
            # normalize codes like '$' -> USD
            if cur in ['$', '€', '£', '¥']:
                cur = sym_map.get(cur, 'USD')
            return amt, cur.upper()

    # 2) Try permissive numeric patterns (e.g., 'from 120', '120/night', 'per night 120 USD')
    m2 = NUM_RE.search(text)
    if m2:
        try:
            amt = float(m2.group(1).replace(',', ''))
            # attempt to pick currency code elsewhere in text
            code_search = re.search(r'(USD|EUR|GBP|JPY)', text, re.IGNORECASE)
            cur = code_search.group(1).upper() if code_search else 'USD'
            return amt, cur
        except Exception:
            return None, None

    # 3) fallback: look for reversed order like '120 USD'
    m3 = re.search(r'([0-9,]+(?:\.[0-9]+)?)\s?(USD|EUR|GBP|JPY)', text, re.IGNORECASE)
    if m3:
        amt = float(m3.group(1).replace(',', ''))
        cur = m3.group(2).upper()
        return amt, cur

    return None, None

def searx_search_hotels(city_code, check_in, check_out, adults=1, max_results=100):
    """Query multiple public searxng instances and return normalized hotel offers.

    This is a best-effort scraper of SERP snippets and is intended for prototyping only.
    """
    instances = _get_instances_from_env()
    query = f"hotel {city_code} checkin {check_in} checkout {check_out} adults {adults}"
    offers = []

    # compute nights
    try:
        nights = max(1, (datetime.strptime(check_out, '%Y-%m-%d') - datetime.strptime(check_in, '%Y-%m-%d')).days)
    except Exception:
        nights = 1

    seen = set()
    session = requests.Session()
    # Friendly headers to reduce blocks
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    }

    # Try a few query variants to surface price snippets from different sites
    query_variants = [
        query,
        query + ' price',
        f'hotel {city_code} price per night',
        query + ' booking.com',
        query + ' expedia',
    ]

    for inst in instances:
        try:
            url = inst.rstrip('/') + '/search'
            # try multiple query patterns per instance
            for q in query_variants:
                params = {'q': q, 'format': 'json'}
                # basic retry/backoff per-instance
                resp = None
                for attempt in range(3):
                    try:
                        resp = session.get(url, params=params, headers=headers, timeout=8)
                        if resp.status_code == 200:
                            break
                        if resp.status_code in (403, 429):
                            break
                    except requests.exceptions.RequestException:
                        time.sleep((2 ** attempt) + random.random())
                        continue
                if not resp or resp.status_code != 200:
                    # try next query variant
                    continue
                j = resp.json()
                results = j.get('results') or []
                # proceed to process results for this query
                for r in results:
                    title = r.get('title') or ''
                    link = r.get('url') or r.get('id') or ''
                    snippet = r.get('content') or r.get('snippet') or ''

                    key = (link or title).strip()
                    if not key or key in seen:
                        continue
                    seen.add(key)
            # basic retry/backoff per-instance
            resp = None
            for attempt in range(3):
                try:
                    resp = session.get(url, params=params, headers=headers, timeout=8)
                    if resp.status_code == 200:
                        break
                    # if rate limited or forbidden, break early for this instance
                    if resp.status_code in (403, 429):
                        break
                except requests.exceptions.RequestException:
                    # exponential backoff with jitter
                    time.sleep((2 ** attempt) + random.random())
                    continue
            if not resp or resp.status_code != 200:
                continue
                # if we got here, we already processed results for this successful query variant
                for r in results:
                    title = r.get('title') or ''
                    link = r.get('url') or r.get('id') or ''
                    snippet = r.get('content') or r.get('snippet') or ''

                    key = (link or title).strip()
                    if not key or key in seen:
                        continue
                    seen.add(key)

                    amt, cur = _parse_price_from_text(snippet + ' ' + title)

                    if amt is None:
                        # skip entries without a parsed price for now
                        continue

                    total_price = round(amt, 2)
                    hotelspec = {
                        'name': title or 'Hotel',
                        'hotel_id': None,
                        'base_price': round((total_price) / nights, 2),
                        'taxes': 0.0,
                        'total_price': total_price,
                        'nights': nights,
                        'total_per_night': round(total_price / nights, 2),
                        'currency': cur or 'USD',
                        'room_type': None,
                        'description': snippet or title,
                        'check_in': check_in,
                        'check_out': check_out,
                        'cancellation': 'Unknown',
                        'breakfast_included': False,
                        'source': link,
                        'provider': inst,
                    }
                    offers.append(hotelspec)
                    if len(offers) >= max_results:
                        break
        except Exception:
            continue
        if len(offers) >= max_results:
            break

    # sort cheapest first
    offers.sort(key=lambda x: x['total_price'])
    return {'hotels': offers, 'count': len(offers)}


def searx_raw_queries(city_code, check_in, check_out, adults=1, max_instances=5):
    """Return raw JSON responses from each searx instance for debugging."""
    instances = _get_instances_from_env()[:max_instances]
    query = f"hotel {city_code} checkin {check_in} checkout {check_out} adults {adults}"
    raw = []
    for inst in instances:
        try:
            url = inst.rstrip('/') + '/search'
            params = {'q': query, 'format': 'json'}
            resp = requests.get(url, params=params, timeout=8)
            entry = {
                'instance': inst,
                'status_code': resp.status_code,
                'json': None
            }
            try:
                entry['json'] = resp.json()
            except Exception:
                entry['json'] = None
            raw.append(entry)
        except Exception as e:
            raw.append({'instance': inst, 'status_code': None, 'error': str(e)})


def searx_search(query, max_results=10, city=None):
    """General search using public searxng instances, with Overpass for food queries."""
    if city and city.lower() not in query.lower():
        query = f"{query} in {city}"
    
    # For food-related queries, try Overpass first for real local data
    food_keywords = ['taco', 'pizza', 'burger', 'sushi', 'asian', 'italian', 'mexican', 'chinese', 'japanese', 'korean', 'restaurant', 'food', 'eat', 'crepe', 'crepes', 'bakery', 'pastry']
    cuisine = None
    query_lower = query.lower()
    if 'taco' in query_lower or 'mexican' in query_lower:
        cuisine = 'mexican'
    elif 'pizza' in query_lower or 'italian' in query_lower:
        cuisine = 'italian'
    elif 'sushi' in query_lower or 'japanese' in query_lower:
        cuisine = 'japanese'
    elif 'chinese' in query_lower:
        cuisine = 'chinese'
    elif 'korean' in query_lower:
        cuisine = 'korean'
    elif 'asian' in query_lower:
        cuisine = 'asian'
    elif 'burger' in query_lower:
        cuisine = 'american'
    elif 'french' in query_lower or 'crepe' in query_lower or 'crepes' in query_lower:
        cuisine = 'french'
    
    if any(kw in query_lower for kw in food_keywords) and city:
        try:
            import overpass_provider
            restaurants = overpass_provider.discover_restaurants(city, limit=max_results, cuisine=cuisine)
            results = []
            for r in restaurants:
                title = r['name']
                url = r['website'] or r['osm_url']
                address = r.get('address', '')
                lat = r.get('lat')
                lon = r.get('lon')
                
                # Try to get real data from Google Places API
                google_data = get_google_places_details(title, lat, lon, city)
                
                if google_data:
                    # Use Google Places data
                    cost = google_data['price_range']
                    rating = f"{google_data['rating']}/5 ({google_data['user_ratings_total']} reviews)" if google_data['rating'] else "Rating unavailable"
                else:
                    # Fallback to OSM data
                    cost = r.get('cost', '-')
                    rating = "Rating unavailable"
                
                maps_link = f"https://maps.google.com/maps?q={quote(r['name'] + ' ' + city)}&ll={r['lat']},{r['lon']}"
                snippet = f"{r['amenity']} - Address: {address} - Price: {cost} - Rating: {rating} - Google Maps: {maps_link} - {r['tags']}"
                results.append({
                    'title': title,
                    'url': url,
                    'snippet': snippet
                })
            if results:
                return results
        except Exception as e:
            print(f"Error in food search: {e}")
            pass  # Fall back to web search
    
    instances = _get_instances_from_env()[:5]  # try more instances
    results = []
    seen = set()
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    }

    # Try multiple query variations to improve results
    query_variants = [query]
    query_lower = query.lower()
    if 'taco' in query_lower:
        query_variants.extend([
            query.replace('taco', 'Mexican restaurant'),
            query.replace('best tacos', 'top Mexican restaurants'),
            'Mexican food ' + ' '.join(query.split()[2:]) if len(query.split()) > 2 else 'Mexican food ' + query.split()[-1]
        ])
    if 'pizza' in query_lower:
        query_variants.extend([
            query.replace('pizza', 'Italian restaurant'),
            query.replace('best pizza', 'top Italian restaurants'),
            'Italian food ' + ' '.join(query.split()[2:]) if len(query.split()) > 2 else 'Italian food ' + query.split()[-1]
        ])
    if 'burger' in query_lower:
        query_variants.extend([
            query.replace('burger', 'hamburger restaurant'),
            query.replace('best burgers', 'top burger places'),
            'burgers ' + ' '.join(query.split()[2:]) if len(query.split()) > 2 else 'burgers ' + query.split()[-1]
        ])
    if 'sushi' in query_lower:
        query_variants.extend([
            query.replace('sushi', 'Japanese restaurant'),
            query.replace('best sushi', 'top Japanese restaurants'),
            'Japanese food ' + ' '.join(query.split()[2:]) if len(query.split()) > 2 else 'Japanese food ' + query.split()[-1]
        ])
    # General variations
    if 'best' in query_lower and len(query.split()) > 2:
        location = ' '.join(query.split()[2:])
        food = query.split()[1]
        query_variants.extend([
            f'top {food} {location}',
            f'{food} restaurants {location}',
            f'best {food} places {location}'
        ])

    for q in query_variants:
        for inst in instances:
            try:
                url = inst.rstrip('/') + '/search'
                params = {'q': q, 'format': 'json'}
                resp = None
                for attempt in range(1):  # only 1 attempt for speed
                    try:
                        resp = session.get(url, params=params, headers=headers, timeout=5)  # shorter timeout
                        if resp.status_code == 200:
                            break
                        if resp.status_code in (403, 429):
                            break
                    except requests.exceptions.RequestException:
                        break
                if not resp or resp.status_code != 200:
                    continue
                j = resp.json()
                for r in j.get('results', []):
                    title = r.get('title', '')
                    link = r.get('url', '') or r.get('id', '')
                    snippet = r.get('content', '') or r.get('snippet', '')
                    key = (link or title).strip()
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    results.append({
                        'title': title,
                        'url': link,
                        'snippet': snippet
                    })
                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break
            except Exception:
                continue
        if len(results) >= max_results:
            break
    # If no results from SearXNG, try DuckDuckGo as fallback
    if not results:
        results = duckduckgo_search(query, max_results)
    # If still no results, try Google as last resort
    if not results:
        results = google_search(query, max_results)
    return results


def duckduckgo_search(query, max_results=10):
    """Fallback search using DuckDuckGo instant answers API."""
    try:
        url = 'https://api.duckduckgo.com/'
        params = {'q': query, 'format': 'json', 'no_html': 1, 'skip_disambig': 1}
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        seen = set()
        
        # Add instant answer if available
        if data.get('AbstractText'):
            title = data.get('Heading', 'Instant Answer')
            url = data.get('AbstractURL', '')
            snippet = data.get('AbstractText', '')
            if url and snippet:
                key = url
                if key not in seen:
                    seen.add(key)
                    results.append({
                        'title': title,
                        'url': url,
                        'snippet': snippet
                    })
        
        # Add related topics
        for topic in data.get('RelatedTopics', []):
            if isinstance(topic, dict):
                title = topic.get('Text', '').split(' - ')[0] if ' - ' in topic.get('Text', '') else topic.get('Text', '')
                url = topic.get('FirstURL', '')
                snippet = topic.get('Text', '')
                if url and title and snippet:
                    key = url
                    if key not in seen:
                        seen.add(key)
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': snippet
                        })
                        if len(results) >= max_results:
                            break
        
        return results[:max_results]
    except Exception:
        return []


def google_search(query, max_results=10):
    """Fallback search using Google (may violate TOS, use carefully)."""
    try:
        from googlesearch import search
        results = []
        seen = set()
        for url in search(query, num_results=max_results*2, lang='en'):
            if len(results) >= max_results:
                break
            if url in seen:
                continue
            seen.add(url)
            # Fetch title and snippet
            try:
                resp = requests.get(url, timeout=3, headers={'User-Agent': 'Mozilla/5.0'})
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    title = soup.title.string if soup.title else url
                    # Get meta description
                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                    snippet = meta_desc['content'] if meta_desc else ''
                    results.append({
                        'title': title[:100] if title else url,
                        'url': url,
                        'snippet': snippet[:200] if snippet else ''
                    })
            except Exception:
                # If can't fetch, just add URL
                results.append({
                    'title': url,
                    'url': url,
                    'snippet': ''
                })
        return results
    except Exception:
        return []
