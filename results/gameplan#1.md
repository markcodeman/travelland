GAME PLAN TO FIX ISSUES
PHASE 1: Address Formatting (CRITICAL)
Root Cause: Geoapify API returning venues without proper address fields Fix Strategy:

Investigate Geoapify response format in /city_guides/src/app.py
Add address normalization logic:
Use formatted address field when available
Fallback to constructing address from street, housenumber, city, postcode
Never display raw coordinates to users
Add validation: Reject venues without readable addresses
Priority: P0 - Blocks usability

PHASE 2: Category Matching (CRITICAL)
Root Cause: Category keywords not properly mapped to Geoapify categories Fix Strategy:

Review Geoapify category mappings in categories parameter
Add strict category filtering:
Food searches → only catering.restaurant, catering.cafe, catering.fast_food
Nightlife → only catering.bar, catering.pub, catering.nightclub
Exclude leisure, commercial, building categories from food searches
Implement post-filtering to remove mismatched venues
Priority: P0 - Results are irrelevant

PHASE 3: Geographic Accuracy (HIGH)
Root Cause: Search radius too broad or geocoding failing Fix Strategy:

Tighten search radius for city searches (currently may be using state/region)
Add distance scoring - weight venues closer to city center higher
Filter results outside city boundaries
Add "within X km of city center" validation
Priority: P1 - NYC results from rural NY unacceptable

PHASE 4: Hidden Gems Redesign (HIGH)
Root Cause: Backend only supports 6 cities, frontend shows 16 unsupported cities Fix Strategy: Two options:

Remove Hidden Gems until backend supports them properly
Transform to Neighborhoods (as previously planned per memory):
Le Marais, Paris
Notting Hill, London
Greenwich Village, NYC
Trastevere, Rome
El Born, Barcelona
Shibuya, Tokyo
Priority: P1 - Currently broken experience

PHASE 5: Duplicate Detection (MEDIUM)
Fix Strategy:

Add deduplication logic based on name + coordinates
Hash venue names and check for duplicates before displaying
Priority: P2 - Quality issue

RECOMMENDED IMMEDIATE ACTIONS
STOP deploying venue feature until address formatting fixed
Fix address formatting first (affects 60%+ of results)
Fix category filtering (affects relevance)
Temporarily hide Hidden Gems until properly supported
Add quality gates - reject venues without addresses or with coordinate-only display
SUCCESS METRICS FOR FIXES
Address Quality: 95%+ venues show readable addresses (not coordinates)
Category Relevance: 90%+ venues match requested category
Geographic Accuracy: 100% venues within city boundaries
No Duplicates: 0 duplicate venues in results
Testing Time: ~20 minutes across 6 cities, 7+ categories
Venues Evaluated: 30+
Critical Issues Found: 5 major categories
Recommendation: Do not deploy in current state - requires significant fixes