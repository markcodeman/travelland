"""
ContentProvider implementation using Wikipedia API.

This provider fetches textual content about locations from Wikipedia
with proper caching and fallbacks.
"""

from typing import Optional, Dict, Any, List
import aiohttp
import json
from pathlib import Path
import hashlib
import re

from city_guides.providers.base import ContentProvider, ProviderMetadata, ProviderError
from city_guides.config import get_config
from city_guides.services.session_manager import get_session


class WikipediaContentProvider(ContentProvider):
    """ContentProvider implementation using Wikipedia API."""
    
    WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
    
    def __init__(self):
        """Initialize the Wikipedia content provider."""
        super().__init__()
        self.config = get_config()
        self.cache_dir = Path(__file__).parent / ".cache" / "content"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata."""
        return ProviderMetadata(
            name="wikipedia",
            version="1.0.0",
            description="Wikipedia content API",
            capabilities=["content", "summary", "facts", "history"],
            rate_limit=None  # No strict rate limit
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
    
    def _clean_wiki_text(self, text: str) -> str:
        """Clean Wikipedia markup from text.
        
        Args:
            text: Raw Wikipedia text
            
        Returns:
            Cleaned text
        """
        # Remove citations [1], [2], etc.
        text = re.sub(r'\[\d+\]', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Strip
        return text.strip()
    
    async def get_content(self, location: str, topic: str = "general") -> Optional[str]:
        """Get content about a location from Wikipedia.
        
        Args:
            location: Location name
            topic: Topic to get content about
            
        Returns:
            Content string or None if not found
        """
        if not location or not location.strip():
            return None
        
        cache_key = self._get_cache_key(f"content:{location}:{topic}")
        cached = self._read_cache(cache_key)
        if cached and cached.get("content"):
            return cached["content"]
        
        try:
            session = await get_session()
            timeout = self.config.get_timeout('wikipedia')
            
            # Search for the page
            search_params = {
                "action": "query",
                "list": "search",
                "srsearch": location,
                "format": "json",
                "srlimit": 1
            }
            
            headers = {
                "User-Agent": "TravelLand/1.0 (https://github.com/markcodeman/travelland)"
            }
            
            async with session.get(
                self.WIKIPEDIA_API_URL,
                params=search_params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                search_results = data.get("query", {}).get("search", [])
                
                if not search_results:
                    return None
                
                page_title = search_results[0]["title"]
            
            # Get the page content
            content_params = {
                "action": "query",
                "prop": "extracts",
                "titles": page_title,
                "format": "json",
                "explaintext": 1,
                "exlimit": 1,
                "exsentences": 10
            }
            
            async with session.get(
                self.WIKIPEDIA_API_URL,
                params=content_params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                pages = data.get("query", {}).get("pages", {})
                
                if not pages:
                    return None
                
                page = list(pages.values())[0]
                extract = page.get("extract", "")
                
                if not extract:
                    return None
                
                cleaned = self._clean_wiki_text(extract)
                
                # Cache result
                self._write_cache(cache_key, {"content": cleaned})
                
                return cleaned
                
        except Exception as e:
            self.logger.warning(f"Failed to get content for {location}: {e}")
            return None
    
    async def get_summary(self, location: str, max_length: int = 500) -> Optional[str]:
        """Get a brief summary about a location.
        
        Args:
            location: Location name
            max_length: Maximum summary length
            
        Returns:
            Summary string or None if not found
        """
        content = await self.get_content(location)
        if not content:
            return None
        
        # Truncate to max_length, ending at a sentence boundary
        if len(content) <= max_length:
            return content
        
        # Find the last sentence end before max_length
        truncated = content[:max_length]
        last_period = truncated.rfind('.')
        last_exclaim = truncated.rfind('!')
        last_question = truncated.rfind('?')
        
        end_pos = max(last_period, last_exclaim, last_question)
        
        if end_pos > 0:
            return content[:end_pos + 1]
        
        # If no sentence boundary found, just truncate with ellipsis
        return content[:max_length - 3] + "..."
    
    async def get_facts(self, location: str, limit: int = 5) -> List[str]:
        """Get interesting facts about a location.
        
        Args:
            location: Location name
            limit: Maximum number of facts
            
        Returns:
            List of fact strings
        """
        content = await self.get_content(location)
        if not content:
            return []
        
        # Split into sentences and filter for interesting ones
        sentences = re.split(r'(?<=[.!?])\s+', content)
        
        facts = []
        for sentence in sentences:
            sentence = sentence.strip()
            # Skip short sentences
            if len(sentence) < 30:
                continue
            # Skip sentences with dates/years (often boring)
            if re.search(r'\b\d{4}\b', sentence):
                continue
            facts.append(sentence)
            
            if len(facts) >= limit:
                break
        
        return facts
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for content."""
        topic = kwargs.get("topic", "general")
        content = await self.get_content(query, topic)
        if content:
            return [{"content": content, "source": "wikipedia"}]
        return []


class WikivoyageContentProvider(ContentProvider):
    """Fallback ContentProvider using Wikivoyage."""
    
    WIKIVOYAGE_API_URL = "https://en.wikivoyage.org/w/api.php"
    
    def __init__(self):
        """Initialize the Wikivoyage content provider."""
        super().__init__()
        self.config = get_config()
    
    async def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata."""
        return ProviderMetadata(
            name="wikivoyage",
            version="1.0.0",
            description="Wikivoyage travel guide API (fallback)",
            capabilities=["content", "summary", "travel_info"],
            rate_limit=None
        )
    
    async def get_content(self, location: str, topic: str = "general") -> Optional[str]:
        """Get travel content from Wikivoyage."""
        if not location or not location.strip():
            return None
        
        try:
            session = await get_session()
            timeout = self.config.get_timeout('wikipedia')
            
            # Get page content
            params = {
                "action": "query",
                "prop": "extracts",
                "titles": location,
                "format": "json",
                "explaintext": 1,
                "exsentences": 10
            }
            
            headers = {
                "User-Agent": "TravelLand/1.0 (https://github.com/markcodeman/travelland)"
            }
            
            async with session.get(
                self.WIKIVOYAGE_API_URL,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                pages = data.get("query", {}).get("pages", {})
                
                if not pages:
                    return None
                
                page = list(pages.values())[0]
                
                # Check if page exists (pageid = -1 means missing)
                if page.get("pageid", 0) == -1 or page.get("missing"):
                    return None
                
                extract = page.get("extract", "")
                
                if not extract:
                    return None
                
                # Clean the text
                extract = re.sub(r'\[\d+\]', '', extract)
                extract = re.sub(r'\s+', ' ', extract).strip()
                
                return extract
                
        except Exception as e:
            self.logger.warning(f"Failed to get Wikivoyage content for {location}: {e}")
            return None
    
    async def get_summary(self, location: str, max_length: int = 500) -> Optional[str]:
        """Get summary from Wikivoyage."""
        content = await self.get_content(location)
        if not content:
            return None
        
        if len(content) <= max_length:
            return content
        
        truncated = content[:max_length]
        last_period = truncated.rfind('.')
        
        if last_period > 0:
            return content[:last_period + 1]
        
        return content[:max_length - 3] + "..."
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for content."""
        topic = kwargs.get("topic", "general")
        content = await self.get_content(query, topic)
        if content:
            return [{"content": content, "source": "wikivoyage"}]
        return []
