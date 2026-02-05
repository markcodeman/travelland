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
        'film': '🎬', 'entertainment': '🎭',
        'tech': '💻', 'innovation': '🚀',
        'finance': '💰', 'business': '💼',
        'michelin': '⭐', 'dining': '🍽️',
        'nightlife': '🌙', 
        'architecture': '🏛️',
        'ancient': '🏛️', 'history': '📜',
        'religious': '⛪', 'spiritual': '🕊️',
        'markets': '🛒', 'shopping': '🛍️',
        'bridges': '🌉', 'waterways': '⛵',
        'skyscrapers': '🏙️',
        'beach': '🏖️', 'coast': '🌊', 'sea': '🏖️', 'ocean': '🌊',
        'parks': '🌳', 'gardens': '🌸', 'nature': '🌿',
        'museums': '🏛️', 'culture': '🎨',
        'transport': '🚇', 'metro': '🚉',
        'food': '🍔', 'cuisine': '🍜', 'specialties': '🥐',
        'wine': '🍷', 'vineyards': '🍇',
        'gold': '🥇', 'souk': '🏪', 'markets': '🛍️',
        'festivals': '🎉', 'events': '🎊',
        # Original icons
        'restaurant': '🍽️', 'dining': '🍽️',
        'historic': '🏛️', 'museum': '🏛️', 'art': '🎨',
        'bar': '🍷', 'club': '🎭', 'music': '🎵',
        'sport': '⚽', 'stadium': '🏟️',
        'education': '🎓', 'university': '🏛️', 'school': '🏫',
        'mountain': '🏔️', 'hiking': '🥾',
        'airport': '✈️', 'transportation': '🚇',
        'recreation': '🏃',
        # Abu Dhabi specific
        'theme': '🎢', 'park': '🎢', 'entertainment': '🎭',
        'luxury': '🏨', 'resort': '🏨',
        'desert': '🏜️', 'adventure': '🚙',
        'cultural': '🎭', 'activities': '🎪',
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
        
        # Import the actual fun_facts from app.py
        try:
            from city_guides.src.app import fun_facts
            fun_facts_data = fun_facts
        except ImportError:
            # Fallback to hardcoded data if import fails
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
                'albuquerque': [
                    "hot air balloon", "Sandia Peak Tramway", "Breaking Bad", "Sandia Mountains", "Duke City"
                ],
                'mumbai': [
                    "real estate", "local trains", "Dharavi", "Dhobi Ghat", "Victoria Terminus", "expensive"
                ],
                'new orleans': [
                    "Mardi Gras", "French Quarter", "jazz", "Cajun food", "Bourbon Street", "Plantation homes"
                ],
                'virginia beach': [
                    "beaches", "boardwalk", "surfing", "naval base", "Atlantic Ocean", "outdoor activities"
                ],
                'shanghai': [
                    "skyscrapers", "The Bund", "Shanghai Tower", "Yu Garden", "acrobats", "street food"
                ],
                'auckland': [
                    "harbor", "Sky Tower", "Hobbiton", "volcanoes", "winery tours", "waterfront"
                ],
                'frankfurt': [
                    "airport", "banking", "Frankfurt Book Fair", "Römerberg", "Oktoberfest", "Main River"
                ],
                'zurich': [
                    "banking", "Swiss Alps", "Lake Zurich", "Old Town", "chocolate", "skiing"
                ],
                'dubai': [
                    "Burj Khalifa", "Palm Jumeirah", "shopping malls", "desert safari", "gold souk", "Arabian cuisine"
                ],
                'tokyo': [
                    "Shibuya Crossing", "Mount Fuji", "sushi", "cherry blossoms", "anime", "temples"
                ],
                'rio de janeiro': [
                    "Christ the Redeemer", "Copacabana Beach", "Carnival", "samba", "Ipanema", "feijoada"
                ],
                'abu dhabi': [
                    "Sheikh Zayed Mosque", "Yas Island", "Emirates Palace", "desert", "Arabian Gulf", "falconry"
                ],
                'guadalajara': [
                    "Mariachi music", "tequila", "tacos", "Historic Center", "Tlaquepaque", "basilica"
                ],
                'cape town': [
                    "Table Mountain", "Robben Island", "Cape Point", "wine regions", "beaches", "Victoria & Alfred Waterfront"
                ],
                'bangkok': [
                    "Grand Palace", "Wat Phra Kaew", "Chatuchak Weekend Market", "street food", "Thai massage", "Chao Phraya River"
                ],
                'lisbon': [
                    "Alfama District", "Belém Tower", "Pastéis de Belém", "tram 28", "Fado music", "Tagus River"
                ],
                'seoul': [
                    "Gyeongbokgung Palace", "Myeongdong", "Gangnam Style", "K-pop", "Hanbok", "Bukchon Hanok Village"
                ],
                'buenos aires': [
                    "Tango", "Recoleta Cemetery", "La Boca", "steak houses", "Plaza de Mayo", "Malba Museum"
                ],
                'cairo': [
                    "Pyramids of Giza", "Sphinx", "Nile River", "Khan el-Khalili", "Egyptian Museum", "Islamic Cairo"
                ],
                'amsterdam': [
                    "canals", "bicycles", "Anne Frank House", "Van Gogh Museum", "Rijksmuseum", "Red Light District"
                ],
                'berlin': [
                    "Brandenburg Gate", "Berlin Wall", "Checkpoint Charlie", "museum island", "currywurst", "Tiergarten"
                ],
                'toronto': [
                    "CN Tower", "Niagara Falls", "Maple Leafs", "Hockey Hall of Fame", "Toronto Islands", "CNE"
                ],
                'sydney': [
                    "Opera House", "Harbour Bridge", "Bondi Beach", "Blue Mountains", "Taronga Zoo", "Manly Ferry"
                ],
                'miami': [
                    "South Beach", "Art Deco District", "Ocean Drive", "Cuban cuisine", "Wynwood Walls", "Everglades"
                ],
                'las vegas': [
                    "Strip", "casinos", "Cirque du Soleil", "Bellagio Fountains", "Venetian canals", "Grand Canyon"
                ],
                'austin': [
                    "Live music", "SXSW", "University of Texas", "BBQ", "Lady Bird Lake", "Texas Capitol"
                ],
                'seattle': [
                    "Space Needle", "Coffee culture", "Pike Place Market", "Fremont Troll", "Mount Rainier", "Seahawks"
                ],
                'denver': [
                    "Rocky Mountains", "Red Rocks Park", "Mile High City", "Craft beer", "Skiing", "Colorado State Capitol"
                ],
                'phoenix': [
                    "Desert climate", "Camelback Mountain", "Southwest cuisine", "Golf courses", "Spring training", "Saguaro cacti"
                ],
                'portland or': [
                    "Rose City", "Coffee culture", "Craft beer", "Powell's Books", "Bridges", "Forest Park"
                ],
                'salt lake city': [
                    "Mormons", "Salt Lake Temple", "Ski resorts", "Great Salt Lake", "Temple Square", "Utah Jazz"
                ],
                'san diego': [
                    "Beaches", "Balboa Park", "San Diego Zoo", "Gaslamp Quarter", "Coronado Bridge", "USS Midway"
                ],
                'philadelphia': [
                    "Independence Hall", "Liberty Bell", "Cheesesteaks", "Rocky Steps", "Museum of Art", "Reading Terminal Market"
                ],
                'pittsburgh': [
                    "Steel industry", "Three Rivers", "Pittsburgh Steelers", "Andy Warhol Museum", "Phipps Conservatory", "Incline"
                ],
                'detroit': [
                    "Motown", "Automotive industry", "Detroit Tigers", "GM Renaissance Center", "Belle Isle", "Henry Ford Museum"
                ],
                'cleveland': [
                    "Rock and Roll Hall of Fame", "Cleveland Browns", "Lake Erie", "Cleveland Museum of Art", "West Side Market", "Flats East Bank"
                ],
                'indianapolis': [
                    "Indy 500", "Indianapolis Colts", "Speedway", "Indianapolis Motor Speedway", "Circle City", "Indiana State Museum"
                ],
                'columbus': [
                    "Ohio State Buckeyes", "Short North Arts District", "Columbus Zoo", "German Village", "Arena District", "Scioto Mile"
                ],
                'nashville': [
                    "Country music", "Grand Ole Opry", "Music Row", "Nashville Predators", "Honky Tonks", "Country Music Hall of Fame"
                ],
                'atlanta': [
                    "CNN Headquarters", "Coca-Cola", "Georgia Aquarium", "Atlanta Braves", "Martin Luther King Jr. National Historic Site", "Centennial Olympic Park"
                ],
                'charlotte': [
                    "NASCAR", "Charlotte Hornets", "Bank of America Stadium", "Uptown", "Carowinds", "Billy Graham Library"
                ],
                'raleigh': [
                    "Research Triangle Park", "North Carolina State University", "Raleigh Convention Center", "Historic Oakwood", "North Carolina Museum of Art", "Pullen Park"
                ],
                'durham': [
                    "Duke University", "Durham Bulls", "Research Triangle Park", "Bull City", "Nasher Museum of Art", "Brightleaf Square"
                ],
                'charleston': [
                    "Historic district", "Plantations", "Charleston Harbor", "Shem Creek", "Rainbow Row", "Magnolia Plantation"
                ],
                'savannah': [
                    "Historic district", "River Street", "Bonaventure Cemetery", "Forsyth Park", "Gullah culture", "Savannah College of Art and Design"
                ],
            }  # <--- Added closing bracket
        
        # Check if city exists in fun facts
        if city_lower in fun_facts_data:
            city_keywords = fun_facts_data[city_lower]
        
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
            
            # Albuquerque specific
            'hot air balloon': ('Festivals & Events', 0.95),
            'Sandia Peak Tramway': ('Parks & Nature', 0.95),
            'Breaking Bad': ('Film & Entertainment', 0.95),
            'Sandia Mountains': ('Parks & Nature', 0.95),
            'Duke City': ('Historic Sites', 0.9),
            
            # New Orleans specific - highly distinctive categories
            'Mardi Gras': ('Mardi Gras & Festivals', 0.95),
            'French Quarter': ('French Quarter', 0.95), 
            'jazz': ('Jazz & Blues', 0.95),
            'Cajun food': ('Cajun & Creole Cuisine', 0.95),
            'Bourbon Street': ('Bourbon Street', 0.95),
            'Plantation homes': ('Plantation Tours', 0.95),
            
            # Virginia Beach specific
            'beaches': ('Beaches & Coast', 0.95),
            'boardwalk': ('Entertainment Districts', 0.9),
            'surfing': ('Water Sports', 0.9),
            'naval base': ('Military History', 0.85),
            'Atlantic Ocean': ('Beaches & Coast', 0.95),
            'outdoor activities': ('Parks & Nature', 0.85),
            
            # Shanghai specific
            'skyscrapers': ('Skyscrapers', 0.95),
            'The Bund': ('Architecture & History', 0.95),
            'Shanghai Tower': ('Skyscrapers', 0.95),
            'Yu Garden': ('Gardens & History', 0.95),
            'acrobats': ('Performing Arts', 0.9),
            'street food': ('Street Food', 0.95),
            
            # Auckland specific
            'harbor': ('Harbor & Waterfront', 0.95),
            'Sky Tower': ('Iconic Landmarks', 0.95),
            'Hobbiton': ('Film & Entertainment', 0.95),
            'volcanoes': ('Geological Features', 0.9),
            'winery tours': ('Wine & Vineyards', 0.9),
            'waterfront': ('Harbor & Waterfront', 0.95),
            
            # Edinburgh specific
            'Edinburgh Castle': ('Historic Sites', 0.95),
            'Festival Fringe': ('Festivals & Events', 0.95),
            'Royal Mile': ('Historic Sites', 0.95),
            'UNESCO': ('World Heritage Sites', 0.95),
            'golf': ('Sports & Recreation', 0.9),
            'whiskey': ('Food & Drink', 0.9),
            
            # Dublin specific
            'Guinness Storehouse': ('Breweries & Distilleries', 0.95),
            'pubs': ('Pubs & Nightlife', 0.95),
            'Trinity College': ('Universities & Education', 0.95),
            'Book of Kells': ('Museums & Culture', 0.95),
            'Dublin Castle': ('Historic Sites', 0.95),
            'Ha\'penny Bridge': ('Iconic Landmarks', 0.95),
            
            # Frankfurt specific
            'airport': ('Transportation Hub', 0.95),
            'banking': ('Financial District', 0.95),
            'Frankfurt Book Fair': ('Cultural Events', 0.95),
            'Römerberg': ('Historic Sites', 0.95),
            'Oktoberfest': ('Festivals & Events', 0.95),
            'Main River': ('River & Waterfront', 0.9),
            
            # Zurich specific
            'banking': ('Financial District', 0.95),
            'Swiss Alps': ('Mountains & Nature', 0.95),
            'Lake Zurich': ('Lakes & Waterfront', 0.95),
            'Old Town': ('Historic Sites', 0.95),
            'chocolate': ('Swiss Chocolate', 0.95),
            'skiing': ('Winter Sports', 0.95),
            
            # Lisbon specific
            'Alfama District': ('Historic Districts', 0.95),
            'Belém Tower': ('Historic Sites', 0.95),
            'Pastéis de Belém': ('Food & Bakeries', 0.95),
            'tram 28': ('Transportation & Tours', 0.95),
            'Fado music': ('Music & Culture', 0.95),
            'Tagus River': ('River & Waterfront', 0.95),
            'hills': ('Viewpoints & Scenic', 0.9),
            'yellow trams': ('Transportation & Tours', 0.9),
            'Vasco da Gama Bridge': ('Iconic Landmarks', 0.95),
            'Oceanarium': ('Family & Attractions', 0.95),
            
            # Lisburn specific
            'Cathedral City': ('Religious Sites', 0.95),
            'linen market': ('Markets & Shopping', 0.95),
            'linen': ('Textiles & Crafts', 0.95),
            'Lisburn Castle': ('Historic Sites', 0.95),
            'Festival': ('Festivals & Events', 0.95),
            'Irish Linen Centre': ('Museums & Culture', 0.95),
            
            # Dundonald specific
            'Dundonald Castle': ('Historic Sites', 0.95),
            'Ice Bowl': ('Sports & Recreation', 0.95),
            'ice hockey': ('Sports & Recreation', 0.9),
            'skating': ('Sports & Recreation', 0.9),
            'International Park': ('Entertainment & Events', 0.95),
            'concerts': ('Entertainment & Events', 0.9),
            'hillforts': ('Archaeological Sites', 0.95),
            'Iron Age': ('Historical Sites', 0.9),
            'transport links': ('Transportation Hub', 0.9),
            
            # Bilbao specific
            'Guggenheim Museum': ('Art Museums', 0.95),
            'transporter bridge': ('Historic Landmarks', 0.95),
            'Vizcaya Bridge': ('Historic Landmarks', 0.95),
            'Casco Viejo': ('Historic Districts', 0.95),
            'pintxos': ('Food & Dining', 0.95),
            'Basque': ('Cultural Heritage', 0.95),
            'industrial port': ('Maritime & Port', 0.9),
            'cultural hub': ('Arts & Culture', 0.9),
            
            # Santutxu specific
            'Santutxu Market': ('Markets & Shopping', 0.95),
            'metro connections': ('Transportation Hub', 0.9),
            'local festivals': ('Festivals & Events', 0.95),
            'community spirit': ('Local Culture', 0.9),
            'Basque mountains': ('Mountains & Nature', 0.95),
            'coastline': ('Beaches & Coast', 0.9),
            
            # Mumbai specific
            'real estate': ('Real Estate & Property', 0.95),
            'local trains': ('Transportation Hub', 0.95),
            'Dharavi': ('Cultural Districts', 0.95),
            'Dhobi Ghat': ('Cultural Sites', 0.95),
            'Victoria Terminus': ('Historic Sites', 0.95),
            
            # Navi Mumbai specific
            'planned city': ('Urban Planning', 0.95),
            'infrastructure': ('Infrastructure & Development', 0.95),
            'container port': ('Maritime & Port', 0.95),
            'Jawaharlal Nehru Port Trust': ('Maritime & Port', 0.95),
            'Balaji Temple': ('Religious Sites', 0.95),
            'Nerul': ('Religious Sites', 0.9),
            'Vashi': ('Business Districts', 0.95),
            'commercial hub': ('Business & Commerce', 0.95),
            'decongest': ('Urban Development', 0.9),
            
            # Los Angeles specific
            'museums': ('Museums & Culture', 0.95),
            'Hollywood': ('Entertainment & Film', 0.95),
            'cars': ('Transportation & Automotive', 0.9),
            
            # Bangkok specific
            'Grand Palace': ('Historic Sites', 0.95),
            'Wat Phra Kaew': ('Religious Sites', 0.95),
            'Chatuchak': ('Markets & Shopping', 0.95),
            'Thai massage': ('Wellness & Spa', 0.95),
            'Chao Phraya River': ('River & Waterfront', 0.95),
            
            # Cartagena specific
            'colonial walled city': ('Historic Sites', 0.95),
            'fortress': ('Historic Sites', 0.95),
            'UNESCO': ('World Heritage Sites', 0.95),
            'pirates': ('Historical Tours', 0.9),
            'Getsemaní': ('Cultural Districts', 0.95),
            'Castillo San Felipe': ('Historic Sites', 0.95),
            
            # Chiba specific
            'monorail': ('Transportation & Tech', 0.95),
            'Makuhari Messe': ('Entertainment & Events', 0.95),
            'anime': ('Pop Culture & Anime', 0.95),
            'manga': ('Pop Culture & Anime', 0.95),
            'cargo hub': ('Maritime & Port', 0.9),
            
            # Balaka specific
            'cathedral': ('Religious Sites', 0.95),
            'Catholic': ('Religious Sites', 0.9),
            'Muslim': ('Religious Sites', 0.9),
            'missionary': ('Cultural Heritage', 0.9),
            'Montfort Media': ('Media & Publishing', 0.9),
            
            # Dubai specific
            'Burj Khalifa': ('Skyscrapers', 0.95),
            'Palm Jumeirah': ('Man-made Islands', 0.95),
            'shopping malls': ('Luxury Shopping', 0.95),
            'desert safari': ('Desert Adventures', 0.95),
            'gold souk': ('Gold & Souks', 0.95),
            'Arabian cuisine': ('Arabian Cuisine', 0.95),
            
            # Tokyo specific
            'Shibuya Crossing': ('Entertainment Districts', 0.95),
            'Mount Fuji': ('Mountains & Nature', 0.95),
            'sushi': ('Sushi & Japanese Cuisine', 0.95),
            'cherry blossoms': ('Seasonal Attractions', 0.95),
            'anime': ('Anime & Pop Culture', 0.95),
            'temples': ('Temples & Shrines', 0.95),
            
            # Rio de Janeiro specific
            'Christ the Redeemer': ('Iconic Landmarks', 0.95),
            'Copacabana Beach': ('Beaches & Coast', 0.95),
            'Carnival': ('Festivals & Events', 0.95),
            'samba': ('Music & Dance', 0.95),
            'Ipanema': ('Beaches & Coast', 0.95),
            'feijoada': ('Brazilian Cuisine', 0.95),
            
            # Abu Dhabi specific
            'Sheikh Zayed Mosque': ('Religious Sites', 0.95),
            'Yas Island': ('Theme Parks & Entertainment', 0.95),
            'Emirates Palace': ('Luxury Resorts', 0.95),
            'desert': ('Desert Adventures', 0.95),
            'Arabian Gulf': ('Beaches & Coast', 0.95),
            'falconry': ('Cultural Activities', 0.95),
            
            # Guadalajara specific
            'Mariachi music': ('Music & Culture', 0.95),
            'tequila': ('Tequila & Mexican Spirits', 0.95),
            'tacos': ('Mexican Street Food', 0.95),
            'Historic Center': ('Historic Sites', 0.95),
            'Tlaquepaque': ('Art & Handicrafts', 0.95),
            'basilica': ('Religious Sites', 0.95),
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
        if source == 'fun_facts_distinctive':
            weight = 3.0  # VERY high confidence for distinctive fun fact categories
        elif source == 'fun_facts':
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
        {'icon': '🍽️', 'label': 'Food & Dining 🍕🍷', 'intent': 'dining'},
        {'icon': '🏛️', 'label': 'Historic Sites 🏰📜', 'intent': 'historical'},
        {'icon': '🎨', 'label': 'Art & Culture 🎭🖼️', 'intent': 'culture'},
        {'icon': '🌳', 'label': 'Parks & Nature 🌲🏔️', 'intent': 'nature'},
        {'icon': '🛍️', 'label': 'Shopping 🛒💎', 'intent': 'shopping'},
        {'icon': '🌙', 'label': 'Nightlife 🍸🎵', 'intent': 'nightlife'}
    ]


def register_category_routes(app):
    """Register dynamic categories endpoint."""
    @app.route('/api/categories/<city>', methods=['GET'])
    async def get_categories(city):
        state = app.request.args.get('state', '')
        country = app.request.args.get('country', 'US')
        categories = await get_dynamic_categories(city, state, country)
        return {'categories': categories}
