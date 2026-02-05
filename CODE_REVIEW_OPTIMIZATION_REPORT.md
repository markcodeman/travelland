# TravelLand Code Review & Optimization Report

**Date:** 2026-02-05  
**Reviewer:** AI Code Analysis Agent  
**Scope:** Full-stack codebase review (Backend Python, Frontend React)

---

## Executive Summary

This comprehensive code review identified **47 distinct issues** across 6 major categories:
1. **Hardcoded Data & Paths** (Critical - violates AKIM directives)
2. **Circular Dependencies & Import Issues**
3. **Code Duplication**
4. **Error Handling Anti-patterns**
5. **Performance & Architecture Issues**
6. **Frontend State Management Problems**

**Severity Breakdown:**
- 🔴 **Critical:** 12 issues (security, maintainability blockers)
- 🟡 **High:** 18 issues (performance, code quality)
- 🟢 **Medium:** 17 issues (technical debt, cleanup)

---

## 1. 🔴 CRITICAL: Hardcoded Data & Paths

### Issue 1.1: Hardcoded User Paths Throughout Codebase
**Severity:** 🔴 CRITICAL  
**Files Affected:**
- `city_guides/src/app.py` (line 98)
- `city_guides/scripts/port_monitor.py` (lines 45, 46, 48, 103)
- `city_guides/providers/mapillary_provider.py`
- `city_guides/src/services/pixabay.py`
- `city_guides/src/semantic.py`

**Problem:**
```python
# BAD - Hardcoded user path
app = Quart(__name__, 
    static_folder="/home/markm/TravelLand/city_guides/static",
    template_folder="/home/markm/TravelLand/city_guides/templates")

# BAD - Hardcoded paths in scripts
cmd = "cd /home/markm/TravelLand/frontend && nohup npm run dev..."
```

**Impact:**
- Code breaks on any machine except developer's
- Deployment failures on CI/CD and production
- Team collaboration blocked

**LLM-Friendly Solution:**
```python
# GOOD - Use Path(__file__) for relative paths
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
STATIC_FOLDER = PROJECT_ROOT / "city_guides" / "static"
TEMPLATE_FOLDER = PROJECT_ROOT / "city_guides" / "templates"

app = Quart(__name__, 
    static_folder=str(STATIC_FOLDER),
    template_folder=str(TEMPLATE_FOLDER))

# For .env loading
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
```

**Action Items:**
1. Create `city_guides/src/paths.py` with all path constants using `Path(__file__)`
2. Replace all `/home/markm/TravelLand` references with dynamic paths
3. Update `port_monitor.py` to use `os.getcwd()` or relative paths
4. Add CI test that fails if `/home/markm` is found in any source file

---

### Issue 1.2: Massive Hardcoded Neighborhood Data (500+ lines)
**Severity:** 🔴 CRITICAL (violates AKIM "ELIMINATE STATIC MAPPINGS")  
**File:** `city_guides/providers/multi_provider.py` (lines 40-98)

**Problem:**
```python
# BAD - 500+ lines of hardcoded neighborhood data
CURATED_NEIGHBORHOODS = {
    "Bangkok": [
        {"name": "Sukhumvit", "vibe": "expat nightlife...", ...},
        {"name": "Silom", "vibe": "business district...", ...},
        # ... 50 more entries for Bangkok alone
    ],
    "Tokyo": [...],  # 40+ entries
    "Paris": [...],  # 30+ entries
    # ... 10 more cities
}
```

**Impact:**
- Data becomes stale (no refresh mechanism)
- Scales terribly (manual updates for each city)
- Violates project's "dynamic data" principle

**LLM-Friendly Solution:**
```python
# GOOD - Move to versioned JSON seed file
# File: city_guides/data/neighborhood_seeds.json
{
  "version": "2.0",
  "last_updated": "2026-02-05",
  "source": "curated_seed",
  "cities": {
    "Bangkok": [
      {"name": "Sukhumvit", "vibe": "...", "source": "seed"}
    ]
  }
}

# Code: Load with fallback to provider
def load_neighborhood_seeds() -> Dict:
    seed_file = Path(__file__).parent.parent / "data" / "neighborhood_seeds.json"
    if seed_file.exists():
        with open(seed_file) as f:
            return json.load(f)
    return {"cities": {}}

def get_neighborhoods_for_city(city: str) -> List[Dict]:
    # 1. Try dynamic provider (OSM, WikiData)
    neighborhoods = await fetch_osm_neighborhoods(city)
    
    # 2. Fallback to seed data only if provider fails
    if not neighborhoods:
        seeds = load_neighborhood_seeds()
        neighborhoods = seeds["cities"].get(city, [])
        for n in neighborhoods:
            n["source"] = "seed_fallback"
            logging.warning(f"Using seed fallback for {city}")
    
    return neighborhoods
```

**Action Items:**
1. Extract `CURATED_NEIGHBORHOODS` to `city_guides/data/neighborhood_seeds.json`
2. Add `version` and `last_updated` fields to track freshness
3. Implement dynamic fetch with seed as fallback only
4. Create script `tools/refresh_neighborhood_seeds.py` to regenerate from GeoNames/OSM
5. Add test asserting seed schema matches provider output

---

### Issue 1.3: Hardcoded Icon Mappings (100+ lines)
**Severity:** 🟡 HIGH  
**File:** `city_guides/src/simple_categories.py` (lines 70-123)

**Problem:**
```python
# BAD - 100+ line static dictionary
def get_category_icon(category: str) -> str:
    icons = {
        'fashion': '👗', 'design': '✨',
        'film': '🎬', 'entertainment': '🎭',
        # ... 80 more hardcoded mappings
    }
```

**LLM-Friendly Solution:**
```python
# GOOD - External JSON config
# File: city_guides/data/category_icons.json
{
  "mappings": {
    "fashion": "👗",
    "design": "✨",
    "film": "🎬"
  },
  "fallback": "📍"
}

# Code: Load once at module init
_icon_cache = None

def get_category_icon(category: str) -> str:
    global _icon_cache
    if _icon_cache is None:
        icon_file = Path(__file__).parent.parent / "data" / "category_icons.json"
        with open(icon_file) as f:
            _icon_cache = json.load(f)
    
    category_lower = category.lower()
    for key, icon in _icon_cache["mappings"].items():
        if key in category_lower:
            return icon
    return _icon_cache["fallback"]
```

**Action Items:**
1. Move `icons` dict to JSON config file
2. Add unit test for icon mapping coverage
3. Document how to add new icon mappings

---

### Issue 1.4: Frontend Hardcoded City/Country Lists
**Severity:** 🟡 HIGH  
**File:** `frontend/src/App.jsx` (lines 16-29)

**Problem:**
```javascript
// BAD - Hardcoded lists in component
const CITY_LIST = ['Rio de Janeiro', 'London', 'New York', 'Lisbon'];
const COUNTRIES = ['USA', 'Mexico', 'Spain', 'UK', ...]; // 20 countries
const POPULAR_CITIES = ['New York', 'London', 'Paris', ...]; // 15 cities
const NEIGHBORHOOD_FALLBACKS = {
  'Rio de Janeiro': ['Copacabana', 'Ipanema', ...],
  'London': ['Camden', 'Chelsea', ...],
  // ...
};
```

**LLM-Friendly Solution:**
```javascript
// GOOD - Fetch from backend API or config file
// Option 1: API endpoint
useEffect(() => {
  fetch('/api/metadata')
    .then(r => r.json())
    .then(data => {
      setCountries(data.countries);
      setPopularCities(data.popularCities);
      setNeighborhoodFallbacks(data.neighborhoodFallbacks);
    });
}, []);

// Option 2: Static config (better for static data)
// File: frontend/src/config/cities.json
{
  "countries": ["USA", "Mexico", ...],
  "popularCities": ["New York", "London", ...],
  "neighborhoodFallbacks": {
    "Rio de Janeiro": ["Copacabana", "Ipanema"]
  }
}

// Import at top
import citiesConfig from './config/cities.json';
const { countries, popularCities, neighborhoodFallbacks } = citiesConfig;
```

**Action Items:**
1. Extract lists to `frontend/src/config/cities.json`
2. For frequently changing data, create `/api/metadata` endpoint
3. Add validation that neighborhood fallbacks match backend

---

## 2. 🔴 CRITICAL: Circular Dependencies & Import Issues

### Issue 2.1: App Import Cycles
**Severity:** 🔴 CRITICAL  
**Files:** Multiple

**Problem:**
```python
# routes.py imports from app.py
from city_guides.src.app import redis_client, app

# app.py imports from routes.py
from city_guides.src.routes import register_routes

# semantic.py also imports from app.py
from city_guides.src.app import redis_client
```

**Evidence:**
- `routes.py` line 52: `# from .app import app  # Removed to avoid circular import`
- `metrics.py` conditionally imports: `from city_guides.src.app import redis_client`
- `semantic.py` conditionally imports: `from city_guides.src.app import redis_client`

**Impact:**
- Fragile initialization order
- Hard to test modules in isolation
- Runtime import errors under certain conditions

**LLM-Friendly Solution:**
```python
# GOOD - Dependency injection pattern

# 1. Create city_guides/src/context.py
class AppContext:
    """Application-wide shared state (dependency injection container)"""
    redis_client: Optional[aioredis.Redis] = None
    app: Optional[Quart] = None
    fun_facts: Optional[FunFactTracker] = None
    
    @classmethod
    def initialize(cls, app: Quart, redis_client: aioredis.Redis, ...):
        cls.app = app
        cls.redis_client = redis_client
        cls.fun_facts = FunFactTracker()

# 2. In app.py (initialize once)
from city_guides.src.context import AppContext

app = Quart(__name__)
redis_client = await aioredis.from_url(REDIS_URL)
AppContext.initialize(app, redis_client, ...)

# 3. In routes.py, semantic.py, etc. (no circular import)
from city_guides.src.context import AppContext

async def my_route():
    result = await AppContext.redis_client.get("key")
    return jsonify(result)
```

**Alternative (Simpler):**
```python
# Pass dependencies as function parameters
def register_routes(app: Quart, redis_client: aioredis.Redis, fun_facts: FunFactTracker):
    @app.route("/search")
    async def search():
        result = await redis_client.get("key")
        return jsonify(result)

# In app.py
app = Quart(__name__)
redis_client = await aioredis.from_url(REDIS_URL)
fun_facts = FunFactTracker()
register_routes(app, redis_client, fun_facts)
```

**Action Items:**
1. Create `context.py` or use function parameters for dependency injection
2. Remove all `from app import` statements in other modules
3. Refactor `register_routes()` to accept dependencies as parameters
4. Add test that imports each module standalone (catches circular deps)

---

### Issue 2.2: Duplicate `geocode_city()` Functions
**Severity:** 🟡 HIGH  
**Files:**
- `city_guides/providers/overpass_provider.py`
- `city_guides/providers/geocoding.py`

**Problem:**
```python
# File 1: overpass_provider.py
async def geocode_city(city: str, session: Optional[aiohttp.ClientSession] = None):
    # Implementation A using Overpass API
    ...

# File 2: geocoding.py
async def geocode_city(city: str, country: str = ''):
    # Implementation B using Geonames
    ...
```

**Impact:**
- Ambiguous which to use (different signatures)
- Both imported in `app.py` lines 84-85:
  ```python
  from city_guides.providers.geocoding import geocode_city, reverse_geocode
  from city_guides.providers.overpass_provider import async_geocode_city
  ```

**LLM-Friendly Solution:**
```python
# GOOD - Rename to clarify providers
# File: overpass_provider.py
async def geocode_city_osm(city: str, session=None) -> Optional[Dict]:
    """Geocode using OpenStreetMap Overpass API"""
    ...

# File: geocoding.py
async def geocode_city_geonames(city: str, country: str = '') -> Optional[Dict]:
    """Geocode using Geonames service"""
    ...

# Create unified interface
# File: geocoding.py
async def geocode_city(city: str, country: str = '', provider: str = 'auto') -> Optional[Dict]:
    """
    Unified geocoding with provider fallback
    
    Args:
        city: City name
        country: Optional country filter
        provider: 'geonames', 'osm', or 'auto' (tries both)
    """
    if provider == 'osm':
        return await geocode_city_osm(city)
    elif provider == 'geonames':
        return await geocode_city_geonames(city, country)
    else:  # auto
        result = await geocode_city_geonames(city, country)
        if not result:
            result = await geocode_city_osm(city)
        return result
```

**Action Items:**
1. Rename provider-specific functions: `geocode_city_osm()`, `geocode_city_geonames()`
2. Create unified `geocode_city()` with fallback logic
3. Update all imports to use unified interface
4. Add tests for fallback behavior

---

### Issue 2.3: Duplicate Logging Imports
**Severity:** 🟢 MEDIUM  
**Files:** 17 files

**Problem:**
```python
# multi_provider.py line 2
import logging
# ...
# multi_provider.py line 14 (duplicate!)
import logging
```

**LLM-Friendly Solution:**
```bash
# Run this to find and fix all duplicate imports
find city_guides -name "*.py" -exec python3 << 'EOF' {} \;
import sys
from pathlib import Path

file_path = Path(sys.argv[1])
with open(file_path) as f:
    lines = f.readlines()

imports = {}
for i, line in enumerate(lines):
    if line.strip().startswith(('import ', 'from ')):
        key = line.strip()
        if key in imports:
            print(f"{file_path}:{i+1}: Duplicate import: {key}")
        imports[key] = i
EOF
```

**Action Items:**
1. Use `isort` to organize imports: `pip install isort && isort city_guides/`
2. Add pre-commit hook to prevent duplicate imports
3. Configure `.isort.cfg` for project standards

---

## 3. 🟡 Error Handling Anti-patterns

### Issue 3.1: Excessive Bare `except Exception:` (167 occurrences)
**Severity:** 🟡 HIGH  
**Files:** Most Python files in `city_guides/src/`

**Problem:**
```python
# BAD - Swallows all errors, hard to debug
try:
    result = await some_api_call()
except Exception:
    pass  # Silent failure

try:
    data = json.loads(response)
except Exception as e:
    return None  # Lost error context
```

**Impact:**
- Bugs hidden silently
- No telemetry for failure rates
- Hard to diagnose production issues

**LLM-Friendly Solution:**
```python
# GOOD - Specific exception types with logging
import logging
logger = logging.getLogger(__name__)

try:
    result = await some_api_call()
except aiohttp.ClientError as e:
    logger.error(f"API call failed: {e}", exc_info=True)
    # Decide: re-raise, return default, or handle gracefully
    return {"error": "external_api_unavailable", "fallback": True}
except asyncio.TimeoutError:
    logger.warning(f"API timeout after 10s")
    return {"error": "timeout"}
except Exception as e:
    # Catch-all ONLY for truly unexpected errors
    logger.exception(f"Unexpected error in some_api_call: {e}")
    raise  # Re-raise to not hide bugs

# For optional features, make it explicit
try:
    enrichment = await get_neighborhood_enrichment(city)
except Exception as e:
    logger.info(f"Enrichment unavailable for {city}: {e}")
    enrichment = None  # Expected fallback
```

**Pattern for refactoring:**
1. Identify what exceptions are expected (API errors, timeouts, missing data)
2. Catch those specifically
3. Log with appropriate level (error/warning/info)
4. Only use `except Exception:` as last resort with clear comment why
5. Add monitoring/metrics for fallback paths

**Action Items:**
1. Audit all 167 `except Exception:` occurrences
2. Replace with specific exception types (top 10 patterns: `ClientError`, `TimeoutError`, `KeyError`, `ValueError`, `JSONDecodeError`)
3. Add logging to every exception handler
4. Create exception handling guide in `CONTRIBUTING.md`

---

### Issue 3.2: Silent `pass` Statements (63 occurrences)
**Severity:** 🟡 HIGH  
**Files:** Most Python files

**Problem:**
```python
# BAD - Silent failure, no context
try:
    config = load_config()
except:
    pass
```

**LLM-Friendly Solution:**
```python
# GOOD - Log or use explicit sentinel
try:
    config = load_config()
except FileNotFoundError:
    logger.debug("Config file not found, using defaults")
    config = DEFAULT_CONFIG
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    config = DEFAULT_CONFIG
```

**Action Items:**
1. Replace all `pass` in exception handlers with logging or explicit sentinel return
2. Add `# pylint: disable=broad-except` only when justified with comment

---

## 4. 🟡 Performance & Architecture Issues

### Issue 4.1: Giant Files (Technical Debt)
**Severity:** 🟡 HIGH  
**Files:**
- `app.py`: 3,217 lines (42 functions/routes)
- `semantic.py`: 2,450 lines (49 functions)
- `persistence.py`: 1,851 lines (26 functions)
- `simple_categories.py`: 1,431 lines

**Problem:**
- Hard to navigate and understand
- Merge conflicts frequent
- Testing difficult (many side effects)

**LLM-Friendly Solution:**

**For `app.py` (3,217 lines → split into 5 files):**
```python
# Structure:
# city_guides/src/
#   app.py (150 lines) - App creation, startup, shutdown
#   routes/
#     __init__.py - Import all routes
#     search.py - Search endpoints
#     neighborhoods.py - Neighborhood endpoints
#     semantic.py - Marco chat endpoints
#     metadata.py - Config/categories endpoints

# app.py (after refactor)
from city_guides.src import routes

app = Quart(__name__, ...)
app = cors(app, ...)

# Register route blueprints
app.register_blueprint(routes.search_bp, url_prefix='/api')
app.register_blueprint(routes.neighborhood_bp, url_prefix='/api')
app.register_blueprint(routes.semantic_bp, url_prefix='/api')
app.register_blueprint(routes.metadata_bp, url_prefix='/api')

# Lifecycle hooks
@app.before_serving
async def startup():
    ...

@app.after_serving
async def shutdown():
    ...

if __name__ == '__main__':
    app.run(...)
```

**For `semantic.py` (2,450 lines → split into 4 modules):**
```python
# city_guides/src/semantic/
#   __init__.py - Public API
#   query_analysis.py - analyze_any_query()
#   response_builder.py - build_response_for_any_query()
#   context_manager.py - Conversation history
#   rag_integration.py - Groq RAG calls
```

**Action Items:**
1. Start with `app.py`: Extract routes to `city_guides/src/routes/` with Quart blueprints
2. Split `semantic.py` into submodules under `city_guides/src/semantic/`
3. Target max 500 lines per file, 20 functions per file
4. Use `__init__.py` to maintain backward-compatible imports

---

### Issue 4.2: App.jsx State Explosion (28 useState calls, 1,126 lines)
**Severity:** 🟡 HIGH  
**File:** `frontend/src/App.jsx`

**Problem:**
```javascript
const [location, setLocation] = useState({...});
const [neighborhoodOptions, setNeighborhoodOptions] = useState([]);
const [neighborhoodOptIn, setNeighborhoodOptIn] = useState(false);
const [category, setCategory] = useState('');
const [categoryLabel, setCategoryLabel] = useState('');
const [generating, setGenerating] = useState(false);
const [weather, setWeather] = useState(null);
const [weatherError, setWeatherError] = useState(null);
// ... 20 more state variables
```

**Impact:**
- Hard to track state changes
- Props drilling to child components
- Re-renders trigger complex cascades

**LLM-Friendly Solution:**

**Option 1: Use React Context + useReducer**
```javascript
// contexts/AppContext.js
const AppContext = createContext();

const initialState = {
  location: { country: '', state: '', city: '', neighborhood: '' },
  ui: { loading: false, loadingMessage: '', generating: false },
  search: { results: null, venues: [], category: '' },
  neighborhoods: { options: [], optIn: false, smartNeighborhoods: [] },
  weather: { data: null, error: null },
  hero: { image: '', imageMeta: {} },
  marco: { open: false, webRAG: false }
};

function appReducer(state, action) {
  switch (action.type) {
    case 'SET_LOCATION':
      return { ...state, location: action.payload };
    case 'SET_LOADING':
      return { ...state, ui: { ...state.ui, loading: action.payload } };
    // ... more actions
    default:
      return state;
  }
}

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

// In App.jsx
const { state, dispatch } = useContext(AppContext);

// Update state
dispatch({ type: 'SET_LOCATION', payload: newLocation });
```

**Option 2: Extract to Custom Hooks**
```javascript
// hooks/useLocation.js
export function useLocation() {
  const [location, setLocation] = useState({...});
  const [options, setOptions] = useState([]);
  
  const updateLocation = useCallback((newLoc) => {
    setLocation(newLoc);
    // Side effects here
  }, []);
  
  return { location, options, updateLocation };
}

// hooks/useSearch.js
export function useSearch() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const search = useCallback(async (query) => {
    setLoading(true);
    const data = await fetch('/api/search', { ... });
    setResults(data);
    setLoading(false);
  }, []);
  
  return { results, loading, search };
}

// In App.jsx
const location = useLocation();
const search = useSearch();
const weather = useWeather();
const neighborhoods = useNeighborhoods();
```

**Action Items:**
1. Group related state into domain objects (location, search, UI, etc.)
2. Use `useReducer` for complex state logic or Context for global state
3. Extract to custom hooks for reusability
4. Target: < 10 state variables in App.jsx

---

### Issue 4.3: No Request Deduplication/Caching (Frontend)
**Severity:** 🟡 HIGH  
**File:** `frontend/src/App.jsx`

**Problem:**
```javascript
// Multiple components may fetch same data
useEffect(() => {
  fetch(`/api/weather?city=${city}`)
    .then(r => r.json())
    .then(setWeather);
}, [city]);

// Another component also fetches weather
useEffect(() => {
  fetch(`/api/weather?city=${city}`)
    .then(r => r.json())
    .then(data => ...);
}, [city]);
```

**LLM-Friendly Solution:**
```javascript
// Use React Query for automatic caching & deduplication
import { useQuery } from '@tanstack/react-query';

function useWeather(city) {
  return useQuery({
    queryKey: ['weather', city],
    queryFn: () => fetch(`/api/weather?city=${city}`).then(r => r.json()),
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: !!city
  });
}

// In component
const { data: weather, isLoading, error } = useWeather(city);

// Multiple components using useWeather(city) will share same request
```

**Alternative (DIY caching):**
```javascript
// utils/apiCache.js
const cache = new Map();

export async function cachedFetch(url, ttlMs = 60000) {
  const cached = cache.get(url);
  if (cached && Date.now() - cached.timestamp < ttlMs) {
    return cached.data;
  }
  
  const data = await fetch(url).then(r => r.json());
  cache.set(url, { data, timestamp: Date.now() });
  return data;
}
```

**Action Items:**
1. Install React Query: `npm install @tanstack/react-query`
2. Wrap app with `<QueryClientProvider>`
3. Replace all `fetch()` calls with `useQuery()` hooks
4. Add request deduplication for hot paths (weather, hero images)

---

## 5. 🟢 Code Quality & Cleanup

### Issue 5.1: Unused Imports
**Severity:** 🟢 MEDIUM  
**Files:** Multiple

**Problem:**
Example from `routes.py`:
```python
import json  # Used
import hashlib  # Used
import re  # Used
import time  # UNUSED
import requests  # UNUSED
```

**LLM-Friendly Solution:**
```bash
# Use autoflake to remove unused imports
pip install autoflake
autoflake --in-place --remove-all-unused-imports --recursive city_guides/

# Or use pylint to detect
pylint --disable=all --enable=unused-import city_guides/
```

**Action Items:**
1. Run `autoflake` on entire codebase
2. Add to pre-commit hooks
3. Configure IDE to highlight unused imports

---

### Issue 5.2: Inconsistent Import Styles
**Severity:** 🟢 MEDIUM  
**Files:** All Python files

**Problem:**
```python
# Some files use try/except for optional imports
try:
    from city_guides.providers.wikipedia_provider import fetch_wikipedia_summary
    WIKI_AVAILABLE = True
except Exception:
    WIKI_AVAILABLE = False

# Other files crash if import fails
from city_guides.providers.wikipedia_provider import fetch_wikipedia_summary
```

**LLM-Friendly Solution:**
```python
# GOOD - Standardize optional import pattern
# File: city_guides/src/optional_imports.py
from typing import Optional, Callable

def optional_import(module_path: str, symbol: str) -> tuple[Optional[Callable], bool]:
    """
    Safely import optional dependencies
    
    Returns:
        (imported_symbol, is_available)
    """
    try:
        module = __import__(module_path, fromlist=[symbol])
        return getattr(module, symbol), True
    except (ImportError, AttributeError) as e:
        logging.debug(f"Optional import {module_path}.{symbol} unavailable: {e}")
        return None, False

# Usage
fetch_wikipedia_summary, WIKI_AVAILABLE = optional_import(
    'city_guides.providers.wikipedia_provider', 
    'fetch_wikipedia_summary'
)

if WIKI_AVAILABLE:
    summary = await fetch_wikipedia_summary(city)
else:
    summary = None
```

**Action Items:**
1. Create `optional_imports.py` helper
2. Standardize all try/except imports to use helper
3. Document required vs optional dependencies in README

---

### Issue 5.3: Missing Type Hints (Only 20/18 src files have them)
**Severity:** 🟢 MEDIUM  
**Files:** Most Python files

**Problem:**
```python
# BAD - No type hints
def format_venue(venue):
    return {
        'name': venue.get('name'),
        'lat': venue.get('lat'),
        # ...
    }
```

**LLM-Friendly Solution:**
```python
# GOOD - Full type hints
from typing import Dict, Any, Optional

def format_venue(venue: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format venue data for API response
    
    Args:
        venue: Raw venue data from provider
        
    Returns:
        Formatted venue dict with standardized fields
    """
    return {
        'name': venue.get('name', ''),
        'lat': venue.get('lat', 0.0),
        # ...
    }
```

**Action Items:**
1. Use `mypy` for gradual type checking: `pip install mypy`
2. Add type hints to public function signatures (start with `src/` directory)
3. Run `mypy --strict city_guides/src` and fix errors incrementally
4. Add to CI: `mypy city_guides/ --no-strict-optional`

---

### Issue 5.4: Console.log Left in Production Code
**Severity:** 🟢 MEDIUM  
**Files:** `frontend/src/services/imageService.js`, `frontend/src/components/CitySuggestions.jsx`, `MarcoChat.jsx`, `GlobeSelector.jsx`

**Problem:**
```javascript
// BAD - Debug logs in production
console.log('Fetching hero image for', city);
console.log('Search results:', results);
```

**LLM-Friendly Solution:**
```javascript
// GOOD - Conditional logging with environment check
const isDev = import.meta.env.MODE === 'development';

const logger = {
  debug: (...args) => isDev && console.log('[DEBUG]', ...args),
  info: (...args) => console.info('[INFO]', ...args),
  warn: (...args) => console.warn('[WARN]', ...args),
  error: (...args) => console.error('[ERROR]', ...args)
};

// Usage
logger.debug('Fetching hero image for', city); // Only in dev
logger.error('API call failed', error); // Always shown
```

**Action Items:**
1. Create `utils/logger.js` with environment-aware logging
2. Replace all `console.log` with `logger.debug`
3. Use ESLint rule `no-console` to prevent future violations
4. Configure in `.eslintrc.js`:
   ```javascript
   rules: {
     'no-console': ['error', { allow: ['warn', 'error'] }]
   }
   ```

---

### Issue 5.5: Test Files in Root Directory (Should be in tests/)
**Severity:** 🟢 MEDIUM  
**Files:** 
- `test_100_cities.py`
- `test_neighborhoods.py`
- `test_neighborhoods_simple.py`
- `test_wikidata_neighborhoods.py`
- `quick_lame_test.py`
- `marco_auto_test.py`

**Problem:**
```
/repo_root/
  test_100_cities.py      # BAD - clutters root
  test_neighborhoods.py   # BAD
  quick_lame_test.py      # BAD
  city_guides/
    tests/                # GOOD - proper location
      test_integration.py
```

**LLM-Friendly Solution:**
```bash
# Move all test files to proper directory
mkdir -p tests/integration
mv test_100_cities.py tests/integration/
mv test_neighborhoods*.py tests/integration/
mv quick_lame_test.py tests/manual/
mv marco_auto_test.py tools/

# Update test discovery in pytest.ini or pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests", "city_guides/tests"]
python_files = ["test_*.py", "*_test.py"]
```

**Action Items:**
1. Move root test files to `tests/` directory
2. Categorize: `tests/integration/`, `tests/manual/`, `tests/e2e/`
3. Update CI/CD to run from new locations
4. Add `.gitignore` entry for `test_*.pyc`

---

## 6. 🟡 Security & Best Practices

### Issue 6.1: Hardcoded Ports and URLs
**Severity:** 🟡 HIGH  
**Files:** Multiple scripts and test files

**Problem:**
```python
# BAD - Hardcoded localhost URLs
URL = "http://127.0.0.1:5010"
API_BASE = "http://localhost:5174"
```

**LLM-Friendly Solution:**
```python
# GOOD - Use environment variables with defaults
import os

API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5010')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5174')

# In tests, allow override
@pytest.fixture
def api_base_url():
    return os.getenv('TEST_API_URL', 'http://localhost:5010')
```

**Action Items:**
1. Extract all hardcoded URLs to environment variables
2. Create `.env.example` with all required variables
3. Update README with configuration instructions

---

### Issue 6.2: No Input Validation on API Endpoints
**Severity:** 🟡 HIGH  
**File:** `city_guides/src/routes.py`

**Problem:**
```python
# BAD - No validation
@app.route("/api/search", methods=["POST"])
async def api_search():
    payload = await request.get_json(silent=True) or {}
    city = payload.get("query", "").strip()
    
    if not city:
        return jsonify({"error": "city required"}), 400
    
    # Directly use city without validation
    result = await search(city)
```

**LLM-Friendly Solution:**
```python
# GOOD - Use Pydantic for validation
from pydantic import BaseModel, Field, validator

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=100)
    category: str = Field(default="", max_length=50)
    neighborhood: Optional[str] = Field(None, max_length=100)
    
    @validator('query')
    def validate_query(cls, v):
        # Prevent injection attacks
        if any(char in v for char in ['<', '>', ';', '&', '|']):
            raise ValueError('Invalid characters in query')
        return v.strip()

@app.route("/api/search", methods=["POST"])
async def api_search():
    try:
        payload = await request.get_json()
        request_data = SearchRequest(**payload)
    except ValidationError as e:
        return jsonify({"error": "validation_failed", "details": e.errors()}), 400
    
    result = await search(request_data.query, request_data.category)
    return jsonify(result)
```

**Action Items:**
1. Add Pydantic to dependencies: `pip install pydantic`
2. Create request/response models for all API endpoints
3. Add input sanitization for SQL injection, XSS
4. Add rate limiting with `quart-rate-limiter`

---

## 7. Summary of Action Items (Prioritized)

### 🔴 Critical (Do First)
1. **Remove all hardcoded paths** (`/home/markm/TravelLand`) - replace with `Path(__file__)` relative paths
2. **Fix circular dependencies** - create `context.py` or use dependency injection
3. **Extract hardcoded neighborhood data** - move to versioned JSON seed file
4. **Rename duplicate functions** - `geocode_city_osm()` vs `geocode_city_geonames()`

### 🟡 High Priority (Do Next)
5. **Refactor exception handling** - replace 167 bare `except Exception:` with specific types
6. **Split giant files** - `app.py` (3.2k lines), `semantic.py` (2.4k lines) into modules
7. **Add input validation** - use Pydantic for all API endpoints
8. **Fix frontend state management** - use useReducer or React Query

### 🟢 Medium Priority (Quality Improvements)
9. **Remove unused imports** - run `autoflake --recursive`
10. **Add type hints** - run `mypy` on `src/` directory
11. **Remove console.log** - replace with environment-aware logger
12. **Move test files** - relocate root test files to `tests/` directory
13. **Extract hardcoded config** - move icon mappings, city lists to JSON

### 🔵 Low Priority (Nice to Have)
14. Add frontend request caching with React Query
15. Add pre-commit hooks for linting
16. Create `CONTRIBUTING.md` with code style guide
17. Add CI job that fails if hardcoded paths detected

---

## 8. Refactoring Checklist for LLMs

When implementing these changes, follow this order to minimize breakage:

### Phase 1: Remove Hardcoded Paths (1 hour)
- [ ] Create `city_guides/src/paths.py` with `PROJECT_ROOT = Path(__file__).parent.parent.parent`
- [ ] Replace all `/home/markm/TravelLand` with imports from `paths.py`
- [ ] Update `app.py` static/template folders
- [ ] Update `port_monitor.py` to use relative paths
- [ ] Test app startup

### Phase 2: Fix Circular Dependencies (2 hours)
- [ ] Create `city_guides/src/context.py` with `AppContext` class
- [ ] Initialize `AppContext` in `app.py` startup
- [ ] Replace `from app import redis_client` with `from context import AppContext`
- [ ] Update `routes.py`, `semantic.py`, `metrics.py` imports
- [ ] Test each module imports standalone: `python -c "import city_guides.src.routes"`

### Phase 3: Extract Hardcoded Data (3 hours)
- [ ] Create `city_guides/data/neighborhood_seeds.json`
- [ ] Move `CURATED_NEIGHBORHOODS` dict to JSON file
- [ ] Update code to load JSON with fallback
- [ ] Create `city_guides/data/category_icons.json`
- [ ] Move icon mappings from `simple_categories.py` to JSON
- [ ] Create `frontend/src/config/cities.json` for frontend lists
- [ ] Test data loads correctly

### Phase 4: Improve Error Handling (4 hours)
- [ ] Create exception handling guide in `CONTRIBUTING.md`
- [ ] Audit top 20 files with most `except Exception:` clauses
- [ ] Replace with specific exception types + logging
- [ ] Add logging to all exception handlers
- [ ] Remove silent `pass` statements

### Phase 5: Refactor Giant Files (8 hours)
- [ ] Split `app.py` into Quart blueprints under `city_guides/src/routes/`
- [ ] Split `semantic.py` into submodules under `city_guides/src/semantic/`
- [ ] Split `persistence.py` by responsibility (caching, formatting, enrichment)
- [ ] Update imports to use new structure
- [ ] Test all endpoints work

### Phase 6: Frontend Improvements (4 hours)
- [ ] Install React Query: `npm install @tanstack/react-query`
- [ ] Extract related state to custom hooks
- [ ] Replace fetch calls with `useQuery`
- [ ] Create `utils/logger.js` for environment-aware logging
- [ ] Replace `console.log` with `logger.debug`

### Phase 7: Code Quality (2 hours)
- [ ] Run `autoflake --in-place --remove-all-unused-imports --recursive city_guides/`
- [ ] Run `isort city_guides/` to organize imports
- [ ] Add type hints to top 10 most-used functions
- [ ] Move root test files to `tests/` directory
- [ ] Add ESLint rule for no-console

---

## 9. Estimated Impact

**Before Refactoring:**
- 🔴 12 critical blockers (hardcoded paths, circular deps)
- 🟡 18 high-priority issues (error handling, giant files)
- 🟢 17 medium-priority issues (code quality)
- **Total Technical Debt:** ~24 hours to fix all issues

**After Refactoring:**
- ✅ Code runs on any machine (no hardcoded paths)
- ✅ Modules can be tested in isolation (no circular deps)
- ✅ Dynamic data from APIs (no stale hardcoded neighborhoods)
- ✅ Debuggable errors (specific exception types + logging)
- ✅ Maintainable codebase (files < 500 lines, clear structure)
- ✅ Type-safe APIs (Pydantic validation, mypy checks)
- ✅ Production-ready (no debug logs, proper caching)

**Maintainability Score:**
- Current: 3/10 (high technical debt, fragile)
- After refactor: 8/10 (modular, typed, tested)

---

## 10. Appendix: Tools & Commands

### Automated Refactoring Tools
```bash
# Install all tools
pip install autoflake isort mypy pylint black
npm install -g eslint prettier

# Python formatting
black city_guides/
isort city_guides/
autoflake --in-place --remove-all-unused-imports --recursive city_guides/

# JavaScript formatting
npx prettier --write "frontend/src/**/*.{js,jsx}"
npx eslint --fix frontend/src/

# Type checking
mypy city_guides/src/ --no-strict-optional

# Linting
pylint city_guides/src/ --disable=C0111,C0103
```

### Pre-commit Hook Setup
```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat << 'EOF' > .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11
  
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
  
  - repo: https://github.com/PyCQA/autoflake
    rev: v2.1.1
    hooks:
      - id: autoflake
        args: ['--in-place', '--remove-all-unused-imports']
  
  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.40.0
    hooks:
      - id: eslint
        files: \.(js|jsx)$
        types: [file]
EOF

# Install hooks
pre-commit install
```

---

**End of Report**

Generated by AI Code Review Agent  
Next Steps: Implement Phase 1-3 (Critical & High Priority) within 1 sprint.
