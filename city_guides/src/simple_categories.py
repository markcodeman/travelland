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
    from city_guides.providers.ddgs_provider import ddgs_search
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

try:
    from city_guides.providers.wikipedia_provider import fetch_wikipedia_summary
    WIKI_AVAILABLE = True
except ImportError:
    WIKI_AVAILABLE = False

# Redis for caching
import redis
redis_client = None  # Will be set from routes.py

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
        'beach': '🏖️', 'sea': '🏖️', 'ocean': '🏖️', 'coast': '🏖️',
        'history': '🏛️', 'historic': '🏛️', 'museum': '🖼️', 'art': '🎨', 'culture': '🎭',
        'nightlife': '🌃', 'bar': '🍷', 'club': '🎶', 'music': '🎵',
        'park': '🌳', 'nature': '🌳', 'garden': '🌸',
        'shopping': '🛍️', 'market': '🛒', 'mall': '🏬',
        'sport': '⚽', 'stadium': '🏟️',
        'religion': '⛪', 'church': '⛪', 'temple': '🕍',
        'mountain': '🏔️', 'hiking': '🥾',
        'airport': '✈️', 'transport': '🚇', 'transportation': '🚇',
        'wine': '🍷', 'vineyard': '🍇', 'winery': '🍷',
        'sport': '⚽', 'recreation': '🏃', 'stadium': '🏟️',
        'education': '🎓', 'university': '🏛️', 'school': '🏫'
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
            async with session.get('https://en.wikipedia.org/w/api.php', params=params) as resp:
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
                async with session.get('https://en.wikipedia.org/w/api.php', params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Extract from section headers
                        sections = data.get('parse', {}).get('sections', [])
                        for section in sections:
                            line = section.get('line', '').lower()
                            
                            # Comprehensive category mapping
                            if any(word in line for word in ['culture', 'art', 'museum', 'theatre', 'gallery']):
                                categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'wikipedia'})
                            if any(word in line for word in ['history', 'historic', 'heritage', 'medieval']):
                                categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'wikipedia'})
                            if any(word in line for word in ['geography', 'climate', 'parks', 'nature', 'environment']):
                                categories.append({'category': 'Parks & Nature', 'confidence': 0.7, 'source': 'wikipedia'})
                            if any(word in line for word in ['economy', 'business', 'commerce', 'shopping', 'retail']):
                                categories.append({'category': 'Shopping', 'confidence': 0.7, 'source': 'wikipedia'})
                            if any(word in line for word in ['transport', 'transportation', 'airport', 'railway', 'metro']):
                                categories.append({'category': 'Transportation', 'confidence': 0.7, 'source': 'wikipedia'})
                            if any(word in line for word in ['architecture', 'buildings', 'structures', 'landmarks']):
                                categories.append({'category': 'Architecture', 'confidence': 0.8, 'source': 'wikipedia'})
                            if any(word in line for word in ['sports', 'stadium', 'recreation', 'leisure']):
                                categories.append({'category': 'Sports & Recreation', 'confidence': 0.7, 'source': 'wikipedia'})
                            if any(word in line for word in ['food', 'cuisine', 'restaurant', 'dining']):
                                categories.append({'category': 'Food & Dining', 'confidence': 0.7, 'source': 'wikipedia'})
                            if any(word in line for word in ['nightlife', 'entertainment', 'bars', 'clubs']):
                                categories.append({'category': 'Nightlife', 'confidence': 0.7, 'source': 'wikipedia'})
                            if any(word in line for word in ['education', 'university', 'schools', 'academic']):
                                categories.append({'category': 'Education', 'confidence': 0.6, 'source': 'wikipedia'})
                            if any(word in line for word in ['beach', 'coast', 'sea', 'ocean', 'waterfront']):
                                categories.append({'category': 'Beaches & Coast', 'confidence': 0.8, 'source': 'wikipedia'})
                            if any(word in line for word in ['wine', 'vineyard', 'winery', 'viticulture']):
                                categories.append({'category': 'Wine & Vineyards', 'confidence': 0.9, 'source': 'wikipedia'})
                        
                        # Extract from page content text
                        page_text = data.get('parse', {}).get('text', {}).get('*', '').lower()
                        
                        # Look for key phrases in content
                        if any(phrase in page_text for phrase in ['world heritage site', 'unesco', 'historic monument']):
                            categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'wikipedia'})
                        if any(phrase in page_text for phrase in ['art gallery', 'museum', 'cultural center']):
                            categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'wikipedia'})
                        if any(phrase in page_text for phrase in ['wine region', 'vineyard', 'winery', 'wine production']):
                            categories.append({'category': 'Wine & Vineyards', 'confidence': 0.9, 'source': 'wikipedia'})
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
    
    if not DDGS_AVAILABLE:
        return categories
        
    try:
        # Comprehensive search queries for different aspects
        queries = [
            f"best things to do in {city} attractions",
            f"top tourist destinations {city}",
            f"{city} famous landmarks monuments",
            f"best restaurants food {city}",
            f"{city} nightlife entertainment",
            f"shopping districts {city}",
            f"parks nature outdoor activities {city}",
            f"museums art culture {city}",
            f"{city} beaches coast",
            f"wine tours vineyards {city}",
            f"historic sites {city}",
            f"architecture buildings {city}",
            f"sports recreation {city}",
            f"transportation getting around {city}"
        ]
        
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

        # Combine with intelligent scoring
        final_categories = combine_and_score_categories(all_categories)
        
        # Debug: Show what was extracted
        print(f"[DEBUG] Extracted {len(all_categories)} raw categories: {[c['category'] for c in all_categories]}")
        print(f"[DEBUG] Final {len(final_categories)} categories: {[c['label'] for c in final_categories]}")

        # Cache result
        if redis_client and final_categories:
            try:
                await asyncio.to_thread(redis_client.set, cache_key, json.dumps(final_categories), ex=CACHE_TTL)
            except Exception as e:
                print(f"[DYNAMIC] Cache write error: {e}")

        # NO FALLBACKS - Return what we found, even if empty. System must be smart enough.
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
