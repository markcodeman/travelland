# Seeded Data Governance

## Overview
This directory contains curated seed data for TravelLand, providing fallback data when dynamic providers are unavailable or rate-limited.

### File Structure
- `seeded_cities.json` - City metadata with coordinates, population, and fun facts
- `europe/` - European city neighborhood data by country (France, Italy, Spain, Romania, etc.)
- `north_america/` - North American city neighborhood data (USA, Mexico)
- `banner_cache.json` - Cached banner images for cities
- `hardcode_candidates.json` - Candidate cities for seed data expansion

## Neighborhood Seed Data

### Schema
Each neighborhood JSON file follows this structure:
```json
{
  "country": "CountryName",
  "cities": {
    "CityName": [
      {
        "name": "Neighborhood Name",
        "description": "Detailed description with highlights",
        "type": "category"
      }
    ]
  }
}
```

### Supported Categories
- `historic` - Historic districts and old towns
- `culture` - Cultural centers, museums, arts districts
- `trendy` - Hipster areas, modern neighborhoods
- `shopping` - Shopping districts and luxury areas
- `food` - Food markets and culinary hubs
- `nightlife` - Entertainment and bar districts
- `beach` - Coastal and beach areas
- `waterfront` - Harbors and riverside areas
- `nature` - Parks and green spaces
- `residential` - Residential neighborhoods
- `market` - Traditional market areas
- `modern` - Business districts and contemporary areas

### Adding New Cities
1. Identify the appropriate country file in `europe/` or `north_america/`
2. Add city entry with 4-20 neighborhoods
3. Include diverse categories for each city
4. Provide authentic, specific descriptions (no generic content)
5. Test with `dynamic_neighborhoods.py` to ensure proper loading

### Current Coverage
**Europe**: Austria, Belgium, Czech Republic, Denmark, Finland, France, Germany, Greece, Italy, Netherlands, Norway, Portugal, Romania, Spain, Sweden, Switzerland, UK

**North America**: USA (major cities + coastal towns like Ocracoke), Mexico (Oaxaca, Mexico City, etc.)

## Regeneration

### Cities (seeded_cities.json)
- Use `tools/generate_seeded_cities.py --count 500 --geonames <GEONAMES_USERNAME>` to regenerate
- Enriches local candidate names with GeoNames data when username provided

### Neighborhoods
- Manually curate neighborhood data for authenticity
- Prioritize lesser-known tourist destinations (Bran Castle, Ocracoke NC, etc.)
- Verify descriptions are accurate and not generic

## Operational Notes
- Seeds are fallback for UX flows (dropdowns, offline demos, API failures)
- Always commit changes with version bump and `last_updated` field
- Add tests to assert schema compatibility
- Application logs when serving from seed data for auditing

## Monitoring
- Check logs for "Found X neighborhoods for {city} from seed data"
- Warning logged when falling back to generic neighborhoods
- Track coverage: `dynamic_neighborhoods.py` cache tracks all loaded cities
