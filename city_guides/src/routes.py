from quart import Quart, request, jsonify
from .enrichment import get_neighborhood_enrichment
from .validation import validate_neighborhood
from city_guides.providers import multi_provider
from city_guides.providers.geocoding import geocode_city, reverse_geocode
from city_guides.providers.overpass_provider import async_geocode_city
from city_guides.providers.utils import get_session
from . import semantic
from .geo_enrichment import enrich_neighborhood
from .synthesis_enhancer import SynthesisEnhancer
from .snippet_filters import looks_like_ddgs_disambiguation_text
from .neighborhood_disambiguator import NeighborhoodDisambiguator
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
import aiohttp
import json
import hashlib
import re
import time
import requests
from redis import asyncio as aioredis
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

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
    @app.route("/api/search", methods=["POST"])
    async def api_search():
        """API endpoint for searching venues and places in a city"""
        print(f"[SEARCH ROUTE] Search request received")
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
