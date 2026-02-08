# Route Extraction Status

## Overview
Extracting 27 routes from `city_guides/src/app.py` (~4,700 lines) into dedicated modules.

**Status: PHASE 1 COMPLETE - HANDOFF TO NEXT LLM**

## ✅ Completed by Cline (7 routes)

| Module | Routes | Lines | Status |
|--------|--------|-------|--------|
| `routes/admin.py` | /admin, /api/health, /healthz, /metrics/json, /smoke | ~100 | ✅ Extracted & Working |
| `routes/media.py` | /api/unsplash-search, /api/pixabay-search | ~150 | ✅ Extracted & Working |

## 📋 Handoff Notes for Next LLM

**Your task:** Extract the remaining 20 routes from `city_guides/src/app.py`

### Priority Order (Easiest First):
1. **POI routes** (`routes/poi.py`) - 2 routes, medium complexity
2. **Utility routes** (`routes/utils.py`) - 3 routes, medium complexity  
3. **Search route** (`routes/search.py`) - 1 route, high complexity
4. **Chat route** (`routes/chat.py`) - 1 route, 534 lines, high complexity
5. **Location routes** (`routes/locations.py`) - 7 routes, high complexity
6. **Guide routes** (`routes/guide.py`) - 3 routes, 1300+ lines, very high complexity

### Key Files:
- `ROUTE_REFACTOR_PLAN.md` - Full route inventory with line numbers
- `city_guides/src/routes/README.md` - Template and extraction guide
- `city_guides/src/routes/__init__.py` - Registration system (already set up)
- `city_guides/src/app.py` - Source file with all routes

### Pattern to Follow:
```python
from quart import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('name', __name__, url_prefix='/api')

@bp.route('/endpoint', methods=['POST'])
async def endpoint_name():
    # Copy from app.py, update imports
    pass

def register(app):
    app.register_blueprint(bp)
    logger.info("✅ Name routes registered")
```

### Global Dependencies to Handle:
- `aiohttp_session` - Import from providers or pass as param
- `redis_client` - Check if available, handle gracefully
- `ddgs_search` - Import from providers.ddgs_provider
- `app.logger` - Use module-level `logger` instead

## ⏳ Remaining Work (20 routes)

| Module | Routes | Lines in app.py | Complexity | Priority |
|--------|--------|-----------------|------------|----------|
| `routes/poi.py` | /api/poi-discovery, /api/smart-neighborhoods | 1693-1817, 2453-2561 | Medium | 1 |
| `routes/utils.py` | /api/parse-dream, /api/location-suggestions, /api/log-suggestion-success | 4006-4564 | Medium | 2 |
| `routes/search.py` | /api/search | 2586-2664 | High | 3 |
| `routes/chat.py` | /api/chat/rag | 23-557 | High | 4 |
| `routes/locations.py` | /api/geocode, /api/reverse_lookup, /api/geonames-search, +4 more | Multiple | High | 5 |
| `routes/guide.py` | /api/generate_quick_guide, /api/fun-fact, /api/synthesize | 2703-4005 | Very High | 6 |

## Core Routes (Keep in app.py)
- `GET /` - Serve React app (keep in app.py)
- `GET /<path:path>` - Catch-all (keep in app.py)

## Testing Checklist per Route
- [ ] Route responds with 200 OK
- [ ] Request/response format unchanged from original
- [ ] Error handling preserved
- [ ] Logs still functional
- [ ] No import errors
- [ ] Can be registered via `register_all_routes(app)`

## File Size Limits
- Python: 800 lines = warning, 1000 lines = blocked
- Current largest remaining: `guide.py` will be ~1300 lines (may need sub-splitting)

## Final Integration Steps
After all routes extracted:
1. Update `app.py` to import and call `register_all_routes(app)`
2. Remove old route definitions from `app.py`
3. Test all endpoints
4. app.py should shrink from ~4,700 to ~300 lines

## Infrastructure Already Complete
✅ `routes/__init__.py` - Registration system
✅ `routes/admin.py` - Working example (5 routes)
✅ `routes/media.py` - Working example (2 routes)
✅ All placeholder modules created
✅ Documentation and templates ready

**Next LLM: Start with `routes/poi.py` and work through priority list!**
