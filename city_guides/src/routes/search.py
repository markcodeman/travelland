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

bp = Blueprint('search', __name__)


async def fetch_city_wikipedia(city: str, state: str | None = None, country: str | None = None) -> tuple[str, str] | None:
    """Return (summary, url) for the given city using Wikipedia."""
    from city_guides.src.app import app, aiohttp_session, WIKI_CITY_AVAILABLE, fetch_wikipedia_summary
    
    if not (WIKI_CITY_AVAILABLE and city):
        return None

    def _candidates():
        base = city.strip()
        seen = set()
        for candidate in [
            base,
            f"{base}, {state}" if state else None,
            f"{base}, {country}" if country else None,
            f"{base}, {state}, {country}" if state and country else None,
        ]:
            if candidate:
                normalized = candidate.strip()
                if normalized.lower() not in seen:
                    seen.add(normalized.lower())
                    yield normalized

    async def _fetch_for_title(title: str, country: str | None = None):
        if not fetch_wikipedia_summary:
            return None
        slug = title.replace(' ', '_')
        summary = await fetch_wikipedia_summary(title, lang="en", city=city, country=country)
        if summary:
            return summary.strip(), f"https://en.wikipedia.org/wiki/{slug}"
        return None

    # Try direct titles first
    for title in _candidates():
        try:
            # Pass country for better disambiguation handling
            result = await _fetch_for_title(title, country)
            if result:
                return result
        except Exception:
            app.logger.exception('Direct Wikipedia summary fetch failed for %s via %s', city, title)

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
                            result = await _fetch_for_title(best_title, country)
                            if result:
                                return result
                        except Exception:
                            app.logger.exception('OpenSearch Wikipedia summary failed for %s via %s', city, best_title)
    except Exception:
        app.logger.exception('Wikipedia open search failed for %s', city)

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
    normalized = unicodedata.normalize('NFKD', (payload.get("query") or "").strip())
    # Keep alphanumeric and spaces, remove other punctuation
    city = ''.join(c for c in normalized if c.isalnum() or c.isspace()).strip()
    q = (payload.get("category") or payload.get("intent") or "").strip().lower()
    neighborhood = payload.get("neighborhood")
    state_name = (payload.get("state") or payload.get("stateName") or "").strip()
    country_name = (payload.get("country") or payload.get("countryName") or "").strip()
    should_cache = False  # disabled for testing
    
    if not city:
        return jsonify({"error": "city required"}), 400
    
    try:
        # Use the search implementation from persistence
        result = await asyncio.to_thread(_search_impl, payload)

        # Add categories to the search result
        if isinstance(result, dict):
            try:
                from city_guides.src.simple_categories import get_dynamic_categories
                categories = await get_dynamic_categories(city, state_name, country_name)
                result['categories'] = categories
            except Exception as e:
                import traceback
                app.logger.error(f'Failed to get categories for {city}: {e}')
                app.logger.error(traceback.format_exc())
                result['categories'] = []

        # Add fun facts from seeded data
        if isinstance(result, dict):
            try:
                seeded_facts = get_city_fun_facts(city)
                if seeded_facts:
                    import random
                    result['fun_facts'] = [random.choice(seeded_facts)]
                    result['fun_fact'] = result['fun_facts'][0]
            except Exception as e:
                app.logger.debug(f'Failed to get fun facts for {city}: {e}')

        # If no quick_guide/summary provided by upstream providers, supplement with Wikipedia summary
        if WIKI_CITY_AVAILABLE and isinstance(result, dict):
            has_quick = bool((result.get('quick_guide') or '').strip())
            has_summary = bool((result.get('summary') or '').strip())
            if not has_quick and not has_summary:
                try:
                    wiki_data = await fetch_city_wikipedia(city, state_name or None, country_name or None)
                    if wiki_data:
                        summary, url = wiki_data
                        result['quick_guide'] = summary
                        result['source'] = 'wikipedia'
                        result['cached'] = False
                        result['source_url'] = url
                except Exception:
                    app.logger.exception('Wikipedia city fallback failed for %s', city)

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
