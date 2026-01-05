# Marco's Search Integration Guide

## Overview
Marco the Explorer now has access to multiple data sources for comprehensive search results:

### 1. **Web Search (Searx/DuckDuckGo)**
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

### 3. **WikiVoyage (via Wikimedia Enterprise API)**
- Travel guide articles
- Background info and cultural context
- Activated as fallback when other sources have gaps

### 4. **OpenTripMap** (ready for integration)
- Points of interest with ratings
- Not yet integrated but available in environment

## How Marco Uses This

When Marco processes a user query:

```python
# In semantic.py, Marco now calls:
results = search_provider.combined_search(search_query, max_results=8, city=city)
```

### Example Queries

**"Where can I find authentic pizza in Rome?"**
- Searx: Generic pizza articles
- **OSM/Overpass**: Local pizzerias in Rome with addresses ← Most useful!
- WikiVoyage: Roman cuisine background

**"Tell me about sushi culture"**
- Searx: Articles and guides
- WikiVoyage: Travel info on sushi destinations
- (OSM skipped—no city provided)

**"Best restaurants near Paris"** (if city=Paris)
- Searx: Web reviews
- **OSM/Overpass**: 100+ actual restaurants in Paris with coordinates
- WikiVoyage: French cuisine guide

## Testing

```bash
# Test combined search programmatically
python test_combined.py

# Test individual sources
from search_provider import combined_search, overpass_provider

# Get OSM restaurants directly
restaurants = overpass_provider.discover_restaurants("Paris", cuisine="italian")

# Get WikiVoyage articles
from search_provider import wikivoyage_search
articles = wikivoyage_search("french cuisine")
```

## Data Quality

### OpenStreetMap (Highest for Local Data)
- Real addresses and coordinates
- Crowdsourced, community-maintained
- Most accurate for local venues
- Best for: Finding specific restaurants/cafes/bars

### Searx (Best for General Info)
- Web aggregation from multiple engines
- Fast, broad coverage
- Good for: Background, reviews, recipes

### WikiVoyage (Best for Travel Context)
- Curated travel guides
- Cultural and historical info
- Good for: Understanding cuisine, culture, travel tips

## Future Enhancements

- [ ] Integrate OpenTripMap for rated POIs
- [ ] Add caching to reduce API calls
- [ ] Support multiple languages from WikiVoyage (27 available)
- [ ] Extract phone numbers/hours from OSM tags
- [ ] Merge duplicate results across sources
