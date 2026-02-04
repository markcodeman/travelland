Seeded cities governance

Overview
- `seeded_cities.json` is a centralized, versioned fallback of curated cities used when dynamic providers (e.g., GeoNames) are unavailable or rate-limited.
- The canonical schema includes: `name`, `countryCode`, `stateCode`, `lat`, `lon`, `population`, `geonameId`, `source: "seed"`.

Regeneration
- Use `tools/generate_seeded_cities.py --count 500 --geonames <GEONAMES_USERNAME>` to regenerate a 500-city seed file.
- The script will enrich local candidate names with GeoNames data when a username is provided and reachable.

Operational notes
- Seeds are intended as a fallback for critical UX flows (popular city lists, dropdowns, offline demos), not as a full global DB.
- Always commit `seeded_cities.json` changes with a release note indicating the `version` and `last_updated` fields.
- Add tests in `tests/` to assert schema compatibility when updating the seed.

Monitoring
- The application logs a message when it serves cities from the seeded fallback to make auditing and incident response easier.

