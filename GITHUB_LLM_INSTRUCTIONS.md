# Instructions for GitHub LLM - Route Extraction

## Task
Extract remaining 20 routes from `city_guides/src/app.py` into `city_guides/src/routes/` modules.

## What's Already Done
- ✅ Infrastructure: `routes/__init__.py` with `register_all_routes(app)`
- ✅ Admin routes: `routes/admin.py` (5 routes - working example)
- ✅ Media routes: `routes/media.py` (2 routes - working example)
- ✅ Placeholder modules: chat.py, search.py, locations.py, poi.py, guide.py, utils.py
- ✅ Documentation: `routes/README.md`, `ROUTE_REFACTOR_PLAN.md`, `ROUTE_EXTRACTION_STATUS.md`

## Your Task: Extract 20 Routes

### Priority Order (Start Here)

1. **POI Routes** - `routes/poi.py`
   - `/api/poi-discovery` (POST) - line 1693-1817 in app.py
   - `/api/smart-neighborhoods` (GET) - line 2453-2561 in app.py
   - Complexity: Medium

2. **Utility Routes** - `routes/utils.py`
   - `/api/parse-dream` (POST) - line 4006-4211
   - `/api/location-suggestions` (POST) - line 4212-4284
   - `/api/log-suggestion-success` (POST) - line 4565-4577
   - Complexity: Medium

3. **Search Route** - `routes/search.py`
   - `/api/search` (POST) - line 2586-2664
   - Complexity: High

4. **Chat Route** - `routes/chat.py`
   - `/api/chat/rag` (POST) - line 23-557
   - Complexity: High (534 lines)

5. **Location Routes** - `routes/locations.py`
   - `/api/geocode` (POST)
   - `/api/reverse_lookup` (POST)
   - `/api/geonames-search` (POST)
   - `/api/countries` (GET)
   - `/api/locations/states` (GET)
   - `/api/locations/cities` (GET)
   - `/api/locations/neighborhoods` (GET)
   - Complexity: High (7 routes)

6. **Guide Routes** - `routes/guide.py`
   - `/api/generate_quick_guide` (POST) - line 2703-4005 (~1300 lines!)
   - `/api/fun-fact` (POST) - line 2369-2452
   - `/api/synthesize` (POST) - line 2665-2702
   - Complexity: Very High (may need splitting)

## Pattern to Follow

```python
"""
Description of routes in this module.
"""

from quart import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('name', __name__, url_prefix='/api')

@bp.route('/endpoint', methods=['POST'])
async def endpoint_name():
    """Docstring"""
    # Copy implementation from app.py
    # Replace app.logger with logger
    # Update imports as needed
    pass

def register(app):
    """Register with app."""
    app.register_blueprint(bp)
    logger.info("✅ Module routes registered")
```

## Common Issues

### Global Variables
- `aiohttp_session` → Import from providers.utils: `from city_guides.providers.utils import get_session`
- `redis_client` → Check if available, handle gracefully
- `ddgs_search` → Import: `from city_guides.providers.ddgs_provider import ddgs_search`
- `app.logger` → Use `logger` (module-level)

### Helper Functions
If routes use helper functions from app.py:
- Copy them to the route module
- Or move to `city_guides/src/utils/` if shared

## Testing Each Route

```bash
# After extracting a route, test it:
curl -X POST http://localhost:5010/api/ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{"param": "value"}'

# Should return 200 OK with expected format
```

## File Size Limits

- Python files: 800 lines = warning, 1000 lines = blocked
- If a module exceeds 1000 lines, split it further
- `guide.py` will likely exceed limit - consider splitting into:
  - `guide_generation.py` - /api/generate_quick_guide
  - `guide_utils.py` - /api/fun-fact, /api/synthesize

## After Extraction

When all routes extracted:

1. Update `app.py`:
   ```python
   from city_guides.src.routes import register_all_routes
   # ... after app creation ...
   register_all_routes(app)
   ```

2. Remove old route definitions from `app.py`

3. Test all endpoints still work

4. app.py should shrink from ~4,700 to ~300 lines

## Need Help?

- See `routes/admin.py` and `routes/media.py` for working examples
- See `routes/README.md` for detailed extraction guide
- See `ROUTE_EXTRACTION_STATUS.md` for current progress
- See `ROUTE_REFACTOR_PLAN.md` for full route inventory with line numbers

## Goal

Extract all routes so `app.py` is under 500 lines (currently ~4,700 lines).
Pre-commit hook enforces 1000-line limit.

Good luck! 🚀
