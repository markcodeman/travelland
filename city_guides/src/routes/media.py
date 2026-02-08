"""
Media routes: External image API integrations (Unsplash, Pixabay)
"""
import os
import aiohttp
from quart import Blueprint, request, jsonify

from city_guides.providers.utils import get_session

bp = Blueprint('media', __name__)


@bp.route('/api/unsplash-search', methods=['POST'])
async def unsplash_search():
    """Secure proxy for Unsplash API - hides API keys from frontend"""
    try:
        from city_guides.src.app import app
        
        payload = await request.get_json(silent=True) or {}
        query = payload.get('query', '').strip()
        per_page = min(int(payload.get('per_page', 3)), 10)
        
        if not query:
            return jsonify({'photos': []})
        
        # Get Unsplash key from environment (never exposed to frontend)
        unsplash_key = os.getenv("UNSPLASH_KEY")
        if not unsplash_key:
            app.logger.warning("Unsplash key not configured")
            return jsonify({'photos': []})
        
        # Make secure request to Unsplash
        params = {
            'query': query,
            'per_page': per_page,
            'orientation': 'landscape',
            'content_filter': 'high',
            'order_by': 'relevant'
        }
        
        headers = {
            'Authorization': f'Client-ID {unsplash_key}',
            'Accept-Encoding': 'gzip, deflate',
            'User-Agent': 'TravelLand/1.0'
        }
        
        async with get_session() as session:
            async with session.get(
                "https://api.unsplash.com/search/photos",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    app.logger.error(f"Unsplash API error: {response.status}")
                    return jsonify({'photos': []})
                
                data = await response.json()
                
                # Transform response to only expose necessary data
                photos = []
                for photo in data.get('results', []):
                    photos.append({
                        'id': photo['id'],
                        'url': photo['urls']['regular'],
                        'thumb_url': photo['urls']['thumb'],
                        'description': photo.get('description', ''),
                        'alt_description': photo.get('alt_description', ''),
                        'user': {
                            'name': photo['user']['name'],
                            'username': photo['user']['username'],
                            'profile_url': photo['user']['links']['html']
                        },
                        'links': {
                            'unsplash': photo['links']['html']
                        }
                    })
                
                return jsonify({'photos': photos})
        
    except Exception as e:
        from city_guides.src.app import app
        app.logger.exception(f'Unsplash proxy failed: {e}')
        app.logger.error('Query was: %s', locals().get('query'))
        app.logger.error('Unsplash key configured: %s', bool(os.getenv('UNSPLASH_KEY')))
        return jsonify({'error': 'unsplash_search_failed'}), 500


@bp.route('/api/pixabay-search', methods=['POST'])
async def pixabay_search():
    """Secure proxy for Pixabay API - hides API keys from frontend"""
    try:
        from city_guides.src.app import app
        
        payload = await request.get_json(silent=True) or {}
        query = payload.get('query', '').strip()
        per_page = min(int(payload.get('per_page', 3)), 20)
        
        if not query:
            return jsonify({'photos': []})
        
        # Get Pixabay key from environment (never exposed to frontend)
        pixabay_key = os.getenv("PIXABAY_KEY")
        if not pixabay_key:
            app.logger.warning("Pixabay key not configured")
            return jsonify({'photos': []})
        
        # Make secure request to Pixabay
        params = {
            'key': pixabay_key,
            'q': query,
            'per_page': per_page,
            'safesearch': 'true',
            'image_type': 'photo',
            'orientation': 'horizontal'
        }
        
        async with get_session() as session:
            async with session.get(
                "https://pixabay.com/api/",
                params=params,
                headers={'Accept-Encoding': 'gzip, deflate', 'User-Agent': 'TravelLand/1.0'},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    app.logger.error(f"Pixabay API error: {response.status}")
                    return jsonify({'photos': []})
                
                data = await response.json()
                
                # Transform response to only expose necessary data
                photos = []
                for hit in data.get('hits', []):
                    photos.append({
                        'id': hit['id'],
                        'url': hit['webformatURL'],
                        'thumb_url': hit['previewURL'],
                        'description': hit.get('tags', ''),
                        'user': hit.get('user', 'Pixabay User'),
                        'links': {
                            'pixabay': hit['pageURL']
                        }
                    })
                
                return jsonify({'photos': photos})
        
    except Exception as e:
        from city_guides.src.app import app
        app.logger.exception(f'Pixabay proxy failed: {e}')
        return jsonify({'error': 'pixabay_search_failed'}), 500


def register(app):
    """Register media blueprint with app"""
    app.register_blueprint(bp)
