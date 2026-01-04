"""
Google Places API integration for restaurant and venue discovery.
Provides rich data including ratings, reviews, price levels, and contact information.
"""

import os
import googlemaps
from typing import List, Dict, Optional

# Initialize Google Maps client
GOOGLE_PLACES_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')
gmaps = googlemaps.Client(key=GOOGLE_PLACES_API_KEY) if GOOGLE_PLACES_API_KEY else None


def map_price_level_to_budget(price_level: Optional[int]) -> tuple:
    """
    Map Google Places price_level (0-4) to budget categories.
    
    Args:
        price_level: Integer from 0-4 representing price level
                    0 = Free, 1 = Inexpensive, 2 = Moderate, 3 = Expensive, 4 = Very Expensive
    
    Returns:
        tuple: (budget_category, price_range_symbol)
               budget_category: 'cheap', 'mid', or 'expensive'
               price_range_symbol: '$', '$$', '$$$', or '$$$$'
    """
    if price_level is None or price_level == 0:
        return ('cheap', '$')
    elif price_level == 1:
        return ('cheap', '$')
    elif price_level == 2:
        return ('mid', '$$')
    elif price_level == 3:
        return ('expensive', '$$$')
    elif price_level == 4:
        return ('expensive', '$$$$')
    else:
        # Fallback for unknown price levels
        return ('mid', '$$')


def get_google_places_details(place_id: str) -> Optional[Dict]:
    """
    Get detailed information about a place from Google Places API.
    
    Args:
        place_id: Google Places ID
    
    Returns:
        Dictionary with detailed place information or None if unavailable
    """
    if not gmaps:
        return None
    
    try:
        result = gmaps.place(place_id=place_id, fields=[
            'name', 'rating', 'user_ratings_total', 'price_level',
            'formatted_phone_number', 'website', 'formatted_address',
            'geometry', 'types'
        ])
        
        if result and result.get('status') == 'OK':
            return result.get('result', {})
        return None
    except Exception as e:
        print(f"Error fetching place details: {e}")
        return None


def discover_restaurants(city: str, limit: int = 200, cuisine: Optional[str] = None) -> List[Dict]:
    """
    Discover restaurants in a city using Google Places API.
    
    Args:
        city: City name to search in
        limit: Maximum number of results (default 200)
        cuisine: Optional cuisine type to filter by
    
    Returns:
        List of dictionaries with restaurant information
    """
    if not gmaps:
        print("Google Places API key not configured")
        return []
    
    results = []
    
    try:
        # Build search query
        query = f"restaurants in {city}"
        if cuisine:
            query = f"{cuisine} restaurants in {city}"
        
        # Perform text search (returns up to 60 results per call)
        search_results = gmaps.places(query=query)
        
        if not search_results or search_results.get('status') not in ['OK', 'ZERO_RESULTS']:
            return []
        
        places = search_results.get('results', [])
        
        # Process each place
        for place in places[:limit]:
            try:
                # Get basic info
                place_id = place.get('place_id')
                name = place.get('name', 'Unknown')
                rating = place.get('rating')
                user_ratings_total = place.get('user_ratings_total', 0)
                price_level = place.get('price_level')
                
                # Map price level to budget category
                budget, price_range = map_price_level_to_budget(price_level)
                
                # Get location
                location = place.get('geometry', {}).get('location', {})
                lat = location.get('lat', 0)
                lng = location.get('lng', 0)
                
                # Get address
                address = place.get('formatted_address', place.get('vicinity', ''))
                
                # Build venue object
                venue = {
                    'id': place_id,
                    'name': name,
                    'budget': budget,
                    'price_range': price_range,
                    'rating': rating,
                    'user_ratings_total': user_ratings_total,
                    'description': ', '.join(place.get('types', [])),
                    'address': address,
                    'latitude': lat,
                    'longitude': lng,
                    'place_id': place_id,
                    'city': city,
                    'amenity': 'restaurant',
                    'tags': ', '.join(place.get('types', [])),
                    'website': None,  # Will be fetched if needed
                    'phone': None,     # Will be fetched if needed
                    'osm_url': f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                    'provider': 'google_places'
                }
                
                results.append(venue)
                
                if len(results) >= limit:
                    break
                    
            except Exception as e:
                print(f"Error processing place: {e}")
                continue
        
        # Get next page token if available and we need more results
        next_page_token = search_results.get('next_page_token')
        while next_page_token and len(results) < limit:
            try:
                import time
                time.sleep(2)  # Required delay for next_page_token to become valid
                
                next_results = gmaps.places(page_token=next_page_token)
                if not next_results or next_results.get('status') != 'OK':
                    break
                
                next_places = next_results.get('results', [])
                for place in next_places:
                    if len(results) >= limit:
                        break
                    
                    try:
                        place_id = place.get('place_id')
                        name = place.get('name', 'Unknown')
                        rating = place.get('rating')
                        user_ratings_total = place.get('user_ratings_total', 0)
                        price_level = place.get('price_level')
                        
                        budget, price_range = map_price_level_to_budget(price_level)
                        
                        location = place.get('geometry', {}).get('location', {})
                        lat = location.get('lat', 0)
                        lng = location.get('lng', 0)
                        address = place.get('formatted_address', place.get('vicinity', ''))
                        
                        venue = {
                            'id': place_id,
                            'name': name,
                            'budget': budget,
                            'price_range': price_range,
                            'rating': rating,
                            'user_ratings_total': user_ratings_total,
                            'description': ', '.join(place.get('types', [])),
                            'address': address,
                            'latitude': lat,
                            'longitude': lng,
                            'place_id': place_id,
                            'city': city,
                            'amenity': 'restaurant',
                            'tags': ', '.join(place.get('types', [])),
                            'website': None,
                            'phone': None,
                            'osm_url': f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                            'provider': 'google_places'
                        }
                        
                        results.append(venue)
                    except Exception as e:
                        print(f"Error processing next page place: {e}")
                        continue
                
                next_page_token = next_results.get('next_page_token')
                
            except Exception as e:
                print(f"Error fetching next page: {e}")
                break
        
        return results
        
    except Exception as e:
        print(f"Error discovering restaurants: {e}")
        return []


def enrich_venue_with_details(venue: Dict) -> Dict:
    """
    Enrich a venue with additional details from Google Places API.
    
    Args:
        venue: Venue dictionary with at least a place_id
    
    Returns:
        Updated venue dictionary with additional details
    """
    if not gmaps or not venue.get('place_id'):
        return venue
    
    try:
        details = get_google_places_details(venue['place_id'])
        if details:
            venue['phone'] = details.get('formatted_phone_number')
            venue['website'] = details.get('website')
            
            # Update rating if not present
            if not venue.get('rating') and details.get('rating'):
                venue['rating'] = details.get('rating')
                venue['user_ratings_total'] = details.get('user_ratings_total', 0)
        
        return venue
    except Exception as e:
        print(f"Error enriching venue: {e}")
        return venue
