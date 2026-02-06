"""
Persistence module for TravelLand application.

This module contains helper functions for caching and persisting data,
separated from app.py and routes.py to avoid circular import issues.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

# Import SynthesisEnhancer lazily to break circular dependency
_synthesis_enhancer = None

def get_synthesis_enhancer():
    global _synthesis_enhancer
    if _synthesis_enhancer is None:
        try:
            from synthesis_enhancer import SynthesisEnhancer
        except ImportError:
            from city_guides.src.synthesis_enhancer import SynthesisEnhancer
        _synthesis_enhancer = SynthesisEnhancer
    return _synthesis_enhancer

# Import other modules
try:
    from city_guides.src.snippet_filters import looks_like_ddgs_disambiguation_text
except ImportError:
    from snippet_filters import looks_like_ddgs_disambiguation_text
try:
    from city_guides.src.venue_quality import filter_high_quality_venues, calculate_venue_quality_score, enhance_chinese_venue_processing
except ImportError:
    from venue_quality import filter_high_quality_venues, calculate_venue_quality_score, enhance_chinese_venue_processing


async def _persist_quick_guide(out_obj: Dict, city_name: str, neighborhood_name: str, file_path: Path) -> None:
    """Persist quick_guide to the filesystem and (optionally) to Redis.

    This is an async function safe to call from an already-running event loop.
    It prefers `aiofiles` for non-blocking writes and falls back to `asyncio.to_thread`.
    """
    try:
        if looks_like_ddgs_disambiguation_text(out_obj.get('quick_guide') or ''):
            logging.info('Not caching disambiguation/promotional ddgs quick_guide for %s/%s', city_name, neighborhood_name)
            # replace with synthesized neutral paragraph if available; fall back to a simple sentence
            try:
                se = get_synthesis_enhancer()
                try:
                    # call possible sync or async method on enhancer in a thread-safe way
                    if hasattr(se, 'generate_neighborhood_paragraph'):
                        # if it's async, run it; otherwise run in thread
                        gen = se.generate_neighborhood_paragraph
                        if asyncio.iscoroutinefunction(gen):
                            new_para = await gen(neighborhood_name, city_name)
                        else:
                            new_para = await asyncio.to_thread(gen, neighborhood_name, city_name)
                    else:
                        new_para = f"{neighborhood_name} is a neighborhood in {city_name}."
                except Exception:
                    new_para = f"{neighborhood_name} is a neighborhood in {city_name}."
            except Exception:
                new_para = f"{neighborhood_name} is a neighborhood in {city_name}."

            out_obj['quick_guide'] = new_para
            out_obj['source'] = out_obj.get('source', 'synthesized')
            out_obj['source_url'] = None
            out_obj['confidence'] = out_obj.get('confidence', 'low')

        # Neutralize tone on quick_guide before persisting (async-safe)
        try:
            se = get_synthesis_enhancer()
            qg = out_obj.get('quick_guide') or ''
            if hasattr(se, 'neutralize_tone'):
                neutral = se.neutralize_tone
                if asyncio.iscoroutinefunction(neutral):
                    qg_clean = await neutral(qg, neighborhood_name, city_name)
                else:
                    qg_clean = await asyncio.to_thread(neutral, qg, neighborhood_name, city_name)
                out_obj['quick_guide'] = qg_clean
        except Exception:
            # Proceed even if neutralization fails
            pass

        # Write to file asynchronously using aiofiles if available, otherwise use thread
        try:
            import aiofiles
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(out_obj, ensure_ascii=False, indent=2))
        except ImportError:
            # Fallback: run blocking write in thread to avoid blocking event loop
            def _sync_write():
                with open(file_path, 'w', encoding='utf-8') as fh:
                    json.dump(out_obj, fh, ensure_ascii=False, indent=2)
            await asyncio.to_thread(_sync_write)

    except Exception as e:
        logging.exception('Failed to persist quick_guide: %s', e)


def build_search_cache_key(city: str, q: str, neighborhood: Dict | None = None) -> str:
    """Build cache key for search results"""
    import hashlib
    
    nh_key = ""
    if neighborhood:
        nh_id = neighborhood.get("id", "")
        nh_key = f":{nh_id}"
    raw = f"search:{(city or '').strip().lower()}:{(q or '').strip().lower()}{nh_key}"
    return "travelland:" + hashlib.sha1(raw.encode()).hexdigest()


def ensure_bbox(neighborhood: Dict) -> Dict:
    """Generate a bbox if neighborhood is a point without one."""
    if neighborhood.get('bbox'):
        return neighborhood
    
    center = neighborhood.get('center')
    if center is None:
        center = {}
    
    lat = center.get('lat')
    lon = center.get('lon')
    
    if lat and lon:
        # Create ~2.5km radius bbox (roughly 0.025 degrees)
        radius = 0.025
        neighborhood['bbox'] = [
            float(lon) - radius,  # min_lon
            float(lat) - radius,  # min_lat
            float(lon) + radius,  # max_lon
            float(lat) + radius   # max_lat
        ]
        neighborhood['bbox_generated'] = True  # Flag for debugging
    
    return neighborhood


def format_venue(venue: Dict) -> Dict:
    """Format venue for display"""
    address = venue.get('address', '')
    
    # Don't use coordinates as display address
    if address and re.match(r'^-?\d+\.\d+,\s*-?\d+\.\d+$', address):
        venue['display_address'] = None
        venue['coordinates'] = address
    else:
        venue['display_address'] = address
    
    return venue


def determine_budget(tags: Dict) -> str:
    """Determine budget level from tags"""
    tags_lower = str(tags).lower()
    if 'fast_food' in tags_lower or 'cost=cheap' in tags_lower:
        return 'cheap'
    elif 'cuisine=fast_food' in tags_lower:
        return 'cheap'
    else:
        return 'mid'


def determine_price_range(tags: Dict) -> str:
    """Determine price range indicator"""
    budget = determine_budget(tags)
    return '$' if budget == 'cheap' else '$$'


def generate_description(poi: Dict) -> str:
    """Generate user-friendly description"""
    tags = poi.get('tags', {})
    features = []

    if tags.get('cuisine'):
        features.append(tags['cuisine'].title())
    if tags.get('outdoor_seating') == 'yes':
        features.append('outdoor seating')
    if tags.get('wheelchair') == 'yes':
        features.append('accessible')
    if tags.get('takeaway') == 'yes':
        features.append('takeaway available')

    feature_text = f" with {', '.join(features)}" if features else ""

    base_type = poi.get('type', 'venue').title()
    return f"{base_type}{feature_text}"


def enrich_venue_data(venue: Dict, city: str = "") -> Dict:
    """
    Enrich venue with human-readable context extracted from tags.
    Handles both dot-notation tags (catering.restaurant.french) and key=value tags (amenity=restaurant).
    """
    raw_tags = venue.get("tags", {})
    
    # Normalize tags into a list format
    tag_list = []
    if isinstance(raw_tags, str):
        tag_list = [t.strip() for t in raw_tags.split(",") if t.strip()]
    elif isinstance(raw_tags, dict):
        # Convert dict to key=value strings
        for k, v in raw_tags.items():
            if v is True or v == "yes":
                tag_list.append(k)
            elif v:
                tag_list.append(f"{k}={v}")
    elif isinstance(raw_tags, list):
        tag_list = raw_tags
    
    # Build a searchable string of all tags
    tag_str = ",".join(tag_list).lower()
    
    # === VENUE TYPE DETECTION ===
    venue_type = None
    venue_emoji = "📍"
    
    # Check dot-notation patterns first (more specific)
    dot_patterns = [
        ("catering.restaurant", "🍽️", "Restaurant"),
        ("catering.restaurant.french", "🍽️", "French Restaurant"),
        ("catering.restaurant.italian", "🍝", "Italian Restaurant"),
        ("catering.restaurant.japanese", "🍜", "Japanese Restaurant"),
        ("catering.restaurant.chinese", "🥡", "Chinese Restaurant"),
        ("catering.restaurant.indian", "🍛", "Indian Restaurant"),
        ("catering.cafe", "☕", "Cafe"),
        ("catering.coffee_shop", "☕", "Coffee Shop"),
        ("catering.bar", "🍺", "Bar"),
        ("catering.pub", "🍻", "Pub"),
        ("catering.fast_food", "🍔", "Fast Food"),
        ("catering.ice_cream", "🍦", "Ice Cream"),
        ("catering.biergarten", "🍺", "Beer Garden"),
        ("accommodation.hotel", "🏨", "Hotel"),
        ("accommodation.hostel", "🏠", "Hostel"),
        ("tourism.museum", "🏛️", "Museum"),
        ("tourism.attraction", "🎯", "Attraction"),
        ("tourism.viewpoint", "📸", "Viewpoint"),
        ("tourism.hotel", "🏨", "Hotel"),
        ("entertainment.cinema", "🎬", "Cinema"),
        ("entertainment.theatre", "🎭", "Theatre"),
        ("commercial.shopping_mall", "🛍️", "Shopping Mall"),
        ("commercial.supermarket", "🛒", "Supermarket"),
        ("commercial.books", "📚", "Bookstore"),
        ("commercial.convenience", "🏪", "Convenience Store"),
        ("commercial.bakery", "🥐", "Bakery"),
        ("leisure.park", "🌳", "Park"),
        ("public_transport.subway", "🚇", "Subway Station"),
        ("public_transport.bus", "🚌", "Bus Stop"),
        ("building.catering", "🍽️", "Restaurant"),
    ]
    
    for pattern, emoji, label in dot_patterns:
        if pattern in tag_str:
            venue_type = f"{emoji} {label}"
            venue_emoji = emoji
            break
    
    # Check key=value amenity tags
    if not venue_type:
        amenity_match = None
        for tag in tag_list:
            if tag.startswith("amenity="):
                amenity_match = tag.split("=", 1)[1].lower()
                break
        
        if amenity_match:
            amenity_map = {
                "restaurant": ("🍽️", "Restaurant"),
                "cafe": ("☕", "Cafe"),
                "coffee_shop": ("☕", "Coffee Shop"),
                "bar": ("🍺", "Bar"),
                "pub": ("�", "Pub"),
                "fast_food": ("🍔", "Fast Food"),
                "ice_cream": ("�", "Ice Cream"),
                "biergarten": ("🍺", "Beer Garden"),
                "hotel": ("🏨", "Hotel"),
                "hostel": ("🏠", "Hostel"),
                "museum": ("🏛️", "Museum"),
                "cinema": ("🎬", "Cinema"),
                "theatre": ("🎭", "Theatre"),
                "library": ("📚", "Library"),
                "shop": ("🛍️", "Shop"),
                "supermarket": ("🛒", "Supermarket"),
                "convenience": ("🏪", "Convenience Store"),
                "bakery": ("🥐", "Bakery"),
                "park": ("🌳", "Park"),
                "wine_bar": ("🍷", "Wine Bar"),
            }
            if amenity_match in amenity_map:
                emoji, label = amenity_map[amenity_match]
                venue_type = f"{emoji} {label}"
                venue_emoji = emoji
    
    if not venue_type:
        venue_type = "📍 Venue"
    
    # === CUISINE DETECTION ===
    cuisine = None
    
    # Look for explicit cuisine tag
    for tag in tag_list:
        if tag.startswith("cuisine="):
            cuisine_val = tag.split("=", 1)[1]
            # Clean up: replace underscores, semicolons with commas
            cuisine = cuisine_val.replace("_", " ").replace(";", ", ")
            cuisine = ", ".join(word.title() for word in cuisine.split(", "))
            break
    
    # Infer cuisine from dot-notation (e.g., catering.restaurant.french)
    if not cuisine:
        cuisine_patterns = [
            (".french", "French"),
            (".italian", "Italian"),
            (".japanese", "Japanese"),
            (".chinese", "Chinese"),
            (".indian", "Indian"),
            (".mexican", "Mexican"),
            (".thai", "Thai"),
            (".vietnamese", "Vietnamese"),
            (".korean", "Korean"),
            (".spanish", "Spanish"),
            (".greek", "Greek"),
            (".turkish", "Turkish"),
            (".lebanese", "Lebanese"),
            (".moroccan", "Moroccan"),
            (".ethiopian", "Ethiopian"),
            (".brazilian", "Brazilian"),
            (".american", "American"),
            (".burger", "Burgers"),
            (".pizza", "Pizza"),
            (".sushi", "Sushi"),
            (".seafood", "Seafood"),
            (".fish", "Seafood"),
            (".steak", "Steakhouse"),
            (".regional", "Regional"),
            (".local", "Local"),
            (".european", "European"),
            (".asian", "Asian"),
            (".mediterranean", "Mediterranean"),
        ]
        for pattern, cuisine_name in cuisine_patterns:
            if pattern in tag_str:
                cuisine = cuisine_name
                break
    
    # Infer cuisine from venue name when no explicit tag
    if not cuisine:
        venue_name_lower = venue.get("name", "").lower()
        name_cuisine_map = [
            ("couscous", "Moroccan"),
            ("sushi", "Japanese"),
            ("ramen", "Japanese"),
            ("pizza", "Italian"),
            ("pasta", "Italian"),
            ("trattoria", "Italian"),
            ("tapas", "Spanish"),
            ("burrito", "Mexican"),
            ("taco", "Mexican"),
            ("curry", "Indian"),
            ("tandoori", "Indian"),
            ("thai", "Thai"),
            ("phở", "Vietnamese"),
            ("pho", "Vietnamese"),
            ("banh mi", "Vietnamese"),
            ("burger", "American"),
            ("angus", "Steakhouse"),
            ("steakhouse", "Steakhouse"),
            ("bbq", "BBQ"),
            ("barbecue", "BBQ"),
            ("kebab", "Turkish"),
            ("shawarma", "Middle Eastern"),
            ("falafel", "Middle Eastern"),
            ("gyros", "Greek"),
            ("souvlaki", "Greek"),
            ("korean", "Korean"),
            ("kimchi", "Korean"),
            ("chinese", "Chinese"),
            ("dim sum", "Chinese"),
            ("noodle", "Asian"),
            ("seafood", "Seafood"),
            ("fish", "Seafood"),
            ("lobster", "Seafood"),
            ("brasserie", "French"),
            ("bistro", "French"),
            ("crêperie", "French"),
            ("creperie", "French"),
            ("bagel", "American"),
            ("café", "Cafe"),
            ("cafe", "Cafe"),
            ("coffee", "Coffee"),
            ("ice cream", "Ice Cream"),
            ("gelato", "Italian"),
        ]
        for keyword, cuisine_type in name_cuisine_map:
            if keyword in venue_name_lower:
                cuisine = cuisine_type
                break
    
    # === PRICE LEVEL DETECTION ===
    price_level = "moderate"
    price_indicator = "€€"
    
    for tag in tag_list:
        if tag.startswith("price=") or tag.startswith("price_range="):
            val = tag.split("=", 1)[1].lower()
            if val in ["cheap", "$", "1", "€"]:
                price_level = "cheap"
                price_indicator = "€"
            elif val in ["expensive", "$$$", "3", "€€€"]:
                price_level = "expensive"
                price_indicator = "€€€"
            elif val in ["very_expensive", "$$$$", "4", "€€€€", "luxury"]:
                price_level = "luxury"
                price_indicator = "€€€€"
            break
    
    # === FEATURES EXTRACTION ===
    features = []
    
    feature_checks = [
        ("wheelchair=yes", "♿ Accessible"),
        ("wheelchair.yes", "♿ Accessible"),
        ("outdoor_seating=yes", "🌿 Outdoor seating"),
        ("terrace", "🌿 Outdoor seating"),
        ("wifi=yes", "📶 WiFi"),
        ("internet_access=yes", "📶 WiFi"),
        ("delivery=yes", "🛵 Delivery"),
        ("takeaway=yes", "🥡 Takeaway"),
        ("vegetarian=yes", "🥗 Vegetarian"),
        ("vegan=yes", "🌱 Vegan"),
        ("halal=yes", "☪️ Halal"),
        ("kosher=yes", "✡️ Kosher"),
        ("live_music=yes", "🎵 Live music"),
        ("music", "🎵 Live music"),
        ("reservation=yes", "📅 Reservations"),
        ("smoking=no", "🚭 No smoking"),
        ("payment:cards=yes", "💳 Cards accepted"),
        ("payment:cash_only=yes", "💵 Cash only"),
    ]
    
    for pattern, feature_label in feature_checks:
        if pattern in tag_str:
            if feature_label not in features:
                features.append(feature_label)
    
    # === OPENING HOURS EXTRACTION ===
    opening_hours = None
    for tag in tag_list:
        if tag.startswith("opening_hours="):
            opening_hours = tag.split("=", 1)[1]
            break
    
    # === PHONE NUMBER EXTRACTION ===
    phone = None
    for tag in tag_list:
        if tag.startswith("phone=") or tag.startswith("contact:phone="):
            phone = tag.split("=", 1)[1]
            break
    
    # === GENERATE DESCRIPTION ===
    description_parts = []
    
    # Start with venue type (without emoji for cleaner description)
    type_clean = venue_type.split(" ", 1)[1] if " " in venue_type else venue_type
    
    if cuisine:
        # Avoid redundant descriptions like "Cafe cafe" or "Coffee coffee shop"
        cuisine_lower = cuisine.lower()
        type_lower = type_clean.lower()
        if cuisine_lower == type_lower or (cuisine_lower in type_lower and len(cuisine_lower) > 3):
            description_parts.append(type_clean)
        else:
            description_parts.append(f"{cuisine} {type_lower}")
    else:
        # Provide contextual fallback based on venue name patterns
        venue_name_lower = venue.get("name", "").lower()
        
        # Try to infer style/type from name - BUT avoid "wine bar" for non-bar venues
        venue_name_lower = venue.get("name", "").lower()
        
        # Check if venue type is actually a bar/pub before inferring "wine bar"
        is_actual_bar = any(bt in venue_type.lower() for bt in ['bar', 'pub', 'biergarten', 'lounge'])
        
        if any(word in venue_name_lower for word in ['table', 'lancaster', 'lutétia', 'lutetia']):
            description_parts.append(f"Classic French {type_clean.lower()}")
        elif any(word in venue_name_lower for word in ['menuiserie', 'atelier', 'workshop']):
            description_parts.append(f"Converted workshop {type_clean.lower()}")
        elif any(word in venue_name_lower for word in ['bistrot', 'bistro']):
            description_parts.append("Traditional bistro")
        elif any(word in venue_name_lower for word in ['brasserie']):
            description_parts.append("Classic brasserie")
        elif is_actual_bar and any(word in venue_name_lower for word in ['wine', 'vin']):
            description_parts.append("Wine bar")
        elif is_actual_bar and any(word in venue_name_lower for word in ['belushi', 'sportsbar', 'sports bar']):
            description_parts.append("Sports bar with American atmosphere")
        elif 'juice bar' in venue_name_lower or 'juice' in venue_name_lower:
            description_parts.append("Juice bar")
        elif 'sushi bar' in venue_name_lower:
            description_parts.append("Sushi bar")
        elif 'raw bar' in venue_name_lower:
            description_parts.append("Raw bar")
        elif is_actual_bar and 'bar' in venue_name_lower:
            # Generic bar without wine/sports specifier
            description_parts.append(type_clean)
        else:
            # Generic but with location
            description_parts.append(type_clean)
    
    # Add city context
    if city:
        description_parts.append(f"in {city}")
    
    # Add key features to description (first 2)
    if features:
        key_features = [f for f in features if not f.startswith("♿")][:2]
        if key_features:
            description_parts.append(f"({', '.join(key_features)})")
    
    description = " ".join(description_parts) if description_parts else f"{type_clean} in {city}" if city else type_clean
    
    return {
        "venue_type": venue_type,
        "cuisine": cuisine or "",
        "price_level": price_level,
        "price_indicator": price_indicator,
        "features": features,
        "description": description,
        "opening_hours": opening_hours,
        "phone": phone
    }


def format_venue_for_display(poi: Dict) -> Dict:
    """Format venue for frontend display"""
    address = poi.get('address', '')

    # Use coordinates only as fallback
    if address and re.match(r'^-?\d+\.\d+,\s*-?\d+\.\d+$', address):
        display_address = None
        coordinates = address
    else:
        display_address = address
        coordinates = f"{poi.get('lat')},{poi.get('lon')}"

    return {
        'id': poi.get('id'),
        'city': '',  # Will be set by caller
        'name': poi.get('name', 'Unknown'),
        'budget': determine_budget(poi.get('tags', {})),
        'price_range': determine_price_range(poi.get('tags', {})),
        'description': generate_description(poi),
        'tags': poi.get('tags', ''),
        'address': display_address,
        'latitude': poi.get('lat'),
        'longitude': poi.get('lon'),
        'website': poi.get('website', ''),
        'osm_url': poi.get('osm_url', ''),
        'amenity': poi.get('type'),
        'provider': 'osm',
        'phone': poi.get('phone'),
        'rating': None,  # OSM doesn't have ratings
        'opening_hours': poi.get('opening_hours'),
        'opening_hours_pretty': _humanize_opening_hours(poi.get('opening_hours')),
        'open_now': _compute_open_now(poi.get('lat'), poi.get('lon'), poi.get('opening_hours'))[0],
        'quality_score': poi.get('quality_score', 0),
    }


def _humanize_opening_hours(opening_hours_str: Optional[str]) -> Optional[str]:
    """Return a user-friendly hours string in 12-hour format if possible."""
    if not opening_hours_str:
        return None
    import re
    from datetime import time

    def fmt(tstr):
        try:
            hh, mm = tstr.split(":")
            t = time(int(hh), int(mm))
            return t.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")
        except Exception:
            return tstr

    pretty_parts = []
    for part in opening_hours_str.split(";"):
        part = part.strip()
        if not part:
            continue
        # replace ranges like 10:00-22:30 with 10:00 AM–10:30 PM
        part = re.sub(
            r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})",
            lambda m: f"{fmt(m.group(1))}–{fmt(m.group(2))}",
            part,
        )
        pretty_parts.append(part)
    return "; ".join(pretty_parts) if pretty_parts else None


def _compute_open_now(lat, lon, opening_hours_str):
    """Best-effort server-side opening_hours check."""
    if not opening_hours_str:
        return (None, None)

    s = opening_hours_str.strip()
    if not s:
        return (None, None)

    # Quick common check
    if "24/7" in s or "24h" in s or "24 hr" in s.lower():
        return (True, None)

    # Determine timezone (best-effort)
    tzname = None
    try:
        from timezonefinder import TimezoneFinder
        tf = TimezoneFinder()
        tzname = tf.timezone_at(lat=float(lat), lng=float(lon)) if lat and lon else None
    except Exception:
        tzname = None

        # If timezonefinder isn't available or didn't find a timezone, allow an
        # explicit override via DEFAULT_TZ (useful on hosts like Render that run in UTC).
        if not tzname:
            tz_env = os.getenv("DEFAULT_TZ")
            if tz_env:
                tzname = tz_env

    from datetime import datetime, time

    try:
        from zoneinfo import ZoneInfo
    except Exception:
        ZoneInfo = None

    if tzname and ZoneInfo:
        try:
            now = datetime.now(ZoneInfo(tzname))
        except Exception:
            now = datetime.now()
    else:
        now = datetime.now()

    # Map short day names to weekday numbers
    days_map = {"mo": 0, "tu": 1, "we": 2, "th": 3, "fr": 4, "sa": 5, "su": 6}

    # Split alternatives by ';'
    parts = [p.strip() for p in s.split(";") if p.strip()]

    def parse_time(tstr):
        try:
            hh, mm = tstr.split(":")
            return time(int(hh), int(mm))
        except Exception:
            return None

    todays_matches = []
    for p in parts:
        # Example: 'Mo-Sa 09:00-18:00' or 'Su 10:00-16:00' or '09:00-18:00'
        tok = p.split()
        if len(tok) == 1 and "-" in tok[0] and ":" in tok[0]:
            # time only, applies every day
            days = list(range(0, 7))
            times = tok[0]
        elif len(tok) >= 2:
            daypart = tok[0]
            times = tok[1]
            days = []
            if "-" in daypart:
                a, b = daypart.split("-")
                a = a.lower()[:2]
                b = b.lower()[:2]
                if a in days_map and b in days_map:
                    ra = days_map[a]
                    rb = days_map[b]
                    if ra <= rb:
                        days = list(range(ra, rb + 1))
                    else:
                        days = list(range(ra, 7)) + list(range(0, rb + 1))
            else:
                # single day or comma-separated
                for d in daypart.split(","):
                    d = d.strip().lower()[:2]
                    if d in days_map:
                        days.append(days_map[d])
        else:
            continue

        if isinstance(times, str) and "-" in times:
            t1s, t2s = times.split("-", 1)
            t1 = parse_time(t1s)
            t2 = parse_time(t2s)
            if t1 and t2:
                if now.weekday() in days:
                    todays_matches.append((t1, t2))

    # Check if current time falls in any range
    for t1, t2 in todays_matches:
        dt = now.time()
        if t1 <= dt <= t2:
            return (True, None)
        # Handle overnight ranges (e.g., 18:00-02:00)
        elif t1 > t2:
            # range spans midnight
            if dt >= t1 or dt <= t2:
                return (True, None)

    return (False, None)


def calculate_search_radius(neighborhood_name, bbox):
    """Calculate appropriate search radius based on context"""
    if neighborhood_name:
        return 300  # Smaller radius for neighborhoods
    elif bbox:
        # Calculate radius based on bbox size
        bbox_width = abs(bbox[2] - bbox[0])
        bbox_height = abs(bbox[3] - bbox[1])
        avg_size = (bbox_width + bbox_height) / 2
        return min(int(avg_size * 50000), 800)  # Convert to meters, cap at 800m
    else:
        return 300  # Smaller default radius for cities to avoid timeouts


def get_country_for_city(city: str) -> Optional[str]:
    """Return country name for a given city using Nominatim (best-effort)."""
    if not city:
        return None
    try:
        import requests
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
        # Request results in English where possible to prefer ASCII country names
        headers = {"User-Agent": "city-guides-app", "Accept-Language": "en"}
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        if data:
            addr = data[0].get("address", {})
            country = addr.get("country")
            # prefer an ASCII/English country name when possible; Nominatim sometimes returns
            # the localized/native country name (e.g. '中国') which may not work with downstream
            # services. Use the display_name fallback to extract an English name if needed.
            if country:
                try:
                    # if country contains non-ascii characters, try to derive an English name
                    if any(ord(ch) > 127 for ch in country):
                        display = data[0].get("display_name", "") or ""
                        parts = [p.strip() for p in display.split(",") if p.strip()]
                        if parts:
                            # last part of display_name is usually the country in English
                            candidate = parts[-1]
                            if any(c.isalpha() for c in candidate):
                                return candidate
                except Exception:
                    pass
            # fallback to country or country_code
            return country or addr.get("country_code")
    except Exception:
        pass
    return None


def get_provider_links(city: str) -> list[Dict]:
    """Return a small list of provider links for UI deep-links (best-effort)."""
    if not city:
        return []
    try:
        import requests
        q = requests.utils.requote_uri(city)
    except Exception:
        q = city
    links = [
        {"name": "Google Maps", "url": f"https://www.google.com/maps/search/{q}"},
        {"name": "OpenStreetMap", "url": f"https://www.openstreetmap.org/search?query={q}"},
        {"name": "Wikivoyage", "url": f"https://en.wikivoyage.org/wiki/{city.replace(' ', '_')}"},
    ]
    return links


def shorten_place(city_name: str) -> str:
    """Shorten city name by taking first part before comma."""
    if not city_name:
        return city_name
    return city_name.split(',')[0].strip()


def get_currency_for_country(country: str) -> Optional[str]:
    """Return the primary currency code (ISO 4217) for a given country name using restcountries API."""
    if not country:
        return None
    try:
        import requests
        url = f"https://restcountries.com/v3.1/name/{requests.utils.requote_uri(country)}"
        resp = requests.get(
            url,
            params={"fields": "name,currencies"},
            headers={"User-Agent": "city-guides-app"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            # currencies is an object with codes as keys
            cur_obj = data[0].get("currencies") or {}
            if isinstance(cur_obj, dict) and cur_obj:
                # return first currency code
                for code in cur_obj.keys():
                    return code
    except Exception:
        pass
    return None


def get_currency_name(code: str) -> Optional[str]:
    """Return a human-friendly currency name for an ISO 4217 code."""
    if not code:
        return None
    code = code.strip().upper()
    names = {
        "USD": "US Dollar",
        "EUR": "Euro",
        "GBP": "Pound Sterling",
        "JPY": "Japanese Yen",
        "CAD": "Canadian Dollar",
        "AUD": "Australian Dollar",
        "MXN": "Mexican Peso",
        "CNY": "Chinese Yuan",
        "THB": "Thai Baht",
        "RUB": "Russian Ruble",
        "CUP": "Cuban Peso",
        "VES": "Venezuelan Bolívar",
        "KES": "Kenyan Shilling",
        "ZWL": "Zimbabwean Dollar",
        "PEN": "Peruvian Sol",
    }
    if code in names:
        return names[code]
    # try RestCountries API to resolve name
    try:
        import requests
        url = f"https://restcountries.com/v3.1/currency/{requests.utils.requote_uri(code)}"
        resp = requests.get(
            url,
            params={"fields": "name,currencies"},
            headers={"User-Agent": "city-guides-app"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            cur_obj = data[0].get("currencies") or {}
            # currencies is dict mapping code -> {name, symbol}
            if isinstance(cur_obj, dict) and code in cur_obj:
                info = cur_obj.get(code)
                if isinstance(info, dict):
                    return info.get("name") or info.get("symbol") or code
    except Exception:
        pass
    return code


def get_cost_estimates(city: str, ttl_seconds: Optional[int] = None) -> list[Dict]:
    """Fetch average local prices for a city using Teleport free API with caching."""
    if not city:
        return []

    if ttl_seconds is None:
        ttl_seconds = int(os.getenv("CACHE_TTL_TELEPORT", "86400"))

    try:
        cache_dir = Path(__file__).parent / ".cache" / "teleport_prices"
        cache_dir.mkdir(parents=True, exist_ok=True)
        import re
        key = re.sub(r"[^a-z0-9]+", "_", city.strip().lower())
        cache_file = cache_dir / f"{key}.json"
        # return cached if fresh
        if cache_file.exists():
            try:
                raw = json.loads(cache_file.read_text())
                if raw.get("ts") and time.time() - raw["ts"] < ttl_seconds:
                    return raw.get("data", [])
            except Exception:
                pass

        # Try Teleport search -> city item -> urban area -> prices
        base = "https://api.teleport.org"
        try:
            import requests
            s = requests.get(
                f"{base}/api/cities/",
                params={"search": city, "limit": 5},
                timeout=6,
                headers={"User-Agent": "city-guides-app"},
            )
            s.raise_for_status()
            j = s.json()
            results = j.get("_embedded", {}).get("city:search-results", [])
            city_item_href = None
            for r in results:
                href = r.get("_links", {}).get("city:item", {}).get("href")
                if href:
                    city_item_href = href
                    break
            if not city_item_href:
                raise RuntimeError("no city item from teleport")

            ci = requests.get(
                city_item_href, timeout=6, headers={"User-Agent": "city-guides-app"}
            )
            ci.raise_for_status()
            ci_j = ci.json()
            urban_href = ci_j.get("_links", {}).get("city:urban_area", {}).get("href")
            if not urban_href:
                # no urban area -> no prices available
                raise RuntimeError("no urban area")

            prices_href = urban_href.rstrip("/") + "/prices/"
            p = requests.get(
                prices_href, timeout=6, headers={"User-Agent": "city-guides-app"}
            )
            p.raise_for_status()
            p_j = p.json()

            items = []
            # Teleport responses typically include 'categories' -> each has 'data' list of items
            for cat in p_j.get("categories", []):
                for d in cat.get("data", []):
                    label = d.get("label") or d.get("id")
                    # find a numeric price in common keys
                    val = None
                    for k in (
                        "usd_value",
                        "currency_dollar_adjusted",
                        "price",
                        "amount",
                        "value",
                    ):
                        if k in d and isinstance(d[k], (int, float)):
                            val = float(d[k])
                            break
                    # some Teleport payloads nest price under 'prices' or similar
                    if val is None:
                        # try nested structures
                        for kk in d.keys():
                            vvv = d.get(kk)
                            if isinstance(vvv, (int, float)):
                                val = float(vvv)
                                break
                    if label and val is not None:
                        items.append({"label": label, "value": round(val, 2)})

            # prefer a short curated subset (coffee, beer, meal, taxi, hotel)
            keywords = ["coffee", "beer", "meal", "taxi", "hotel", "apartment", "rent"]
            selected = []
            lower_seen = set()
            for k in keywords:
                for it in items:
                    if (
                        k in it["label"].lower()
                        and it["label"].lower() not in lower_seen
                    ):
                        selected.append(it)
                        lower_seen.add(it["label"].lower())
                        break
            # if not selected, take first N items
            if not selected:
                selected = items[:8]

            # save cache
            try:
                cache_file.write_text(json.dumps({"ts": time.time(), "data": selected}))
            except Exception:
                pass
            return selected
        except Exception as e:
            logging.debug(f"Teleport fetch failed: {e}")
            # fall through to local fallback

        # Local fallback map keyed by country (best-effort)
        try:
            country = get_country_for_city(city) or ""
        except Exception:
            country = ""
        fb = {
            "china": [
                {"label": "Coffee (cafe)", "value": 20.0},
                {"label": "Local beer (0.5L)", "value": 12.0},
                {"label": "Meal (mid-range)", "value": 70.0},
                {"label": "Taxi start (local)", "value": 10.0},
                {"label": "Hotel (1 night, mid)", "value": 350.0},
            ],
            "russia": [
                {"label": "Coffee (cafe)", "value": 200.0},
                {"label": "Local beer (0.5L)", "value": 150.0},
                {"label": "Meal (mid-range)", "value": 700.0},
                {"label": "Taxi start (local)", "value": 100.0},
                {"label": "Hotel (1 night, mid)", "value": 4000.0},
            ],
            "cuba": [
                {"label": "Coffee (cafe)", "value": 50.0},
                {"label": "Local beer (0.5L)", "value": 60.0},
                {"label": "Meal (mid-range)", "value": 200.0},
                {"label": "Taxi (short)", "value": 80.0},
                {"label": "Hotel (1 night, mid)", "value": 2500.0},
            ],
            "portugal": [
                {"label": "Coffee (cafe)", "value": 1.6},
                {"label": "Local beer (0.5L)", "value": 2.0},
                {"label": "Meal (mid-range)", "value": 12.0},
                {"label": "Taxi start (local)", "value": 3.0},
                {"label": "Hotel (1 night, mid)", "value": 80.0},
            ],
            "united states": [
                {"label": "Coffee (cafe)", "value": 3.5},
                {"label": "Local beer (0.5L)", "value": 5.0},
                {"label": "Meal (mid-range)", "value": 20.0},
                {"label": "Taxi start (local)", "value": 3.0},
                {"label": "Hotel (1 night, mid)", "value": 140.0},
            ],
            "united kingdom": [
                {"label": "Coffee (cafe)", "value": 2.8},
                {"label": "Local beer (0.5L)", "value": 4.0},
                {"label": "Meal (mid-range)", "value": 15.0},
                {"label": "Taxi start (local)", "value": 3.5},
                {"label": "Hotel (1 night, mid)", "value": 120.0},
            ],
            "thailand": [
                {"label": "Coffee (cafe)", "value": 50.0},
                {"label": "Local beer (0.5L)", "value": 60.0},
                {"label": "Meal (mid-range)", "value": 250.0},
                {"label": "Taxi start (local)", "value": 35.0},
                {"label": "Hotel (1 night, mid)", "value": 1200.0},
            ],
        }
        lookup = (country or "").strip().lower()
        # sometimes country is a code; attempt to match common names
        for k in fb.keys():
            if k in lookup:
                try:
                    cache_file.write_text(
                        json.dumps({"ts": time.time(), "data": fb[k]})
                    )
                except Exception:
                    pass
                return fb[k]
        # nothing found
        return []
    except Exception:
        return []


def fetch_safety_section(city: str) -> list[str]:
    """Attempt to extract a 'Safety' or 'Crime' section from Wikivoyage or Wikipedia."""
    if not city:
        return []
    import requests
    import re
    
    keywords = [
        "safety",
        "crime",
        "security",
        "safety and security",
        "crime and safety",
    ]
    # Try Wikivoyage first, then Wikipedia
    sites = [
        ("https://en.wikivoyage.org/w/api.php"),
        ("https://en.wikipedia.org/w/api.php"),
    ]
    for api in sites:
        try:
            # fetch sections list
            params = {
                "action": "parse",
                "page": city,
                "prop": "sections",
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                api, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            data = resp.json()
            secs = data.get("parse", {}).get("sections", [])
            for s in secs:
                line = (s.get("line") or "").lower()
                for kw in keywords:
                    if kw in line:
                        idx = s.get("index")
                        # fetch that section's HTML and strip tags
                        params2 = {
                            "action": "parse",
                            "page": city,
                            "prop": "text",
                            "section": idx,
                            "format": "json",
                            "redirects": 1,
                        }
                        resp2 = requests.get(
                            api,
                            params=params2,
                            headers={"User-Agent": "TravelLand/1.0"},
                            timeout=8,
                        )
                        resp2.raise_for_status()
                        html = (
                            resp2.json().get("parse", {}).get("text", {}).get("*", "")
                        )
                        text = re.sub(r"<[^>]+>", "", html).strip()
                        if text:
                            return _sanitize_safety_text(text)
        except Exception:
            # ignore and try next source
            continue

    # Try plaintext extracts and look for paragraphs mentioning keywords
    try:
        for api in sites:
            params = {
                "action": "query",
                "prop": "extracts",
                "explaintext": True,
                "titles": city,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                api, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                extract = p.get("extract", "") or ""
                lower = extract.lower()
                for kw in keywords:
                    if kw in lower:
                        # try to return the paragraph containing the keyword
                        parts = re.split(r"\n\s*\n", extract)
                        for part in parts:
                            if kw in part.lower():
                                return _sanitize_safety_text(part.strip())
    except Exception:
        pass

    # Last resort: synthesise safety tips via semantic module
    try:
        import asyncio
        q = f"Provide 5 concise crime and safety tips for travelers in {city}. Include common scams, areas to avoid, and nighttime safety."
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio  # type: ignore
            nest_asyncio.apply()
            res = loop.run_until_complete(semantic.search_and_reason(q, city, mode="explorer"))
        else:
            res = loop.run_until_complete(semantic.search_and_reason(q, city, mode="explorer"))
        if isinstance(res, dict):
            out = str(res.get("answer") or res.get("text") or res)
        else:
            out = str(res)
        return _sanitize_safety_text(out)
    except Exception:
        return []


def _sanitize_safety_text(raw: str) -> list[str]:
    """Sanitize safety text: remove salutations/persona intros and return concise sentences (up to 5)."""
    if not raw:
        return []
    try:
        text = raw.strip()
        # remove common greetings at start
        text = re.sub(
            r"^(\s*(buon giorno|bonjour|hello|hi|dear|greetings)[^\n]*\n)+",
            "",
            text,
            flags=re.I,
        )
        # remove lines that mention 'Marco' as persona
        text = re.sub(r"(?im)^.*\bmarco\b.*$", "", text)
        # collapse multiple newlines
        text = re.sub(r"\n{2,}", "\n", text).strip()

        # split into sentences (rough)
        sentences = re.findall(r"[^\.\!\?]+[\.\!\?]+", text)
        if not sentences:
            # fallback to line splits
            sentences = [s.strip() for s in text.split("\n") if s.strip()]

        # find first advisory-like sentence
        advice_idx = 0
        adv_regex = re.compile(
            r"^(Be|Avoid|Don't|Do not|Keep|Watch|Stay|Avoiding|Use caution|Exercise|Carry|Keep)\b",
            re.I,
        )
        for i, s in enumerate(sentences):
            if adv_regex.search(s.strip()):
                advice_idx = i
                break

        # take up to 5 sentences from advice_idx; if advice_idx==0, still take first 5
        chosen = sentences[advice_idx : advice_idx + 5]
        # final cleanup: remove ordinal lists like '1.' at the start of a sentence
        clean = [re.sub(r"^\s*\d+\.\s*", "", s).strip() for s in chosen]
        return clean
    except Exception:
        return [raw[:1000]]


def fetch_us_state_advisory(country: str) -> Optional[Dict]:
    """Best-effort fetch of US State Dept travel advisory for a country."""
    if not country:
        return None
    # construct slug
    slug = country.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    urls = [
        f"https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/{slug}.html",
        f"https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/2020/{slug}.html",
    ]
    for u in urls:
        try:
            import requests
            resp = requests.get(u, headers={"User-Agent": "TravelLand/1.0"}, timeout=8)
            if resp.status_code != 200:
                continue
            html = resp.text
            # try meta description
            m = re.search(
                r'<meta\s+name="description"\s+content="([^"]+)"', html, flags=re.I
            )
            summary = None
            if m:
                summary = m.group(1).strip()
            else:
                # try to find first paragraph
                m2 = re.search(r"<p[^>]*>(.*?)</p>", html, flags=re.I | re.S)
                if m2:
                    summary = re.sub(r"<[^>]+>", "", m2.group(1)).strip()
            return {"url": u, "summary": summary}
        except Exception:
            continue
    return None


def get_weather(lat: float, lon: float) -> Optional[Dict]:
    """Fetch current weather for given latitude and longitude using Open-Meteo API."""
    if not lat or not lon:
        return None
    try:
        import requests
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "temperature_unit": "celsius",
            "windspeed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto",
        }
        resp = requests.get(url, params=params, timeout=6)
        resp.raise_for_status()
        data = resp.json().get("current_weather", {})
        return data
    except Exception:
        return None


def _fetch_image_from_website(url: str) -> Optional[str]:
    """Attempt to fetch an og:image or other image hint from a webpage."""
    try:
        import requests
        headers = {"User-Agent": "TravelLand/1.0"}
        resp = requests.get(url, headers=headers, timeout=4)
        resp.raise_for_status()
        html = resp.text
        # look for og:image
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r'<meta[^>]+name=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
        if not m:
            m = re.search(
                r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
        if m:
            img = m.group(1)
            # make absolute if needed
            try:
                p = urlparse(img)
                if not p.scheme:
                    base = urlparse(url)
                    img = f"{base.scheme}://{base.netloc}{img if img.startswith('/') else '/' + img}"
            except Exception:
                pass
            return img
    except Exception:
        return None


def _is_relevant_wikimedia_image(wik_img: Dict, city_name: str, neighborhood_name: str) -> bool:
    """Heuristic to decide if a Wikimedia banner image is relevant to the place."""
    if not wik_img:
        return False
    page_title = (wik_img.get('page_title') or '')
    remote = (wik_img.get('remote_url') or wik_img.get('url') or '')
    lower_title = page_title.lower()
    lower_remote = remote.lower()
    bad_terms = ['trophy', 'portrait', 'headshot', 'award', 'cup', 'ceremony', 'medal', 'singer', 'performing', 'performer', 'concert', 'festival', 'band', 'photo', 'photograph', 'portrait']
    good_terms = ['skyline', 'panorama', 'view', 'street', 'market', 'plaza', 'park', 'bridge', 'neighborhood', 'colonia', 'architecture', 'building']
    # Detect obvious person/performer pages by title patterns or keywords
    is_bad = any(b in lower_title for b in bad_terms) or any(b in lower_remote for b in bad_terms)
    is_performer_name = False
    # If page title contains two capitalized words (likely a person's name) and doesn't mention the city, treat as performer-like
    if page_title and sum(1 for w in page_title.split() if w and w[0].isupper()) >= 2 and (city_name.lower() not in lower_title):
        is_performer_name = True
    is_good = any(g in lower_title for g in good_terms) or any(g in lower_remote for g in good_terms) or (city_name.lower() in lower_title)
    if (is_bad or is_performer_name) and not is_good:
        return False
    return True


def _search_impl(payload):
    """Core search implementation with real provider integrations"""
    print(f"[SEARCH DEBUG] _search_impl called with payload: {payload}")
    
    city_input = (payload.get("query") or "").strip()
    city = city_input
    if not city:
        return {"error": "City not found or invalid", "debug_info": {"city_input": city_input}}
    
    try:
        limit = int(payload.get('limit', 10))
    except Exception:
        limit = 10
    
    q = (payload.get("category") or payload.get("intent") or "").strip().lower()
    neighborhood = payload.get("neighborhood")
    
    # Initialize result structure
    result = {
        "venues": [],
        "quick_guide": "",
        "summary": "",
        "city": city,
        "category": q,
        "neighborhood": neighborhood,
        "debug_info": {
            "city": city,
            "category": q,
            "neighborhood": neighborhood,
            "limit": limit
        }
    }
    
    # Import providers here to avoid circular imports
    wikipedia_search = None
    mapillary_search = None
    try:
        from city_guides.providers import multi_provider
        print("[SEARCH DEBUG] Successfully imported multi_provider")
    except Exception as e:
        print(f"[SEARCH DEBUG] Failed to import multi_provider: {e}")
        result["debug_info"]["multi_provider_error"] = str(e)
        return result
    
    # Try to import Wikipedia provider, but don't fail if it's not available
    try:
        import aiohttp
        wikipedia_search = True  # We'll implement our own simple Wikipedia fetch
        print("[SEARCH DEBUG] Wikipedia support available")
    except Exception as e:
        print(f"[SEARCH DEBUG] Wikipedia not available: {e}")
        result["debug_info"]["wikipedia_warning"] = str(e)
        # Continue without Wikipedia
    
    # Try to import image providers for city and venue images
    try:
        from city_guides.providers.image_provider import get_banner_for_city
        city_image_search = get_banner_for_city
        print("[SEARCH DEBUG] City image provider available")
    except Exception as e:
        print(f"[SEARCH DEBUG] City image provider not available: {e}")
        city_image_search = None
    
    # Try to import Mapillary for venue images
    try:
        from city_guides.providers.mapillary_provider import async_search_images_near
        mapillary_search = async_search_images_near
        print("[SEARCH DEBUG] Mapillary support available")
    except Exception as e:
        print(f"[SEARCH DEBUG] Mapillary not available: {e}")
        result["debug_info"]["mapillary_warning"] = str(e)
        # Continue without Mapillary
    
    try:
        from city_guides.providers.geocoding import geocode_city
        print("[SEARCH DEBUG] Successfully imported geocode_city")
    except Exception as e:
        print(f"[SEARCH DEBUG] Failed to import geocode_city: {e}")
        result["debug_info"]["geocoding_error"] = str(e)
        return result
    
    import asyncio
    print("[SEARCH DEBUG] Successfully imported asyncio")
    
    # Get city coordinates for bbox-based searches
    city_coords = None
    bbox = None
    
    try:
        # Try to geocode the city
        print(f"[SEARCH DEBUG] Geocoding city: {city}")
        # geocode_city returns a coroutine, so we need to run it in an event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            city_coords = loop.run_until_complete(geocode_city(city))
            if city_coords:
                print(f"[SEARCH DEBUG] City coordinates: {city_coords}")
                bbox = [
                    city_coords.get('lon', 0) - 0.05,  # min_lon
                    city_coords.get('lat', 0) - 0.05,  # min_lat  
                    city_coords.get('lon', 0) + 0.05,  # max_lon
                    city_coords.get('lat', 0) + 0.05   # max_lat
                ]
                result["debug_info"]["city_coords"] = city_coords
                result["debug_info"]["bbox"] = bbox
            else:
                print("[SEARCH DEBUG] Failed to geocode city")
        finally:
            loop.close()
    except Exception as e:
        print(f"[SEARCH DEBUG] Geocoding error: {e}")
        result["debug_info"]["geocoding_error"] = str(e)
    
    # Search for venues using multi_provider ONLY if user specified a category
    # If no category, just return city guide without venues
    if q:
        try:
            print(f"[SEARCH DEBUG] Searching for venues with category: {q}")
            
            # Map common categories to POI types
            poi_type = "restaurant"  # default
            category_mapping = {
                "food": "restaurant",
                "restaurants": "restaurant",
                "dining": "restaurant",
                "hotel": "hotel",
                "hotels": "hotel",
                "accommodation": "hotel",
                "attractions": "tourism",
                "attraction": "tourism",
                "sights": "tourism",
                "historic": "historic",
                "historic sites": "historic",
                "historical": "historic",
                "culture": "museum",
                "art": "museum",
                "museum": "museum",
                "museums": "museum",
                "nature": "park",
                "park": "park",
                "parks": "park",
                "garden": "park",
                "gardens": "park",
                "shopping": "shop",
                "shops": "shop",
                "nightlife": "bar",
                "entertainment": "amenity",
                "public transport": "amenity",
                "transport": "amenity",
                "transit": "amenity"
            }
            poi_type = category_mapping.get(q, q)
            
            print(f"[SEARCH DEBUG] Mapped category '{q}' to POI type '{poi_type}'")
            
            # Use asyncio to run the async discovery
            async def get_venues_with_images():
                print(f"[SEARCH DEBUG] Calling multi_provider with poi_type: {poi_type}")
                venues = await multi_provider.async_discover_pois(
                    city=city,
                    poi_type=poi_type,
                    limit=limit,
                    bbox=bbox,
                    timeout=10.0
                )
                print(f"[SEARCH DEBUG] multi_provider returned {len(venues)} venues")
                
                # Format venues for response and add images
                formatted_venues = []
                for venue in venues[:limit]:
                    # Apply Chinese venue processing first
                    venue = enhance_chinese_venue_processing(venue)
                    # First try venue's native address
                    address = venue.get("address", "")
                    lat = venue.get("lat")
                    lon = venue.get("lon")
                    
                    # Skip venues with no address or coordinates
                    if not address and (not lat or not lon):
                        print(f"[SEARCH DEBUG] Skipping venue '{venue.get('name', 'Unknown')}' - no address or coordinates")
                        continue
                    
                    # Check if address is just coordinates (e.g., "48.8449, 2.3487")
                    import re
                    is_coordinate_only = False
                    if address and re.match(r'^\s*-?\d+\.?\d*\s*,\s*-?\d+\.?\d*\s*$', address.strip()):
                        is_coordinate_only = True
                    
                    # If no address or coordinate-only, try reverse geocoding
                    if not address or is_coordinate_only:
                        if lat and lon:
                            try:
                                from city_guides.providers.geocoding import reverse_geocode
                                print(f"[SEARCH DEBUG] Reverse geocoding '{venue.get('name', 'Unknown')}' at {lat}, {lon}")
                                geocoded_address = await reverse_geocode(float(lat), float(lon))
                                if geocoded_address:
                                    address = geocoded_address
                                    print(f"[SEARCH DEBUG] Got address: {address[:50]}...")
                                else:
                                    print(f"[SEARCH DEBUG] Reverse geocoding failed for '{venue.get('name', 'Unknown')}'")
                                    continue
                            except Exception as e:
                                print(f"[SEARCH DEBUG] Reverse geocoding error for '{venue.get('name', 'Unknown')}': {e}")
                                continue
                        else:
                            print(f"[SEARCH DEBUG] Skipping venue '{venue.get('name', 'Unknown')}' - no coordinates for reverse geocoding")
                            continue
                    
                    # Standardize address presentation
                    if not address.startswith("📍"):
                        address = f"📍 {address}"
                    
                    # Enrich venue with human-readable context
                    enriched_data = enrich_venue_data(venue, city)
                    
                    formatted_venue = {
                        "id": venue.get("id", ""),
                        "name": venue.get("name", ""),
                        "address": address,
                        "description": enriched_data.get("description", ""),
                        "venue_type": enriched_data.get("venue_type", ""),
                        "cuisine": enriched_data.get("cuisine", ""),
                        "price_level": enriched_data.get("price_level", ""),
                        "price_indicator": enriched_data.get("price_indicator", ""),
                        "features": enriched_data.get("features", []),
                        "opening_hours": enriched_data.get("opening_hours"),
                        "phone": enriched_data.get("phone"),
                        "lat": venue.get("lat"),
                        "lon": venue.get("lon"),
                        "provider": venue.get("provider", ""),
                        "tags": venue.get("tags", {}),
                        "osm_url": venue.get("osm_url", ""),
                        "website": venue.get("website", "")
                    }
                    
                    # Add images if Mapillary is available and venue has coordinates
                    if mapillary_search and formatted_venue.get("lat") and formatted_venue.get("lon"):
                        try:
                            images = await mapillary_search(
                                lat=formatted_venue["lat"],
                                lon=formatted_venue["lon"],
                                radius_m=50,
                                limit=2
                            )
                            if images:
                                formatted_venue["images"] = [
                                    {
                                        "id": img.get("id"),
                                        "url": img.get("url"),
                                        "lat": img.get("lat"),
                                        "lon": img.get("lon")
                                    }
                                    for img in images
                                ]
                        except Exception as e:
                            print(f"[SEARCH DEBUG] Mapillary error: {e}")
                    
                    formatted_venues.append(formatted_venue)
                
                return formatted_venues
                
            # Run in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                formatted_venues = loop.run_until_complete(get_venues_with_images())
                print(f"[SEARCH DEBUG] Found {len(formatted_venues)} venues")
                
                # Filter for public transport venues if category is public transport
                if q == "public transport":
                    transport_venues = []
                    for venue in formatted_venues:
                        tags_str = venue.get("tags", "")
                        # Check if the tags string contains transport-related keywords
                        if "railway" in tags_str or "station" in tags_str or "bus_station" in tags_str or "ferry_terminal" in tags_str or "public_transport" in tags_str:
                            transport_venues.append(venue)
                    result["venues"] = transport_venues
                    print(f"[SEARCH DEBUG] Filtered to {len(transport_venues)} transport venues")
                elif q == "shopping":
                    # Filter for shopping venues - shops, boutiques, malls
                    shopping_venues = []
                    for venue in formatted_venues:
                        tags = venue.get("tags", {})
                        tags_str = str(tags).lower()
                        # Check for shop-related tags and exclude food
                        is_shop = any(keyword in tags_str for keyword in ["shop=", "boutique", "mall", "store", "retail"])
                        is_food = any(keyword in tags_str for keyword in ["restaurant", "cafe", "food", "cuisine", "couscous", "kitchen"])
                        if is_shop and not is_food:
                            shopping_venues.append(venue)
                    result["venues"] = shopping_venues
                    print(f"[SEARCH DEBUG] Filtered to {len(shopping_venues)} shopping venues")
                elif q == "nightlife":
                    # Filter for nightlife venues - bars, pubs, clubs, lounges
                    nightlife_venues = []
                    for venue in formatted_venues:
                        tags = venue.get("tags", {})
                        tags_str = str(tags).lower()
                        name = venue.get("name", "").lower()
                        
                        # STRICT filtering - exclude obvious non-nightlife
                        excluded_types = [
                            "library", "bookcase", "education.library", "public_bookcase",
                            "employment", "government", "office", "administration",
                            "social_facility", "community_centre", "townhall",
                            "embassy", "consulate", "courthouse", "police",
                            "post_office", "bank", "atm", "clinic", "hospital"
                        ]
                        if any(bad in tags_str for bad in excluded_types):
                            continue
                        
                        # Must have explicit nightlife amenity tags
                        nightlife_amenities = [
                            "amenity=bar", "amenity=pub", "amenity=nightclub",
                            "amenity=biergarten", "amenity=stripclub",
                            "bar=yes", "pub=yes"
                        ]
                        has_nightlife_amenity = any(tag in tags_str for tag in nightlife_amenities)
                        
                        # OR have strong name indicators + beverage keywords
                        strong_name_indicators = [
                            "bar", "pub", "tavern", "biergarten", "brewery",
                            "cocktail", "lounge", "club"
                        ]
                        has_strong_name = any(ind in name for ind in strong_name_indicators)
                        
                        # Require amenity tag OR (strong name + not excluded)
                        if has_nightlife_amenity or (has_strong_name and not any(bad in name for bad in ["library", "office", "employment", "government"])):
                            # Additional check: must have beverage/entertainment related tags
                            beverage_keywords = ["bar", "pub", "biergarten", "cocktail", "beer", "wine", "drinks", "nightclub", "club", "lounge"]
                            if any(kw in tags_str for kw in beverage_keywords):
                                nightlife_venues.append(venue)
                    
                    result["venues"] = nightlife_venues
                    print(f"[SEARCH DEBUG] Filtered to {len(nightlife_venues)} nightlife venues (strict mode)")
                elif q in ["historic", "historic sites"]:
                    # Filter for actual historic sites - monuments, museums, castles, etc.
                    historic_venues = []
                    for venue in formatted_venues:
                        tags = venue.get("tags", {})
                        tags_str = str(tags).lower()
                        name = venue.get("name", "").lower()
                        
                        # STRICT filtering - must have actual historic/tourism tags
                        historic_indicators = [
                            "historic", "monument", "memorial", "castle", "palace",
                            "museum", "gallery", "cathedral", "church", "temple",
                            "ruins", "archaeological", "heritage", "landmark",
                            "tourism=attraction", "tourism=museum", "tourism=gallery",
                            "building=cathedral", "building=church", "building=castle",
                            "historic=monument", "historic=castle", "historic=ruins"
                        ]
                        
                        # Must have at least one historic indicator
                        has_historic = any(ind in tags_str for ind in historic_indicators)
                        
                        # Exclude garbage like traffic signs, construction, random shops
                        garbage_indicators = [
                            "traffic", "sign", "construction", "speed limit",
                            "kebab", "burger", "fast food", "driveway", "parking",
                            "regulatory", "maxspeed", "construction--"
                        ]
                        is_garbage = any(garb in name or garb in tags_str for garb in garbage_indicators)
                        
                        if has_historic and not is_garbage:
                            historic_venues.append(venue)
                    
                    result["venues"] = historic_venues
                    print(f"[SEARCH DEBUG] Filtered to {len(historic_venues)} historic venues (strict mode)")
                else:
                    result["venues"] = formatted_venues
                
                # Apply venue quality filtering
                # Use a lower threshold for neighborhood searches to avoid over-filtering
                try:
                    from city_guides.src.venue_quality import MINIMUM_QUALITY_SCORE
                except Exception:
                    from venue_quality import MINIMUM_QUALITY_SCORE

                threshold = MINIMUM_QUALITY_SCORE
                # If a neighborhood is specified, be slightly more permissive
                if neighborhood:
                    threshold = min(threshold, 0.6)  # lower to 0.6 for neighborhood-level searches

                # Filter using the selected threshold
                high_quality_venues = filter_high_quality_venues(result["venues"], min_score=threshold)
                result["debug_info"]["quality_filtered"] = len(result["venues"]) - len(high_quality_venues)

                # Fallback: if too few venues remain, include top-scoring remaining venues until we reach MIN_VENUES
                MIN_VENUES = 5
                fallback_included = False
                if len(high_quality_venues) < MIN_VENUES:
                    # Ensure quality scores exist for all venues
                    for v in result["venues"]:
                        if 'quality_score' not in v:
                            v['quality_score'] = calculate_venue_quality_score(v)

                    existing_ids = set(v.get('id') for v in high_quality_venues)
                    remaining = [v for v in result["venues"] if v.get('id') not in existing_ids]
                    remaining_sorted = sorted(remaining, key=lambda x: x.get('quality_score', 0), reverse=True)

                    to_add = []
                    for v in remaining_sorted:
                        if len(high_quality_venues) + len(to_add) >= MIN_VENUES:
                            break
                        to_add.append(v)

                    if to_add:
                        fallback_included = True
                        high_quality_venues.extend(to_add)
                        result["debug_info"]["fallback_included"] = True
                        result["debug_info"]["fallback_added"] = [ {"id": v.get("id"), "name": v.get("name"), "quality_score": v.get("quality_score")} for v in to_add ]

                result["venues"] = high_quality_venues
                result["debug_info"]["venues_found"] = len(result["venues"])
                
            finally:
                loop.close()
                
        except Exception as e:
            print(f"[SEARCH DEBUG] Venue search error: {e}")
            result["debug_info"]["venue_search_error"] = str(e)
    else:
        print("[SEARCH DEBUG] No category specified, skipping venue search - will return city guide only")
    
    # Generate quick guide using Wikipedia for CITY-level searches only
    # Neighborhood searches should use the existing /generate_quick_guide endpoint
    if wikipedia_search and not neighborhood and city:
        try:
            print(f"[SEARCH DEBUG] Generating city-wide Wikipedia quick guide for {city}")
            
            async def get_city_guide():
                # Simple Wikipedia API call with proper User-Agent
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{city.replace(' ', '_')}"
                headers = {"User-Agent": "TravelLand/1.0 (travel-guide-app; https://github.com/example/travelland)"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            extract = data.get('extract')
                            if extract:
                                # Add city image if available
                                city_image = None
                                if city_image_search:
                                    try:
                                        image_info = await city_image_search(city, session=session)
                                        if image_info and image_info.get('image_url'):
                                            city_image = {
                                                'url': image_info['image_url'],
                                                'attribution': image_info.get('attribution'),
                                                'source': 'wikipedia'
                                            }
                                    except Exception as e:
                                        print(f"[SEARCH DEBUG] Failed to fetch city image: {e}")
                                
                                return {
                                    'guide': extract,
                                    'image': city_image
                                }
                        return None
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                city_guide_result = loop.run_until_complete(get_city_guide())
                if city_guide_result:
                    result["quick_guide"] = city_guide_result['guide']
                    if city_guide_result.get('image'):
                        result["city_image"] = city_guide_result['image']
                    result["source"] = "wikipedia_city"
                    print("[SEARCH DEBUG] Generated city-wide quick guide using Wikipedia")
                else:
                    print("[SEARCH DEBUG] No Wikipedia results for city")
            finally:
                loop.close()
                
        except Exception as e:
            print(f"[SEARCH DEBUG] Wikipedia city guide generation error: {e}")
            result["debug_info"]["city_guide_error"] = str(e)
    elif neighborhood:
        print(f"[SEARCH DEBUG] Neighborhood specified ({neighborhood}), skipping city-level Wikipedia guide (will use /generate_quick_guide endpoint)")
    else:
        print("[SEARCH DEBUG] Wikipedia not available or no city specified, skipping quick guide generation")
    
    print(f"[SEARCH DEBUG] Final result: {len(result.get('venues', []))} venues, quick_guide: {bool(result.get('quick_guide'))}")
    return result


# Re-export key functions for backward compatibility
__all__ = [
    '_persist_quick_guide',
    'build_search_cache_key',
    'ensure_bbox',
    'format_venue',
    'determine_budget',
    'determine_price_range',
    'generate_description',
    'enrich_venue_data',
    'format_venue_for_display',
    '_humanize_opening_hours',
    '_compute_open_now',
    'calculate_search_radius',
    'get_country_for_city',
    'get_provider_links',
    'shorten_place',
    'get_currency_for_country',
    'get_currency_name',
    'get_cost_estimates',
    'fetch_safety_section',
    'fetch_us_state_advisory',
    'get_weather',
    '_fetch_image_from_website',
    '_is_relevant_wikimedia_image',
    '_search_impl'
]