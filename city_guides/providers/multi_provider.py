import threading
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import math
import re
from typing import List, Dict, Optional
import os


# Robust import for overpass_provider, always using absolute import
import logging
overpass_provider = None
try:
    # Try direct import first
    from city_guides.providers import overpass_provider
    logging.info("✅ overpass_provider imported successfully")
except Exception as e:
    logging.error(f"❌ Failed to import overpass_provider: {e}")
    overpass_provider = None

geonames_provider = None
try:
    from city_guides.providers import geonames_provider
    logging.info("✅ geonames_provider imported successfully")
except Exception as e:
    logging.error(f"❌ Failed to import geonames_provider: {e}")
    geonames_provider = None

try:
    import opentripmap_provider
except Exception:
    opentripmap_provider = None


def _norm_name(name: str) -> str:
    if not name:
        return ""
    s = name.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _haversine_meters(lat1, lon1, lat2, lon2):
    # returns distance in meters
    if None in (lat1, lon1, lat2, lon2):
        return 1e9
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _normalize_osm_entry(e: Dict) -> Dict:
    # e expected from overpass_provider.discover_restaurants
    return {
        "id": e.get("osm_id") or e.get("id") or "",
        "name": e.get("name")
        or (e.get("tags", "").split("=")[-1] if e.get("tags") else "Unknown"),
        "lat": float(e.get("lat") or e.get("latitude") or 0),
        "lon": float(e.get("lon") or e.get("longitude") or 0),
        "address": e.get("address", ""),
        "osm_url": e.get("osm_url", ""),
        "tags": e.get("tags", ""),
        "website": e.get("website", ""),
        "amenity": e.get("amenity", ""),
        "provider": e.get("provider") or "osm",
        "raw": e,
    }


def _normalize_generic_entry(e: Dict) -> Dict:
    """Handle entries from web or other mixed sources."""
    return {
        "id": e.get("id") or e.get("osm_id") or e.get("place_id") or "",
        "name": e.get("name") or "Unknown",
        "lat": float(e.get("lat") or e.get("latitude") or 0),
        "lon": float(e.get("lon") or e.get("longitude") or 0),
        "address": e.get("address", ""),
        "osm_url": e.get("osm_url", ""),
        "tags": e.get("tags", ""),
        "website": e.get("website", ""),
        "description": e.get("description", ""),
        "amenity": e.get("amenity", "restaurant"),
        "rating": e.get("rating"),
        "budget": e.get("budget"),
        "price_range": e.get("price_range"),
        "provider": e.get("provider") or "web",
        "raw": e,
    }


def discover_pois(
    city: str,
    poi_type: str = "restaurant",
    limit: int = 100,
    local_only: bool = False,
    timeout: float = 12.0,
    bbox: Optional[tuple] = None,
    neighborhood: Optional[str] = None,
    name_query: Optional[str] = None,
) -> List[Dict]:
    """Orchestrate multiple providers concurrently for different POI types.

    Args:
        city: City name to search in
        poi_type: Type of POI ("restaurant", "historic", "museum", "park", etc.)
        limit: Maximum results to return
        local_only: Filter out chain restaurants (only applies to restaurants)
        timeout: Timeout for provider calls
        bbox: Optional bounding box (west, south, east, north) to restrict search
        neighborhood: Optional neighborhood name to geocode to bbox (e.g., "Soho, London")
        name_query: Optional name query to filter by (e.g., "taco" to find places with "taco" in name)

    Returns list of unified entries with at least keys: id,name,lat,lon,osm_url,provider,raw
    """
    print(f"[MULTI_PROVIDER DEBUG] discover_pois called with city={city}, poi_type={poi_type}, bbox={bbox}, neighborhood={neighborhood}, limit={limit}")
    results = []
    
    # Use bbox if provided (for neighborhood searches), otherwise city-level
    print(f"[DEBUG] Starting discover_pois with city={city}, bbox={bbox}, neighborhood={neighborhood}, poi_type={poi_type}")

    # Heuristic: process at most ~10x the requested limit per provider and cap the
    # combined candidate pool too.
    max_per_provider = max(int(limit) * 10, 200)
    max_total_candidates = max(int(limit) * 20, 600)

    # Run async providers in a single event loop
    async def _gather_providers():
        print(f"[MULTI_PROVIDER DEBUG] _gather_providers running for city={city}, poi_type={poi_type}, bbox={bbox}, neighborhood={neighborhood}")
        """Run all async provider calls concurrently in a single event loop.
        Uses the async_discover_pois which calls Overpass, Geoapify, 
        Opentripmap, and Mapillary in parallel."""
        
        try:
            # Use the async_discover_pois which runs ALL providers in parallel:
            # - Overpass (OSM data via async_discover_pois)
            # - Geoapify (places API)
            # - Opentripmap (tourism attractions)  
            # - Mapillary (image enrichment)
            print(f"[MULTI_PROVIDER DEBUG] Calling async_discover_pois with city={city}, poi_type={poi_type}, bbox={bbox}")
            all_results = await async_discover_pois(
                city=city,
                poi_type=poi_type,
                limit=max_per_provider,
                local_only=local_only,
                timeout=timeout,
                bbox=bbox,
            )
            print(f"[MULTI_PROVIDER DEBUG] async_discover_pois returned {len(all_results)} results from all providers")
            return all_results
        except Exception as e:
            logging.error(f"Error in async_discover_pois: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    # Run all async providers in a single event loop
    try:
        print(f"[DEBUG] About to call asyncio.run(_gather_providers())")
        provider_results = asyncio.run(_gather_providers())
        print(f"[DEBUG] Got {len(provider_results) if provider_results else 0} results from providers")
        if provider_results:
            results.extend(provider_results)
    except Exception as e:
        logging.error(f"Error gathering provider results: {e}")
        import traceback
        traceback.print_exc()

    # Normalize and dedupe
    normalized = []
    seen_ids = set()
    for e in results[:max_total_candidates]:
        try:
            if poi_type == "restaurant":
                norm = _normalize_osm_entry(e)
            else:
                norm = _normalize_generic_entry(e)
            print(f"[DEBUG] Normalized entry: {norm}")
            # Skip duplicates by ID
            if norm["id"] and norm["id"] not in seen_ids:
                seen_ids.add(norm["id"])
                normalized.append(norm)
        except Exception as e:
            logging.warning(f"Error normalizing entry: {e}. Entry: {e}")

    # Sort by some quality heuristic (name length as proxy for specificity)
    def _safe_name_len(item):
        try:
            if isinstance(item, dict):
                name = item.get("name", "")
            else:
                return 0
            if isinstance(name, str):
                return len(name)
            return 0
        except Exception:
            return 0

    normalized.sort(key=_safe_name_len, reverse=True)


    

    

    # No bbox filtering here; city-level only. Neighborhood filtering is done after provider call.

    return normalized[:limit]


async def async_discover_pois(
    city: str,
    poi_type: str = "restaurant",
    limit: int = 100,
    local_only: bool = False,
    timeout: float = 12.0,
    bbox: Optional[tuple] = None,
    session=None,
) -> List[Dict]:
    """Async version of discover_pois. It will call async provider functions
    when available, otherwise offload sync providers to a thread.
    """
    results = []

    max_per_provider = max(int(limit) * 10, 200)
    max_total_candidates = max(int(limit) * 20, 600)

    async def _call_provider(func, provider_name, *fargs, **fkwargs):
        print(f"[DEBUG] _call_provider calling {provider_name} with fargs={fargs}, fkwargs={fkwargs}")
        start = time.time()
        res = None
        try:
            if asyncio.iscoroutinefunction(func):
                # pass session if provider accepts it
                try:
                    res = await func(*fargs, session=session, **fkwargs)
                except TypeError:
                    res = await func(*fargs, **fkwargs)
            else:
                # run blocking provider in thread to avoid blocking loop
                res = await asyncio.to_thread(func, *fargs, **fkwargs)
                # If the result is a coroutine, await it
                if asyncio.iscoroutine(res):
                    res = await res
            return res
        except Exception as e:
            logging.warning(f"Provider {provider_name} raised: {e}")
            return None
        finally:
            dur = time.time() - start
            try:
                # Only call len() if res is not a coroutine
                if res is not None and not asyncio.iscoroutine(res):
                    count = len(res)
                else:
                    count = 0
            except Exception:
                count = 0
            logging.info(
                f"Provider timing: {provider_name} took {dur:.2f}s and returned {count} items"
            )

    # Build coroutines for providers and run them concurrently using asyncio.gather
    city = city or ""
    poi_type = poi_type or "restaurant"

    provider_coros = []

    # Overpass (OSM) - supports different POI types
    if overpass_provider is not None:
        if poi_type == "restaurant":
            func = getattr(overpass_provider, "async_discover_restaurants", overpass_provider.discover_restaurants)
            provider_coros.append(_call_provider(func, "overpass", city, limit, None, local_only, bbox=bbox))
        else:
            func = getattr(overpass_provider, "async_discover_pois", overpass_provider.discover_pois)
            provider_coros.append(_call_provider(func, "overpass", city, poi_type, limit, local_only, bbox=bbox))
    else:
        logging.error("overpass_provider is None! Cannot fetch POIs.")

    # OpenTripMap (optional)
    if opentripmap_provider:
        try:
            otm_kinds = {
                "restaurant": "restaurants",
                "historic": "historic,museums",
                "museum": "museums",
                "park": "parks",
                "market": "markets",
                "transport": "transport",
                "family": "amusements",
                "event": "cultural",
                "local": "cultural",
                "hidden": "cultural",
                "coffee": "cafes",
            }.get(poi_type, poi_type)

            # prefer async function if available
            func = getattr(opentripmap_provider, "async_discover_pois", opentripmap_provider.discover_pois)
            provider_coros.append(_call_provider(func, "opentripmap", city, otm_kinds, limit))
        except Exception:
            pass

    # Geoapify (via overpass_provider) - only if function exists. It prefers bbox input.
    geo_func = getattr(overpass_provider, "geoapify_discover_pois", None)
    if geo_func:
        # pass bbox and poi_type to let geoapify pick mapped categories when available
        provider_coros.append(_call_provider(geo_func, "geoapify", bbox, None, poi_type, limit, session=session))

    # Mapillary Places (optional) - use if token present
    try:
        import importlib
        mapillary_mod = importlib.import_module("city_guides.mapillary_provider")
    except Exception:
        mapillary_mod = None

    if mapillary_mod and os.getenv("MAPILLARY_TOKEN"):
        func = getattr(mapillary_mod, "async_discover_places", None)
        if func:
            provider_coros.append(_call_provider(func, "mapillary", bbox, poi_type, limit, session=session))

    # Run all provider coroutines concurrently. Use return_exceptions=True so one failing
    # provider does not cancel others.
    try:
        gather_results = await asyncio.gather(*provider_coros, return_exceptions=True)
    except Exception as e:
        logging.warning(f"Unexpected error during asyncio.gather: {e}")
        gather_results = []

    # Collect results, ignoring providers that raised exceptions
    for idx, res in enumerate(gather_results):
        if isinstance(res, Exception):
            logging.warning(f"Provider {idx} raised during gather: {res}")
            continue
        if not res:
            continue
        # If result is a coroutine or future (rare because _call_provider resolves), await it
        try:
            if asyncio.iscoroutine(res) or asyncio.isfuture(res):
                res = await res
        except Exception as e:
            logging.warning(f"Error awaiting provider result {idx}: {e}")
            continue
        if res:
            results.extend(res)

    # Normalize and dedupe
    normalized = []
    seen_ids = set()
    for e in results[:max_total_candidates]:
        try:
            if poi_type == "restaurant":
                norm = _normalize_osm_entry(e)
            else:
                norm = _normalize_generic_entry(e)
            if norm["id"] and norm["id"] not in seen_ids:
                seen_ids.add(norm["id"])
                normalized.append(norm)
        except Exception as e:
            logging.warning(f"Error normalizing entry: {e}")

    def _safe_name_len_async(item):
        try:
            if isinstance(item, dict):
                name = item.get("name", "")
            else:
                return 0
            if isinstance(name, str):
                return len(name)
            return 0
        except Exception:
            return 0

    normalized.sort(key=_safe_name_len_async, reverse=True)

    # Optionally enrich async results with Mapillary thumbnails if configured and session provided.
    try:
        import os
        if session and os.getenv("MAPILLARY_TOKEN"):
            try:
                import city_guides.mapillary_provider as mapillary_provider  # type: ignore
                try:
                    await mapillary_provider.async_enrich_venues(normalized, session=session, radius_m=50, limit=3)
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass

    # Filter by bbox if provided
    if bbox is not None:
        print(f"[BBOX FILTER] Applying bbox filter: {bbox} to {len(normalized)} venues")
        min_lon, min_lat, max_lon, max_lat = bbox
        filtered = []
        for n in normalized:
            lon = n.get('lon', 0)
            lat = n.get('lat', 0)
            inside = min_lon <= lon <= max_lon and min_lat <= lat <= max_lat
            if inside:
                filtered.append(n)
            else:
                print(f"[BBOX FILTER] Excluding {n.get('name', 'Unknown')} at {lat},{lon}")
        normalized = filtered
        print(f"[BBOX FILTER] After filtering: {len(normalized)} venues remain")

    return normalized[:limit]


def discover_restaurants(
    city: str,
    cuisine: Optional[str] = None,
    limit: int = 100,
    local_only: bool = False,
    timeout: float = 12.0,
) -> List[Dict]:
    """Orchestrate multiple providers concurrently, normalize, dedupe, and rank results.

    Returns list of unified entries with at least keys: id,name,lat,lon,osm_url,provider,raw
    """
    # Ensure city is a string, not None
    city = city or ""
    return discover_pois(city, "restaurant", limit, local_only, timeout)


async def async_discover_restaurants(
    city: str,
    cuisine: Optional[str] = None,
    limit: int = 100,
    local_only: bool = False,
    timeout: float = 12.0,
    session=None,
) -> List[Dict]:
    # multi_provider's restaurant path currently maps to discover_pois
    # Ensure city is a string, not None
    city = city or ""
    return await async_discover_pois(city, "restaurant", limit, local_only, timeout, session=session)


async def async_get_neighborhoods(city: str | None = None, lat: float | None = None, lon: float | None = None, lang: str = "en", session=None):
    """Wrapper that combines results from multiple providers."""
    results = []
    
    # Get from Overpass (OSM)
    if overpass_provider is not None:
        try:
            func = getattr(overpass_provider, "async_get_neighborhoods", None)
            if func and asyncio.iscoroutinefunction(func):
                osm_results = await func(city=city, lat=lat, lon=lon, lang=lang, session=session)
                if osm_results:
                    results.extend(osm_results)
            # fallback: call sync version in thread if available
            else:
                func_sync = getattr(overpass_provider, "get_neighborhoods", None)
                if func_sync:
                    osm_results = await asyncio.to_thread(func_sync, city or "", lat, lon, lang)
                    if osm_results:
                        results.extend(osm_results)
        except Exception as e:
            logging.warning(f"Overpass neighborhoods provider error: {e}")
    
    # Get from GeoNames if lat/lon provided
    if geonames_provider is not None and lat is not None and lon is not None:
        try:
            geonames_results = await asyncio.wait_for(
                geonames_provider.async_get_neighborhoods_geonames(city=city, lat=lat, lon=lon, max_rows=100, lang=lang, session=session),
                timeout=10.0
            )
            if geonames_results:
                # Convert GeoNames format to match OSM format
                for item in geonames_results:
                    if isinstance(item, dict) and 'name' in item:
                        results.append({
                            'id': item.get('id', f"geonames/{item.get('geonameId', '')}"),
                            'name': item['name'],
                            'slug': _norm_name(item['name']),
                            'center': {'lat': item.get('lat'), 'lon': item.get('lon')},
                            'bbox': None,  # GeoNames doesn't provide bbox
                            'source': 'geonames'
                        })
        except asyncio.TimeoutError:
            logging.warning("GeoNames neighborhoods call timed out")
        except Exception as e:
            logging.warning(f"GeoNames neighborhoods provider error: {e}")
    
    # Remove duplicates based on normalized name
    seen = set()
    unique_results = []
    for r in results:
        norm = _norm_name(r.get('name', ''))
        if norm and norm not in seen:
            seen.add(norm)
            unique_results.append(r)
    
    return unique_results
