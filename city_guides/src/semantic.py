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
    from ..groq.traveland_rag import recommend_venues_rag, recommend_neighborhoods_rag
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
    venue_keywords = ['restaurant', 'cafe', 'coffee', 'bar', 'pub', 'food', 'eat', 'drink', 'shop', 'store', 'museum', 'park', 'attraction']
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
                return f"That's awesome you found great pubs! Since you're asking about traditional Irish pubs in {city}, would you like recommendations for:\n\n• More authentic Irish pubs with live music?\n• Historic pubs with traditional atmosphere?\n• Pubs known for their Guinness or local brews?\n\nOr would you like me to suggest some top-rated traditional spots?"
        return f"Excellent pub discoveries! What would you like to know about traditional Irish pubs in {city}? I can help with recommendations for different styles, atmospheres, or specific areas."
    
    if "coffee" in query_lower or "cafe" in query_lower:
        if venues:
            coffee_venues = [v for v in venues if 'coffee' in v.get('type', '').lower() or 'cafe' in v.get('type', '').lower()]
            if coffee_venues:
                return f"That's awesome you found good coffee! Since you're asking about coffee in {city} generally, are you interested in:\n\n• Other great coffee spots across the city?\n• Specific coffee styles (local roasters, specialty brews)?\n• Coffee shops with particular amenities (outdoor seating, WiFi)?\n\nOr would you like me to suggest some top-rated options based on local data?"
        return f"Excellent coffee discoveries! What would you like to know about coffee in {city}? I can help with recommendations for different neighborhoods, coffee styles, or specific amenities you're looking for."
    
    if "food" in query_lower or "restaurant" in query_lower or "eat" in query_lower:
        if venues:
            food_venues = [v for v in venues if v.get('type', '').lower() in ['restaurant', 'food']]
            if food_venues:
                return f"That's great you found good food! Since you're asking about dining in {city}, are you interested in:\n\n• Different cuisines or types of restaurants?\n• Specific neighborhoods with great food scenes?\n• Restaurants with particular atmospheres or price ranges?\n\nOr would you like me to recommend some top-rated dining options?"
        return f"Excellent food discoveries! What would you like to know about dining in {city}? I can help with recommendations for different cuisines, neighborhoods, or specific types of restaurants."
    
    # Generic followup
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


def build_venue_suggestions(query, venues, city):
    """Build suggestions when user wants specific venue types"""
    if not venues:
        return f"I'd be happy to help you find what you're looking for in {city}! Could you be more specific about the type of place?"

    # This will be handled by AI with venue context
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
    
    def should_escalate(self) -> bool:
        """Determine if Marco should provide concrete information"""
        return (
            self.user_frustration >= 1 or
            self.topic_depth >= 2 or
            self.repeated_response_count >= 1
        )
    
    def get_response_strategy(self) -> str:
        """Determine best response strategy"""
        if self.user_frustration >= 1:
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
    
    return f"""You're Marco, a local travel expert! 🗺️

**QUESTION TO ANSWER:** "{query}"

{history_context}
{venue_context}
{weather_advice}
{neighborhood_context}

**Your mission:**
- Answer the QUESTION TO ANSWER above directly
- Recommend specific venues from the list above when relevant
- Explain WHY each recommendation fits their request
- Use the weather context for practical advice
- Mention neighborhood characteristics when relevant
- Keep it friendly but focused on the actual data

**Response format:**
Start with 2-3 specific venue recommendations, then add general area advice.

Ready to explore! 🧭"""

def enhance_marco_response(response_text, venues):
    """Add specific venue references to Marco's response"""
    if not venues or not response_text:
        return response_text
    
    # Look for general mentions that could be linked to specific venues
    response_lower = response_text.lower()
    
    # Check if response mentions venue types but not specific names
    venue_types = ['restaurant', 'cafe', 'bar', 'pub', 'coffee', 'bakery']
    mentioned_types = [vt for vt in venue_types if vt in response_lower]
    
    if mentioned_types and not any(venue['name'].lower() in response_lower for venue in venues if venue.get('name')):
        # Response mentions types but not specific venues - enhance it
        relevant_venues = []
        for venue in venues[:3]:
            name = venue.get('name', '')
            venue_type = venue.get('type', '').lower()
            if name and any(mt in venue_type for mt in mentioned_types):
                relevant_venues.append(venue)
        
        if relevant_venues:
            enhancement = "\n\nBased on local data, I'd recommend:\n"
            for i, venue in enumerate(relevant_venues[:2]):
                name = venue.get('name')
                desc = venue.get('description', 'local spot')
                enhancement += f"• **{name}** - {desc}\n"
            
            response_text += enhancement
    
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
                                pattern = re.compile(rf"(\*\*{re.escape(name)}\*\*|{re.escape(name)})", re.IGNORECASE)
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

            fallback = f"Ahoy! 🧭 Based on your interests in '{query}', I'd recommend exploring these {city or 'city'} neighborhoods:\n\n" + "\n".join(neighborhood_list) + "\n\nClick any neighborhood to focus your search there! - Marco 🗺️"
        elif names:
            fallback = f"Recommended neighborhoods for '{query}': {', '.join(names)}. Try selecting one to explore venues there."
        else:
            fallback = f"Ahoy! 🧭 I'm exploring {city or 'this city'}! Try searching for a specific place above to help me navigate better. - Marco"
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
                            pattern = re.compile(rf"(\*\*{re.escape(name)}\*\*|{re.escape(name)})", re.IGNORECASE)
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

        fallback = f"Ahoy! 🧭 Based on your interests in '{query}', I'd recommend exploring these {city or 'city'} neighborhoods:\n\n" + "\n".join(neighborhood_list) + "\n\nClick any neighborhood to focus your search there! - Marco 🗺️"
    elif names:
        fallback = f"Recommended neighborhoods for '{query}': {', '.join(names)}. Try selecting one to explore venues there."
    else:
        fallback = f"Ahoy! 🧭 I'm exploring {city or 'this city'}! Try searching for a specific place above to help me navigate better. - Marco"
    try:
        _cache_set(cache_key, fallback, source="fallback")
    except Exception:
        pass
    return fallback


from typing import Optional

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
                return f"Ahoy! 🪙 As your trusty currency converter, here's the exchange: {result}. Safe travels with your coins!"
            else:
                return f"Currency conversion: {result}"
        else:
            if mode == "explorer":
                return "Arrr, I couldn't parse that currency request. Try 'convert 100 USD to EUR'!"
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
                    return f"Ahoy! 🧭 The current weather in {city or 'this city'} is: {summary}. {details}. Safe travels! - Marco"
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
                print("DEBUG: Early escalation - attempting local auto-enrichment of venues before other logic")
                enriched = await multi_provider.async_discover_pois(city or '', poi_type='restaurant', limit=6)
                if enriched:
                    print(f"DEBUG: Early auto-enrichment found {len(enriched)} venues; returning concrete response")
                    return produce_concrete_response(query, city, enriched, conv_analyzer)
            except Exception as e:
                print(f"DEBUG: Early auto-enrichment failed: {e}")
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
                "tell me more about what you're looking for",
                "i'm ready to explore",
                "could you tell me more",
                "what would you like to know",
            ]
            is_generic_sr = any(p in lower_sr for p in generic_checks) or lower_sr.strip().endswith('?')
            print(f"DEBUG: is_generic_sr={is_generic_sr}")
        except Exception:
            is_generic_sr = False

        # If analyzer suggests escalation and the smart_response is generic, skip the quick return
        if conv_analyzer.should_escalate() and is_generic_sr:
            # continue to AI/Groq path to get concrete suggestions
            pass
        else:
            if mode == "explorer":
                return f"Ahoy! 🧭 {smart_response} - Marco"
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
    if conv_analyzer.should_escalate():
        prompt = f"""You are Marco, a helpful travel assistant! 🗺️

User query: "{query}"

CONVERSATION CONTEXT:
- Current topic: {conv_analyzer.topic}
- User frustration: {conv_analyzer.user_frustration}/3
- Response repetition: {conv_analyzer.repeated_response_count}/3

{weather_context}
{venue_context}

CRITICAL INSTRUCTIONS:
1. NEVER repeat previous responses
2. If user frustration is high, acknowledge it and provide CONCRETE information
3. If topic is established, go deeper into that topic with SPECIFIC examples
4. Use venue data to provide actual recommendations
5. NEVER say "Tell me more about what you're looking for"
6. NEVER ask generic questions when user has been specific

Response format:
- Start with specific recommendations or information
- Be concise but informative
- Sign off as "- Marco 🧭"

Example of GOOD response (if user asked about coffee):
"Ahoy! 🧭 Based on your interest in coffee, I found these spots in {city or 'the area'}:
• Blue Bottle Coffee (known for dark roasts)
• Philz Coffee (specialty pour-overs)
Would you like details about any of these?"

Example of BAD response:
"Tell me more about what you're looking for!" (NEVER use this)"""
    else:
        prompt = f"""You are Marco, a helpful travel assistant! 🗺️

User query: "{query}"
{weather_context}
{venue_context}

INSTRUCTIONS:
1. Answer the specific question asked
2. If user mentioned something specific (e.g., "dark coffee"), address it directly
3. Use venue data when available
4. Keep responses concise and helpful
5. Sign off as "- Marco 🧭" """

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
            return "Ahoy! 🪙 My explorer's eyes are tired. Try searching for a specific place above first! - Marco"

        # 2. Otherwise, if escalation is needed and we lack venue context, try to auto-enrich locally
        try:
            print(f"DEBUG: conv_analyzer state: topic={conv_analyzer.topic}, frustration={conv_analyzer.user_frustration}, should_escalate={conv_analyzer.should_escalate()}")
        except Exception:
            pass
        if conv_analyzer.should_escalate() and (not context_venues or len(context_venues) == 0):
            try:
                from city_guides.providers import multi_provider
                print("DEBUG: Escalation requested - attempting local auto-enrichment of venues")
                enriched = await multi_provider.async_discover_pois(city or '', poi_type='restaurant', limit=6)
                if enriched:
                    print(f"DEBUG: Auto-enrichment found {len(enriched)} venues; returning concrete response")
                    return produce_concrete_response(query, city, enriched, conv_analyzer)
            except Exception as e:
                print(f"DEBUG: Auto-enrichment attempt failed: {e}")

        # 2. Otherwise, call Groq as before
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
            fallback = f"Ahoy! 🧭 My compass is spinning, but looking at our map, **{name}** stands out! Based on my logs, it should be a fine spot for your quest. Safe travels! - Marco"
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
                fallback2 = f"Ahoy! 🧭 While my compass is adjusting, check out {names_str} - they look promising based on local data! - Marco"
            else:
                fallback2 = "Ahoy! 🧭 I'm exploring this area! The venues on your screen have good local ratings. - Marco"
        else:
            fallback2 = "Ahoy! 🧭 I'm ready to explore! Search for a specific place to get detailed recommendations. - Marco"
        try:
            _cache_set(cache_key, fallback2, source="fallback")
        except Exception:
            pass
        return fallback2
    except Exception as e:
        print(f"DEBUG: Groq Exception: {e}")
        if context_venues:
            fallback = f"Ahoy! 🧭 My compass is spinning, but **{context_venues[0].get('name')}** on your screen looks like a treasure! - Marco"
            try:
                _cache_set(cache_key, fallback, source="fallback")
            except Exception:
                pass
            return fallback
        fallback3 = "Ahoy! � I'm ready for adventure! - Marco"
        try:
            _cache_set(cache_key, fallback3, source="fallback")
        except Exception:
            pass
        return fallback3


def apply_response_safeguards(response, query, history, venues, analyzer, city=None):
    """Fix generic responses and ensure conversation flow"""
    if not response:
        return response

    # Check for generic fallbacks
    generic_phrases = [
        "tell me more about what you're looking for",
        "i'm ready to explore",
        "search for a specific place",
        "click any neighborhood",
        "i'd recommend exploring",
        "i'm ready for adventure",
        "ready for adventure",
        "ready to explore",
    ]
    is_generic = any(phrase in response.lower() for phrase in generic_phrases)

    # Check if user was specific but Marco is generic
    user_specific = any(term in query.lower() for term in [
        'dark', 'black', 'espresso', 'museum', 'park', 'transport', 'history'
    ])

    if is_generic and (user_specific or analyzer.should_escalate()):
        topic = analyzer.topic if analyzer.topic != "general" else "travel"
        venue_names = [v.get('name') for v in venues[:3] if v.get('name')] if venues else []
        if venue_names:
            return (
                f"Ahoy! 🧭 I understand you're interested in {topic} - here are specific places: "
                f"{', '.join(venue_names)}. Would you like details about any of these?"
            )

        # Fallback to specific venue types
        venue_types = []
        if venues:
            venue_types = list(set(v.get('type', 'spot') for v in venues if v.get('type')))

        return (
            f"Ahoy! 🧭 For {topic} in {city or 'this area'}, I recommend exploring: "
            f"{', '.join(venue_types[:2]) if venue_types else 'local spots'}. "
            f"What specifically about them would you like to know?"
        )

    # Check for repeated responses
    if history and response and history.count(response) > 1:
        return "Ahoy! 🧭 I realize I'm repeating myself - let me give you concrete information: [Specific details based on venue data]"

    return response


def produce_concrete_response(query, city, venues, analyzer):
    """Force a concrete, venue-based response when conversation needs escalation."""
    topic = analyzer.topic if analyzer and analyzer.topic != "general" else None
    q_lower = (query or "").lower()

    # Use provided venues if available
    if venues and len(venues) > 0:
        venue_lines = []
        for v in venues[:3]:
            name = v.get('name') or v.get('title') or 'Local spot'
            desc = v.get('description') or v.get('type') or ''
            addr = v.get('address') or v.get('display_address') or ''
            line = f"• {name} — {desc}" + (f" ({addr})" if addr else "")
            venue_lines.append(line)
        header_topic = topic or (q_lower.split()[0] if q_lower else 'travel')
        return (
            f"Ahoy! 🧭 I understand you're interested in {header_topic} — here are specific places in {city or 'this area'}:\n"
            + "\n".join(venue_lines)
            + "\nWould you like details about any of these? - Marco 🧭"
        )

    # Fallback to bundled data in data/venues.json
    try:
        root = Path(__file__).resolve().parents[1]
        vfile = root / 'data' / 'venues.json'
        if vfile.exists():
            with open(vfile, 'r', encoding='utf-8') as f:
                allv = json.load(f)
            matches = []
            c_low = (city or '').lower()
            for v in allv:
                if c_low and c_low in (v.get('city') or '').lower():
                    matches.append(v)
            if not matches:
                matches = allv[:3]
            venue_lines = [f"• {v.get('name')} — {v.get('description')}" for v in matches[:3]]
            return (
                f"Ahoy! 🧭 Here are some specific suggestions for {city or 'this area'}:\n"
                + "\n".join(venue_lines)
                + "\nWould you like details about any of these? - Marco 🧭"
            )
    except Exception:
        pass

    # Last-resort concrete suggestions based on query keywords
    if any(k in q_lower for k in ['coffee', 'cafe', 'espresso', 'dark']):
        return (
            f"Ahoy! 🧭 I found several coffee-focused spots nearby: try searching for 'roaster', 'specialty cafe', or 'espresso bar' in {city or 'this area'}. "
            f"If you want, I can list top picks by neighborhood. - Marco 🧭"
        )

    return response if (response := ("Ahoy! 🧭 Here are some concrete suggestions: check local cafes and restaurants in the neighborhoods shown.")) else response


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
        fallback = f"Ahoy! 🧭 My compass is spinning, but looking at our map, **{name}** stands out! Based on my logs, it should be a fine spot for your quest. Safe travels! - Marco"
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
            fallback2 = f"Ahoy! 🧭 While my compass is adjusting, check out {names_str} - they look promising based on local data! - Marco"
        else:
            fallback2 = "Ahoy! 🧭 I'm exploring this area! The venues on your screen have good local ratings. - Marco"
    else:
        fallback2 = "Ahoy! 🧭 I'm ready to explore! Search for a specific place to get detailed recommendations. - Marco"
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
