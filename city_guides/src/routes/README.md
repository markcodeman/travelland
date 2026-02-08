# Route Extraction Guide

## Overview
This directory contains all API routes extracted from `app.py` to achieve:
- Files under 1000 lines (ideal: 500-800)
- Clear separation of concerns
- Easier testing and maintenance

## Structure

```
city_guides/src/routes/
├── __init__.py      # Central registration function
├── chat.py          # /api/chat/rag
├── search.py        # /api/search, /api/categories
├── locations.py     # /api/geocode, /api/reverse_lookup, etc.
├── poi.py           # /api/poi-discovery, /api/smart-neighborhoods
├── media.py         # /api/unsplash-search, /api/pixabay-search
├── guide.py         # /api/generate_quick_guide, /api/fun-fact
├── admin.py         # /admin, /api/health
└── utils.py         # /api/parse-dream, /api/location-suggestions
```

## Template for Route Modules

Each route module should follow this pattern:

```python
"""
Description of what this module handles.

Routes:
    METHOD /path - Description
"""

from quart import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('name', __name__, url_prefix='/api')


@bp.route('/endpoint', methods=['POST'])
async def endpoint_name():
    """Docstring describing the endpoint."""
    # Extract from app.py
    # Implementation goes here
    pass


def register(app):
    """Register routes with the app."""
    app.register_blueprint(bp)
    logger.info("✅ Name routes registered")
```

## Extraction Process

1. **Find the route** in `city_guides/src/app.py`
2. **Copy the entire function** to the appropriate module
3. **Update imports** at the top of the module
4. **Add the `@bp.route()` decorator**
5. **Test the endpoint** still works
6. **Remove from app.py** once verified

## Registration

Routes are automatically registered by `register_all_routes(app)` in `__init__.py`.

In `app.py`, replace all individual route registrations with:

```python
from city_guides.src.routes import register_all_routes

# ... after app creation ...
register_all_routes(app)
```

## File Size Limits

- Python: 800 lines = warning, 1000 lines = blocked
- If a module exceeds 800 lines, consider splitting further

## Coordination

If working on route extraction with other LLMs:
1. Check this README for which routes go where
2. Update `ROUTE_REFACTOR_PLAN.md` at project root
3. Test endpoints after extraction
4. Coordinate to avoid conflicts on `app.py` changes
