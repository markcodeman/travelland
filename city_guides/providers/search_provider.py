"""
SearchProvider implementation using DuckDuckGo Search (DDGS).

This provider performs web searches using DDGS with proper fallbacks
and result filtering.
"""

from typing import Optional, Dict, Any, List
import asyncio
from urllib.parse import urlparse

from city_guides.providers.base import SearchProvider, ProviderMetadata, ProviderError
from city_guides.config import get_config


class DDGSearchProvider(SearchProvider):
    """SearchProvider implementation using DuckDuckGo Search."""
    
    def __init__(self):
        """Initialize the DDG search provider."""
        super().__init__()
        self.config = get_config()
        self.blocked_domains = set(self.config.provider_config.blocked_ddgs_domains)
    
    async def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata."""
        return ProviderMetadata(
            name="ddgs",
            version="1.0.0",
            description="DuckDuckGo Search API",
            capabilities=["search", "web_results", "news"],
            rate_limit=100  # requests per hour (estimated)
        )
    
    def _is_blocked_domain(self, url: str) -> bool:
        """Check if URL is from a blocked domain.
        
        Args:
            url: URL to check
            
        Returns:
            True if domain is blocked
        """
        try:
            domain = urlparse(url).netloc.lower()
            # Remove www. prefix for comparison
            if domain.startswith('www.'):
                domain = domain[4:]
            
            for blocked in self.blocked_domains:
                if blocked in domain:
                    return True
            return False
        except Exception:
            return False
    
    def _format_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format search result to standard format.
        
        Args:
            result: Raw search result
            
        Returns:
            Formatted result dictionary
        """
        return {
            "title": result.get("title", ""),
            "url": result.get("href", ""),
            "snippet": result.get("body", ""),
            "source": "ddgs"
        }
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Perform a search using DuckDuckGo.
        
        Args:
            query: Search query
            limit: Maximum results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        if not query or not query.strip():
            return []
        
        try:
            # Import DDGS here to avoid dependency issues
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                self.logger.error("duckduckgo-search package not installed")
                return []
            
            # Run DDGS in thread pool to not block async
            loop = asyncio.get_event_loop()
            
            def _do_search():
                with DDGS() as ddgs:
                    results = []
                    for r in ddgs.text(
                        query,
                        max_results=limit * 2,  # Get extra to filter blocked domains
                        region="wt-wt",  # Worldwide
                        safesearch="moderate"
                    ):
                        results.append(r)
                        if len(results) >= limit * 2:
                            break
                    return results
            
            raw_results = await asyncio.wait_for(
                loop.run_in_executor(None, _do_search),
                timeout=self.config.get_timeout('ddgs')
            )
            
            # Filter blocked domains and format
            filtered = []
            for result in raw_results:
                url = result.get("href", "")
                if not self._is_blocked_domain(url):
                    filtered.append(self._format_result(result))
                    if len(filtered) >= limit:
                        break
            
            return filtered
            
        except asyncio.TimeoutError:
            self.logger.warning(f"DDG search timed out for query: {query}")
            return []
        except Exception as e:
            self.logger.warning(f"DDG search failed: {e}")
            return []
    
    async def search_with_fallback(
        self,
        query: str,
        limit: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search with fallback support.
        
        This method is the same as search() for DDGS since it handles
        its own fallbacks internally.
        
        Args:
            query: Search query
            limit: Maximum results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        return await self.search(query, limit, **kwargs)
    
    async def search_news(
        self,
        query: str,
        limit: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search for news articles.
        
        Args:
            query: Search query
            limit: Maximum results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of news results
        """
        if not query or not query.strip():
            return []
        
        try:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                self.logger.error("duckduckgo-search package not installed")
                return []
            
            loop = asyncio.get_event_loop()
            
            def _do_news_search():
                with DDGS() as ddgs:
                    results = []
                    for r in ddgs.news(
                        query,
                        max_results=limit,
                        region="wt-wt"
                    ):
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "snippet": r.get("body", ""),
                            "source": r.get("source", ""),
                            "date": r.get("date", ""),
                            "image": r.get("image", None)
                        })
                        if len(results) >= limit:
                            break
                    return results
            
            return await asyncio.wait_for(
                loop.run_in_executor(None, _do_news_search),
                timeout=self.config.get_timeout('ddgs')
            )
            
        except asyncio.TimeoutError:
            self.logger.warning(f"DDG news search timed out for query: {query}")
            return []
        except Exception as e:
            self.logger.warning(f"DDG news search failed: {e}")
            return []


class SearxSearchProvider(SearchProvider):
    """Fallback SearchProvider using Searx instance."""
    
    def __init__(self, base_url: Optional[str] = None):
        """Initialize the Searx search provider.
        
        Args:
            base_url: Searx instance URL (optional)
        """
        super().__init__()
        self.config = get_config()
        self.base_url = base_url or "https://searx.be"  # Public instance
    
    async def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata."""
        return ProviderMetadata(
            name="searx",
            version="1.0.0",
            description="Searx meta-search engine (fallback)",
            capabilities=["search", "web_results"],
            rate_limit=30  # requests per minute
        )
    
    def _format_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format Searx result to standard format."""
        return {
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "snippet": result.get("content", ""),
            "source": result.get("engine", "searx")
        }
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search using Searx."""
        if not query or not query.strip():
            return []
        
        try:
            from city_guides.services.session_manager import get_session
            import aiohttp
            
            session = await get_session()
            timeout = self.config.get_timeout('search')
            
            params = {
                "q": query,
                "format": "json",
                "language": "en-US",
                "safesearch": "1",
                "categories": "general"
            }
            
            async with session.get(
                f"{self.base_url}/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                results = data.get("results", [])
                
                return [self._format_result(r) for r in results[:limit]]
                
        except Exception as e:
            self.logger.warning(f"Searx search failed: {e}")
            return []
    
    async def search_with_fallback(
        self,
        query: str,
        limit: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search with fallback."""
        return await self.search(query, limit, **kwargs)
