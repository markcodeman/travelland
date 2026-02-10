# Marco's Search Integration Guide

## Overview
Marco the Explorer now has access to multiple data sources for comprehensive search results:

### 1. **Web Search (DuckDuckGo)**
- Primary source for general queries
- Returns web snippets and articles
- Works for any type of query

### 2. **OpenStreetMap / Overpass**
- Local Point-of-Interest (POI) data
- **Activated when**: A city is provided AND query contains food/restaurant keywords
- **Returns**: Local restaurants, cafes, bars, food courts with:
  - Exact coordinates (lat/lon)
  - Address and opening hours (from OSM tags)
  - Website/contact info (when available)
  - OSM map links
- **Smart filtering**: Excludes major chain restaurants for authentic local recommendations

### 3. **WikiVoyage (planned)**
- Travel guide articles (not yet implemented)
- Would provide background info and cultural context
- Currently falls back to Wikipedia for city summaries

### 4. **OpenTripMap** (ready for integration)
- Points of interest with ratings
- Not yet integrated but available in environment

## How Marco Uses This

When Marco processes a user query:

```python
# In semantic.py, Marco now calls:
results = search_provider.duckduckgo_search(query, max_results=5)
```

### Example Queries

**"Where can I find authentic pizza in Rome?"**
- DuckDuckGo: Generic pizza articles
- **OSM/Overpass**: Local pizzerias in Rome with addresses ← Most useful!
- Wikipedia: Roman cuisine background (fallback)

**"Tell me about sushi culture"**
- DuckDuckGo: Articles and guides
- Wikipedia: Travel info on sushi destinations (fallback)
- (OSM skipped—no city provided)

**"Best restaurants near Paris"** (if city=Paris)
- DuckDuckGo: Web reviews
- **OSM/Overpass**: 100+ actual restaurants in Paris with coordinates
- Wikipedia: French cuisine guide (fallback)

## Testing

```bash
# Test web search programmatically
from city_guides.providers.search_provider import duckduckgo_search
results = duckduckgo_search("best pizza in Rome", max_results=5)

# Test OSM restaurants directly
from city_guides.providers.overpass_provider import discover_restaurants
restaurants = discover_restaurants("Paris", cuisine="italian")
```

## Data Quality

### OpenStreetMap (Highest for Local Data)
- Real addresses and coordinates
- Crowdsourced, community-maintained
- Most accurate for local venues
- Best for: Finding specific restaurants/cafes/bars

### DuckDuckGo (Best for General Info)
- Web aggregation from multiple engines
- Fast, broad coverage
- Good for: Background, reviews, recipes

### WikiVoyage (planned)
- Curated travel guides (not yet implemented)
- Would provide cultural and historical info
- Currently falls back to Wikipedia

## Future Enhancements

- [ ] Implement WikiVoyage integration via Wikimedia Enterprise API
- [ ] Integrate OpenTripMap for rated POIs
- [ ] Add caching to reduce API calls
- [ ] Support multiple languages from WikiVoyage (27 available)
- [ ] Extract phone numbers/hours from OSM tags
- [ ] Merge duplicate results across sources
