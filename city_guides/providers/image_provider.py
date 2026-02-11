"""
ImageProvider implementation using Unsplash API.

This provider fetches images for locations from Unsplash
with proper attribution and fallbacks.
"""

from typing import Optional, Dict, Any, List
import aiohttp
import json
from pathlib import Path
import hashlib

from city_guides.providers.base import ImageProvider, ProviderMetadata, ProviderError
from city_guides.config import get_config
from city_guides.services.session_manager import get_session


class UnsplashImageProvider(ImageProvider):
    """ImageProvider implementation using Unsplash API."""
    
    UNSPLASH_API_URL = "https://api.unsplash.com"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Unsplash image provider.
        
        Args:
            api_key: Unsplash API access key (optional, will use config if not provided)
        """
        super().__init__()
        self.config = get_config()
        self.api_key = api_key or self.config.unsplash_key
        self.cache_dir = Path(__file__).parent / ".cache" / "images"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata."""
        return ProviderMetadata(
            name="unsplash",
            version="1.0.0",
            description="Unsplash image API",
            capabilities=["images", "hero_image", "attribution"],
            rate_limit=50  # requests per hour for demo key
        )
    
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for query."""
        return hashlib.md5(query.lower().encode()).hexdigest()
    
    def _read_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """Read from cache if available."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def _write_cache(self, cache_key: str, data: List[Dict]) -> None:
        """Write to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            self.logger.warning(f"Failed to write cache: {e}")
    
    def _format_image(self, photo: Dict[str, Any]) -> Dict[str, Any]:
        """Format Unsplash photo data to standard format.
        
        Args:
            photo: Unsplash photo data
            
        Returns:
            Formatted image dictionary
        """
        urls = photo.get("urls", {})
        user = photo.get("user", {})
        
        return {
            "url": urls.get("regular") or urls.get("small"),
            "thumb_url": urls.get("thumb"),
            "full_url": urls.get("full"),
            "attribution": f"Photo by {user.get('name', 'Unknown')} on Unsplash",
            "photographer": user.get("name"),
            "photographer_url": user.get("links", {}).get("html"),
            "source": "unsplash",
            "source_id": photo.get("id"),
            "description": photo.get("description") or photo.get("alt_description", ""),
            "width": photo.get("width"),
            "height": photo.get("height")
        }
    
    async def get_images(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get images for a query.
        
        Args:
            query: Image search query
            limit: Maximum number of images to return
            
        Returns:
            List of image dictionaries
        """
        if not self.api_key:
            self.logger.warning("Unsplash API key not configured")
            return []
        
        if not query or not query.strip():
            return []
        
        # Check cache
        cache_key = self._get_cache_key(f"images:{query}:{limit}")
        cached = self._read_cache(cache_key)
        if cached:
            return cached[:limit]
        
        try:
            session = await get_session()
            timeout = self.config.get_timeout('image')
            
            params = {
                "query": query,
                "per_page": min(limit, 30),  # Unsplash max is 30
                "orientation": "landscape"  # Better for hero images
            }
            
            headers = {
                "Authorization": f"Client-ID {self.api_key}"
            }
            
            async with session.get(
                f"{self.UNSPLASH_API_URL}/search/photos",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 401:
                    raise ProviderError(
                        "Invalid Unsplash API key",
                        provider_name="unsplash"
                    )
                
                if response.status != 200:
                    raise ProviderError(
                        f"Unsplash returned status {response.status}",
                        provider_name="unsplash"
                    )
                
                data = await response.json()
                results = data.get("results", [])
                
                images = [self._format_image(photo) for photo in results]
                
                # Cache results
                if images:
                    self._write_cache(cache_key, images)
                
                return images[:limit]
                
        except ProviderError:
            raise
        except Exception as e:
            self.logger.warning(f"Failed to get images for '{query}': {e}")
            return []
    
    async def get_hero_image(self, location: str, intent: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a hero image for a location.
        
        Args:
            location: Location name
            intent: Optional context/intent for the image
            
        Returns:
            Image dictionary or None
        """
        # Build search query
        search_terms = [location]
        if intent:
            search_terms.append(intent)
        
        query = " ".join(search_terms)
        
        images = await self.get_images(query, limit=1)
        return images[0] if images else None
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for images."""
        limit = kwargs.get("limit", 5)
        return await self.get_images(query, limit)


class PixabayImageProvider(ImageProvider):
    """Fallback ImageProvider using Pixabay API."""
    
    PIXABAY_API_URL = "https://pixabay.com/api"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Pixabay image provider."""
        super().__init__()
        self.config = get_config()
        self.api_key = api_key or self.config.pixabay_key
    
    async def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata."""
        return ProviderMetadata(
            name="pixabay",
            version="1.0.0",
            description="Pixabay image API (fallback)",
            capabilities=["images", "hero_image"],
            rate_limit=100  # requests per minute
        )
    
    def _format_image(self, photo: Dict[str, Any]) -> Dict[str, Any]:
        """Format Pixabay photo to standard format."""
        return {
            "url": photo.get("webformatURL"),
            "thumb_url": photo.get("previewURL"),
            "full_url": photo.get("largeImageURL"),
            "attribution": f"Photo by {photo.get('user', 'Unknown')} on Pixabay",
            "photographer": photo.get("user"),
            "source": "pixabay",
            "source_id": str(photo.get("id")),
            "description": photo.get("tags", ""),
            "width": photo.get("webformatWidth"),
            "height": photo.get("webformatHeight")
        }
    
    async def get_images(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get images from Pixabay."""
        if not self.api_key:
            return []
        
        if not query or not query.strip():
            return []
        
        try:
            session = await get_session()
            timeout = self.config.get_timeout('image')
            
            params = {
                "key": self.api_key,
                "q": query,
                "per_page": limit,
                "orientation": "horizontal",
                "safesearch": "true"
            }
            
            async with session.get(
                self.PIXABAY_API_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                hits = data.get("hits", [])
                
                return [self._format_image(photo) for photo in hits]
                
        except Exception as e:
            self.logger.warning(f"Pixabay image search failed: {e}")
            return []
    
    async def get_hero_image(self, location: str, intent: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get hero image."""
        search_terms = [location]
        if intent:
            search_terms.append(intent)
        
        query = " ".join(search_terms)
        images = await self.get_images(query, limit=1)
        return images[0] if images else None
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for images."""
        limit = kwargs.get("limit", 5)
        return await self.get_images(query, limit)
