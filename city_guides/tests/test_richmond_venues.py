import json
from city_guides.providers.neighborhood_provider import get_neighborhood_venues

venues = get_neighborhood_venues("richmond_district", city="san_francisco")
print(json.dumps(venues, indent=2))
