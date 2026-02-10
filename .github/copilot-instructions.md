# TravelLand Codebase Instructions for AI Agents

## Architecture Overview

TravelLand is a full-stack travel exploration app with:
- **Backend**: Quart async web framework (`city_guides/src/app.py`) serving REST API on port 5010
- **Frontend**: React/Vite app (`frontend/`) running on port 5174 with proxy to backend
- **Data Providers**: Multi-source venue/location data (GeoNames, OpenTripMap, Overpass/OSM, DuckDuckGo)
- **AI Chat**: Groq-powered Marco chat for personalized recommendations
- **Monitoring**: Auto-restart port monitoring (`city_guides/scripts/port_monitor.py`)

## Key Components

- **API Endpoints**: `/search` (venue search), `/semantic-search` (AI chat), `/api/locations/*` (geocoding)
- **Data Flow**: Frontend → Backend API → Providers → AI enrichment → Response
- **State Management**: React hooks for location selection, search results, chat state
- **External Services**: GeoNames API, OpenTripMap API, Groq AI, Wikivoyage data

## Developer Workflows

### Starting Services
```bash
# Start all services (backend, frontend, port monitor)
./dev.sh
```


### Testing Frontend Changes
- Use MCP/Playwright browser automation for UI testing
- Navigate to `http://localhost:5174`, test location selection → search → chat flow
- Check console for errors, verify data flows correctly
- **STRICT REQUIREMENT**: Always perform these tests immediately after proposing any frontend changes

### Server Restart Policy
- **ALWAYS** restart the relevant server (backend, frontend, Next.js, etc.) automatically after making changes that require a restart (code, config, env, or proxy changes).
- Do **NOT** ask the user for permission to restart—just do it as part of your workflow.
- After restart, verify the service is running and ready for testing.

### Backend Development
- Run with `hypercorn city_guides.src.app:app` (production) or `python -m city_guides.src.app` (dev)
- API responses include `venues`, `wikivoyage`, `costs`, `transport` arrays
- Use `.env` for API keys (GROQ_API_KEY, OPENTRIPMAP_KEY)

## Project Conventions

### Coding Style

**Python:**
- **Async-first:** All I/O operations use `async/await`
- **Type hints:** Use `typing` for function signatures
- **Error handling:** Explicit try/except with logging, never silent failures
- **No hardcoding:** All data dynamic via APIs; seed data only in `seeded_cities.json`
- **Normalization:** Preserve spaces in city names ("Hong Kong" not "HongKong")
- **Imports:** Group by stdlib, third-party, local; absolute imports preferred

**JavaScript/React:**
- **Hooks:** Functional components with `useState`, `useEffect`, `useCallback`
- **State updates:** Use functional updates when preserving existing state
  ```js
  setResults(prev => ({...prev, newData}))
  ```
- **API calls:** Centralized in `fetchAPI` utility with error handling
- **Console logging:** Use for debugging but clean up before production
- **File paths:** Always use absolute paths from filesystem root
- **Emojis:** Verify Unicode renders correctly (e.g., 🏛️ not corrupted)

### File Structure
- `city_guides/src/`: Backend code
- `frontend/src/`: React components
- `city_guides/providers/`: Data provider modules
- `tools/`: Service management scripts

### Naming Patterns
- Provider classes: `{Source}Provider` (e.g., `GeonamesProvider`)
- API responses: Snake_case keys (`quick_guide`, `wikivoyage`)
- Component props: CamelCase (`onLocationChange`, `selectedSuggestion`)

### Error Handling
- Backend: Quart error handlers, try/catch with JSON error responses
- Frontend: Console logging, fallback UI states
- Network: CORS enabled, proxy configuration in `frontend/vite.config.js`

### Dependencies
- Python: Quart, aiohttp, redis (caching)
- Node.js: React, Vite (dev server with proxy)
- Testing: Playwright for E2E, pytest for backend

## Integration Points

- **Frontend-Backend**: REST API with JSON payloads, proxied via Vite dev server
- **Multi-Provider**: Orchestrated search combining OSM, Wikivoyage, external APIs
- **AI Enrichment**: Groq API for chat responses, venue recommendations
- **Caching**: Redis for API responses, file-based for static data
- **Deployment**: Render.com with environment variables, auto-scaling

## Common Patterns

- **Async Operations**: Use `async/await` throughout (Quart routes, React effects)
- **Data Transformation**: Convert provider responses to unified venue format
- **UI Updates**: React state updates trigger re-renders, use useEffect for side effects
- **Logging**: Print to stderr for debugging, structured JSON responses
- **Configuration**: Environment variables for secrets, constants for app settings

## Key Files to Reference

- `city_guides/src/app.py`: Main backend app, API routes, provider orchestration
- `frontend/src/App.jsx`: Main React component, state management, API calls
- `city_guides/providers/`: Individual data provider implementations
- `./dev.sh`: Service startup script
- `frontend/vite.config.js`: Dev server proxy configuration

## Travel App Vision

**TravelLand** is an AI-powered city exploration platform that helps travelers:
- Discover authentic neighborhoods, venues, and hidden gems in any city
- Get personalized recommendations from AI travel assistant "Marco"
- Explore smart categories with semantic emoji icons (🏭 Industrial, 🎓 University, 🎭 Art)
- Access seeded fun facts for popular destinations (e.g., "Star Ferry since 1888" for Hong Kong)
- Navigate with neighborhood guides and venue cards

Core philosophy: **Dynamic data over hardcoding** — real facts or nothing, no fake generic content.

## Freemium Budget Constraints

### API Limits (Free Tiers)
| Provider | Limit | Usage |
|----------|-------|-------|
| Wikipedia | 500 req/hour | City summaries, full content |
| OpenTripMap | 5K req/day | Venues, attractions |
| GeoNames | 1K req/hour | Geocoding, city lookups |
| Overpass | Fair use | Neighborhoods, OSM data |
| Mapillary | 10K req/month | Street imagery |
| Render | 750 hrs/month | Hosting (sleeps after inactivity) |

### Optimization Strategies
- Aggressive caching (Redis/memory, 30s TTL for dev)
- Batch requests where possible
- Lazy loading for images
- Static export for frontend

## IDE Configuration

### VS Code
- Extensions: Python, ESLint, Prettier
- Settings: Format on save, 2-space indent

### Windsurf
- Cascade integration for AI-assisted coding
- Follows `.cursorrules` conventions

### CLine
- MCP tools for Playwright testing
- Command palette integration

### Universal
- **Line endings:** LF (Unix)
- **Encoding:** UTF-8 (critical for emoji support)
- **EditorConfig:** 2 spaces, no trailing whitespace

## Troubleshooting

### Server won't start
```bash
pkill -f hypercorn
./dev.sh
```

### Categories vanishing
Check `App.jsx` - must use `setResults(prev => ({...prev, ...}))`

### Emojis not rendering
Check `simple_categories.py` - Unicode must not be corrupted

### Neighborhoods timeout
Check `app.py` - timeout added, verify Overpass query simplified

### Build fails on Render
- Verify `render.yaml` has `mkdir -p city_guides/static`
- Check paths: run from `frontend/` for npm, copy to `../city_guides/static/`

### Redis not running
Set `DISABLE_CACHE=true` in environment</content>
<parameter name="filePath">/home/markm/TravelLand/.github/copilot-instructions.md