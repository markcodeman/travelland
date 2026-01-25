"""Geo enrichment helpers: best-effort neighborhood bounding box, POI discovery and short evidence sentence.

This module prefers using existing provider functions (Geoapify via `overpass_provider`). It is
resilient when providers are unavailable and returns None/empty results in that case.
"""
from __future__ import annotations

from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

try:
    from city_guides.providers import overpass_provider
except Exception:
    overpass_provider = None


async def enrich_neighborhood(city: str, neighborhood: str, session=None) -> Optional[Dict]:
    """Return enrichment dict or None.

    Returns a dict like:
      {
        'boundary': True|False,
        'bbox': (west, south, east, north) or None,
        'pois': [ {'name': str, 'type': str, 'lat': float, 'lon': float, 'source': str}, ... ],
        'text': 'Concise human-friendly enrichment sentence.'
      }

    This function is best-effort and always returns quickly if providers are missing.
    """
    if not city or not neighborhood:
        return None

    if overpass_provider is None:
        logger.debug('overpass_provider not available; geo enrichment skipped')
        return None

    try:
        # 1) Ask the neighborhood-finder for a canonical match (best-effort)
        try:
            cand = await overpass_provider.fetch_neighborhoods_enhanced(city=city)
        except Exception:
            cand = []

        matched_bbox = None
        boundary_found = False
        for c in (cand or []):
            nm = (c.get('name') or '').lower()
            if not nm:
                continue
            if neighborhood.lower() in nm or nm in neighborhood.lower():
                # Try to geocode the matched name to a bbox
                try:
                    bb = await overpass_provider.geoapify_geocode_city(f"{c.get('name')}, {city}")
                    if bb:
                        matched_bbox = bb
                        boundary_found = True
                        break
                except Exception:
                    pass

        # 2) If not found above, try geocoding neighborhood directly
        if not matched_bbox:
            try:
                bb = await overpass_provider.geoapify_geocode_city(f"{neighborhood}, {city}")
                if bb:
                    matched_bbox = bb
                    boundary_found = True
            except Exception:
                matched_bbox = None

        # 3) If we have a bbox, fetch POIs nearby using geoapify_discover_pois
        pois = []
        if matched_bbox:
            try:
                # Query for common categories: cafe, park, restaurant
                kinds = None
                # prefer to ask for more general categories and filter afterwards
                raw = await overpass_provider.geoapify_discover_pois(matched_bbox, kinds=kinds, limit=10)
                if raw:
                    for r in raw[:6]:
                        pois.append({
                            'name': r.get('name') or r.get('address') or 'Unknown',
                            'type': (r.get('amenity') or r.get('tags') or '').split(',')[0] if (r.get('amenity') or r.get('tags')) else 'poi',
                            'lat': r.get('lat'),
                            'lon': r.get('lon'),
                            'source': r.get('source') or 'geoapify'
                        })
            except Exception:
                logger.debug('geoapify_discover_pois failed', exc_info=True)

        # 4) Build a concise text if we have POIs
        text = None
        if pois:
            snippets = []
            for p in pois[:3]:
                t = p.get('type') or 'place'
                snippets.append(f"{p.get('name')} ({t})")
            text = f"{neighborhood} is a neighborhood in {city}. Notable nearby: {', '.join(snippets)}."

        return {'boundary': boundary_found, 'bbox': matched_bbox, 'pois': pois, 'text': text}
    except Exception:
        logger.exception('enrich_neighborhood failed')
        return None


def build_enriched_quick_guide(neighborhood: str, city: str, enrichment: Dict) -> str:
    """Return a concise enriched quick guide string from enrichment dict."""
    if not enrichment:
        return f"{neighborhood} is a neighborhood in {city}."
    if enrichment.get('text'):
        return enrichment.get('text')
    pois = enrichment.get('pois') or []
    if pois:
        snippets = []
        for p in pois[:3]:
            t = p.get('type') or 'place'
            snippets.append(f"{p.get('name')} ({t})")
        return f"{neighborhood} is a neighborhood in {city}. Nearby: {', '.join(snippets)}."
    return f"{neighborhood} is a neighborhood in {city}."
