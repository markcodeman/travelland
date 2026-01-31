"""
Pixabay API Service for TravelLand
Compliant with Pixabay API Terms of Use:
- 24-hour caching for all responses
- Proper attribution with links
- Rate limiting (100 requests/hour)
- Human-triggered searches only
"""

import aiohttp
import asyncio
import hashlib
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class PixabayService:
    def __init__(self):
        # Load environment variables from .env file if they exist
        env_file = Path("/home/markm/TravelLand/.env")
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()
        
        self.api_key = os.getenv('PIXABAY_KEY')
        self.base_url = "https://pixabay.com/api/"
        self.cache = {}  # In-memory 24-hour cache
        self.rate_limit_tracker = []
        self.session = None
        
        if not self.api_key:
            logger.warning("PIXABAY_KEY not found in environment variables")
        else:
            logger.info("Pixabay API key loaded successfully")
    
    async def get_session(self):
        """Create or reuse aiohttp session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def _generate_cache_key(self, query: str, page: int = 1, per_page: int = 20) -> str:
        """Generate cache key for search query"""
        cache_data = f"{query}_{page}_{per_page}"
        return hashlib.md5(cache_data.encode()).hexdigest()
    
    def _is_rate_limited(self) -> bool:
        """Check if we've hit the 100 requests/hour limit"""
        current_time = time.time()
        hour_ago = current_time - 3600
        
        # Remove requests older than 1 hour
        self.rate_limit_tracker = [req_time for req_time in self.rate_limit_tracker if req_time > hour_ago]
        
        return len(self.rate_limit_tracker) >= 100
    
    def _track_request(self):
        """Track API request for rate limiting"""
        self.rate_limit_tracker.append(time.time())
    
    def _is_cached(self, cache_key: str) -> Optional[Dict]:
        """Check if response is cached and not expired (24 hours)"""
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if time.time() - cached_data['timestamp'] < 86400:  # 24 hours
                return cached_data['data']
            else:
                # Remove expired cache
                del self.cache[cache_key]
        return None
    
    def _cache_response(self, cache_key: str, data: Dict):
        """Cache API response with timestamp"""
        self.cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    async def search_destination_images(self, query: str, page: int = 1, per_page: int = 20) -> Dict:
        """
        Search for destination images with Pixabay API
        Implements 24-hour caching and rate limiting
        """
        if not self.api_key:
            return {"error": "Pixabay API key not configured"}
        
        # Check rate limit
        if self._is_rate_limited():
            return {"error": "API rate limit exceeded. Please try again later."}
        
        # Check cache first
        cache_key = self._generate_cache_key(query, page, per_page)
        cached_result = self._is_cached(cache_key)
        if cached_result:
            logger.info(f"Cache hit for Pixabay search: {query}")
            return cached_result
        
        # Track request for rate limiting
        self._track_request()
        
        # Prepare API parameters
        params = {
            'key': self.api_key,
            'q': query,
            'lang': 'en',
            'image_type': 'photo',
            'category': 'places',
            'safesearch': 'true',
            'page': page,
            'per_page': min(per_page, 200)  # Pixabay max is 200
        }
        
        try:
            session = await self.get_session()
            async with session.get(self.base_url, params=params) as response:
                if response.status == 429:
                    return {"error": "API rate limit exceeded. Please try again later."}
                
                if response.status != 200:
                    logger.error(f"Pixabay API error: {response.status}")
                    return {"error": f"API request failed with status {response.status}"}
                
                data = await response.json()
                
                # Add attribution information
                processed_data = self._add_attribution_info(data)
                
                # Cache the response
                self._cache_response(cache_key, processed_data)
                
                logger.info(f"Pixabay search successful: {query}, found {len(processed_data.get('hits', []))} images")
                return processed_data
                
        except Exception as e:
            logger.error(f"Error searching Pixabay: {str(e)}")
            return {"error": f"Failed to search images: {str(e)}"}
    
    def _add_attribution_info(self, data: Dict) -> Dict:
        """Add required attribution information to response"""
        if 'hits' in data:
            for hit in data['hits']:
                # Ensure all required attribution fields are present
                hit['attribution'] = {
                    'photographer': hit.get('user', 'Unknown'),
                    'photographer_url': hit.get('userImageURL', ''),
                    'pixabay_url': hit.get('pageURL', ''),
                    'credit_text': f"Photo by {hit.get('user', 'Unknown')} on Pixabay"
                }
        
        # Add Pixabay attribution to the response
        data['pixabay_attribution'] = {
            'api_url': 'https://pixabay.com/api/',
            'terms_url': 'https://pixabay.com/api/docs/',
            'credit_text': 'Images powered by Pixabay',
            'required_attribution': 'All images require attribution to Pixabay and the photographer'
        }
        
        return data
    
    async def get_destination_hero_image(self, city: str) -> Optional[Dict]:
        """
        Get a single hero image for a destination
        Returns the highest quality image available
        """
        # Search with city name first
        result = await self.search_destination_images(city, per_page=3)
        
        if 'hits' in result and result['hits']:
            # Select the best image (prioritize landscape orientation and high resolution)
            best_image = None
            best_score = 0
            
            for hit in result['hits']:
                score = 0
                
                # Prefer landscape orientation for hero images
                if hit.get('imageWidth', 0) > hit.get('imageHeight', 0):
                    score += 2
                
                # Prefer higher resolution
                score += min(hit.get('imageWidth', 0) / 1000, 5)
                score += min(hit.get('imageHeight', 0) / 1000, 5)
                
                # Prefer more likes/views
                score += min(hit.get('likes', 0) / 100, 2)
                score += min(hit.get('views', 0) / 10000, 2)
                
                if score > best_score:
                    best_score = score
                    best_image = hit
            
            return best_image
        
        # Try alternative search terms
        alternative_terms = [f"{city} skyline", f"{city} landmarks", f"{city} city"]
        
        for term in alternative_terms:
            result = await self.search_destination_images(term, per_page=3)
            if 'hits' in result and result['hits']:
                return result['hits'][0]  # Return first result from alternative search
        
        return None
    
    async def get_thumbnail_images(self, city: str, count: int = 5) -> List[Dict]:
        """
        Get thumbnail images for autocomplete suggestions
        Returns smaller previewURL images
        """
        result = await self.search_destination_images(city, per_page=count)
        
        thumbnails = []
        if 'hits' in result:
            for hit in result['hits'][:count]:
                thumbnails.append({
                    'previewURL': hit.get('previewURL', ''),
                    'webformatURL': hit.get('webformatURL', ''),
                    'id': hit.get('id'),
                    'attribution': hit.get('attribution', {})
                })
        
        return thumbnails
    
    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

# Global instance
pixabay_service = PixabayService()
