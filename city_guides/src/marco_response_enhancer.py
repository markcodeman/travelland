"""
Marco Response Enhancer

This module provides enhanced response generation for Marco Chat to avoid
generic fallbacks and provide more specific, helpful responses.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from .venue_quality import calculate_venue_quality_score, filter_high_quality_venues


class MarcoResponseEnhancer:
    """Enhances Marco's responses to avoid generic fallbacks and provide specific recommendations."""
    
    def __init__(self):
        self.generic_phrases = [
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
            "i'm ready to help you discover",
            "i'm ready to help you explore",
            "i'm ready to help you find",
            "i'm ready to help you discover",
            "i'm ready to help you explore",
            "i'm ready to help you find",
        ]
        
        self.venue_keywords = [
            'restaurant', 'cafe', 'coffee', 'bar', 'pub', 'food', 'eat', 'drink',
            'shop', 'store', 'museum', 'park', 'attraction', 'pizza', 'taco', 
            'burger', 'sushi', 'italian', 'chinese', 'mexican', 'thai', 'indian',
            'french', 'japanese', 'korean', 'vietnamese', 'mediterranean', 
            'american', 'breakfast', 'lunch', 'dinner', 'snacks', 'dessert', 
            'bakery', 'ice cream', 'hotel', 'accommodation', 'hotel', 'hostel'
        ]
        
        self.transport_keywords = [
            'bus', 'metro', 'train', 'transport', 'transit', 'subway', 'tram',
            'ferry', 'station', 'stop', 'terminal', 'public transport'
        ]
        
        self.attraction_keywords = [
            'museum', 'attraction', 'landmark', 'tourist', 'sightseeing', 
            'monument', 'gallery', 'theatre', 'cinema', 'park', 'beach'
        ]
        
        self.neighborhood_keywords = [
            'neighborhood', 'area', 'district', 'explore', 'walk around', 
            'stroll', 'explore', 'discover', 'find'
        ]

    def is_generic_response(self, response: str) -> bool:
        """Check if a response is generic and should be enhanced."""
        if not response:
            return True
            
        response_lower = response.lower().strip()
        
        # Check for generic phrases
        for phrase in self.generic_phrases:
            if phrase in response_lower:
                return True
        
        # Check for responses that end with just a question mark (too generic)
        if len(response_lower) < 50 and response_lower.strip().endswith('?'):
            return True
            
        # Check for responses that are too short and generic
        if len(response_lower) < 30 and any(word in response_lower for word in ['explore', 'search', 'find']):
            return True
            
        return False

    def analyze_user_intent(self, query: str, venues: List[Dict]) -> Dict[str, Any]:
        """Analyze user query to determine intent and available data."""
        query_lower = query.lower().strip()
        
        intent = {
            'type': 'general',
            'specific_keywords': [],
            'has_venue_data': len(venues) > 0,
            'is_venue_request': False,
            'is_transport_request': False,
            'is_attraction_request': False,
            'is_neighborhood_request': False,
            'is_followup': False
        }
        
        # Check for venue-specific requests
        venue_matches = [kw for kw in self.venue_keywords if kw in query_lower]
        if venue_matches:
            intent['type'] = 'venue'
            intent['is_venue_request'] = True
            intent['specific_keywords'] = venue_matches
        
        # Check for transport requests
        transport_matches = [kw for kw in self.transport_keywords if kw in query_lower]
        if transport_matches:
            intent['type'] = 'transport'
            intent['is_transport_request'] = True
            intent['specific_keywords'] = transport_matches
        
        # Check for attraction requests
        attraction_matches = [kw for kw in self.attraction_keywords if kw in query_lower]
        if attraction_matches:
            intent['type'] = 'attraction'
            intent['is_attraction_request'] = True
            intent['specific_keywords'] = attraction_matches
        
        # Check for neighborhood requests
        neighborhood_matches = [kw for kw in self.neighborhood_keywords if kw in query_lower]
        if neighborhood_matches:
            intent['type'] = 'neighborhood'
            intent['is_neighborhood_request'] = True
            intent['specific_keywords'] = neighborhood_matches
        
        # Check for follow-up patterns
        followup_patterns = ['explored', 'found', 'visited', 'tried', 'been to', 'saw', 'discovered']
        if any(pattern in query_lower for pattern in followup_patterns):
            intent['is_followup'] = True
        
        return intent

    def get_specific_venue_recommendations(self, query: str, venues: List[Dict], limit: int = 3) -> List[Dict]:
        """Get specific venue recommendations based on query and venue data."""
        if not venues:
            return []
        
        # Filter for high-quality venues
        high_quality_venues = filter_high_quality_venues(venues)
        if not high_quality_venues:
            # If no high-quality venues, use all venues but warn
            high_quality_venues = venues[:10]
        
        query_lower = query.lower()
        
        # Sort venues by relevance
        scored_venues = []
        for venue in high_quality_venues:
            score = 0
            venue_lower = (venue.get('name', '') + ' ' + venue.get('description', '')).lower()
            
            # Boost score for keyword matches
            for keyword in self.venue_keywords:
                if keyword in query_lower and keyword in venue_lower:
                    score += 2
                elif keyword in venue_lower:
                    score += 0.5
            
            # Boost score for quality
            quality_score = venue.get('quality_score', 0)
            score += quality_score * 3
            
            # Boost score for complete information
            if venue.get('address') and venue.get('description'):
                score += 1
            
            scored_venues.append((score, venue))
        
        # Sort by score and return top venues
        scored_venues.sort(key=lambda x: x[0], reverse=True)
        return [venue for score, venue in scored_venues[:limit]]

    def create_venue_response(self, query: str, city: str, venues: List[Dict]) -> str:
        """Create a specific venue response."""
        recommendations = self.get_specific_venue_recommendations(query, venues)
        
        if not recommendations:
            return f"I don't have specific venue data for '{query}' in {city} yet. Try searching for a specific type of place!"
        
        # Build response with specific venue names
        response_parts = [f"Based on your interest in '{query}', here are some great spots in {city}:"]
        
        for i, venue in enumerate(recommendations, 1):
            name = venue.get('name', 'Local spot')
            description = venue.get('description', 'Great venue')
            address = venue.get('address', 'Nearby')
            quality_score = venue.get('quality_score', 0)
            
            # Add quality indicator
            quality_indicator = ""
            if quality_score >= 0.8:
                quality_indicator = "⭐ Highly recommended"
            elif quality_score >= 0.6:
                quality_indicator = "✓ Good option"
            
            response_parts.append(f"{i}. **{name}** - {description}")
            response_parts.append(f"   📍 {address} {quality_indicator}")
        
        response_parts.append("\nWould you like more details about any of these places?")
        response_parts.append("- Marco 🧭")
        
        return "\n".join(response_parts)

    def create_transport_response(self, query: str, city: str, venues: List[Dict]) -> str:
        """Create a specific transport response."""
        # Filter for transport-related venues
        transport_venues = []
        for venue in venues:
            tags_str = str(venue.get('tags', {})).lower()
            if any(keyword in tags_str for keyword in ['railway', 'station', 'bus', 'metro', 'tram', 'ferry']):
                transport_venues.append(venue)
        
        if transport_venues:
            response = f"Great news! I found some transport options in {city}:\n\n"
            for i, venue in enumerate(transport_venues[:3], 1):
                name = venue.get('name', 'Transport hub')
                description = venue.get('description', 'Transport station')
                address = venue.get('address', 'Nearby')
                response += f"{i}. **{name}** - {description}\n   📍 {address}\n\n"
            response += "These should help you get around the city! Need directions to any of these?\n- Marco 🧭"
            return response
        
        return f"I don't have specific transport data for {city} yet. Try searching for 'bus station', 'train station', or 'metro' to find transport options!\n- Marco 🧭"

    def create_attraction_response(self, query: str, city: str, venues: List[Dict]) -> str:
        """Create a specific attraction response."""
        # Filter for attraction-related venues
        attraction_venues = []
        for venue in venues:
            tags_str = str(venue.get('tags', {})).lower()
            if any(keyword in tags_str for keyword in ['museum', 'gallery', 'theatre', 'cinema', 'monument', 'tourism']):
                attraction_venues.append(venue)
        
        if attraction_venues:
            response = f"Excellent! I found some attractions in {city}:\n\n"
            for i, venue in enumerate(attraction_venues[:3], 1):
                name = venue.get('name', 'Attraction')
                description = venue.get('description', 'Interesting place')
                address = venue.get('address', 'Nearby')
                response += f"{i}. **{name}** - {description}\n   📍 {address}\n\n"
            response += "These should provide some great sightseeing opportunities! Want more details?\n- Marco 🧭"
            return response
        
        return f"I don't have specific attraction data for {city} yet. Try searching for 'museum', 'park', or 'landmark' to find things to see!\n- Marco 🧭"

    def create_neighborhood_response(self, query: str, city: str, neighborhoods: List[Dict]) -> str:
        """Create a specific neighborhood response."""
        if not neighborhoods:
            return f"I don't have neighborhood data for {city} yet. Try searching for a specific area or type of neighborhood!"
        
        # Get top 3 neighborhoods
        top_neighborhoods = neighborhoods[:3]
        
        response = f"Based on your interest in exploring, here are some great neighborhoods in {city}:\n\n"
        
        for i, neighborhood in enumerate(top_neighborhoods, 1):
            name = neighborhood.get('name', 'Neighborhood')
            description = neighborhood.get('description', 'Great area to explore')
            response += f"{i}. **{name}** - {description}\n\n"
        
        response += "Each of these areas has its own unique character and charm! Want to explore venues in any of these neighborhoods?\n- Marco 🧭"
        
        return response

    def enhance_response(self, original_response: str, query: str, city: str, venues: List[Dict], neighborhoods: List[Dict]) -> str:
        """Enhance a response to avoid generic fallbacks."""
        # If response is already good, return as-is
        if not self.is_generic_response(original_response):
            return original_response
        
        # Analyze user intent
        intent = self.analyze_user_intent(query, venues)
        
        # Create specific response based on intent
        if intent['is_venue_request']:
            return self.create_venue_response(query, city, venues)
        elif intent['is_transport_request']:
            return self.create_transport_response(query, city, venues)
        elif intent['is_attraction_request']:
            return self.create_attraction_response(query, city, venues)
        elif intent['is_neighborhood_request']:
            return self.create_neighborhood_response(query, city, neighborhoods)
        elif intent['is_followup']:
            return self.create_followup_response(query, city, venues)
        else:
            # Default fallback - still try to be specific
            if venues:
                return self.create_venue_response(query, city, venues)
            elif neighborhoods:
                return self.create_neighborhood_response(query, city, neighborhoods)
            else:
                return f"I'd love to help you explore {city}! Try searching for a specific type of place or neighborhood to get detailed recommendations.\n- Marco 🧭"

    def create_followup_response(self, query: str, city: str, venues: List[Dict]) -> str:
        """Create a response for follow-up questions."""
        query_lower = query.lower()
        
        # Check what they were interested in before
        if any(kw in query_lower for kw in ['coffee', 'cafe', 'espresso']):
            return self.create_coffee_response(query, city, venues)
        elif any(kw in query_lower for kw in ['food', 'restaurant', 'eat', 'dining']):
            return self.create_food_response(query, city, venues)
        elif any(kw in query_lower for kw in ['bar', 'pub', 'drink', 'drinks']):
            return self.create_drink_response(query, city, venues)
        else:
            # General follow-up
            if venues:
                return self.create_venue_response(query, city, venues)
            return f"Great question! Let me help you find more options in {city}. Try searching for what you're interested in!\n- Marco 🧭"

    def create_coffee_response(self, query: str, city: str, venues: List[Dict]) -> str:
        """Create a specific coffee response."""
        coffee_venues = []
        for venue in venues:
            tags_str = str(venue.get('tags', {})).lower()
            name_lower = venue.get('name', '').lower()
            if any(keyword in tags_str or keyword in name_lower for keyword in ['coffee', 'cafe', 'espresso', 'latte']):
                coffee_venues.append(venue)
        
        if coffee_venues:
            response = f"Excellent coffee choices in {city}:\n\n"
            for i, venue in enumerate(coffee_venues[:3], 1):
                name = venue.get('name', 'Coffee shop')
                description = venue.get('description', 'Great coffee')
                address = venue.get('address', 'Nearby')
                response += f"{i}. **{name}** - {description}\n   📍 {address}\n\n"
            response += "These spots should satisfy your coffee cravings! Want details on any of these?\n- Marco ☕"
            return response
        
        return f"I don't have specific coffee shop data for {city} yet. Try searching for 'coffee' or 'cafe' to find great spots!\n- Marco ☕"

    def create_food_response(self, query: str, city: str, venues: List[Dict]) -> str:
        """Create a specific food response."""
        food_venues = []
        for venue in venues:
            tags_str = str(venue.get('tags', {})).lower()
            name_lower = venue.get('name', '').lower()
            if any(keyword in tags_str or keyword in name_lower for keyword in ['restaurant', 'food', 'eat', 'dining']):
                food_venues.append(venue)
        
        if food_venues:
            response = f"Delicious food options in {city}:\n\n"
            for i, venue in enumerate(food_venues[:3], 1):
                name = venue.get('name', 'Restaurant')
                description = venue.get('description', 'Great food')
                address = venue.get('address', 'Nearby')
                response += f"{i}. **{name}** - {description}\n   📍 {address}\n\n"
            response += "These should satisfy your hunger! Want more details?\n- Marco 🍽️"
            return response
        
        return f"I don't have specific restaurant data for {city} yet. Try searching for 'restaurant' or specific cuisines!\n- Marco 🍽️"

    def create_drink_response(self, query: str, city: str, venues: List[Dict]) -> str:
        """Create a specific drink response."""
        drink_venues = []
        for venue in venues:
            tags_str = str(venue.get('tags', {})).lower()
            name_lower = venue.get('name', '').lower()
            if any(keyword in tags_str or keyword in name_lower for keyword in ['bar', 'pub', 'drink', 'cocktail', 'beer', 'wine']):
                drink_venues.append(venue)
        
        if drink_venues:
            response = f"Great places to grab a drink in {city}:\n\n"
            for i, venue in enumerate(drink_venues[:3], 1):
                name = venue.get('name', 'Bar')
                description = venue.get('description', 'Great drinks')
                address = venue.get('address', 'Nearby')
                response += f"{i}. **{name}** - {description}\n   📍 {address}\n\n"
            response += "These spots should have great drinks and atmosphere! Want more info?\n- Marco 🍻"
            return response
        
        return f"I don't have specific bar data for {city} yet. Try searching for 'bar' or 'pub' to find great spots!\n- Marco 🍻"


# Global enhancer instance
MARCO_ENHANCER = MarcoResponseEnhancer()


def enhance_marco_response(response: str, query: str, city: str, venues: List[Dict], neighborhoods: List[Dict]) -> str:
    """Enhance Marco's response to avoid generic fallbacks."""
    return MARCO_ENHANCER.enhance_response(response, query, city, venues, neighborhoods)


def is_generic_marco_response(response: str) -> bool:
    """Check if a Marco response is generic."""
    return MARCO_ENHANCER.is_generic_response(response)


def should_call_groq(result: Dict[str, Any], intent: Dict[str, Any]) -> bool:
    """Determine whether to call Groq API based on result quality and user intent."""
    # If result already has good quality content, skip Groq
    if result.get('quality_score', 0) >= 0.7:
        return False
    
    # If user has specific intent and we have venue data, call Groq for better recommendations
    if intent.get('is_venue_request') and intent.get('has_venue_data'):
        return True
    
    # If user is asking about neighborhoods and we have neighborhood data, call Groq
    if intent.get('is_neighborhood_request') and result.get('neighborhoods'):
        return True
    
    # If user is asking about transport and we have transport venues, call Groq
    if intent.get('is_transport_request') and any(v.get('tags', {}).get('railway') for v in result.get('venues', [])):
        return True
    
    # If user is asking about attractions and we have attraction venues, call Groq
    if intent.get('is_attraction_request') and any(v.get('tags', {}).get('tourism') for v in result.get('venues', [])):
        return True
    
    # For general queries with low quality results, call Groq
    if result.get('quality_score', 0) < 0.5:
        return True
    
    # Default: don't call Groq for high quality results
    return False

def analyze_user_intent(query: str, venues: List[Dict]) -> Dict[str, Any]:
    """Analyze user query to determine intent."""
    return MARCO_ENHANCER.analyze_user_intent(query, venues)
