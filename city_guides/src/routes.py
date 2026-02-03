from quart import Quart, request, jsonify
from .enrichment import get_neighborhood_enrichment
from .validation import validate_neighborhood
from city_guides.providers import multi_provider
from city_guides.providers.geocoding import geocode_city, reverse_geocode
from city_guides.providers.overpass_provider import async_geocode_city
from city_guides.providers.utils import get_session
from . import semantic
from .geo_enrichment import enrich_neighborhood
from .synthesis_enhancer import SynthesisEnhancer
from .snippet_filters import looks_like_ddgs_disambiguation_text
from .neighborhood_disambiguator import NeighborhoodDisambiguator
from .persistence import (
    _compute_open_now,
    _fetch_image_from_website,
    _humanize_opening_hours,
    _is_relevant_wikimedia_image,
    _persist_quick_guide,
    _search_impl,
    build_search_cache_key,
    calculate_search_radius,
    determine_budget,
    determine_price_range,
    ensure_bbox,
    fetch_safety_section,
    fetch_us_state_advisory,
    format_venue,
    format_venue_for_display,
    generate_description,
    get_cost_estimates,
    get_country_for_city,
    get_currency_for_country,
    get_currency_name,
    get_provider_links,
    get_weather,
    shorten_place,
)
import asyncio
import aiohttp
import json
import hashlib
import re
import time
import requests
from redis import asyncio as aioredis
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# from .app import app  # Removed to avoid circular import

# Re-export key functions for backward compatibility
__all__ = [
    'get_neighborhood_enrichment',
    'validate_neighborhood',
    'enrich_neighborhood',
    'build_enriched_quick_guide',
    'build_search_cache_key',
    'ensure_bbox',
    'format_venue',
    'determine_budget',
    'determine_price_range',
    'generate_description',
    'format_venue_for_display',
    '_humanize_opening_hours',
    '_compute_open_now',
    'calculate_search_radius',
    'get_country_for_city',
    'get_provider_links',
    'shorten_place',
    'get_currency_for_country',
    'get_currency_name',
    'get_cost_estimates',
    'fetch_safety_section',
    'fetch_us_state_advisory',
    'get_weather',
    '_fetch_image_from_website',
    '_is_relevant_wikimedia_image',
    '_persist_quick_guide',
    '_search_impl'
]

def register_routes(app):
    """Register routes with the Quart app instance.
    
    This function should be called after the app instance is created
    to avoid circular import issues.
    """
    @app.route("/api/city-categories", methods=["POST"])
    async def api_city_categories():
        """API endpoint to get dynamic category suggestions for a city"""
        print(f"[CITY-CATEGORIES ROUTE] Request received")
        payload = await request.get_json(silent=True) or {}
        city = (payload.get("city") or "").strip()
        
        if not city:
            return jsonify({"error": "city required"}), 400
        
        try:
            # Dynamic category generation based on city characteristics
            city_lower = city.lower()
            
            # Check for a few special hardcoded cases first (for very specific cities)
            special_cases = {
                'new york': 'nyc',  # Alias handling
                'nyc': 'nyc'
            }
            
            if city_lower in special_cases:
                # For now, let dynamic handle everything
                pass
            
            # Use dynamic analysis for all cities
            categories = await _analyze_city_categories(city)
            return jsonify({ "categories": categories, "source": "dynamic" })
            
        except Exception as e:
            print(f"[CITY-CATEGORIES ROUTE] Error: {e}")
            # Return default categories on error
            return jsonify({
                "categories": [
                    { "icon": "🍽️", "label": "Food & Dining", "intent": "dining" },
                    { "icon": "🏛️", "label": "Historic Sites", "intent": "historical" },
                    { "icon": "🎨", "label": "Art & Culture", "intent": "culture" },
                    { "icon": "🌳", "label": "Parks & Nature", "intent": "nature" },
                    { "icon": "🛍️", "label": "Shopping", "intent": "shopping" },
                    { "icon": "🌙", "label": "Nightlife", "intent": "nightlife" }
                ],
                "source": "fallback"
            })
    
    async def _analyze_city_categories(city: str) -> list:
        """Advanced dynamic category analysis using multiple data sources"""
        import asyncio
        from city_guides.providers.geocoding import geocode_city
        from city_guides.providers import multi_provider
        
        print(f"[DYNAMIC CATEGORIES] Advanced analysis for {city}...")
        
        # Get city coordinates and basic info
        try:
            city_info = await geocode_city(city)
            print(f"[DYNAMIC CATEGORIES] Raw geocoding result: {city_info}")
            if not city_info:
                print(f"[DYNAMIC CATEGORIES] Geocoding failed for {city}")
                return _get_default_categories()
        except Exception as e:
            print(f"[DYNAMIC CATEGORIES] Geocoding error: {e}")
            return _get_default_categories()
        
        # Extract city characteristics
        display_name = city_info.get('display_name', '').lower()
        lat = city_info.get('lat', 0)
        lon = city_info.get('lon', 0)
        
        # Enhanced country detection with more patterns
        country = _extract_country_enhanced(display_name)
        
        print(f"[DYNAMIC CATEGORIES] Country: '{country}', Display: '{display_name}'")
        print(f"[DYNAMIC CATEGORIES] Lat: {lat}, Lon: {lon}")
        
        # Dynamic category generation based on characteristics
        categories = []
        
        # 1. Advanced country-specific categories using cultural patterns
        print(f"[DYNAMIC CATEGORIES] Checking country-specific categories...")
        country_categories = _get_advanced_country_categories(country, display_name, lat, lon)
        print(f"[DYNAMIC CATEGORIES] Country categories: {len(country_categories)} items")
        categories.extend(country_categories)
        
        # 2. Geographic and climate-based categories
        print(f"[DYNAMIC CATEGORIES] Checking geographic categories...")
        geo_categories = _get_geographic_categories(lat, lon, display_name)
        categories.extend(geo_categories)
        
        # 3. Multi-provider venue analysis for local patterns
        print(f"[DYNAMIC CATEGORIES] Analyzing venue patterns...")
        venue_categories = await _analyze_multi_provider_venues(lat, lon, display_name)
        categories.extend(venue_categories)
        
        # 4. City size and type detection
        city_type = _detect_city_type(display_name, lat, lon)
        type_categories = _get_city_type_categories(city_type, display_name)
        categories.extend(type_categories)
        
        # 5. Cultural and historical context analysis
        cultural_categories = _analyze_cultural_context(display_name, country)
        categories.extend(cultural_categories)
        
        # 6. Ensure exactly 6 categories, prioritize and trim if needed
        categories = _prioritize_and_trim_categories(categories)
        
        # If no categories were generated, add some basic ones based on what we know
        if not categories:
            print(f"[DYNAMIC CATEGORIES] No categories generated, adding fallbacks")
            categories = _get_basic_categories_for_city(city_info, display_name)
        
        print(f"[DYNAMIC CATEGORIES] Generated {len(categories)} categories for {city}")
        return categories
    
    def _extract_country_enhanced(display_name: str) -> str:
        """Enhanced country extraction with more patterns"""
        # Country patterns from display names
        country_patterns = {
            'france': ['france', 'french', 'français'],
            'italy': ['italy', 'italian', 'italia', 'italiano'],
            'spain': ['spain', 'spanish', 'españa', 'español'],
            'portugal': ['portugal', 'portuguese', 'portugal', 'português'],
            'uk': ['united kingdom', 'uk', 'britain', 'british', 'england', 'scotland', 'wales'],
            'usa': ['usa', 'united states', 'america', 'american', 'us'],
            'japan': ['japan', 'japanese', 'japón', '日本'],
            'china': ['china', 'chinese', '中国'],
            'mexico': ['mexico', 'mexican', 'méxico'],
            'india': ['india', 'indian', 'भारत'],
            'germany': ['germany', 'german', 'deutschland'],
            'netherlands': ['netherlands', 'dutch', 'nederland'],
            'belgium': ['belgium', 'belgian', 'belgique'],
            'switzerland': ['switzerland', 'swiss', 'suisse'],
            'austria': ['austria', 'austrian', 'österreich'],
            'greece': ['greece', 'greek', 'ελλάδα'],
            'turkey': ['turkey', 'turkish', 'türkiye'],
            'russia': ['russia', 'russian', 'россия'],
            'brazil': ['brazil', 'brazilian', 'brasil'],
            'argentina': ['argentina', 'argentinian', 'argentina'],
            'canada': ['canada', 'canadian'],
            'australia': ['australia', 'australian'],
            'thailand': ['thailand', 'thai', 'ประเทศไทย'],
            'vietnam': ['vietnam', 'vietnamese', 'việt nam'],
            'egypt': ['egypt', 'egyptian', 'مصر'],
            'south africa': ['south africa', 'south african'],
            'morocco': ['morocco', 'moroccan', 'المغرب'],
            'uae': ['uae', 'emirates', 'dubai', 'abu dhabi']
        }
        
        display_lower = display_name.lower()
        for country, patterns in country_patterns.items():
            for pattern in patterns:
                if pattern in display_lower:
                    return country
        
        return ''
    
    def _get_advanced_country_categories(country: str, display_name: str, lat: float, lon: float) -> list:
        """Advanced country-specific categories with cultural depth"""
        categories = []
        
        if country == 'france':
            categories.extend([
                {'icon': '🥐', 'label': 'Boulangeries & Pâtisseries', 'intent': 'cafes'},
                {'icon': '🍷', 'label': 'Vins & Fromages', 'intent': 'dining'},
                {'icon': '🎨', 'label': 'Musées & Galeries', 'intent': 'museums'},
                {'icon': '🏰', 'label': 'Châteaux & Monuments', 'intent': 'historical'},
                {'icon': '🚲', 'label': 'Vélo & Seine', 'intent': 'transport'},
                {'icon': '🌹', 'label': 'Jardins Romantiques', 'intent': 'nature'}
            ])
        elif country == 'italy':
            categories.extend([
                {'icon': '🍝', 'label': 'Pasta & Pizza Artigianali', 'intent': 'food'},
                {'icon': '🍷', 'label': 'Vini & Enoteche', 'intent': 'dining'},
                {'icon': '🏛️', 'label': 'Rovine Antiche & Siti', 'intent': 'historical'},
                {'icon': '🛵', 'label': 'Vespa & Strade', 'intent': 'transport'},
                {'icon': '⛪', 'label': 'Chiese & Cattedrali', 'intent': 'religious'},
                {'icon': '🎭', 'label': 'Opera & Teatro', 'intent': 'culture'}
            ])
        elif country == 'portugal':
            categories.extend([
                {'icon': '🥐', 'label': 'Pastéis & Cafés', 'intent': 'cafes'},
                {'icon': '🍷', 'label': 'Vinhos & Petiscos', 'intent': 'dining'},
                {'icon': '🎵', 'label': 'Fado & Música', 'intent': 'culture'},
                {'icon': '🚋', 'label': 'Elétricos & História', 'intent': 'transport'},
                {'icon': '🏖️', 'label': 'Praias & Atlântico', 'intent': 'beaches'},
                {'icon': '🦀', 'label': 'Marisco & Bacalhau', 'intent': 'food'}
            ])
        elif country == 'spain':
            categories.extend([
                {'icon': '🍷', 'label': 'Tapas & Vino', 'intent': 'dining'},
                {'icon': '💃', 'label': 'Flamenco & Cultura', 'intent': 'culture'},
                {'icon': '🏖️', 'label': 'Playas & Sol', 'intent': 'beaches'},
                {'icon': '🏘️', 'label': 'Pueblos Blancos', 'intent': 'historical'},
                {'icon': '🥘', 'label': 'Paella & Arroz', 'intent': 'food'},
                {'icon': '🏛️', 'label': 'Alhambra & Moorish', 'intent': 'historical'}
            ])
        elif country == 'uk':
            categories.extend([
                {'icon': '🫖', 'label': 'Afternoon Tea', 'intent': 'cafes'},
                {'icon': '👑', 'label': 'Royalty & Palaces', 'intent': 'historical'},
                {'icon': '🇬🇧', 'label': 'Pubs & Ale', 'intent': 'nightlife'},
                {'icon': '🎭', 'label': 'West End & Theatre', 'intent': 'culture'},
                {'icon': '🌧️', 'label': 'Indoor Markets', 'intent': 'shopping'},
                {'icon': '🏰', 'label': 'Castles & Heritage', 'intent': 'historical'}
            ])
        elif country == 'usa':
            if 'new york' in display_name:
                categories.extend([
                    {'icon': '🍕', 'label': 'Pizza & Bagels', 'intent': 'food'},
                    {'icon': '🗽', 'label': 'Icons & Landmarks', 'intent': 'landmarks'},
                    {'icon': '🎭', 'label': 'Broadway & Theater', 'intent': 'theater'},
                    {'icon': '🏙️', 'label': 'Skyscrapers & Skyline', 'intent': 'architecture'},
                    {'icon': '🚕', 'label': 'Yellow Cabs & Streets', 'intent': 'transport'},
                    {'icon': '🌃', 'label': 'Rooftop Bars', 'intent': 'nightlife'}
                ])
            else:
                categories.extend([
                    {'icon': '🍔', 'label': 'Local Cuisine', 'intent': 'food'},
                    {'icon': '🏛️', 'label': 'Historic Sites', 'intent': 'historical'},
                    {'icon': '🎵', 'label': 'Live Music & Jazz', 'intent': 'nightlife'},
                    {'icon': '🏞️', 'label': 'National Parks', 'intent': 'nature'},
                    {'icon': '🏈', 'label': 'Sports & Stadiums', 'intent': 'sports'},
                    {'icon': '🛣️', 'label': 'Road Trips', 'intent': 'transport'}
                ])
        elif country == 'japan':
            categories.extend([
                {'icon': '🍱', 'label': 'Sushi & Ramen', 'intent': 'food'},
                {'icon': '🏮', 'label': 'Temples & Shrines', 'intent': 'religious'},
                {'icon': '🌸', 'label': 'Cherry Blossoms', 'intent': 'nature'},
                {'icon': '🎮', 'label': 'Anime & Gaming', 'intent': 'culture'},
                {'icon': '🚊', 'label': 'Trains & Stations', 'intent': 'transport'},
                {'icon': '🏮', 'label': 'Onsen & Ryokan', 'intent': 'relaxation'}
            ])
        elif country == 'china':
            categories.extend([
                {'icon': '🥟', 'label': 'Dim Sum & Dumplings', 'intent': 'food'},
                {'icon': '🏛️', 'label': 'Great Wall & History', 'intent': 'historical'},
                {'icon': '🍵', 'label': 'Tea Culture', 'intent': 'culture'},
                {'icon': '🏙️', 'label': 'Modern Skylines', 'intent': 'architecture'},
                {'icon': '🐉', 'label': 'Dragon Festivals', 'intent': 'culture'},
                {'icon': '🚄', 'label': 'High-Speed Rail', 'intent': 'transport'}
            ])
        elif country == 'mexico':
            categories.extend([
                {'icon': '🌮', 'label': 'Tacos & Street Food', 'intent': 'food'},
                {'icon': '🏛️', 'label': 'Mayan & Aztec Ruins', 'intent': 'historical'},
                {'icon': '🏖️', 'label': 'Beaches & Resorts', 'intent': 'beaches'},
                {'icon': '🎉', 'label': 'Dia de los Muertos', 'intent': 'culture'},
                {'icon': '🌶️', 'label': 'Chili & Chocolate', 'intent': 'food'},
                {'icon': '🏜️', 'label': 'Desert & Cacti', 'intent': 'nature'}
            ])
        elif country == 'india':
            categories.extend([
                {'icon': '🍛', 'label': 'Curry & Spice', 'intent': 'food'},
                {'icon': '🕌', 'label': 'Temples & History', 'intent': 'religious'},
                {'icon': '🛍️', 'label': 'Markets & Bazaars', 'intent': 'shopping'},
                {'icon': '🐘', 'label': 'Wildlife & Tigers', 'intent': 'nature'},
                {'icon': '🕉️', 'label': 'Yoga & Spirituality', 'intent': 'culture'},
                {'icon': '🚕', 'label': 'Auto Rickshaws', 'intent': 'transport'}
            ])
        elif country == 'greece':
            categories.extend([
                {'icon': '🥙', 'label': 'Gyros & Souvlaki', 'intent': 'food'},
                {'icon': '🏛️', 'label': 'Ancient Ruins', 'intent': 'historical'},
                {'icon': '🏖️', 'label': 'Islands & Beaches', 'intent': 'beaches'},
                {'icon': '🫒', 'label': 'Olive Oil & Feta', 'intent': 'food'},
                {'icon': '⚪', 'label': 'White & Blue Villages', 'intent': 'architecture'},
                {'icon': '🌊', 'label': 'Sailing & Watersports', 'intent': 'water'}
            ])
        elif country == 'uae':
            categories.extend([
                {'icon': '🏗️', 'label': 'Burj Khalifa & Towers', 'intent': 'architecture'},
                {'icon': '🛍️', 'label': 'Gold Souks & Shopping', 'intent': 'shopping'},
                {'icon': '🏜️', 'label': 'Desert Safari', 'intent': 'nature'},
                {'icon': '🚤', 'label': 'Marina Yachts', 'intent': 'water'},
                {'icon': '🍽️', 'label': 'Luxury Dining', 'intent': 'dining'},
                {'icon': '🏊', 'label': 'Beach Clubs', 'intent': 'beaches'}
            ])
        
        return categories
    
    def _get_geographic_categories(lat: float, lon: float, display_name: str) -> list:
        """Enhanced geographic and climate-based categories"""
        categories = []
        
        # Coastal detection
        if _is_near_coast(lat, lon):
            categories.extend([
                {'icon': '🏖️', 'label': 'Beaches & Coast', 'intent': 'beaches'},
                {'icon': '🌊', 'label': 'Water Activities', 'intent': 'water'}
            ])
            print(f"[DYNAMIC CATEGORIES] Added coastal categories")
        
        # Climate zones
        if lat > 60:  # Arctic/Northern
            categories.extend([
                {'icon': '❄️', 'label': 'Winter Activities', 'intent': 'winter'},
                {'icon': '🏔️', 'label': 'Northern Lights', 'intent': 'nature'}
            ])
            print(f"[DYNAMIC CATEGORIES] Added arctic categories")
        elif lat < -60:  # Antarctic/Southern
            categories.extend([
                {'icon': '🐧', 'label': 'Wildlife', 'intent': 'nature'},
                {'icon': '🏔️', 'label': 'Glaciers', 'intent': 'nature'}
            ])
            print(f"[DYNAMIC CATEGORIES] Added antarctic categories")
        elif -23.5 <= lat <= 23.5:  # Tropical
            categories.extend([
                {'icon': '🌺', 'label': 'Tropical Paradise', 'intent': 'nature'},
                {'icon': '🥥', 'label': 'Island Life', 'intent': 'culture'}
            ])
            print(f"[DYNAMIC CATEGORIES] Added tropical categories")
        elif 23.5 < lat < 35:  # Subtropical
            categories.extend([
                {'icon': '🌴', 'label': 'Palm Trees & Gardens', 'intent': 'nature'},
                {'icon': '☀️', 'label': 'Sunshine & Outdoors', 'intent': 'nature'}
            ])
            print(f"[DYNAMIC CATEGORIES] Added subtropical categories")
        elif 35 <= lat <= 60:  # Temperate
            categories.extend([
                {'icon': '🍂', 'label': 'Seasons & Foliage', 'intent': 'nature'},
                {'icon': '🌳', 'label': 'Parks & Forests', 'intent': 'nature'}
            ])
            print(f"[DYNAMIC CATEGORIES] Added temperate categories")
        
        return categories
    
    async def _analyze_multi_provider_venues(lat: float, lon: float, display_name: str) -> list:
        """Analyze venues from multiple providers to detect local patterns"""
        categories = []
        
        try:
            bbox = [lon - 0.05, lat - 0.05, lon + 0.05, lat + 0.05]
            
            # Sample different types of venues
            venue_types = ['restaurant', 'bar', 'museum', 'park', 'shop']
            
            for venue_type in venue_types:
                try:
                    venues = await multi_provider.async_discover_pois(
                        city=None, poi_type=venue_type, bbox=bbox, limit=20, timeout=3.0
                    )
                    
                    if venues:
                        type_categories = _analyze_venue_patterns_enhanced(venues, display_name, venue_type)
                        categories.extend(type_categories)
                        
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"[DYNAMIC CATEGORIES] Multi-provider analysis failed: {e}")
        
        return categories
    
    def _analyze_venue_patterns_enhanced(venues: list, display_name: str, venue_type: str) -> list:
        """Enhanced venue pattern analysis"""
        categories = []
        
        if not venues:
            return categories
        
        # Count venue characteristics
        characteristics = {
            'has_website': 0,
            'has_phone': 0,
            'has_hours': 0,
            'price_cheap': 0,
            'price_expensive': 0,
            'outdoor_seating': 0,
            'live_music': 0,
            'local_cuisine': 0
        }
        
        cuisine_types = {}
        
        for venue in venues[:15]:  # Sample first 15
            tags = venue.get('tags', {})
            if isinstance(tags, str):
                continue
            
            # Check characteristics
            if tags.get('website'):
                characteristics['has_website'] += 1
            if tags.get('phone'):
                characteristics['has_phone'] += 1
            if tags.get('opening_hours'):
                characteristics['has_hours'] += 1
                
            # Price indicators
            if tags.get('price_level') == 'cheap' or tags.get('fee') == 'no':
                characteristics['price_cheap'] += 1
            elif tags.get('price_level') == 'expensive':
                characteristics['price_expensive'] += 1
                
            # Features
            if tags.get('outdoor_seating') == 'yes':
                characteristics['outdoor_seating'] += 1
            if tags.get('live_music') == 'yes':
                characteristics['live_music'] += 1
                
            # Cuisine analysis
            cuisine = tags.get('cuisine', '')
            if cuisine:
                for c in cuisine.split(';'):
                    c = c.strip().lower()
                    cuisine_types[c] = cuisine_types.get(c, 0) + 1
        
        # Generate categories based on patterns
        total_venues = len(venues[:15])
        
        if characteristics['outdoor_seating'] > total_venues * 0.3:
            categories.append({'icon': '🌳', 'label': 'Outdoor Dining', 'intent': 'dining'})
        
        if characteristics['live_music'] > 0:
            categories.append({'icon': '🎵', 'label': 'Live Music Venues', 'intent': 'nightlife'})
        
        if characteristics['price_cheap'] > total_venues * 0.4:
            categories.append({'icon': '💰', 'label': 'Budget-Friendly', 'intent': 'dining'})
        
        if characteristics['price_expensive'] > total_venues * 0.3:
            categories.append({'icon': '💎', 'label': 'Fine Dining', 'intent': 'dining'})
        
        # Cuisine-based categories
        if cuisine_types:
            top_cuisine = max(cuisine_types, key=cuisine_types.get)
            if top_cuisine == 'italian':
                categories.append({'icon': '🍝', 'label': 'Italian Cuisine', 'intent': 'food'})
            elif top_cuisine == 'japanese':
                categories.append({'icon': '🍱', 'label': 'Japanese Cuisine', 'intent': 'food'})
            elif top_cuisine == 'indian':
                categories.append({'icon': '🍛', 'label': 'Indian Cuisine', 'intent': 'food'})
            elif top_cuisine == 'chinese':
                categories.append({'icon': '🥟', 'label': 'Chinese Cuisine', 'intent': 'food'})
            elif top_cuisine == 'mexican':
                categories.append({'icon': '🌮', 'label': 'Mexican Cuisine', 'intent': 'food'})
            elif top_cuisine == 'thai':
                categories.append({'icon': '🥘', 'label': 'Thai Cuisine', 'intent': 'food'})
        
        return categories
    
    def _detect_city_type(display_name: str, lat: float, lon: float) -> str:
        """Detect city type based on characteristics"""
        display_lower = display_name.lower()
        
        # Capital cities
        capital_indicators = ['capital', 'capitol', 'federal district']
        if any(indicator in display_lower for indicator in capital_indicators):
            return 'capital'
        
        # Tourist destinations
        tourist_indicators = ['resort', 'beach', 'coast', 'island', 'tourist']
        if any(indicator in display_lower for indicator in tourist_indicators):
            return 'tourist'
        
        # Historic cities
        historic_indicators = ['old town', 'historic', 'ancient', 'medieval']
        if any(indicator in display_lower for indicator in historic_indicators):
            return 'historic'
        
        # University cities
        university_indicators = ['university', 'college', 'campus']
        if any(indicator in display_lower for indicator in university_indicators):
            return 'university'
        
        # Major metropolitan areas (based on coordinates)
        if abs(lat) < 60 and abs(lon) < 180:  # Basic check
            # Could be enhanced with population data
            return 'metropolitan'
        
        return 'general'
    
    def _get_city_type_categories(city_type: str, display_name: str) -> list:
        """Get categories based on city type"""
        categories = []
        
        if city_type == 'capital':
            categories.extend([
                {'icon': '🏛️', 'label': 'Government & Politics', 'intent': 'historical'},
                {'icon': '🎭', 'label': 'National Museums', 'intent': 'museums'}
            ])
        elif city_type == 'tourist':
            categories.extend([
                {'icon': '📸', 'label': 'Photo Spots', 'intent': 'landmarks'},
                {'icon': '🎢', 'label': 'Tourist Attractions', 'intent': 'attractions'}
            ])
        elif city_type == 'historic':
            categories.extend([
                {'icon': '🏰', 'label': 'Historic Districts', 'intent': 'historical'},
                {'icon': '📚', 'label': 'Heritage Sites', 'intent': 'museums'}
            ])
        elif city_type == 'university':
            categories.extend([
                {'icon': '🎓', 'label': 'Campus Life', 'intent': 'culture'},
                {'icon': '📚', 'label': 'Student Cafes', 'intent': 'cafes'}
            ])
        
        return categories
    
    def _analyze_cultural_context(display_name: str, country: str) -> list:
        """Analyze cultural context for additional categories"""
        categories = []
        
        # Language-based categories
        if country == 'france':
            categories.append({'icon': '💬', 'label': 'French Language', 'intent': 'culture'})
        elif country == 'spain':
            categories.append({'icon': '💬', 'label': 'Spanish Language', 'intent': 'culture'})
        elif country == 'italy':
            categories.append({'icon': '💬', 'label': 'Italian Language', 'intent': 'culture'})
        
        # Regional specialties
        if 'tuscany' in display_name and country == 'italy':
            categories.extend([
                {'icon': '🍷', 'label': 'Chianti Wine', 'intent': 'dining'},
                {'icon': '🏛️', 'label': 'Renaissance Art', 'intent': 'museums'}
            ])
        elif 'bavaria' in display_name and country == 'germany':
            categories.extend([
                {'icon': '🍺', 'label': 'Beer Gardens', 'intent': 'nightlife'},
                {'icon': '🥨', 'label': 'Pretzels & Sausages', 'intent': 'food'}
            ])
        
        return categories
    
    def _get_basic_categories_for_city(city_info: dict, display_name: str) -> list:
        """Generate basic categories when no specific ones were detected"""
        categories = []
        
        # Always add food
        categories.append({'icon': '🍽️', 'label': 'Food & Dining', 'intent': 'dining'})
        
        # Add historical if it seems like a historic place
        if any(word in display_name for word in ['rome', 'athens', 'cairo', 'paris', 'london']):
            categories.append({'icon': '🏛️', 'label': 'Historic Sites', 'intent': 'historical'})
        
        # Add culture/arts for major cities
        categories.append({'icon': '🎨', 'label': 'Art & Culture', 'intent': 'culture'})
        
        # Add nature/parks
        categories.append({'icon': '🌳', 'label': 'Parks & Nature', 'intent': 'nature'})
        
        # Add shopping
        categories.append({'icon': '🛍️', 'label': 'Shopping', 'intent': 'shopping'})
        
        # Add nightlife
        categories.append({'icon': '�', 'label': 'Nightlife', 'intent': 'nightlife'})
        
        return categories
    
    def _is_near_coast(lat: float, lon: float) -> bool:
        """Conservative heuristic to determine if city is near coast"""
        # Only very obvious coastal cities get beach categories
        # This prevents false positives for inland cities
        
        # Clear coastal areas (be very conservative)
        if 35 <= lat <= 45 and -10 <= lon <= 0:  # Portugal, Spain, France coast
            # But exclude Paris area specifically
            if not (48 <= lat <= 49 and 1 <= lon <= 3):
                return True
        elif 40 <= lat <= 45 and 5 <= lon <= 15:  # Italy coast
            return True
        elif -30 <= lat <= 30 and 100 <= lon <= 180:  # Asia/Oceania islands
            return True
        elif 25 <= lat <= 45 and -80 <= lon <= -60:  # US East Coast
            return True
        elif 30 <= lat <= 50 and -125 <= lon <= -110:  # US West Coast
            return True
        
        return False
    
    def _get_country_specific_categories(country: str, display_name: str) -> list:
        """Get categories based on country characteristics"""
        categories = []
        
        # Country-specific patterns
        if 'italy' in country or 'italian' in display_name:
            categories.extend([
                {'icon': '🍝', 'label': 'Pasta & Pizza', 'intent': 'food'},
                {'icon': '🏛️', 'label': 'Ancient History', 'intent': 'historical'},
                {'icon': '🍷', 'label': 'Wine Regions', 'intent': 'dining'}
            ])
        elif 'france' in country or 'french' in display_name:
            categories.extend([
                {'icon': '🥐', 'label': 'Bakeries & Cafes', 'intent': 'cafes'},
                {'icon': '🍷', 'label': 'Wine & Cheese', 'intent': 'dining'},
                {'icon': '🎨', 'label': 'Art Museums', 'intent': 'museums'}
            ])
        elif 'japan' in country or 'japanese' in display_name:
            categories.extend([
                {'icon': '🍱', 'label': 'Sushi & Ramen', 'intent': 'food'},
                {'icon': '🏮', 'label': 'Temples & Shrines', 'intent': 'religious'},
                {'icon': '🌸', 'label': 'Cherry Blossoms', 'intent': 'nature'}
            ])
        elif 'usa' in country or 'america' in display_name:
            if 'new york' in display_name:
                categories.extend([
                    {'icon': '🍕', 'label': 'Pizza & Bagels', 'intent': 'food'},
                    {'icon': '🗽', 'label': 'Icons & Landmarks', 'intent': 'landmarks'},
                    {'icon': '🎭', 'label': 'Broadway & Theater', 'intent': 'theater'}
                ])
            else:
                categories.extend([
                    {'icon': '🍔', 'label': 'Local Cuisine', 'intent': 'food'},
                    {'icon': '🏛️', 'label': 'Historic Sites', 'intent': 'historical'},
                    {'icon': '🎵', 'label': 'Live Music', 'intent': 'nightlife'}
                ])
        elif 'portugal' in country or 'portuguese' in display_name:
            categories.extend([
                {'icon': '🥐', 'label': 'Pastéis & Cafes', 'intent': 'cafes'},
                {'icon': '🍷', 'label': 'Wine & Petiscos', 'intent': 'dining'},
                {'icon': '🎵', 'label': 'Fado Music', 'intent': 'culture'}
            ])
        elif 'spain' in country or 'spanish' in display_name:
            categories.extend([
                {'icon': '🍷', 'label': 'Tapas & Wine', 'intent': 'dining'},
                {'icon': '🏖️', 'label': 'Beaches', 'intent': 'beaches'},
                {'icon': '💃', 'label': 'Flamenco & Culture', 'intent': 'culture'}
            ])
        elif 'uk' in country or 'britain' in country or 'london' in display_name:
            categories.extend([
                {'icon': '🫖', 'label': 'Afternoon Tea', 'intent': 'cafes'},
                {'icon': '👑', 'label': 'Royalty & Palaces', 'intent': 'historical'},
                {'icon': '🇬🇧', 'label': 'Pubs & Bars', 'intent': 'nightlife'}
            ])
        elif 'mexico' in country or 'mexican' in display_name:
            categories.extend([
                {'icon': '🌮', 'label': 'Tacos & Street Food', 'intent': 'food'},
                {'icon': '🏛️', 'label': 'Mayan & Aztec', 'intent': 'historical'},
                {'icon': '🏖️', 'label': 'Beaches & Resorts', 'intent': 'beaches'}
            ])
        elif 'india' in country or 'indian' in display_name:
            categories.extend([
                {'icon': '🍛', 'label': 'Curry & Spice', 'intent': 'food'},
                {'icon': '🕌', 'label': 'Temples & History', 'intent': 'religious'},
                {'icon': '🛍️', 'label': 'Markets & Bazaars', 'intent': 'shopping'}
            ])
        elif 'china' in country or 'chinese' in display_name:
            categories.extend([
                {'icon': '🥟', 'label': 'Dim Sum & Dumplings', 'intent': 'food'},
                {'icon': '🏛️', 'label': 'Ancient Wonders', 'intent': 'historical'},
                {'icon': '🍵', 'label': 'Tea Culture', 'intent': 'culture'}
            ])
        
        return categories
    
    async def _sample_city_venues(bbox: list) -> list:
        """Sample venues from the city to analyze patterns"""
        try:
            venues = await multi_provider.async_discover_pois(
                city=None, poi_type="restaurant", bbox=bbox, limit=50, timeout=5.0
            )
            return venues
        except Exception:
            return []
    
    def _analyze_venue_patterns(venues: list, display_name: str) -> list:
        """Analyze venue patterns to detect local specialties"""
        categories = []
        
        if not venues:
            return categories
        
        # Count venue types
        venue_types = {}
        cuisine_types = {}
        
        for venue in venues[:20]:  # Sample first 20
            tags = venue.get('tags', {})
            if isinstance(tags, str):
                continue
                
            # Count amenity types
            amenity = tags.get('amenity', '')
            if amenity:
                venue_types[amenity] = venue_types.get(amenity, 0) + 1
            
            # Count cuisine types
            cuisine = tags.get('cuisine', '')
            if cuisine:
                for c in cuisine.split(';'):
                    c = c.strip().lower()
                    cuisine_types[c] = cuisine_types.get(c, 0) + 1
        
        # Generate categories based on patterns
        if venue_types.get('bar', 0) > 5:
            categories.append({'icon': '🍷', 'label': 'Bars & Nightlife', 'intent': 'nightlife'})
        
        if venue_types.get('cafe', 0) > 5:
            categories.append({'icon': '☕', 'label': 'Coffee Culture', 'intent': 'cafes'})
        
        # Cuisine-based categories
        top_cuisines = sorted(cuisine_types.items(), key=lambda x: x[1], reverse=True)[:3]
        for cuisine, count in top_cuisines:
            if count > 3:
                if cuisine == 'italian':
                    categories.append({'icon': '🍝', 'label': 'Italian Food', 'intent': 'food'})
                elif cuisine == 'japanese':
                    categories.append({'icon': '🍱', 'label': 'Japanese Food', 'intent': 'food'})
                elif cuisine == 'indian':
                    categories.append({'icon': '🍛', 'label': 'Indian Food', 'intent': 'food'})
                elif cuisine == 'chinese':
                    categories.append({'icon': '🥟', 'label': 'Chinese Food', 'intent': 'food'})
        
        return categories
    
    def _prioritize_and_trim_categories(categories: list) -> list:
        """Ensure exactly 6 categories, prioritizing unique ones"""
        if len(categories) <= 6:
            return categories
        
        # Remove duplicates based on intent
        seen_intents = set()
        unique_categories = []
        for cat in categories:
            intent = cat.get('intent', '')
            if intent not in seen_intents:
                seen_intents.add(intent)
                unique_categories.append(cat)
                if len(unique_categories) == 6:
                    break
        
        return unique_categories
    
    def _get_default_categories() -> list:
        """Fallback categories for unknown cities"""
        return [
            { 'icon': '🍽️', 'label': 'Food & Dining', 'intent': 'dining' },
            { 'icon': '🏛️', 'label': 'Historic Sites', 'intent': 'historical' },
            { 'icon': '🎨', 'label': 'Art & Culture', 'intent': 'culture' },
            { 'icon': '🌳', 'label': 'Parks & Nature', 'intent': 'nature' },
            { 'icon': '🛍️', 'label': 'Shopping', 'intent': 'shopping' },
            { 'icon': '�', 'label': 'Nightlife', 'intent': 'nightlife' }
        ]
    
    @app.route("/api/search", methods=["POST"])
    async def api_search():
        """API endpoint for searching venues and places in a city"""
        print(f"[SEARCH ROUTE] Search request received")
        payload = await request.get_json(silent=True) or {}
        print(f"[SEARCH ROUTE] Payload: {payload}")
        
        # Lightweight heuristic to decide whether to cache this search (focuses on food/top queries)
        city = (payload.get("query") or "").strip()
        q = (payload.get("category") or "").strip().lower()
        neighborhood = payload.get("neighborhood")
        should_cache = False  # disabled for testing
        
        if not city:
            return jsonify({"error": "city required"}), 400
        
        try:
            # Use the search implementation from persistence
            result = await asyncio.to_thread(_search_impl, payload)
            
            if should_cache and redis_client:
                cache_key = build_search_cache_key(city, q, neighborhood)
                try:
                    await redis_client.set(cache_key, json.dumps(result), ex=PREWARM_TTL)
                    app.logger.info("Cached search result for %s/%s", city, q)
                except Exception:
                    app.logger.exception("Failed to cache search result")
            
            return jsonify(result)
            
        except Exception as e:
            app.logger.exception('Search failed')
            return jsonify({"error": "search_failed", "details": str(e)}), 500
