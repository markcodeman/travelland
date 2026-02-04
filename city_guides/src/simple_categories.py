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
        # Distinctive category icons
        'fashion': '👗', 'design': '✨',
        'film': '�', 'entertainment': '�',
        'tech': '💻', 'innovation': '🚀',
        'finance': '💰', 'business': '💼',
        'michelin': '⭐', 'dining': '�️',
        'nightlife': '�', 
        'architecture': '�️',
        'ancient': '🏛️', 'history': '📜',
        'religious': '⛪', 'spiritual': '�',
        'markets': '🛒', 'shopping': '🛍️',
        'bridges': '🌉', 'waterways': '⛵',
        'skyscrapers': '�️',
        'beach': '�️', 'coast': '�', 'sea': '🏖️', 'ocean': '�️',
        'parks': '🌳', 'gardens': '�', 'nature': '�',
        'museums': '🏛️', 'culture': '🎨',
        'transport': '�', 'metro': '🚉',
        'food': '🍔', 'cuisine': '🍜', 'specialties': '🥐',
        'wine': '🍷', 'vineyards': '🍇',
        'festivals': '🎉', 'events': '🎊',
        # Original icons
        'restaurant': '�️', 'dining': '🍽️',
        'historic': '🏛️', 'museum': '�️', 'art': '🎨',
        'bar': '🍷', 'club': '�', 'music': '�',
        'sport': '⚽', 'stadium': '🏟️',
        'education': '🎓', 'university': '🏛️', 'school': '🏫',
        'mountain': '🏔️', 'hiking': '🥾',
        'airport': '✈️', 'transportation': '🚇',
        'recreation': '🏃',
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
    """Extract semantic categories from fun facts with distinctive city-specific keywords."""
    categories = []
    
    try:
        city_lower = city.lower().strip()
        
        # Import the fun_facts dictionary directly from app.py
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        import city_guides.src.app as app_module
        
        # Access the fun_facts dictionary directly from the module
        # It's defined inside get_fun_fact but we can access it by looking at the function's closure
        # or by replicating the logic here
        fun_facts_data = {
            'paris': [
                "Eiffel Tower", "bakeries", "baguettes", "Louvre", "art", "fashion", "Métro"
            ],
            'london': [
                "British Museum", "museums", "Underground", "Big Ben", "ravens", "Tower"
            ],
            'new york': [
                "Statue of Liberty", "Central Park", "parks", "subway", "Times Square", "languages"
            ],
            'tokyo': [
                "Shibuya", "Michelin", "restaurants", "Skytree", "trains", "Edo"
            ],
            'barcelona': [
                "Sagrada Familia", "Gaudí", "Park Güell", "beaches", "architecture", "orange trees"
            ],
            'rome': [
                "Colosseum", "Vatican", "Pantheon", "fountains", " Trevi", "ancient"
            ],
            'los angeles': [
                "Hollywood", "film", "movies", "studios", "Walk of Fame", "sunshine"
            ],
            'sydney': [
                "Opera House", "Harbour Bridge", "beaches", "Bondi Beach", "Royal Botanic Gardens"
            ],
            'dubai': [
                "Burj Khalifa", "skyscrapers", "shopping", "Palm Jumeirah", "supercars"
            ],
            'amsterdam': [
                "canals", "bicycles", "museums", "Anne Frank House", "bridges"
            ],
            'istanbul': [
                "Hagia Sophia", "Grand Bazaar", "mosques", "Blue Mosque", "two continents"
            ],
            'rio de janeiro': [
                "Christ the Redeemer", "Copacabana", "beaches", "Carnival", "Sugarloaf"
            ],
        }
        
        # Get keywords for this city
        city_keywords = fun_facts_data.get(city_lower, [])
        
        # Map keywords to distinctive categories
        keyword_to_category = {
            # Fashion & Design
            'fashion': ('Fashion & Design', 0.95),
            'couture': ('Fashion & Design', 0.95),
            'designer': ('Fashion & Design', 0.95),
            
            # Film & Entertainment  
            'Hollywood': ('Film & Entertainment', 0.95),
            'film': ('Film & Entertainment', 0.95),
            'movies': ('Film & Entertainment', 0.95),
            'studios': ('Film & Entertainment', 0.95),
            'Walk of Fame': ('Film & Entertainment', 0.95),
            
            # Architecture & Design
            'Gaudí': ('Architecture & Design', 0.95),
            'Sagrada Familia': ('Architecture & Design', 0.95),
            'architecture': ('Architecture & Design', 0.9),
            'modernisme': ('Architecture & Design', 0.95),
            'skyscrapers': ('Skyscrapers', 0.9),
            'Burj Khalifa': ('Skyscrapers', 0.95),
            
            # Ancient History
            'Colosseum': ('Ancient History', 0.95),
            'Pantheon': ('Ancient History', 0.95),
            'ancient': ('Ancient History', 0.9),
            'Vatican': ('Religious Sites', 0.95),
            'mosques': ('Religious Sites', 0.9),
            
            # Food & Dining special
            'Michelin': ('Michelin Dining', 0.95),
            'restaurants': ('Food & Dining', 0.85),
            'bakeries': ('Local Food Specialties', 0.9),
            'baguettes': ('Local Food Specialties', 0.9),
            
            # Beaches
            'beaches': ('Beaches & Coast', 0.9),
            'Bondi Beach': ('Beaches & Coast', 0.95),
            'Copacabana': ('Beaches & Coast', 0.95),
            
            # Transport
            'Métro': ('Metro & Transport', 0.9),
            'Underground': ('Metro & Transport', 0.9),
            'subway': ('Metro & Transport', 0.9),
            'trains': ('Metro & Transport', 0.85),
            
            # Museums & Culture
            'museums': ('Museums & Culture', 0.85),
            'British Museum': ('Museums & Culture', 0.95),
            'Louvre': ('Museums & Culture', 0.95),
            'art': ('Art & Culture', 0.85),
            
            # Parks & Gardens
            'parks': ('Parks & Gardens', 0.85),
            'Central Park': ('Parks & Gardens', 0.95),
            'Royal Botanic Gardens': ('Parks & Gardens', 0.95),
            
            # Markets & Shopping
            'Grand Bazaar': ('Markets & Shopping', 0.95),
            'shopping': ('Shopping', 0.8),
            
            # Landmarks
            'Eiffel Tower': ('Iconic Landmarks', 0.95),
            'Statue of Liberty': ('Iconic Landmarks', 0.95),
            'Christ the Redeemer': ('Iconic Landmarks', 0.95),
            'Opera House': ('Iconic Landmarks', 0.95),
            'Skytree': ('Iconic Landmarks', 0.9),
            
            # Nightlife/Entertainment
            'Times Square': ('Entertainment Districts', 0.95),
            'Shibuya': ('Entertainment Districts', 0.95),
            'Carnival': ('Festivals & Events', 0.95),
            
            # Waterways
            'canals': ('Canals & Waterways', 0.95),
            'bridges': ('Bridges & Waterways', 0.9),
            'Harbour Bridge': ('Bridges & Waterways', 0.95),
        }
        
        # Extract categories based on keywords
        added_categories = set()
        for keyword in city_keywords:
            keyword_lower = keyword.lower()
            for key, (category, confidence) in keyword_to_category.items():
                if key.lower() in keyword_lower or keyword_lower in key.lower():
                    if category not in added_categories:
                        categories.append({
                            'category': category,
                            'confidence': confidence,
                            'source': 'fun_facts_distinctive'
                        })
                        added_categories.add(category)
                        
    except Exception as e:
        print(f"[FUN_FACTS_DISTINCTIVE] Error: {e}")
    
    return categories


# Enhanced Wikipedia fetch that gets full article content
async def fetch_wikipedia_full_content(city: str) -> str:
    """Fetch full Wikipedia article content for better category extraction"""
    try:
        import aiohttp
        # Get full article content via Wikipedia API
        url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext&exlimit=1&titles={city}&format=json"
        headers = {'User-Agent': 'TravelLand/1.0 (Educational)'}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pages = data.get('query', {}).get('pages', {})
                    for page_id, page_data in pages.items():
                        content = page_data.get('extract', '')
                        if content and len(content) > 200:
                            print(f"[WIKI] Got full content for {city}: {len(content)} chars")
                            return content
        
        # Fallback to summary API if full content fails
        return await simple_wikipedia_fetch(city)
    except Exception as e:
        print(f"[WIKI] Full content fetch error: {e}")
        return await simple_wikipedia_fetch(city)


# Simple Wikipedia fetch for testing
async def simple_wikipedia_fetch(city: str) -> str:
    """Simple Wikipedia summary fetch that actually works"""
    try:
        import aiohttp
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{city}"
        headers = {'User-Agent': 'TravelLand/1.0 (Educational)'}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('extract', '')
                else:
                    print(f"[WIKI] HTTP {resp.status} for {city}")
    except Exception as e:
        print(f"[WIKI] Simple fetch error: {e}")
    return ""


async def extract_from_city_guide(city: str) -> List[Dict[str, Any]]:
    """Extract categories from the Wikipedia city guide content."""
    categories = []
    city_lower = city.lower().strip()
    
    try:
        # Use FULL Wikipedia content for better extraction
        content = await fetch_wikipedia_full_content(city)
        if content:
            guide_text = content.lower()
            print(f"[WIKI] Analyzing {len(content)} chars for {city}")
            
            # Extract based on full article content
            if any(word in guide_text for word in ['museum', 'art', 'gallery', 'culture', 'exhibition']):
                categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'city_guide'})
            
            # Beaches validation - must have actual beach/coastal evidence, not just harbor/river
            beach_keywords = ['beach', 'beaches', 'coastline', 'seaside', 'oceanfront', 'sandy beach']
            harbor_mentions = guide_text.count('harbor') + guide_text.count('harbour') + guide_text.count('port')
            beach_mentions = sum(guide_text.count(word) for word in beach_keywords)
            
            # Only add beaches if strong beach evidence AND not a lake city
            lake_keywords = ['lake', 'inland', 'freshwater']
            is_lake_city = any(word in guide_text[:3000] for word in lake_keywords) and 'ocean' not in guide_text[:5000]
            
            if not is_lake_city and (beach_mentions >= 3 or any(word in guide_text for word in ['coastal city', 'seaside resort', 'beach resort', 'popular beaches'])):
                categories.append({'category': 'Beaches & Coast', 'confidence': 0.8, 'source': 'city_guide'})
            
            if any(word in guide_text for word in ['park', 'garden', 'nature', 'green', 'forest', 'mountain']):
                categories.append({'category': 'Parks & Nature', 'confidence': 0.8, 'source': 'city_guide'})
            if any(word in guide_text for word in ['food', 'dining', 'restaurant', 'cuisine', 'eat', 'gastronomy', 'pub', 'bar']):
                categories.append({'category': 'Food & Dining', 'confidence': 0.8, 'source': 'city_guide'})
            if any(word in guide_text for word in ['shopping', 'market', 'store', 'boutique', 'retail', 'mall']):
                categories.append({'category': 'Shopping', 'confidence': 0.7, 'source': 'city_guide'})
            if any(word in guide_text for word in ['nightlife', 'bar', 'pub', 'club', 'entertainment', 'music']):
                categories.append({'category': 'Nightlife', 'confidence': 0.7, 'source': 'city_guide'})
            if any(word in guide_text for word in ['historic', 'history', 'monument', 'castle', 'heritage', 'ancient']):
                categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'city_guide'})
            if any(word in guide_text for word in ['university', 'education', 'college', 'school', 'academic']):
                categories.append({'category': 'Education', 'confidence': 0.6, 'source': 'city_guide'})
            if any(word in guide_text for word in ['theatre', 'theater', 'opera', 'concert', 'performance']):
                categories.append({'category': 'Theatre & Shows', 'confidence': 0.75, 'source': 'city_guide'})
            if any(word in guide_text for word in ['sports', 'stadium', 'football', 'soccer', 'rugby', 'gaa']):
                categories.append({'category': 'Sports', 'confidence': 0.7, 'source': 'city_guide'})
        else:
            print(f"[WIKI] No content found for {city}")
        
        print(f"[WIKI] Extracted {len(categories)} categories for {city}: {[c['category'] for c in categories]}")
            
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
                            # Note: Beaches & Coast is handled in content text extraction with stricter validation
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
                        
                        # Beaches validation - stricter criteria
                        beach_phrases = ['beaches', 'coastline', 'seaside', 'oceanfront', 'beach resort', 'popular beaches']
                        beach_mentions = sum(page_text.count(phrase) for phrase in beach_phrases)
                        # Exclude lake cities
                        is_lake = any(word in page_text[:3000] for word in ['lake', 'inland', 'freshwater']) and 'ocean' not in page_text[:5000]
                        if not is_lake and beach_mentions >= 2:
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
                    # Strict beach validation - must be actual beach destination
                    if any(word in text for word in ['beaches', 'coastal city', 'seaside', 'oceanfront', 'beach resort', 'sandy beach']):
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
