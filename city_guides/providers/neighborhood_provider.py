"""Neighborhood-specific venue provider for TravelLand.
Reads pre-curated venue data from neighborhood JSON files.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional

def get_neighborhood_venue_data(neighborhood_name: str, city: str = "san_francisco") -> Optional[Dict]:
    """
    Get pre-curated venue data for a specific neighborhood.

    Args:
        neighborhood_name: Name of the neighborhood (e.g., "japantown")
        city: City name in lowercase with underscores (e.g., "san_francisco")

    Returns:
        Dictionary containing venue data or None if not found
    """
    try:
        # Construct the path to the neighborhood data file
        base_path = Path(__file__).parent.parent / "src" / "data" / "neighborhood_quick_guides" / city
        file_path = base_path / f"{neighborhood_name.lower()}.json"

        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        else:
            return None

    except Exception as e:
        print(f"Error reading neighborhood venue data: {e}")
        return None

def get_neighborhood_venues(neighborhood_name: str, venue_type: str = None, city: str = "san_francisco") -> List[Dict]:
    """
    Get specific venues from neighborhood data. Falls back to API providers when local data missing.

    Args:
        neighborhood_name: Name of the neighborhood
        venue_type: Type of venues to filter by (e.g., "coffee_and_tea", "restaurants")
        city: City name

    Returns:
        List of venue dictionaries
    """
    neighborhood_data = get_neighborhood_venue_data(neighborhood_name, city)
    venues = []
    
    # First try local curated data
    if neighborhood_data and 'venues' in neighborhood_data:
        venues_data = neighborhood_data['venues']
        
        if venue_type and venue_type in venues_data:
            venues = venues_data[venue_type]
        elif not venue_type:
            # Return all venues if no specific type requested
            for venue_category in venues_data.values():
                if isinstance(venue_category, list):
                    venues.extend(venue_category)

    # If local data missing, try API providers (with fallback)
    if not venues:
        try:
            from city_guides.providers.multi_provider import discover_pois
            print(f"[FALLBACK] Querying API providers for {neighborhood_name}")

            # Map venue type to POI category
            poi_type = "restaurant"
            if venue_type:
                type_map = {
                    "coffee_and_tea": "cafe",
                    "restaurants": "restaurant",
                    "shopping": "shop",
                    "parks": "park"
                }
                poi_type = type_map.get(venue_type, venue_type.split('_')[0])

            # Attempt API provider lookup
            venues = discover_pois(
                city=city,
                poi_type=poi_type,
                limit=12,
                neighborhood=neighborhood_name
            )
            
            if not venues:
                print(f"[WARN] No API venues found for {neighborhood_name}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch venues from API providers: {e}")
            return []

    return venues

def get_neighborhood_recommendations(neighborhood_name: str, category: str = None, city: str = "san_francisco") -> Optional[str]:
    """
    Get pre-written recommendations for a neighborhood.

    Args:
        neighborhood_name: Name of the neighborhood
        category: Recommendation category (e.g., "coffee_tea", "food", "culture")
        city: City name

    Returns:
        Recommendation text or None
    """
    neighborhood_data = get_neighborhood_venue_data(neighborhood_name, city)

    if not neighborhood_data or 'recommendations' not in neighborhood_data:
        return None

    recommendations = neighborhood_data['recommendations']

    if category and category in recommendations:
        return recommendations[category]
    elif not category and recommendations:
        # Return all recommendations concatenated
        all_recs = []
        for rec_category, rec_text in recommendations.items():
            all_recs.append(f"**{rec_category.replace('_', ' ').title()}**: {rec_text}")
        return "\n\n".join(all_recs)
    else:
        return None

def normalize_venue_for_search(venue: Dict) -> Dict:
    """
    Normalize neighborhood venue data to match the format expected by search functions.

    Args:
        venue: Raw venue dictionary from neighborhood data

    Returns:
        Normalized venue dictionary
    """
    normalized = {
        "name": venue.get("name", "Unnamed venue"),
        "amenity": venue.get("type", "venue"),
        "cuisine": venue.get("cuisine", ""),
        "address": venue.get("address", ""),
        "website": venue.get("website", ""),
        "lat": None,  # These would need to be geocoded
        "lon": None,
        "tags": ", ".join(venue.get("features", [])),
        "description": venue.get("description", ""),
        "specialty": venue.get("specialty", ""),
        "hours": venue.get("hours", ""),
        "rating": venue.get("rating", 0),
        "source": "neighborhood_data"
    }

    # Add OSM-style URL if we had coordinates (we don't in this data)
    # normalized["osm_url"] = f"https://www.openstreetmap.org/node/{venue.get('osm_id', '')}" if venue.get('osm_id') else ""

    return normalized

async def async_get_neighborhood_venues(neighborhood_name: str, venue_type: str = None, city: str = "san_francisco") -> List[Dict]:
    """
    Async wrapper for getting neighborhood venues.

    Args:
        neighborhood_name: Name of the neighborhood
        venue_type: Type of venues to filter by
        city: City name

    Returns:
        List of normalized venue dictionaries
    """
    venues = get_neighborhood_venues(neighborhood_name, venue_type, city)
    return [normalize_venue_for_search(venue) for venue in venues]

def search_neighborhood_venues_by_query(query: str, neighborhood_name: str, city: str = "san_francisco") -> List[Dict]:
    """
    Search neighborhood venues based on a user query.

    Args:
        query: User's search query
        neighborhood_name: Name of the neighborhood
        city: City name

    Returns:
        List of matching venue dictionaries
    """
    query_lower = query.lower()

    # Get all venues for this neighborhood
    all_venues = get_neighborhood_venues(neighborhood_name, city=city)

    if not all_venues:
        return []

    # Filter venues based on query keywords
    matching_venues = []

    coffee_keywords = ['coffee', 'cafe', 'espresso', 'latte', 'brew']
    tea_keywords = ['tea', 'matcha', 'green tea', 'tea house', 'tea ceremony']
    japanese_keywords = ['japanese', 'sushi', 'ramen', 'izakaya', 'sake']

    for venue in all_venues:
        venue_name = venue.get("name", "").lower()
        venue_type = venue.get("type", "").lower()
        venue_cuisine = venue.get("cuisine", "").lower()
        venue_description = venue.get("description", "").lower()
        venue_specialty = venue.get("specialty", "").lower()
        venue_features = [f.lower() for f in venue.get("features", [])]

        # Check if this venue matches the query
        matches_query = False

        # Direct name match
        if query_lower in venue_name:
            matches_query = True
        # Type/cuisine match
        elif any(keyword in query_lower for keyword in [venue_type, venue_cuisine, venue_specialty]):
            matches_query = True
        # Description match
        elif query_lower in venue_description:
            matches_query = True
        # Feature match
        elif any(query_lower in feature for feature in venue_features):
            matches_query = True
        # Category-based matching
        elif any(keyword in query_lower for keyword in coffee_keywords) and venue_type in ['coffee_shop', 'cafe']:
            matches_query = True
        elif any(keyword in query_lower for keyword in tea_keywords) and venue_type in ['tea_house', 'cafe']:
            matches_query = True
        elif any(keyword in query_lower for keyword in japanese_keywords) and 'japanese' in venue_cuisine:
            matches_query = True

        if matches_query:
            matching_venues.append(venue)

    return matching_venues

def get_japantown_coffee_tea_venues() -> List[Dict]:
    """
    Get coffee and tea venues specifically for Japantown, San Francisco.

    Returns:
        List of coffee/tea venue dictionaries
    """
    return get_neighborhood_venues("japantown", "coffee_and_tea", "san_francisco")