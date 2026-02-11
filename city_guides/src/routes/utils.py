"""
Utility routes: Weather, synthesis, and logging
"""
from quart import Blueprint, request, jsonify
from aiohttp import ClientTimeout

from city_guides.providers.geocoding import geocode_city
from city_guides.providers.utils import get_session
from city_guides.src.services.learning import increment_location_weight

bp = Blueprint('utils', __name__)


async def get_weather_async(lat, lon):
    """Fetch weather data from Open-Meteo API"""
    if lat is None or lon is None:
        return None
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            # include current weather and today's sunrise/sunset (small payload)
            "current_weather": True,
            "daily": ",".join(["sunrise", "sunset"]),
            "temperature_unit": "celsius",
            "windspeed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto",
        }
        # coerce boolean params to strings
        coerced = {k: (str(v).lower() if isinstance(v, bool) else v) for k, v in params.items()}
        async with get_session() as session:
            async with session.get(url, params=coerced, timeout=ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    print(f"[DEBUG app.py] get_weather_async HTTP error: {resp.status}")
                resp.raise_for_status()
                data = await resp.json()
                # return a compact payload containing current weather and today's daily fields
                return {
                    'current_weather': data.get('current_weather'),
                    'daily': data.get('daily'),
                    'timezone': data.get('timezone'),
                    'timezone_abbreviation': data.get('timezone_abbreviation'),
                    'utc_offset_seconds': data.get('utc_offset_seconds')
                }
    except Exception as e:
        print(f"[DEBUG app.py] get_weather_async Exception: {e}")
        return None


@bp.route("/api/weather", methods=["POST"])
async def weather():
    """Get weather data for a location"""
    payload = await request.get_json(silent=True) or {}
    city = (payload.get("city") or "").strip()
    lat = payload.get("lat")
    lon = payload.get("lon")
    if not (lat and lon):
        if not city:
            return jsonify({"error": "city or lat/lon required"}), 400
        result = await geocode_city(city)
        if not result:
            return jsonify({"error": "geocode_failed"}), 400
        lat = result['lat']
        lon = result['lon']
    weather_data = await get_weather_async(lat, lon)
    if weather_data is None:
        return jsonify({"error": "weather_fetch_failed"}), 500
    return jsonify({"lat": lat, "lon": lon, "city": city, "weather": weather_data})


@bp.route('/api/synthesize', methods=['POST'])
async def synthesize():
    """Synthesize venues from search results using AI enhancement"""
    try:
        from city_guides.src.app import app
        
        data = await request.get_json(silent=True) or {}
        search_result = data.get('search_result')
        
        if not search_result:
            return jsonify({'error': 'search_result required'}), 400
        
        # For now, return a simple synthesis based on available venues
        # In the future, this could use AI to enhance the venue data
        venues = search_result.get('venues', [])
        synthesized_venues = []
        
        for venue in venues[:10]:  # Limit to 10 venues
            synthesized_venue = {
                'id': venue.get('id'),
                'name': venue.get('name'),
                'address': venue.get('address'),
                'description': venue.get('description') or f'A popular {search_result.get("category", "spot")} in {search_result.get("city", "the city")}',
                'lat': venue.get('lat'),
                'lon': venue.get('lon'),
                'provider': venue.get('provider', 'osm'),
                'tags': venue.get('tags', {}),
                'enhanced_description': venue.get('description') or f'Great option for {search_result.get("category", "dining")} in the area'
            }
            synthesized_venues.append(synthesized_venue)
        
        return jsonify({
            'synthesized_venues': synthesized_venues,
            'total': len(synthesized_venues)
        })
        
    except Exception as e:
        from city_guides.src.app import app
        app.logger.exception('Synthesis failed')
        return jsonify({'error': 'synthesis_failed', 'details': str(e)}), 500


@bp.route("/api/categories", methods=["POST"])
async def api_city_categories():
    """Get dynamic categories for a city or neighborhood based on real venue data"""
    payload = await request.get_json(silent=True) or {}
    city = (payload.get("city") or "").strip()
    state = (payload.get("state") or "").strip()
    neighborhood = (payload.get("neighborhood") or "").strip()
    
    if not city:
        return jsonify({"error": "city required"}), 400
    
    try:
        # If neighborhood is specified, generate neighborhood-specific categories
        if neighborhood:
            from city_guides.src.simple_categories import get_neighborhood_specific_categories
            categories = await get_neighborhood_specific_categories(city, neighborhood, state)
            source = "neighborhood_dynamic"
        else:
            from city_guides.src.simple_categories import get_dynamic_categories
            categories = await get_dynamic_categories(city, state)
            source = "dynamic"
        
        # FALLBACK: If no categories found, use generic categories
        if not categories:
            from city_guides.src.simple_categories import get_generic_categories
            categories = get_generic_categories()
            source = "fallback"
            from city_guides.src.app import app
            app.logger.warning(f"No categories found for {city}{'/' + neighborhood if neighborhood else ''}, using fallback")
        
        return jsonify({
            "categories": categories,
            "source": source,
            "city": city,
            "neighborhood": neighborhood if neighborhood else None
        })
    except Exception as e:
        from city_guides.src.app import app
        app.logger.error(f"Failed to get categories for {city}{'/' + neighborhood if neighborhood else ''}: {e}")
        from city_guides.src.simple_categories import get_generic_categories
        categories = get_generic_categories()
        return jsonify({
            "categories": categories,
            "source": "error_fallback",
            "city": city,
            "neighborhood": neighborhood if neighborhood else None
        })


@bp.route('/api/log-suggestion-success', methods=['POST'])
async def log_suggestion_success():
    """Log successful suggestion usage for learning"""
    try:
        from city_guides.src.app import app
        
        payload = await request.get_json(silent=True) or {}
        suggestion = payload.get('suggestion', '').strip().lower()
        
        if suggestion:
            increment_location_weight(suggestion)
        
        return jsonify({'success': True})
        
    except Exception:
        from city_guides.src.app import app
        app.logger.exception('Failed to log suggestion success')
        return jsonify({'error': 'logging_failed'}), 500


@bp.route('/api/groq-enabled', methods=['GET'])
async def groq_enabled():
    """Return whether GROQ LLM features are enabled on this server."""
    import os
    enabled = bool(os.getenv('GROQ_API_KEY'))
    return jsonify({'groq_enabled': enabled})


def register(app):
    """Register utils blueprint with app"""
    app.register_blueprint(bp)
