# TRAVELLAND CODING STANDARDS

## CODE SIZE & REFACTORING

### Line Count Guidelines
- **< 2000 lines:** Healthy size
- **2000-2500 lines:** Monitor - consider refactoring soon
- **2500+ lines:** Definitely needs refactoring
- **3000+ lines:** Critical - immediate refactoring required

### When to Refactor
- Can't locate code quickly
- Files feel "heavy" or unwieldy
- Duplicate code blocks > 10 lines
- Functions > 50 lines
- Mixed concerns in single file
- Routes > 100 lines each

### Monitoring Commands
```bash
# Check line count periodically
wc -l city_guides/src/app.py

# Find large functions
grep -n "def " app.py | awk 'length($0) > 50'

# Check for duplicates
grep -n "city_mappings" app.py
```

## MODULAR ARCHITECTURE

### Directory Structure
```
city_guides/src/
├── app.py              # Core Flask app (< 2500 lines)
├── services/           # Business logic
│   ├── location.py     # City mappings, fuzzy matching
│   ├── learning.py     # Weights, hemisphere detection
│   └── weather.py      # Weather-related services
├── utils/              # Pure functions
│   ├── seasonal.py     # Seasonal logic
│   ├── distance.py     # Levenshtein, calculations
│   └── cache.py        # Caching utilities
└── routes/             # API endpoints (if needed)
    ├── location.py     # Location-related routes
    ├── weather.py      # Weather routes
    └── health.py       # Health check routes
```

### Service Separation Rules
- **services/**: Business logic with state
- **utils/**: Pure functions, no side effects
- **routes/**: HTTP handlers only
- **app.py**: Core setup, imports, startup

## CODE QUALITY

### Function Guidelines
- **< 20 lines:** Ideal
- **20-50 lines:** Acceptable
- **50+ lines:** Break down

### Import Organization
1. Standard library imports
2. Third-party imports  
3. Local service imports
4. Local utility imports

### Error Handling
- Always log exceptions with `app.logger.exception()`
- Return meaningful error messages
- Use proper HTTP status codes

## TESTING & VERIFICATION

### After Refactoring Checklist
- [ ] All endpoints respond correctly
- [ ] No console errors
- [ ] Line count reduced
- [ ] Imports working
- [ ] Core functionality preserved

### Test Commands
```bash
# Test key endpoints
curl -X POST http://localhost:5010/api/location-suggestions \
  -H "Content-Type: application/json" \
  -d '{"query": "pa"}'

# Check backend health
curl http://localhost:5010/healthz
```

## MAINTENANCE

### Review Schedule
- **Monthly:** Check line count
- **Quarterly:** Full architecture review
- **When adding features:** Assess impact on size

### Decision Framework
1. **Is it working?** → Don't break it
2. **Is it hard to maintain?** → Refactor
3. **Is it reusable?** → Extract to service/util
4. **Is it pure logic?** → Move to utils
5. **Is it business logic?** → Move to services

## PRAGMATIC PRINCIPLES

- **Working code > perfect architecture**
- **Incremental changes > big rewrites**
- **Test each step** → Verify functionality
- **Document the why** → Not just the what
- **Prevent over-engineering** → Keep it simple

## TRIGGERS FOR ACTION

### Immediate Refactoring Required
- File > 3000 lines
- Duplicate code > 50 lines
- Function > 100 lines
- Multiple concerns mixed

### Consider Refactoring Soon
- File > 2500 lines
- Can't find code in 10 seconds
- New features feel "forced" in

### Monitor Only
- File > 2000 lines
- Minor duplication
- Slightly complex functions
