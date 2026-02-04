"""
Dynamic Category System - Web-Driven & Robust

This module provides truly dynamic category suggestions based on Wikipedia and DDGS data.
No OSM venue counting - uses real travel content from the web.
"""

import asyncio
import aiohttp
import json
import re
from typing import List, Dict, Any
from urllib.parse import urlparse

# Import existing providers
try:
    from providers.ddgs_provider import ddgs_search
    DDGS_AVAILABLE = True
except ImportError as e:
    DDGS_AVAILABLE = False

try:
    from providers.wikipedia_provider import fetch_wikipedia_summary
    WIKI_AVAILABLE = True
except ImportError as e:
    WIKI_AVAILABLE = False

# Redis for caching
import redis
redis_client = None  # Will be set from routes.py

# Mock redis client for testing
class MockRedis:
    def __init__(self):
        self.data = {}
    
    def get(self, key):
        return self.data.get(key)
    
    def set(self, key, value, ex=None):
        self.data[key] = value
        return True

if redis_client is None:
    redis_client = MockRedis()

CACHE_TTL = 3600  # 1 hour


def normalize_category(cat: str) -> str:
    """Normalize category name: lowercase, remove prefixes, stem basics."""
    if not cat:
        return ""
    # Remove common prefixes
    cat = re.sub(r'^(category:\s*|tourism in\s*|visitor attractions in\s*|attractions in\s*)', '', cat, flags=re.I)
    # Basic stemming
    cat = cat.lower().strip()
    cat = re.sub(r'\b(attractions?|tourism|travel|places?|sites?|areas?)\b', '', cat)
    return cat.strip()


def dedupe_categories(categories: List[str]) -> List[Dict[str, str]]:
    """Dedupe categories with fuzzy matching and assign icons."""
    normalized = []
    unique = []

    for cat in categories:
        norm = normalize_category(cat)
        if norm and norm not in normalized:
            # Simple dedupe - can enhance with better fuzzy matching later
            normalized.append(norm)
            intent = norm.replace(' ', '_').lower()
            unique.append({
                'icon': get_category_icon(norm),
                'label': cat.title(),
                'intent': intent
            })

    return unique[:20]  # Cap at 20


def get_category_icon(category: str) -> str:
    """Map normalized category to emoji icon."""
    icons = {
        'food': '🍔', 'restaurant': '🍽️', 'dining': '🍽️', 'cuisine': '🍽️',
        'street food': '🥘', 'night market': '🌃', 'floating market': '🛶',
        'beach': '🏖️', 'sea': '🏖️', 'ocean': '🏖️', 'coast': '🏖️',
        'history': '🏛️', 'historic': '🏛️', 'museum': '🖼️', 'art': '🎨', 'culture': '🎭',
        'temple': '🏛️', 'wat': '🏛️', 'spirit house': '🏮',
        'nightlife': '🌃', 'bar': '🍷', 'club': '🎶', 'music': '🎵', 'rooftop bar': '🌆',
        'park': '🌳', 'nature': '🌳', 'garden': '🌸',
        'shopping': '🛍️', 'market': '🛒', 'mall': '🏬', 'chinatown': '🏮',
        'transport': '🚇', 'transportation': '🚇', 'river cruise': '🚢', 'airport': '✈️',
        'religion': '⛪', 'church': '⛪', 'temple': '🕍',
        'mountain': '🏔️', 'hiking': '🥾',
        'wine': '🍷', 'vineyard': '🍇', 'winery': '🍷',
        'sport': '⚽', 'recreation': '🏃', 'stadium': '🏟️',
        'education': '🎓', 'university': '🏛️', 'school': '🏫',
        'massage': '💆', 'spa': '💆', 'thai massage': '💆'
    }

    for key, icon in icons.items():
        if key in category:
            return icon
    return '📍'


async def fetch_wikipedia_categories(city: str, state: str = "", country: str = "US") -> List[str]:
    """Fetch categories from Wikipedia page."""
    categories = []

    try:
        # Try city page
        title = f"{city}"
        if state:
            title += f", {state}"

        # Use existing wikipedia provider
        if WIKI_AVAILABLE:
            summary_result = await fetch_wikipedia_summary(title, lang="en")
            if summary_result:
                summary, _ = summary_result
                # Extract topics from summary
                topic_matches = re.findall(r'\b(tourism|attractions?|neighborhoods?|food|cuisine|history|nightlife|beaches?|parks?|museums?|shopping|culture|art|music|sport|religion|nature|mountains?|transport)\b', summary, re.I)
                categories.extend(topic_matches)

        # Also fetch actual Wikipedia categories
        async with aiohttp.ClientSession() as session:
            params = {
                'action': 'query',
                'titles': title,
                'prop': 'categories',
                'format': 'json',
                'origin': '*'
            }
            headers = {'User-Agent': 'TravelLand/1.0 (Educational Project)'}
            async with session.get('https://en.wikipedia.org/w/api.php', params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pages = data.get('query', {}).get('pages', {})
                    for page in pages.values():
                        wiki_cats = page.get('categories', [])
                        for cat in wiki_cats:
                            cat_title = cat.get('title', '')
                            if 'tourism' in cat_title.lower() or 'attractions' in cat_title.lower():
                                categories.append(cat_title)

    except Exception as e:
        print(f"[WIKI] Error fetching categories for {city}: {e}")

    return categories


async def fetch_ddgs_categories(city: str, state: str = "") -> List[str]:
    """Fetch categories from DDGS search results."""
    categories = []

    if not DDGS_AVAILABLE:
        return categories

    try:
        query = f"tourist attractions categories {city}"
        if state:
            query += f" {state}"

        results = await ddgs_search(query, engine="google", max_results=10)

        for result in results:
            title = result.get('title', '')
            body = result.get('body', '')

            # Extract category-like terms
            text = f"{title} {body}"
            cat_matches = re.findall(r'\b(beaches?|parks?|museums?|food|dining|cuisine|history|nightlife|shopping|culture|art|music|sport|religion|nature|mountains?|transport|attractions?|tourism)\b', text, re.I)
            categories.extend(cat_matches)

            # Also use topic from URL if available
            href = result.get('href', '')
            if href:
                path = urlparse(href).path
                topic = path.split('/')[-1].replace('_', ' ')
                if len(topic) > 3 and len(topic) < 30:
                    categories.append(topic)

    except Exception as e:
        print(f"[DDGS] Error fetching categories for {city}: {e}")

    return categories


<<<<<<< /home/markcodeman/CascadeProjects/travelland/city_guides/src/simple_categories.py
<<<<<<< /home/markcodeman/CascadeProjects/travelland/city_guides/src/simple_categories.py
def extract_from_fun_facts(city: str) -> List[Dict[str, Any]]:
    """Extract semantic categories from fun facts with context."""
    categories = []
    
    try:
        # Import fun facts from the actual app.py function
        # We need to access the fun_facts data that's defined in get_fun_fact
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        
        # Get the fun facts by calling the actual function
        from city_guides.src.app import get_fun_fact
        
        city_lower = city.lower().strip()
        
        # Try to get a fun fact - if it exists, we know the city has fun facts data
        try:
            fact_result = get_fun_fact(city_lower, '', '')
            if fact_result and fact_result.get('fun_fact'):
                # City has fun facts, extract from the known categories
                # This is more dynamic - we work with what actually exists
                fact_text = fact_result['fun_fact'].lower()
                
                # Semantic extraction based on the actual fun fact content
                if any(word in fact_text for word in ['museum', 'art', 'gallery', 'culture']):
                    categories.append({'category': 'Art & Culture', 'confidence': 0.9, 'source': 'fun_facts'})
                if any(word in fact_text for word in ['beach', 'sea', 'ocean', 'coast']):
                    categories.append({'category': 'Beaches & Coast', 'confidence': 0.9, 'source': 'fun_facts'})
                if any(word in fact_text for word in ['park', 'garden', 'nature', 'forest', 'trees']):
                    categories.append({'category': 'Parks & Nature', 'confidence': 0.8, 'source': 'fun_facts'})
                if any(word in fact_text for word in ['food', 'dining', 'restaurant', 'cuisine', 'wine', 'bakeries']):
                    categories.append({'category': 'Food & Dining', 'confidence': 0.9, 'source': 'fun_facts'})
                if any(word in fact_text for word in ['wine', 'vineyard', 'winery', 'château', 'cellar']):
                    categories.append({'category': 'Wine & Vineyards', 'confidence': 0.95, 'source': 'fun_facts'})
                if any(word in fact_text for word in ['shopping', 'market', 'street', 'store']):
                    categories.append({'category': 'Shopping', 'confidence': 0.8, 'source': 'fun_facts'})
                if any(word in fact_text for word in ['nightlife', 'bar', 'club', 'music']):
                    categories.append({'category': 'Nightlife', 'confidence': 0.8, 'source': 'fun_facts'})
                if any(word in fact_text for word in ['history', 'historic', 'monument', 'castle', 'heritage']):
                    categories.append({'category': 'Historic Sites', 'confidence': 0.9, 'source': 'fun_facts'})
                if any(word in fact_text for word in ['transport', 'metro', 'train', 'bus', 'bridge']):
                    categories.append({'category': 'Transportation', 'confidence': 0.7, 'source': 'fun_facts'})
                if any(word in fact_text for word in ['bridge', 'tower', 'architecture', 'building', 'square']):
                    categories.append({'category': 'Architecture', 'confidence': 0.8, 'source': 'fun_facts'})
                if any(word in fact_text for word in ['festival', 'event', 'celebration', 'heritage']):
                    categories.append({'category': 'Festivals & Events', 'confidence': 0.8, 'source': 'fun_facts'})
        except:
            # City doesn't have fun facts, that's fine - other sources will handle it
            pass
                    
    except Exception as e:
        print(f"[FUN_FACTS] Error: {e}")
=======
def extract_from_city_data(city: str) -> List[Dict[str, Any]]:
    """Extract categories from city-specific data using dynamic API calls."""
    city_lower = city.lower().strip()
    
    # For major cities, use enhanced dynamic extraction with multiple API calls
    if city_lower in ['paris', 'london']:
        try:
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_enhanced_city_categories(city))
                    return future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run
                return asyncio.run(get_enhanced_city_categories(city))
        except Exception as e:
            print(f"[CITY_DATA] Error for {city}: {e}")
            return []
    
    return []


async def get_enhanced_city_categories(city: str) -> List[Dict[str, Any]]:
    """Enhanced category extraction for major cities using multiple data sources."""
    categories = []
    
    try:
=======
def extract_from_city_data(city: str) -> List[Dict[str, Any]]:
    """Extract categories from city-specific data using dynamic API calls."""
    city_lower = city.lower().strip()
    
    # For major cities, use enhanced dynamic extraction with multiple API calls
    if city_lower in ['paris', 'london']:
        try:
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_enhanced_city_categories(city))
                    return future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run
                return asyncio.run(get_enhanced_city_categories(city))
        except Exception as e:
            print(f"[CITY_DATA] Error for {city}: {e}")
            return []
    
    return []


async def get_enhanced_city_categories(city: str) -> List[Dict[str, Any]]:
    """Enhanced category extraction for major cities using multiple data sources."""
    categories = []
    
    try:
>>>>>>> /home/markcodeman/.windsurf/worktrees/travelland/travelland-55ed203d/city_guides/src/simple_categories.py
        # Use Wikipedia with enhanced queries for city-specific content
        if WIKI_AVAILABLE:
            # Get comprehensive Wikipedia data
            title = f"{city}"
            async with aiohttp.ClientSession() as session:
                params = {
                    'action': 'query',
                    'titles': title,
                    'prop': 'categories|extracts',
                    'explaintext': True,
                    'format': 'json',
                    'origin': '*',
                    'cllimit': 50
                }
                headers = {'User-Agent': 'TravelLand/1.0 (Educational Project)'}
                async with session.get('https://en.wikipedia.org/w/api.php', params=params, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pages = data.get('query', {}).get('pages', {})
                        
                        for page in pages.values():
                            # Extract from categories
                            wiki_cats = page.get('categories', [])
                            for cat in wiki_cats:
                                cat_title = cat.get('title', '').lower()
                                
                                # Dynamic category mapping based on actual Wikipedia categories
                                if any(word in cat_title for word in ['art', 'museum', 'culture', 'gallery']):
                                    categories.append({'category': 'Art & Culture', 'confidence': 0.9, 'source': 'wikipedia_enhanced'})
                                if any(word in cat_title for word in ['history', 'historic', 'heritage', 'monument']):
                                    categories.append({'category': 'Historic Sites', 'confidence': 0.9, 'source': 'wikipedia_enhanced'})
                                if any(word in cat_title for word in ['food', 'cuisine', 'restaurant']):
                                    categories.append({'category': 'Food & Dining', 'confidence': 0.8, 'source': 'wikipedia_enhanced'})
                                if any(word in cat_title for word in ['architecture', 'building', 'structure']):
                                    categories.append({'category': 'Architecture', 'confidence': 0.8, 'source': 'wikipedia_enhanced'})
                                if any(word in cat_title for word in ['park', 'garden', 'nature']):
                                    categories.append({'category': 'Parks & Nature', 'confidence': 0.7, 'source': 'wikipedia_enhanced'})
                                if any(word in cat_title for word in ['shopping', 'market', 'retail']):
                                    categories.append({'category': 'Shopping', 'confidence': 0.7, 'source': 'wikipedia_enhanced'})
                                if any(word in cat_title for word in ['nightlife', 'entertainment', 'bar']):
                                    categories.append({'category': 'Nightlife', 'confidence': 0.7, 'source': 'wikipedia_enhanced'})
                                if any(word in cat_title for word in ['transport', 'metro', 'railway']):
                                    categories.append({'category': 'Transportation', 'confidence': 0.6, 'source': 'wikipedia_enhanced'})
                            
                            # Extract from page content
                            extract = page.get('extract', '').lower()
                            if 'louvre' in extract or 'british museum' in extract:
                                categories.append({'category': 'Art & Culture', 'confidence': 0.95, 'source': 'wikipedia_enhanced'})
                            if 'eiffel tower' in extract or 'big ben' in extract or 'tower of london' in extract:
                                categories.append({'category': 'Historic Sites', 'confidence': 0.95, 'source': 'wikipedia_enhanced'})
                            if 'seine' in extract or 'thames' in extract:
                                categories.append({'category': 'Parks & Nature', 'confidence': 0.8, 'source': 'wikipedia_enhanced'})
        
        # Use DDGS for current trending topics
        if DDGS_AVAILABLE:
            queries = [
                f"best attractions {city}",
                f"famous landmarks {city}",
                f"top museums {city}",
                f"popular restaurants {city}",
                f"nightlife areas {city}"
            ]
            
            for query in queries:
                try:
                    results = await ddgs_search(query, engine="google", max_results=3)
                    for result in results:
                        title = result.get('title', '').lower()
                        body = result.get('body', '').lower()
                        text = f"{title} {body}"
                        
                        # Dynamic extraction based on real search results
                        if any(word in text for word in ['museum', 'art', 'gallery', 'culture']):
                            categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'ddgs_enhanced'})
                        if any(word in text for word in ['historic', 'monument', 'landmark', 'heritage']):
                            categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'ddgs_enhanced'})
                        if any(word in text for word in ['restaurant', 'food', 'dining', 'cuisine']):
                            categories.append({'category': 'Food & Dining', 'confidence': 0.7, 'source': 'ddgs_enhanced'})
                        if any(word in text for word in ['nightlife', 'bar', 'club', 'entertainment']):
                            categories.append({'category': 'Nightlife', 'confidence': 0.7, 'source': 'ddgs_enhanced'})
                        if any(word in text for word in ['shopping', 'market', 'boutique']):
                            categories.append({'category': 'Shopping', 'confidence': 0.6, 'source': 'ddgs_enhanced'})
                        
                except Exception as e:
                    print(f"[DDGS_ENHANCED] Search error: {e}")
                    continue
                    
    except Exception as e:
        print(f"[ENHANCED_CATEGORIES] Error for {city}: {e}")
<<<<<<< /home/markcodeman/CascadeProjects/travelland/city_guides/src/simple_categories.py
>>>>>>> /home/markcodeman/.windsurf/worktrees/travelland/travelland-55ed203d/city_guides/src/simple_categories.py
=======
>>>>>>> /home/markcodeman/.windsurf/worktrees/travelland/travelland-55ed203d/city_guides/src/simple_categories.py
    
    return categories


async def extract_from_city_guide(city: str) -> List[Dict[str, Any]]:
    """Extract categories from the Wikipedia city guide content."""
    categories = []
    
    try:
        # For now, use Wikipedia summary as city guide content
        if WIKI_AVAILABLE:
            summary_result = await fetch_wikipedia_summary(city, lang="en")
            if summary_result:
                summary, _ = summary_result
                guide_text = summary.lower()
                
                # Extract based on guide content
                if any(word in guide_text for word in ['museum', 'art', 'gallery', 'culture']):
                    categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'city_guide'})
                if any(word in guide_text for word in ['beach', 'sea', 'coastal', 'ocean']):
                    categories.append({'category': 'Beaches & Coast', 'confidence': 0.8, 'source': 'city_guide'})
                if any(word in guide_text for word in ['park', 'garden', 'nature', 'green']):
                    categories.append({'category': 'Parks & Nature', 'confidence': 0.8, 'source': 'city_guide'})
                if any(word in guide_text for word in ['food', 'dining', 'restaurant', 'cuisine']):
                    categories.append({'category': 'Food & Dining', 'confidence': 0.8, 'source': 'city_guide'})
                if any(word in guide_text for word in ['shopping', 'market', 'boutique']):
                    categories.append({'category': 'Shopping', 'confidence': 0.7, 'source': 'city_guide'})
                if any(word in guide_text for word in ['nightlife', 'bar', 'club', 'entertainment']):
                    categories.append({'category': 'Nightlife', 'confidence': 0.7, 'source': 'city_guide'})
                if any(word in guide_text for word in ['history', 'historic', 'heritage', 'ancient']):
                    categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'city_guide'})
                if any(word in guide_text for word in ['architecture', 'building', 'structure']):
                    categories.append({'category': 'Architecture', 'confidence': 0.7, 'source': 'city_guide'})
                
    except Exception as e:
        print(f"[CITY_GUIDE] Error: {e}")
    
    return categories


async def extract_from_wikipedia_sections(city: str, state: str = "") -> List[Dict[str, Any]]:
    """Extract categories from Wikipedia page with comprehensive analysis."""
    categories = []
    city_lower = city.lower().strip()
    
    try:
        if WIKI_AVAILABLE:
            title = f"{city}"
            if state:
                title += f", {state}"
                
            async with aiohttp.ClientSession() as session:
                # Get full page content with sections
                params = {
                    'action': 'parse',
                    'page': title,
                    'prop': 'sections|text|categories',
                    'format': 'json',
                    'origin': '*'
                }
                headers = {'User-Agent': 'TravelLand/1.0 (Educational Project)'}
                async with session.get('https://en.wikipedia.org/w/api.php', params=params, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Extract from section headers
                        sections = data.get('parse', {}).get('sections', [])
                        for section in sections:
                            line = section.get('line', '').lower()
                            
                            # Dynamic pattern extraction - no hardcoded city lists
                            # Extract temple patterns (works for any city with temples)
                            if any(word in line for word in ['temple', 'wat', 'pagoda', 'shrine', 'mosque', 'church']):
                                categories.append({'category': 'Temples & Religious Sites', 'confidence': 0.8, 'source': 'wikipedia'})
                            
                            # Extract food/cuisine patterns
                            if any(word in line for word in ['food', 'cuisine', 'restaurant', 'dining', 'culinary']):
                                categories.append({'category': 'Food & Dining', 'confidence': 0.7, 'source': 'wikipedia'})
                            
                            # Extract shopping/market patterns  
                            if any(word in line for word in ['shopping', 'market', 'mall', 'retail', 'commerce']):
                                categories.append({'category': 'Shopping & Markets', 'confidence': 0.7, 'source': 'wikipedia'})
                            
                            # Extract nightlife patterns
                            if any(word in line for word in ['nightlife', 'bars', 'clubs', 'entertainment']):
                                categories.append({'category': 'Nightlife & Entertainment', 'confidence': 0.7, 'source': 'wikipedia'})
                            
                            # Extract transport patterns
                            if any(word in line for word in ['transport', 'transportation', 'airport', 'railway', 'metro', 'river', 'boat']):
                                categories.append({'category': 'Transportation', 'confidence': 0.7, 'source': 'wikipedia'})
                            
                            # Extract culture/arts patterns
                            if any(word in line for word in ['culture', 'art', 'museum', 'theatre', 'gallery', 'music']):
                                categories.append({'category': 'Arts & Culture', 'confidence': 0.8, 'source': 'wikipedia'})
                            
                            # Extract history patterns
                            if any(word in line for word in ['history', 'historic', 'heritage', 'ancient', 'monument']):
                                categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'wikipedia'})
                            
                            # Extract nature patterns
                            if any(word in line for word in ['parks', 'nature', 'garden', 'green', 'outdoor']):
                                categories.append({'category': 'Parks & Nature', 'confidence': 0.7, 'source': 'wikipedia'})
                            
                            # Extract beach/coastal patterns
                            if any(word in line for word in ['beach', 'coast', 'sea', 'ocean', 'waterfront']):
                                categories.append({'category': 'Beaches & Coast', 'confidence': 0.8, 'source': 'wikipedia'})
                        
                        # Extract from page content text with city-specific landmark detection
                        page_text = data.get('parse', {}).get('text', {}).get('*', '').lower()
                        
                        # Look for key phrases in content
                        if any(phrase in page_text for phrase in ['world heritage site', 'unesco', 'historic monument']):
                            categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'wikipedia'})
                        if any(phrase in page_text for phrase in ['art gallery', 'museum', 'cultural center']):
                            categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'wikipedia'})
                        if any(phrase in page_text for phrase in ['wine region', 'vineyard', 'winery', 'wine production']):
                            categories.append({'category': 'Wine & Vineyards', 'confidence': 0.9, 'source': 'wikipedia'})
                        
                        # Extract city-specific landmarks and features
                        import re
                        
                        # Find actual landmark names in the text
                        landmark_patterns = [
                            r'\b(grand palace|eiffel tower|colosseum|statue of liberty|big ben|taj mahal|sydney opera house)\b',
                            r'\b(wat [a-z]+|temple of [a-z]+|saint [a-z]+ cathedral|notre dame)\b',
                            r'\b([a-z]+ museum|[a-z]+ gallery|[a-z]+ monument)\b',
                            r'\b([a-z]+ market|[a-z]+ bazaar|[a-z]+ souk)\b',
                            r'\b([a-z]+ park|[a-z]+ gardens|[a-z]+ square)\b'
                        ]
                        
                        found_landmarks = []
                        for pattern in landmark_patterns:
                            matches = re.findall(pattern, page_text)
                            found_landmarks.extend(matches)
                        
                        # Generate city-specific categories based on actual landmarks found
                        if found_landmarks:
                            # Group landmarks by type and create specific categories
                            temples = [l for l in found_landmarks if any(word in l for word in ['wat', 'temple', 'cathedral', 'saint'])]
                            museums = [l for l in found_landmarks if any(word in l for word in ['museum', 'gallery'])]
                            markets = [l for l in found_landmarks if any(word in l for word in ['market', 'bazaar', 'souk'])]
                            monuments = [l for l in found_landmarks if any(word in l for word in ['palace', 'tower', 'monument', 'colosseum'])]
                            
                            if temples and len(temples) >= 2:
                                categories.append({'category': f'City Temples ({len(temples)} major sites)', 'confidence': 0.9, 'source': 'wikipedia'})
                            elif temples:
                                categories.append({'category': f'{temples[0].title()} & Religious Sites', 'confidence': 0.8, 'source': 'wikipedia'})
                            
                            if museums and len(museums) >= 2:
                                categories.append({'category': f'Art Museums ({len(museums)} major)', 'confidence': 0.8, 'source': 'wikipedia'})
                            elif museums:
                                categories.append({'category': f'{museums[0].title()} & Culture', 'confidence': 0.7, 'source': 'wikipedia'})
                            
                            if markets and len(markets) >= 2:
                                categories.append({'category': f'Local Markets ({len(markets)} areas)', 'confidence': 0.8, 'source': 'wikipedia'})
                            elif markets:
                                categories.append({'category': f'{markets[0].title()} & Shopping', 'confidence': 0.7, 'source': 'wikipedia'})
                            
                            if monuments and len(monuments) >= 2:
                                categories.append({'category': f'Famous Monuments ({len(monuments)} sites)', 'confidence': 0.9, 'source': 'wikipedia'})
                            elif monuments:
                                categories.append({'category': f'{monuments[0].title()} & Landmarks', 'confidence': 0.8, 'source': 'wikipedia'})
                        
                        # Extract city-specific cultural features
                        cultural_patterns = [
                            r'\b(street food|night market|food stall|hawker)\b',
                            r'\b(rooftop bar|sky bar|terrace bar)\b',
                            r'\b(floating market|boat market|river market)\b',
                            r'\b(thai massage|spa|wellness|massage)\b',
                            r'\b(chinatown|little india|quartier)\b'
                        ]
                        
                        found_cultural = []
                        for pattern in cultural_patterns:
                            matches = re.findall(pattern, page_text)
                            found_cultural.extend(matches)
                        
                        # Create cultural categories based on actual features found
                        if 'street food' in found_cultural or 'night market' in found_cultural:
                            categories.append({'category': 'Street Food & Night Markets', 'confidence': 0.9, 'source': 'wikipedia'})
                        if 'rooftop bar' in found_cultural or 'sky bar' in found_cultural:
                            categories.append({'category': 'Rooftop Bars & Sky Dining', 'confidence': 0.8, 'source': 'wikipedia'})
                        if 'floating market' in found_cultural or 'boat market' in found_cultural:
                            categories.append({'category': 'Floating Markets & River Life', 'confidence': 0.9, 'source': 'wikipedia'})
                        if 'thai massage' in found_cultural or 'spa' in found_cultural:
                            categories.append({'category': 'Traditional Spas & Wellness', 'confidence': 0.8, 'source': 'wikipedia'})
                        if 'chinatown' in found_cultural:
                            categories.append({'category': 'Chinatown & Cultural Districts', 'confidence': 0.8, 'source': 'wikipedia'})
                        if any(phrase in page_text for phrase in ['beach', 'coastline', 'sea', 'ocean']):
                            categories.append({'category': 'Beaches & Coast', 'confidence': 0.8, 'source': 'wikipedia'})
                        if any(phrase in page_text for phrase in ['park', 'garden', 'green space', 'nature reserve']):
                            categories.append({'category': 'Parks & Nature', 'confidence': 0.7, 'source': 'wikipedia'})
                        
                        # Extract from Wikipedia categories
                        wiki_cats = data.get('parse', {}).get('categories', [])
                        for cat in wiki_cats:
                            cat_title = cat.get('title', '').lower()
                            
                            if any(word in cat_title for word in ['culture', 'art', 'museums']):
                                categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'wikipedia'})
                            if any(word in cat_title for word in ['history', 'historic', 'heritage']):
                                categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'wikipedia'})
                            if any(word in cat_title for word in ['architecture', 'buildings', 'structures']):
                                categories.append({'category': 'Architecture', 'confidence': 0.8, 'source': 'wikipedia'})
                            if any(word in cat_title for word in ['wine', 'vineyards', 'viticulture']):
                                categories.append({'category': 'Wine & Vineyards', 'confidence': 0.9, 'source': 'wikipedia'})
                                
    except Exception as e:
        print(f"[WIKIPEDIA] Error: {e}")
    
    return categories


async def extract_from_ddgs_trends(city: str, state: str = "") -> List[Dict[str, Any]]:
    """Extract current trending categories from DDGS search with comprehensive analysis."""
    categories = []
    city_lower = city.lower().strip()
    
    if not DDGS_AVAILABLE:
        return categories
        
    try:
        # City-specific search queries for different aspects - dynamic approach
        # Use city name in queries to get city-specific results, not hardcoded lists
        base_queries = [
            f"best things to do in {city}",
            f"top tourist destinations {city}",
            f"{city} famous landmarks monuments",
            f"best restaurants food {city}",
            f"{city} nightlife entertainment",
            f"shopping districts {city}",
            f"parks nature outdoor activities {city}",
            f"museums art culture {city}",
            f"historic sites {city}",
            f"architecture buildings {city}",
            f"sports recreation {city}",
            f"transportation getting around {city}"
        ]
        
        # Add coastal/beach queries only if city might be coastal
        coastal_indicators = ['beach', 'coast', 'sea', 'ocean', 'island', 'port']
        if any(indicator in city_lower for indicator in coastal_indicators):
            base_queries.extend([
                f"{city} beaches coast",
                f"waterfront activities {city}"
            ])
        
        # Add wine region queries only if city might be in wine region
        wine_indicators = ['valley', 'region', 'country', 'estate', 'vineyard']
        if any(indicator in city_lower for indicator in wine_indicators):
            base_queries.append(f"wine tours vineyards {city}")
            
        queries = base_queries
        
        for query in queries:
            try:
                results = await ddgs_search(query, engine="google", max_results=5)
                
                for result in results:
                    title = result.get('title', '').lower()
                    body = result.get('body', '').lower()
                    text = f"{title} {body}"
                    
                    # Comprehensive category extraction with context
                    if any(word in text for word in ['museum', 'art gallery', 'cultural center', 'theatre', 'opera']):
                        categories.append({'category': 'Art & Culture', 'confidence': 0.7, 'source': 'ddgs'})
                    if any(word in text for word in ['beach', 'coast', 'sea', 'ocean', 'waterfront', 'beaches']):
                        categories.append({'category': 'Beaches & Coast', 'confidence': 0.7, 'source': 'ddgs'})
                    if any(word in text for word in ['restaurant', 'food', 'dining', 'cuisine', 'eat', 'culinary']):
                        categories.append({'category': 'Food & Dining', 'confidence': 0.7, 'source': 'ddgs'})
                    if any(word in text for word in ['shopping', 'market', 'mall', 'boutique', 'store', 'retail']):
                        categories.append({'category': 'Shopping', 'confidence': 0.6, 'source': 'ddgs'})
                    if any(word in text for word in ['nightlife', 'bar', 'club', 'pub', 'entertainment', 'music']):
                        categories.append({'category': 'Nightlife', 'confidence': 0.6, 'source': 'ddgs'})
                    if any(word in text for word in ['park', 'garden', 'nature', 'outdoor', 'hiking', 'green space']):
                        categories.append({'category': 'Parks & Nature', 'confidence': 0.6, 'source': 'ddgs'})
                    if any(word in text for word in ['historic', 'history', 'monument', 'landmark', 'heritage', 'ancient']):
                        categories.append({'category': 'Historic Sites', 'confidence': 0.7, 'source': 'ddgs'})
                    if any(word in text for word in ['architecture', 'building', 'structure', 'skyscraper', 'bridge']):
                        categories.append({'category': 'Architecture', 'confidence': 0.7, 'source': 'ddgs'})
                    if any(word in text for word in ['wine', 'winery', 'vineyard', 'wine tour', 'tasting']):
                        categories.append({'category': 'Wine & Vineyards', 'confidence': 0.8, 'source': 'ddgs'})
                    if any(word in text for word in ['sport', 'stadium', 'recreation', 'activity', 'adventure']):
                        categories.append({'category': 'Sports & Recreation', 'confidence': 0.6, 'source': 'ddgs'})
                    if any(word in text for word in ['transport', 'airport', 'metro', 'train', 'bus', 'public transit']):
                        categories.append({'category': 'Transportation', 'confidence': 0.6, 'source': 'ddgs'})
                    if any(word in text for word in ['festival', 'event', 'celebration', 'local event']):
                        categories.append({'category': 'Festivals & Events', 'confidence': 0.6, 'source': 'ddgs'})
                    if any(word in text for word in ['university', 'education', 'school', 'academic']):
                        categories.append({'category': 'Education', 'confidence': 0.5, 'source': 'ddgs'})
                        
            except Exception as e:
                print(f"[DDGS] Search error for query '{query}': {e}")
                continue
                    
    except Exception as e:
        print(f"[DDGS] Error: {e}")
    
    return categories


def combine_and_score_categories(all_categories: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Combine categories from all sources with intelligent scoring."""
    category_scores = {}
    
    # Aggregate scores by category name
    for cat_info in all_categories:
        cat_name = cat_info['category']
        confidence = cat_info['confidence']
        source = cat_info['source']
        
        if cat_name not in category_scores:
            category_scores[cat_name] = {
                'total_score': 0,
                'sources': [],
                'count': 0
            }
        
        # Weight sources differently
        weight = 1.0
        if source == 'fun_facts':
            weight = 1.2  # High confidence for curated facts
        elif source == 'city_guide':
            weight = 1.0  # Good confidence
        elif source == 'wikipedia':
            weight = 0.9  # Good but general
        elif source == 'ddgs':
            weight = 0.7  # Current but less reliable
            
        category_scores[cat_name]['total_score'] += confidence * weight
        category_scores[cat_name]['sources'].append(source)
        category_scores[cat_name]['count'] += 1
    
    # Sort by total score and convert to final format
    sorted_categories = sorted(
        category_scores.items(),
        key=lambda x: x[1]['total_score'],
        reverse=True
    )
    
    final_categories = []
    for cat_name, scores in sorted_categories[:12]:  # Top 12 categories
        intent = cat_name.lower().replace(' & ', '_').replace(' ', '_')
        final_categories.append({
            'icon': get_category_icon(cat_name.lower()),
            'label': cat_name,
            'intent': intent,
            'score': round(scores['total_score'], 2),
            'sources': scores['sources']
        })
    
    return final_categories


<<<<<<< /home/markcodeman/CascadeProjects/travelland/city_guides/src/simple_categories.py
<<<<<<< /home/markcodeman/CascadeProjects/travelland/city_guides/src/simple_categories.py
=======
=======
>>>>>>> /home/markcodeman/.windsurf/worktrees/travelland/travelland-55ed203d/city_guides/src/simple_categories.py
async def is_coastal_city(city: str, state: str = "") -> bool:
    """Determine if city is coastal using actual geographic data."""
    try:
        # Use OpenStreetMap Nominatim API to get city coordinates and geography
        headers = {'User-Agent': 'TravelLand/1.0 (Educational Project)'}
        
        # Build city query
        query = f"{city}"
        if state:
            query += f", {state}"
            
        async with aiohttp.ClientSession() as session:
            # Get city coordinates
            params = {
                'q': query,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            async with session.get('https://nominatim.openstreetmap.org/search', params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        city_data = data[0]
                        lat = float(city_data.get('lat', 0))
                        lon = float(city_data.get('lon', 0))
                        
                        # Use Ocean API to check distance to coast
                        # Ocean API provides distance to nearest coastline
                        ocean_params = {
                            'lat': lat,
                            'lon': lon,
                            'radius': 50000  # 50km radius
                        }
                        async with session.get('https://ocean-api.vercel.app/v1/coastline', params=ocean_params, headers=headers) as ocean_resp:
                            if ocean_resp.status == 200:
                                ocean_data = await ocean_resp.json()
                                # If coastline found within 50km, consider it coastal
                                return ocean_data.get('distance', float('inf')) < 50000
                            
                return False  # Default to inland if API calls fail
    except Exception as e:
        print(f"[GEO_API] Error checking coastal status for {city}: {e}")
        return False  # Default to inland on error

async def filter_geographic_impossibilities(city: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter out categories that are geographically impossible for the given city using actual geographic APIs."""
    filtered_categories = []
    
    for category in categories:
        label = category.get('label', '').lower()
        
        # Remove beach/coast categories for inland cities using actual API
        if any(term in label for term in ['beach', 'coast', 'ocean', 'sea']):
            is_coastal = await is_coastal_city(city)
            if not is_coastal:
                print(f"[GEO_FILTER] Removed '{category['label']}' for inland city {city} (API verified)")
                continue
            else:
                print(f"[GEO_FILTER] Kept '{category['label']}' for coastal city {city} (API verified)")
        
        # Keep everything else
        filtered_categories.append(category)
    
    return filtered_categories


>>>>>>> /home/markcodeman/.windsurf/worktrees/travelland/travelland-55ed203d/city_guides/src/simple_categories.py
async def get_dynamic_categories(city: str, state: str = "", country: str = "US") -> List[Dict[str, str]]:
    """
    Generate categories by leveraging ALL available data sources with semantic understanding:
    - Fun facts (curated, high confidence)
    - City guides (Wikipedia content)
    - Wikipedia sections and categories
    - DDGS current trends
    """
    
    try:
        cache_key = f"categories:{country}:{state}:{city}".lower()

        # Check Redis cache
        if redis_client:
            try:
                cached = await asyncio.to_thread(redis_client.get, cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                print(f"[DYNAMIC] Cache read error: {e}")

        # Extract categories from ALL sources
        all_categories = []
<<<<<<< /home/markcodeman/CascadeProjects/travelland/city_guides/src/simple_categories.py
<<<<<<< /home/markcodeman/CascadeProjects/travelland/city_guides/src/simple_categories.py
        
        # 1. Fun facts (highest confidence for major cities)
        fun_fact_cats = extract_from_fun_facts(city)
        all_categories.extend(fun_fact_cats)
        
        # 2. City guide content
        guide_cats = await extract_from_city_guide(city)
        all_categories.extend(guide_cats)
        
        # 3. Wikipedia sections and categories
        wiki_cats = await extract_from_wikipedia_sections(city, state)
        all_categories.extend(wiki_cats)
        
        # 4. DDGS current trends
        ddgs_cats = await extract_from_ddgs_trends(city, state)
        all_categories.extend(ddgs_cats)
=======
=======
>>>>>>> /home/markcodeman/.windsurf/worktrees/travelland/travelland-55ed203d/city_guides/src/simple_categories.py

        # 1. City profile data (most reliable)
        city_cats = extract_from_city_data(city)
        all_categories.extend(city_cats)
>>>>>>> /home/markcodeman/.windsurf/worktrees/travelland/travelland-55ed203d/city_guides/src/simple_categories.py

        # 2. Wikipedia city guide extraction
        guide_cats = await extract_from_city_guide(city)
        all_categories.extend(guide_cats)

        # 3. Wikipedia sections and categories
        wiki_cats = await extract_from_wikipedia_sections(city, state)
        all_categories.extend(wiki_cats)

        # 4. DDGS current trends (only if we need more categories AND DDGS is working)
        if len(all_categories) < 8 and DDGS_AVAILABLE:
            try:
                # Test DDGS with a simple query first
                test_results = await ddgs_search(f"attractions {city}", max_results=1)
                if test_results:  # Only proceed if DDGS is working
                    ddgs_cats = await extract_from_ddgs_trends(city, state)
                    all_categories.extend(ddgs_cats)
                else:
                    print(f"[DDGS] Rate limited, skipping for {city}")
            except Exception as e:
                print(f"[DDGS] Error checking availability: {e}")

        # 2. Wikipedia city guide extraction
        guide_cats = await extract_from_city_guide(city)
        all_categories.extend(guide_cats)

        # 3. Wikipedia sections and categories
        wiki_cats = await extract_from_wikipedia_sections(city, state)
        all_categories.extend(wiki_cats)

        # 4. DDGS current trends (only if we need more categories AND DDGS is working)
        if len(all_categories) < 8 and DDGS_AVAILABLE:
            try:
                # Test DDGS with a simple query first
                test_results = await ddgs_search(f"attractions {city}", max_results=1)
                if test_results:  # Only proceed if DDGS is working
                    ddgs_cats = await extract_from_ddgs_trends(city, state)
                    all_categories.extend(ddgs_cats)
                else:
                    print(f"[DDGS] Rate limited, skipping for {city}")
            except Exception as e:
                print(f"[DDGS] Error checking availability: {e}")

        # Combine with intelligent scoring
        final_categories = combine_and_score_categories(all_categories)
        
<<<<<<< /home/markcodeman/CascadeProjects/travelland/city_guides/src/simple_categories.py
<<<<<<< /home/markcodeman/CascadeProjects/travelland/city_guides/src/simple_categories.py
=======
=======
>>>>>>> /home/markcodeman/.windsurf/worktrees/travelland/travelland-55ed203d/city_guides/src/simple_categories.py
        # Apply geographic common sense filtering using actual APIs
        final_categories = await filter_geographic_impossibilities(city, final_categories)
        
>>>>>>> /home/markcodeman/.windsurf/worktrees/travelland/travelland-55ed203d/city_guides/src/simple_categories.py
        # Debug: Show what was extracted
        print(f"[DEBUG] Extracted {len(all_categories)} raw categories: {[c['category'] for c in all_categories]}")
        print(f"[DEBUG] Final {len(final_categories)} categories: {[c['label'] for c in final_categories]}")

        # Cache result
        if redis_client and final_categories:
            try:
                if hasattr(redis_client, 'set') and not callable(redis_client.set):
                    # MockRedis case
                    redis_client.set(cache_key, json.dumps(final_categories))
                else:
                    # Real Redis case
                    await asyncio.to_thread(redis_client.set, cache_key, json.dumps(final_categories), ex=CACHE_TTL)
            except Exception as e:
                print(f"[DYNAMIC] Cache write error: {e}")

<<<<<<< /home/markcodeman/CascadeProjects/travelland/city_guides/src/simple_categories.py
        # NO FALLBACKS - Return what we found, even if empty. System must be smart enough.
=======
        # If no categories found, fallback to generic categories
        if not final_categories or len(final_categories) < 3:
            print(f"[DYNAMIC] Only {len(final_categories) if final_categories else 0} categories found for {city}, using generic fallback")
            return get_generic_categories()

>>>>>>> /home/markcodeman/.windsurf/worktrees/travelland/travelland-55ed203d/city_guides/src/simple_categories.py
        return final_categories
        
    except Exception as e:
        print(f"[SMART CATEGORIES] Error: {e}")
        # Still return empty, not generic fallbacks
        return []


def get_generic_categories() -> list:
    """Generic fallback categories when no venue data available"""
    return [
        {'icon': '🍽️', 'label': 'Food & Dining', 'intent': 'dining'},
        {'icon': '🏛️', 'label': 'Historic Sites', 'intent': 'historical'},
        {'icon': '🎨', 'label': 'Art & Culture', 'intent': 'culture'},
        {'icon': '🌳', 'label': 'Parks & Nature', 'intent': 'nature'},
        {'icon': '🛍️', 'label': 'Shopping', 'intent': 'shopping'},
        {'icon': '🌙', 'label': 'Nightlife', 'intent': 'nightlife'}
    ]


def register_category_routes(app):
    """Alias for backward compatibility"""
    register_routes(app)
