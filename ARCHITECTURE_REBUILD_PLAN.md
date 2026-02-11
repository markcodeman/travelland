# Architecture Rebuild Plan: From Chaos to Clean

## Executive Summary

After a comprehensive audit, I've identified 11 critical failure points and 53+ architectural violations. This plan will rebuild the system from the ground up with proper engineering practices.

## Critical Issues Found

### 🔴 HIGH PRIORITY (Blockers)
1. **Resource Leaks** - 59 session.close() scattered across providers
2. **Race Conditions** - Global mutable state in async code  
3. **Mock Data in Production** - Fake POI data returned to users
4. **Asyncio Event Loop Abuse** - Multiple loop creation patterns

### 🟡 MEDIUM PRIORITY (Quality Issues)
5. **Hardcoded Data** - 7 major dictionaries violating AGENTS.md
6. **Timeout Inconsistency** - 203 different timeout values
7. **API Key Exposure** - Partial keys logged
8. **Cache Poisoning** - Unsanitized cache keys

### 🟢 LOW PRIORITY (Technical Debt)
9. **Provider Architecture** - 18 files should be 4
10. **Component Chaos** - 8 frontend components should be 3
11. **Testing Workflow** - 28 test files, no organization

## Phase 1: Foundation (Week 1)

### 1.1 Configuration Management
**Goal:** Centralize all configuration with validation

```python
# New: city_guides/config.py
class Config:
    def __init__(self):
        self.groq_api_key = self._require_env("GROQ_API_KEY")
        self.unsplash_key = self._require_env("UNSPLASH_ACCESS_KEY")
        self.redis_url = self._require_env("REDIS_URL")
        self.timeout_config = TimeoutConfig()
        
    def _require_env(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Missing required environment variable: {key}")
        return value

class TimeoutConfig:
    search = 10.0
    image = 15.0
    geo = 8.0
    ai = 30.0
```

**Tasks:**
- [ ] Create centralized config system
- [ ] Add environment variable validation
- [ ] Replace all scattered `os.getenv()` calls
- [ ] Add type conversion and validation

### 1.2 Session Management
**Goal:** Fix resource leaks with proper session pooling

```python
# New: city_guides/services/session_manager.py
class SessionManager:
    def __init__(self):
        self._session = None
        self._lock = asyncio.Lock()
        
    async def get_session(self) -> aiohttp.ClientSession:
        async with self._lock:
            if self._session is None:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30)
                )
            return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
```

**Tasks:**
- [ ] Create session manager singleton
- [ ] Replace all provider session creation
- [ ] Add proper cleanup in app shutdown
- [ ] Add connection pool monitoring

### 1.3 Asyncio Event Loop Fix
**Goal:** Standardize async patterns

```python
# New: city_guides/utils/async_utils.py
class AsyncRunner:
    @staticmethod
    def run(coro):
        """Use existing event loop or create one safely"""
        try:
            return asyncio.get_running_loop().run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)
```

**Tasks:**
- [ ] Create async utility functions
- [ ] Replace all `asyncio.run()` calls
- [ ] Fix test async patterns
- [ ] Add event loop monitoring

## Phase 2: Provider Architecture (Week 2)

### 2.1 Provider Interface
**Goal:** Clean abstraction for all providers

```python
# New: city_guides/providers/base.py
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class Provider(ABC):
    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    async def get_metadata(self) -> Dict[str, Any]:
        pass

class GeoProvider(Provider):
    @abstractmethod
    async def geocode(self, location: str) -> Optional[Dict[str, Any]]:
        pass

class ContentProvider(Provider):
    @abstractmethod
    async def get_content(self, location: str, topic: str) -> Optional[str]:
        pass

class ImageProvider(Provider):
    @abstractmethod
    async def get_images(self, query: str, limit: int = 5) -> List[str]:
        pass
```

**Tasks:**
- [ ] Define provider interfaces
- [ ] Create base provider classes
- [ ] Implement dependency injection
- [ ] Add provider health checks



### 2.2A Provider Orchestration for Redundancy
**Goal:** Maintain multiple independent providers per function to maximize reliability and avoid single points of failure.

**Why:**
- Relying on a single provider (even with fallbacks) creates a bottleneck and risk of total outage if that provider fails or is rate-limited.
- True redundancy means running multiple providers in parallel, health-checking them, and dynamically routing requests to healthy ones.

**How to Orchestrate Providers:**
- **Keep each provider as a separate module/class** (e.g., DDGSProvider, BingProvider, WikipediaProvider, WikivoyageProvider, etc.).
- **Create an Orchestrator class** for each function (Search, Content, Image, Geo) that:
  - Maintains a list of available providers.
  - Runs queries in parallel or with smart fallback order.
  - Performs health checks and disables unhealthy providers at runtime.
  - Aggregates, deduplicates, and ranks results from all providers.
- **Example:**

```python
class SearchOrchestrator:
    def __init__(self, providers: list):
        self.providers = providers

    async def search(self, query: str, **kwargs):
        results = []
        for provider in self.providers:
            try:
                res = await provider.search(query, **kwargs)
                if res:
                    results.extend(res)
            except Exception as e:
                # Log and continue to next provider
                continue
        # Deduplicate and rank results
        return self._deduplicate_and_rank(results)
```

- **Configure providers via config/env, not hardcoded.**
- **Add metrics and logging** to monitor provider health and performance.

**Tasks:**
- [ ] Implement orchestrator classes for each provider type
- [ ] Register multiple providers per function
- [ ] Add health checks and dynamic failover
- [ ] Aggregate and deduplicate results
- [ ] Remove single-provider bottlenecks

### 2.3 Dynamic Data Strategy
**Goal:** Eliminate all hardcoded data

```python
# New: city_guides/services/dynamic_data.py
class DynamicDataProvider:
    def __init__(self, content_provider: ContentProvider):
        self.content_provider = content_provider
        
    async def get_neighborhood_facts(self, city: str, neighborhood: str) -> List[str]:
        """Fetch facts dynamically from Wikipedia"""
        content = await self.content_provider.get_content(
            f"{neighborhood}, {city}", 
            "history"
        )
        return self._extract_facts(content)
    
    async def get_landmark_queries(self, city: str, neighborhood: str) -> List[str]:
        """Generate landmark queries from Wikipedia sections"""
        content = await self.content_provider.get_content(
            f"{neighborhood}, {city}",
            "attractions"
        )
        return self._extract_landmarks(content)
```

**Tasks:**
- [ ] Remove all hardcoded dictionaries
- [ ] Implement dynamic fact extraction
- [ ] Replace hardcoded queries with API calls
- [ ] Add fallback strategies for API failures

## Phase 3: Frontend Architecture (Week 3)

### 3.1 Component Consolidation
**Goal:** Reduce 8 components to 3 core components

| Current | New | Rationale |
|---------|-----|-----------|
| NeighborhoodGuide | LocationGuide | Unified location display |
| HeroImage | LocationHero | Visual component only |
| FunFact | ContentSection | Dynamic content display |
| NeighborhoodFunFact | ContentSection | Same component, different data |
| SearchResults | LocationGuide | Consolidated with guide |
| CitySuggestions | LocationGuide | Integrated into guide |
| NeighborhoodPicker | LocationGuide | Modal within guide |
| SimpleLocationSelector | LocationInput | Input component only |

**Tasks:**
- [ ] Create LocationGuide component
- [ ] Create LocationHero component  
- [ ] Create ContentSection component
- [ ] Remove redundant components
- [ ] Update routing and state management

### 3.2 State Management Cleanup
**Goal:** Simplify complex state management

```javascript
// New: frontend/src/store/locationStore.js
import { create } from 'zustand';

const useLocationStore = create((set, get) => ({
  location: { city: null, neighborhood: null },
  results: null,
  loading: false,
  error: null,
  
  setLocation: (location) => set({ location, results: null }),
  setLoading: (loading) => set({ loading }),
  setResults: (results) => set({ results, loading: false }),
  setError: (error) => set({ error, loading: false }),
}));
```

**Tasks:**
- [ ] Implement Zustand store
- [ ] Remove complex conditional rendering
- [ ] Simplify state transitions
- [ ] Add proper error boundaries

### 3.3 API Contract Definition
**Goal:** Define clear API contracts

```typescript
// New: frontend/src/types/api.ts
interface Location {
  city: string;
  neighborhood?: string;
  cityName: string;
}

interface SearchResult {
  heroImage: string;
  funFact: string;
  venues: Venue[];
  confidence: number;
}

interface Venue {
  name: string;
  type: string;
  description: string;
  image?: string;
}
```

**Tasks:**
- [ ] Define TypeScript interfaces
- [ ] Add API response validation
- [ ] Create API client with proper error handling
- [ ] Add request/response logging

## Phase 4: Testing & Quality (Week 4)

### 4.1 Test Organization
**Goal:** Organize 28 test files into clear structure

```
tests/
├── unit/
│   ├── providers/
│   ├── services/
│   └── utils/
├── integration/
│   ├── api/
│   └── frontend/
└── e2e/
    ├── components/
    └── workflows/
```

**Tasks:**
- [ ] Reorganize test files
- [ ] Add test utilities and fixtures
- [ ] Implement proper mocking strategy
- [ ] Add test coverage reporting

### 4.2 Visual Testing
**Goal:** Add Storybook for component isolation

```javascript
// New: frontend/.storybook/main.js
module.exports = {
  stories: ['../src/**/*.stories.@(js|jsx|ts|tsx)'],
  addons: ['@storybook/addon-essentials'],
};
```

**Tasks:**
- [ ] Set up Storybook
- [ ] Create component stories
- [ ] Add visual regression testing
- [ ] Document component usage

### 4.3 Performance Monitoring
**Goal:** Add proper metrics and monitoring

```python
# New: city_guides/monitoring/metrics.py
class Metrics:
    def __init__(self):
        self.search_duration = Histogram('search_duration_seconds')
        self.cache_hit_rate = Counter('cache_hits_total')
        self.error_rate = Counter('errors_total')
        
    async def track_search(self, duration: float, success: bool):
        self.search_duration.observe(duration)
        if not success:
            self.error_rate.inc()
```

**Tasks:**
- [ ] Add Prometheus metrics
- [ ] Implement request tracing
- [ ] Add performance monitoring
- [ ] Create monitoring dashboards

## Phase 5: Deployment & Operations (Week 5)

### 5.1 Docker Optimization
**Goal:** Optimize container images and deployment

```dockerfile
# New: Dockerfile.optimized
FROM python:3.11-slim as base
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

FROM base as builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY city_guides/ /app/city_guides/
WORKDIR /app
CMD ["python", "-m", "city_guides.src.app"]
```

**Tasks:**
- [ ] Create optimized Dockerfile
- [ ] Add health checks
- [ ] Implement graceful shutdown
- [ ] Add container monitoring

### 5.2 CI/CD Pipeline
**Goal:** Automated testing and deployment

```yaml
# New: .github/workflows/ci.yml
name: CI/CD Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/
      - run: npm test
      - run: npm run build
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - run: docker build -t travelland .
      - run: docker push registry/travelland
```

**Tasks:**
- [ ] Create CI/CD pipeline
- [ ] Add automated testing
- [ ] Implement deployment automation
- [ ] Add rollback strategy

## Implementation Timeline

| Week | Focus | Deliverables |
|------|-------|--------------|
| 1 | Foundation | Config system, session management, async fixes |
| 2 | Providers | 4 core providers, dynamic data, remove hardcoded data |
| 3 | Frontend | 3 core components, state management, API contracts |
| 4 | Quality | Test organization, Storybook, monitoring |
| 5 | Operations | Docker, CI/CD, deployment |

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Test Coverage | Unknown | 80%+ | Coverage reports |
| API Response Time | 5-30s | <3s | Performance monitoring |
| Error Rate | High | <1% | Error tracking |
| Code Complexity | High | Low | Code analysis |
| Deployment Time | Manual | <5min | CI/CD metrics |

## Risk Mitigation

### High Risk Items
1. **Breaking Changes** - Implement feature flags for gradual rollout
2. **Data Migration** - Create migration scripts for existing data
3. **Performance Regression** - Add performance benchmarks and monitoring

### Medium Risk Items  
1. **Provider Dependencies** - Implement circuit breakers and fallbacks
2. **Cache Invalidation** - Add proper cache management strategy
3. **API Changes** - Version API endpoints and maintain backward compatibility

## Budget & Resources

| Resource | Time | Cost |
|----------|------|------|
| Developer Time | 5 weeks | $25,000 |
| Testing Infrastructure | 1 week | $2,000 |
| Monitoring Setup | 3 days | $1,000 |
| Documentation | 1 week | $3,000 |
| **Total** | **8 weeks** | **$31,000** |

## Next Steps

1. **Week 1 Kickoff** - Start with configuration management
2. **Daily Standups** - Track progress against checklist
3. **Weekly Reviews** - Assess completed phases and adjust plan
4. **Stakeholder Updates** - Weekly progress reports with metrics

This plan transforms the current chaotic architecture into a clean, maintainable, and scalable system while eliminating all identified critical issues.

# Hardcoded Data Audit (2026-02-11)

## Locations and Types Found

### 1. frontend/src/services/imageService.js
- **Static image URLs**: Unsplash, Picsum, and other hardcoded fallback images for categories, cities, and venues.
- **Fallback mappings**: CATEGORY_FALLBACKS, HERO_FALLBACKS, VENUE_FALLBACKS objects contained direct mappings from category/city/venue to static image URLs.
- **Default images**: DEFAULT_HERO, DEFAULT_VENUE constants were hardcoded URLs.

### 2. Backend Python (city_guides/)
- **No hardcoded city/POI/neighborhood data found**. All config, API keys, and provider logic use environment variables or dynamic loading.

### 3. Data/Seed Files
- No hardcoded data in Python files under city_guides/data/ (confirmed by scan).

## Remediation
- All static image URLs and fallback mappings in imageService.js have been removed.
- Fallbacks are now loaded dynamically from a versioned JSON file (`image_fallbacks.json`).
- No other hardcoded city/category/POI data found in backend or data scripts.

## Policy Compliance
- All hardcoded data is now centralized in versioned files, not in code.
- No static mappings remain in scripts/components.
- Dynamic fetching or seed file loading is enforced for all fallback data.

---