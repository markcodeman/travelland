"""
Neighborhood enrichment module for TravelLand
Handles geo-enrichment and quick guide building
"""

from typing import Dict, Optional
from city_guides.providers import multi_provider
try:
    from city_guides.src.geo_enrichment import enrich_neighborhood as geo_enrich_neighborhood
except ImportError:
    try:
        from geo_enrichment import enrich_neighborhood as geo_enrich_neighborhood
    except ImportError:
        # Fallback to direct imports if in same directory or PYTHONPATH is set
        import geo_enrichment
        geo_enrich_neighborhood = geo_enrichment.enrich_neighborhood
from city_guides.src.synthesis_enhancer import SynthesisEnhancer


async def enrich_neighborhood(city: str, neighborhood: str, session=None) -> Optional[Dict]:
    """
    Enrich neighborhood data with geo information and POIs
    
    Args:
        city: City name
        neighborhood: Neighborhood name
        session: Optional aiohttp session
        
    Returns:
        Enriched neighborhood data or None
    """
    try:
        # Try to get neighborhood data from providers
        neighborhoods = await multi_provider.async_get_neighborhoods(
            city=city, 
            lat=None, 
            lon=None, 
            lang='en', 
            session=session
        )
        
        # Find matching neighborhood
        target_neighborhood = None
        for nb in neighborhoods:
            if nb.get('name', '').lower() == neighborhood.lower():
                target_neighborhood = nb
                break
        
        if not target_neighborhood:
            return None
            
        # Get coordinates for geo enrichment
        lat = target_neighborhood.get('lat') or target_neighborhood.get('center', {}).get('lat')
        lon = target_neighborhood.get('lon') or target_neighborhood.get('center', {}).get('lon')
        
        if not lat or not lon:
            return None
            
        # Perform geo enrichment
        enrichment = await geo_enrich_neighborhood(city, neighborhood, session=session)
        return enrichment
        
    except Exception as e:
        print(f"Error enriching neighborhood {neighborhood}: {e}")
        return None


def build_enriched_quick_guide(neighborhood: str, city: str, enrichment: Dict) -> str:
    """
    Build a quick guide from enriched neighborhood data
    
    Args:
        neighborhood: Neighborhood name
        city: City name
        enrichment: Enrichment data from geo_enrichment module
        
    Returns:
        Formatted quick guide text
    """
    try:
        text = enrichment.get('text', '')
        pois = enrichment.get('pois', [])
        
        if text and pois:
            # Combine text and POIs
            poi_names = [poi.get('name', '') for poi in pois if poi.get('name')]
            poi_list = ', '.join(poi_names[:3])  # Top 3 POIs
            
            guide = f"{neighborhood} is a neighborhood in {city}. {text}"
            if poi_list:
                guide += f" Notable places include: {poi_list}."
            return guide
        elif text:
            return f"{neighborhood} is a neighborhood in {city}. {text}"
        elif pois:
            poi_names = [poi.get('name', '') for poi in pois if poi.get('name')]
            poi_list = ', '.join(poi_names[:3])
            return f"{neighborhood} is a neighborhood in {city}. Notable places include: {poi_list}."
        else:
            return f"{neighborhood} is a neighborhood in {city}."
            
    except Exception as e:
        print(f"Error building enriched quick guide: {e}")
        return f"{neighborhood} is a neighborhood in {city}."


async def get_neighborhood_enrichment(city: str, neighborhood: str, session=None) -> Dict:
    """
    Get comprehensive neighborhood enrichment data
    
    Args:
        city: City name
        neighborhood: Neighborhood name
        session: Optional aiohttp session
        
    Returns:
        Comprehensive enrichment data
    """
    enrichment = await enrich_neighborhood(city, neighborhood, session)
    
    if enrichment:
        quick_guide = build_enriched_quick_guide(neighborhood, city, enrichment)
        return {
            'quick_guide': quick_guide,
            'enrichment': enrichment,
            'source': 'geo-enriched',
            'confidence': 'medium'
        }
    else:
        # Fallback to synthesized content
        try:
            synthesized = SynthesisEnhancer.generate_neighborhood_paragraph(neighborhood, city)
            return {
                'quick_guide': synthesized,
                'enrichment': None,
                'source': 'synthesized',
                'confidence': 'low'
            }
        except Exception:
            return {
                'quick_guide': f"{neighborhood} is a neighborhood in {city}.",
                'enrichment': None,
                'source': 'data-first',
                'confidence': 'low'
            }