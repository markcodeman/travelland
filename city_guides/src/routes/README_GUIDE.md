# Guide Routes Module

## Overview
This module contains 4 guide-related routes extracted from `app.py` for modular organization.

## File
`city_guides/src/routes/guide.py` (1620 lines)

## Routes

### 1. GET /api/neighborhoods
- **Purpose**: Get neighborhoods for a city or location
- **Query params**: `city`, `lat`, `lon`, `lang`
- **Returns**: `{ cached: bool, neighborhoods: [] }`
- **Features**: Geocoding fallback, Redis caching, timeout handling

### 2. POST /api/reverse_lookup
- **Purpose**: Reverse geocode coordinates to structured location info
- **Payload**: `{ lat: number, lon: number }`
- **Returns**: `{ display_name, countryName, countryCode, stateName, cityName, neighborhoods: [] }`
- **Features**: Geoapify + Nominatim fallback, debug mode

### 3. GET /api/smart-neighborhoods
- **Purpose**: Get smart neighborhood suggestions for any city
- **Query params**: `city`, `category` (optional)
- **Returns**: `{ is_large_city: bool, neighborhoods: [], source: 'seed'|'overpass' }`
- **Features**: Seed data priority, Overpass API fallback, Redis caching

### 4. POST /api/generate_quick_guide
- **Purpose**: Generate neighborhood quick guide using Wikipedia and DDGS
- **Payload**: `{ city: string, neighborhood: string }`
- **Returns**: `{ quick_guide: string, source: string, cached: bool, confidence: string }`
- **Features**: Multi-source (Wikipedia, DDGS, synthesis), image enrichment, tone neutralization

## Usage

### Registering the Blueprint

```python
from city_guides.src.routes.guide import register_blueprint

# In your main app setup:
register_blueprint(app, aiohttp_session, redis_client)
```

### Blueprint Design
- **Name**: `'guide'`
- **Shared Resources**: Accessed via blueprint attributes
  - `guide.aiohttp_session`
  - `guide.redis_client`

## Dependencies
- Standard library: `sys`, `pathlib`, `os`, `asyncio`, `json`, `hashlib`, `re`, `time`, `typing`
- Quart: `Blueprint`, `request`, `jsonify`, `current_app`
- aiohttp: `aiohttp`, `ClientTimeout`
- city_guides modules: providers, services, persistence, utils

## Helper Functions
- `_is_content_sparse_or_low_quality(content, neighborhood, city)` - Quality check for generated content
- `_get_countries()` - Fetch country list from GeoNames or fallback

## Notes
- All routes use async/await patterns
- Redis caching is optional (checks for `redis_client` availability)
- DDGS search integration with fallback stubs
- Comprehensive error handling and logging throughout
