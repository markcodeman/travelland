import logging
import time
import asyncio
import math
import re
import unicodedata
from typing import List, Dict, Optional
import os


# Robust import for overpass_provider, always using absolute import
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
    from city_guides.providers import opentripmap_provider
except Exception:
    opentripmap_provider = None


# Curated neighborhood hints for major tourist cities
# These supplement OSM data with tourist-relevant areas and hidden gems
CURATED_NEIGHBORHOODS = {
    "Bangkok": [
        {"name": "Sukhumvit", "vibe": "expat nightlife, malls, and street food", "hidden_gems": ["Soi 38 street food", "Japanese Town at Sukhumvit 26"], "type": "district"},
        {"name": "Silom", "vibe": "business district by day, street food and nightlife after dark", "hidden_gems": ["Soi 20 curry stalls", "Lumphini Park dawn tai chi"], "type": "district"},
        {"name": "Khao San Road", "vibe": "backpacker hub with budget eats and nightlife", "hidden_gems": ["Soi Rambuttri for quieter dining", "Santichaiprakarn Park riverside"], "type": "area"},
        {"name": "Thonglor", "vibe": "hipster cafes, boutiques, and craft cocktail bars", "hidden_gems": ["The Commons community mall", "Soi 55 local eats"], "type": "district"},
        {"name": "Ekkamai", "vibe": "local hipster scene, less touristy than Thonglor", "hidden_gems": ["Ekkamai Soi 10 beer bars", "Gateway mall Japanese food"], "type": "district"},
        {"name": "Chinatown (Yaowarat)", "vibe": "street food paradise and gold shops", "hidden_gems": ["Soi Texas late-night seafood", "Trok Hua Met temple"], "type": "district"},
        {"name": "Talad Noi", "vibe": "200-year-old Chinese mechanic quarter, gritty authentic", "hidden_gems": ["River-view warehouses", "Hoy Kraeng Pa Jeen seafood"], "type": "neighborhood"},
        {"name": "Rattanakosin", "vibe": "historic old city with temples and palaces", "hidden_gems": ["Wat Saket at sunset", "Krua Apsorn royal kitchen"], "type": "area"},
        {"name": "Dusit", "vibe": "royal precinct with palaces and mansion cafes", "hidden_gems": ["Suan Pakkad Palace", "Vimanmek Mansion"], "type": "district"},
        {"name": "Ari", "vibe": "young creative scene with cafes and bars", "hidden_gems": ["Ari Soi 1 hidden bars", "Nana Coffee Roasters"], "type": "neighborhood"},
        {"name": "Bang Rak", "vibe": "where chefs eat after service, serious food", "hidden_gems": ["Soi 38 duck rice", "Le Du restaurant row"], "type": "district"},
        {"name": "Phra Athit", "vibe": "riverside locals area near Khao San but quieter", "hidden_gems": ["Phra Sumen Fort park", "Rambling House jazz bar"], "type": "area"},
    ],
    "Tokyo": [
        {"name": "Shibuya", "vibe": "youth culture, fashion, and nightlife", "hidden_gems": ["Nonbei Yokocho alley bars", "Shibuya Stream rooftop"], "type": "district"},
        {"name": "Harajuku", "vibe": "street fashion and quirky culture", "hidden_gems": ["Cat Street vintage shops", "Takeshita Street crepe stalls"], "type": "district"},
        {"name": "Shinjuku", "vibe": "neon nightlife and business", "hidden_gems": ["Omoide Yokocho yakitori alley", "Shinjuku Gyoen garden"], "type": "district"},
        {"name": "Shimokitazawa", "vibe": "indie music and vintage shopping", "hidden_gems": ["Live music bars", "Vintage clothing maze"], "type": "neighborhood"},
        {"name": "Koenji", "vibe": "alternative culture and punk rock", "hidden_gems": ["Antique shops", "Live houses"], "type": "neighborhood"},
        {"name": "Nakameguro", "vibe": "chic canal-side cafes and boutiques", "hidden_gems": ["Cherry blossom canal walks", "Meguro River coffee"], "type": "neighborhood"},
        {"name": "Yanaka", "vibe": "old Tokyo shitamachi atmosphere", "hidden_gems": ["Yanaka Ginza shopping street", "Nezu Shrine azaleas"], "type": "district"},
        {"name": "Golden Gai", "vibe": "micro bars and intimate nightlife", "hidden_gems": ["Albatross bar", "Champion bar"], "type": "area"},
    ],
    "Paris": [
        {"name": "1er Arrondissement", "vibe": "historic heart with Louvre and Palais Royal", "hidden_gems": ["Palais Royal gardens", "Louvre at night"], "type": "historic"},
        {"name": "2e Arrondissement", "vibe": "historic stock exchange district with passages", "hidden_gems": ["Galerie Vivienne", "Passage des Panoramas"], "type": "historic"},
        {"name": "3e Arrondissement (Le Marais)", "vibe": "historic Jewish quarter, LGBTQ+ friendly", "hidden_gems": ["Place des Vosges arcades", "Rue des Rosiers falafel"], "type": "historic"},
        {"name": "4e Arrondissement (Le Marais)", "vibe": "oldest area with Notre-Dame and gay bars", "hidden_gems": ["Île Saint-Louis", "Hôtel de Ville square"], "type": "historic"},
        {"name": "5e Arrondissement (Latin Quarter)", "vibe": "student area with Sorbonne and Roman ruins", "hidden_gems": ["Pantheron", "Jardin des Plantes"], "type": "culture"},
        {"name": "6e Arrondissement (Saint-Germain)", "vibe": "literary history and chic boutiques", "hidden_gems": ["Café de Flore", "Luxembourg Gardens"], "type": "culture"},
        {"name": "7e Arrondissement", "vibe": "elegant district with Eiffel Tower", "hidden_gems": ["Rue Cler market", "Musée d'Orsay"], "type": "culture"},
        {"name": "8e Arrondissement", "vibe": "Champs-Élysées and luxury shopping", "hidden_gems": ["Parc Monceau", "Petit Palais"], "type": "shopping"},
        {"name": "9e Arrondissement", "vibe": "Opéra and Grands Boulevards", "hidden_gems": ["Palais Garnier", "Galeries Lafayette rooftop"], "type": "culture"},
        {"name": "10e Arrondissement", "vibe": "Canal Saint-Martin hipster scene", "hidden_gems": ["Canal Saint-Martin locks", "Gare du Nord area"], "type": "culture"},
        {"name": "11e Arrondissement", "vibe": "trendy nightlife and food scene", "hidden_gems": ["Oberkampf bars", "Belleville border cafes"], "type": "nightlife"},
        {"name": "12e Arrondissement", "vibe": "Bercy and Bois de Vincennes", "hidden_gems": ["Coulée verte", "Marché d'Aligre"], "type": "residential"},
        {"name": "13e Arrondissement", "vibe": "Chinatown and modern architecture", "hidden_gems": ["Bibliothèque François Mitterrand", "Butte-aux-Cailles"], "type": "food"},
        {"name": "14e Arrondissement", "vibe": "Montparnasse and catacombs", "hidden_gems": ["Denfert-Rochereau", "Fondation Cartier"], "type": "culture"},
        {"name": "15e Arrondissement", "vibe": "family-friendly residential area", "hidden_gems": ["Parc André Citroën", "Île aux Cygnes"], "type": "residential"},
        {"name": "16e Arrondissement", "vibe": "upscale with Trocadéro views", "hidden_gems": ["Musée Marmottan", "Boileau village"], "type": "residential"},
        {"name": "17e Arrondissement", "vibe": "quiet Batignolles village vibe", "hidden_gems": ["Square des Batignolles", "Rue de Lévis market"], "type": "residential"},
        {"name": "18e Arrondissement (Montmartre)", "vibe": "artist hill with village atmosphere", "hidden_gems": ["Vineyards of Clos Montmartre", "Place du Tertre artists"], "type": "culture"},
        {"name": "19e Arrondissement", "vibe": "Belleville and Buttes-Chaumont park", "hidden_gems": ["Parc des Buttes-Chaumont", "Bassin de la Villette"], "type": "nature"},
        {"name": "20e Arrondissement", "vibe": "Père Lachaise and local vibe", "hidden_gems": ["Père Lachaise Cemetery", "Rue de Bagnolet"], "type": "historic"},
    ],
    "London": [
        {"name": "Shoreditch", "vibe": "street art and hipster nightlife", "hidden_gems": ["Brick Lane curry", "Columbia Road flower market"], "type": "neighborhood"},
        {"name": "Notting Hill", "vibe": "colorful houses and Portobello market", "hidden_gems": ["Golborne Road market", "Electric Cinema"], "type": "neighborhood"},
        {"name": "Brixton", "vibe": "Afro-Caribbean culture and music", "hidden_gems": ["Brixton Village food hall", "Pop Brixton"], "type": "neighborhood"},
        {"name": "Peckham", "vibe": "up-and-coming arts scene, diverse", "hidden_gems": ["Frank's Cafe rooftop", "Bussey Building"], "type": "neighborhood"},
        {"name": "Camden", "vibe": "alternative culture and markets", "hidden_gems": ["Camden Lock market", "Jazz Cafe"], "type": "neighborhood"},
    ],
    "New York City": [
        {"name": "Greenwich Village", "vibe": "bohemian history and jazz clubs", "hidden_gems": ["Washington Square arch", "Blue Note jazz"], "type": "neighborhood"},
        {"name": "Williamsburg", "vibe": "hipster central with craft everything", "hidden_gems": ["Smorgasburg food market", "Domino Park sunset"], "type": "neighborhood"},
        {"name": "Lower East Side", "vibe": "immigrant history meets trendy bars", "hidden_gems": ["Tenement Museum", "Essex Market"], "type": "neighborhood"},
        {"name": "Chelsea", "vibe": "art galleries and High Line park", "hidden_gems": ["Chelsea Market", "The High Line at sunset"], "type": "neighborhood"},
        {"name": "Astoria", "vibe": "Greek food and beer gardens, local feel", "hidden_gems": ["Bohemian Hall beer garden", "Museum of the Moving Image"], "type": "neighborhood"},
    ],
    "Rome": [
        {"name": "Trastevere", "vibe": "bohemian riverside with trattorias", "hidden_gems": ["Santa Maria Basilica mosaics", "Tiber Island"], "type": "neighborhood"},
        {"name": "Monti", "vibe": "vintage shopping and aperitivo culture", "hidden_gems": ["Mercato Monti", "Suburra 13"], "type": "neighborhood"},
        {"name": "Testaccio", "vibe": "working-class food traditions", "hidden_gems": ["Testaccio Market", "Piramide Cestia"], "type": "neighborhood"},
        {"name": "Pigneto", "vibe": "artsy neighborhood, Roman Brooklyn", "hidden_gems": ["Pigneto street art", "Necci dal 1924"], "type": "neighborhood"},
    ],
    "Barcelona": [
        {"name": "El Born", "vibe": "trendy medieval quarter", "hidden_gems": ["Santa Maria del Mar", "Passeig del Born bars"], "type": "neighborhood"},
        {"name": "Gràcia", "vibe": "village atmosphere with plazas", "hidden_gems": ["Festa Major street festivals", "Carrer de Verdi cinemas"], "type": "neighborhood"},
        {"name": "Poble-sec", "vibe": "authentic tapas and local life", "hidden_gems": ["Carrer Blai pinxtos", "Montjuïc Magic Fountain"], "type": "neighborhood"},
        {"name": "Sant Antoni", "vibe": "emerging food scene", "hidden_gems": ["Sant Antoni Market", "Tapas bars on Carrer del Parlament"], "type": "neighborhood"},
    ],
}


def _norm_name(name: str) -> str:
    if not name:
        return ""
    # Transliterate non-Latin scripts first
    s = _transliterate_name(name)
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _transliterate_name(name: str) -> str:
    """Convert non-Latin scripts to Latin approximations for English speakers."""
    if not name:
        return name
    
    # Check if name contains non-Latin scripts
    has_non_latin = False
    for char in name:
        try:
            # Check if character is outside basic Latin range
            if ord(char) > 0x007F:
                has_non_latin = True
                break
        except:
            pass
    
    if not has_non_latin:
        return name
    
    # Try unidecode first for better transliteration
    try:
        from unidecode import unidecode
        result = unidecode(name)
        if result and result != name:
            return result
    except ImportError:
        pass
    
    # Fallback: NFKD normalization + ASCII filtering
    normalized = unicodedata.normalize('NFKD', name)
    ascii_only = ''.join(c for c in normalized if ord(c) < 128)
    return ascii_only.strip() or name


def _normalize_display_name(name: str) -> str:
    if not name:
        return name
    n = name.strip()
    # Normalize common transliteration variants for user-facing display
    if n.lower() == "theseio":
        return "Thissio"
    return n


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


def _normalize_osm_entry(e: Dict) -> Optional[Dict]:
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


def _normalize_generic_entry(e: Dict) -> Optional[Dict]:
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
        print("[DEBUG] About to call asyncio.run(_gather_providers())")
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
            if norm and norm["id"] and norm["id"] not in seen_ids:
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
    print(f"[CRITICAL] async_discover_pois called: city={city}, poi_type={poi_type}, overpass_provider={'AVAILABLE' if overpass_provider else 'NONE'}")
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
                "historic": "historic",
                "museum": "museums",
                "park": "parks",
                "market": "marketplaces",
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

    # Geoapify (via overpass_provider) - only if function exists. It requires bbox input.
    # Geocode city if bbox not provided
    geo_func = getattr(overpass_provider, "geoapify_discover_pois", None)
    if geo_func:
        geoapify_bbox = bbox
        if geoapify_bbox is None and city:
            try:
                if overpass_provider is not None and hasattr(overpass_provider, "async_geocode_city"):
                    geoapify_bbox = await overpass_provider.async_geocode_city(city, session=session)
            except Exception:
                pass
        if geoapify_bbox:
            provider_coros.append(_call_provider(geo_func, "geoapify", geoapify_bbox, None, poi_type, limit, session=session))

    # Mapillary Places (optional) - use if token present
    try:
        import importlib
        mapillary_mod = importlib.import_module("providers.mapillary_provider")
    except Exception:
        mapillary_mod = None

    if mapillary_mod and os.getenv("MAPILLARY_TOKEN"):
        func = getattr(mapillary_mod, "async_discover_places", None)
        if func:
            # Geocode city if bbox not provided for Mapillary too
            mapillary_bbox = bbox
            if mapillary_bbox is None and city:
                try:
                    if overpass_provider is not None and hasattr(overpass_provider, "async_geocode_city"):
                        mapillary_bbox = await overpass_provider.async_geocode_city(city, session=session)
                except Exception:
                    pass
            if mapillary_bbox:
                provider_coros.append(_call_provider(func, "mapillary", mapillary_bbox, poi_type, limit, session=session))

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
        if res and isinstance(res, list):
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
            if norm and norm.get("id") and norm["id"] not in seen_ids:
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
        if session and os.getenv("MAPILLARY_TOKEN"):
            try:
                import providers.mapillary_provider as mapillary_provider
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
    """Wrapper that combines results from multiple providers and ranks by tourist relevance.
    
    Prioritizes curated neighborhoods for major tourist cities, then supplements with OSM data.
    """
    results = []
    city_normalized = _norm_name(city or "").split()[0]  # Extract first word (city name before comma/country)
    
    # Add curated neighborhoods for major tourist cities (with highest priority)
    curated_added = False
    for curated_city, neighborhoods in CURATED_NEIGHBORHOODS.items():
        # Match against first word of normalized city name (handles "Paris, France" -> "paris")
        if _norm_name(curated_city).split()[0] == city_normalized:
            for nb in neighborhoods:
                results.append({
                    'id': f"curated/{nb['name']}",
                    'name': nb['name'],
                    'slug': _norm_name(nb['name']),
                    'center': None,  # Will be filled by geocoding if needed
                    'bbox': None,
                    'source': 'curated',
                    'vibe': nb.get('vibe', ''),
                    'hidden_gems': nb.get('hidden_gems', []),
                    'type': nb.get('type', 'neighborhood'),
                    'curated_priority': 1000  # High priority bonus
                })
            curated_added = True
            logging.info(f"Added {len(neighborhoods)} curated neighborhoods for {city}")
            break
    
    # Get city center for ranking
    city_center = None
    if lat is not None and lon is not None:
        city_center = (lat, lon)
    elif city and overpass_provider is not None:
        try:
            geocode_func = getattr(overpass_provider, "async_geocode_city", None)
            if geocode_func:
                bbox = await geocode_func(city, session=session)
                if bbox and len(bbox) == 4:
                    # Calculate center from bbox (west, south, east, north)
                    west, south, east, north = bbox
                    city_center = ((south + north) / 2, (west + east) / 2)
        except Exception:
            pass
    
    # Get from Overpass (OSM) - supplement curated data
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
            if session is not None:
                geonames_results = await asyncio.wait_for(
                    geonames_provider.async_get_neighborhoods_geonames(city=city, lat=lat, lon=lon, max_rows=100, session=session),
                    timeout=10.0
                )
            else:
                geonames_results = await asyncio.wait_for(
                    geonames_provider.async_get_neighborhoods_geonames(city=city, lat=lat, lon=lon, max_rows=100),
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
    
    # Remove duplicates based on normalized name (prefer curated over OSM)
    seen = set()
    unique_results = []
    # Sort by source priority: curated first, then OSM, then others
    results_sorted = sorted(results, key=lambda x: 0 if x.get('source') == 'curated' else 1)
    for r in results_sorted:
        norm = _norm_name(r.get('name', ''))
        if norm and norm not in seen:
            seen.add(norm)
            unique_results.append(r)
    
    # Rank neighborhoods by tourist relevance
    ranked_results = _rank_neighborhoods_by_relevance(unique_results, city_center)
    
    # Apply transliteration to non-Latin names for English speakers
    # and add dynamic descriptions for known neighborhoods
    for r in ranked_results:
        original_name = r.get('name', '')
        if original_name:
            r['name_original'] = original_name
            r['name'] = _normalize_display_name(_transliterate_name(original_name))
            # Add description for known tourist neighborhoods
            name_lower = r['name'].lower().strip()
            r['description'] = _get_neighborhood_description(name_lower)
    
    # Return top 25 most relevant neighborhoods
    return ranked_results[:25]


def _get_neighborhood_description(name_lower: str) -> str:
    """Get dynamic description for known tourist neighborhoods."""
    NEIGHBORHOOD_DESCRIPTIONS = {
        # Athens
        'plaka': "The 'neighborhood of the gods,' known for its historical, picturesque streets under the Acropolis",
        'monastiraki': "A bustling, eclectic area famous for its flea market, ruins, and rooftop bars",
        'kolonaki': "An upscale, fashionable neighborhood with high-end boutiques and cafes",
        'psyrri': "Known for its vibrant, edgy nightlife, trendy cafes, and artistic scene",
        'psiri': "Known for its vibrant, edgy nightlife, trendy cafes, and artistic scene",
        'koukaki': "A popular, walkable area near the Acropolis Museum with a local vibe",
        'thissio': "A charming, quieter area with cafes offering great views of the Acropolis",
        'thisio': "A charming, quieter area with cafes offering great views of the Acropolis",
        'theseio': "A charming, quieter area with cafes offering great views of the Acropolis",
        'exarchia': "An edgy, artistic district known for its student population, street art, and bookstores",
        'exarcheia': "An edgy, artistic district known for its student population, street art, and bookstores",
        'pangrati': "A charming, local neighborhood near the Panathenaic Stadium with tree-lined streets",
        'gazi': "The city's main nightlife hub, featuring restaurants and clubs",
        'gkazi': "The city's main nightlife hub, featuring restaurants and clubs",
        'keramikos': "Historic area with ancient cemetery and vibrant nightlife scene",
        'kerameikos': "Historic area with ancient cemetery and vibrant nightlife scene",
        # Rome
        'trastevere': "Bohemian riverside neighborhood with trattorias and cobblestone streets",
        'monti': "Vintage shopping and aperitivo culture in Rome's oldest neighborhood",
        'testaccio': "Working-class food traditions and authentic Roman cuisine",
        # Barcelona
        'el born': "Trendy medieval quarter with boutiques and tapas bars",
        'gracia': "Village atmosphere with plazas and local character",
        # London
        'shoreditch': "Street art and hipster nightlife hub",
        'camden': "Alternative culture and famous markets",
        # Paris
        'le marais': "Historic Jewish quarter, LGBTQ+ friendly with boutiques",
        'montmartre': "Artist hill with village atmosphere and Sacré-Cœur",
        # Tokyo
        'shibuya': "Youth culture, fashion, and nightlife",
        'shinjuku': "Neon nightlife and business district",
        # Bangkok
        'sukhumvit': "Expat nightlife, malls, and street food",
        'silom': "Business district by day, street food and nightlife after dark",
        # NYC
        'greenwich village': "Bohemian history and jazz clubs",
        'williamsburg': "Hipster central with craft everything",
        'soho': "Cast-iron architecture and upscale shopping",
        'chelsea': "Art galleries and High Line park",
    }
    return NEIGHBORHOOD_DESCRIPTIONS.get(name_lower, "")


def _rank_neighborhoods_by_relevance(neighborhoods: list[dict], city_center: tuple[float, float] | None) -> list[dict]:
    """Sort neighborhoods by tourist relevance based on centrality, English names, and exclusions.
    
    Curated neighborhoods get highest priority, followed by OSM results based on scores.
    """
    
    # Known tourist neighborhoods get a boost (normalized names)
    TOURIST_NEIGHBORHOODS = {
        # Athens
        'plaka', 'monastiraki', 'kolonaki', 'psyrri', 'psiri', 'koukaki', 'thissio', 'thisio', 'theseio',
        'exarchia', 'exarcheia', 'pangrati', 'gazi', 'gkazi', 'keramikos', 'kerameikos',
        # Other major cities
        'trastevere', 'monti', 'testaccio', 'el born', 'gracia', 'shoreditch', 'camden',
        'le marais', 'montmartre', 'shibuya', 'shinjuku', 'sukhumvit', 'silom',
        'greenwich village', 'williamsburg', 'soho', 'chelsea',
    }
    
    # Dynamic descriptions for known neighborhoods
    NEIGHBORHOOD_DESCRIPTIONS = {
        # Athens
        'plaka': "The 'neighborhood of the gods,' known for its historical, picturesque streets under the Acropolis",
        'monastiraki': "A bustling, eclectic area famous for its flea market, ruins, and rooftop bars",
        'kolonaki': "An upscale, fashionable neighborhood with high-end boutiques and cafes",
        'psyrri': "Known for its vibrant, edgy nightlife, trendy cafes, and artistic scene",
        'psiri': "Known for its vibrant, edgy nightlife, trendy cafes, and artistic scene",
        'koukaki': "A popular, walkable area near the Acropolis Museum with a local vibe",
        'thissio': "A charming, quieter area with cafes offering great views of the Acropolis",
        'thisio': "A charming, quieter area with cafes offering great views of the Acropolis",
        'exarchia': "An edgy, artistic district known for its student population, street art, and bookstores",
        'exarcheia': "An edgy, artistic district known for its student population, street art, and bookstores",
        'pangrati': "A charming, local neighborhood near the Panathenaic Stadium with tree-lined streets",
        'gazi': "The city's main nightlife hub, featuring restaurants and clubs",
        'gkazi': "The city's main nightlife hub, featuring restaurants and clubs",
        'keramikos': "Historic area with ancient cemetery and vibrant nightlife scene",
        'kerameikos': "Historic area with ancient cemetery and vibrant nightlife scene",
        # Rome
        'trastevere': "Bohemian riverside neighborhood with trattorias and cobblestone streets",
        'monti': "Vintage shopping and aperitivo culture in Rome's oldest neighborhood",
        'testaccio': "Working-class food traditions and authentic Roman cuisine",
        # Barcelona
        'el born': "Trendy medieval quarter with boutiques and tapas bars",
        'gracia': "Village atmosphere with plazas and local character",
        # London
        'shoreditch': "Street art and hipster nightlife hub",
        'camden': "Alternative culture and famous markets",
        # Paris
        'le marais': "Historic Jewish quarter, LGBTQ+ friendly with boutiques",
        'montmartre': "Artist hill with village atmosphere and Sacré-Cœur",
        # Tokyo
        'shibuya': "Youth culture, fashion, and nightlife",
        'shinjuku': "Neon nightlife and business district",
        # Bangkok
        'sukhumvit': "Expat nightlife, malls, and street food",
        'silom': "Business district by day, street food and nightlife after dark",
        # NYC
        'greenwich village': "Bohemian history and jazz clubs",
        'williamsburg': "Hipster central with craft everything",
        'soho': "Cast-iron architecture and upscale shopping",
        'chelsea': "Art galleries and High Line park",
    }
    
    def calculate_score(n: dict) -> float:
        score = 100.0  # Base score
        
        # Guard against None values
        if not n or not isinstance(n, dict):
            return -9999  # Lowest possible score to filter out
        
        name = n.get('name', '')
        # Transliterate for matching against known neighborhoods
        name_transliterated = _transliterate_name(name).lower().strip()
        name_lower = name.lower().strip()
        
        # 0. Curated neighborhoods get massive priority bonus
        if n.get('source') == 'curated':
            score += n.get('curated_priority', 1000)
        
        # 0.5 Known tourist neighborhoods get a big boost (check both original and transliterated)
        if name_transliterated in TOURIST_NEIGHBORHOODS or any(t in name_transliterated for t in TOURIST_NEIGHBORHOODS):
            score += 800
        elif name_lower in TOURIST_NEIGHBORHOODS or any(t in name_lower for t in TOURIST_NEIGHBORHOODS):
            score += 800
        
        # 1. Centrality - closer to city center = higher score
        if city_center:
            center_lat, center_lon = city_center
            center_data = n.get('center')
            if center_data:
                lat = center_data.get('lat')
                lon = center_data.get('lon')
                if lat is not None and lon is not None:
                    try:
                        distance = _haversine_meters(center_lat, center_lon, float(lat), float(lon))
                        # Closer = more points (max 500 bonus for being within 1km)
                        centrality_bonus = max(0, 500 - distance / 1000)
                        score += centrality_bonus
                    except (ValueError, TypeError):
                        pass
        
        # 2. Has English name bonus
        tags = n.get('tags', {})
        if isinstance(tags, dict) and 'name:en' in tags:
            score += 100
        
        # 3. Source quality bonus
        source = n.get('source', '')
        if source == 'osm':
            score += 20  # Prefer OSM over GeoNames
        
        # 4. Penalize non-touristy patterns (housing estates, industrial zones, etc.)
        # Aggressive penalization for residential/factory patterns
        
        # Residential/housing patterns (high penalty)
        residential_patterns = ['village', 'community', 'housing', 'estate', 'residential']
        for pattern in residential_patterns:
            if pattern in name_lower:
                score -= 500
                break
        
        # Thai patterns (ชุมชน = community, หมู่บ้าน = village)
        thai_residential = ['ชุมชน', 'หมู่บ้าน', 'โซน', 'แดน', 'แปลง', 'zone']
        for pattern in thai_residential:
            if pattern in name:
                score -= 400
                break
        
        # Greek admin district patterns (Demotike Koinoteta = municipal community)
        greek_admin = ['demotike', 'koinoteta', 'dimotiki', 'δημοτική', 'κοινότητα']
        for pattern in greek_admin:
            if pattern in name_lower:
                score -= 600
                break
        
        # Other bad patterns (medium penalty)
        bad_patterns = [
            'industrial', 'factory', 'estate', 'corner', 'cross', 'heights', 
            'accommodation', 'staff', 'outsource', 'villas', 'apartments',
            'private', 'pattanakarn'  # Bangkok specific suburbs
        ]
        for pattern in bad_patterns:
            if pattern in name_lower:
                score -= 200
                break
        
        # Numbers often indicate housing estates (e.g., "Phetkasem 40")
        if re.search(r'\d+', name):
            score -= 100  # Small penalty for numbered areas
        
        # 5. Bonus for tourist-friendly keywords
        good_patterns = [
            'downtown', 'old town', 'historic', 'city centre', 'city center',
            'district', 'quarter', 'square', 'market', 'harbor', 'harbour'
        ]
        for pattern in good_patterns:
            if pattern in name_lower:
                score += 80
                break  # Only bonus once
        
        return score
    
    # Sort by score (highest first)
    return sorted(neighborhoods, key=calculate_score, reverse=True)
