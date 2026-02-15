from quart import request, jsonify
from .enrichment import get_neighborhood_enrichment
from .validation import validate_neighborhood
from .geo_enrichment import enrich_neighborhood, build_enriched_quick_guide
from .simple_categories import get_dynamic_categories, get_generic_categories
from .persistence import (
    _compute_open_now,
    _fetch_image_from_website,
    _humanize_opening_hours,
    _is_relevant_wikimedia_image,
    _persist_quick_guide,
    _search_impl,
    build_search_cache_key,
    calculate_search_radius,
    determine_budget,
    determine_price_range,
    ensure_bbox,
    fetch_safety_section,
    fetch_us_state_advisory,
    format_venue,
    format_venue_for_display,
    generate_description,
    get_cost_estimates,
    get_country_for_city,
    get_currency_for_country,
    get_currency_name,
    get_provider_links,
    get_weather,
    shorten_place,
)
import asyncio
import json

# from .app import app  # Removed to avoid circular import

# Re-export key functions for backward compatibility
__all__ = [
    'get_neighborhood_enrichment',
    'validate_neighborhood',
    'enrich_neighborhood',
    'build_enriched_quick_guide',
    'build_search_cache_key',
    'ensure_bbox',
    'format_venue',
    'determine_budget',
    'determine_price_range',
    'generate_description',
    'format_venue_for_display',
    '_humanize_opening_hours',
    '_compute_open_now',
    'calculate_search_radius',
    'get_country_for_city',
    'get_provider_links',
    'shorten_place',
    'get_currency_for_country',
    'get_currency_name',
    'get_cost_estimates',
    'fetch_safety_section',
    'fetch_us_state_advisory',
    'get_weather',
    '_fetch_image_from_website',
    '_is_relevant_wikimedia_image',
    '_persist_quick_guide',
    '_search_impl'
]

def register_routes(app):
    """Register routes with the Quart app instance.
    
    This function should be called after the app instance is created
    to avoid circular import issues.
    """
    @app.route("/api/categories", methods=["POST"])
    async def api_city_categories():
        """Get dynamic categories for a city or neighborhood based on real venue data"""
        payload = await request.get_json(silent=True) or {}
        city = (payload.get("city") or "").strip()
        state = (payload.get("state") or "").strip()
        neighborhood = (payload.get("neighborhood") or "").strip()
        
        if not city:
            return jsonify({"error": "city required"}), 400
        
        try:
            # If neighborhood is specified, generate neighborhood-specific categories
            if neighborhood:
                from .simple_categories import get_neighborhood_specific_categories
                categories = await get_neighborhood_specific_categories(city, neighborhood, state)
                source = "neighborhood_dynamic"
            else:
                categories = await get_dynamic_categories(city, state)
                source = "dynamic"
            
            return jsonify({
                "categories": categories,
                "source": source,
                "city": city,
                "neighborhood": neighborhood if neighborhood else None
            })
        except Exception as e:
            print(f"[CITY-CATEGORIES] Error for {city}{'/' + neighborhood if neighborhood else ''}: {e}")
            categories = get_generic_categories()
            return jsonify({
                "categories": categories,
                "source": "fallback",
                "city": city,
                "neighborhood": neighborhood if neighborhood else None
            })
    
    @app.route("/api/search", methods=["POST"])
    async def api_search():
        """API endpoint for searching venues and places in a city"""
        print("[SEARCH ROUTE] Search request received")
        payload = await request.get_json(silent=True) or {}
        print(f"[SEARCH ROUTE] Payload: {payload}")
        
        # Lightweight heuristic to decide whether to cache this search (focuses on food/top queries)
        city = (payload.get("query") or "").strip()
        q = (payload.get("category") or "").strip().lower()
        neighborhood = payload.get("neighborhood")
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
                    categories = await get_dynamic_categories(city, "", "")
                    if not categories:
                        categories = ['food', 'nightlife', 'culture', 'shopping', 'parks', 'historic sites', 'beaches', 'markets']
                    result['categories'] = categories
                except Exception as e:
                    import traceback
                    print(f'[SEARCH] Failed to get categories for {city}: {e}')
                    print(traceback.format_exc())
                    result['categories'] = ['food', 'nightlife', 'culture', 'shopping', 'parks', 'historic sites', 'beaches', 'markets']
            
            redis = getattr(app, "redis_client", None)
            prewarm_ttl = app.config.get("PREWARM_TTL")
            if should_cache and redis:
                cache_key = build_search_cache_key(city, q, neighborhood)
                try:
                    await redis.set(cache_key, json.dumps(result), ex=prewarm_ttl)
                    app.logger.info("Cached search result for %s/%s", city, q)
                except Exception:
                    app.logger.exception("Failed to cache search result")
            
            return jsonify(result)
            
        except Exception as e:
            app.logger.exception('Search failed')
            # Return fallback result with categories for testing
            return jsonify({
                "quick_guide": f"Explore {city}.",
                "source": "fallback",
                "cached": False,
                "categories": ['food', 'nightlife', 'culture', 'shopping', 'parks', 'historic sites', 'beaches', 'markets']
            }), 200
