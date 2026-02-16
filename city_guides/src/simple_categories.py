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
from quart import request

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
redis_client = None  # Will be set from routes.py

# Country name normalizations for Wikipedia lookups
COUNTRY_NORMALIZATIONS = {
    'bosnia': 'Bosnia and Herzegovina',
    'czech republic': 'Czech Republic',
    'czech': 'Czech Republic',
    'uk': 'United Kingdom',
    'usa': 'United States',
    'us': 'United States',
    'uae': 'United Arab Emirates',
    'south korea': 'South Korea',
    'north korea': 'North Korea',
    'russia': 'Russia',
    'china': 'China',
    'india': 'India',
    'brazil': 'Brazil',
    'mexico': 'Mexico',
    'canada': 'Canada',
    'australia': 'Australia',
    'japan': 'Japan',
    'germany': 'Germany',
    'france': 'France',
    'italy': 'Italy',
    'spain': 'Spain',
    'portugal': 'Portugal',
    'netherlands': 'Netherlands',
    'belgium': 'Belgium',
    'switzerland': 'Switzerland',
    'austria': 'Austria',
    'poland': 'Poland',
    'sweden': 'Sweden',
    'norway': 'Norway',
    'denmark': 'Denmark',
    'finland': 'Finland',
    'ireland': 'Ireland',
    'scotland': 'United Kingdom',
    'wales': 'United Kingdom',
    'england': 'United Kingdom'
}

# Cache settings - REDUCED TTL for faster iteration
CACHE_TTL = 30  # 30 seconds for rapid testing
CACHE_VERSION = "v2"  # Increment when logic changes


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
    """Map normalized category to emoji icon - order matters, most specific first."""
    # Most specific first to avoid overlaps - LONGER strings BEFORE shorter substrings
    icons = [
        # ★ DISTINCTIVE Categories - must match BEFORE generic patterns ★
        ('vatican', '🇻🇦'),        # Vatican - unique flag (before religious)
        ('fountain', '⛲'),         # Fountains - Rome special (before fountain matches)
        ('fountains', '⛲'),
        ('industrial heritage', '🏭'),  # BEFORE 'industrial' alone
        ('music heritage', '🎵'),       # BEFORE 'music' alone
        ('musical heritage', '🎵'),
        ('literary heritage', '📚'),    # BEFORE 'literary' alone
        ('religious heritage', '⛪'),    # BEFORE 'religious' alone
        ('castle', '🏰'),          # Castles & Fortifications (before generic)
        ('fortress', '🏰'),
        ('fortification', '🏰'),
        ('citadel', '🏰'),
        ('walled', '🏰'),
        
        # Ancient & Archaeology - must come AFTER distinctive patterns
        ('ancient', '🏛️'),
        ('roman', '🏛️'),
        ('archaeological', '🏛️'),
        ('colosseum', '🏛️'),
        ('pantheon', '🏛️'),
        ('forum', '🏛️'),
        ('ruins', '🏛️'),
        
        # Religious
        ('religious', '⛪'),
        ('cathedral', '⛪'),
        ('church', '⛪'),
        ('basilica', '⛪'),
        ('temple', '🛕'),
        ('mosque', '🕌'),
        ('pilgrimage', '🙏'),
        
        # Art & Culture
        ('art', '🎨'),
        ('museum', '🏛️'),
        ('gallery', '🖼️'),
        ('exhibition', '🎨'),
        
        # Historic Sites
        ('historic', '📜'),
        ('heritage', '🏛️'),
        ('monument', '🗿'),
        ('landmark', '🗿'),
        
        # Industrial (alone)
        ('industrial', '🏭'),
        ('industry', '🏭'),
        
        # Music (alone)
        ('music', '🎵'),
        ('musical', '🎵'),
        
        # Literary (alone)
        ('literary', '📚'),
        ('literature', '📚'),
        
        # Beaches & Coast
        ('beach', '🏖️'),
        ('coast', '🌊'),
        ('seaside', '🏖️'),
        
        # Nature & Parks
        ('park', '🌳'),
        ('garden', '🌺'),
        ('nature', '🌿'),
        ('mountain', '⛰️'),
        ('hiking', '🥾'),
        
        # Food & Dining
        ('restaurant', '🍝'),
        ('dining', '🍝'),
        ('food', '🍴'),
        ('cuisine', '🍜'),
        ('wine', '🍷'),
        ('vineyard', '🍇'),
        ('coffee', '☕'),
        ('cafe', '☕'),
        ('bar', '🍸'),
        
        # Nightlife & Entertainment
        ('nightlife', '🌙'),
        ('club', '🎭'),
        ('music venue', '🎵'),
        ('theatre', '🎭'),
        ('theater', '🎭'),
        
        # Shopping
        ('shopping', '🛍️'),
        ('market', '🛒'),
        ('boutique', '🏪'),
        
        # Sports & Recreation
        ('sport', '⚽'),
        ('stadium', '🏟️'),
        ('recreation', '🎯'),
        
        # Education
        ('university', '🎓'),
        ('education', '🎓'),
        ('school', '🏫'),
        
        # Architecture
        ('architecture', '🏗️'),
        ('skyscraper', '🏙️'),
        ('building', '🏛️'),
        
        # Transportation
        ('transport', '🚇'),
        ('metro', '🚉'),
        ('airport', '✈️'),
        
        # Local specialties
        ('local specialty', '🏆'),
        ('traditional', '🎯'),
        
        # Anime & Electronics
        ('anime', '🎮'),
        ('electronics', '📱'),
        ('gaming', '🎮'),
        ('arcade', '🕹️'),
        ('tech', '💻'),
        ('otaku', '🎌'),
        ('manga', '📚'),
        ('cosplay', '🎭'),
        
        # Fashion & Style
        ('fashion', '👗'),
        ('style', '👠'),
        ('luxury', '💎'),
        ('boutique', '🏪'),
        ('street fashion', '👟'),
        ('youth culture', '🎒'),
        ('trendy', '🔥'),
        
        # Traditional Japanese
        ('traditional', '⛩️'),
        ('temple', '⛩️'),
        ('shrine', '⛩️'),
        ('japanese', '🗾'),
        ('crafts', '🎋'),
        ('cherry blossom', '🌸'),
        ('sakura', '🌸'),
        
        # Art & Museums
        ('art museum', '🎨'),
        ('contemporary art', '🖼️'),
        ('gallery', '🖼️'),
        ('museum', '🏛️'),
        
        # Business & Finance
        ('business', '💼'),
        ('finance', '💰'),
        ('banking', '🏦'),
        ('corporate', '🏢'),
        
        # Nightlife & Entertainment
        ('nightlife', '🌃'),
        ('bar', '🍸'),
        ('club', '🎵'),
        ('live music', '🎶'),
        ('entertainment', '🎪'),
        
        # Transport & Station Areas
        ('transport', '🚆'),
        ('station', '🚉'),
        ('hub', '🎯'),
        
        # Alternative Culture
        ('alternative', '�'),
        ('vintage', '📀'),
        ('secondhand', '♻️'),
        ('subculture', '🎪'),
        
        # Waterfront & Modern
        ('waterfront', '🌊'),
        ('modern', '🏙️'),
        ('architecture', '🏗️'),
        ('bay', '⚓'),
        
        # Local Life
        ('local', '🏘️'),
        ('cafe', '☕'),
        ('bakery', '🥐'),
        ('small shop', '🏪'),
    ]
    
    category_lower = category.lower()
    
    for key, icon in icons:
        if key in category_lower:
            return icon
    
    # Ultimate fallback
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
        
        # Prefer seeded facts via the seeded_facts loader for reliable seed data
        try:
            from city_guides.src.data.seeded_facts import get_city_fun_facts
            # get_city_fun_facts returns a list of facts/keywords for the city
            city_keywords = get_city_fun_facts(city) or []
        except Exception:
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
                'marseille': [
                    "Vieux-Port", "Calanques", "Château d'If", "Notre-Dame de la Garde", "bouillabaisse", 
                    "Mediterranean port", "Le Panier", "MuCEM", "Count of Monte Cristo", "Canebière"
                ],
                'kampala': [
                    "Seven Hills", "Lake Victoria", "Uganda Museum", "Owino Market", "Kabalagala", 
                    "political heart", "economic hub", "equator", "spring-like climate", "nightlife"
                ],
                'tokchon': [
                    "Sungri Motor Plant", "automobile factory", "fertile valley", "agricultural production", 
                    "hot springs", "limestone caves", "South Pyongan Province", "rice and maize"
                ],
                'tanchon': [
                    "Sungri Motor Plant", "automobile factory", "fertile valley", "agricultural production", 
                    "hot springs", "limestone caves", "South Pyongan Province", "rice and maize"
                ],
                'faro': [
                    "Ria Formosa", "natural park", "lagoons", "islands", "historic old town", 
                    "cobblestone streets", "medieval architecture", "moorish times", "faro cathedral", 
                    "bone chapel", "stunning beaches", "ilha deserta", "ilha da barreta", "algarve region", 
                    "vibrant marina", "waterfront dining", "maritime history", "port city"
                ],
                'tegucigalpa': [
                    "capital city", "honduras", "mountain valley", "3300 feet elevation", "basilica of suyapa",
                    "catholic pilgrimage", "virgin of suyapa", "colonial spanish architecture", "historic center",
                    "cloud forests", "mountainous landscapes", "honduran cuisine", "baleadas", "pastelitos",
                    "financial center", "political center", "colonial architecture"
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
        
        # Check if city exists in fun facts (fallback map)
        if 'fun_facts_data' in locals() and city_lower in fun_facts_data:
            city_keywords = fun_facts_data[city_lower]
        elif 'city_keywords' not in locals():
            city_keywords = []
        
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
            'Trevi': ('Iconic Fountains', 0.95),
            'fountains': ('Iconic Fountains', 0.9),
            
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
            
            # Marseille specific - highly distinctive categories
            'Vieux-Port': ('Old Port & Harbor', 0.95),
            'Calanques': ('Calanques & Coast', 0.95),
            'Château d\'If': ('Island Fortresses', 0.95),
            'Notre-Dame de la Garde': ('Basilicas & Religious', 0.95),
            'bouillabaisse': ('Bouillabaisse & Seafood', 0.95),
            'Mediterranean port': ('Port & Maritime', 0.95),
            'Le Panier': ('Historic Districts', 0.95),
            'MuCEM': ('Museums & Culture', 0.95),
            'Count of Monte Cristo': ('Literary History', 0.95),
            'Canebière': ('Historic Streets', 0.9),
            
            # Kampala specific - highly distinctive categories
            'Seven Hills': ('Hills & Viewpoints', 0.95),
            'Lake Victoria': ('Lakes & Waterfront', 0.95),
            'Uganda Museum': ('Museums & Culture', 0.95),
            'Owino Market': ('Markets & Shopping', 0.95),
            'Kabalagala': ('Nightlife & Entertainment', 0.95),
            'political heart': ('Government & Politics', 0.95),
            'economic hub': ('Business & Finance', 0.9),
            'equator': ('Geographical Features', 0.95),
            'nightlife': ('Nightlife & Entertainment', 0.9),
            
            # Tokchon specific - highly distinctive categories
            'Sungri Motor Plant': ('Industrial Sites', 0.95),
            'automobile factory': ('Industrial Sites', 0.95),
            'fertile valley': ('Agriculture & Farming', 0.95),
            'agricultural production': ('Agriculture & Farming', 0.9),
            'hot springs': ('Natural Springs', 0.95),
            'limestone caves': ('Natural Caves', 0.95),
            'South Pyongan Province': ('Regional Information', 0.9),
            'rice and maize': ('Agriculture & Farming', 0.85),
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
            
            # Faro specific
            'ria formosa': ('Natural Parks & Wetlands', 0.95),
            'natural park': ('Nature Reserves', 0.95),
            'lagoons': ('Coastal Lagoons', 0.95),
            'islands': ('Island Hopping', 0.95),
            'historic old town': ('Historic Districts', 0.95),
            'cobblestone streets': ('Historic Streets', 0.95),
            'medieval architecture': ('Medieval Heritage', 0.95),
            'moorish times': ('Moorish Heritage', 0.95),
            'faro cathedral': ('Religious Sites', 0.95),
            'bone chapel': ('Unique Attractions', 0.95),
            'stunning beaches': ('Beaches & Coast', 0.95),
            'ilha deserta': ('Deserted Islands', 0.95),
            'ilha da barreta': ('Barrier Islands', 0.95),
            'algarve region': ('Regional Exploration', 0.95),
            'vibrant marina': ('Marina & Waterfront', 0.95),
            'waterfront dining': ('Seaside Dining', 0.95),
            'maritime history': ('Maritime Heritage', 0.95),
            'port city': ('Port Cities', 0.95),
            
            # Tegucigalpa specific
            'basilica of suyapa': ('Religious Sites', 0.95),
            'catholic pilgrimage': ('Pilgrimage Sites', 0.95),
            'virgin of suyapa': ('Religious Icons', 0.95),
            'colonial spanish architecture': ('Colonial Architecture', 0.95),
            'historic center': ('Historic Districts', 0.95),
            'cloud forests': ('Cloud Forests & Nature', 0.95),
            'mountainous landscapes': ('Mountain Scenery', 0.9),
            'honduran cuisine': ('Local Cuisine', 0.95),
            'baleadas': ('Street Food', 0.9),
            'pastelitos': ('Local Snacks', 0.9),
            'financial center': ('Business Districts', 0.85),
            'political center': ('Government Districts', 0.85),
            'capital city': ('Capital Cities', 0.9),
            
            # Hong Kong specific
            'star ferry': ('Harbour Cruises', 0.95),
            'victoria harbour': ('Harbour Views', 0.95),
            'mid-levels escalator': ('Unique Transport', 0.95),
            'skyscrapers': ('Skyscraper Viewing', 0.95),
            'vertical city': ('Urban Exploration', 0.9),
            'peak tram': ('Scenic Transport', 0.95),
            'victoria peak': ('Panoramic Views', 0.95),
            'dim sum': ('Dim Sum & Cantonese', 0.95),
            'dumplings': ('Dumpling Houses', 0.9),
            'big buddha': ('Buddhist Sites', 0.95),
            'lantau island': ('Island Excursions', 0.95),
            'symphony of lights': ('Light Shows', 0.95),
            'temple street night market': ('Night Markets', 0.95),
            'night market': ('Street Shopping', 0.9),
            'ferry': ('Ferry Rides', 0.9),
            'harbour': ('Waterfront', 0.9),
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
async def fetch_wikipedia_full_content(city: str, state: str = "", country: str = "") -> str:
    """Fetch full Wikipedia article content for better category extraction.
    Uses state/country for disambiguation of small towns."""
    try:
        import aiohttp
        
        # Normalize country names for Wikipedia
        normalized_country = COUNTRY_NORMALIZATIONS.get(country.lower(), country) if country else ""
        
        # Try variations with BASE CITY FIRST, then disambiguation
        search_variations = [city]  # Try base city name first
        if state and normalized_country:
            search_variations.append(f"{city}, {state}")
        if state:
            search_variations.append(f"{city}, {state}")
        if normalized_country:
            search_variations.append(f"{city}, {normalized_country}")
        
        for search_title in search_variations:
            # URL encode the search title
            from urllib.parse import quote
            encoded_title = quote(search_title.replace(" ", "_"))
            url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext&exlimit=1&titles={encoded_title}&format=json"
            headers = {'User-Agent': 'TravelLand/1.0 (Educational)'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pages = data.get('query', {}).get('pages', {})
                        for page_id, page_data in pages.items():
                            content = page_data.get('extract', '')
                            if content and len(content) > 200:
                                print(f"[WIKI] Got full content for {search_title}: {len(content)} chars")
                                return content
        
        # Fallback to summary API if full content fails
        return await simple_wikipedia_fetch(city, state, country)
    except Exception as e:
        print(f"[WIKI] Full content fetch error: {e}")
        return await simple_wikipedia_fetch(city, state, country)


# Simple Wikipedia fetch for testing
async def simple_wikipedia_fetch(city: str, state: str = "", country: str = "") -> str:
    """Simple Wikipedia summary fetch with state/country support."""
    try:
        import aiohttp
        from urllib.parse import quote
        
        # Try variations - city name alone first (works for Mostar)
        search_variations = [city]
        if state:
            search_variations.append(f"{city}, {state}")
        if country:
            search_variations.append(f"{city}, {country}")
        
        headers = {'User-Agent': 'TravelLand/1.0 (Educational)'}
        async with aiohttp.ClientSession() as session:
            for search_title in search_variations:
                # Skip empty variations
                if not search_title or search_title.endswith(', '):
                    continue
                    
                encoded = quote(search_title.replace(" ", "_"))
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
                
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get('extract', '')
                        if content:
                            print(f"[WIKI] Got summary for {search_title}")
                            return content
                    else:
                        print(f"[WIKI] HTTP {resp.status} for {search_title}")
    except Exception as e:
        print(f"[WIKI] Simple fetch error: {e}")
    return ""


async def extract_from_city_guide(city: str, state: str = "", country: str = "") -> List[Dict[str, Any]]:
    """Extract categories from the Wikipedia city guide content using keyword enrichment."""
    categories = []
    city_lower = city.lower().strip()
    
    try:
        import os
        import json
        
        # Load keyword mapping from JSON (DDD-compliant)
        mapping_path = os.path.join(os.path.dirname(__file__), '../data/category_keywords.json')
        with open(mapping_path, 'r') as f:
            keyword_map = json.load(f)
        
        # Use FULL Wikipedia content for better extraction
        content = await fetch_wikipedia_full_content(city, state, country)
        if content:
            guide_text = content.lower()
            print(f"[WIKI] Analyzing {len(content)} chars for {city}")
            
            # DDD-compliant keyword enrichment from Wikipedia content
            for cat, keywords in keyword_map.items():
                for kw in keywords:
                    if kw.lower() in guide_text:
                        categories.append({
                            'category': cat.title(),
                            'confidence': 0.8,
                            'source': 'city_guide',
                            'matched': kw
                        })
                        break  # One match per category is enough
        else:
            print(f"[WIKI] No content found for {city}")
            # Fallback to category page extraction
            category_cats = await extract_from_wikipedia_category(city, state, country)
            categories.extend(category_cats)
        
        print(f"[WIKI] Extracted {len(categories)} categories for {city}: {[c['category'] for c in categories]}")
            
    except Exception as e:
        print(f"[CITY_GUIDE] Error: {e}")
    
    return categories


async def extract_from_wikipedia_category(city: str, state: str = "", country: str = "") -> List[Dict[str, Any]]:
    """Extract categories from Wikipedia category page subcategories."""
    categories = []
    try:
        import aiohttp
        from urllib.parse import quote
        import os
        # Load keyword mapping from JSON (DDD-compliant)
        mapping_path = os.path.join(os.path.dirname(__file__), '../data/category_keywords.json')
        with open(mapping_path, 'r') as f:
            keyword_map = json.load(f)

        # Use categorymembers API to get subcategories
        category_title = f"Category:{city}"
        encoded_title = quote(category_title)
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle={encoded_title}&cmtype=subcat&format=json&origin=*"
        headers = {'User-Agent': 'TravelLand/1.0 (Educational)'}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    members = data.get('query', {}).get('categorymembers', [])
                    print(f"[WIKI_CATEGORY] Found {len(members)} subcategories for {city}")
                    for member in members:
                        subcat_name = member.get('title', '').replace('Category:', '').strip()
                        # DDD-compliant keyword enrichment
                        enriched = False
                        for cat, keywords in keyword_map.items():
                            for kw in keywords:
                                if kw.lower() in subcat_name.lower():
                                    categories.append({'category': cat.title(), 'confidence': 0.8, 'source': 'keyword_enrichment', 'matched': subcat_name})
                                    enriched = True
                                    break
                            if enriched:
                                break
                        if not enriched:
                            categories.append({'category': subcat_name, 'confidence': 0.7, 'source': 'wikipedia_category'})
                    print(f"[WIKI_CATEGORY] Extracted {len(categories)} categories (enriched+raw) from Wikipedia for {city}")
    except Exception as e:
        print(f"[WIKI_CATEGORY] Error: {e}")
    return categories


async def extract_from_wikipedia_sections(city: str, state: str = "", country: str = "") -> List[Dict[str, Any]]:
    """Extract categories from Wikipedia page with comprehensive analysis.

    Extended behavior:
    - If the city page is sparse, also search for 'Tourism in <country>' pages and parse any section that mentions the city.
    - Additionally query `Category:Tourist attractions in <city>` for complementary signals.
    """
    categories = []
    
    try:
        if WIKI_AVAILABLE:
            title = f"{city}"
            if state:
                title += f", {state}"

            async with aiohttp.ClientSession() as session:
                # Primary: Get full page content with sections for the city page
                params = {
                    'action': 'parse',
                    'page': title,
                    'prop': 'sections|text|categories',
                    'format': 'json',
                    'origin': '*'
                }
                async with session.get('https://en.wikipedia.org/w/api.php', params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Extract categories from the city's own page (existing heuristics)
                        sections = data.get('parse', {}).get('sections', [])
                        for section in sections:
                            line = section.get('line', '').lower()

                            # Comprehensive category mapping (unchanged heuristics)
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
                            if any(word in line for word in ['wine', 'vineyard', 'winery', 'viticulture']):
                                categories.append({'category': 'Wine & Vineyards', 'confidence': 0.9, 'source': 'wikipedia'})

                        # Extract from page content text
                        page_text = data.get('parse', {}).get('text', {}).get('*', '').lower()

                        # Look for key phrases in content (existing heuristics)
                        if any(phrase in page_text for phrase in ['world heritage site', 'unesco', 'historic monument']):
                            categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'wikipedia'})
                        if any(phrase in page_text for phrase in ['art gallery', 'museum', 'cultural center']):
                            categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'wikipedia'})
                        if any(phrase in page_text for phrase in ['wine region', 'vineyard', 'winery', 'wine production']):
                            categories.append({'category': 'Wine & Vineyards', 'confidence': 0.9, 'source': 'wikipedia'})

                        # Beaches validation - stricter criteria
                        beach_phrases = ['beaches', 'coastline', 'seaside', 'oceanfront', 'beach resort', 'popular beaches']
                        beach_mentions = sum(page_text.count(phrase) for phrase in beach_phrases)
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

                # --- Extended behavior: if the city's page is sparse or doesn't include tourism text,
                # check for country-level 'Tourism in <country>' pages and category members.
                need_additional = len(categories) < 3

                # 1) Search for 'tourism <city>' or 'Tourism in <country>' pages that mention the city
                if need_additional:
                    try:
                        search_params = {
                            'action': 'query',
                            'list': 'search',
                            'srsearch': f'tourism {city}',
                            'srlimit': 8,
                            'format': 'json',
                            'origin': '*'
                        }
                        async with session.get('https://en.wikipedia.org/w/api.php', params=search_params, timeout=8) as sresp:
                            if sresp.status == 200:
                                sdata = await sresp.json()
                                hits = sdata.get('query', {}).get('search', [])
                                for hit in hits:
                                    title_hit = hit.get('title')
                                    # Parse the candidate page and look for sections mentioning the city
                                    pparams = {'action': 'parse', 'page': title_hit, 'prop': 'sections|text', 'format': 'json', 'origin': '*'}
                                    async with session.get('https://en.wikipedia.org/w/api.php', params=pparams, timeout=8) as ph:
                                        if ph.status != 200:
                                            continue
                                        pjson = await ph.json()
                                        sections = pjson.get('parse', {}).get('sections', [])
                                        for section in sections:
                                            sec_line = section.get('line', '')
                                            if city.lower() in sec_line.lower():
                                                # reuse header heuristics
                                                line = sec_line.lower()
                                                if any(word in line for word in ['history', 'heritage', 'historic', 'museum', 'landmark']):
                                                    categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'wikipedia_tourism_page', 'matched_section': sec_line})
                                                if any(word in line for word in ['culture', 'art', 'gallery', 'museum']):
                                                    categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'wikipedia_tourism_page', 'matched_section': sec_line})
                                        # Also inspect the section text body for city mentions and key phrases
                                        page_text = pjson.get('parse', {}).get('text', {}).get('*', '').lower()
                                        if city.lower() in page_text and any(kw in page_text for kw in ['museum', 'mosque', 'bridge', 'castle', 'historic']):
                                            categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'wikipedia_tourism_page', 'matched_page': title_hit})
                    except Exception:
                        pass

                # 2) Query Category:Tourist attractions in <city>
                try:
                    from urllib.parse import quote
                    cat_title = f"Category:Tourist attractions in {city}"
                    encoded_title = quote(cat_title)
                    cm_url = f"https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle={encoded_title}&cmtype=page&cmlimit=50&format=json&origin=*"
                    async with session.get(cm_url, timeout=8) as cmr:
                        if cmr.status == 200:
                            cmdata = await cmr.json()
                            members = cmdata.get('query', {}).get('categorymembers', [])
                            if members:
                                # If the category exists and contains pages, it's a strong signal for attractions
                                categories.append({'category': 'Historic Sites', 'confidence': 0.85, 'source': 'wikipedia_category_tourist_attractions', 'count': len(members)})
                                # Inspect member titles for additional signals
                                for mem in members[:20]:
                                    title_mem = (mem.get('title') or '').lower()
                                    if any(k in title_mem for k in ['museum', 'gallery', 'church', 'mosque', 'bridge', 'fort', 'castle', 'palace']):
                                        categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'wikipedia_category_member', 'matched': title_mem})
                except Exception:
                    pass
    except Exception as e:
        print(f"[WIKIPEDIA] Error: {e}")
    
    return categories


async def extract_distinctive_categories(city: str, state: str = "", country: str = "") -> List[Dict[str, Any]]:
    """
    Extract DISTINCTIVE categories by analyzing what makes this city UNIQUE.
    Not generic categories - specific to this city's character.
    """
    categories = []
    
    try:
        # Fetch Wikipedia content with state/country for small towns
        content = await fetch_wikipedia_full_content(city, state, country)
        if not content or len(content) < 200:
            normalized_country = COUNTRY_NORMALIZATIONS.get(country.lower(), country) if country else ""
            print(f"[DISTINCTIVE] No Wikipedia content for {city}{', ' + state if state else ''}{', ' + normalized_country if normalized_country else ''}")
            return categories
            
        text_lower = content.lower()
        
        # Define distinctive feature mappings
        distinctive_mappings = [
            # Industrial heritage
            {
                'triggers': ['industrial revolution', 'manufacturing', 'factory', 'steel', 'ironworks', 
                           'textile industry', 'mill town', 'industrial heritage', 'jewellery quarter'],
                'category': 'Industrial Heritage',
                'confidence': 0.95
            },
            # Canals & Waterways  
            {
                'triggers': ['canal', 'waterway', 'navigable', 'canal network', 'barge', 'locks'],
                'category': 'Canals & Waterways',
                'confidence': 0.90
            },
            # Music Heritage
            {
                'triggers': ['birthplace of', 'music scene', 'band formed', 'musical heritage', 
                           'live music capital', 'jazz heritage'],
                'category': 'Music Heritage',
                'confidence': 0.90
            },
            # Literary Heritage
            {
                'triggers': ['author lived', 'writer born', 'literary heritage', 'poet', 
                           'novel set in', 'famous author'],
                'category': 'Literary Heritage',
                'confidence': 0.90
            },
            # Religious Heritage
            {
                'triggers': ['pilgrimage', 'sacred site', 'religious significance', 'holy city',
                           'cathedral city', 'monastic'],
                'category': 'Religious Heritage',
                'confidence': 0.90
            },
            # Maritime Heritage
            {
                'triggers': ['port city', 'shipbuilding', 'naval history', 'maritime museum',
                           'historic harbor', 'fishing port'],
                'category': 'Maritime Heritage',
                'confidence': 0.90
            },
            # Railway Heritage
            {
                'triggers': ['railway junction', 'train station', 'steam railway', 'railway museum',
                           'first railway', 'locomotive works'],
                'category': 'Railway Heritage',
                'confidence': 0.90
            },
            # Victorian Architecture
            {
                'triggers': ['victorian architecture', 'victorian era', 'victorian buildings',
                           '19th century architecture'],
                'category': 'Victorian Architecture',
                'confidence': 0.85
            },
            # Street Art
            {
                'triggers': ['street art', 'graffiti art', 'mural', 'urban art district'],
                'category': 'Street Art & Murals',
                'confidence': 0.85
            },
            # Food Specialties
            {
                'triggers': ['famous for', 'local specialty', 'traditional dish', 'cuisine known',
                           'signature food', 'invented here'],
                'category': 'Local Food Specialties',
                'confidence': 0.90
            },
            # University Town
            {
                'triggers': ['university town', 'college town', 'student population', 'academic center'],
                'category': 'University & Academia',
                'confidence': 0.85
            },
            # Castles & Fortifications - routes to RAG for intelligent architecture answers
            {
                'triggers': ['castle', 'fortress', 'fortification', 'walled city', 'medieval fort', 'citadel'],
                'category': 'Castles & Fortifications',
                'confidence': 0.90
            },
        ]
        
        # Check each distinctive feature
        for mapping in distinctive_mappings:
            triggers = mapping['triggers']
            # Count how many trigger phrases appear
            matches = sum(1 for trigger in triggers if trigger in text_lower)
            
            if matches >= 1:  # At least one match
                categories.append({
                    'category': mapping['category'],
                    'confidence': mapping['confidence'],
                    'source': 'distinctive_features',
                    'evidence': f"Found {matches} matching phrases"
                })
                print(f"[DISTINCTIVE] Found '{mapping['category']}' for {city}")
        
        print(f"[DISTINCTIVE] Extracted {len(categories)} distinctive categories for {city}")
        
    except Exception as e:
        print(f"[DISTINCTIVE] Error: {e}")
    
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


# Semantic category groups - keep highest scoring category from each group
CATEGORY_GROUPS = {
    # Food categories - keep one
    'food': ['Food & Dining', 'Local Food Specialties', 'Michelin Dining', 'Food & Drink', 
             'Street Food', 'Cajun & Creole Cuisine', 'Brazilian Cuisine', 'Mexican Street Food',
             'Sushi & Japanese Cuisine', 'Food & Bakeries', 'Seafood', 'Bouillabaisse & Seafood'],
    
    # Art categories - keep one
    'art': ['Art & Culture', 'Museums & Culture', 'Art Museums', 'Cultural Heritage', 
            'Arts & Culture', 'Cultural Districts'],
    
    # Nature categories - keep one
    'nature': ['Parks & Nature', 'Parks & Gardens', 'Nature', 'Green Spaces'],
    
    # Historic categories - keep one
    'history': ['Historic Sites', 'Historic Districts', 'Historical Sites', 'Historic Landmarks'],
    
    # Religious categories - keep one
    'religious': ['Religious Sites', 'Religious Heritage', 'Religious Icons', 'Pilgrimage Sites'],
    
    # Music categories - keep one
    'music': ['Music Heritage', 'Jazz & Blues', 'Music & Culture', 'Music & Dance'],
    
    # Water categories - keep one
    'water': ['Beaches & Coast', 'Coast', 'Seaside'],
}


def _get_category_group(cat_name: str) -> str:
    """Get the semantic group for a category name."""
    cat_lower = cat_name.lower()
    for group_key, group_cats in CATEGORY_GROUPS.items():
        for gc in group_cats:
            if gc.lower() in cat_lower or cat_lower in gc.lower():
                return group_key
    return cat_lower  # Return itself as unique key


def combine_and_score_categories(all_categories: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Combine categories from all sources with intelligent scoring and deduplication."""
    category_scores = {}
    group_scores = {}  # Track best score per semantic group
    
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
        elif source == 'distinctive_features':
            weight = 2.5  # HIGH confidence for Wikipedia distinctive features
        elif source == 'fun_facts':
            weight = 1.2  # High confidence for curated facts
        elif source == 'city_guide':
            weight = 1.0  # Good confidence
        elif source == 'wikipedia':
            weight = 0.9  # Good but general
        elif source == 'ddgs':
            weight = 0.7  # Current but less reliable
            
        score = confidence * weight
        category_scores[cat_name]['total_score'] += score
        category_scores[cat_name]['sources'].append(source)
        category_scores[cat_name]['count'] += 1
        
        # Track best per semantic group
        group_key = _get_category_group(cat_name)
        if group_key not in group_scores or category_scores[cat_name]['total_score'] > group_scores[group_key]['score']:
            group_scores[group_key] = {
                'category': cat_name,
                'score': category_scores[cat_name]['total_score']
            }
    
    # Sort by total score and convert to final format
    sorted_categories = sorted(
        category_scores.items(),
        key=lambda x: x[1]['total_score'],
        reverse=True
    )
    
    final_categories = []
    seen_groups = set()
    
    for cat_name, scores in sorted_categories[:12]:  # Top 12 categories
        group_key = _get_category_group(cat_name)
        
        # Skip if we've already used a category from this semantic group
        if group_key in seen_groups:
            continue
        seen_groups.add(group_key)
        
        intent = cat_name.lower().replace(' & ', '_').replace(' ', '_')
        final_categories.append({
            'icon': get_category_icon(cat_name.lower()),
            'label': cat_name,
            'intent': intent,
            'score': round(scores['total_score'], 2),
            'sources': scores['sources']
        })
    
    return final_categories


async def get_neighborhood_specific_categories(city: str, neighborhood: str, state: str = "") -> List[Dict[str, Any]]:
    """Generate categories based on neighborhood-specific content and characteristics."""
    categories = []
    
    try:
        print(f"[NEIGHBORHOOD-CATEGORIES] Analyzing {neighborhood}, {city}")
        print(f"[NEIGHBORHOOD-CATEGORIES] Normalized neighborhood: {neighborhood.lower().replace('-', '').replace(' ', '')}")
        
        # Neighborhood name-based heuristics for common patterns
        neighborhood_lower = neighborhood.lower().replace('-', '').replace(' ', '')  # Normalize for matching
        city_lower = city.lower()
        print(f"[NEIGHBORHOOD-CATEGORIES] Checking patterns against: '{neighborhood_lower}'")
        
        # Historic neighborhoods (common patterns)
        if any(word in neighborhood_lower for word in ['old town', 'historic', 'quartier', 'distrito', 'ciudad vieja', 'altstadt', 'vieille ville']):
            categories.append({'category': 'Historic Sites', 'confidence': 0.9, 'source': 'neighborhood_name'})
            categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'neighborhood_name'})
        
        # University areas
        if any(word in neighborhood_lower for word in ['university', 'campus', 'academic', 'student', 'college']):
            categories.append({'category': 'University & Academia', 'confidence': 0.9, 'source': 'neighborhood_name'})
        
        # Beach/coastal neighborhoods
        if any(word in neighborhood_lower for word in ['beach', 'coast', 'seaside', 'waterfront', 'playa', 'costa']):
            categories.append({'category': 'Beaches & Coast', 'confidence': 0.9, 'source': 'neighborhood_name'})
        
        # Entertainment districts
        if any(word in neighborhood_lower for word in ['entertainment', 'nightlife', 'district', 'quartier', 'shibuya', 'ginza', 'times square', 'sukhumvit']):
            categories.append({'category': 'Entertainment Districts', 'confidence': 0.8, 'source': 'neighborhood_name'})
        
        # Shopping areas
        if any(word in neighborhood_lower for word in ['market', 'bazaar', 'shopping', 'mall', 'boutique', 'souk']):
            categories.append({'category': 'Shopping', 'confidence': 0.8, 'source': 'neighborhood_name'})
        
        # Food-specific neighborhoods
        if any(word in neighborhood_lower for word in ['food', 'dining', 'restaurant', 'cuisine', 'gastronomy']):
            categories.append({'category': 'Food & Dining', 'confidence': 0.9, 'source': 'neighborhood_name'})
        
        # Parks/nature
        if any(word in neighborhood_lower for word in ['park', 'garden', 'nature', 'green', 'forest', 'mountain', 'central park']):
            categories.append({'category': 'Parks & Nature', 'confidence': 0.8, 'source': 'neighborhood_name'})
        
        # Industrial/railway
        if any(word in neighborhood_lower for word in ['industrial', 'factory', 'railway', 'station', 'port', 'harbor']):
            categories.append({'category': 'Industrial Heritage', 'confidence': 0.7, 'source': 'neighborhood_name'})
        
        # Castles/fortifications
        if any(word in neighborhood_lower for word in ['castle', 'fort', 'fortification', 'palace', 'citadel']):
            categories.append({'category': 'Castles & Fortifications', 'confidence': 0.8, 'source': 'neighborhood_name'})
        
        # Railway specific
        if any(word in neighborhood_lower for word in ['railway', 'train', 'station', 'railroad']):
            categories.append({'category': 'Railway Heritage', 'confidence': 0.7, 'source': 'neighborhood_name'})
        
        # Anime & Electronics specific for Tokyo
        if any(word in neighborhood_lower for word in ['akihabara', 'ota', 'kanda']):
            categories.append({'category': 'Anime & Electronics', 'confidence': 0.95, 'source': 'city_specific'})
            categories.append({'category': 'Gaming & Arcades', 'confidence': 0.9, 'source': 'city_specific'})
            categories.append({'category': 'Tech Culture', 'confidence': 0.8, 'source': 'city_specific'})
        
        # Fashion & Youth Culture specific for Tokyo
        if any(word in neighborhood_lower for word in ['harajuku', 'omotesando', 'shibuya']):
            categories.append({'category': 'Fashion & Style', 'confidence': 0.95, 'source': 'city_specific'})
            categories.append({'category': 'Youth Culture', 'confidence': 0.9, 'source': 'city_specific'})
            categories.append({'category': 'Street Fashion', 'confidence': 0.85, 'source': 'city_specific'})
        
        # Traditional Culture
        if any(word in neighborhood_lower for word in ['asakusa', 'ueno', 'yanaka']):
            categories.append({'category': 'Traditional Culture', 'confidence': 0.95, 'source': 'city_specific'})
            categories.append({'category': 'Temples & Shrines', 'confidence': 0.9, 'source': 'city_specific'})
            categories.append({'category': 'Japanese Crafts', 'confidence': 0.8, 'source': 'city_specific'})
        
        # Art & Museums
        if any(word in neighborhood_lower for word in ['ueno', 'roppongi']):
            categories.append({'category': 'Art Museums', 'confidence': 0.95, 'source': 'city_specific'})
            categories.append({'category': 'Contemporary Art', 'confidence': 0.9, 'source': 'city_specific'})
        
        # Business & Finance
        if any(word in neighborhood_lower for word in ['shinbashi', 'toranomon', 'kasumigaseki']):
            categories.append({'category': 'Business District', 'confidence': 0.95, 'source': 'city_specific'})
            categories.append({'category': 'Finance & Banking', 'confidence': 0.9, 'source': 'city_specific'})
        
        # Luxury Shopping
        if any(word in neighborhood_lower for word in ['ginza', 'omotesando']):
            categories.append({'category': 'Luxury Shopping', 'confidence': 0.95, 'source': 'city_specific'})
            categories.append({'category': 'High Fashion', 'confidence': 0.9, 'source': 'city_specific'})
        
        # Nightlife & Entertainment
        if any(word in neighborhood_lower for word in ['shinjuku', 'roppongi', 'shibuya', 'kabukicho']):
            categories.append({'category': 'Nightlife', 'confidence': 0.95, 'source': 'city_specific'})
            categories.append({'category': 'Bars & Clubs', 'confidence': 0.9, 'source': 'city_specific'})
            categories.append({'category': 'Live Music', 'confidence': 0.8, 'source': 'city_specific'})
        
        # Parks & Recreation
        if any(word in neighborhood_lower for word in ['shinjuku', 'ueno', 'meguro', 'komazawa']):
            categories.append({'category': 'Parks & Gardens', 'confidence': 0.9, 'source': 'city_specific'})
            categories.append({'category': 'Cherry Blossoms', 'confidence': 0.85, 'source': 'city_specific'})
        
        # Station/Transport Hub Areas
        if any(word in neighborhood_lower for word in ['tokyostation', 'shinagawa', 'shibuya', 'shinjuku']):
            categories.append({'category': 'Transport Hub', 'confidence': 0.9, 'source': 'city_specific'})
            categories.append({'category': 'Station Shopping', 'confidence': 0.8, 'source': 'city_specific'})
        
        # Subculture & Alternative
        if any(word in neighborhood_lower for word in ['kōenji', 'shimokitazawa', 'kichijoji']):
            categories.append({'category': 'Alternative Culture', 'confidence': 0.95, 'source': 'city_specific'})
            categories.append({'category': 'Vintage & Secondhand', 'confidence': 0.9, 'source': 'city_specific'})
            categories.append({'category': 'Live Music Venues', 'confidence': 0.85, 'source': 'city_specific'})
        
        # Waterfront & Bay Areas
        if any(word in neighborhood_lower for word in ['odaiba', 'toyosu', 'koto']):
            categories.append({'category': 'Waterfront', 'confidence': 0.9, 'source': 'city_specific'})
            categories.append({'category': 'Modern Architecture', 'confidence': 0.85, 'source': 'city_specific'})
            categories.append({'category': 'Entertainment Complexes', 'confidence': 0.8, 'source': 'city_specific'})
        
        # Traditional Crafts & Local Industry
        if any(word in neighborhood_lower for word in ['sumida', 'taito']):
            categories.append({'category': 'Traditional Crafts', 'confidence': 0.9, 'source': 'city_specific'})
            categories.append({'category': 'Local Industry', 'confidence': 0.8, 'source': 'city_specific'})
        
        # Residential with Local Flavor
        if any(word in neighborhood_lower for word in ['setagaya', 'meguro', 'minato', 'suginami']):
            categories.append({'category': 'Local Life', 'confidence': 0.8, 'source': 'city_specific'})
            categories.append({'category': 'Cafes & Bakeries', 'confidence': 0.85, 'source': 'city_specific'})
            categories.append({'category': 'Small Shops', 'confidence': 0.8, 'source': 'city_specific'})
        
        elif 'paris' in city_lower:
            # Paris-specific patterns
            if any(word in neighborhood_lower for word in ['marais', 'latin', 'saint-germain', 'montmartre']):
                categories.append({'category': 'Historic Sites', 'confidence': 0.9, 'source': 'city_specific'})
                categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'city_specific'})
            if any(word in neighborhood_lower for word in ['champs-elysées', 'opera', 'saint-honoré']):
                categories.append({'category': 'Shopping', 'confidence': 0.8, 'source': 'city_specific'})
            if any(word in neighborhood_lower for word in ['le marais', 'bastille', 'canal saint-martin']):
                categories.append({'category': 'Entertainment Districts', 'confidence': 0.8, 'source': 'city_specific'})
        
        elif 'london' in city_lower:
            # London-specific patterns
            if any(word in neighborhood_lower for word in ['covent garden', 'soho', 'camden', 'shoreditch']):
                categories.append({'category': 'Entertainment Districts', 'confidence': 0.9, 'source': 'city_specific'})
            if any(word in neighborhood_lower for word in ['westminster', 'city of london', 'southwark']):
                categories.append({'category': 'Historic Sites', 'confidence': 0.9, 'source': 'city_specific'})
            if any(word in neighborhood_lower for word in ['notting hill', 'kensington', 'knightsbridge']):
                categories.append({'category': 'Shopping', 'confidence': 0.8, 'source': 'city_specific'})
        
        elif 'new york' in city_lower:
            # NYC-specific patterns
            if any(word in neighborhood_lower for word in ['greenwich village', 'soho', 'east village']):
                categories.append({'category': 'Entertainment Districts', 'confidence': 0.9, 'source': 'city_specific'})
            if any(word in neighborhood_lower for word in ['financial district', 'wall street', 'tribeca']):
                categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'city_specific'})
            if any(word in neighborhood_lower for word in ['fifth avenue', 'madison', 'soho']):
                categories.append({'category': 'Shopping', 'confidence': 0.9, 'source': 'city_specific'})
        
        # Enhanced fallback for unknown neighborhoods - provide contextually relevant options
        if len(categories) <= 1:  # Only has Food & Dining or nothing
            # Add universally useful categories for any neighborhood
            categories.append({'category': 'Historic Sites', 'confidence': 0.6, 'source': 'enhanced_fallback'})
            categories.append({'category': 'Art & Culture', 'confidence': 0.6, 'source': 'enhanced_fallback'})
            categories.append({'category': 'Shopping', 'confidence': 0.5, 'source': 'enhanced_fallback'})
            
            # Add city-specific likely categories
            if 'tokyo' in city_lower:
                categories.append({'category': 'Entertainment Districts', 'confidence': 0.7, 'source': 'city_fallback'})
            elif 'paris' in city_lower:
                categories.append({'category': 'Art & Culture', 'confidence': 0.8, 'source': 'city_fallback'})
            elif 'london' in city_lower:
                categories.append({'category': 'Historic Sites', 'confidence': 0.8, 'source': 'city_fallback'})
            elif 'new york' in city_lower:
                categories.append({'category': 'Entertainment Districts', 'confidence': 0.8, 'source': 'city_fallback'})
        
        # Always include Food & Dining as fallback (most neighborhoods have food options)
        if not any(c['category'] == 'Food & Dining' for c in categories):
            categories.append({'category': 'Food & Dining', 'confidence': 0.7, 'source': 'fallback'})
        
        # Remove duplicates and sort by confidence
        seen = set()
        unique_categories = []
        for cat in sorted(categories, key=lambda x: x['confidence'], reverse=True):
            if cat['category'] not in seen:
                seen.add(cat['category'])
                unique_categories.append(cat)
        
        # Limit to top 8 most relevant categories for neighborhoods
        final_categories = unique_categories[:8]
        
        print(f"[NEIGHBORHOOD-CATEGORIES] Final categories before return: {[c['category'] for c in final_categories]}")
        print(f"[NEIGHBORHOOD-CATEGORIES] Generated {len(final_categories)} categories for {neighborhood}, {city}: {[c['category'] for c in final_categories]}")
        
        return final_categories
        
    except Exception as e:
        print(f"[NEIGHBORHOOD-CATEGORIES] Error for {neighborhood}, {city}: {e}")
        # Fallback to basic categories with correct format
        return [
            {'category': 'Food & Dining', 'confidence': 0.8, 'source': 'fallback'},
            {'category': 'Historic Sites', 'confidence': 0.7, 'source': 'fallback'},
            {'category': 'Shopping', 'confidence': 0.6, 'source': 'fallback'}
        ]


async def get_dynamic_categories(city: str, state: str = "", country: str = "US") -> List[Dict[str, str]]:
    """
    Generate categories by leveraging ALL available data sources with semantic understanding:
    - Fun facts (curated, high confidence)
    - City guides (Wikipedia content)
    - Wikipedia sections and categories
    - DDGS current trends
    """
    
    try:
        cache_key = f"categories:{CACHE_VERSION}:{country}:{state}:{city}".lower()

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
        
        # 2. Distinctive features (what makes this city UNIQUE)
        distinctive_cats = await extract_distinctive_categories(city, state, country)
        all_categories.extend(distinctive_cats)
        
        # 3. City guide content
        guide_cats = await extract_from_city_guide(city, state, country)
        all_categories.extend(guide_cats)
        
        # 3. Wikipedia sections and categories
        wiki_cats = await extract_from_wikipedia_sections(city, state, country)
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
        import traceback
        print(f"[SMART CATEGORIES] Error: {e}")
        print(traceback.format_exc())
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
    # Country-level tourism POI extractor
    @app.route('/api/extract_country_tourism', methods=['GET'])
    async def extract_country_tourism():
        """Discover cities from a country's tourism page and return POIs per city.

        Query parameters:
        - country: country name (required)
        - per_city_limit: int (optional)
        - concurrency: int (optional)
        - nocache: true/false (optional)
        """
        country = request.args.get('country') or request.args.get('q')
        if not country:
            return {'error': 'country parameter required'}, 400

        per_city_limit = int(request.args.get('per_city_limit', 50))
        concurrency = int(request.args.get('concurrency', 4))
        max_cities = int(request.args.get('max_cities', 8))
        per_city_timeout = float(request.args.get('per_city_timeout', 20))
        cities_raw = request.args.get('cities', '')
        forced_cities = [c.strip() for c in cities_raw.split(',') if c.strip()] if cities_raw else None
        nocache = request.args.get('nocache', '').lower() == 'true'

        cache_key = f"country_pois:v1:{country.lower()}"
        # Return cached result if available unless nocache
        if redis_client and not nocache:
            try:
                cached = await asyncio.to_thread(redis_client.get, cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        try:
            from city_guides.src.wiki_country_extractor import extract_pois_for_country
        except Exception as e:
            return {'error': f'Extractor unavailable: {e}'}, 500

        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "city-guides-bot/1.0"}) as session:
                data = await extract_pois_for_country(
                    country,
                    per_city_limit=per_city_limit,
                    concurrency=concurrency,
                    max_cities=max_cities,
                    per_city_timeout=per_city_timeout,
                    forced_cities=forced_cities,
                    session=session,
                )
        except Exception as e:
            return {'error': str(e)}, 500

        # Cache results for a day
        if redis_client and data:
            try:
                await asyncio.to_thread(redis_client.setex, cache_key, 60 * 60 * 24, json.dumps(data))
            except Exception:
                pass

        return data
    @app.route('/api/categories/<city>', methods=['GET'])
    async def get_categories(city):
        # Use the request context for query params
        state = request.args.get('state', '')
        country = request.args.get('country', 'US')
        nocache = request.args.get('nocache', '').lower() == 'true'
        
        # Support nocache parameter for testing
        if nocache:
            print(f"[CACHE] NOCACHE requested for {city}")
            # Temporarily disable cache for this request
            global redis_client
            original_client = redis_client
            redis_client = None
            try:
                categories = await get_dynamic_categories(city, state, country)
                return {'categories': categories, 'cached': False, 'note': 'nocache mode'}
            finally:
                redis_client = original_client
        else:
            categories = await get_dynamic_categories(city, state, country)
            return {'categories': categories}
    
    @app.route('/api/admin/clear-cache', methods=['POST'])
    async def clear_cache():
        """Clear all category cache entries. Admin endpoint."""
        if not redis_client:
            return {'success': False, 'message': 'Redis not available'}, 500
            
        try:
            # Find and delete all category cache keys
            pattern = f"categories:{CACHE_VERSION}:*"
            keys = await asyncio.to_thread(redis_client.keys, pattern)
            if keys:
                deleted = await asyncio.to_thread(redis_client.delete, *keys)
                return {
                    'success': True, 
                    'deleted_keys': deleted,
                    'pattern': pattern,
                    'message': f'Cleared {deleted} cached entries'
                }
            else:
                return {'success': True, 'message': 'No cache entries found'}
        except Exception as e:
            return {'success': False, 'message': str(e)}, 500
    
    @app.route('/api/admin/cache-stats', methods=['GET'])
    async def cache_stats():
        """Get cache statistics."""
        if not redis_client:
            return {'redis_available': False}
            
        try:
            pattern = f"categories:{CACHE_VERSION}:*"
            keys = await asyncio.to_thread(redis_client.keys, pattern)
            return {
                'redis_available': True,
                'cache_version': CACHE_VERSION,
                'ttl_seconds': CACHE_TTL,
                'cached_cities': len(keys),
                'sample_keys': keys[:10] if keys else []
            }
        except Exception as e:
            return {'error': str(e)}, 500
