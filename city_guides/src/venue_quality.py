"""
Venue Quality Scoring System

This module provides comprehensive quality scoring for venues to ensure
only high-quality venues are presented to users.
"""

import re
import logging
from typing import Dict, Any, List

# Quality scoring constants
QUALITY_WEIGHTS = {
    'address_completeness': 0.25,
    'contact_info': 0.20,
    'opening_hours': 0.15,
    'website': 0.15,
    'description': 0.15,
    'coordinates': 0.10
}

MINIMUM_QUALITY_SCORE = 0.7  # Minimum score to be considered "good"


def is_venue_closed_or_disused(venue: Dict[str, Any]) -> bool:
    """
    Check if a venue is closed, disused, or demolished based on OSM tags.
    
    Returns True if venue appears to be permanently closed.
    """
    tags = venue.get('tags', {})
    if isinstance(tags, str):
        # Parse string tags to dict if needed
        tags_dict = {}
        for tag in tags.split(','):
            if '=' in tag:
                k, v = tag.split('=', 1)
                tags_dict[k.strip()] = v.strip()
        tags = tags_dict
    
    # Check for explicit closed/disused/demolished tags
    closed_indicators = [
        'disused:amenity', 'disused:shop', 'disused:tourism',
        'demolished:building', 'demolished:amenity',
        'was:amenity', 'was:shop', 'was:tourism',
        'abandoned:amenity', 'abandoned:building',
        'removed:amenity', 'removed:building'
    ]
    
    for indicator in closed_indicators:
        if indicator in tags:
            return True
    
    # Check for status tags indicating closure
    status_tags = ['status', 'condition', 'operational_status']
    for tag in status_tags:
        if tag in tags:
            value = tags[tag].lower()
            if any(word in value for word in ['closed', 'disused', 'demolished', 'abandoned', 'removed', 'inactive']):
                return True
    
    # Check for opening hours indicating permanent closure
    hours = tags.get('opening_hours', '').lower()
    if hours and any(indicator in hours for indicator in ['closed', 'demolished', 'removed']):
        return True
    
    return False


def calculate_venue_quality_score(venue: Dict[str, Any]) -> float:
    """
    Calculate a comprehensive quality score for a venue (0.0 to 1.0).
    
    Args:
        venue: Venue dictionary with tags, address, etc.
    
    Returns:
        Quality score between 0.0 and 1.0 (0.0 if venue is closed)
    """
    # First check if venue is closed/disused - automatic 0.0 score
    if is_venue_closed_or_disused(venue):
        logging.debug(f"Venue '{venue.get('name', 'Unknown')}' appears to be closed/disused")
        return 0.0
    
    score = 0.0
    weights = QUALITY_WEIGHTS
    
    # 1. Address Completeness (25%)
    address_score = _calculate_address_score(venue)
    score += address_score * weights['address_completeness']
    
    # 2. Contact Information (20%)
    contact_score = _calculate_contact_score(venue)
    score += contact_score * weights['contact_info']
    
    # 3. Opening Hours (15%)
    hours_score = _calculate_hours_score(venue)
    score += hours_score * weights['opening_hours']
    
    # 4. Website (15%)
    website_score = _calculate_website_score(venue)
    score += website_score * weights['website']
    
    # 5. Description/Tags (15%)
    description_score = _calculate_description_score(venue)
    score += description_score * weights['description']
    
    # 6. Coordinates (10%)
    coordinates_score = _calculate_coordinates_score(venue)
    score += coordinates_score * weights['coordinates']
    
    return round(score, 2)


def _calculate_address_score(venue: Dict[str, Any]) -> float:
    """Calculate address quality score (0.0 to 1.0)."""
    address = venue.get('address', '')
    display_address = venue.get('display_address', '')
    
    # Check if address is just coordinates (poor quality)
    if address and re.match(r'^-?\d+\.?\d*\s*,\s*-?\d+\.?\d*$', address.strip()):
        return 0.0
    
    # Check if display address exists and is meaningful
    if display_address and len(display_address) > 10 and not display_address.startswith('📍'):
        return 1.0
    
    # Check if raw address exists and is meaningful
    if address and len(address) > 10:
        return 0.8
    
    # Check for coordinate-only fallback
    lat = venue.get('lat')
    lon = venue.get('lon')
    if lat and lon:
        return 0.3  # Better than nothing, but poor
    
    return 0.0


def _calculate_contact_score(venue: Dict[str, Any]) -> float:
    """Calculate contact information quality score."""
    tags = venue.get('tags', {})
    if isinstance(tags, str):
        # Parse string tags
        tags_dict = {}
        for tag in tags.split(','):
            if '=' in tag:
                k, v = tag.split('=', 1)
                tags_dict[k.strip()] = v.strip()
    elif isinstance(tags, dict):
        tags_dict = tags
    else:
        tags_dict = {}
    
    # Check for phone number
    phone = tags_dict.get('phone') or tags_dict.get('contact:phone')
    if phone and len(str(phone)) >= 7:
        return 1.0
    
    # Check for email
    email = tags_dict.get('email') or tags_dict.get('contact:email')
    if email and '@' in str(email):
        return 0.5
    
    return 0.0


def _calculate_hours_score(venue: Dict[str, Any]) -> float:
    """Calculate opening hours quality score."""
    opening_hours = venue.get('opening_hours', '')
    
    if not opening_hours:
        return 0.0
    
    # Check for meaningful hours (not just "24/7" or empty)
    if opening_hours.strip() in ['24/7', '24h', '24 hr', '']:
        return 0.3
    
    # Check for actual time ranges
    if re.search(r'\d{1,2}:\d{2}', opening_hours):
        return 1.0
    
    return 0.2


def _calculate_website_score(venue: Dict[str, Any]) -> float:
    """Calculate website quality score."""
    website = venue.get('website', '')
    tags = venue.get('tags', {})
    
    if isinstance(tags, dict):
        website = website or tags.get('website') or tags.get('contact:website')
    
    if website and ('http' in str(website) or '.' in str(website)):
        return 1.0
    
    return 0.0


def _calculate_description_score(venue: Dict[str, Any]) -> float:
    """Calculate description and tags quality score."""
    tags = venue.get('tags', {})
    name = venue.get('name', '')
    
    if isinstance(tags, str):
        # Count meaningful tags
        tag_count = len([t for t in tags.split(',') if '=' in t and len(t) > 3])
        if tag_count >= 3:
            return 1.0
        elif tag_count >= 1:
            return 0.5
        else:
            return 0.0
    elif isinstance(tags, dict):
        # Count meaningful tag keys
        meaningful_tags = 0
        for key, value in tags.items():
            if key and value and len(str(key)) > 2 and len(str(value)) > 1:
                meaningful_tags += 1
        
        if meaningful_tags >= 3:
            return 1.0
        elif meaningful_tags >= 1:
            return 0.5
        else:
            return 0.0
    
    # If no tags, check if name is meaningful
    if name and len(name) > 3 and name.lower() not in ['unknown', 'unnamed', '']:
        return 0.3
    
    return 0.0


def _calculate_coordinates_score(venue: Dict[str, Any]) -> float:
    """Calculate coordinates quality score."""
    lat = venue.get('lat')
    lon = venue.get('lon')
    
    try:
        lat_val = float(lat) if lat is not None else None
        lon_val = float(lon) if lon is not None else None
        
        # Valid coordinates range check
        if lat_val is not None and lon_val is not None:
            if -90 <= lat_val <= 90 and -180 <= lon_val <= 180:
                return 1.0
    
    except (ValueError, TypeError):
        pass
    
    return 0.0


def filter_high_quality_venues(venues: List[Dict[str, Any]], min_score: float = None) -> List[Dict[str, Any]]:
    """
    Filter venues to only include high-quality ones.
    
    Args:
        venues: List of venue dictionaries
        min_score: Minimum quality score (defaults to MINIMUM_QUALITY_SCORE)
    
    Returns:
        List of high-quality venues
    """
    if min_score is None:
        min_score = MINIMUM_QUALITY_SCORE
    
    high_quality = []
    for venue in venues:
        score = calculate_venue_quality_score(venue)
        venue['quality_score'] = score
        if score >= min_score:
            high_quality.append(venue)
        else:
            logging.debug(f"Filtered out venue '{venue.get('name', 'Unknown')}' with quality score {score}")
    
    return high_quality


def get_venue_quality_insights(venue: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get detailed quality insights for a venue.
    
    Returns:
        Dictionary with quality breakdown and improvement suggestions
    """
    insights = {
        'overall_score': calculate_venue_quality_score(venue),
        'components': {},
        'improvements': []
    }
    
    # Calculate individual component scores
    insights['components']['address'] = _calculate_address_score(venue)
    insights['components']['contact'] = _calculate_contact_score(venue)
    insights['components']['hours'] = _calculate_hours_score(venue)
    insights['components']['website'] = _calculate_website_score(venue)
    insights['components']['description'] = _calculate_description_score(venue)
    insights['components']['coordinates'] = _calculate_coordinates_score(venue)
    
    # Generate improvement suggestions
    if insights['components']['address'] < 0.8:
        insights['improvements'].append("Add complete street address")
    
    if insights['components']['contact'] < 1.0:
        insights['improvements'].append("Add phone number or email")
    
    if insights['components']['hours'] < 1.0:
        insights['improvements'].append("Add detailed opening hours")
    
    if insights['components']['website'] < 1.0:
        insights['improvements'].append("Add official website")
    
    if insights['components']['description'] < 1.0:
        insights['improvements'].append("Add more descriptive tags")
    
    return insights


def is_venue_acceptable(venue: Dict[str, Any], min_score: float = None) -> bool:
    """Check if a venue meets minimum quality standards."""
    return calculate_venue_quality_score(venue) >= (min_score or MINIMUM_QUALITY_SCORE)


def enhance_venue_with_quality_data(venue: Dict[str, Any]) -> Dict[str, Any]:
    """Add quality score and insights to venue data."""
    venue_copy = venue.copy()
    venue_copy['quality_score'] = calculate_venue_quality_score(venue)
    venue_copy['quality_insights'] = get_venue_quality_insights(venue)
    return venue_copy


# Special handling for Chinese venues
def is_chinese_venue(venue: Dict[str, Any]) -> bool:
    """Detect if venue is likely Chinese based on name or tags."""
    name = venue.get('name', '')
    tags = venue.get('tags', {})
    
    if isinstance(tags, dict):
        cuisine = tags.get('cuisine', '').lower()
        if 'chinese' in cuisine:
            return True
    
    # Check for Chinese characters in name
    chinese_pattern = r'[\u4e00-\u9fff]'
    if re.search(chinese_pattern, name):
        return True
    
    # Check for common Chinese venue patterns
    chinese_keywords = ['chinese', 'dim sum', 'noodles', 'wok', 'bao', 'dumpling']
    name_lower = name.lower()
    if any(keyword in name_lower for keyword in chinese_keywords):
        return True
    
    return False


def enhance_chinese_venue_processing(venue: Dict[str, Any]) -> Dict[str, Any]:
    """Apply special processing for Chinese venues to improve quality."""
    if not is_chinese_venue(venue):
        return venue
    
    venue_copy = venue.copy()
    
    # Improve address handling for Chinese venues
    address = venue_copy.get('address', '')
    if address and len(address) < 10:
        # Chinese addresses might be shorter but still valid
        venue_copy['address_quality_boost'] = 0.2
    
    # Special handling for Chinese cuisine tags
    tags = venue_copy.get('tags', {})
    if isinstance(tags, dict):
        cuisine = tags.get('cuisine', '').lower()
        if 'chinese' in cuisine:
            # Boost quality score for properly tagged Chinese venues
            venue_copy['cuisine_quality_boost'] = 0.1
    
    return venue_copy