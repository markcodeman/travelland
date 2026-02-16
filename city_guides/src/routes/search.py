"""
Search routes: Main venue and place search endpoint
"""
import os
import json
import asyncio
import unicodedata
from quart import Blueprint, request, jsonify
from aiohttp import ClientTimeout
import aiohttp

bp = Blueprint('search', __name__, url_prefix='/api')


async def fetch_city_wikipedia(city: str, state: str | None = None, country: str | None = None) -> tuple[str, str] | None:
    """Return (summary, url) for the given city using Wikipedia."""
    from city_guides.src.app import app, aiohttp_session, WIKI_CITY_AVAILABLE, fetch_wikipedia_summary
    debug_logs = []
    if not (WIKI_CITY_AVAILABLE and city):
        debug_logs.append("[WIKI] Not available or city missing")
        return None

    # Normalize country names for Wikipedia
    country_normalizations = {
        'bosnia': 'Bosnia and Herzegovina',
        'czech republic': 'Czech Republic', 
        'czech': 'Czech Republic',
        'uk': 'United Kingdom',
        'usa': 'United States',
        'us': 'United States',
        'uae': 'United Arab Emirates',
        'south korea': 'South Korea',
        'north korea': 'North Korea'
    }
    
    normalized_country = country_normalizations.get(country.lower(), country) if country else None

    def _candidates():
        raw_base = city.strip()
        parts = raw_base.split()
        primary = parts[0] if parts else raw_base  # e.g., "Mostar" from "Mostar Bosnia"
        # Strip a trailing country token if present
        base = raw_base
        if normalized_country and raw_base.lower().endswith(normalized_country.lower()):
            base = raw_base[: -len(normalized_country)].strip().strip(',').strip()
        seen = set()
        for candidate in [
            primary,
            base,
            f"{primary}, {normalized_country}" if normalized_country else None,
            f"{base}, {normalized_country}" if normalized_country else None,
            f"{base}, {state}" if state else None,
            f"{base}, {state}, {normalized_country}" if state and normalized_country else None,
        ]:
            if candidate:
                normalized = candidate.strip()
                if normalized.lower() not in seen:
                    seen.add(normalized.lower())
                    yield normalized

    async def _fetch_for_title(title: str, country: str | None = None):
        if not fetch_wikipedia_summary:
            debug_logs.append(f"[WIKI] fetch_wikipedia_summary not available for {title}")
            return None
        slug = title.replace(' ', '_')
        summary = await fetch_wikipedia_summary(title, lang="en", city=city, country=country, debug_logs=debug_logs)
        if summary:
            debug_logs.append(f"[WIKI] Returning summary for {title}")
            return summary.strip(), f"https://en.wikipedia.org/wiki/{slug}"
        debug_logs.append(f"[WIKI] No summary for {title}")
        return None

    # Try direct titles first
    for title in _candidates():
        try:
            # Pass country for better disambiguation handling
            result = await _fetch_for_title(title, normalized_country)
            if result:
                debug_logs.append(f"[WIKI] Success for candidate {title}")
                print("\n".join(debug_logs))
                return result
        except Exception:
            app.logger.exception('Direct Wikipedia summary fetch failed for %s via %s', city, title)
            debug_logs.append(f"[WIKI] Exception for {title}")

    # Fallback: use Wikipedia open search with candidates
    try:
        async with aiohttp.ClientSession() as session:
            for title in _candidates():
                params = {
                    "action": "opensearch",
                    "search": title,
                    "limit": 1,
                    "namespace": 0,
                    "format": "json",
                }
                async with session.get("https://en.wikipedia.org/w/api.php", params=params, timeout=ClientTimeout(total=6)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    if isinstance(data, list) and len(data) >= 2 and data[1]:
                        best_title = data[1][0]
                        try:
                            result = await _fetch_for_title(best_title, normalized_country)
                            if result:
                                debug_logs.append(f"[WIKI] OpenSearch success for {best_title}")
                                print("\n".join(debug_logs))
                                return result
                        except Exception:
                            app.logger.exception('OpenSearch Wikipedia summary failed for %s via %s', city, best_title)
                            debug_logs.append(f"[WIKI] Exception in OpenSearch for {best_title}")
    except Exception:
        app.logger.exception('Wikipedia open search failed for %s', city)
        debug_logs.append(f"[WIKI] OpenSearch outer exception for {city}")

    print("\n".join(debug_logs))
    return None


@bp.route("/search", methods=["POST"])
async def search():
    """Search for venues and places in a city"""
    from city_guides.src.app import (
        app, redis_client, WIKI_CITY_AVAILABLE, 
        fetch_wikipedia_summary, PREWARM_TTL
    )
    from city_guides.src.persistence import build_search_cache_key, _search_impl
    from city_guides.src.data.seeded_facts import get_city_fun_facts
    
    print("[SEARCH ROUTE] Search request received")
    payload = await request.get_json(silent=True) or {}
    print(f"[SEARCH ROUTE] Payload: {payload}")
    
    # Normalize city name but preserve spaces for multi-word cities
    raw_query = (payload.get("query") or "").strip()
    
    # Parse country from query if not explicitly provided
    parsed_city = raw_query
    parsed_country = ""
    
    # Check if query contains a country name
    country_keywords = [
        'bosnia', 'herzegovina', 'croatia', 'serbia', 'montenegro', 'macedonia', 'kosovo', 'albania',
        'bulgaria', 'romania', 'hungary', 'slovenia', 'austria', 'czech', 'slovakia', 'poland',
        'germany', 'france', 'italy', 'spain', 'portugal', 'netherlands', 'belgium', 'switzerland',
        'usa', 'united states', 'canada', 'mexico', 'brazil', 'argentina', 'chile', 'peru',
        'colombia', 'venezuela', 'ecuador', 'bolivia', 'paraguay', 'uruguay', 'china', 'japan',
        'korea', 'india', 'thailand', 'vietnam', 'malaysia', 'indonesia', 'philippines', 'australia',
        'new zealand', 'egypt', 'morocco', 'tunisia', 'algeria', 'turkey', 'greece', 'uk', 'england',
        'scotland', 'wales', 'ireland', 'norway', 'sweden', 'denmark', 'finland', 'iceland'
    ]
    
    query_lower = raw_query.lower()
    for country in country_keywords:
        if f' {country.lower()}' in query_lower or query_lower.endswith(f' {country.lower()}'):
            # Found country at the end of the query
            parsed_country = country
            # Remove country from city name
            parsed_city = raw_query.rsplit(f' {country}', 1)[0].strip()
            break
    
    # Remove any trailing country part after a comma (e.g., "Brasov, Romania" -> "Brasov")
    if ',' in parsed_city:
        parsed_city = parsed_city.split(',')[0].strip()
    
    # Normalize base city name for alphanumeric processing
    normalized = unicodedata.normalize('NFKD', parsed_city.lower())
    # Keep alphanumeric and spaces, remove other punctuation
    city = ''.join(c for c in normalized if c.isalnum() or c.isspace()).strip()
    
    q = (payload.get("category") or payload.get("intent") or "").strip().lower()
    raw_neighborhood = payload.get("neighborhood") or ""
    # Normalize neighborhood: keep alnum/space, drop generic suffixes for wiki lookups
    nh_norm = ''.join(c for c in unicodedata.normalize('NFKD', raw_neighborhood) if c.isalnum() or c.isspace()).strip()
    # Strip generic trailing words that hurt wiki hits
    for suffix in ["waterfront", "bay", "area", "district", "neighborhood", "quarter"]:
        if nh_norm.lower().endswith(suffix):
            nh_norm = nh_norm[: -len(suffix)].strip()
    neighborhood = nh_norm
    state_name = (payload.get("state") or payload.get("stateName") or "").strip()
    country_name = (payload.get("country") or payload.get("countryName") or parsed_country).strip()
    should_cache = True  # enabled for performance
    
    if not city:
        return jsonify({"error": "city required"}), 400
    
    try:
        # Use the search implementation from persistence
        result = await asyncio.to_thread(_search_impl, payload)

        # Add categories to the search result
        if isinstance(result, dict):
            try:
                from city_guides.src.simple_categories import get_dynamic_categories, get_neighborhood_specific_categories
                neighborhood = payload.get('neighborhood', '').strip()
                
                if neighborhood:
                    # Use neighborhood-specific categories
                    categories = await get_neighborhood_specific_categories(city, neighborhood, state_name)
                    # Normalize categories to dicts with 'category' key
                    norm_categories = []
                    for c in categories or []:
                        if isinstance(c, dict):
                            norm_categories.append(c if 'category' in c else {'category': c.get('name') or c.get('label') or str(c)})
                        else:
                            norm_categories.append({'category': str(c)})
                    categories = norm_categories
                    app.logger.info(f'Using neighborhood-specific categories for {neighborhood}, {city}: {[c.get("category", c) for c in categories]}')
                else:
                    # Use city-wide categories
                    categories = await get_dynamic_categories(city, state_name, country_name)
                    norm_categories = []
                    for c in categories or []:
                        if isinstance(c, dict):
                            norm_categories.append(c if 'category' in c else {'category': c.get('name') or c.get('label') or str(c)})
                        else:
                            norm_categories.append({'category': str(c)})
                    categories = norm_categories
                    app.logger.info(f'Using city-wide categories for {city}: {[c.get("category", c) for c in categories]}')
                
                result['categories'] = categories
            except Exception as e:
                import traceback
                app.logger.error(f'Failed to get categories for {city}{" / " + neighborhood if payload.get("neighborhood") else ""}: {e}')
                app.logger.error(traceback.format_exc())
                result['categories'] = []

        # Add fun facts from seeded data
        if isinstance(result, dict):
            try:
                # Add seeded fun facts using base city name
                seeded_facts = get_city_fun_facts(city)
                if seeded_facts:
                    import random
                    result['fun_facts'] = [random.choice(seeded_facts)]
                    result['fun_fact'] = result['fun_facts'][0]
            except Exception as e:
                app.logger.debug(f'Failed to get fun facts for {city}: {e}')

        # If no quick_guide/summary provided by upstream providers, try WikiVoyage and Wikipedia, then merge if both exist
        if WIKI_CITY_AVAILABLE and isinstance(result, dict):
            has_quick = bool((result.get('quick_guide') or '').strip())
            has_summary = bool((result.get('summary') or '').strip())
            try:
                from city_guides.providers.wikipedia_provider import fetch_wikivoyage_summary
                from city_guides.src.persistence import get_country_for_city
                # Attempt to disambiguate city by detecting country first (best-effort)
                detected_country = None
                try:
                    detected_country = get_country_for_city(city)
                except Exception:
                    detected_country = None
                if not country_name and detected_country:
                    country_name = detected_country

                # Prefer local WikiVoyage language for countries with strong local content (e.g., Spain -> 'es')
                preferred_langs = ["en"]
                if country_name and isinstance(country_name, str) and "spa" in country_name.lower() or (country_name and country_name.lower() in ("spain", "españa", "espana")):
                    preferred_langs = ["es", "en"]

                wikivoyage_summary = None
                # Neighborhood-level Wikipedia attempt first
                wikipedia_summary = None
                wikipedia_url = None
                if neighborhood:
                    try:
                        # Try both raw and normalized neighborhoods, with and without country
                        raw_neighborhood = (payload.get("neighborhood") or "").strip()
                        nh_candidates = []
                        for nh in [raw_neighborhood, neighborhood]:
                            if nh:
                                nh_candidates.append(nh)
                                if country_name:
                                    nh_candidates.append(f"{nh}, {country_name}")
                        for nh_title in nh_candidates:
                            nh_slug = nh_title.replace(' ', '_')
                            nh_summary = await fetch_wikipedia_summary(nh_title, lang="en", city=city, country=country_name or None, debug_logs=[])
                            if nh_summary:
                                wikipedia_summary = nh_summary.strip()
                                wikipedia_url = f"https://en.wikipedia.org/wiki/{nh_slug}"
                                break
                    except Exception:
                        pass
                for lang in preferred_langs:
                    try:
                        wikivoyage_summary = await fetch_wikivoyage_summary(city, lang=lang, city=city, country=country_name or None)
                        if wikivoyage_summary:
                            break
                    except Exception:
                        continue
                if not wikipedia_summary:
                    wiki_data = await fetch_city_wikipedia(city, state_name or None, country_name or None)
                    wikipedia_summary, wikipedia_url = (wiki_data if wiki_data else (None, None))
                merged = None
                sources = []
                source_urls = []
                if wikivoyage_summary:
                    sources.append('wikivoyage')
                    source_urls.append(f"https://en.wikivoyage.org/wiki/{city.replace(' ', '_')}")
                if wikipedia_summary:
                    sources.append('wikipedia')
                    source_urls.append(wikipedia_url)

                # If both sources available, merge deduped sentences and prefer richer combined text
                if wikivoyage_summary and wikipedia_summary:
                    def split_sentences(text):
                        import re
                        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
                    seen = set()
                    merged_sentences = []
                    for s in split_sentences(wikivoyage_summary) + split_sentences(wikipedia_summary):
                        key = s.lower()
                        if key not in seen:
                            seen.add(key)
                            merged_sentences.append(s)
                    merged = ' '.join(merged_sentences)

                # If only WikiVoyage exists and no upstream quick_guide/summary, use it
                elif wikivoyage_summary and not has_quick and not has_summary:
                    merged = wikivoyage_summary

                # If only Wikipedia exists and no upstream quick_guide/summary, use it
                elif wikipedia_summary and not has_quick and not has_summary:
                    merged = wikipedia_summary

                # If upstream quick_guide exists but is too short/generic, and Wikipedia offers richer content, merge
                elif wikivoyage_summary and wikipedia_summary and has_quick:
                    existing_qg = (result.get('quick_guide') or '').strip()
                    if len(existing_qg) < 160 or existing_qg.lower().startswith(city.lower()):
                        # Prefer the merged richer version
                        def split_sentences(text):
                            import re
                            return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
                        seen = set()
                        merged_sentences = []
                        for s in split_sentences(wikivoyage_summary) + split_sentences(wikipedia_summary):
                            key = s.lower()
                            if key not in seen:
                                seen.add(key)
                                merged_sentences.append(s)
                        merged = ' '.join(merged_sentences)

                if merged:
                    result['quick_guide'] = merged
                    result['source'] = '+'.join(sources) if sources else result.get('source')
                    result['cached'] = False
                    result['source_url'] = source_urls[0] if source_urls else result.get('source_url')
            except Exception:
                app.logger.exception('WikiVoyage/Wikipedia city fallback failed for %s', city)

        if should_cache and redis_client:
            cache_key = build_search_cache_key(city, q, neighborhood)
            try:
                await redis_client.set(cache_key, json.dumps(result), ex=PREWARM_TTL)
                app.logger.info("Cached search result for %s/%s", city, q)
            except Exception:
                app.logger.exception("Failed to cache search result")
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.exception('Search failed')
        return jsonify({"error": "search_failed", "details": str(e)}), 500


def register(app):
    """Register search blueprint with app"""
    app.register_blueprint(bp)


@bp.route('/geocode_candidates', methods=['POST'])
async def geocode_candidates():
    """Return geocoding candidates for a user query to assist disambiguation."""
    payload = await request.get_json(silent=True) or {}
    query = (payload.get('query') or payload.get('city') or '').strip()
    country = (payload.get('country') or payload.get('countryName') or '').strip()
    if not query:
        return jsonify({'error': 'query required'}), 400
    try:
        from city_guides.providers.geocoding import geocode_city_candidates
        candidates = await geocode_city_candidates(query, country=country, limit=5)
        return jsonify({'candidates': candidates})
    except Exception as e:
        from city_guides.src.app import app
        app.logger.exception('Geocode candidates failed')
        return jsonify({'error': 'geocode_failed', 'details': str(e)}), 500
