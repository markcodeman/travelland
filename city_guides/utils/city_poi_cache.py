"""City POI Caching System

Caches discovered POIs from APIs (TomTom, Wikidata, Overpass) to JSON files.
Provides fallback when live APIs fail or rate limited.

Governance (per AGENTS.md Controlled Seed Data rules):
- All cached data stored in versioned JSON files
- Metadata includes: source, version, last_updated, refresh_path
- Used only as fallback when dynamic providers fail
- All fallback usage is logged for audit
- Refresh script available to regenerate from live APIs
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# Cache directory for city POIs
CACHE_DIR = Path(__file__).parent.parent / "data" / "city_poi_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache version for schema tracking
CACHE_VERSION = "1.0.0"


def get_cache_path(city: str) -> Path:
    """Get cache file path for a city."""
    safe_city = city.lower().replace(" ", "_").replace(",", "").replace(".", "")
    return CACHE_DIR / f"{safe_city}_pois.json"


def save_city_pois(city: str, pois: List[Dict[str, Any]], sources: List[str]) -> None:
    """Save discovered POIs to cache file with metadata.
    
    Args:
        city: City name
        pois: List of POI dictionaries
        sources: List of source names (e.g., ["tomtom", "wikidata"])
    """
    if not pois:
        logging.warning(f"[CACHE] No POIs to save for {city}")
        return
    
    cache_data = {
        "metadata": {
            "city": city,
            "version": CACHE_VERSION,
            "source": "seed",
            "sources": sources,
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "count": len(pois),
            "refresh_path": "scripts/refresh_city_cache.py",
            "governance": "Controlled Seed Data - AGENTS.md compliant"
        },
        "pois": pois
    }
    
    cache_path = get_cache_path(city)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        logging.info(f"[CACHE] Saved {len(pois)} POIs for {city} to {cache_path}")
    except Exception as e:
        logging.error(f"[CACHE] Failed to save cache for {city}: {e}")


def load_city_pois(city: str, max_age_days: int = 30) -> Optional[List[Dict[str, Any]]]:
    """Load cached POIs for a city if available and not stale.
    
    Args:
        city: City name
        max_age_days: Maximum age of cache in days
        
    Returns:
        List of POIs or None if no valid cache
    """
    cache_path = get_cache_path(city)
    
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # Validate metadata
        metadata = cache_data.get("metadata", {})
        if metadata.get("version") != CACHE_VERSION:
            logging.warning(f"[CACHE] Version mismatch for {city}, ignoring cache")
            return None
        
        # Check age
        last_updated = metadata.get("last_updated", "")
        if last_updated:
            updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            age_days = (datetime.utcnow() - updated_dt.replace(tzinfo=None)).days
            if age_days > max_age_days:
                logging.info(f"[CACHE] Cache for {city} is {age_days} days old, treating as stale")
                return None
        
        pois = cache_data.get("pois", [])
        sources = metadata.get("sources", ["unknown"])
        
        logging.info(f"[CACHE] Loaded {len(pois)} POIs for {city} from cache (sources: {sources})")
        return pois
        
    except Exception as e:
        logging.error(f"[CACHE] Failed to load cache for {city}: {e}")
        return None


def clear_city_cache(city: str) -> bool:
    """Clear cache for a specific city.
    
    Args:
        city: City name
        
    Returns:
        True if cache was cleared, False otherwise
    """
    cache_path = get_cache_path(city)
    if cache_path.exists():
        try:
            cache_path.unlink()
            logging.info(f"[CACHE] Cleared cache for {city}")
            return True
        except Exception as e:
            logging.error(f"[CACHE] Failed to clear cache for {city}: {e}")
            return False
    return False


def list_cached_cities() -> List[str]:
    """List all cities with cached POI data.
    
    Returns:
        List of city names
    """
    cities = []
    for cache_file in CACHE_DIR.glob("*_pois.json"):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                city = data.get("metadata", {}).get("city")
                if city:
                    cities.append(city)
        except:
            pass
    return sorted(cities)


def get_cache_stats() -> Dict[str, Any]:
    """Get statistics about the POI cache.
    
    Returns:
        Dictionary with cache statistics
    """
    stats = {
        "total_cities": 0,
        "total_pois": 0,
        "oldest_cache": None,
        "newest_cache": None,
        "cities": []
    }
    
    for cache_file in CACHE_DIR.glob("*_pois.json"):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metadata = data.get("metadata", {})
            city = metadata.get("city", "unknown")
            count = metadata.get("count", 0)
            last_updated = metadata.get("last_updated", "")
            
            stats["total_cities"] += 1
            stats["total_pois"] += count
            stats["cities"].append({
                "city": city,
                "count": count,
                "last_updated": last_updated
            })
            
        except:
            pass
    
    return stats
