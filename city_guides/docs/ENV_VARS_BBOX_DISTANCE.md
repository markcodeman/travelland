# TravelLand: Environment Variables for Geographic Accuracy

## Search/BBox/Distance Controls

- `CITY_MAX_DISTANCE_KM` (default: 40)
  - Maximum allowed distance (in km) from city center for venues to be included in search results. Venues farther than this are filtered out.
- `CITY_DISTANCE_DECAY_KM` (default: 20)
  - Distance (in km) at which the distance-based score for venues decays to zero. Venues closer to the center are ranked higher.
- `CITY_FALLBACK_BBOX_KM` (default: 10)
  - When geocoding fails or returns a very large bounding box, a conservative bbox of this radius (in km) is used around the best available city coordinates. Prevents state/region-wide queries and rural results.

## Usage
- Set these variables in your `.env` file or deployment environment to tune search radius and filtering for your deployment.
- Example `.env` snippet:

```
CITY_MAX_DISTANCE_KM=30
CITY_DISTANCE_DECAY_KM=15
CITY_FALLBACK_BBOX_KM=8
```

## Rationale
- These controls ensure that city searches do not return venues from rural areas or the entire state/region, especially for cities like New York (NYC) where state-level geocoding is too broad.
- Tightening the bbox and filtering by distance ensures geographic accuracy and relevance.
