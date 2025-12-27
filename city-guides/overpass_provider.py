import requests
import time
from urllib.parse import urlencode

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
OVERPASS_URL = 'https://overpass-api.de/api/interpreter'


def reverse_geocode(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
    headers = {'User-Agent': 'CityGuides/1.0'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        j = r.json()
        return j.get('display_name', '')
    except Exception:
        return ''


def geocode_city(city):
    params = {'q': city, 'format': 'json', 'limit': 1}
    headers = {'User-Agent': 'CityGuides/1.0'}
    r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    j = r.json()
    if not j:
        return None
    entry = j[0]
    # return bbox as (south, west, north, east)
    bbox = entry.get('boundingbox')
    if bbox and len(bbox) == 4:
        south, north, west, east = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        # Overpass expects south,west,north,east
        return (south, west, north, east)
    return None


def discover_restaurants(city, limit=50, cuisine=None):
    """Discover restaurant POIs for a city using Nominatim + Overpass. Returns list of candidates with possible website or OSM url."""
    bbox = geocode_city(city)
    if not bbox:
        return []
    south, west, north, east = bbox
    # Overpass bbox format: south,west,north,east
    bbox_str = f"{south},{west},{north},{east}"
    # query nodes/ways/rels with amenity=restaurant, fast_food, cafe, etc. (budget-friendly options)
    amenity_filter = "[\"amenity\"~\"restaurant|fast_food|cafe|bar|pub|food_court\"]"
    cuisine_filter = f"[\"cuisine\"~\"{cuisine}\"]" if cuisine else ""
    q = f"[out:json][timeout:25];(node{amenity_filter}{cuisine_filter}({bbox_str});way{amenity_filter}{cuisine_filter}({bbox_str});relation{amenity_filter}{cuisine_filter}({bbox_str}););out center;"
    headers = {'User-Agent': 'CityGuides/1.0'}
    try:
        r = requests.post(OVERPASS_URL, data={'data': q}, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
    except Exception:
        return []
    elements = j.get('elements', [])
    out = []
    # Known chain restaurants to exclude for more authentic recommendations
    chain_keywords = [
        'chipotle', 'qdoba', 'taco bell', 'moe\'s', 'baja fresh', 'del taco', 
        'rubio\'s', 'mexican grill', 'taco time', 'jack in the box', 'mcdonald\'s', 
        'burger king', 'wendy\'s', 'subway', 'starbucks', 'dunkin\'', 'kfc', 
        'pizza hut', 'domino\'s', 'papa john\'s', 'little caesars'
    ]
    for el in elements[:limit]:
        tags = el.get('tags') or {}
        name = tags.get('name') or tags.get('operator') or 'Unnamed'
        # Get lat/lon
        if el['type'] == 'node':
            lat = el.get('lat')
            lon = el.get('lon')
        else:
            center = el.get('center')
            if center:
                lat = center['lat']
                lon = center['lon']
            else:
                continue
        # Build address
        address = tags.get('addr:full') or f"{tags.get('addr:housenumber','')} {tags.get('addr:street','')} {tags.get('addr:city','')} {tags.get('addr:postcode','')}".strip()
        # Skip slow reverse geocoding for now to keep it dynamic and fast
        if not address:
            address = f"{lat}, {lon}"
        
        # Skip known chains for more authentic local recommendations
        name_lower = name.lower()
        if any(chain.lower() in name_lower for chain in chain_keywords):
            continue
        website = tags.get('website') or tags.get('contact:website')
        osm_type = el.get('type')  # node/way/relation
        osm_id = el.get('id')
        osm_url = f'https://www.openstreetmap.org/{osm_type}/{osm_id}'
        tags_str = ', '.join([f"{k}={v}" for k,v in tags.items()])
        entry = {
            'name': name, 
            'website': website, 
            'osm_url': osm_url,
            'amenity': tags.get('amenity', ''),
            'cost': tags.get('cost', ''),
            'address': address,
            'lat': lat,
            'lon': lon,
            'tags': tags_str
        }
        out.append(entry)
    
    # Sort for budget-friendly: prioritize cheaper amenities and cost
    def sort_key(entry):
        amenity = entry['amenity']
        cost = entry['cost']
        # Amenity priority: fast_food=1, cafe=2, restaurant=3, others=4
        amenity_score = {'fast_food': 1, 'cafe': 2, 'restaurant': 3}.get(amenity, 4)
        # Cost score: cheap=1, moderate=2, expensive=3, unknown=2 (assume moderate)
        cost_score = {'cheap': 1, 'moderate': 2, 'expensive': 3}.get(cost.lower() if cost else '', 2)
        return (amenity_score, cost_score)
    
    out.sort(key=sort_key)
    return out
