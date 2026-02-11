"""
GeoProvider implementation using Nominatim.

This provider handles geocoding and reverse geocoding using OpenStreetMap's
Nominatim service with proper fallbacks and caching.
"""

from typing import Optional, Dict, Any, Tuple, List
import aiohttp
import json
from pathlib import Path
import hashlib

from city_guides.providers.base import GeoProvider, ProviderMetadata, ProviderError
from city_guides.config import get_config
from city_guides.services.session_manager import get_session


class NominatimGeoProvider(GeoProvider):
    """GeoProvider implementation using Nominatim."""
    
    NOMINATIM_URL = "https://nominatim.openstreetmap.org"
    
    def __init__(self):
        """Initialize the Nominatim geo provider."""
        super().__init__()
        self.config = get_config()
        self.cache_dir = Path(__file__).parent / ".cache" / "geocoding"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata."""
        return ProviderMetadata(
            name="nominatim",
            version="1.0.0",
            description="OpenStreetMap Nominatim geocoding service",
            capabilities=["geocoding", "reverse_geocoding", "bounding_box"],
            rate_limit=60  # 1 request per second
        )
    
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for query."""
        return hashlib.md5(query.lower().encode()).hexdigest()
    
    def _read_cache(self, cache_key: str) -> Optional[Dict]:
        """Read from cache if available."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def _write_cache(self, cache_key: str, data: Dict) -> None:
        """Write to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            self.logger.warning(f"Failed to write cache: {e}")
    
    async def geocode(self, location: str) -> Optional[Dict[str, Any]]:
        """Convert location name to coordinates.
        
        Args:
            location: Location name (e.g., "New York, USA")
            
        Returns:
            Dictionary with lat, lon, and display_name, or None if not found
        """
        if not location or not location.strip():
            return None
        
        # Check cache
        cache_key = self._get_cache_key(f"geocode:{location}")
        cached = self._read_cache(cache_key)
        if cached:
            return cached
        
        try:
            session = await get_session()
            timeout = self.config.get_timeout('geo')
            
            params = {
                "q": location,
                "format": "json",
                "limit": 1,
                "addressdetails": 1
            }
            
            headers = {
                "User-Agent": "TravelLand/1.0 (https://github.com/markcodeman/travelland)"
            }
            
            async with session.get(
                f"{self.NOMINATIM_URL}/search",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    raise ProviderError(
                        f"Nominatim returned status {response.status}",
                        provider_name="nominatim"
                    )
                
                data = await response.json()
                
                if not data or len(data) == 0:
                    return None
                
                result = data[0]
                
                # Extract bounding box if available
                bbox = result.get("boundingbox")
                if bbox and len(bbox) == 4:
                    # Convert to (west, south, east, north)
                    bbox = (
                        float(bbox[2]),  # west
                        float(bbox[0]),  # south
                        float(bbox[3]),  # east
                        float(bbox[1])   # north
                    )
                
                geocoded = {
                    "lat": float(result.get("lat")),
                    "lon": float(result.get("lon")),
                    "display_name": result.get("display_name"),
                    "boundingbox": bbox,
                    "osm_type": result.get("osm_type"),
                    "osm_id": result.get("osm_id"),
                    "place_id": result.get("place_id")
                }
                
                # Cache result
                self._write_cache(cache_key, geocoded)
                
                return geocoded
                
        except aiohttp.ClientError as e:
            raise ProviderError(
                f"Network error during geocoding: {e}",
                provider_name="nominatim"
            )
        except Exception as e:
            raise ProviderError(
                f"Geocoding failed: {e}",
                provider_name="nominatim"
            )
    
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """Convert coordinates to location name.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Location name or None if not found
        """
        if lat is None or lon is None:
            return None
        
        # Check cache
        cache_key = self._get_cache_key(f"reverse:{lat},{lon}")
        cached = self._read_cache(cache_key)
        if cached:
            return cached.get("display_name")
        
        try:
            session = await get_session()
            timeout = self.config.get_timeout('geo')
            
            params = {
                "lat": lat,
                "lon": lon,
                "format": "json"
            }
            
            headers = {
                "User-Agent": "TravelLand/1.0 (https://github.com/markcodeman/travelland)"
            }
            
            async with session.get(
                f"{self.NOMINATIM_URL}/reverse",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                
                if not data or "display_name" not in data:
                    return None
                
                display_name = data["display_name"]
                
                # Cache result
                self._write_cache(cache_key, {"display_name": display_name})
                
                return display_name
                
        except Exception as e:
            self.logger.warning(f"Reverse geocoding failed: {e}")
            return None
    
    async def get_bounding_box(self, location: str) -> Optional[Tuple[float, float, float, float]]:
        """Get bounding box for a location.
        
        Args:
            location: Location name
            
        Returns:
            Tuple of (west, south, east, north) or None
        """
        result = await self.geocode(location)
        if result and result.get("boundingbox"):
            return result["boundingbox"]
        return None
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for locations."""
        result = await self.geocode(query)
        return [result] if result else []


class GeoapifyGeoProvider(GeoProvider):
    """Fallback GeoProvider using Geoapify."""
    
    GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Geoapify provider."""
        super().__init__()
        self.config = get_config()
        self.api_key = api_key or self.config._get_optional("GEOAPIFY_API_KEY")
    
    async def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata."""
        return ProviderMetadata(
            name="geoapify",
            version="1.0.0",
            description="Geoapify geocoding service (fallback)",
            capabilities=["geocoding", "reverse_geocoding"],
            rate_limit=3000  # requests per day for free tier
        )
    
    async def geocode(self, location: str) -> Optional[Dict[str, Any]]:
        """Geocode using Geoapify."""
        if not self.api_key:
            return None
        
        try:
            session = await get_session()
            timeout = self.config.get_timeout('geo')
            
            params = {
                "text": location,
                "format": "json",
                "apiKey": self.api_key
            }
            
            async with session.get(
                f"{self.GEOAPIFY_URL}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                results = data.get("results", [])
                
                if not results:
                    return None
                
                result = results[0]
                
                return {
                    "lat": result.get("lat"),
                    "lon": result.get("lon"),
                    "display_name": result.get("formatted"),
                    "boundingbox": result.get("bbox")
                }
                
        except Exception as e:
            self.logger.warning(f"Geoapify geocoding failed: {e}")
            return None
    
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """Reverse geocode using Geoapify."""
        if not self.api_key:
            return None
        
        try:
            session = await get_session()
            timeout = self.config.get_timeout('geo')
            
            params = {
                "lat": lat,
                "lon": lon,
                "format": "json",
                "apiKey": self.api_key
            }
            
            async with session.get(
                f"{self.GEOAPIFY_URL}/reverse",
                params=params,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                features = data.get("features", [])
                
                if not features:
                    return None
                
                return features[0].get("properties", {}).get("formatted")
                
        except Exception as e:
            self.logger.warning(f"Geoapify reverse geocoding failed: {e}")
            return None
    
    async def get_bounding_box(self, location: str) -> Optional[Tuple[float, float, float, float]]:
        """Get bounding box."""
        result = await self.geocode(location)
        if result and result.get("boundingbox"):
            bbox = result["boundingbox"]
            # Convert to (west, south, east, north) format
            if isinstance(bbox, dict):
                return (
                    bbox.get("lon1"),  # west
                    bbox.get("lat1"),  # south
                    bbox.get("lon2"),  # east
                    bbox.get("lat2")   # north
                )
        return None
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for locations."""
        result = await self.geocode(query)
        return [result] if result else []
