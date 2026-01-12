import threading
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import math
import re
from typing import List, Dict

import overpass_provider

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
) -> List[Dict]:
    """Orchestrate multiple providers concurrently for different POI types.

    Args:
        city: City name to search in
        poi_type: Type of POI ("restaurant", "historic", "museum", "park", etc.)
        limit: Maximum results to return
        local_only: Filter out chain restaurants (only applies to restaurants)
        timeout: Timeout for provider calls

    Returns list of unified entries with at least keys: id,name,lat,lon,osm_url,provider,raw
    """
    results = []

    # Heuristic: process at most ~10x the requested limit per provider and cap the
    # combined candidate pool too.
    max_per_provider = max(int(limit) * 10, 200)
    max_total_candidates = max(int(limit) * 20, 600)

    # Helper to wrap provider calls and record timings for instrumentation.
    def _timed_call(func, provider_name, *fargs, **fkwargs):
        start = time.time()
        try:
            res = func(*fargs, **fkwargs)
            return res
        except Exception as e:
            logging.warning(f"Provider {provider_name} raised: {e}")
            return None
        finally:
            dur = time.time() - start
            try:
                count = len(res) if "res" in locals() and res else 0
            except Exception:
                count = 0
            logging.info(
                f"Provider timing: {provider_name} took {dur:.2f}s and returned {count} items"
            )

    calls = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        # Overpass (OSM) - supports different POI types
        if poi_type == "restaurant":
            calls.append(
                ex.submit(
                    _timed_call,
                    overpass_provider.discover_restaurants,
                    "overpass",
                    city,
                    limit,
                    None,  # cuisine
                    local_only,
                )
            )
        else:
            # For other POI types, use the general discover_pois function
            calls.append(
                ex.submit(
                    _timed_call,
                    overpass_provider.discover_pois,
                    "overpass",
                    city,
                    poi_type,
                    limit,
                    local_only,
                )
            )

        # OpenTripMap (optional) - supports different kinds
        if opentripmap_provider:
            try:
                # Map poi_type to OpenTripMap kinds
                otm_kinds = {
                    "restaurant": "restaurants",
                    "historic": "historic,museums",
                    "museum": "museums",
                    "park": "parks",
                    "market": "markets",
                    "transport": "transport",
                    "family": "amusements",  # closest match
                    "event": "cultural",
                    "local": "cultural",
                    "hidden": "cultural",
                    "coffee": "cafes",
                }.get(poi_type, poi_type)

                calls.append(
                    ex.submit(
                        _timed_call,
                        opentripmap_provider.discover_pois,
                        "opentripmap",
                        city,
                        otm_kinds,
                        limit,
                    )
                )
            except Exception:
                pass

    # Collect results from all providers
    for call in as_completed(calls):
        try:
            provider_results = call.result()
            if provider_results:
                results.extend(provider_results)
        except Exception as e:
            logging.warning(f"Error collecting provider results: {e}")

    # Normalize and dedupe
    normalized = []
    seen_ids = set()
    for e in results[:max_total_candidates]:
        try:
            if poi_type == "restaurant":
                norm = _normalize_osm_entry(e)
            else:
                norm = _normalize_generic_entry(e)
            # Skip duplicates by ID
            if norm["id"] and norm["id"] not in seen_ids:
                seen_ids.add(norm["id"])
                normalized.append(norm)
        except Exception as e:
            logging.warning(f"Error normalizing entry: {e}")

    # Sort by some quality heuristic (name length as proxy for specificity)
    normalized.sort(key=lambda x: len(x.get("name", "")), reverse=True)

    return normalized[:limit]


async def async_discover_pois(
    city: str,
    poi_type: str = "restaurant",
    limit: int = 100,
    local_only: bool = False,
    timeout: float = 12.0,
    session=None,
) -> List[Dict]:
    """Async version of discover_pois. It will call async provider functions
    when available, otherwise offload sync providers to a thread.
    """
    results = []

    max_per_provider = max(int(limit) * 10, 200)
    max_total_candidates = max(int(limit) * 20, 600)

    async def _call_provider(func, provider_name, *fargs, **fkwargs):
        start = time.time()
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
            return res
        except Exception as e:
            logging.warning(f"Provider {provider_name} raised: {e}")
        finally:
            dur = time.time() - start
            try:
                count = len(res) if "res" in locals() and res else 0
            except Exception:
                count = 0
            logging.info(
                f"Provider timing: {provider_name} took {dur:.2f}s and returned {count} items"
            )

    tasks = []
    # Overpass (OSM) - supports different POI types
    if poi_type == "restaurant":
        func = getattr(overpass_provider, "async_discover_restaurants", overpass_provider.discover_restaurants)
        tasks.append(asyncio.create_task(_call_provider(func, "overpass", city, limit, None, local_only)))
    else:
        func = getattr(overpass_provider, "async_discover_pois", overpass_provider.discover_pois)
        tasks.append(asyncio.create_task(_call_provider(func, "overpass", city, poi_type, limit, local_only)))

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
            tasks.append(asyncio.create_task(_call_provider(func, "opentripmap", city, otm_kinds, limit)))
        except Exception:
            pass

    done, pending = await asyncio.wait(tasks)
    for t in done:
        try:
            provider_results = t.result()
            if provider_results:
                results.extend(provider_results)
        except Exception as e:
            logging.warning(f"Error collecting provider results: {e}")

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

    normalized.sort(key=lambda x: len(x.get("name", "")), reverse=True)
    return normalized[:limit]


def discover_restaurants(
    city: str,
    cuisine: str = None,
    limit: int = 100,
    local_only: bool = False,
    timeout: float = 12.0,
) -> List[Dict]:
    """Orchestrate multiple providers concurrently, normalize, dedupe, and rank results.

    Returns list of unified entries with at least keys: id,name,lat,lon,osm_url,provider,raw
    """
    return discover_pois(city, "restaurant", limit, local_only, timeout)


async def async_discover_restaurants(
    city: str,
    cuisine: str = None,
    limit: int = 100,
    local_only: bool = False,
    timeout: float = 12.0,
    session=None,
) -> List[Dict]:
    # multi_provider's restaurant path currently maps to discover_pois
    return await async_discover_pois(city, "restaurant", limit, local_only, timeout, session=session)


async def async_get_neighborhoods(city: str | None = None, lat: float | None = None, lon: float | None = None, lang: str = "en", session=None):
    """Wrapper that prefers provider async implementation and falls back to sync provider in a thread."""
    try:
        func = getattr(overpass_provider, "async_get_neighborhoods", None)
        if func and asyncio.iscoroutinefunction(func):
            return await func(city=city, lat=lat, lon=lon, lang=lang, session=session)
        # fallback: call sync version in thread if available
        func_sync = getattr(overpass_provider, "get_neighborhoods", None)
        if func_sync:
            return await asyncio.to_thread(func_sync, city, lat, lon, lang)
    except Exception as e:
        logging.warning(f"neighborhoods provider error: {e}")
    return []
