"""
POI (Points of Interest) routes: Fun facts and dream destination parsing
"""
import os
import re
import random
import json
import unicodedata
import httpx
from quart import Blueprint, request, jsonify

from ..data.seeded_facts import get_city_fun_facts
from ..services.location import (
    city_mappings,
    region_mappings,
    levenshtein_distance
)

bp = Blueprint('poi', __name__)


async def fetch_wikidata_fact(city: str):
    """Fetch a single factual snippet from Wikidata (inception year + description)."""
    if not city:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            search_resp = await client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbsearchentities",
                    "search": city,
                    "language": "en",
                    "format": "json",
                    "limit": 1,
                },
            )
            if not search_resp.is_success:
                return None
            search_json = search_resp.json()
            search_results = search_json.get("search") or []
            if not search_results:
                return None
            entity_id = search_results[0].get("id")
            label = (search_results[0].get("label") or city).strip()
            desc = (search_results[0].get("description") or "").strip()
            if not entity_id:
                return None

            entity_resp = await client.get(f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json")
            if not entity_resp.is_success:
                return None
            entity_json = entity_resp.json()
            entity = (entity_json.get("entities") or {}).get(entity_id, {})
            claims = entity.get("claims", {})

            def extract_year():
                inception = claims.get("P571", [])
                if not inception:
                    return None
                try:
                    time_val = inception[0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time", "")
                    if time_val and len(time_val) >= 5 and time_val[0] == "+":
                        return time_val[1:5]
                except Exception:
                    return None
                return None

            year = extract_year()
            if year and desc:
                return f"{label}, {desc}, was completed around {year}."
            if desc:
                return f"{label}: {desc}."
            if year:
                return f"{label} dates to around {year}."
            return None
    except Exception as e:
        from city_guides.src.app import app as _app
        _app.logger.warning(f"[FUN-FACT] Wikidata fetch failed for {city}: {e}")
        return None


@bp.route('/api/fun-fact', methods=['POST'])
async def get_fun_fact():
    """Get a fun fact about a city"""
    try:
        from city_guides.src.app import app
        
        payload = await request.get_json(silent=True) or {}
        city = payload.get('city', '').strip()
        country = (payload.get('country') or '').strip()
        
        app.logger.info(f"[FUN-FACT] Received request for city: '{city}'")
        
        if not city:
            app.logger.warning("[FUN-FACT] No city provided in request")
            return jsonify({'error': 'city required'}), 400
        
        # Import tracker
        from city_guides.src.fun_fact_tracker import track_fun_fact
        
        # Normalize city name but preserve spaces for multi-word cities
        normalized = unicodedata.normalize('NFKD', city.lower())
        # Keep alphanumeric and spaces, remove other punctuation
        city_lower = ''.join(c for c in normalized if c.isalnum() or c.isspace()).strip()
        
        app.logger.info(f"[FUN-FACT] Normalized city name: '{city_lower}'")
        
        # Initialize city_facts to prevent UnboundLocalError
        fact_sentences: list[str] = []
        
        # Get seeded facts for this city
        seeded_facts = get_city_fun_facts(city_lower)
        
        # If city not in seeded list, fetch interesting facts
        if not seeded_facts:
            try:
                # Check for special cases
                is_landmark = any(k in city_lower for k in ["castle", "palace", "tower", "bridge", "monument", "pyramid", "colosseum"])
                bran_bias = any(k in city_lower for k in ["bran", "dracula", "vlad"])
                
                # Clean up city name for Wikipedia lookup
                # Remove country suffix if it looks like a landmark
                wiki_lookup = city.split(',')[0].strip() if is_landmark else city
                
                # Try Wikipedia first for higher-quality sentences
                from city_guides.providers.wikipedia_provider import fetch_wikipedia_summary
                wiki_text = await fetch_wikipedia_summary(wiki_lookup, lang="en")
                
                if wiki_text:
                    # Split into sentences and filter for interesting ones
                    sentences = [s.strip() for s in wiki_text.split('.') if 40 < len(s.strip()) < 200]
                    
                    # PRIORITIZE sentences with numbers/dates for fun facts
                    # These make for better "fun facts" than generic descriptions
                    fun_fact_candidates = []
                    generic_descriptions = []
                    
                    for s in sentences:
                        s_lower = s.lower()
                        # Check if it's a boring definition
                        is_definition = bool(re.match(r'^\w+ is (a |an |the )?(city|town|commune|village|place|area|region|district|borough|section|castle|fortress|building|monument|landmark)', s_lower))
                        
                        # Check if it has interesting content (numbers, dates, unique facts)
                        # Use \d to match numbers with or without commas
                        has_number = bool(re.search(r'\d', s_lower))
                        has_interest = has_number or any(pattern in s_lower for pattern in [
                            'oldest', 'newest', 'largest', 'smallest', 'tallest',
                            'first', 'only', 'unique', 'famous', 'world',
                            'built in', 'founded', 'established', 'created',
                            'known as', 'called', 'renowned', 'legend', 'history',
                            'medieval', 'century'
                        ])
                        
                        if has_interest and not is_definition:
                            fun_fact_candidates.append(s)
                        elif not is_definition:
                            generic_descriptions.append(s)
                    
                    # Use fun fact candidates first, fall back to generic descriptions
                    chosen_pool = fun_fact_candidates if fun_fact_candidates else generic_descriptions
                    
                    # For Bran, prefer Vlad/Dracula sentences
                    if bran_bias:
                        vlad_hits = [s for s in chosen_pool if re.search(r'vlad|dracula', s, re.IGNORECASE)]
                        if vlad_hits:
                            chosen_pool = vlad_hits
                    
                    if chosen_pool:
                        # Prefer up to two strong sentences to build a richer fact
                        selected = []
                        if bran_bias:
                            selected.extend(chosen_pool[:2])
                        else:
                            selected.extend(chosen_pool[:2])
                        fact_sentences.extend([s if s.endswith('.') else s + '.' for s in selected])

                # If still empty, try DDGS (with better error handling)
                if len(fact_sentences) < 4:
                    try:
                        from city_guides.providers.ddgs_provider import ddgs_search
                        ddgs_query = f"{city} interesting historical facts about {city}"
                        if bran_bias:
                            ddgs_query = "Bran Castle Vlad the Impaler history fact"
                        ddgs_results = await ddgs_search(ddgs_query, max_results=5, timeout=int(os.getenv('DDGS_TIMEOUT','5')))
                        
                        if ddgs_results:  # Only process if we got results
                            fun_facts_from_ddgs = []
                            for r in ddgs_results:
                                body = r.get('body', '')
                                sentences = re.split(r'(?<=[.!?])\s+', body)
                                for s in sentences:
                                    if 50 < len(s) < 180 and re.search(r'\d|largest|oldest|first|only|famous|world', s.lower()):
                                        if not re.match(r'^\w+ is a (city|town)', s.lower()):
                                            fun_facts_from_ddgs.append(s)
                            if fun_facts_from_ddgs:
                                fact_sentences.append(random.choice(fun_facts_from_ddgs))
                    except Exception as ddgs_err:
                        app.logger.debug(f"DDGS fun fact fetch failed: {ddgs_err}")

                # Final fallback: Wikidata
                if len(fact_sentences) < 4:
                    wd_fact = await fetch_wikidata_fact(wiki_lookup)
                    if bran_bias and not wd_fact:
                        wd_fact = await fetch_wikidata_fact("Bran Castle")
                    if not wd_fact and bran_bias:
                        wd_fact = await fetch_wikidata_fact("Vlad the Impaler")
                    if wd_fact:
                        fact_sentences.append(wd_fact if wd_fact.endswith('.') else wd_fact + '.')
            except Exception as e:
                app.logger.warning(f"Failed to fetch fun fact for {city}: {e}")
        else:
            fact_sentences = seeded_facts
        
        # Trim and dedupe, cap at 4 sentences for a balanced quick guide-style fact
        cleaned = []
        seen = set()
        for s in fact_sentences:
            if not s:
                continue
            text = s.strip()
            if not text.endswith('.'):  # enforce sentence ending
                text += '.'
            if text.lower() in seen:
                continue
            seen.add(text.lower())
            cleaned.append(text)
            if len(cleaned) >= 4:
                break

        # Ensure Bran/Dracula requests include Vlad/Dracula lore
        if bran_bias:
            has_vlad = any(re.search(r'vlad|dracula', c, re.IGNORECASE) for c in cleaned)
            if not has_vlad:
                try:
                    vlad_fact = await fetch_wikidata_fact("Vlad the Impaler")
                except Exception:
                    vlad_fact = None
                if vlad_fact:
                    cleaned.append(vlad_fact if vlad_fact.endswith('.') else vlad_fact + '.')
                else:
                    cleaned.append("Bran Castle is famously tied to Dracula lore and Vlad the Impaler legends.")
                # cap at 4 after insertion
                cleaned = cleaned[:4]

        if not cleaned:
            cleaned = [f"{city.title()} offers a mix of history, culture, and local landmarks worth exploring."]
        
        return jsonify({"city": city, "country": country, "facts": cleaned})

    except Exception as e:
        from city_guides.src.app import app
        app.logger.exception('Fun fact fetch failed')
        return jsonify({'error': 'Failed to fetch fun fact', 'details': str(e)}), 500


@bp.route('/api/llm-paraphrase', methods=['POST'])
async def llm_paraphrase():
    """Paraphrase text using Groq LLM. Strictly paraphrase — do not add facts."""
    try:
        from city_guides.src.app import app
        payload = await request.get_json(silent=True) or {}
        text = (payload.get('text') or '').strip()
        style = (payload.get('style') or 'punchy').strip().lower()

        if not text:
            return jsonify({'error': 'text required'}), 400

        # Check GROQ availability
        from city_guides.groq.groq_reccomend import call_groq_chat
        import os
        if not os.getenv('GROQ_API_KEY'):
            app.logger.warning('LLM paraphrase requested but GROQ_API_KEY not set')
            return jsonify({'error': 'llm_disabled', 'message': 'LLM paraphrase not available on this server'}), 501

        # Build system instruction — be strict about not inventing facts
        sys_msg = {
            'role': 'system',
            'content': (
                'You are a professional city guide and historian. Your task is to REWRITE the provided city fact '
                'to be more engaging while remaining strictly FACTUAL. '
                'DO NOT add marketing fluff, teasers, or "wanna know a secret" phrases. '
                'DO NOT add new facts or numbers. Preserve existing numbers and names exactly. '
                'Available styles: punchy (concise), slang (local flavor), nerdy (data-focused). '
                'Use family-friendly, PG-13 language. '
                'Output ONLY the rewritten fact.'
            )
        }
        user_msg = {'role': 'user', 'content': f"Style: {style}\nText: {text}"}
        resp = call_groq_chat([sys_msg, user_msg], timeout=15)

        # Extract paraphrase
        paraphrase = ''
        try:
            paraphrase = resp['choices'][0]['message']['content'].strip()
        except Exception:
            app.logger.exception('Unexpected Groq response')
            return jsonify({'error': 'llm_error', 'message': 'Unexpected LLM response'}), 500

        # Safety: reject paraphrases containing disallowed language (profanity, explicit sexual/drug content)
        import re
        bad_words = ['fuck','shit','bitch','cunt','asshole','motherfucker']
        if re.search(r"\b(?:" + "|".join(bad_words) + r")\b", paraphrase.lower()):
            app.logger.warning('Paraphrase contained disallowed language; rejecting')
            return jsonify({'error': 'llm_rejected', 'message': 'Paraphrase contained disallowed language'}), 422

        # Safety check: no new numeric tokens
        orig_nums = set(re.findall(r"\d+", text))
        new_nums = set(re.findall(r"\d+", paraphrase))
        if not new_nums.issubset(orig_nums):
            app.logger.warning('Paraphrase introduced new numeric claims; rejecting')
            return jsonify({'error': 'llm_rejected', 'message': 'Paraphrase introduced new numeric claims'}), 422

        # Length guard
        if len(paraphrase) > 400:
            paraphrase = paraphrase[:400].rsplit(' ', 1)[0] + '…'

        return jsonify({'paraphrase': paraphrase, 'style': style, 'source': 'groq'})

    except Exception as e:
        from city_guides.src.app import app as _app
        _app.logger.exception('LLM paraphrase failed')
        return jsonify({'error': 'llm_failed', 'details': str(e)}), 500


@bp.route('/api/parse-dream', methods=['POST'])
async def parse_dream():
    """Parse natural language travel dreams into structured location data.
    Accepts queries like "Paris cafes", "Tokyo nightlife", "Barcelona beaches"
    Returns: { city, country, state, neighborhood, intent, confidence }
    """
    try:
        from city_guides.src.app import app
        
        payload = await request.get_json(silent=True) or {}
        query = (payload.get('query') or '').strip()
        
        if not query:
            return jsonify({'error': 'query required'}), 400
        
        # Initialize result
        result = {
            'city': '',
            'country': '',
            'state': '',
            'neighborhood': '',
            'cityName': '',
            'countryName': '',
            'stateName': '',
            'neighborhoodName': '',
            'intent': '',
            'confidence': 'low'
        }
        
        # Common neighborhood mappings
        neighborhood_mappings = {
            'brooklyn': {'city': 'New York', 'neighborhood': 'Brooklyn', 'country': 'US', 'state': 'NY'},
            'manhattan': {'city': 'New York', 'neighborhood': 'Manhattan', 'country': 'US', 'state': 'NY'},
            'shoreditch': {'city': 'London', 'neighborhood': 'Shoreditch', 'country': 'GB'},
            'camden': {'city': 'London', 'neighborhood': 'Camden', 'country': 'GB'},
            'soho': {'city': 'London', 'neighborhood': 'Soho', 'country': 'GB'},
            'copacabana': {'city': 'Rio de Janeiro', 'neighborhood': 'Copacabana', 'country': 'BR', 'state': 'RJ'},
            'ipanema': {'city': 'Rio de Janeiro', 'neighborhood': 'Ipanema', 'country': 'BR', 'state': 'RJ'},
            'santa teresa': {'city': 'Rio de Janeiro', 'neighborhood': 'Santa Teresa', 'country': 'BR', 'state': 'RJ'},
            'leblon': {'city': 'Rio de Janeiro', 'neighborhood': 'Leblon', 'country': 'BR', 'state': 'RJ'},
            'alfama': {'city': 'Lisbon', 'neighborhood': 'Alfama', 'country': 'PT'},
            'baixa': {'city': 'Lisbon', 'neighborhood': 'Baixa', 'country': 'PT'},
            'chiado': {'city': 'Lisbon', 'neighborhood': 'Chiado', 'country': 'PT'},
            'bairro alto': {'city': 'Lisbon', 'neighborhood': 'Bairro Alto', 'country': 'PT'},
            'belém': {'city': 'Lisbon', 'neighborhood': 'Belém', 'country': 'PT'},
        }
        
        # Intent keywords
        intent_keywords = {
            'coffee': ['coffee', 'cafe', 'cafes', 'espresso', 'latte', 'cappuccino'],
            'nightlife': ['nightlife', 'bars', 'club', 'clubs', 'party', 'drinks', 'pub', 'pubs'],
            'beaches': ['beach', 'beaches', 'coast', 'shore', 'ocean', 'sea', 'sand'],
            'food': ['food', 'eat', 'restaurant', 'restaurants', 'dining', 'cuisine', 'dish'],
            'shopping': ['shop', 'shopping', 'mall', 'stores', 'boutique', 'market'],
            'culture': ['museum', 'museums', 'art', 'culture', 'gallery', 'historical', 'monument'],
            'nature': ['park', 'parks', 'nature', 'hiking', 'garden', 'outdoor'],
            'romance': ['romantic', 'romance', 'couples', 'date', 'sunset'],
            'adventure': ['adventure', 'adventurous', 'extreme', 'thrill'],
            'relaxation': ['relax', 'relaxing', 'spa', 'peaceful', 'quiet'],
        }
        
        # Parse the query
        query_lower = query.lower()
        
        def find_best_match(query, options, max_distance=2):
            """Find best fuzzy match from options"""
            best_match = None
            best_score = float('inf')
            
            for option in options:
                distance = levenshtein_distance(query, option)
                if distance <= max_distance and distance < best_score:
                    best_score = distance
                    best_match = option
            
            return best_match
        
        # Combine all searchable locations
        all_regions = list(region_mappings.keys())
        all_cities = list(city_mappings.keys())
        all_neighborhoods = list(neighborhood_mappings.keys())
        
        # Try fuzzy matching for regions first
        region_match = find_best_match(query_lower, all_regions)
        if region_match:
            mapping = region_mappings[region_match]
            result.update(mapping)
            result['cityName'] = mapping['city']
            result['countryName'] = mapping['countryName']
            if 'region' in mapping:
                result['region'] = mapping['region']
            result['confidence'] = 'medium'
        
        # Check for explicit neighborhoods first
        neighborhood_match = find_best_match(query_lower, all_neighborhoods)
        if neighborhood_match:
            hood_data = neighborhood_mappings[neighborhood_match]
            result.update(hood_data)
            result['neighborhoodName'] = hood_data['neighborhood']
            result['cityName'] = hood_data['city']
            result['confidence'] = 'high'
        
        # If no neighborhood found, check for cities
        if not result['city']:
            city_match = find_best_match(query_lower, all_cities)
            if city_match:
                city_data = city_mappings[city_match]
                result.update(city_data)
                result['cityName'] = city_data['city']
                result['confidence'] = 'high'
        
        # Extract intent
        detected_intent = []
        for intent, keywords in intent_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_intent.append(intent)
        
        if detected_intent:
            result['intent'] = ', '.join(detected_intent)
            # Boost confidence if we have both location and intent
            if result['city'] and result['confidence'] == 'high':
                result['confidence'] = 'very_high'
            elif result['city']:
                result['confidence'] = 'medium'
        
        # If no city found, try to extract using AI as fallback
        if not result['city']:
            try:
                # Use Groq for natural language parsing as fallback
                from city_guides.groq.traveland_rag import recommender
                if recommender.api_key:
                    messages = [
                        {"role": "system", "content": "Extract location information from travel queries. Return JSON with city, country, and optionally state/neighborhood. Be conservative - only return locations you're confident about."},
                        {"role": "user", "content": f"Extract location from: {query}"}
                    ]
                    response = await recommender.call_groq_chat(messages, timeout=10)
                    if response:
                        parsed = json.loads(response["choices"][0]["message"]["content"])
                        if parsed.get('city'):
                            result.update(parsed)
                            result['cityName'] = parsed.get('city', '')
                            result['countryName'] = parsed.get('country', '')
                            result['stateName'] = parsed.get('state', '')
                            result['neighborhoodName'] = parsed.get('neighborhood', '')
                            result['confidence'] = 'medium'
            except Exception as e:
                app.logger.warning(f"AI parsing fallback failed: {e}")
        
        # Final fallback: try simple city name extraction
        if not result['city']:
            words = query.lower().split()
            # Check multi-word regions first
            query_lower = query.lower()
            for region_name, mapping in region_mappings.items():
                if region_name in query_lower:
                    result.update(mapping)
                    result['cityName'] = mapping['city']
                    result['countryName'] = mapping['countryName']
                    if 'region' in mapping:
                        result['region'] = mapping['region']
                    result['confidence'] = 'low'
                    break
            
            # If still no city, check single words
            if not result['city']:
                for word in words:
                    if word in city_mappings:
                        mapping = city_mappings[word]
                        result.update(mapping)
                        result['cityName'] = mapping['city']
                        result['countryName'] = mapping['countryName']
                        if 'stateName' in mapping:
                            result['stateName'] = mapping['stateName']
                        result['confidence'] = 'low'
                        break
        
        # Clean up result
        if not result['city']:
            return jsonify({'error': 'no_location_detected', 'query': query}), 400
        
        return jsonify(result)
        
    except Exception as e:
        from city_guides.src.app import app
        app.logger.exception('Dream parsing failed')
        return jsonify({'error': 'parsing_failed', 'details': str(e)}), 500


def register(app):
    """Register POI blueprint with app"""
    app.register_blueprint(bp)
