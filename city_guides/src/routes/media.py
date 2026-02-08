"""
Media search routes for TravelLand API.

Routes:
    POST /api/unsplash-search - Secure proxy for Unsplash API
    POST /api/pixabay-search - Secure proxy for Pixabay API
"""

from quart import Blueprint, request, jsonify
from aiohttp import ClientTimeout
import logging
import os

logger = logging.getLogger(__name__)
bp = Blueprint('media', __name__, url_prefix='/api')

# Import get_session from providers
from city_guides.providers.utils import get_session


@bp.route('/unsplash-search', methods=['POST'])
async def unsplash_search():
    """Secure proxy for Unsplash API - hides API keys from frontend."""
    try:
        payload = await request.get_json(silent=True) or {}
        query = payload.get('query', '').strip()
        per_page = min(int(payload.get('per_page', 3)), 10)
        
        if not query:
            return jsonify({'photos': []})
        
        unsplash_key = os.getenv("UNSPLASH_KEY")
        if not unsplash_key:
            logger.warning("Unsplash key not configured")
            return jsonify({'photos': []})
        
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
                timeout=ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.error(f"Unsplash API error: {response.status}")
                    return jsonify({'photos': []})
                
                data = await response.json()
                
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
        logger.exception(f'Unsplash proxy failed: {e}')
        return jsonify({'error': 'unsplash_search_failed'}), 500


@bp.route('/pixabay-search', methods=['POST'])
async def pixabay_search():
    """Secure proxy for Pixabay API - hides API keys from frontend."""
    try:
        payload = await request.get_json(silent=True) or {}
        query = payload.get('query', '').strip()
        per_page = min(int(payload.get('per_page', 3)), 20)
        
        if not query:
            return jsonify({'photos': []})
        
        pixabay_key = os.getenv("PIXABAY_KEY")
        if not pixabay_key:
            logger.warning("Pixabay key not configured")
            return jsonify({'photos': []})
        
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
                timeout=ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.error(f"Pixabay API error: {response.status}")
                    return jsonify({'photos': []})
                
                data = await response.json()
                
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
        logger.exception(f'Pixabay proxy failed: {e}')
        return jsonify({'error': 'pixabay_search_failed'}), 500


def register(app):
    """Register media routes with the app."""
    app.register_blueprint(bp)
    logger.info("✅ Media routes registered")
