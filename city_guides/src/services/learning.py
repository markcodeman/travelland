# Learning service - handles suggestion weights and tracking

# Simple in-memory learning storage
_location_weights = {}

def get_location_weight(location):
    """Get learning weight for a location"""
    return _location_weights.get(location.lower(), 1.0)

def increment_location_weight(location):
    """Increment weight for successful location"""
    key = location.lower()
    _location_weights[key] = _location_weights.get(key, 1.0) + 0.1

def detect_hemisphere_from_searches():
    """Detect user's hemisphere from search patterns"""
    try:
        recent_searches = list(_location_weights.keys())[-10:]  # Last 10 searches
    except:
        recent_searches = []
    
    southern_cities = {'sydney', 'melbourne', 'rio de janeiro', 'cape town'}
    northern_cities = {'paris', 'london', 'new york', 'tokyo'}
    
    southern_count = sum(1 for city in recent_searches if city in southern_cities)
    northern_count = sum(1 for city in recent_searches if city in northern_cities)
    
    return 'southern' if southern_count > northern_count else 'northern'
