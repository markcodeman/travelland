import os
import aiohttp
from bs4 import BeautifulSoup
import math
import re
import logging
import hashlib
import json
import datetime
import threading
import time
from pathlib import Path

# Load .env file if it exists (for standalone testing)
_env_paths = [
    Path(__file__).parent / ".env",
    Path(__file__).parent.parent / ".env",
    Path("/home/markm/TravelLand/.env"),
]
for _env_file in _env_paths:
    if _env_file.exists():
        with open(_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
        break
from pathlib import Path

from city_guides.providers import search_provider
from city_guides.providers.utils import get_session

# Import Wikipedia provider
try:
    from city_guides.providers.wikipedia_provider import fetch_wikipedia_summary, fetch_wikipedia_full
    WIKI_AVAILABLE = True
except Exception as e:
    WIKI_AVAILABLE = False
    logging.warning(f"Wikipedia provider not available: {e}")

# Import RAG recommender
try:
    from city_guides.groq.traveland_rag import recommend_venues_rag, recommend_neighborhoods_rag
    RAG_AVAILABLE = True
except Exception as e:
    RAG_AVAILABLE = False
    logging.warning(f"RAG recommender not available, falling back to text-based recommendations: {e}")

# duckduckgo_provider removed

def analyze_any_query(query, available_venues, conversation_history):
    """Analyze ANY query intelligently"""
    # 1. What is the user asking FOR? (not just keywords)
    question_words = ['what', 'where', 'when', 'how', 'why', 'which', 'can', 'do', 'does', 'is', 'are']
    is_question = any(query.lower().startswith(word) for word in question_words) or '?' in query

    # 2. What context do we have? (venues, neighborhoods, history)
    has_venues = len(available_venues) > 0 if available_venues else False
    has_prev_context = len(conversation_history) > 0 if conversation_history else False

    # 3. Check for specific intent patterns
    query_lower = query.lower()

    # Follow-up patterns (user mentions they've explored/found things)
    followup_patterns = ['explored', 'found', 'visited', 'tried', 'been to', 'saw', 'discovered']
    is_followup = any(pattern in query_lower for pattern in followup_patterns)

    # Specific venue/place requests
    venue_keywords = ['restaurant', 'cafe', 'coffee', 'bar', 'pub', 'food', 'eat', 'drink', 'shop', 'store', 'museum', 'park', 'attraction', 'pizza', 'taco', 'burger', 'sushi', 'italian', 'chinese', 'mexican', 'thai', 'indian', 'french', 'japanese', 'korean', 'vietnamese', 'mediterranean', 'american', 'breakfast', 'lunch', 'dinner', 'snacks', 'dessert', 'bakery', 'ice cream']
    wants_specific_venues = any(keyword in query_lower for keyword in venue_keywords)

    # Neighborhood exploration (only if explicitly mentioned)
    neighborhood_keywords = ['neighborhood', 'area', 'district', 'explore', 'walk around', 'stroll']
    wants_neighborhoods = any(keyword in query_lower for keyword in neighborhood_keywords) and not wants_specific_venues

    # 4. Determine response strategy
    if is_followup:
        return "followup_conversation"
    elif is_question and has_venues and wants_specific_venues:
        return "answer_with_venue_data"
    elif is_question and wants_neighborhoods:
        return "neighborhood_exploration"
    elif is_question and wants_specific_venues:  # User is asking about specific venue types
        return "venue_request"  # New category for venue requests without existing venue data
    elif is_question:
        return "general_question"
    elif has_prev_context:  # Follow-up to previous conversation
        return "continue_conversation"
    elif wants_specific_venues and has_venues:
        return "venue_suggestions"
    else:
        return "exploratory_engagement"

def build_response_for_any_query(query, context, analysis_result):
    """Build appropriate response for ANY user input"""

    available_venues = context.get('venues', [])
    city = context.get('city', 'this city')
    neighborhoods = context.get('neighborhoods', [])
    history = context.get('history', '')

    # Handle different analysis results
    if analysis_result == "followup_conversation":
        return handle_followup_conversation(query, available_venues, city)

    elif analysis_result == "answer_with_venue_data":
        return None  # Let the AI handle venue questions with context

    elif analysis_result == "neighborhood_exploration":
        return build_neighborhood_response(query, neighborhoods, city)

    elif analysis_result == "venue_request":
        return handle_venue_request(query, city)

    elif analysis_result == "general_question":
        return handle_general_question(query, available_venues, city)

    elif analysis_result == "continue_conversation":
        return build_conversation_continuation(query, history, available_venues, city)

    elif analysis_result == "venue_suggestions":
        return build_venue_suggestions(query, available_venues, city)

    else:  # exploratory_engagement
        return engage_and_explore(query, available_venues, neighborhoods, city)


def handle_followup_conversation(query, venues, city):
    """Handle conversations where user mentions they've explored/found things"""
    query_lower = query.lower()

    # Detect what they were interested in
    if "pub" in query_lower or "bar" in query_lower or "drink" in query_lower:
        if venues:
            pub_venues = [v for v in venues if v.get('type', '').lower() in ['pub', 'bar']]
            if pub_venues:
                venue_names = [v.get('name', 'this pub') for v in pub_venues[:3] if v.get('name')]
                if venue_names:
                    names_str = "**, **".join(venue_names[:2])
                    return f"That's awesome you found great pubs! Based on local data, here are some excellent options in {city}:\n\n• **{names_str}\**\n\nWould you like more details on any of these, or are you looking for a specific type of pub?"
        return f"Excellent pub discoveries! What would you like to know about pubs in {city}? I can help with recommendations for different styles, atmospheres, or specific areas."

    if "coffee" in query_lower or "cafe" in query_lower or "roast" in query_lower:
        if venues:
            coffee_venues = [v for v in venues if 'coffee' in v.get('type', '').lower() or 'cafe' in v.get('type', '').lower()]
            if coffee_venues:
                venue_names = [v.get('name') for v in coffee_venues[:3] if v.get('name')]
                if venue_names:
                    names_str = "**, **".join(venue_names[:2])
                    # Check for specific coffee preferences
                    if "medium roast" in query_lower:
                        return f"Ahoy! 🧭 Based on your interest in medium roast, here are some excellent coffee spots in {city}:\n\n• **{names_str}**\n\nThese cafes are known for their balanced medium roast blends. Would you like more details on any of these, or are you looking for other coffee styles?"
                    elif "dark roast" in query_lower:
                        return f"Ahoy! 🧭 For dark roast lovers, here are some great coffee options in {city}:\n\n• **{names_str}**\n\nThese spots specialize in rich, bold dark roast coffees. Would you like more details on any of these?"
                    elif "light roast" in query_lower:
                        return f"Ahoy! 🧭 If you enjoy light roast, check out these coffee cafes in {city}:\n\n• **{names_str}**\n\nThese places offer bright, fruity light roast options. Would you like more details on any of these?"
                    else:
                        return f"Ahoy! 🧭 Based on local data, here are some excellent coffee spots in {city}:\n\n• **{names_str}**\n\nWould you like more details on any of these, or are you looking for a specific coffee style (like dark roast, medium roast, or light roast)?"
        return f"Ahoy! 🧭 I can help you find great coffee in {city}! Let me search for some excellent coffee shops and cafes in the area. One moment while I find the best spots for you. - Marco ☕"

    if "food" in query_lower or "restaurant" in query_lower or "eat" in query_lower:
        if venues:
            food_venues = [v for v in venues if v.get('type', '').lower() in ['restaurant', 'food']]
            if food_venues:
                venue_names = [v.get('name', 'this restaurant') for v in food_venues[:3] if v.get('name')]
                if venue_names:
                    names_str = "**, **".join(venue_names[:2])
                    return f"That's great you found good food! Based on local data, here are some excellent restaurants in {city}:\n\n• **{names_str}\**\n\nWould you like more details on any of these, or are you looking for a specific cuisine?"
        return f"Excellent food discoveries! What would you like to know about dining in {city}? I can help with recommendations for different cuisines, neighborhoods, or specific types of restaurants."

    # Generic followup - use available venue names if we have them
    if venues:
        venue_names = [v.get('name', 'this spot') for v in venues[:2] if v.get('name')]
        if venue_names:
            names_str = "**, **".join(venue_names)
            return f"That's great you've been exploring! Based on local data, here are some popular spots you've already discovered:\n\n• **{names_str}\**\n\nWhat would you like to discover next? I can help with more recommendations for food, attractions, or specific interests!"

    return f"That's great you've been exploring! What would you like to discover next in {city}? I can help with recommendations for food, attractions, or other interests."


def build_neighborhood_response(query, neighborhoods, city):
    """Build response for explicit neighborhood exploration queries"""
    if not neighborhoods:
        return f"I'd be happy to help you explore neighborhoods in {city}! While I don't have specific neighborhood data right now, I can help you discover different areas based on your interests - food, attractions, or specific types of places."
    
    # This will be handled by the existing neighborhood recommendation logic
    return None  # Let the AI handle this


def handle_general_question(query, venues, city):
    """Handle general questions without specific venue context"""
    query_lower = query.lower()

    # Questions about food/dining
    if any(word in query_lower for word in ['eat', 'food', 'restaurant', 'dining']):
        return f"For food and dining in {city}, I can help you find restaurants by cuisine type, price range, or location. What type of food are you in the mood for?"

    # Questions about attractions
    if any(word in query_lower for word in ['see', 'attraction', 'tourist', 'sightseeing']):
        return f"{city} has so many great attractions! Are you interested in museums, parks, historical sites, or outdoor activities?"

    # General exploration
    return f"I'd love to help you explore {city}! Could you tell me more about what interests you - food, attractions, shopping, or something specific you've heard about?"


def build_conversation_continuation(query, history, venues, city):
    """Continue an ongoing conversation"""
    # Use history to provide contextually relevant suggestions
    if history and venues:
        return f"Continuing our conversation about {city}... Based on what we've discussed, here are some relevant suggestions from the venues nearby."

    return f"Tell me more about what you're looking for in {city}! I can provide specific recommendations based on your interests."


def handle_venue_request(query, city):
    """Handle venue requests when no venues are currently available"""
    query_lower = query.lower()

    # Detect specific food/cuisine types
    food_keywords = {
        'pizza': ['pizza', 'pizzeria'],
        'taco': ['taco', 'tacos', 'mexican'],
        'burger': ['burger', 'burgers', 'american'],
        'sushi': ['sushi', 'japanese'],
        'italian': ['italian', 'pasta', 'pizza'],
        'chinese': ['chinese'],
        'mexican': ['mexican', 'taco'],
        'thai': ['thai'],
        'indian': ['indian', 'curry'],
        'french': ['french'],
        'japanese': ['japanese', 'sushi'],
        'korean': ['korean'],
        'vietnamese': ['vietnamese', 'pho'],
        'mediterranean': ['mediterranean', 'greek'],
        'american': ['american', 'burger'],
        'breakfast': ['breakfast'],
        'lunch': ['lunch'],
        'dinner': ['dinner'],
        'snacks': ['snacks'],
        'dessert': ['dessert'],
        'bakery': ['bakery'],
        'ice cream': ['ice cream', 'gelato'],
        'coffee': ['coffee', 'cafe', 'espresso'],
        'bar': ['bar', 'pub', 'drinks'],
        'restaurant': ['restaurant', 'food', 'eat', 'dining']
    }

    # Find matching food type
    matched_food_type = None
    for food_type, keywords in food_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            matched_food_type = food_type
            break

    if matched_food_type:
        # Map food types to more descriptive categories
        food_descriptions = {
            'pizza': 'pizza',
            'taco': 'tacos',
            'burger': 'burgers',
            'sushi': 'sushi',
            'italian': 'Italian cuisine',
            'chinese': 'Chinese cuisine',
            'mexican': 'Mexican cuisine',
            'thai': 'Thai cuisine',
            'indian': 'Indian cuisine',
            'french': 'French cuisine',
            'japanese': 'Japanese cuisine',
            'korean': 'Korean cuisine',
            'vietnamese': 'Vietnamese cuisine',
            'mediterranean': 'Mediterranean cuisine',
            'american': 'American cuisine',
            'breakfast': 'breakfast spots',
            'lunch': 'lunch options',
            'dinner': 'dinner restaurants',
            'snacks': 'snacks',
            'dessert': 'desserts',
            'bakery': 'bakeries',
            'ice cream': 'ice cream',
            'coffee': 'coffee shops',
            'bar': 'bars',
            'restaurant': 'restaurants'
        }

        food_description = food_descriptions.get(matched_food_type, matched_food_type)
        return f"Ahoy! 🧭 I understand you're looking for {food_description} in {city}! Let me find some great options for you. One moment while I search for the best {food_description} spots in the area. - Marco 🍕"

    # Fallback for general venue requests
    return f"Ahoy! 🧭 I understand you're looking for something specific in {city}! Let me find some great options for you. One moment while I search for the best spots in the area. - Marco 🏙️"

def build_venue_suggestions(query, venues, city):
    """Build suggestions when user wants specific venue types - returns SPECIFIC recommendations"""
    if not venues:
        return f"I'd be happy to help you find what you're looking for in {city}! Could you be more specific about the type of place?"

    # Extract venue names from available data
    venue_names = [v.get('name', 'Local spot') for v in venues[:5] if v.get('name')]
    
    if venue_names:
        # Create a specific response with actual venue names
        if len(venue_names) == 1:
            return f"Based on local data, here's a top pick in {city}: **{venue_names[0]}**. Would you like more details about this place or other options?"
        elif len(venue_names) == 2:
            return f"Here are the top spots in {city} based on local data:\n\n• **{venue_names[0]}**\n• **{venue_names[1]}**\n\nWould you like more details about any of these?"
        else:
            names_str = "**, **".join(venue_names[:3])
            return f"Here are the top spots in {city} based on local data:\n\n• **{names_str}**\n\nWould you like more details about any of these?"

    # This will be handled by AI with venue context - but we now have venue data
    return None


def engage_and_explore(query, venues, neighborhoods, city):
    """Engage user in exploratory conversation"""
    if venues:
        venue_types = set()
        for venue in venues[:5]:
            v_type = venue.get('type', '').lower()
            if v_type:
                venue_types.add(v_type)

        if venue_types:
            types_str = ", ".join(list(venue_types)[:3])
            return f"I see some great {types_str} options nearby in {city}! What sounds most interesting to you, or would you like me to recommend some top picks?"

    return f"I'm excited to help you explore {city}! What are you most curious about - I can recommend restaurants, attractions, coffee shops, or help with specific interests."

# Simple in-memory vector store + ingestion that prefers Groq.ai embeddings
GROQ_EMBEDDING_ENDPOINT = "https://api.groq.ai/v1/embeddings"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class InMemoryIndex:
    def __init__(self):
        self.items = []  # list of (embedding:list[float], meta:dict)

    def add(self, embedding, meta):
        self.items.append((embedding, meta))

    def search(self, query_emb, top_k=5):
        logging.debug(f"Performing search with top_k={top_k}")
        scores = []
        q_norm = math.sqrt(sum(x * x for x in query_emb))
        for emb, meta in self.items:
            # cosine similarity
            dot = sum(a * b for a, b in zip(query_emb, emb))
            e_norm = math.sqrt(sum(x * x for x in emb))
            score = dot / (q_norm * e_norm + 1e-12)
            scores.append((score, meta))
        scores.sort(key=lambda x: x[0], reverse=True)
        results = [{"score": float(s), "meta": m} for s, m in scores[:top_k]]
        logging.debug(f"Search results: {results}")
        return results


INDEX = InMemoryIndex()

# Simple file-based cache for Marco responses. Stored at data/marco_cache.json.
_CACHE_FILE = Path(__file__).resolve().parents[1] / "data" / "marco_cache.json"
_CACHE_LOCK = threading.Lock()


def _make_cache_key(query, city, mode):
    s = f"{(city or '').strip().lower()}|{mode}|{(query or '').strip().lower()}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_cache():
    try:
        if not _CACHE_FILE.exists():
            return {}
        with _CACHE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_cache(cache):
    try:
        tmp = _CACHE_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        tmp.replace(_CACHE_FILE)
    except Exception:
        pass


def _cache_get(key):
    ttl_days = int(os.getenv("MARCO_CACHE_TTL_DAYS", "7"))
    with _CACHE_LOCK:
        c = _load_cache()
        rec = c.get(key)
        if not rec:
            return None
        gen = rec.get("generated_at")
        if not gen:
            return rec.get("value")
        try:
            gen_dt = datetime.datetime.fromisoformat(gen)
            if (datetime.datetime.utcnow() - gen_dt).days >= ttl_days:
                # expired
                try:
                    del c[key]
                    _write_cache(c)
                except Exception:
                    pass
                return None
            return rec.get("value")
        except Exception:
            return rec.get("value")


def _cache_set(key, value, source="groq"):
    rec = {
        "value": value,
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "source": source,
    }
    with _CACHE_LOCK:
        c = _load_cache()
        c[key] = rec
        _write_cache(c)


from typing import Optional

def create_venue_context_string(venues, limit=8):
    """Create a detailed string describing venues for AI context"""
    if not venues:
        return "No specific venues available yet. Suggest exploring the area."
    
    venue_descriptions = []
    for venue in venues[:limit]:
        name = venue.get('name', 'Unnamed venue')
        venue_type = venue.get('amenity', venue.get('type', 'place'))
        address = venue.get('display_address') or venue.get('address', 'Address not specified')
        
        # Build feature description
        features = []
        tags = venue.get('tags', {})
        if isinstance(tags, str):
            # Parse string tags if needed
            pass
            
        if venue.get('cuisine'):
            features.append(f"cuisine: {venue.get('cuisine')}")
        if venue.get('opening_hours'):
            features.append("has opening hours")
        if venue.get('website'):
            features.append("has website")
        if venue.get('outdoor_seating') == 'yes':
            features.append("outdoor seating")
        if venue.get('wheelchair') == 'yes':
            features.append("wheelchair accessible")
            
        features_str = f" ({', '.join(features)})" if features else ""
        
        desc = venue.get('description', '')
        if not desc and features_str:
            desc = f"{venue_type}{features_str}"
        elif not desc:
            desc = venue_type
            
        venue_descriptions.append(f"• {name}: {desc} | {address}")
    
    return "VENUES IN THIS AREA:\n" + "\n".join(venue_descriptions)


class ConversationMemory:
    """Enhanced conversation memory for natural multi-turn travel conversations.
    
    Tracks user interests, topic transitions, and builds context for coherent
    follow-up responses.
    """
    
    def __init__(self, history: str = None):
        self.history = history or ""
        self.user_interests = []  # Topics the user mentioned
        self.venues_mentioned = []  # Venues discussed
        self.last_topic = None  # Most recent topic
        self.topic_transitions = []  # When user changed topics
        self.conversation_flow = []  # Order of messages
        self.parse_history()
    
    def parse_history(self):
        """Parse conversation history to build memory."""
        if not self.history:
            return
        
        lines = [line.strip() for line in self.history.split('\n') if line.strip()]
        if not lines:
            return
        
        # Interest keywords to track
        interest_keywords = {
            'coffee': ['coffee', 'cafe', 'espresso', 'latte', 'cappuccino', 'brew'],
            'food': ['food', 'restaurant', 'eat', 'dining', 'cuisine', 'breakfast', 'lunch', 'dinner'],
            'bars': ['bar', 'pub', 'drinks', 'nightlife', 'cocktail', 'beer', 'wine'],
            'attractions': ['museum', 'park', 'attraction', 'sightseeing', 'landmark', 'tourist'],
            'transport': ['bus', 'metro', 'train', 'transport', 'subway', 'taxi'],
            'shopping': ['shop', 'market', 'mall', 'store', 'boutique'],
            'dark': ['dark', 'black', 'strong', 'bold'],
            'outdoor': ['outdoor', 'patio', 'terrace', 'garden', 'outside'],
            'budget': ['cheap', 'budget', 'affordable', 'inexpensive', 'price'],
            'atmosphere': ['cozy', 'romantic', 'lively', 'quiet', 'vibe', 'ambiance'],
        }
        
        for line in lines:
            # Detect speaker
            is_user = line.lower().startswith('user:')
            is_marco = line.lower().startswith('marco:')
            
            if not is_user and not is_marco:
                continue
            
            # Extract text
            if ':' in line:
                text = line.split(':', 1)[1].strip().lower()
            else:
                text = line.lower()
            
            if is_user:
                # Track user interests
                for interest, keywords in interest_keywords.items():
                    if any(kw in text for kw in keywords):
                        if interest not in self.user_interests:
                            self.user_interests.append(interest)
                        self.conversation_flow.append(('interest', interest))
                
                # Track topic transitions
                if self.last_topic and not any(kw in text for kw in interest_keywords.get(self.last_topic, [])):
                    # User changed topic
                    self.topic_transitions.append((self.last_topic, text[:50]))
                
                # Update last topic
                for interest, keywords in interest_keywords.items():
                    if any(kw in text for kw in keywords):
                        self.last_topic = interest
                        break
        
        # Parse for venue mentions
        venue_patterns = ['try', 'recommend', 'check out', 'go to', 'visit']
        for line in lines:
            if is_marco and any(pattern in line.lower() for pattern in venue_patterns):
                # Extract potential venue names (simple heuristic)
                words = line.split()
                for i, word in enumerate(words):
                    if word in ['try', 'recommend', 'check', 'go']:
                        if i + 1 < len(words):
                            venue = words[i + 1:i + 4]
                            if venue:
                                venue_name = ' '.join(venue).rstrip('.,!')
                                if venue_name not in self.venues_mentioned:
                                    self.venues_mentioned.append(venue_name)
    
    def get_interests_str(self) -> str:
        """Get string representation of user interests."""
        if not self.user_interests:
            return "No specific interests mentioned yet"
        return ", ".join(self.user_interests)
    
    def should_reference_previous(self) -> bool:
        """Check if we should reference previous conversation."""
        return len(self.conversation_flow) >= 2
    
    def get_followup_context(self) -> str:
        """Build context for follow-up responses."""
        if not self.should_reference_previous():
            return ""
        
        context_parts = []
        
        if self.user_interests:
            interests = ", ".join(self.user_interests[-3:])  # Last 3 interests
            context_parts.append(f"User interests so far: {interests}")
        
        if self.venues_mentioned:
            venues = ", ".join(self.venues_mentioned[-2:])  # Last 2 venues
            context_parts.append(f"Venues already discussed: {venues}")
        
        if self.topic_transitions:
            last_trans = self.topic_transitions[-1]
            context_parts.append(f"Recent topic: {last_trans[1]}...")
        
        return " | ".join(context_parts)


class ConversationAnalyzer:
    """Analyzes conversation history to understand context and user intent"""
    
    def __init__(self, history: str = None):
        self.history = history or ""
        self.topic = "general"
        self.topic_depth = 0
        self.user_frustration = 0
        self.repeated_response_count = 0
        self.last_user_query = ""
        self.specific_intents = []  # Track specific user intents (dark coffee, outdoor, etc.)
        self.parse_history()
    
    def parse_history(self):
        """Analyze conversation to determine current state"""
        if not self.history:
            return
        
        lines = [line.strip() for line in self.history.split('\n') if line.strip()]
        if not lines:
            return
            
        # Extract last 6 lines (3 exchanges)
        recent = lines[-6:]
        
        # Analyze topic depth
        topic_count = {}
        for line in recent:
            if line.lower().startswith('user:'):
                text = line.split(':', 1)[1].strip().lower()
                self.last_user_query = text
                
                # Extract specific intents from the query
                self._detect_specific_intents(text)
                
                # Simple keyword extraction - could be enhanced with NLP
                for word in text.split():
                    if len(word) > 3 and word not in ['the', 'and', 'for', 'with', 'what', 'where']:
                        topic_count[word] = topic_count.get(word, 0) + 1
        
        # Determine main topic
        if topic_count:
            main_topic = max(topic_count, key=topic_count.get)
            if topic_count[main_topic] >= 2:  # Repeated topic
                self.topic = main_topic
                self.topic_depth = topic_count[main_topic]
        
        # Detect frustration
        frustration_phrases = [
            "i just told you",
            "you're not listening",
            "where do i click",
            "same response",
            "repeating yourself"
        ]
        self.user_frustration = sum(1 for line in recent 
                                  if any(phrase in line.lower() for phrase in frustration_phrases))
        
        # Detect Marco's repetition
        marco_lines = [line for line in recent if line.lower().startswith('marco:')]
        if len(marco_lines) >= 2:
            last_2 = [line.split(':', 1)[1].strip() for line in marco_lines[-2:]]
            if last_2[0] == last_2[1]:
                self.repeated_response_count = 2
    
    def _detect_specific_intents(self, text):
        """Detect specific user intents from query text"""
        intents = []
        
        # Coffee-related specific intents
        if any(kw in text for kw in ['dark', 'black', 'strong', 'bold', 'espresso']):
            intents.append('dark_coffee')
        if any(kw in text for kw in ['outdoor', 'patio', 'terrace', 'garden', 'outside seating']):
            intents.append('outdoor_seating')
        if any(kw in text for kw in ['budget', 'cheap', 'affordable', 'inexpensive', 'under $']):
            intents.append('budget_friendly')
        if any(kw in text for kw in ['cozy', 'romantic', 'quiet', 'intimate', 'peaceful']):
            intents.append('cozy_atmosphere')
        if any(kw in text for kw in ['quick', 'fast', 'takeaway', 'takeout', 'grab and go']):
            intents.append('quick_service')
        if any(kw in text for kw in ['wheelchair', 'accessible', 'disabled', 'mobility']):
            intents.append('accessible')
        
        self.specific_intents = intents
    
    def should_escalate(self) -> bool:
        """Determine if Marco should provide concrete information"""
        """More sensitive escalation triggers"""
        return (
            len(self.specific_intents) > 0 or
            self.user_frustration >= 1 or
            self.topic_depth >= 2 or
            self.repeated_response_count >= 1 or
            (self.last_user_query and len(self.last_user_query.split()) >= 3)  # More specific queries
        )
    
    def get_response_strategy(self) -> str:
        """Determine best response strategy"""
        if self.specific_intents:
            return "address_specific_intent"
        elif self.user_frustration >= 1:
            return "apology_with_concrete_info"
        elif self.topic_depth >= 2:
            return "deepen_topic"
        elif self.repeated_response_count >= 1:
            return "break_repetition"
        return "continue_conversation"

def create_rich_venue_context(venues, query, limit=6):
    """Create detailed AI context from OSM data only"""
    if not venues:
        return "No specific venues found in this area yet. I'll help you explore!"
    
    # Analyze query to determine what's important
    q_lower = query.lower()
    features_to_highlight = set()
    
    if any(kw in q_lower for kw in ['outdoor', 'patio', 'terrace', 'garden']):
        features_to_highlight.add('outdoor seating')
    if any(kw in q_lower for kw in ['accessible', 'wheelchair', 'disabled']):
        features_to_highlight.add('wheelchair accessible')
    if any(kw in q_lower for kw in ['cheap', 'budget', 'affordable', 'inexpensive']):
        features_to_highlight.add('budget-friendly')
    if any(kw in q_lower for kw in ['quick', 'fast', 'takeaway', 'takeout']):
        features_to_highlight.add('quick service')
    
    venue_details = []
    for venue in venues[:limit]:
        name = venue.get('name', 'Local spot')
        venue_type = venue.get('amenity', venue.get('type', 'venue'))
        
        # Build smart description
        desc_parts = []
        
        # Use OSM tags intelligently
        tags = venue.get('tags', {})
        cuisine = tags.get('cuisine', '')
        if cuisine:
            desc_parts.append(cuisine)
        
        # Highlight features relevant to query
        venue_features = []
        if tags.get('outdoor_seating') == 'yes' and 'outdoor seating' in features_to_highlight:
            venue_features.append("outdoor seating")
        if tags.get('wheelchair') == 'yes' and 'wheelchair accessible' in features_to_highlight:
            venue_features.append("accessible")
        if tags.get('takeaway') == 'yes' and 'quick service' in features_to_highlight:
            venue_features.append("takeaway available")
        
        if venue_features:
            desc_parts.append(f"({', '.join(venue_features)})")
        
        # Add hours if available
        hours = venue.get('opening_hours', '')
        if hours and '24/7' in hours:
            desc_parts.append("open 24/7")
        elif hours and any(kw in q_lower for kw in ['open', 'hours', 'late']):
            desc_parts.append("listed hours")
        
        description = ' '.join(desc_parts) if desc_parts else venue_type
        address = venue.get('display_address') or venue.get('address', 'Nearby')
        
        venue_details.append(f"📍 **{name}** - {description}\n   🏠 {address}")
    
    context = f"I found {len(venue_details)} places matching your interests:\n\n"
    context += "\n\n".join(venue_details)
    context += f"\n\nBased on local data, these spots should match what you're looking for!"
    
    return context

def build_marco_prompt(query, city, venues, weather, neighborhoods, history, mode="explorer"):
    """Build a comprehensive prompt for Marco with rich context"""
    
    venue_context = create_venue_context_string(venues)
    
    weather_context = ""
    if weather:
        icons = {
            0: "☀️ Clear", 1: "🌤️ Mainly clear", 2: "⛅ Partly cloudy", 3: "☁️ Overcast",
            45: "🌫️ Fog", 51: "🌦️ Light drizzle", 61: "🌦️ Slight rain",
            71: "🌨️ Slight snow", 80: "🌧️ Slight rain showers", 95: "⛈️ Thunderstorm"
        }
        w_code = weather.get('weathercode', 0)
        w_summary = icons.get(w_code, "Unknown")
        temp = weather.get('temperature_c', 'N/A')
        weather_context = f"\nWEATHER: {w_summary}, {temp}°C\n"
    
    neighborhood_context = ""
    if neighborhoods:
        names = [n.get('name') for n in neighborhoods[:5] if n.get('name')]
        if names:
            neighborhood_context = f"\nNEIGHBORHOODS: {', '.join(names)}\n"
    
    history_context = f"\nCONVERSATION HISTORY:\n{history}\n" if history else ""
    
    if mode == "explorer":
        return f"""You are Marco, an experienced travel guide! 🗺️

Traveler asks: "{query}"

{weather_context}
{neighborhood_context}
{venue_context}
{history_context}

GUIDELINES:
• Focus on the SPECIFIC VENUES listed above - reference them by name
• Use the weather to suggest appropriate activities
• Mention neighborhood characteristics when relevant
• Be enthusiastic but factual based on the data
• Keep responses concise but helpful
• If suggesting venues, explain WHY they're good choices

Sign off as Marco! 🧭"""
    else:
        return f"""User query: {query}
{weather_context}{neighborhood_context}{venue_context}
Provide factual recommendations."""

def build_focused_marco_prompt(query, city, venues, weather, neighborhoods, history=None):
    """Build prompt that maximizes use of venue data"""
    
    venue_context = create_rich_venue_context(venues, query)
    
    # Smart weather integration
    weather_advice = ""
    if weather:
        temp = weather.get('temperature_c', 20)
        conditions = weather.get('weathercode', 0)
        
        # Weather-based suggestions
        if conditions in [51, 53, 55, 61, 63, 65, 80, 81, 82]:  # Rain codes
            weather_advice = "💡 Since it's raining, you might prefer indoor spots or places with covered seating."
        elif conditions in [71, 73, 75, 85, 86]:  # Snow codes
            weather_advice = "⛄ With snow forecast, cozy indoor venues would be perfect!"
        elif temp > 30:
            weather_advice = "☀️ It's hot out - look for places with air conditioning or outdoor shade."
        elif temp < 10:
            weather_advice = "🧣 Chilly weather - warm, cozy spots would be ideal."
    
    neighborhood_context = ""
    if neighborhoods:
        names = [n.get('name') for n in neighborhoods[:3] if n.get('name')]
        if names:
            neighborhood_context = f"\n**Neighborhoods to explore:** {', '.join(names)}"
    
    history_context = f"\n**Previous user questions:**\n{history}\n" if history else ""
    
    return f"""You are Marco, a SPECIFIC and helpful travel guide! 🗺️

**USER QUERY:** "{query}"

{venue_context}

**CRITICAL RULES:**
1. NEVER say "Tell me more about what you're looking for"
2. ALWAYS recommend SPECIFIC venues by name when available
3. If venues exist, reference at least 2-3 of them
4. NEVER ask generic questions when specific venues are available
5. Provide practical details: location, why it's good, features

**VENUE DATA AVAILABLE:** {len(venues)} venues
**MUST USE THIS DATA:** Reference venues by name and explain why they match the query

Response format:
- Start with 2-3 specific venue recommendations
- Explain WHY each fits the user's query
- Add practical tips based on weather/location
- End with a specific follow-up question

**Example BAD response (NEVER DO THIS):** "I'm ready to explore! What are you interested in?"
**Example GOOD response:** "Based on your interest in coffee, I recommend **Blue Bottle Coffee** for their dark roasts and **Philz Coffee** for custom blends. Both have outdoor seating and are within walking distance."

Ready to help! 🧭"""


def build_mandatory_venues_prompt(query, city, venues, weather, neighborhoods):
    """FORCE Marco to use venue data - no generic responses allowed"""
    
    venue_context = create_rich_venue_context(venues[:6], query)
    
    return f"""You are Marco, a travel assistant that MUST provide specific recommendations. FAILURE to use venue data will result in poor user experience.

**USER QUERY:** "{query}" in {city}

**AVAILABLE VENUE DATA ({len(venues)} venues):**
{venue_context}

**CRITICAL COMMANDS (MUST OBEY):**
1. You MUST reference specific venues by NAME from the list above
2. You MUST provide concrete recommendations, not generic suggestions  
3. You MUST explain why each venue fits the user's request
4. You MUST NOT say "I'm ready to explore" or other generic phrases
5. You MUST NOT ask "What are you interested in?" - use the venues provided
6. You MUST include practical details (distance, features, etc.)

**PROHIBITED PHRASES (NEVER USE):**
- "Tell me more about what you're looking for"
- "I'm ready to help you discover" 
- "What are you interested in?"
- "Let me know what you'd like to find"
- Any variation of asking for more input when venues exist

**EXAMPLE OF GOOD RESPONSE:**
"Based on your interest in coffee, here are specific options:
• **Blue Bottle Coffee** - Known for dark roasts and artisanal brewing (0.3km away)
• **Sightglass Coffee** - Local favorite with outdoor seating (0.5km away)  
• **Ritual Coffee Roasters** - Sustainable sourcing and cozy atmosphere (0.7km away)

Which of these sounds most appealing?"

**BAD RESPONSE (NEVER DO THIS):**
"I'm ready to explore coffee options! What type of coffee do you like?"

**BECAUSE:** Real venues exist - use them immediately.

Now respond with SPECIFIC venue recommendations:"""

def enhance_marco_response(response_text, venues):
    """Add specific venue references to Marco's response"""
    if not venues or not response_text:
        return response_text
    
    # Look for general mentions that could be linked to specific venues
    response_lower = response_text.lower()
    
    # Check if response mentions venue types but not specific names
    # Detect whether any known venue name is referenced (case-insensitive, tokenized)
    def mentions_any_venue(text_lower):
        for venue in venues:
            nm = venue.get('name')
            if not nm:
                continue
            nm_lower = nm.lower()
            if nm_lower in text_lower:
                return True
            # tokenized partial match: check multi-word overlap
            tokens = [t for t in nm_lower.split() if len(t) > 3]
            if tokens and any(tok in text_lower for tok in tokens):
                return True
        return False

    venue_types = ['restaurant', 'cafe', 'bar', 'pub', 'coffee', 'bakery']
    mentioned_types = [vt for vt in venue_types if vt in response_lower]

    if mentioned_types and not mentions_any_venue(response_lower):
        # Response mentions types but not specific venues - enhance it
        relevant_venues = []
        for venue in venues[:6]:
            name = venue.get('name', '')
            venue_type = (venue.get('type') or '').lower()
            tags = venue.get('tags') or {}
            cuisine = (tags.get('cuisine') or '').lower()
            match = False
            for mt in mentioned_types:
                if mt in venue_type or mt in cuisine or mt in name.lower():
                    match = True
                    break
            if match:
                relevant_venues.append(venue)

        # If none matched by type, fall back to top venues
        if not relevant_venues:
            relevant_venues = venues[:2]

        if relevant_venues:
            enhancement = "\n\nBased on local data, I'd recommend:\n"
            for i, venue in enumerate(relevant_venues[:3]):
                name = venue.get('name')
                desc = venue.get('description') or venue.get('tags', {}).get('cuisine') or venue.get('type', '')
                maps = _create_google_maps_link(name, '')
                enhancement += f"• **{name}** - {desc} — {maps}\n"
            response_text = response_text.strip() + "\n\n" + enhancement
    
    return response_text

def enhance_with_osm_data(response, venues, query):
    """Enhance AI response with specific OSM details"""
    if not venues or not response:
        return response
    
    # Check if response mentions specific venues
    response_lower = response.lower()
    mentioned_venues = []
    
    for venue in venues[:5]:
        name = venue.get('name', '')
        if name and name.lower() in response_lower:
            mentioned_venues.append(venue)
    
    # If no venues mentioned but we have good data, enhance
    if not mentioned_venues and len(venues) >= 2:
        # Add specific recommendations
        enhancement = "\n\n🏆 **Based on local data, I'd recommend:**\n"
        
        for venue in venues[:2]:
            name = venue.get('name')
            venue_type = venue.get('type', 'spot').title()
            features = []
            
            tags = venue.get('tags', {})
            if tags.get('cuisine'):
                features.append(tags['cuisine'])
            if tags.get('outdoor_seating') == 'yes':
                features.append('outdoor seating')
            if tags.get('wheelchair') == 'yes':
                features.append('accessible')
            
            features_str = f" ({', '.join(features)})" if features else ""
            enhancement += f"• **{name}** - Great {venue_type}{features_str}\n"
        
        response += enhancement
    
    return response

async def convert_currency(amount, from_curr, to_curr, session: Optional[aiohttp.ClientSession] = None):
    if session is None:
        async with get_session() as session:
            return await _convert_currency_impl(amount, from_curr, to_curr, session)
    else:
        return await _convert_currency_impl(amount, from_curr, to_curr, session)


async def _convert_currency_impl(amount, from_curr, to_curr, session):
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{from_curr.upper()}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return f"Error: API request failed with status {resp.status}"
            data = await resp.json()
            rate = data["rates"].get(to_curr.upper())
            if rate:
                converted = amount * rate
                return f"{amount} {from_curr.upper()} = {converted:.2f} {to_curr.upper()}"
            else:
                return "Currency not supported."
    except Exception as e:
        return f"Error: {str(e)}"


from typing import Optional

# Expanded venue discovery categories
VENUE_CATEGORIES = {
    'transport': ['station', 'bus_stop', 'tram_stop', 'ferry_terminal', 'bicycle_rental'],
    'attractions': ['museum', 'gallery', 'theatre', 'cinema', 'monument', 'artwork'],
    'accommodation': ['hotel', 'hostel', 'guest_house', 'apartment'],
    'food': ['restaurant', 'cafe', 'bar', 'pub', 'fast_food'],
    'shopping': ['mall', 'market', 'boutique', 'supermarket'],
    'services': ['bank', 'pharmacy', 'post_office', 'tourist_info'],
    'activities': ['park', 'beach', 'sports_centre', 'swimming_pool']
}

def get_poi_type_from_query(query):
    """Determine POI type based on broader travel categories"""
    q_lower = query.lower()

    if any(kw in q_lower for kw in ['bus', 'metro', 'train', 'transport', 'transit']):
        return 'transport'
    elif any(kw in q_lower for kw in ['museum', 'attraction', 'landmark', 'tourist']):
        return 'attractions'
    elif any(kw in q_lower for kw in ['hotel', 'hostel', 'stay', 'accommodation']):
        return 'accommodation'
    elif any(kw in q_lower for kw in ['shop', 'store', 'market', 'mall']):
        return 'shopping'
    elif any(kw in q_lower for kw in ['park', 'hike', 'beach', 'activity']):
        return 'activities'
    else:
        return 'restaurant'  # Default to food for generic queries

async def _fetch_text(url, timeout=8, session: Optional[aiohttp.ClientSession] = None):
    if session is None:
        async with get_session() as session:
            return await _fetch_text_impl(url, timeout, session)
    else:
        return await _fetch_text_impl(url, timeout, session)


async def _fetch_text_impl(url, timeout, session):
    try:
        headers = {"User-Agent": "CityGuidesBot/1.0 (+https://example.com)"}
        aio_timeout = aiohttp.ClientTimeout(total=timeout) if isinstance(timeout, (int, float)) else timeout
        async with session.get(url, headers=headers, timeout=aio_timeout) as r:
            if r.status != 200:
                return ""
            text_content = await r.text()
            soup = BeautifulSoup(text_content, "html.parser")
            for s in soup(["script", "style", "noscript"]):
                s.decompose()
            text = " ".join(
                p.get_text(separator=" ", strip=True)
                for p in soup.find_all(["p", "h1", "h2", "h3", "li"])
            )
            return text
    except Exception:
        return ""


def _chunk_text(text, max_chars=1000):
    if not text:
        return []
    parts = []
    start = 0
    L = len(text)
    while start < L:
        end = min(L, start + max_chars)
        parts.append(text[start:end])
        start = end
    return parts


def _shorten(text, n=200):
    if not text:
        return ""
    s = " ".join(text.split())
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0] + "..."


def summarize_results(results, max_items=3):
    """Create a short, human-readable summary of search results to keep prompts small."""
    if not results:
        return ""
    items = []
    for r in results[:max_items]:
        title = r.get("title") or r.get("name") or ""
        snippet = r.get("snippet") or r.get("description") or ""
        url = r.get("url") or r.get("link") or ""
        brief = _shorten(snippet, 180)
        line = f"- {title}: {brief} {f'({url})' if url else ''}"
        items.append(line)
    return "\n".join(items)


def _get_api_key():
    return os.getenv("GROQ_API_KEY")


from typing import Optional

async def _embed_with_groq(text, session: Optional[aiohttp.ClientSession] = None):
    # call Groq.ai embeddings endpoint (best-effort)
    key = _get_api_key()
    if session is None:
        async with get_session() as session:
            return await _embed_with_groq_impl(text, key, session)
    else:
        return await _embed_with_groq_impl(text, key, session)


async def _embed_with_groq_impl(text, key, session):
    try:
        if not key:
            raise RuntimeError("no groq key")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"model": "embed-english-v1", "input": text}
        async with session.post(GROQ_EMBEDDING_ENDPOINT, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200:
                return None
            j = await r.json()
            if (
                isinstance(j, dict)
                and "data" in j
                and len(j["data"]) > 0
                and "embedding" in j["data"][0]
            ):
                return j["data"][0]["embedding"]
    except Exception:
        pass
    return None


def _fallback_embedding(text, dim=128):
    # deterministic, simple hash-based fallback embedding for demos
    vec = [0.0] * dim
    words = (text or "").split()
    for i, w in enumerate(words):
        h = 0
        for c in w:
            h = (h * 131 + ord(c)) & 0xFFFFFFFF
        idx = h % dim
        vec[idx] += 1.0
    # normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


from typing import Optional

async def embed_text(text, session: Optional[aiohttp.ClientSession] = None):
    emb = await _embed_with_groq(text, session=session)
    if emb and isinstance(emb, list):
        return emb
    return _fallback_embedding(text)


from typing import Optional

async def ingest_urls(urls, session: Optional[aiohttp.ClientSession] = None):
    count = 0
    for url in urls:
        txt = await _fetch_text(url, session=session)
        if not txt:
            continue
        chunks = _chunk_text(txt)
        for i, c in enumerate(chunks):
            emb = await embed_text(c, session=session)
            meta = {"source": url, "snippet": c[:500], "chunk_index": i}
            INDEX.add(emb, meta)
            count += 1
    return count


from typing import Optional

async def semantic_search(query, top_k=5, session: Optional[aiohttp.ClientSession] = None):
    q_emb = await embed_text(query, session=session)
    return INDEX.search(q_emb, top_k=top_k)


from typing import Optional

async def recommend_neighborhoods(query, city, neighborhoods, mode="explorer", weather=None, session: Optional[aiohttp.ClientSession] = None):
    """Use AI to recommend neighborhoods based on user preferences and available data."""

    # Build neighborhood context
    neighborhood_list = []
    for n in neighborhoods[:20]:  # Limit to avoid token limits
        name = n.get("name", "Unknown")
        center = n.get("center", {})
        lat, lon = center.get("lat", 0), center.get("lon", 0)
        neighborhood_list.append(f"- {name} (coordinates: {lat:.4f}, {lon:.4f})")

    neighborhood_context = "AVAILABLE NEIGHBORHOODS:\n" + "\n".join(neighborhood_list)

    weather_context = ""
    if weather:
        icons = {
            0: "Clear ☀️", 1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
            45: "Fog 🌫️", 48: "Depositing rime fog 🌫️", 51: "Light drizzle 🌦️",
            53: "Moderate drizzle 🌦️", 55: "Dense drizzle 🌦️", 56: "Light freezing drizzle 🌧️",
            57: "Dense freezing drizzle 🌧️", 61: "Slight rain 🌦️", 63: "Moderate rain 🌦️",
            65: "Heavy rain 🌧️", 66: "Light freezing rain 🌧️", 67: "Heavy freezing rain 🌧️",
            71: "Slight snow fall 🌨️", 73: "Moderate snow fall 🌨️", 75: "Heavy snow fall ❄️",
            77: "Snow grains ❄️", 80: "Slight rain showers 🌧️", 81: "Moderate rain showers 🌧️",
            82: "Violent rain showers 🌧️", 85: "Slight snow showers 🌨️", 86: "Heavy snow showers 🌨️",
            95: "Thunderstorm ⛈️", 96: "Thunderstorm with slight hail ⛈️", 99: "Thunderstorm with heavy hail ⛈️",
        }
        w_summary = icons.get(weather.get("weathercode"), "Unknown")
        weather_context = f"\nCURRENT WEATHER: {w_summary}, {weather.get('temperature_c')}°C."

    # Detect if the query is about transport
    transport_keywords = ["transport", "bus", "public transit", "subway", "metro", "train", "tram"]
    is_transport_query = any(k in query.lower() for k in transport_keywords)

    if mode == "explorer":
        prompt = f"""You are Marco, the legendary explorer! 🗺️

A traveler is asking about neighborhoods in {city or 'this city'}: "{query}"

{weather_context}

{neighborhood_context}

INSTRUCTIONS FOR MARCO:
1. Analyze the traveler's request and recommend 2-4 neighborhoods that best match their interests.
2. For each recommendation, explain WHY it's a good choice based on the neighborhood name and general knowledge about {city or 'the city'}.
3. Consider the weather if relevant (e.g., suggest indoor activities if raining).
4. Be enthusiastic and explorer-themed.
5. If the traveler is interested in public transport or buses, you MUST mention available public transport options, bus routes, or stations in the recommended neighborhoods. If possible, provide helpful links (such as Google Maps or local transit sites) for getting around.
6. End with an invitation to explore further.
7. Sign off as Marco.🗺️🧭

Format your response as:
🏘️ **Neighborhood Name**: Brief description of why it's perfect for their interests. If relevant, include public transport info and links.

[Repeat for 2-4 recommendations]

Ready to explore these areas? Click any neighborhood to focus your search there! - Marco 🗺️"""
    else:
        prompt = f"User query: {query}\n\nCity: {city}\n\n{neighborhood_context}\n\n{weather_context}\n\nProvide factual neighborhood recommendations based on the available data. If the query is about public transport, include relevant transport options and links."

    # Cache lookup
    try:
        cache_key = _make_cache_key(f"neighborhoods_{query}", city, mode)
        cached = _cache_get(cache_key)
        if cached:
            logging.debug(f"Marco neighborhood cache hit for key={cache_key}")
            return cached

        key = _get_api_key()
        print(f"DEBUG: Calling Groq for neighborhood recommendation: {query}")
        print(f"DEBUG: Neighborhoods count: {len(neighborhoods)}")

        if not key:
            print("DEBUG: No GROQ_API_KEY found")
            # Fallback: return simple list
            names = [n.get("name") for n in neighborhoods[:6] if n.get("name")]
            return f"Based on your interests, here are some neighborhoods in {city or 'this city'} you might like: {', '.join(names)}. Try clicking on one to explore venues there!"

        # Truncate if too long
        MAX_PROMPT_CHARS = 1500
        if len(prompt) > MAX_PROMPT_CHARS:
            print(f"DEBUG: Prompt too long ({len(prompt)} chars), truncating")
            prompt = prompt[:MAX_PROMPT_CHARS] + "\n\n[TRUNCATED]"

        if session is None:
            async with get_session() as session:
                return await _recommend_neighborhoods_impl(prompt, key, neighborhoods, city, cache_key, mode, query, session)
        else:
            return await _recommend_neighborhoods_impl(prompt, key, neighborhoods, city, cache_key, mode, query, session)
        try:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 700,  # Increased for longer responses
                    "temperature": 0.8,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    print(f"DEBUG: Groq API Error {response.status}: {await response.text()}")
                if response.status == 200:
                    res_data = await response.json()
                    answer = res_data["choices"][0]["message"]["content"]
                    if answer and answer.strip():
                        ans = answer.strip()
                        # --- Post-process to add Google Maps links if missing ---
                        import re
                        import urllib.parse
                        def add_gmaps_links(text, neighborhoods, city):
                            for n in neighborhoods[:4]:
                                name = n.get("name")
                                if not name:
                                    continue
                                # If the neighborhood name appears in the answer but no link is present, add a link after the first mention
                                pattern = re.compile(rf"(**{re.escape(name)}**|{re.escape(name)})", re.IGNORECASE)
                                # Properly URL-encode the search query
                                search_query = f"{name} {city}".strip()
                                maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(search_query)}"
                                link = f" ([Google Maps]({maps_url}))"
                                # Only add if not already present
                                if name in text and maps_url not in text:
                                    text = pattern.sub(r"\1" + link, text, count=1)
                            return text
                        ans = add_gmaps_links(ans, neighborhoods, city)
                        try:
                            _cache_set(cache_key, ans, source="groq")
                        except Exception:
                            pass
                        if own_session:
                            await session.close()
                        return ans
        finally:
            if own_session:
                await session.close()

        # Fallback - use actual neighborhoods for the city
        names = [n.get("name") for n in neighborhoods[:6] if n.get("name")]
        if mode == "explorer" and names:
            neighborhood_list = []
            for i, name in enumerate(names[:4]):  # Show up to 4 neighborhoods
                neighborhood_list.append(f"🏘️ **{name}**: A great area to explore in {city or 'this city'}")

            fallback = f"Based on your interests, Based on your interests in '{query}', I'd recommend exploring these {city or 'city'} neighborhoods:\n\n" + "\n".join(neighborhood_list) + "\n\nClick any neighborhood to focus your search there! - Marco 🗺️"
        elif names:
            fallback = f"Recommended neighborhoods for '{query}': {', '.join(names)}. Try selecting one to explore venues there."
        else:
            fallback = f"Based on your interests, I'm exploring {city or 'this city'}! Try searching for a specific place above to help me navigate better. - Marco"
        try:
            _cache_set(cache_key, fallback, source="fallback")
        except Exception:
            pass
        return fallback
    except Exception as e:
        print(f"DEBUG: Groq neighborhood exception: {e}")
        names = [n.get("name") for n in neighborhoods[:3] if n.get("name")]
        return f"Here are some neighborhoods you might enjoy: {', '.join(names)}. Try selecting one to explore!"


async def _recommend_neighborhoods_impl(prompt, key, neighborhoods, city, cache_key, mode, query, session=None):
    own_session = False
    if session is None:
        from .utils import get_session
        session = await get_session()
        own_session = True
    
    try:
        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 700,  # Increased for longer responses
                "temperature": 0.8,
            },
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                print(f"DEBUG: Groq API Error {response.status}: {await response.text()}")
            if response.status == 200:
                res_data = await response.json()
                answer = res_data["choices"][0]["message"]["content"]
                if answer and answer.strip():
                    ans = answer.strip()
                    # --- Post-process to add Google Maps links if missing ---
                    import re
                    import urllib.parse
                    def add_gmaps_links(text, neighborhoods, city):
                        for n in neighborhoods[:4]:
                            name = n.get("name")
                            if not name:
                                continue
                            # If the neighborhood name appears in the answer but no link is present, add a link after the first mention
                            pattern = re.compile(rf"(**{re.escape(name)}**|{re.escape(name)})", re.IGNORECASE)
                            # Properly URL-encode the search query
                            search_query = f"{name} {city}".strip()
                            maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(search_query)}"
                            link = f" ([Google Maps]({maps_url}))"
                            # Only add if not already present
                            if name in text and maps_url not in text:
                                text = pattern.sub(r"\1" + link, text, count=1)
                        return text
                    ans = add_gmaps_links(ans, neighborhoods, city)
                    try:
                        _cache_set(cache_key, ans, source="groq")
                    except Exception:
                        pass
                    return ans
    except Exception:
        pass
    finally:
        if own_session and session:
            await session.close()

    # Fallback - use actual neighborhoods for the city
    names = [n.get("name") for n in neighborhoods[:6] if n.get("name")]
    if mode == "explorer" and names:
        neighborhood_list = []
        for i, name in enumerate(names[:4]):  # Show up to 4 neighborhoods
            neighborhood_list.append(f"🏘️ **{name}**: A great area to explore in {city or 'this city'}")

        fallback = f"Based on your interests, Based on your interests in '{query}', I'd recommend exploring these {city or 'city'} neighborhoods:\n\n" + "\n".join(neighborhood_list) + "\n\nClick any neighborhood to focus your search there! - Marco 🗺️"
    elif names:
        fallback = f"Recommended neighborhoods for '{query}': {', '.join(names)}. Try selecting one to explore venues there."
    else:
        fallback = f"Based on your interests, I'm exploring {city or 'this city'}! Try searching for a specific place above to help me navigate better. - Marco"
    try:
        _cache_set(cache_key, fallback, source="fallback")
    except Exception:
        pass
    return fallback


from typing import Optional

# Import Marco response enhancer
try:
    from .marco_response_enhancer import enhance_marco_response, is_generic_marco_response
    MARCO_ENHANCER_AVAILABLE = True
except Exception:
    MARCO_ENHANCER_AVAILABLE = False
    def enhance_marco_response(response, query, city, venues, neighborhoods):
        return response
    def is_generic_marco_response(response):
        return False


async def search_and_reason(
    query, city=None, mode="explorer", context_venues=None, weather=None, neighborhoods=None, session: Optional[aiohttp.ClientSession] = None, wikivoyage=None, history: str = None
):
    """Search the web and use Groq to reason about the query.

    mode: 'explorer' for themed responses, 'rational' for straightforward responses
    context_venues: optional list of venues already showing in the UI
    neighborhoods: optional list of neighborhoods for recommendation
    """

    # Check for currency conversion
    if "convert" in query.lower() or "currency" in query.lower():
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*([A-Z]{3})\s*to\s*([A-Z]{3})", query, re.IGNORECASE
        )
        if match:
            amount = float(match.group(1))
            from_curr = match.group(2)
            to_curr = match.group(3)
            result = await convert_currency(amount, from_curr, to_curr, session=session)
            if mode == "explorer":
                return f"For your As your trusty currency converter, here's the exchange: {result}. Safe travels with your coins!"
            else:
                return f"Currency conversion: {result}"
        else:
            if mode == "explorer":
                return "I'm having trouble parsing that currency request. Try 'convert 100 USD to EUR'!"
            else:
                return "Unable to parse currency conversion request. Please use format like 'convert 100 USD to EUR'."

    # Check for weather questions
    weather_keywords = [
        "weather",
        "temperature",
        "forecast",
        "wind",
        "rain",
        "sunny",
        "cloudy",
        "humidity",
        "umbrella",
        "jacket",
        "coat",
        "wear",
        "outdoor",
    ]
    if any(w in query.lower() for w in weather_keywords):
        # Use provided weather data if available
        if weather:
            icons = {
                0: "Clear ☀️",
                1: "Mainly clear 🌤️",
                2: "Partly cloudy ⛅",
                3: "Overcast ☁️",
                45: "Fog 🌫️",
                48: "Depositing rime fog 🌫️",
                51: "Light drizzle 🌦️",
                53: "Moderate drizzle 🌦️",
                55: "Dense drizzle 🌦️",
                56: "Light freezing drizzle 🌧️",
                57: "Dense freezing drizzle 🌧️",
                61: "Slight rain 🌦️",
                63: "Moderate rain 🌦️",
                65: "Heavy rain 🌧️",
                66: "Light freezing rain 🌧️",
                67: "Heavy freezing rain 🌧️",
                71: "Slight snow fall 🌨️",
                73: "Moderate snow fall 🌨️",
                75: "Heavy snow fall ❄️",
                77: "Snow grains ❄️",
                80: "Slight rain showers 🌧️",
                81: "Moderate rain showers 🌧️",
                82: "Violent rain showers 🌧️",
                85: "Slight snow showers 🌨️",
                86: "Heavy snow showers 🌨️",
                95: "Thunderstorm ⛈️",
                96: "Thunderstorm with slight hail ⛈️",
                99: "Thunderstorm with heavy hail ⛈️",
            }
            summary = icons.get(weather.get("weathercode"), "Unknown")
            details = f"{weather.get('temperature_c')}°C / {weather.get('temperature_f')}°F, Wind {weather.get('wind_kmh')} km/h / {weather.get('wind_mph')} mph"

            # If it's a simple weather check, return immediately.
            # If it's more complex (like "should I bring an umbrella?"), we'll let it fall through to the AI.
            simple_weather_check = (
                any(
                    w in query.lower()
                    for w in ["weather", "temperature", "forecast", "forecasts"]
                )
                and len(query.split()) < 5
            )
            if simple_weather_check:
                if mode == "explorer":
                    return f"Based on your interests, The current weather in {city or 'this city'} is: {summary}. {details}. Safe travels! - Marco"
                else:
                    return f"Current weather in {city or 'this city'}: {summary}. {details}."

    # Smart query analysis - understand what the user is actually asking for
    analysis_result = analyze_any_query(query, context_venues, history)
    print(f"DEBUG: Query analysis result: {analysis_result}")

    # Handle different query types with appropriate responses
    context_data = {
        'venues': context_venues or [],
        'city': city,
        'neighborhoods': neighborhoods or [],
        'history': history
    }

    # Initialize conversation analyzer early so we can decide whether to escalate
    conv_analyzer = ConversationAnalyzer(history)
    try:
        print(f"DEBUG early conv_analyzer: topic={conv_analyzer.topic}, frustration={conv_analyzer.user_frustration}, should_escalate={conv_analyzer.should_escalate()}")
    except Exception:
        pass

    # If analyzer requests escalation, prioritize local auto-enrichment and concrete replies
    try:
        if conv_analyzer.should_escalate():
            try:
                from city_guides.providers import multi_provider
                print("DEBUG: Early escalation - attempting aggressive local auto-enrichment of venues before other logic")
                # Aggressive POI search: try multiple POI types and increase the result limit
                aggressive_limit = 40
                candidate_types = ['restaurant', 'cafe', 'bar', 'tourism', 'park']
                enriched_candidates = []
                for t in candidate_types:
                    try:
                        res = await multi_provider.async_discover_pois(city or '', poi_type=t, limit=aggressive_limit)
                        if res:
                            enriched_candidates.extend(res)
                    except Exception as _:
                        continue
                # Deduplicate by id and keep top results
                seen = set()
                deduped = []
                for v in enriched_candidates:
                    vid = v.get('id')
                    if not vid:
                        continue
                    if vid in seen:
                        continue
                    seen.add(vid)
                    deduped.append(v)
                if deduped:
                    print(f"DEBUG: Early aggressive auto-enrichment found {len(deduped)} venues; returning concrete response")
                    return produce_concrete_response(query, city, deduped[:12], conv_analyzer)
            except Exception as e:
                print(f"DEBUG: Early auto-enrichment failed: {e}")
    except Exception:
        pass

    # Provider-first for explicit venue queries:
    # For queries that clearly request venues (pizza, coffee, restaurant, etc.),
    # attempt to fetch verified POIs from providers before calling the generative model.
    try:
        q_lower_local = (query or "").lower()
        venue_indicators = ['pizza', 'pizzeria', 'restaurant', 'food', 'eat', 'coffee', 'cafe', 'bar', 'pub', 'sushi', 'taco', 'burger']
        is_venue_query = any(k in q_lower_local for k in venue_indicators) or analysis_result in ("venue_request", "venue_suggestions")

        if is_venue_query:
            try:
                from city_guides.providers import multi_provider
                # Use the new get_poi_type_from_query function to determine POI type
                poi_type = get_poi_type_from_query(query)

                print(f"DEBUG: Provider-first enrichment for venue query (poi_type={poi_type}) - aggressive mode")
                # Aggressive provider-first search: increase limit and try related types if necessary
                enriched = await multi_provider.async_discover_pois(city or '', poi_type=poi_type, limit=40)
                if not enriched:
                    # fallback: try broader types
                    fallback_types = [poi_type, 'restaurant', 'cafe', 'bar']
                    enriched_candidates = []
                    for t in fallback_types:
                        try:
                            res = await multi_provider.async_discover_pois(city or '', poi_type=t, limit=40)
                            if res:
                                enriched_candidates.extend(res)
                        except Exception:
                            continue
                    # dedupe
                    seen = set()
                    deduped = []
                    for v in enriched_candidates:
                        vid = v.get('id')
                        if not vid or vid in seen:
                            continue
                        seen.add(vid)
                        deduped.append(v)
                    enriched = deduped

                if enriched:
                    print(f"DEBUG: Provider-first enrichment found {len(enriched)} venues; returning concrete response")
                    return produce_concrete_response(query, city, enriched[:12], conv_analyzer)
                else:
                    print("DEBUG: Provider-first enrichment found no venues; will continue to AI path")
            except Exception as e:
                print(f"DEBUG: Provider-first enrichment failed: {e}")
    except Exception:
        pass

    smart_response = build_response_for_any_query(query, context_data, analysis_result)
    try:
        print(f"DEBUG: smart_response: {smart_response}")
    except Exception:
        pass

    # If we got a direct response from the analysis, consider returning it unless escalation is required
    if smart_response is not None:
        try:
            lower_sr = (smart_response or "").lower()
            generic_checks = [
                # Generic responses that indicate Marco is not being helpful
                "tell me more about what you're looking for",
                "i'm ready to explore",
                "search for a specific place",
                "click any neighborhood",
                "i'd recommend exploring",
                "i'm ready for adventure",
                "ready for adventure",
                "ready to explore",
                "could you tell me more",
                "what are you most curious",
                "what interests you",
                "what would you like to know",
                "how can i help you",
                "what are you looking for",
                "any specific interests",
                "let me know what interests you",
                "safe travels",
                "my explorer's eyes are tired",
                "i'd be happy to help",
                "what sounds most interesting",
                "what are you most curious about",
                # Question-only endings
                "?",  # Any response that ends with just a question mark
            ]
            is_generic_sr = any(p in lower_sr for p in generic_checks)
            # Also consider it generic if response is very short (< 50 chars) and ends with ?
            if len(lower_sr) < 50 and lower_sr.strip().endswith('?'):
                is_generic_sr = True
            print(f"DEBUG: is_generic_sr={is_generic_sr}, response_preview={lower_sr[:80]}")
        except Exception:
            is_generic_sr = False

        # If analyzer suggests escalation and the smart_response is generic, skip the quick return
        if conv_analyzer.should_escalate() and is_generic_sr:
            # continue to AI/Groq path to get concrete suggestions
            pass
        else:
            if mode == "explorer":
                return f"Based on your interests, {smart_response} - Marco"
            else:
                return smart_response

    # For venue-focused queries, continue with AI analysis
    # Only fall back to neighborhood recommendations for explicit neighborhood queries
    if analysis_result == "neighborhood_exploration" and neighborhoods:
        return await recommend_neighborhoods(query, city, neighborhoods, mode, weather, session)

    # Perform web search for additional context
    try:
        results = await search_provider.duckduckgo_search(query, max_results=5)
    except Exception:
        results = []
    context = summarize_results(results)

    ui_context = ""
    if context_venues and len(context_venues) > 0:
        ui_lines = [
            f"- {v.get('name')} | {v.get('address')} | {v.get('description')}"
            for v in context_venues
        ]
        ui_context = "VENUES TO CONSIDER:\n" + "\n".join(ui_lines)

    # Process conversation history and build prompt using ConversationAnalyzer
    conv_analyzer = ConversationAnalyzer(history)

    # Build venue context string if available
    venue_context = create_venue_context_string(context_venues or [])

    # Weather context
    weather_context = ""
    if weather:
        weather_context = f"\nCURRENT WEATHER: {weather.get('temperature_c')}°C"

    # Choose prompt depending on conversation state
    # Use the mandatory venues prompt when escalation is requested or when the query is venue-focused
    venue_keywords = ['coffee', 'food', 'restaurant', 'bar', 'pub', 'cafe', 'eat', 'drink']
    is_venue_query_ui = any(keyword in (query or "").lower() for keyword in venue_keywords)
    if conv_analyzer.should_escalate() or (context_venues and is_venue_query_ui):
        prompt = build_mandatory_venues_prompt(query, city, context_venues or [], weather, neighborhoods or [])
    else:
        # Use the focused prompt as a sensible default (still enforces venue usage when available)
        prompt = build_focused_marco_prompt(query, city, context_venues or [], weather, neighborhoods or [], history)

    # Check for public-data-only mode
    import os
    PUBLIC_DATA_ONLY = os.getenv("PUBLIC_DATA_ONLY", "0") == "1"

    # Cache lookup: avoid calling Groq repeatedly for identical queries
    try:
        cache_key = _make_cache_key(query, city, mode)
        cached = _cache_get(cache_key)
        if cached:
            logging.debug(f"Marco cache hit for key={cache_key}")
            return cached

        # 1. Try to answer with public data first (WikiVoyage, OSM, venues, etc.)
        # If there are venues, neighborhoods, or Wikivoyage data, use that for a direct answer
        # (This is a simplified heuristic; you can expand this logic as needed)

        summary_parts = []
        # Try Wikipedia provider for the main neighborhood

        # Always attempt to fetch Wikipedia summary for the user's query, even if not in neighborhoods list
        if WIKI_AVAILABLE:
            # Use the query as the Wikipedia title
            wiki_debug_logs = []
            query_title = query.strip()
            logging.debug(f"[Marco DEBUG] Attempting Wikipedia fetch for user query: {query_title}")
            wiki_summary = await fetch_wikipedia_summary(query_title, lang="pt", city=city or "", debug_logs=wiki_debug_logs)
            if not wiki_summary and neighborhoods and len(neighborhoods) > 0:
                # Fallback: try the main neighborhood name
                main_nh = neighborhoods[0].get("name")
                logging.debug(f"[Marco DEBUG] Attempting fallback Wikipedia fetch for: {main_nh}")
                wiki_summary = await fetch_wikipedia_summary(main_nh, lang="pt", city=city or "", debug_logs=wiki_debug_logs)
            if wiki_summary:
                logging.debug(f"[Marco DEBUG] Wikipedia summary found for: {query_title} or fallback neighborhood")
                summary_parts.append(f"**Wikipedia:** {wiki_summary}")
            else:
                logging.debug(f"[Marco DEBUG] Wikipedia summary NOT found for: {query_title} or fallback neighborhood")
            # Always include debug logs in the response for debugging
            if wiki_debug_logs:
                summary_parts.append(f"**Wikipedia Debug Logs:**\n" + "\n".join(wiki_debug_logs))
            # Sections: try query title, then fallback
            wiki_sections = await fetch_wikipedia_full(query_title)
            if not wiki_sections and neighborhoods and len(neighborhoods) > 0:
                main_nh = neighborhoods[0].get("name")
                wiki_sections = await fetch_wikipedia_full(main_nh)
            if wiki_sections:
                logging.debug(f"[Marco DEBUG] Wikipedia sections found for: {query_title} or fallback neighborhood")
                for title, content in wiki_sections.items():
                    summary_parts.append(f"**{title}**: {content}")
            else:
                logging.debug(f"[Marco DEBUG] Wikipedia sections NOT found for: {query_title} or fallback neighborhood")
        # Use the explorer-themed recommender for neighborhoods
        # BUT only if the query analysis didn't determine this should be something else
        should_add_neighborhoods = (
            neighborhoods and len(neighborhoods) > 0 and
            analysis_result in ["exploratory_engagement", "neighborhood_exploration"]
        )

        if should_add_neighborhoods:
            marco_answer = await recommend_neighborhoods(query, city, neighborhoods, mode=mode, weather=weather, session=session)
            summary_parts.append(marco_answer)
        # Blend all other public data as before
        if wikivoyage:
            if isinstance(wikivoyage, list):
                for section in wikivoyage:
                    title = section.get('title') or section.get('section')
                    content = section.get('content')
                    if title and content:
                        summary_parts.append(f"**{title}**: {content}")
                    elif content:
                        summary_parts.append(content)
            elif isinstance(wikivoyage, str):
                summary_parts.append(wikivoyage)
        if context_venues and len(context_venues) > 0:
            venue_lines = [f"- {v.get('name')} ({v.get('address') or 'no address'}) — {v.get('description') or ''}" for v in context_venues[:5] if v.get('name')]
            if venue_lines:
                summary_parts.append("\n**Notable places you can visit:**\n" + "\n".join(venue_lines))
        if neighborhoods and len(neighborhoods) > 0 and analysis_result in ["exploratory_engagement", "neighborhood_exploration"]:
            nh_names = [n.get("name") for n in neighborhoods if n.get("name")]
            if nh_names:
                summary_parts.append("\n**Other neighborhoods to explore:** " + ", ".join(nh_names))

        # If we have good public data and PUBLIC_DATA_ONLY is enabled, return it
        if PUBLIC_DATA_ONLY and summary_parts:
            return "\n\n".join(summary_parts)

        # If we have context venues but no good public data synthesis, we should still call Groq
        # Only fall back to generic message if we have no context at all AND no way to get more data
        if not context_venues and not neighborhoods and not wikivoyage and not summary_parts and not WIKI_AVAILABLE and not RAG_AVAILABLE:
            return "For your My explorer's eyes are tired. Try searching for a specific place above first! - Marco"

        # 2. Otherwise, if escalation is needed and we lack venue context, try to auto-enrich locally
        try:
            print(f"DEBUG: conv_analyzer state: topic={conv_analyzer.topic}, frustration={conv_analyzer.user_frustration}, should_escalate={conv_analyzer.should_escalate()}")
        except Exception:
            pass
        if conv_analyzer.should_escalate() and (not context_venues or len(context_venues) == 0):
            try:
                from city_guides.providers import multi_provider
                print("DEBUG: Escalation requested - attempting local auto-enrichment of venues")
                # Try to infer POI type from the user's query (prefer cafes for coffee-related queries)
                q_lower_local = (query or "").lower()
                poi_type = 'restaurant'
                if any(k in q_lower_local for k in ['coffee', 'cafe', 'espresso', 'roaster', 'latte']):
                    poi_type = 'cafe'
                # Aggressive auto-enrichment: try multiple related types and increase limit
                aggressive_limit = 40
                types_to_try = [poi_type, 'restaurant', 'cafe', 'bar', 'tourism']
                enriched_candidates = []
                for t in types_to_try:
                    try:
                        res = await multi_provider.async_discover_pois(city or '', poi_type=t, limit=aggressive_limit)
                        if res:
                            enriched_candidates.extend(res)
                    except Exception:
                        continue
                # dedupe
                seen = set()
                deduped = []
                for v in enriched_candidates:
                    vid = v.get('id')
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    deduped.append(v)
                if deduped:
                    print(f"DEBUG: Auto-enrichment found {len(deduped)} venues; returning concrete response")
                    return produce_concrete_response(query, city, deduped[:12], conv_analyzer)
            except Exception as e:
                print(f"DEBUG: Auto-enrichment attempt failed: {e}")

        # 2. Skip AI call entirely if we have good venue data for venue-related queries
        if context_venues and len(context_venues) > 0:
            venue_keywords = ['coffee', 'food', 'restaurant', 'bar', 'pub', 'cafe', 'eat', 'drink']
            if any(keyword in (query or "").lower() for keyword in venue_keywords):
                print(f"DEBUG: Skipping AI call - direct concrete response for venue query: {query}")
                return produce_concrete_response(query, city, context_venues, conv_analyzer)

        # 3. Otherwise, call Groq as before
        key = _get_api_key()
        print(f"DEBUG: Calling Groq for query: {query}")
        print(f"DEBUG: Context Venues Count: {len(context_venues) if context_venues else 0}")

        if not key:
            print("DEBUG: No GROQ_API_KEY found in environment")
            raise Exception("No API Key")

        # Respect service limits: truncate overly large prompts to avoid 413 errors
        MAX_PROMPT_CHARS = 1200
        if len(prompt) > MAX_PROMPT_CHARS:
            print(f"DEBUG: Prompt too long ({len(prompt)} chars), truncating to {MAX_PROMPT_CHARS}")
            prompt = prompt[:MAX_PROMPT_CHARS] + "\n\n[TRUNCATED]"

        # Call Groq / reasoning implementation and apply response safeguards
        answer = None
        if session is None:
            async with get_session() as session:
                answer = await _search_and_reason_impl(prompt, key, cache_key, context_venues, query, session)
        else:
            answer = await _search_and_reason_impl(prompt, key, cache_key, context_venues, query, session)

        # Apply response safeguards
        try:
            final_response = apply_response_safeguards(
                answer,
                query,
                history,
                context_venues or [],
                conv_analyzer,
                city,
            )
        except Exception:
            final_response = answer

        # Store response in redis if available (best-effort)
        try:
            # note: redis_client may be defined in app context; do not require it
            from city_guides.src.app import redis_client  # type: ignore
            if redis_client and cache_key:
                cache_data = {
                    "response": final_response,
                    "query": query,
                    "city": city,
                    "topic": conv_analyzer.topic,
                    "timestamp": time.time(),
                }
                try:
                    await redis_client.setex(cache_key, 3600, json.dumps(cache_data))
                except Exception:
                    pass
        except Exception:
            pass

        # If analyzer indicates escalation but response is still generic/asking for clarification,
        # force a concrete venue-based reply.
        try:
            generic_phrases = [
                "tell me more about what you're looking for",
                "i'm ready to explore",
                "search for a specific place",
                "click any neighborhood",
                "i'm ready for adventure",
                "ready for adventure",
                "ready to explore",
                "could you tell me more",
                "what are you most curious",
            ]
            lower_final = (final_response or "").lower()
            is_generic_final = any(p in lower_final for p in generic_phrases) or lower_final.strip().endswith('?')
        except Exception:
            is_generic_final = False

        if conv_analyzer.should_escalate() and is_generic_final:
            try:
                concrete = produce_concrete_response(query, city, context_venues or [], conv_analyzer)
                final_response = concrete
            except Exception:
                pass

        return final_response
        try:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 256,
                    "temperature": 0.7,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    print(f"DEBUG: Groq API Error {response.status}: {await response.text()}")
                if response.status == 200:
                    res_data = await response.json()
                    answer = res_data["choices"][0]["message"]["content"]
                    if answer and answer.strip():
                        ans = answer.strip()
                        # Enhance response with specific venue references
                        ans = enhance_with_osm_data(ans, context_venues, query)
                        try:
                            _cache_set(cache_key, ans, source="groq")
                        except Exception:
                            pass
                        return ans
        finally:
            if own_session:
                await session.close()

        # Smarter fallback if AI fails
        if context_venues:
            import random
            pool = context_venues[:5] if len(context_venues) >= 5 else context_venues
            v = random.choice(pool)
            name = v.get("name", "this spot")
            fallback = f"Based on your interests, My compass is spinning, but looking at our map, **{name}** stands out! Based on my logs, it should be a fine spot for your quest. Safe travels! - Marco"
            try:
                _cache_set(cache_key, fallback, source="fallback")
            except Exception:
                pass
            return fallback

        # Venue-aware fallback
        if context_venues:
            # Use actual venue names in fallback
            venue_names = [v.get('name') for v in context_venues[:3] if v.get('name')]
            if venue_names:
                names_str = ", ".join(venue_names)
                fallback2 = f"Based on your interests, While my compass is adjusting, check out {names_str} - they look promising based on local data! - Marco"
            else:
                fallback2 = "Based on your interests, I'm exploring this area! The venues on your screen have good local ratings. - Marco"
        else:
            fallback2 = "Based on your interests, I'm ready to explore! Search for a specific place to get detailed recommendations. - Marco"
        try:
            _cache_set(cache_key, fallback2, source="fallback")
        except Exception:
            pass
        return fallback2
    except Exception as e:
        print(f"DEBUG: Groq Exception: {e}")
        if context_venues:
            fallback = f"Based on your interests, My compass is spinning, but **{context_venues[0].get('name')}** on your screen looks like a treasure! - Marco"
            try:
                _cache_set(cache_key, fallback, source="fallback")
            except Exception:
                pass
            return fallback
        fallback3 = "I'm I'm ready for adventure! - Marco"
        try:
            _cache_set(cache_key, fallback3, source="fallback")
        except Exception:
            pass
        return fallback3


def apply_response_safeguards(response, query, history, venues, analyzer, city=None):
    """More aggressive filtering of generic responses"""
    if not response:
        return response

    # Expanded list of generic phrases to catch
    generic_phrases = [
        "tell me more about what you're looking for",
        "i'm ready to explore",
        "search for a specific place",
        "click any neighborhood",
        "i'd recommend exploring",
        "i'm ready for adventure",
        "ready for adventure",
        "ready to explore",
        "could you tell me more",
        "what are you most curious",
        "what would you like to know",
        "how can i help you",
        "what are you looking for",
        "any specific interests",
        "let me know what interests you",
        "safe travels",
        "my explorer's eyes are tired",
        "i'd be happy to help",
        "what sounds most interesting",
        "what are you most curious about",
    ]

    # If response is generic AND we have venue data, force concrete response
    is_generic = any(phrase in response.lower() for phrase in generic_phrases)

    if is_generic and venues and len(venues) > 0:
        return produce_concrete_response(query, city, venues, analyzer)
    # Clean banned/generic phrases from responses even when not forcing concrete reply
    cleaned = response
    for phrase in generic_phrases:
        cleaned = cleaned.replace(phrase, "").replace(phrase.capitalize(), "")

    # If cleaned becomes empty or only punctuation, fall back to original
    if not cleaned.strip():
        return response

    # If analyzer suggests escalation but response still ends with a question or generic prompt,
    # and we have venues, force concrete recommendations
    try:
        if analyzer and analyzer.should_escalate():
            low_clean = cleaned.strip().lower()
            if low_clean.endswith('?') and venues:
                return produce_concrete_response(query, city, venues, analyzer)
    except Exception:
        pass

    return cleaned


def _create_google_maps_link(name, city):
    """Create a Google Maps search URL for a venue."""
    import urllib.parse
    search_query = f"{name} {city}".strip()
    encoded = urllib.parse.quote_plus(search_query)
    return f"https://www.google.com/maps/search/{encoded}"


def _get_venue_emoji(venue):
    """Get an appropriate emoji for a venue based on its type."""
    name = (venue.get('name') or '').lower()
    venue_type = (venue.get('type') or '').lower()
    tags = venue.get('tags', {})
    cuisine = (tags.get('cuisine') or '').lower()
    
    if 'pizza' in cuisine or 'pizza' in name:
        return '🍕'
    elif 'curry' in cuisine or 'indian' in cuisine:
        return '🍛'
    elif 'coffee' in cuisine or 'cafe' in cuisine:
        return '☕'
    elif 'burger' in cuisine or 'american' in cuisine:
        return '🍔'
    elif 'sushi' in cuisine or 'japanese' in cuisine:
        return '🍣'
    elif 'mexican' in cuisine or 'taco' in cuisine:
        return '🌮'
    elif 'thai' in cuisine or 'vietnamese' in cuisine or 'pho' in name:
        return '🍜'
    elif 'pub' in venue_type or 'bar' in venue_type or 'beer' in name:
        return '🍺'
    elif 'wine' in cuisine:
        return '🍷'
    elif 'bakery' in venue_type or 'breakfast' in cuisine:
        return '🥐'
    elif 'ice cream' in venue_type:
        return '🍦'
    elif 'chinese' in cuisine:
        return '🥡'
    elif 'italian' in cuisine or 'pasta' in cuisine:
        return '🍝'
    elif 'french' in cuisine:
        return '🥖'
    elif 'mediterranean' in cuisine or 'greek' in cuisine:
        return '🥙'
    elif 'restaurant' in venue_type:
        return '🍽️'
    elif 'cafe' in venue_type:
        return '☕'
    elif 'bar' in venue_type:
        return '🍸'
    elif 'fast_food' in venue_type:
        return '🍔'
    
    return '📍'


def produce_concrete_response(query, city, venues, analyzer):
    """Force a concrete, venue-based response when conversation needs escalation."""
    if not venues or len(venues) == 0:
        return f"I'd love to help you explore {city}! Try searching for specific venues first to get detailed recommendations."

    # Build a rich list: emoji, name (maps link), short description
    lines = []
    for v in venues[:4]:
        name = v.get('name') or 'Local spot'
        desc = v.get('description') or v.get('tags', {}).get('cuisine') or v.get('type') or ''
        emoji = _get_venue_emoji(v)
        maps = _create_google_maps_link(name, city or '')
        address = v.get('display_address') or v.get('address') or ''
        addr_str = f" — {address}" if address else ""
        lines.append(f"{emoji} **{name}** ({desc}) — <{maps}>{addr_str}")

    body = "\n".join(lines)
    return f"Based on your interest in '{query}', here are some great spots in **{city}**:\n\n{body}\n\nWould you like details about any of these, or should I find more options? - Marco 🧭"


async def _search_and_reason_impl(prompt, key, cache_key, context_venues, query, session=None):
    own_session = False
    if session is None:
        from .utils import get_session
        session = await get_session()
        own_session = True
    
    try:
        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 256,
                "temperature": 0.7,
            },
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                print(f"DEBUG: Groq API Error {response.status}: {await response.text()}")
            if response.status == 200:
                res_data = await response.json()
                answer = res_data["choices"][0]["message"]["content"]
                if answer and answer.strip():
                    ans = answer.strip()
                    # Enhance response with specific venue references
                    ans = enhance_with_osm_data(ans, context_venues, query)
                    try:
                        _cache_set(cache_key, ans, source="groq")
                    except Exception:
                        pass
                    return ans
    except Exception as e:
        print(f"DEBUG: Groq API call failed with exception: {e}")
        pass
    finally:
        if own_session and session:
            await session.close()

    # Smarter fallback if AI fails
    if context_venues:
        import random
        pool = context_venues[:5] if len(context_venues) >= 5 else context_venues
        v = random.choice(pool)
        name = v.get("name", "this spot")
        fallback = f"Based on your interests, My compass is spinning, but looking at our map, **{name}** stands out! Based on my logs, it should be a fine spot for your quest. Safe travels! - Marco"
        try:
            _cache_set(cache_key, fallback, source="fallback")
        except Exception:
            pass
        return fallback

    # Venue-aware fallback
    if context_venues:
        # Use actual venue names in fallback
        venue_names = [v.get('name') for v in context_venues[:3] if v.get('name')]
        if venue_names:
            names_str = ", ".join(venue_names)
            fallback2 = f"Based on your interests, While my compass is adjusting, check out {names_str} - they look promising based on local data! - Marco"
        else:
            fallback2 = "Based on your interests, I'm exploring this area! The venues on your screen have good local ratings. - Marco"
    else:
        fallback2 = "Based on your interests, I'm ready to explore! Search for a specific place to get detailed recommendations. - Marco"
    try:
        _cache_set(cache_key, fallback2, source="fallback")
    except Exception:
        pass
    return fallback2


# ============================================================
# NEW CONVERSATION OPTIMIZATION FUNCTIONS
# Added for improved Marco travel conversations
# ============================================================

def create_conversation_prompt(query, city, venues, weather, history):
    """Create a natural conversation-style prompt for Marco.
    
    This prompt is designed to:
    1. Reference specific venues by name
    2. Remember what user asked before
    3. Ask natural follow-up questions
    4. Avoid generic responses
    """
    
    # Build conversation memory context
    memory = ConversationMemory(history)
    followup_context = memory.get_followup_context()
    
    # Venue context
    venue_context = create_rich_venue_context(venues, query)
    
    # Weather context
    weather_context = ""
    if weather:
        temp = weather.get('temperature_c', 20)
        conditions = weather.get('weathercode', 0)
        icons = {
            0: "☀️ Clear", 1: "🌤️ Mainly clear", 2: "⛅ Partly cloudy", 3: "☁️ Overcast",
            45: "🌫️ Fog", 51: "🌦️ Light drizzle", 61: "🌦️ Slight rain",
            71: "🌨️ Slight snow", 80: "🌧️ Rain showers", 95: "⛈️ Thunderstorm"
        }
        w_summary = icons.get(conditions, "Unknown")
        weather_context = f"\n🌤️ Current weather: {w_summary}, {temp}°C"
        
        # Weather-based advice
        if conditions in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            weather_context += " (rainy - indoor spots or covered seating recommended)"
        elif conditions in [71, 73, 75]:
            weather_context += " (snowy - cozy indoor venues ideal)"
        elif temp > 28:
            weather_context += " (hot - places with AC or outdoor shade)"
        elif temp < 10:
            weather_context += " (chilly - warm, cozy spots recommended)"
    
    # Detect if this is a follow-up
    is_followup = memory.should_reference_previous()
    user_interests = memory.get_interests_str()
    
    # Build the system prompt
    system_prompt = """You are Marco, an experienced travel guide! 🗺️

Your personality:
- Enthusiastic but knowledgeable
- Speak like a local expert, not a robot
- Reference specific places by NAME when you recommend them
- Ask natural follow-up questions to keep conversation going
- Never say "Tell me more about what you're looking for"
- Never give generic responses like "I recommend exploring"
- Always explain WHY a place is good for the user's specific interest

Rules for responses:
1. If user asks about coffee, mention SPECIFIC coffee shops by name
2. If user asks about food, recommend SPECIFIC restaurants with cuisines
3. Reference the VENUE DATA provided - don't make up places
4. If user asks follow-up, reference what they asked before
5. End with a natural question, not a generic invitation

Example of GOOD response:
"Based on your interest in dark roast, **Blue Bottle Coffee** on High Street is excellent - they specialize in bold espresso roasts and have a cozy atmosphere. For something more intimate, **Temple Coffee** nearby offers single-origin beans with knowledgeable baristas. Both are within walking distance of each other. Would you like more details on either, or are you looking for something with outdoor seating?"

Example of BAD response (NEVER do this):
"I recommend trying local coffee shops. Tell me more about what you're looking for!" """

    # Build conversation context
    conversation_context = ""
    if is_followup and followup_context:
        conversation_context = f"\n📜 CONVERSATION CONTEXT:\n{followup_context}\n"
    
    # Query analysis
    q_lower = query.lower()
    is_followup_q = any(kw in q_lower for kw in ['what about', 'and', 'also', 'too', 'more', 'other', 'another'])
    
    # User intent detection
    intent = "general"
    if any(kw in q_lower for kw in ['dark', 'black', 'strong', 'bold', 'espresso']):
        intent = "dark_coffee"
    elif any(kw in q_lower for kw in ['cheap', 'budget', 'affordable', 'under']):
        intent = "budget"
    elif any(kw in q_lower for kw in ['outdoor', 'patio', 'terrace', 'garden']):
        intent = "outdoor"
    elif any(kw in q_lower for kw in ['cozy', 'romantic', 'quiet', 'intimate']):
        intent = "atmosphere"
    
    # Build user message based on context
    user_message = f"""Traveler asks: "{query}"

{city or 'This area'} - {intent.upper()} query{weather_context}{conversation_context}

{venue_context}

User's stated interests: {user_interests}

Response requirements:
1. If this is a follow-up question, REFERENCE what they asked before
2. If venues are listed, recommend SPECIFIC ones by NAME
3. Explain WHY each recommendation fits their request
4. Give practical details (location, price hints, atmosphere)
5. Ask a natural follow-up question

{"This appears to be a follow-up question - build on previous context." if is_followup_q else ""}

Remember: You're a local expert. Be specific, helpful, and conversational! 🧭"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]


def create_venue_recommendation(query, city, venues, limit=3):
    """Create a concise venue recommendation for quick responses."""
    if not venues:
        return f"I don't have specific venue data for {city} yet. Try searching for the type of place you're looking for!"
    
    recommendations = []
    for venue in venues[:limit]:
        name = venue.get('name', 'Local spot')
        venue_type = venue.get('type', 'venue').title()
        tags = venue.get('tags', {})
        cuisine = tags.get('cuisine', '').title()
        
        if cuisine:
            desc = f"{cuisine} {venue_type}"
        else:
            desc = venue_type
        
        # Get address
        address = venue.get('display_address') or venue.get('address', '')
        if address:
            address = f" at {address}"
        
        recommendations.append(f"• **{name}** - {desc}{address}")
    
    if len(venues) > limit:
        recommendations.append(f"• ...and {len(venues) - limit} more great spots!")
    
    return f"Here are my top picks in {city}:\n\n" + "\n".join(recommendations)


# Export semantic module interface
semantic = {
    'analyze_any_query': analyze_any_query,
    'build_response_for_any_query': build_response_for_any_query,
    'handle_followup_conversation': handle_followup_conversation,
    'build_neighborhood_response': build_neighborhood_response,
    'handle_general_question': handle_general_question,
    'build_conversation_continuation': build_conversation_continuation,
    'handle_venue_request': handle_venue_request,
    'build_venue_suggestions': build_venue_suggestions,
    'engage_and_explore': engage_and_explore,
    'create_venue_context_string': create_venue_context_string,
    'ConversationMemory': ConversationMemory,
    'ConversationAnalyzer': ConversationAnalyzer,
    'create_rich_venue_context': create_rich_venue_context,
    'build_marco_prompt': build_marco_prompt,
    'build_focused_marco_prompt': build_focused_marco_prompt,
    'build_mandatory_venues_prompt': build_mandatory_venues_prompt,
    'enhance_marco_response': enhance_marco_response,
    'enhance_with_osm_data': enhance_with_osm_data,
    'get_poi_type_from_query': get_poi_type_from_query,
    'summarize_results': summarize_results,
    'apply_response_safeguards': apply_response_safeguards,
    'produce_concrete_response': produce_concrete_response,
    'create_conversation_prompt': create_conversation_prompt,
    'create_venue_recommendation': create_venue_recommendation,
    'InMemoryIndex': InMemoryIndex,
}
