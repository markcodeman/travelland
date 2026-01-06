import requests
import os
import re
from typing import List, Dict

# SearX instances from environment or defaults
DEFAULT_INSTANCES = [
    'https://searx.prvcy.eu',
    'https://searx.info',
    'https://searx.divided-by-zero.eu',
    'https://notsearch.org',
    'https://drehtuer.pyrate.berlin',
    'https://search.mdosch.de',
    'https://searx.mha.fi',
    'https://searx.gnu.style',
]

def _get_instances():
    env = os.getenv('SEARX_INSTANCES')
    if env:
        return [u.strip() for u in env.split(',') if u.strip()]
    return DEFAULT_INSTANCES

def discover_restaurants(city: str, limit: int = 20, cuisine: str = None) -> List[Dict]:
    """Search for restaurants using SearX (aggregator of search engines)."""
    query = f"best {cuisine or 'restaurants'} in {city} local"
    instances = _get_instances()
    results = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }
    
    # Try more instances
    for instance in random_sample(instances, min(len(instances), 8)):
        try:
            print(f"Trying SearX instance: {instance}")
            url = f"{instance.rstrip('/')}/search"
            params = {
                'q': query,
                'format': 'json'
            }
            r = requests.get(url, params=params, headers=headers, timeout=15)
            if r.status_code != 200:
                print(f"Bailed: {r.status_code}")
                continue
            
            j = r.json()
            items = j.get('results', [])
            print(f"Instance returned {len(items)} items")
            for itm in items:
                title = itm.get('title', '')
                url_itm = itm.get('url', '')
                content = itm.get('content', '')
                
                # Try to extract a name-like string
                name = title.split('|')[0].split('-')[0].split('—')[0].strip()
                if len(name) < 2 or len(name) > 60:
                    continue
                
                results.append({
                    'name': name,
                    'address': f"Search result from {instance}",
                    'description': content[:200],
                    'website': url_itm,
                    'osm_url': url_itm,
                    'provider': 'searx',
                    'budget': 'cheap',
                    'price_range': '$',
                    'amenity': 'restaurant'
                })
                if len(results) >= limit:
                    break
            
            if results:
                break
        except Exception as e:
            print(f"Err on {instance}: {e}")
            continue
            
    return results

def random_sample(arr, n):
    import random
    if not arr: return []
    return random.sample(arr, min(arr.__len__(), n))
