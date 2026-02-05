"""
Configuration module for TravelLand application
Centralizes all configuration constants and provides validation
"""

import os
from typing import Dict, Optional

# Cache TTL constants (in seconds)
CACHE_TTL_TELEPORT = int(os.getenv("CACHE_TTL_TELEPORT", "86400"))  # 24 hours
CACHE_TTL_RAG = int(os.getenv("RAG_CACHE_TTL", "21600"))  # 6 hours
CACHE_TTL_NEIGHBORHOOD = int(os.getenv("NEIGHBORHOOD_CACHE_TTL", "604800"))  # 7 days
CACHE_TTL_SEARCH = int(os.getenv("SEARCH_CACHE_TTL", "3600"))  # 1 hour

# API timeout constants
DDGS_TIMEOUT = float(os.getenv("DDGS_TIMEOUT", "5.0"))
GROQ_TIMEOUT = int(os.getenv("GROQ_CHAT_TIMEOUT", "10"))
GEOCODING_TIMEOUT = float(os.getenv("GEOCODING_TIMEOUT", "5.0"))

# Concurrency limits
DDGS_CONCURRENCY = int(os.getenv("DDGS_CONCURRENCY", "3"))
PREWARM_RAG_CONCURRENCY = int(os.getenv("PREWARM_RAG_CONCURRENCY", "4"))

# Feature flags
DISABLE_PREWARM = os.getenv("DISABLE_PREWARM", "false").lower() == "true"
VERBOSE_OPEN_HOURS = os.getenv("VERBOSE_OPEN_HOURS", "false").lower() == "true"

# Default values
DEFAULT_PREWARM_CITIES = os.getenv("SEARCH_PREWARM_CITIES", "London,Paris").split(",")
DEFAULT_PREWARM_QUERIES = [q.strip() for q in os.getenv("SEARCH_PREWARM_QUERIES", "Top food").split(",") if q.strip()]
POPULAR_CITIES = [c.strip() for c in os.getenv("POPULAR_CITIES", "London,Paris,New York,Tokyo,Rome,Barcelona,Bruges,Hallstatt,Chefchaouen,Ravello,Colmar,Sintra,Ghent,Annecy,Kotor,Cesky Krumlov,Rothenburg,Positano").split(",") if c.strip()]

# Validation function
def validate_config() -> Dict[str, Optional[str]]:
    """Validate configuration and return any issues found"""
    issues = {}

    # Check required API keys
    required_keys = {
        "GEOAPIFY_API_KEY": "Geoapify API key is required for geocoding",
        "GEONAMES_USERNAME": "GeoNames username is required for location data"
    }

    for key, message in required_keys.items():
        if not os.getenv(key):
            issues[key] = message

    # Check Redis configuration
    if not os.getenv("REDIS_URL"):
        issues["REDIS_URL"] = "Redis URL is required for caching"

    return issues