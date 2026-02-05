# Quick Fixes Checklist - TravelLand

**Priority fixes that can be done independently. Check off as you complete each.**

## 🔴 CRITICAL - Do Immediately

### 1. Remove Hardcoded Paths (30 min)
**Files to fix:**
```bash
grep -r "/home/markm" city_guides/ --include="*.py" -l
```

**Fix pattern:**
```python
# REPLACE THIS:
static_folder="/home/markm/TravelLand/city_guides/static"

# WITH THIS:
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
static_folder=str(PROJECT_ROOT / "city_guides" / "static")
```

**Files:**
- [ ] `city_guides/src/app.py` line 98
- [ ] `city_guides/scripts/port_monitor.py` lines 45, 46, 48
- [ ] `city_guides/providers/mapillary_provider.py`
- [ ] `city_guides/src/services/pixabay.py`
- [ ] `city_guides/src/semantic.py`

---

### 2. Fix Duplicate Function Names (15 min)
**Problem:** Two `geocode_city()` functions exist

**Action:**
```python
# In overpass_provider.py
async def geocode_city(city, session=None):  # RENAME TO:
async def geocode_city_osm(city, session=None):

# In geocoding.py - keep as is but add fallback
async def geocode_city(city, country=''):
    result = await geocode_city_geonames(city, country)
    if not result:
        result = await geocode_city_osm(city)
    return result
```

**Files:**
- [ ] `city_guides/providers/overpass_provider.py` - rename to `geocode_city_osm`
- [ ] `city_guides/providers/geocoding.py` - add unified interface
- [ ] Update all imports in `app.py`

---

### 3. Move Hardcoded Data to JSON (1 hour)
**Files to create:**
- [ ] `city_guides/data/neighborhood_seeds.json` - extract `CURATED_NEIGHBORHOODS` from `multi_provider.py`
- [ ] `city_guides/data/category_icons.json` - extract icon dict from `simple_categories.py`
- [ ] `frontend/src/config/cities.json` - extract `COUNTRIES`, `POPULAR_CITIES` from `App.jsx`

**Example structure for `neighborhood_seeds.json`:**
```json
{
  "version": "2.0",
  "last_updated": "2026-02-05",
  "cities": {
    "Bangkok": [
      {"name": "Sukhumvit", "vibe": "...", "source": "seed"}
    ]
  }
}
```

---

## 🟡 HIGH PRIORITY - Do This Week

### 4. Remove Duplicate Logging Imports (10 min)
```bash
# Run this command to find and fix
find city_guides -name "*.py" -exec sed -i '/^import logging$/!b;n;/^import logging$/d' {} \;
```

**Or use isort:**
```bash
pip install isort
isort city_guides/
```

- [ ] Run isort on entire codebase
- [ ] Add to pre-commit hook

---

### 5. Fix Bare Exception Handlers (2 hours)
**Pattern to find:**
```bash
grep -n "except Exception:" city_guides/src/*.py | head -20
```

**Fix pattern:**
```python
# REPLACE THIS:
try:
    data = await fetch_api()
except Exception:
    pass

# WITH THIS:
try:
    data = await fetch_api()
except aiohttp.ClientError as e:
    logger.error(f"API fetch failed: {e}")
    data = None
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    raise
```

**Top files to fix (20 worst offenders):**
- [ ] `city_guides/src/persistence.py` (30+ occurrences)
- [ ] `city_guides/src/semantic.py` (25+ occurrences)
- [ ] `city_guides/src/app.py` (20+ occurrences)

---

### 6. Remove console.log from Frontend (15 min)
```bash
# Find all console.log
grep -rn "console.log" frontend/src/ --include="*.js" --include="*.jsx"
```

**Create logger utility:**
```javascript
// frontend/src/utils/logger.js
const isDev = import.meta.env.MODE === 'development';
export const logger = {
  debug: (...args) => isDev && console.log('[DEBUG]', ...args),
  info: (...args) => console.info('[INFO]', ...args),
  error: (...args) => console.error('[ERROR]', ...args)
};
```

**Files:**
- [ ] `frontend/src/services/imageService.js`
- [ ] `frontend/src/components/CitySuggestions.jsx`
- [ ] `frontend/src/components/MarcoChat.jsx`
- [ ] `frontend/src/components/GlobeSelector.jsx`

---

### 7. Move Root Test Files (5 min)
```bash
mkdir -p tests/integration tests/manual
mv test_100_cities.py tests/integration/
mv test_neighborhoods*.py tests/integration/
mv quick_lame_test.py tests/manual/
mv marco_auto_test.py tools/
```

- [ ] Run commands above
- [ ] Update CI config to run from new locations

---

## 🟢 MEDIUM PRIORITY - Do This Month

### 8. Add Type Hints (4 hours)
**Start with most-used functions:**

```python
# BEFORE
def format_venue(venue):
    return {...}

# AFTER
from typing import Dict, Any

def format_venue(venue: Dict[str, Any]) -> Dict[str, Any]:
    return {...}
```

**Priority files:**
- [ ] `city_guides/src/persistence.py` - `format_venue()`, `format_venue_for_display()`
- [ ] `city_guides/providers/geocoding.py` - all functions
- [ ] `city_guides/src/validation.py` - `validate_neighborhood()`

---

### 9. Split Giant Files (8 hours)
**Target: Max 500 lines per file**

**Split `app.py` (3,217 lines → 5 files):**
```
city_guides/src/
  app.py (150 lines) - App creation only
  routes/
    __init__.py
    search.py
    neighborhoods.py
    semantic.py
    metadata.py
```

- [ ] Create `routes/` directory structure
- [ ] Move route functions to appropriate files
- [ ] Convert to Quart blueprints
- [ ] Update imports

**Split `semantic.py` (2,450 lines → 4 files):**
```
city_guides/src/semantic/
  __init__.py - Public API
  query_analysis.py
  response_builder.py
  rag_integration.py
```

- [ ] Create `semantic/` directory structure
- [ ] Split by responsibility
- [ ] Update imports

---

### 10. Remove Unused Imports (10 min)
```bash
pip install autoflake
autoflake --in-place --remove-all-unused-imports --recursive city_guides/
autoflake --in-place --remove-all-unused-imports --recursive frontend/src/
```

- [ ] Run autoflake
- [ ] Review changes
- [ ] Commit

---

### 11. Add Input Validation (2 hours)
```bash
pip install pydantic
```

**Pattern:**
```python
from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=100)
    category: str = Field(default="", max_length=50)

@app.route("/api/search", methods=["POST"])
async def api_search():
    try:
        payload = await request.get_json()
        req = SearchRequest(**payload)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    # Use req.query, req.category
```

**Files:**
- [ ] `city_guides/src/routes.py` - `/api/search` endpoint
- [ ] `city_guides/src/routes.py` - `/api/categories` endpoint
- [ ] `city_guides/src/routes.py` - `/api/neighborhoods` endpoint

---

## 🔧 Automated Fixes (Run These First)

### One-Command Fixes
```bash
# Remove unused imports
pip install autoflake
autoflake --in-place --remove-all-unused-imports --recursive city_guides/

# Organize imports
pip install isort
isort city_guides/

# Format code
pip install black
black city_guides/

# Frontend formatting
cd frontend
npx prettier --write "src/**/*.{js,jsx}"
```

### Setup Pre-commit Hooks (Prevent Future Issues)
```bash
pip install pre-commit
cat << 'EOF' > .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
  - repo: https://github.com/PyCQA/autoflake
    rev: v2.1.1
    hooks:
      - id: autoflake
        args: ['--in-place', '--remove-all-unused-imports']
EOF

pre-commit install
```

- [ ] Create `.pre-commit-config.yaml`
- [ ] Run `pre-commit install`
- [ ] Test with `pre-commit run --all-files`

---

## 📊 Progress Tracking

**Completion Status:**
- 🔴 Critical: 0/3 complete (0%)
- 🟡 High: 0/4 complete (0%)
- 🟢 Medium: 0/4 complete (0%)

**Total Estimated Time:** 24 hours
**Completion Target:** 1 sprint (2 weeks)

---

## 🚀 Quick Wins (Can Do Right Now)

These have immediate impact with minimal risk:

1. **Remove hardcoded paths** (30 min) - CRITICAL blocker
2. **Move test files** (5 min) - Clean up root directory
3. **Run autoflake** (10 min) - Remove unused imports
4. **Remove console.log** (15 min) - Production readiness
5. **Add .env.example** (5 min) - Document configuration

**Total Quick Wins Time:** 65 minutes for 30% of issues fixed!

---

## 📝 Notes for LLMs

When implementing these fixes:

1. **One file at a time** - Don't change multiple files in parallel for same issue
2. **Test after each fix** - Run the app/tests to verify no breakage
3. **Commit frequently** - One commit per checklist item
4. **Use the full report** - See `CODE_REVIEW_OPTIMIZATION_REPORT.md` for detailed context
5. **Ask before big refactors** - Giant file splits should be reviewed by human first

---

**Last Updated:** 2026-02-05  
**See Full Report:** `CODE_REVIEW_OPTIMIZATION_REPORT.md`
