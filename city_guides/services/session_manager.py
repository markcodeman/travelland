"""
Session management for proper resource handling and connection pooling.

This module provides a centralized session manager to fix resource leaks
and ensure proper cleanup of HTTP sessions across all providers.
"""

import asyncio
import aiohttp
from typing import Optional
from contextlib import asynccontextmanager

from city_guides.utils.async_utils import get_timeout


class SessionManager:
    """Centralized HTTP session manager with proper resource management.
    
    This fixes the resource leak issue where 59 different providers
    were creating and closing their own sessions, leading to:
    - Connection pool exhaustion
    - Resource leaks
    - Inconsistent timeout configurations
    - Race conditions in session management
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one session manager exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the session manager."""
        if not hasattr(self, '_initialized'):
            self._session: Optional[aiohttp.ClientSession] = None
            self._initialized = True
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get the shared HTTP session, creating it if necessary.
        
        Uses a lock to prevent race conditions when multiple coroutines
        try to create the session simultaneously.
        
        Returns:
            HTTP client session
        """
        async with self._lock:
            if self._session is None or self._session.closed:
                self._session = self._create_session()
            return self._session
    
    def _create_session(self) -> aiohttp.ClientSession:
        """Create a new HTTP session with proper configuration.
        
        Returns:
            Configured HTTP client session
        """
        timeout = aiohttp.ClientTimeout(
            total=get_timeout('api'),
            connect=get_timeout('api'),
            sock_read=get_timeout('api'),
            sock_connect=get_timeout('api')
        )
        
        connector = aiohttp.TCPConnector(
            limit=100,  # Max connections
            limit_per_host=20,  # Max connections per host
            enable_cleanup_closed=True,
            force_close=False,
            keepalive_timeout=30.0,
            ttl_dns_cache=300,
            use_dns_cache=True
        )
        
        return aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'User-Agent': 'TravelLand/1.0 (https://github.com/markcodeman/travelland)',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        )
    
    async def close(self):
        """Close the shared session and clean up resources."""
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
    
    @asynccontextmanager
    async def session_context(self):
        """Context manager for session usage with automatic cleanup.
        
        Example:
            async with session_manager.session_context() as session:
                async with session.get(url) as response:
                    return await response.json()
        """
        session = await self.get_session()
        try:
            yield session
        except Exception:
            # Don't close session on exceptions, let it be reused
            raise
        finally:
            # Session is managed centrally, don't close it here
            pass
    
    async def health_check(self) -> bool:
        """Check if the session manager is healthy.
        
        Returns:
            True if session is available and healthy
        """
        try:
            session = await self.get_session()
            return not session.closed
        except Exception:
            return False
    
    async def get_stats(self) -> dict:
        """Get session statistics for monitoring.
        
        Returns:
            Dictionary with session statistics
        """
        try:
            session = await self.get_session()
            connector = session.connector
            
            if connector:
                return {
                    'total_connections': connector._total_connections,
                    'available_connections': connector._acquired,
                    'closed': session.closed,
                    'timeout': session.timeout.total,
                }
            else:
                return {'error': 'No connector available'}
        except Exception as e:
            return {'error': str(e)}


# Global session manager instance
session_manager = SessionManager()


# Convenience functions for common usage patterns

async def get_session() -> aiohttp.ClientSession:
    """Get the global HTTP session.
    
    Returns:
        HTTP client session from the global manager
    """
    return await session_manager.get_session()


@asynccontextmanager
async def session_context():
    """Get a session context from the global manager.
    
    Example:
        async with session_context() as session:
            async with session.get(url) as response:
                return await response.json()
    """
    async with session_manager.session_context() as session:
        yield session


async def close_session():
    """Close the global session manager.
    
    This should be called during application shutdown.
    """
    await session_manager.close()


async def health_check() -> bool:
    """Check if the global session manager is healthy.
    
    Returns:
        True if session manager is healthy
    """
    return await session_manager.health_check()


async def get_session_stats() -> dict:
    """Get statistics from the global session manager.
    
    Returns:
        Dictionary with session statistics
    """
    return await session_manager.get_stats()


# Provider-specific session utilities

class ProviderSessionManager:
    """Session manager specifically for providers with retry logic."""
    
    def __init__(self, max_retries: int = 3):
        """Initialize with retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
        """
        self.max_retries = max_retries
    
    async def make_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """Make an HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional request arguments
            
        Returns:
            HTTP response
            
        Raises:
            aiohttp.ClientError: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                session = await get_session()
                
                # Add common headers
                headers = kwargs.get('headers', {})
                headers.update({
                    'Accept': 'application/json',
                    'User-Agent': 'TravelLand/1.0 (https://github.com/markcodeman/travelland)',
                })
                kwargs['headers'] = headers
                
                async with session.request(method, url, **kwargs) as response:
                    # Raise for status to catch HTTP errors
                    response.raise_for_status()
                    return response
                    
            except aiohttp.ClientError as e:
                last_exception = e
                if attempt == self.max_retries:
                    break
                
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
        
        # If we get here, all retries failed
        raise last_exception
    
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make a GET request with retry logic.
        
        Args:
            url: Request URL
            **kwargs: Additional request arguments
            
        Returns:
            HTTP response
        """
        return await self.make_request('GET', url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make a POST request with retry logic.
        
        Args:
            url: Request URL
            **kwargs: Additional request arguments
            
        Returns:
            HTTP response
        """
        return await self.make_request('POST', url, **kwargs)


# Global provider session manager
provider_session_manager = ProviderSessionManager()


# Convenience functions for providers

async def provider_get(url: str, **kwargs) -> aiohttp.ClientResponse:
    """Make a GET request with retry logic for providers.
    
    Args:
        url: Request URL
        **kwargs: Additional request arguments
        
    Returns:
        HTTP response
    """
    return await provider_session_manager.get(url, **kwargs)


async def provider_post(url: str, **kwargs) -> aiohttp.ClientResponse:
    """Make a POST request with retry logic for providers.
    
    Args:
        url: Request URL
        **kwargs: Additional request arguments
        
    Returns:
        HTTP response
    """
    return await provider_session_manager.post(url, **kwargs)