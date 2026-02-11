"""
Provider base interfaces and abstract classes.

This module defines clean abstractions for all providers to ensure:
- Consistent interfaces across providers
- Proper dependency injection
- Health check capabilities
- Standardized error handling
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import time
import logging


class ProviderStatus(Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a provider health check."""
    status: ProviderStatus
    latency_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None
    
    @property
    def is_healthy(self) -> bool:
        """Check if provider is healthy."""
        return self.status == ProviderStatus.HEALTHY


@dataclass
class ProviderMetadata:
    """Metadata about a provider."""
    name: str
    version: str
    description: str
    capabilities: List[str]
    rate_limit: Optional[int] = None  # requests per minute
    

class Provider(ABC):
    """Base provider interface.
    
    All providers must implement this interface to ensure consistent
    behavior and proper integration with the system.
    """
    
    def __init__(self):
        """Initialize the provider."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self._metadata: Optional[ProviderMetadata] = None
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for content based on query.
        
        Args:
            query: Search query string
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
            
        Raises:
            ProviderError: If search fails
        """
        pass
    
    @abstractmethod
    async def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata.
        
        Returns:
            Provider metadata including name, version, capabilities
        """
        pass
    
    async def health_check(self) -> HealthCheckResult:
        """Check provider health.
        
        Default implementation attempts a simple search.
        Providers can override for custom health checks.
        
        Returns:
            Health check result
        """
        start_time = time.time()
        try:
            # Try a simple search to verify connectivity
            await self.search("test", limit=1)
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                status=ProviderStatus.HEALTHY,
                latency_ms=latency_ms,
                message=f"Provider {self.__class__.__name__} is healthy",
                details={"latency_ms": latency_ms}
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                status=ProviderStatus.UNHEALTHY,
                latency_ms=latency_ms,
                message=f"Provider health check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def is_available(self) -> bool:
        """Check if provider is available.
        
        Returns:
            True if provider is available and healthy
        """
        result = await self.health_check()
        return result.is_healthy


class GeoProvider(Provider):
    """Geocoding provider interface.
    
    Providers that handle geographic data and location services.
    """
    
    @abstractmethod
    async def geocode(self, location: str) -> Optional[Dict[str, Any]]:
        """Convert location name to coordinates.
        
        Args:
            location: Location name (e.g., "New York, USA")
            
        Returns:
            Dictionary with lat, lon, and display_name, or None if not found
            
        Example:
            {
                "lat": 40.7128,
                "lon": -74.0060,
                "display_name": "New York, USA",
                "boundingbox": [south, north, west, east]
            }
        """
        pass
    
    @abstractmethod
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """Convert coordinates to location name.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Location name or None if not found
        """
        pass
    
    @abstractmethod
    async def get_bounding_box(self, location: str) -> Optional[Tuple[float, float, float, float]]:
        """Get bounding box for a location.
        
        Args:
            location: Location name
            
        Returns:
            Tuple of (west, south, east, north) or None
        """
        pass
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Default search implementation for geo providers.
        
        Geo providers search by geocoding the query.
        """
        result = await self.geocode(query)
        return [result] if result else []


class ContentProvider(Provider):
    """Content provider interface.
    
    Providers that fetch textual content about locations.
    """
    
    @abstractmethod
    async def get_content(self, location: str, topic: str = "general") -> Optional[str]:
        """Get content about a location.
        
        Args:
            location: Location name
            topic: Topic to get content about (e.g., "history", "attractions")
            
        Returns:
            Content string or None if not found
        """
        pass
    
    @abstractmethod
    async def get_summary(self, location: str, max_length: int = 500) -> Optional[str]:
        """Get a brief summary about a location.
        
        Args:
            location: Location name
            max_length: Maximum summary length
            
        Returns:
            Summary string or None if not found
        """
        pass
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Default search implementation for content providers.
        
        Content providers search by getting content.
        """
        topic = kwargs.get("topic", "general")
        content = await self.get_content(query, topic)
        if content:
            return [{"content": content, "source": self.__class__.__name__}]
        return []


class ImageProvider(Provider):
    """Image provider interface.
    
    Providers that fetch images for locations.
    """
    
    @abstractmethod
    async def get_images(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get images for a query.
        
        Args:
            query: Image search query
            limit: Maximum number of images to return
            
        Returns:
            List of image dictionaries with url, attribution, etc.
            
        Example:
            [
                {
                    "url": "https://example.com/image.jpg",
                    "attribution": "Photo by John Doe",
                    "source": "unsplash"
                }
            ]
        """
        pass
    
    @abstractmethod
    async def get_hero_image(self, location: str, intent: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a hero image for a location.
        
        Args:
            location: Location name
            intent: Optional context/intent for the image
            
        Returns:
            Image dictionary or None
        """
        pass
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Default search implementation for image providers."""
        limit = kwargs.get("limit", 5)
        return await self.get_images(query, limit)


class SearchProvider(Provider):
    """Search provider interface.
    
    Providers that perform general web searches.
    """
    
    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Perform a search.
        
        Args:
            query: Search query
            limit: Maximum results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results with title, url, snippet, etc.
        """
        pass
    
    @abstractmethod
    async def search_with_fallback(
        self,
        query: str,
        limit: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search with fallback providers.
        
        If primary search fails, try fallback providers.
        
        Args:
            query: Search query
            limit: Maximum results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        pass


class ProviderError(Exception):
    """Base exception for provider errors."""
    
    def __init__(self, message: str, provider_name: Optional[str] = None, details: Optional[Dict] = None):
        """Initialize provider error.
        
        Args:
            message: Error message
            provider_name: Name of the provider that failed
            details: Additional error details
        """
        super().__init__(message)
        self.provider_name = provider_name
        self.details = details or {}


class ProviderNotAvailableError(ProviderError):
    """Raised when a provider is not available."""
    pass


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limit is exceeded."""
    pass


class ProviderTimeoutError(ProviderError):
    """Raised when provider request times out."""
    pass
