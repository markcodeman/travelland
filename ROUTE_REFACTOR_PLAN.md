# Route Refactoring Plan

## Goal
Extract all routes from `city_guides/src/app.py` into dedicated route modules to achieve:
- Files under 1000 lines (ideal: 500-800)
- Clear separation of concerns
- Easier testing and maintenance

## Proposed Structure

```
city_guides/src/
├── app.py                    # ~200 lines - App factory, config, startup
├── routes/
│   ├── __init__.py           # register_all_routes(app)
│   ├── chat.py               # /api/chat/* routes (~300 lines)
│   ├── search.py             # /api/search, /api/categories (~200 lines)
│   ├── locations.py          # /api/geocode, /api/reverse_lookup, /api/geonames-search (~400 lines)
│   ├── poi.py                # /api/poi-discovery, /api/smart-neighborhoods (~200 lines)
│   ├── media.py              # /api/unsplash-search, /api/pixabay-search (~150 lines)
│   ├── guide.py              # /api/generate_quick_guide, /api/fun-fact, /api/synthesize (~800 lines)
│   ├── admin.py              # /admin, /api/health, /metrics/json (~100 lines)
│   └── utils.py              # /api/parse-dream, /api/location-suggestions (~200 lines)
```

## Route Inventory

### 1. chat.py
- [ ] `POST /api/chat/rag` - RAG chat endpoint

### 2. search.py
- [ ] `POST /api/search` - Venue search
- [ ] `POST /api/categories` - Dynamic categories (already in routes.py, needs migration)

### 3. locations.py
- [ ] `POST /api/geocode` - Geocode city/neighborhood
- [ ] `POST /api/reverse_lookup` - Reverse geocode coordinates
- [ ] `POST /api/geonames-search` - GeoNames city search
- [ ] `GET /api/countries` - List countries
- [ ] `GET /api/locations/states` - Get states for country
- [ ] `GET /api/locations/cities` - Get cities for state
- [ ] `GET /api/locations/neighborhoods` - Get neighborhoods for city
- [ ] `GET /api/neighborhoods/<country_code>` - Get neighborhoods from seed data

### 4. poi.py
- [ ] `POST /api/poi-discovery` - POI discovery endpoint
- [ ] `GET /api/smart-neighborhoods` - Smart neighborhood suggestions

### 5. media.py
- [ ] `POST /api/unsplash-search` - Unsplash API proxy
- [ ] `POST /api/pixabay-search` - Pixabay API proxy

### 6. guide.py
- [ ] `POST /api/generate_quick_guide` - Generate neighborhood quick guide
- [ ] `POST /api/fun-fact` - Get fun facts about a city
- [ ] `POST /api/synthesize` - Synthesize venues from search results

### 7. admin.py
- [ ] `GET /admin` - Admin dashboard
- [ ] `GET /api/health` - Health check
- [ ] `GET /healthz` - Lightweight health endpoint
- [ ] `GET /metrics/json` - Metrics endpoint
- [ ] `GET /smoke` - Smoke test endpoint

### 8. utils.py
- [ ] `POST /api/parse-dream` - Parse natural language travel queries
- [ ] `POST /api/location-suggestions` - Location suggestions with learning
- [ ] `POST /api/log-suggestion-success` - Log successful suggestions

## Migration Pattern

Each route file should use Blueprint pattern:

```python
# routes/locations.py
from quart import Blueprint, request, jsonify

bp = Blueprint('locations', __name__, url_prefix='/api')

@bp.route('/geocode', methods=['POST'])
async def geocode():
    # implementation
    pass

def register(app):
    app.register_blueprint(bp)
```

Then in `app.py`:

```python
from city_guides.src.routes import chat, search, locations, poi, media, guide, admin, utils

def register_all_routes(app):
    chat.register(app)
    search.register(app)
    locations.register(app)
    poi.register(app)
    media.register(app)
    guide.register(app)
    admin.register(app)
    utils.register(app)
```

## Coordination Notes

- **Current Status**: Another LLM is working on route extraction
- **This LLM Focus**: Admin dashboard HTML/JS extraction (separate concern)
- **No Conflicts**: Routes and admin templates are independent workstreams
- **Integration Point**: Both will update `app.py` to remove extracted code and register blueprints

## Size Targets

| Module | Target Lines | Max Lines |
|--------|--------------|-----------|
| app.py | 200 | 500 |
| routes/*.py | 300-500 | 800 |
| admin/*.py | 200-400 | 600 |

## Pre-commit Hook

Global file size enforcement is active:
- Python: 800 lines = warning, 1000 lines = blocked
- JavaScript: 600 lines max
- CSS: 500 lines max

## Testing Checklist

After each route module extraction:
- [ ] Route responds with 200 OK
- [ ] Request/response format unchanged
- [ ] Error handling preserved
- [ ] Logs still functional
- [ ] No import errors
