# Backend Search Failure Fix Plan

## Problem Summary
All 12 venue categories fail with "search_failed" error while 4 RAG-only categories work fine.

## Root Cause Analysis

### 1. Provider Import Failures (CRITICAL)
**File**: `city_guides/providers/multi_provider.py` (Lines 12-24)
```python
overpass_provider = None
try:
    from city_guides.providers import overpass_provider  # May fail
except Exception as e:
    overpass_provider = None  # Silently fails, no POIs returned
```

**Impact**: If `overpass_provider` is None, no venue searches work.

### 2. Nested Event Loop Issues
**File**: `city_guides/src/persistence.py` (Lines 1424-1432)
```python
# Creates NEW event loop while already in async context
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    city_coords = loop.run_until_complete(geocode_city(city))
```

**Impact**: Quart runs in async context; creating nested event loops causes failures.

### 3. Missing Error Propagation
**File**: `city_guides/src/routes.py` (Lines 85-87)
```python
except Exception as e:
    app.logger.exception('Search failed')
    return jsonify({"error": "search_failed", "details": str(e)}), 500
```

**Impact**: Generic error masks actual failure reason.

### 4. Category Mapping Gaps
**File**: `city_guides/src/persistence.py` (Lines 1470-1520)
Missing mappings for test categories:
- `literary_heritage` → maps to `historic` (works)
- `music_heritage` → maps to `historic` (works)  
- `industrial_heritage` → maps to `historic` (works)
- `entertainment` → NOT in mapping (falls through to raw `q` value)

## Fix Steps

### Phase 1: Diagnostic Logging (5 min)
Add immediate visibility into what's failing:

```python
# In multi_provider.py, add at top of async_discover_pois():
print(f"[CRITICAL] overpass_provider is {'AVAILABLE' if overpass_provider else 'NONE'}")
```

### Phase 2: Fix Event Loop Handling (15 min)
Replace nested event loop pattern with proper async/await:

```python
# persistence.py - Remove nested loops
# BEFORE:
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
city_coords = loop.run_until_complete(geocode_city(city))

# AFTER:
city_coords = await geocode_city(city)
```

### Phase 3: Fix Import Path (5 min)
```python
# multi_provider.py - Make imports more robust
try:
    from city_guides.providers.overpass_provider import async_discover_pois as op_discover
    overpass_provider = ...
except Exception as e:
    print(f"[FATAL] Cannot import overpass_provider: {e}")
    raise  # Don't silently fail
```

### Phase 4: Add Missing Category Mappings (5 min)
```python
# persistence.py - Add missing mappings
"entertainment": "amenity",  # or "theatre"
"theatre": "amenity",
"theater": "amenity",
```

### Phase 5: Fix Routes Error Handling (10 min)
```python
# routes.py - Better error details
except Exception as e:
    import traceback
    app.logger.error(f"Search error: {e}\n{traceback.format_exc()}")
    return jsonify({
        "error": "search_failed",
        "details": str(e),
        "traceback": traceback.format_exc() if app.debug else None
    }), 500
```

## Quick Test After Each Phase
```bash
python tools/test_marco_categories.py 2>&1 | head -50
```

## Success Criteria
- [ ] All 12 venue categories return 200 status
- [ ] At least 50% return actual venues (not empty arrays)
- [ ] No "search_failed" errors in output

## Estimated Time: 40 minutes
