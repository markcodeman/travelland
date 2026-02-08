# TravelLand Routes Module

## Overview

This directory contains modularized API routes extracted from the monolithic `app.py`. Each module uses Quart's Blueprint pattern for clean separation of concerns.

## Structure

```
routes/
├── __init__.py          # Blueprint registration system
├── README.md            # This file
├── admin.py             # Health, metrics, smoke tests
├── media.py             # External media API integrations
├── utils.py             # Utility endpoints (weather, synthesis, logging)
├── poi.py               # Points of Interest (fun facts, dream parsing)
├── search.py            # Main venue search endpoint
├── chat.py              # RAG chat with Marco AI
├── locations.py         # Location services (geocoding, states, cities)
├── suggestions.py       # Location suggestion autocomplete
├── guide.py             # Neighborhood guides and quick guides
└── frontend.py          # Static file serving for React app
```

## Blueprint Pattern

Each route module follows this pattern:

```python
"""
Module description
"""
from quart import Blueprint, request, jsonify

# Import dependencies
from city_guides.src.services.xyz import some_service

# Create blueprint
bp = Blueprint('module_name', __name__)

@bp.route('/api/endpoint', methods=['POST'])
async def handler():
    """Handler docstring"""
    # Implementation
    pass

def register(app):
    """Register blueprint with app"""
    app.register_blueprint(bp)
```

## Extraction Guidelines

1. **Preserve Imports**: Copy all necessary imports from app.py
2. **Maintain Signatures**: Keep route paths, methods, and function signatures identical
3. **Include Docstrings**: Preserve existing docstrings for API documentation
4. **Error Handling**: Keep try/except blocks and error responses
5. **Async/Await**: Maintain async patterns for all routes
6. **Dependencies**: Import from app.py globals (redis_client, aiohttp_session, etc.) as needed

## Route Categories

### Admin Routes (admin.py)
- `/healthz` - Health check
- `/metrics/json` - Metrics endpoint
- `/smoke` - Smoke test

### Media Routes (media.py)
- `/api/unsplash-search` - Unsplash image search
- `/api/pixabay-search` - Pixabay image search

### Utils Routes (utils.py)
- `/api/weather` - Weather data
- `/api/synthesize` - Text synthesis
- `/api/log-suggestion-success` - Success logging

### POI Routes (poi.py)
- `/api/fun-fact` - City fun facts
- `/api/parse-dream` - Dream destination parsing

### Search Routes (search.py)
- `/search` - Main venue search

### Chat Routes (chat.py)
- `/api/chat/rag` - RAG-powered chat with Marco

### Locations Routes (locations.py)
- `/api/countries` - Country list
- `/api/neighborhoods/<country_code>` - Neighborhoods by country
- `/api/locations/states` - State/region list
- `/api/locations/cities` - City list
- `/api/locations/neighborhoods` - Neighborhood list
- `/api/geocode` - Geocoding service
- `/api/geonames-search` - GeoNames search

### Suggestions Routes (suggestions.py)
- `/api/location-suggestions` - Autocomplete suggestions

### Guide Routes (guide.py)
- `/api/neighborhoods` - Get neighborhoods for location
- `/api/reverse_lookup` - Reverse geocode
- `/api/smart-neighborhoods` - Smart neighborhood detection
- `/api/generate_quick_guide` - Generate city quick guide

### Frontend Routes (frontend.py)
- `/` - Serve React app
- `/<path:path>` - Client-side routing catch-all

## Testing

After extraction:
1. Start the server: `python -m city_guides.src.app`
2. Test each endpoint with curl or Postman
3. Verify responses match original behavior
4. Check logs for errors

## Integration

Routes are registered in `routes/__init__.py` via the `register_blueprints()` function, called from `app.py`:

```python
from city_guides.src.routes import register_blueprints
register_blueprints(app)
```
