# TravelLand Python Async & Config Best Practices

## Asyncio Event Loop Management
- **Always use `AsyncRunner.run(coro)`** for running coroutines from sync code. Never use `asyncio.get_event_loop()`, `new_event_loop()`, or `run_until_complete()` directly in production code.
- **Never create or set event loops manually** except in test utilities.
- **Avoid `asyncio.run()` in library code**; use it only in top-level scripts or CLI entrypoints.
- **For tests**, prefer `pytest-asyncio` or `AsyncRunner.run()` to avoid event loop conflicts.
- **No global mutable state**: All async resources (sessions, caches) must be injected or context-managed.

## Configuration Management
- **Centralize all config in `config.py`**. Never use scattered `os.getenv()` calls.
- **Use type-safe config dataclasses** for timeouts, providers, cache, and logging.
- **Validate all config on startup**; fail fast if required env vars are missing or invalid.
- **Mask secrets in logs/output**; never print or expose full API keys or .env contents.
- **No hardcoded data**: All static data must be in versioned seed files, never in code (except for controlled/test-only seeds).

## Fun Facts Implementation Best Practices

### Dynamic Content Generation
- **Always fetch dynamic facts**: Never hardcode fun facts in production code. Use Wikipedia/DDGS for fresh content.
- **Prioritize interesting content**: Filter for facts with numbers, unique characteristics, or historical significance.
- **Diverse sources**: Combine Wikipedia summaries, DDGS results, and Wikidata for comprehensive facts.
- **Quality filtering**: Exclude generic definitions and prioritize specific, engaging content.

### Implementation Details
The `/api/fun-fact` endpoint demonstrates best practices:

**Key Features:**
- **Dynamic fact gathering**: Fetches from Wikipedia, DDGS, and Wikidata
- **Quality filtering**: Prioritizes facts with numbers, superlatives, or unique characteristics
- **Fallback chain**: Wikipedia → DDGS → Wikidata → Generic fallback
- **Error handling**: Graceful recovery from API failures with logging
- **Caching**: Uses seeded facts for frequently requested cities

**Interesting Content Patterns:**
```python
# Prioritize facts with these characteristics
INTERESTING_PATTERNS = [
    'oldest', 'newest', 'largest', 'smallest', 'tallest',
    'first', 'only', 'unique', 'famous', 'world',
    'built in', 'founded', 'established', 'created',
    'known as', 'called', 'renowned', 'legend', 'history',
    'medieval', 'century', 'population', 'square kilometers',
    'miles', 'height', 'length', 'width', 'deepest', 'highest',
    'lowest', 'longest', 'shortest', 'fastest', 'slowest',
    'most visited', 'popular', 'UNESCO', 'world heritage',
    'historical significance', 'cultural importance',
    'architectural style', 'famous for'
]
```

**Usage:**
```python
# Example from /api/fun-fact endpoint
if has_interest and not is_definition:
    fun_fact_candidates.append(sentence)
```

### Quality Assurance
- **Avoid generic facts**: Exclude sentences like "Paris is a city..."
- **Deduplicate**: Remove duplicate facts from multiple sources
- **Trim to size**: Keep facts between 40-200 characters for readability
- **Validate sources**: Ensure facts come from reputable sources (Wikipedia, Wikidata)

## Mock/Test Data
- **No mock POI data in production paths**. All mock data must be isolated to test files or explicit test helpers.
- **Seed data**: Only use for bootstrapping, with clear schema and versioning. Log all seed fallbacks.

## General Python Practices
- **Async-first**: All I/O and network code must be async/await.
- **Type hints required** for all public functions and methods.
- **Explicit error handling**: Use try/except with logging; never silent failures.
- **No singletons except immutable config**: Use dependency injection or contextvars for shared state.
- **No global dicts/lists for runtime data**: Use context, request, or explicit stores.

## Logging
- **Configure logging via `config.py`** only.
- **No print statements in production** (except for startup warnings/errors).
- **Log at appropriate levels**: DEBUG for dev, INFO for prod, WARNING/ERROR for issues.

## Security
- **Never expose secrets**: Mask all API keys in logs/output. Never display or cat .env files.
- **Enforce secret masking in all scripts and outputs.**

---

## React/Frontend Component Best Practices

### Component Design
- **Unified visual components**: Create reusable components like `LocationHero` that consolidate multiple similar functionalities (e.g., hero images, loading states, overlays).
- **Prop-driven design**: Components should be configurable via props rather than internal state or hardcoded values.
- **Accessibility first**: Include proper ARIA labels, semantic HTML, and keyboard navigation support.
- **Responsive design**: Use CSS media queries and flexible layouts for mobile-first responsive behavior.

### LocationHero Component Example
The `LocationHero` component demonstrates best practices for image-heavy components:

**Key Features:**
- **Multiple image cycling**: Automatically cycles through image arrays every 8 seconds
- **Loading states**: Shows spinner and loading text during image fetch
- **Error handling**: Graceful fallback to placeholder with location icon and text
- **Accessibility**: Proper ARIA labels and semantic image roles
- **Performance**: Lazy loading, image preloading, and opacity transitions
- **Responsive**: Adapts height and layout for mobile/tablet/desktop

**Props Interface:**
```javascript
{
  location: { name, country, state },     // Location metadata
  images: Array<string>,                  // Image URLs array
  loading: boolean,                       // Loading state
  onError: Function,                      // Error callback
  className: string                       // Additional CSS classes
}
```

**Usage:**
```javascript
<LocationHero
  location={{ name: "Granada", country: "Spain" }}
  images={["url1.jpg", "url2.jpg"]}
  loading={false}
  onError={() => console.log("Image failed to load")}
/>
```

### TypeScript Interface Best Practices
- **Comprehensive type definitions**: Define interfaces for all data structures used across components
- **Progressive enhancement**: Start with basic interfaces and extend for specialized use cases
- **Optional properties**: Use optional fields (`?:`) for data that may not always be available
- **Union types**: Use union types for enumerated values and polymorphic data
- **Function signatures**: Define callback function types explicitly

### Location Types Example
The `location.js` file provides comprehensive TypeScript interfaces for location-related data:

**Core Interfaces:**
```typescript
// Basic location information
interface Location {
    name: string;
    country?: string;
    state?: string;
    countryCode?: string;
    stateCode?: string;
}

// Extended with coordinates
interface LocationWithCoords extends Location {
    lat?: number;
    lon?: number;
}

// Neighborhood data structure
interface Neighborhood {
    name: string;
    description?: string;
    image?: string;
    category?: string;
    population?: number;
    attractions?: string[];
}

// Image metadata with attribution
interface ImageSource {
    url: string;
    alt?: string;
    credit?: string;
    width?: number;
    height?: number;
    type?: 'hero' | 'thumbnail' | 'placeholder';
}
```

**Content Types:**
```typescript
// Union type for content sections
type ContentSectionType = 
    | 'fun_fact'
    | 'neighborhood_info'
    | 'search_results'
    | 'city_suggestions'
    | 'location_input'
    | 'custom';

// Configuration interface
interface ContentSection {
    type: ContentSectionType;
    title?: string;
    content: string | React.ReactNode;
    icon?: string;
    actions?: ContentAction[];
    loading?: boolean;
    error?: string;
}

// Action button interface
interface ContentAction {
    label: string;
    onClick: () => void;
}
```

**Benefits:**
- **Type safety**: Prevents runtime errors from malformed data
- **IDE support**: Autocomplete and refactoring assistance
- **Documentation**: Self-documenting code with clear contracts
- **Reusability**: Interfaces can be imported across multiple components
- **Maintainability**: Centralized type definitions for consistent data structures

---

_See also: `AGENTS.md`, `.github/copilot-instructions.md`, and code comments for further guidance._
