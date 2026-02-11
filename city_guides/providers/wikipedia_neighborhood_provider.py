# Wikipedia Neighborhood Provider for TravelLand
# Direct MediaWiki API integration for neighborhood data
# Clean, English-focused, lightweight implementation

import aiohttp
import re
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

class WikipediaNeighborhoodProvider:
    """Direct MediaWiki API provider for Wikipedia neighborhood data"""
    
    def __init__(self):
        self.base_url = "https://en.wikipedia.org/api/rest_v1"
        self.cache_dir = Path(__file__).parent.parent / ".cache" / "wikipedia_neighborhood"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    async def get_neighborhood_data(self, city: str, neighborhood: str, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        """Get neighborhood data from Wikipedia MediaWiki API with redirect handling"""
        cache_key = f"{city.lower()}_{neighborhood.lower()}"
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        # Check cache first (24 hour TTL)
        if cache_file.exists():
            try:
                import time
                if time.time() - cache_file.stat().st_mtime < 86400:  # 24 hours
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.logger.debug(f"Wikipedia cache hit for {city}/{neighborhood}")
                    return data
                else:
                    # Cache expired, remove it
                    cache_file.unlink()
            except Exception as e:
                self.logger.warning(f"Failed to read Wikipedia cache for {city}/{neighborhood}: {e}")
        
        # Try multiple search approaches for neighborhood data
        search_queries = []
        
        # If it's a Mexican city, prioritize Spanish Wikipedia and Mexican context
        if city.lower() in ['rosarito', 'tijuana', 'ensenada', 'mexicali', 'playas de tijuana'] or neighborhood.lower() in ['corona del mar', 'pórticos de san antonio']:
            # Spanish Wikipedia queries for Mexican neighborhoods
            search_queries.extend([
                f"{neighborhood}, {city}",  # Most specific
                f"{neighborhood} {city}",  # Simple combination
                f"{neighborhood}, Tijuana Municipality",  # Administrative context
                f"{neighborhood}, Baja California",  # State context
                f"{neighborhood}, Mexico",  # Country context
                f"{neighborhood}"  # Fallback
            ])
            
            # Try Spanish Wikipedia first for Mexican content
            base_url = "https://es.wikipedia.org/api/rest_v1"
        else:
            # English Wikipedia for other locations
            search_queries.extend([
                f"{neighborhood}, {city}",
                f"{neighborhood} neighborhood {city}",
                f"{neighborhood} {city}",
                f"{neighborhood}, {city}, California" if city.lower() in ['newport beach', 'los angeles', 'san diego'] else f"{neighborhood}, {city}",
                f"{neighborhood}"
            ])
            base_url = self.base_url
        
        self.logger.info(f"Wikipedia search for {city}/{neighborhood}: Using {'Spanish' if base_url == 'https://es.wikipedia.org/api/rest_v1' else 'English'} Wikipedia")
        
        for query in search_queries:
            try:
                # Try Wikipedia summary API
                slug = re.sub(r"\s+", "_", query)
                url = f"{base_url}/page/summary/{slug}"
                
                self.logger.info(f"Wikipedia API query: {query} -> {url}")
                async with session.get(url, timeout=8) as resp:
                    self.logger.info(f"Wikipedia API response status: {resp.status} for {query}")
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Check for redirects and follow them
                        if data.get('redirected'):
                            self.logger.debug(f"Wikipedia redirected from {query} to {data.get('title', 'unknown')}")
                        
                        # Validate that this is actually about the neighborhood/city
                        is_relevant = self._is_relevant_result(data, neighborhood, city)
                        self.logger.info(f"Wikipedia result relevance for {query}: {is_relevant}")
                        
                        if is_relevant:
                            # Cache the result
                            try:
                                with open(cache_file, 'w', encoding='utf-8') as f:
                                    json.dump(data, f, indent=2)
                            except Exception as e:
                                self.logger.warning(f"Failed to cache Wikipedia data for {city}/{neighborhood}: {e}")
                            
                            self.logger.info(f"Wikipedia found relevant data for {city}/{neighborhood}")
                            return data
                        else:
                            self.logger.debug(f"Wikipedia result not relevant for {query}")
                    else:
                        self.logger.debug(f"Wikipedia API returned status {resp.status} for {query}")
            except Exception as e:
                self.logger.debug(f"Wikipedia API failed for query '{query}': {e}")
                continue
        
        return None
    
    def _is_relevant_result(self, data: Dict[str, Any], neighborhood: str, city: str) -> bool:
        """Check if Wikipedia result is actually about the neighborhood/city"""
        if not data:
            return False
        
        title = data.get('title', '').lower()
        description = data.get('extract', '').lower()
        
        # Must mention the neighborhood
        if neighborhood.lower() not in title:
            return False
        
        # Check for city mention
        city_mentioned = city.lower() in title or city.lower() in description
        
        # For Mexican cities, prioritize Mexican context
        if city.lower() in ['rosarito', 'tijuana', 'ensenada', 'mexicali', 'playas de tijuana']:
            mexican_indicators = [
                'mexico', 'méxico', 'baja california', 'tijuana', 'rosarito', 
                'ensenada', 'mexicali', 'municipio', 'colonia'
            ]
            has_mexican_context = any(indicator in description for indicator in mexican_indicators)
            
            # Reject if it mentions US locations for Mexican neighborhoods
            us_indicators = ['california', 'united states', 'usa', 'newport beach']
            has_us_context = any(indicator in description for indicator in us_indicators)
            
            if has_us_context and not has_mexican_context:
                return False  # Reject US content for Mexican neighborhoods
            
            return has_mexican_context or city_mentioned
        
        # For non-Mexican cities, use original logic
        neighborhood_indicators = [
            'neighborhood', 'area', 'district', 'suburb', 'locality', 
            'colonia', 'barrio', 'residential', 'community'
        ]
        
        has_neighborhood_keywords = any(indicator in description for indicator in neighborhood_indicators)
        
        # Must have some neighborhood indicators or city mention
        return has_neighborhood_keywords or city_mentioned
    
    def extract_neighborhood_info(self, wiki_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract essential neighborhood information from Wikipedia data"""
        info = {
            'name': wiki_data.get('title', ''),
            'source': 'wikipedia',
            'source_url': wiki_data.get('content_urls', {}).get('desktop', {}).get('page', ''),
            'description': wiki_data.get('extract', ''),
            'summary': wiki_data.get('description', ''),  # One-line summary
            'coordinates': {
                'lat': wiki_data.get('coordinates', {}).get('lat'),
                'lon': wiki_data.get('coordinates', {}).get('lon')
            },
            'thumbnail': wiki_data.get('thumbnail', {}),
            'image': wiki_data.get('originalimage', {}),  # Full-size image
            'lang': wiki_data.get('lang', 'en')
        }
        
        # Clean up the description (remove disclaimers)
        description = info['description']
        if description:
            # Remove common Wikipedia disclaimers
            disclaimers = [
                'This article is about',
                'For other uses',
                'See also',
                'Not to be confused with',
                'This article may be too long to read and navigate comfortably'
            ]
            for disclaimer in disclaimers:
                if disclaimer.lower() in description.lower():
                    # Remove everything from the disclaimer onward
                    idx = description.lower().find(disclaimer.lower())
                    if idx != -1:
                        description = description[:idx].rstrip()
                        break
            info['description'] = description.strip()
        
        # Handle case where we have both summary and extract
        if info['summary'] and info['description']:
            # Use summary as primary, extract as backup
            if len(info['summary']) > 50:  # Only use if summary is substantial
                info['description'] = info['summary']
        
        return info

# Global instance
# No global singleton. Always create and pass WikipediaNeighborhoodProvider explicitly.
