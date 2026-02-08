"""
Suggestions routes: Location autocomplete with learning weights
"""
from datetime import datetime
from quart import Blueprint, request, jsonify

from city_guides.src.services.location import (
    city_mappings,
    region_mappings,
    levenshtein_distance
)
from city_guides.src.services.learning import (
    get_location_weight,
    detect_hemisphere_from_searches
)
from city_guides.src.utils.seasonal import get_seasonal_destinations

bp = Blueprint('suggestions', __name__)


@bp.route('/api/location-suggestions', methods=['POST'])
async def location_suggestions():
    """Provide location suggestions based on partial input with learning weights"""
    try:
        from city_guides.src.app import app
        
        payload = await request.get_json(silent=True) or {}
        query = (payload.get('query') or '').strip().lower()
        
        if len(query) < 2:
            return jsonify({'suggestions': []})
        
        suggestions = []
        
        # Get all locations with their weights
        all_locations = []
        
        # Trending destinations 2025 (higher priority)
        trending_destinations = {
            'london': 3.0, 'barcelona': 3.0, 'bangkok': 3.0, 'paris': 3.0,
            'rome': 3.0, 'tokyo': 3.0, 'new york': 3.0, 'amsterdam': 3.0,
            'dubai': 3.0, 'singapore': 3.0, 'venice': 2.5, 'prague': 2.5,
            'madrid': 2.5, 'berlin': 2.5, 'vienna': 2.5, 'zurich': 2.5,
            'copenhagen': 2.5, 'stockholm': 2.5, 'oslo': 2.5, 'helsinki': 2.5,
            'warsaw': 2.5, 'athens': 2.5, 'dublin': 2.5, 'edinburgh': 2.5,
            'lisbon': 2.5, 'budapest': 2.5, 'istanbul': 2.5, 'cairo': 2.5,
            'mumbai': 2.5
        }
        
        # Seasonal recommendations (current month)
        current_month = datetime.now().month
        
        user_hemisphere = detect_hemisphere_from_searches()
        current_seasonal = get_seasonal_destinations(current_month, user_hemisphere)
        
        # Add cities with weights (base weight + trending bonus + seasonal bonus)
        for city, data in city_mappings.items():
            base_weight = get_location_weight(city)
            trending_bonus = trending_destinations.get(city, 1.0)
            seasonal_bonus = current_seasonal.get(city, 1.0)
            weight = base_weight * trending_bonus * seasonal_bonus
            if query in city or levenshtein_distance(query, city) <= 2:
                all_locations.append({
                    'display_name': data['city'],
                    'detail': data['countryName'],
                    'type': 'city',
                    'weight': weight,
                    'exact_match': query == city
                })
        
        # Add regions with weights
        for region, data in region_mappings.items():
            weight = get_location_weight(region)
            if query in region or levenshtein_distance(query, region) <= 2:
                all_locations.append({
                    'display_name': data['city'],
                    'detail': f"{data['countryName']} - {region}",
                    'type': 'region',
                    'weight': weight,
                    'exact_match': query == region
                })
        
        # Sort by weight and relevance
        all_locations.sort(key=lambda x: (not x['exact_match'], -x['weight'], len(x['display_name'])))
        
        # Return top 5 suggestions
        suggestions = all_locations[:5]
        
        return jsonify({'suggestions': suggestions})
        
    except Exception:
        from city_guides.src.app import app
        app.logger.exception('Location suggestions failed')
        return jsonify({'error': 'suggestions_failed'}), 500


def register(app):
    """Register suggestions blueprint with app"""
    app.register_blueprint(bp)
