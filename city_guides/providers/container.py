"""
Provider container for dependency injection and provider management.

This module provides a centralized registry for all providers, enabling:
- Dependency injection
- Provider lifecycle management
- Health monitoring
- Fallback chain management
"""

from typing import Dict, List, Optional, Type, Any
import logging
import asyncio

from city_guides.providers.base import (
    Provider, 
    GeoProvider, 
    ContentProvider, 
    ImageProvider,
    SearchProvider,
    ProviderStatus,
    HealthCheckResult
)


class ProviderContainer:
    """Container for managing provider instances and dependencies.
    
    This implements a service locator pattern with dependency injection
    capabilities for the provider architecture.
    """
    
    def __init__(self):
        """Initialize the provider container."""
        self.logger = logging.getLogger(__name__)
        self._providers: Dict[str, Provider] = {}
        self._provider_classes: Dict[str, Type[Provider]] = {}
        self._fallback_chains: Dict[str, List[str]] = {}
        self._health_status: Dict[str, HealthCheckResult] = {}
    
    def register(
        self, 
        name: str, 
        provider_class: Type[Provider],
        instance: Optional[Provider] = None,
        fallback_to: Optional[List[str]] = None
    ) -> None:
        """Register a provider with the container.
        
        Args:
            name: Provider name/identifier
            provider_class: Provider class type
            instance: Optional pre-created instance
            fallback_to: List of provider names to fallback to
        """
        self._provider_classes[name] = provider_class
        
        if instance:
            self._providers[name] = instance
            
        if fallback_to:
            self._fallback_chains[name] = fallback_to
            
        self.logger.info(f"Registered provider: {name}")
    
    def get(self, name: str) -> Optional[Provider]:
        """Get a provider by name.
        
        Args:
            name: Provider name
            
        Returns:
            Provider instance or None if not found
        """
        # Return existing instance if available
        if name in self._providers:
            return self._providers[name]
        
        # Create instance if class is registered
        if name in self._provider_classes:
            provider_class = self._provider_classes[name]
            instance = provider_class()
            self._providers[name] = instance
            return instance
        
        return None
    
    def get_geo_provider(self, name: Optional[str] = None) -> Optional[GeoProvider]:
        """Get a geocoding provider.
        
        Args:
            name: Specific provider name, or None for default
            
        Returns:
            GeoProvider instance or None
        """
        if name:
            provider = self.get(name)
            return provider if isinstance(provider, GeoProvider) else None
        
        # Return first available geo provider
        for provider in self._providers.values():
            if isinstance(provider, GeoProvider):
                return provider
        return None
    
    def get_content_provider(self, name: Optional[str] = None) -> Optional[ContentProvider]:
        """Get a content provider.
        
        Args:
            name: Specific provider name, or None for default
            
        Returns:
            ContentProvider instance or None
        """
        if name:
            provider = self.get(name)
            return provider if isinstance(provider, ContentProvider) else None
        
        # Return first available content provider
        for provider in self._providers.values():
            if isinstance(provider, ContentProvider):
                return provider
        return None
    
    def get_image_provider(self, name: Optional[str] = None) -> Optional[ImageProvider]:
        """Get an image provider.
        
        Args:
            name: Specific provider name, or None for default
            
        Returns:
            ImageProvider instance or None
        """
        if name:
            provider = self.get(name)
            return provider if isinstance(provider, ImageProvider) else None
        
        # Return first available image provider
        for provider in self._providers.values():
            if isinstance(provider, ImageProvider):
                return provider
        return None
    
    def get_search_provider(self, name: Optional[str] = None) -> Optional[SearchProvider]:
        """Get a search provider.
        
        Args:
            name: Specific provider name, or None for default
            
        Returns:
            SearchProvider instance or None
        """
        if name:
            provider = self.get(name)
            return provider if isinstance(provider, SearchProvider) else None
        
        # Return first available search provider
        for provider in self._providers.values():
            if isinstance(provider, SearchProvider):
                return provider
        return None
    
    async def health_check_all(self) -> Dict[str, HealthCheckResult]:
        """Run health checks on all registered providers.
        
        Returns:
            Dictionary mapping provider names to health check results
        """
        results = {}
        
        for name, provider in self._providers.items():
            try:
                result = await provider.health_check()
                results[name] = result
                self._health_status[name] = result
            except Exception as e:
                self.logger.error(f"Health check failed for {name}: {e}")
                results[name] = HealthCheckResult(
                    status=ProviderStatus.UNHEALTHY,
                    latency_ms=0,
                    message=f"Health check error: {str(e)}"
                )
        
        return results
    
    def get_healthy_providers(self) -> List[str]:
        """Get list of healthy provider names.
        
        Returns:
            List of provider names that are healthy
        """
        healthy = []
        for name, status in self._health_status.items():
            if status.is_healthy:
                healthy.append(name)
        return healthy
    
    def get_fallback_chain(self, name: str) -> List[str]:
        """Get fallback chain for a provider.
        
        Args:
            name: Provider name
            
        Returns:
            List of fallback provider names
        """
        return self._fallback_chains.get(name, [])
    
    async def execute_with_fallback(
        self,
        provider_name: str,
        method_name: str,
        *args,
        **kwargs
    ) -> Any:
        """Execute a provider method with fallback support.
        
        Args:
            provider_name: Primary provider name
            method_name: Method to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Method result
            
        Raises:
            Exception: If all providers fail
        """
        providers_to_try = [provider_name] + self.get_fallback_chain(provider_name)
        
        last_error = None
        for name in providers_to_try:
            provider = self.get(name)
            if not provider:
                continue
            
            try:
                method = getattr(provider, method_name)
                return await method(*args, **kwargs)
            except Exception as e:
                self.logger.warning(f"Provider {name} failed: {e}")
                last_error = e
                continue
        
        if last_error:
            raise last_error
        raise Exception(f"No available providers for {provider_name}.{method_name}")
    
    def list_providers(self) -> List[str]:
        """List all registered provider names.
        
        Returns:
            List of provider names
        """
        return list(self._provider_classes.keys())
    
    def list_provider_types(self) -> Dict[str, List[str]]:
        """List providers grouped by type.
        
        Returns:
            Dictionary mapping type names to provider names
        """
        types = {
            "geo": [],
            "content": [],
            "image": [],
            "search": [],
            "other": []
        }
        
        for name, provider in self._providers.items():
            if isinstance(provider, GeoProvider):
                types["geo"].append(name)
            elif isinstance(provider, ContentProvider):
                types["content"].append(name)
            elif isinstance(provider, ImageProvider):
                types["image"].append(name)
            elif isinstance(provider, SearchProvider):
                types["search"].append(name)
            else:
                types["other"].append(name)
        
        return types
    
    async def close_all(self) -> None:
        """Close all provider connections and cleanup resources."""
        for name, provider in self._providers.items():
            try:
                if hasattr(provider, 'close'):
                    await provider.close()
                    self.logger.info(f"Closed provider: {name}")
            except Exception as e:
                self.logger.error(f"Error closing provider {name}: {e}")


# Global container instance
_container: Optional[ProviderContainer] = None


def get_container() -> ProviderContainer:
    """Get the global provider container.
    
    Returns:
        ProviderContainer instance
    """
    global _container
    if _container is None:
        _container = ProviderContainer()
    return _container


def reset_container() -> None:
    """Reset the global container (useful for testing)."""
    global _container
    _container = None


def register_provider(
    name: str,
    provider_class: Type[Provider],
    instance: Optional[Provider] = None,
    fallback_to: Optional[List[str]] = None
) -> None:
    """Register a provider with the global container.
    
    Args:
        name: Provider name
        provider_class: Provider class
        instance: Optional instance
        fallback_to: Fallback chain
    """
    container = get_container()
    container.register(name, provider_class, instance, fallback_to)


def get_provider(name: str) -> Optional[Provider]:
    """Get a provider from the global container.
    
    Args:
        name: Provider name
        
    Returns:
        Provider instance or None
    """
    return get_container().get(name)


# Convenience functions for common providers

def get_geo() -> Optional[GeoProvider]:
    """Get default geo provider."""
    return get_container().get_geo_provider()


def get_content() -> Optional[ContentProvider]:
    """Get default content provider."""
    return get_container().get_content_provider()


def get_image() -> Optional[ImageProvider]:
    """Get default image provider."""
    return get_container().get_image_provider()


def get_search() -> Optional[SearchProvider]:
    """Get default search provider."""
    return get_container().get_search_provider()
