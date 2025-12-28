"""
Google Places API provider for discovering restaurants and points of interest.
"""
import os
import requests
from typing import List, Dict, Optional


GOOGLE_PLACES_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')


def discover_restaurants_places(city: str, cuisine: Optional[str] = None, limit: int = 20) -> List[Dict]:
    """
    Discover restaurants using Google Places API.
    
    Args:
        city: City name to search in
        cuisine: Optional cuisine type filter
        limit: Maximum number of results to return
        
    Returns:
        List of restaurant dictionaries with standardized format
    """
    if not GOOGLE_PLACES_API_KEY:
        raise ValueError("GOOGLE_PLACES_API_KEY environment variable not set")
    
    # First, geocode the city to get coordinates
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    geocode_params = {
        'address': city,
        'key': GOOGLE_PLACES_API_KEY
    }
    
    try:
        geocode_resp = requests.get(geocode_url, params=geocode_params, timeout=10)
        geocode_resp.raise_for_status()
        geocode_data = geocode_resp.json()
        
        if geocode_data.get('status') != 'OK' or not geocode_data.get('results'):
            raise ValueError(f"Could not geocode city: {city}")
        
        location = geocode_data['results'][0]['geometry']['location']
        lat = location['lat']
        lng = location['lng']
        
    except Exception as e:
        raise ValueError(f"Geocoding failed: {str(e)}")
    
    # Now search for restaurants near this location
    places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    
    # Build search query based on cuisine
    search_type = "restaurant"
    keyword = cuisine if cuisine else "restaurant"
    
    places_params = {
        'location': f"{lat},{lng}",
        'radius': 5000,  # 5km radius
        'type': search_type,
        'keyword': keyword,
        'key': GOOGLE_PLACES_API_KEY
    }
    
    try:
        places_resp = requests.get(places_url, params=places_params, timeout=10)
        places_resp.raise_for_status()
        places_data = places_resp.json()
        
        if places_data.get('status') not in ['OK', 'ZERO_RESULTS']:
            raise ValueError(f"Places API error: {places_data.get('status')}")
        
        results = []
        for place in places_data.get('results', [])[:limit]:
            # Get more details for each place
            place_details = _get_place_details(place['place_id'])
            
            # Determine budget based on price_level
            price_level = place.get('price_level', 2)
            if price_level <= 1:
                budget = 'cheap'
                price_range = '$'
            elif price_level == 2:
                budget = 'mid'
                price_range = '$$'
            else:
                budget = 'expensive'
                price_range = '$$$'
            
            # Build address string
            address = place.get('vicinity', '')
            
            # Build description with cuisine types
            types = place.get('types', [])
            cuisine_types = [t.replace('_', ' ').title() for t in types if t not in ['restaurant', 'food', 'point_of_interest', 'establishment']]
            description = ', '.join(cuisine_types[:3]) if cuisine_types else 'Restaurant'
            
            # Get rating and user ratings count
            rating = place.get('rating', 0)
            user_ratings_total = place.get('user_ratings_total', 0)
            
            venue = {
                'id': place['place_id'],
                'city': city,
                'name': place.get('name', 'Unknown'),
                'budget': budget,
                'price_range': price_range,
                'description': description,
                'tags': ', '.join(cuisine_types),
                'address': address,
                'latitude': place['geometry']['location']['lat'],
                'longitude': place['geometry']['location']['lng'],
                'website': place_details.get('website', ''),
                'phone': place_details.get('formatted_phone_number', ''),
                'rating': rating,
                'user_ratings_total': user_ratings_total,
                'opening_hours': place.get('opening_hours', {}).get('open_now', None),
                'amenity': 'restaurant',
                'source': 'google_places'
            }
            results.append(venue)
        
        return results
        
    except Exception as e:
        raise ValueError(f"Places search failed: {str(e)}")


def _get_place_details(place_id: str) -> Dict:
    """
    Get additional details for a specific place.
    
    Args:
        place_id: Google Place ID
        
    Returns:
        Dictionary with place details
    """
    if not GOOGLE_PLACES_API_KEY:
        return {}
    
    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
    details_params = {
        'place_id': place_id,
        'fields': 'website,formatted_phone_number,opening_hours',
        'key': GOOGLE_PLACES_API_KEY
    }
    
    try:
        resp = requests.get(details_url, params=details_params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('status') == 'OK':
            return data.get('result', {})
        return {}
        
    except Exception:
        return {}
