# Compatibility shim for older imports that expect top-level `providers` package
# Re-export modules from the canonical `city_guides.providers` package.
from city_guides.providers import (
    multi_provider,
    overpass_provider,
    search_provider,
    ddgs_provider,
    geonames_provider,
    neighborhood_suggestions,
    image_provider,
)

__all__ = [
    'multi_provider',
    'overpass_provider',
    'search_provider',
    'ddgs_provider',
    'geonames_provider',
    'neighborhood_suggestions',
    'image_provider',
]
