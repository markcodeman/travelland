from flask import Flask, render_template, request, jsonify
import json
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

import semantic
import overpass_provider
import places_provider

app = Flask(__name__, static_folder='static', template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    payload = request.json or {}
    city = (payload.get('city') or '').strip()
    budget = (payload.get('budget') or '').strip().lower()
    q = (payload.get('q') or '').strip().lower()
    provider = (payload.get('provider') or 'osm').strip().lower()  # 'osm' or 'google_places'

    results = []
    if city:
        try:
            # Choose data provider based on user selection
            if provider == 'google_places' and places_provider.gmaps:
                # Use Google Places API
                food_keywords = ['taco', 'pizza', 'burger', 'sushi', 'asian', 'italian', 'mexican', 'chinese', 'japanese', 'korean', 'restaurant', 'food', 'eat', 'irish', 'indian', 'thai', 'vietnamese', 'greek', 'spanish', 'german', 'british']
                cuisine_param = q if q in food_keywords else None
                pois = places_provider.discover_restaurants(city, limit=200, cuisine=cuisine_param)
                
                for poi in pois:
                    # Filter by query if provided
                    if q:
                        combined = ' '.join([str(poi.get(k,'')) for k in ('name','tags','description')]).lower()
                        if q not in combined:
                            continue
                    
                    # Filter by budget if provided
                    if budget and budget != 'any' and poi.get('budget') != budget:
                        continue
                    
                    # Format venue for response
                    venue = {
                        'id': poi.get('id', ''),
                        'city': city,
                        'name': poi.get('name', 'Unknown'),
                        'budget': poi.get('budget', 'mid'),
                        'price_range': poi.get('price_range', '$$'),
                        'rating': poi.get('rating'),
                        'user_ratings_total': poi.get('user_ratings_total', 0),
                        'description': poi.get('description', ''),
                        'tags': poi.get('tags', ''),
                        'address': poi.get('address'),
                        'latitude': poi.get('latitude', 0),
                        'longitude': poi.get('longitude', 0),
                        'website': poi.get('website', ''),
                        'phone': poi.get('phone', ''),
                        'osm_url': poi.get('osm_url', ''),
                        'amenity': poi.get('amenity', 'restaurant'),
                        'provider': 'google_places'
                    }
                    results.append(venue)
            else:
                # Use OpenStreetMap (default)
                food_keywords = ['taco', 'pizza', 'burger', 'sushi', 'asian', 'italian', 'mexican', 'chinese', 'japanese', 'korean', 'restaurant', 'food', 'eat']
                cuisine_param = q if q in food_keywords else None
                pois = overpass_provider.discover_restaurants(city, limit=200, cuisine=cuisine_param)
                
                for poi in pois:
                    # Filter by query if provided
                    if q:
                        combined = ' '.join([str(poi.get(k,'')) for k in ('name','tags')]).lower()
                        if q not in combined:
                            continue
                    
                    # Map POI to venue format
                    amenity = poi.get('amenity', '')
                    v_budget = 'mid'
                    price_range = '$$'
                    if amenity in ['fast_food', 'cafe', 'food_court']:
                        v_budget = 'cheap'
                        price_range = '$'
                    elif amenity in ['bar', 'pub']:
                        v_budget = 'mid'
                        price_range = '$$'
                    
                    if budget and budget != 'any' and v_budget != budget:
                        continue
                    
                    # Parse tags for better description
                    tags_dict = dict(tag.split('=', 1) for tag in poi.get('tags', '').split(', ') if '=' in tag)
                    cuisine = tags_dict.get('cuisine', '').replace(';', ', ')
                    brand = tags_dict.get('brand', '')
                    
                    if cuisine:
                        desc = f"{cuisine.title()} restaurant"
                        if brand:
                            desc = f"{brand} - {desc}"
                    else:
                        desc = f"Restaurant ({amenity})"
                        if brand:
                            desc = f"{brand} - {desc}"
                    
                    address = poi.get('address', '').strip()
                    if not address:
                        address = None
                    
                    venue = {
                        'id': poi.get('osm_id', ''),
                        'city': city,
                        'name': poi.get('name', 'Unknown'),
                        'budget': v_budget,
                        'price_range': price_range,
                        'description': desc,
                        'tags': poi.get('tags', ''),
                        'address': address,
                        'latitude': poi.get('lat', 0),
                        'longitude': poi.get('lon', 0),
                        'website': poi.get('website', ''),
                        'osm_url': poi.get('osm_url', ''),
                        'amenity': amenity,
                        'provider': 'osm'
                    }
                    results.append(venue)
        except Exception as e:
            print(f"Error fetching real-time data: {e}")

    return jsonify({'count': len(results), 'venues': results})


@app.route('/ingest', methods=['POST'])
def ingest():
    payload = request.json or {}
    urls = payload.get('urls') or []
    if isinstance(urls, str):
        urls = [urls]
    # basic validation: allow only http/https
    valid = []
    for u in urls:
        try:
            p = urlparse(u)
            if p.scheme in ('http', 'https'):
                valid.append(u)
        except Exception:
            continue
    if not valid:
        return jsonify({'error': 'no valid urls provided'}), 400
    n = semantic.ingest_urls(valid)
    return jsonify({'indexed_chunks': n, 'urls': valid})



@app.route('/poi-discover', methods=['POST'])
def poi_discover():
    payload = request.json or {}
    city = payload.get('city') or payload.get('location') or ''
    if not city:
        return jsonify({'error': 'city required'}), 400
    # discover via Overpass (OSM)
    try:
        candidates = overpass_provider.discover_restaurants(city, limit=200)
    except Exception as e:
        return jsonify({'error': 'discover_failed', 'details': str(e)}), 500
    return jsonify({'count': len(candidates), 'candidates': candidates})

@app.route('/semantic-search', methods=['POST'])
def ai_reason():
    print("AI REASON ROUTE CALLED")
    payload = request.json or {}
    q = payload.get('q', '').strip()
    city = payload.get('city', '').strip()  # optional
    mode = payload.get('mode', 'explorer')  # default to explorer
    if not q:
        return jsonify({'error': 'query required'}), 400
    try:
        answer = semantic.search_and_reason(q, city if city else None, mode)
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/convert', methods=['POST'])
def convert_currency():
    payload = request.json or {}
    amount = float(payload.get('amount', 0))
    from_curr = payload.get('from', 'USD')
    to_curr = payload.get('to', 'EUR')
    try:
        result = semantic.convert_currency(amount, from_curr, to_curr)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5010))
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
