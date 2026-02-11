# Groq Neighborhood Provider for TravelLand
# Uses Groq API to generate rich neighborhood content when Wikipedia is unavailable
# Perfect for Mexican neighborhoods without Spanish Wikipedia coverage

import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

class GroqNeighborhoodProvider:
    """Groq API provider for neighborhood content generation"""
    
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.1-8b-instant"
        self.cache_dir = Path(__file__).parent.parent / ".cache" / "groq_neighborhood"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        if not self.api_key:
            self.logger.warning("GROQ_API_KEY not configured - Groq provider will be disabled")
    
    async def generate_neighborhood_content(self, city: str, neighborhood: str, session=None) -> Optional[Dict[str, Any]]:
        """Generate neighborhood content using Groq API"""
        if not self.api_key:
            return None
        
        cache_key = f"{city.lower()}_{neighborhood.lower()}"
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        # Check cache first (24 hour TTL)
        if cache_file.exists():
            try:
                import time
                if time.time() - cache_file.stat().st_mtime < 86400:  # 24 hours
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.logger.debug(f"Groq cache hit for {city}/{neighborhood}")
                    return data
                else:
                    # Cache expired, remove it
                    cache_file.unlink()
            except Exception as e:
                self.logger.warning(f"Failed to read Groq cache for {city}/{neighborhood}: {e}")
        
        try:
            # Build system prompt for neighborhood content
            system_prompt = self._build_neighborhood_system_prompt(city)
            
            # Build user prompt with context
            user_prompt = self._build_neighborhood_user_prompt(city, neighborhood)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Call Groq API
            import aiohttp
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, headers=headers, json=payload, timeout=15) as resp:
                    if resp.status == 200:
                        response_data = await resp.json()
                        
                        if "choices" in response_data and len(response_data["choices"]) > 0:
                            content = response_data["choices"][0]["message"]["content"]
                            
                            # Parse and structure the content
                            structured_content = self._parse_groq_response(content, city, neighborhood)
                            
                            # Cache the result
                            try:
                                with open(cache_file, 'w', encoding='utf-8') as f:
                                    json.dump(structured_content, f, indent=2)
                            except Exception as e:
                                self.logger.warning(f"Failed to cache Groq data for {city}/{neighborhood}: {e}")
                            
                            self.logger.info(f"Groq generated content for {city}/{neighborhood}")
                            return structured_content
                    else:
                        self.logger.warning(f"Groq API returned status {resp.status}")
        except Exception as e:
            self.logger.exception(f"Groq API call failed for {city}/{neighborhood}: {e}")
        
        return None
    
    def _build_neighborhood_system_prompt(self, city: str) -> str:
        """Build system prompt for neighborhood content generation"""
        # Add city-specific context
        city_context = ""
        if city.lower() in ['rosarito', 'tijuana', 'ensenada', 'mexicali']:
            city_context = f"""
You are generating content for neighborhoods in {city}, Baja California, Mexico.
Focus on Mexican context, local culture, geography, and practical information for visitors.
Include details about local amenities, transportation, safety, and what makes this area unique.
"""
        else:
            city_context = f"""
You are generating content for neighborhoods in {city}.
Focus on local context, practical information, and what makes this area special.
"""
        
        return f"""You are a travel content writer specializing in neighborhood descriptions.{city_context}

Generate a concise, informative paragraph (2-4 sentences) about the neighborhood.
Focus on:
- Location and geographic context
- Notable features, amenities, or attractions  
- Local character and atmosphere
- Practical information for visitors

Use a neutral, informative tone suitable for a travel guide.
Avoid overly promotional language or generic descriptions.
If the neighborhood is in Mexico, emphasize Mexican culture and local context.
"""
    
    def _build_neighborhood_user_prompt(self, city: str, neighborhood: str) -> str:
        """Build user prompt with specific neighborhood context"""
        return f"""Generate a travel guide description for "{neighborhood}" in "{city}".

Please provide:
- A concise 2-4 sentence description
- Focus on what makes this neighborhood special or notable
- Include practical information for visitors
- Use an informative, neutral tone
- Avoid generic statements like "This is a neighborhood in..."

Context: This is for a travel guide app that helps visitors understand local neighborhoods."""
    
    def _parse_groq_response(self, content: str, city: str, neighborhood: str) -> Dict[str, Any]:
        """Parse Groq response into structured format"""
        return {
            'name': neighborhood,
            'city': city,
            'source': 'groq',
            'description': content.strip(),
            'generated_at': __import__('time').time(),
            'model': self.model
        }
    
    def extract_neighborhood_info(self, groq_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract neighborhood information from Groq data"""
        return {
            'name': groq_data.get('name', ''),
            'source': 'groq',
            'description': groq_data.get('description', ''),
            'city': groq_data.get('city', ''),
            'generated_at': groq_data.get('generated_at'),
            'model': groq_data.get('model')
        }

# Global instance
# No global singleton. Always create and pass GroqNeighborhoodProvider explicitly.
