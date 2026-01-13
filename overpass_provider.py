import aiohttp
import time
import os
import json
import hashlib
from pathlib import Path
from urllib.parse import urlencode
import asyncio
import re
from typing import Optional, Union

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Geoapify endpoints
GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
GEOAPIFY_REVERSE_URL = "https://api.geoapify.com/v1/geocode/reverse"

def get_geoapify_key() -> Optional[str]:
    return os.getenv("GEOAPIFY_API_KEY")

async def geoapify_geocode_city(city: str, session: Optional[aiohttp.ClientSession] = None):
    api_key = get_geoapify_key()
    if not api_key:
        return None
    params = {"text": city, "format": "json", "apiKey": api_key, "limit": 1}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(GEOAPIFY_GEOCODE_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                if own:
                    await session.close()
                return None
            j = await r.json()
            features = j.get("features", [])
            if not features:
                if own:
                    await session.close()
                return None
            prop = features[0].get("properties", {})
            bbox = features[0].get("bbox")
            if bbox and len(bbox) == 4:
                # Geoapify bbox: [minlon, minlat, maxlon, maxlat]
                minlon, minlat, maxlon, maxlat = bbox
                if own:
                    await session.close()
                # Overpass expects south,west,north,east
                return (minlat, minlon, maxlat, maxlon)
            # fallback: use lat/lon with small buffer
            lat = prop.get("lat")
            lon = prop.get("lon")
            if lat is not None and lon is not None:
                buf = 0.05
                if own:
                    await session.close()
                return (lat-buf, lon-buf, lat+buf, lon+buf)
            if own:
                await session.close()
            return None
    except Exception:
        if own:
            await session.close()
        return None

async def geoapify_reverse_geocode(lat, lon, session: Optional[aiohttp.ClientSession] = None):
    api_key = get_geoapify_key()
    if not api_key:
        return ""
    params = {"lat": lat, "lon": lon, "format": "json", "apiKey": api_key}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(GEOAPIFY_REVERSE_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                if own:
                    await session.close()
                return ""
            j = await r.json()
            features = j.get("features", [])
            if not features:
                if own:
                    await session.close()
                return ""
            prop = features[0].get("properties", {})
            addr = prop.get("formatted", "")
            if own:
                await session.close()
            return addr
    except Exception:
        if own:
            await session.close()
        return ""

# --- GEOAPIFY POI SEARCH ---
GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"

async def geoapify_discover_pois(
    bbox: Optional[Union[list[float], tuple[float, float, float, float]]],
    kinds: Optional[str] = None,
    limit: int = 200,
    session: Optional[aiohttp.ClientSession] = None,
) -> list[dict]:
    """Discover POIs using Geoapify Places API, normalized to Overpass-like output."""
    api_key = get_geoapify_key()
    if not api_key or not bbox or len(bbox) != 4:
        return []
    south, west, north, east = bbox
    params = {
        "filter": f"rect:{west},{south},{east},{north}",
        "limit": str(limit),
        "apiKey": api_key,
        "format": "json",
    }
    if kinds:
        params["categories"] = kinds
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with session.get(GEOAPIFY_PLACES_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                if own:
                    await session.close()
                return []
            j = await r.json()
            features = j.get("features", [])
            out = []
            for feat in features:
                prop = feat.get("properties", {})
                name = prop.get("name") or prop.get("address_line1") or "Unnamed"
                lat = prop.get("lat")
                lon = prop.get("lon")
                address = prop.get("formatted") or prop.get("address_line1")
                website = prop.get("website")
                kinds_str = prop.get("categories", "")
                osm_url = prop.get("datasource", {}).get("url")
                entry = {
                    "osm_id": prop.get("place_id"),
                    "name": name,
                    "website": website,
                    "osm_url": osm_url,
                    "amenity": kinds_str,
                    "address": address,
                    "lat": lat,
                    "lon": lon,
                    "tags": kinds_str,
                    "source": "geoapify",
                }
                out.append(entry)
            if own:
                await session.close()
            return out
    except Exception:
        if own:
            await session.close()
        return []

# Expanded list of public Overpass API endpoints for global, robust failover
OVERPASS_URLS = [
    "https://overpass.osm.jp/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


async def reverse_geocode(lat, lon, session: Optional[aiohttp.ClientSession] = None):
    # Cache reverse geocodes to minimize API calls
    cache_dir = Path(__file__).parent / ".cache" / "nominatim"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    cache_key = f"{lat:.6f},{lon:.6f}"
    cache_file = cache_dir / f"{hashlib.md5(cache_key.encode()).hexdigest()}.json"
    if cache_file.exists():
        try:
            with cache_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(url, headers=headers, timeout=timeout) as r:
            if r.status == 200:
                j = await r.json()
                addr = j.get("display_name", "")
                try:
                    cache_file.write_text(json.dumps(addr), encoding="utf-8")
                except Exception:
                    pass
                if own:
                    await session.close()
                return addr
    except Exception:
        pass
    # Fallback to Geoapify
    addr = await geoapify_reverse_geocode(lat, lon, session=session)
    try:
        cache_file.write_text(json.dumps(addr), encoding="utf-8")
    except Exception:
        pass
    if own:
        await session.close()
    return addr


async def async_reverse_geocode(lat, lon, session: Optional[aiohttp.ClientSession] = None):
    cache_dir = Path(__file__).parent / ".cache" / "nominatim"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    cache_key = f"{lat:.6f},{lon:.6f}"
    cache_file = cache_dir / f"{hashlib.md5(cache_key.encode()).hexdigest()}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(url, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                if own:
                    await session.close()
                return ""
            j = await r.json()
            addr = j.get("display_name", "")
            try:
                cache_file.write_text(json.dumps(addr), encoding="utf-8")
            except Exception:
                pass
            if own:
                await session.close()
            return addr
    except Exception:
        if own:
            await session.close()
        return ""


async def geocode_city(city: str, session: Optional[aiohttp.ClientSession] = None):
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status == 200:
                j = await r.json()
                if j:
                    entry = j[0]
                    bbox = entry.get("boundingbox")
                    if bbox and len(bbox) == 4:
                        south, north, west, east = (
                            float(bbox[0]),
                            float(bbox[1]),
                            float(bbox[2]),
                            float(bbox[3]),
                        )
                        if own:
                            await session.close()
                        return (south, west, north, east)
    except Exception:
        pass
    # Fallback to Geoapify
    bbox = await geoapify_geocode_city(city, session=session)
    if own:
        await session.close()
    return bbox


async def async_geocode_city(city: str, session: Optional[aiohttp.ClientSession] = None):
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                if own:
                    await session.close()
                return None
            j = await r.json()
            if not j:
                if own:
                    await session.close()
                return None
            entry = j[0]
            bbox = entry.get("boundingbox")
            if bbox and len(bbox) == 4:
                south, north, west, east = (
                    float(bbox[0]),
                    float(bbox[1]),
                    float(bbox[2]),
                    float(bbox[3]),
                )
                if own:
                    await session.close()
                return (south, west, north, east)
            if own:
                await session.close()
            return None
    except Exception:
        if own:
            await session.close()
        return None


async def async_get_neighborhoods(city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None, lang: str = "en", session: Optional[aiohttp.ClientSession] = None):
    """Best-effort neighborhood lookup using OSM place tags within the city area or a bbox.

    Returns list of dicts: {id, name, slug, center, bbox, source}
    """
    own = False
    if session is None:
        session = await aiohttp.ClientSession().__aenter__()
        own = True
    try:
        area_id = None
        if city:
            params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
            headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": lang}
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
                    if r.status == 200:
                        j = await r.json()
                        if j:
                            if j[0].get("osm_type") == "relation" and j[0].get("osm_id"):
                                area_id = 3600000000 + int(j[0]["osm_id"])  # relation -> area id
            except Exception:
                pass

        # build query
        if area_id:
            q = f"""
                [out:json][timeout:25];
                area({area_id})->.cityArea;
                (
                  relation["place"~"neighbourhood|suburb|quarter|city_district"](area.cityArea);
                  way["place"~"neighbourhood|suburb|quarter|city_district"](area.cityArea);
                  node["place"~"neighbourhood|suburb|quarter|city_district"](area.cityArea);
                );
                out center tags;
            """
        else:
            bbox_str = None
            if lat and lon:
                buf = float(os.getenv("NEIGHBORHOOD_DEFAULT_BUFFER_KM", 5.0)) / 111.0
                minlat, minlon, maxlat, maxlon = lat - buf, lon - buf, lat + buf, lon + buf
                bbox_str = f"{minlat},{minlon},{maxlat},{maxlon}"
            else:
                bb = await async_geocode_city(city or "", session=session)
                if bb:
                    south, west, north, east = bb
                    bbox_str = f"{south},{west},{north},{east}"

            if not bbox_str:
                return []

            q = f"""
                [out:json][timeout:25];
                (
                  relation["place"~"neighbourhood|suburb|quarter|city_district"]({bbox_str});
                  way["place"~"neighbourhood|suburb|quarter|city_district"]({bbox_str});
                  node["place"~"neighbourhood|suburb|quarter|city_district"]({bbox_str});
                );
                out center tags;
            """

        # call overpass endpoints
        for url in OVERPASS_URLS:
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with session.post(url, data={"data": q}, timeout=timeout) as resp:
                    if resp.status != 200:
                        continue
                    j = await resp.json()
                    elements = j.get("elements", [])
                    results = []
                    for el in elements:
                        name = el.get("tags", {}).get("name")
                        if not name:
                            continue
                        el_id = f"{el.get('type')}/{el.get('id')}"
                        bbox = None
                        if el.get("type") == "relation":
                            bbox = el.get("bounds") or el.get("bbox")
                        center = None
                        if "center" in el:
                            center = {"lat": el["center"]["lat"], "lon": el["center"]["lon"]}
                        elif "lat" in el and "lon" in el:
                            center = {"lat": el["lat"], "lon": el["lon"]}
                        results.append({
                            "id": el_id,
                            "name": name,
                            "slug": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
                            "center": center,
                            "bbox": bbox,
                            "source": "osm",
                        })
                    if results:
                        return results
            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

        # If Overpass produced no results, try GeoNames as a best-effort fallback
        geonames_user = os.getenv("GEONAMES_USERNAME")
        if geonames_user:
            try:
                # import lazily to avoid import-time cost when not used
                from . import geonames_provider
                geores = await geonames_provider.async_get_neighborhoods_geonames(
                    city=city, lat=lat, lon=lon, session=session
                )
                if geores:
                    return geores
            except Exception:
                pass

        return []

    finally:
        if own:
            await session.close()


def _singularize(word: str) -> str:
    w = (word or "").lower().strip()
    if w.endswith("ies") and len(w) > 3:
        return w[:-3] + "y"
    if w.endswith("'s"):
        w = w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


# Expanded list of known chain restaurants to exclude for "Local Only" filter
CHAIN_KEYWORDS = [
    "chipotle",
    "qdoba",
    "taco bell",
    "moe's",
    "baja fresh",
    "del taco",
    "rubio's",
    "mexican grill",
    "taco time",
    "jack in the box",
    "mcdonald's",
    "burger king",
    "wendy's",
    "subway",
    "starbucks",
    "dunkin'",
    "kfc",
    "pizza hut",
    "domino's",
    "papa john's",
    "little caesars",
    "applebee's",
    "chili's",
    "tgif",
    "olive garden",
    "red lobster",
    "outback",
    "panera",
    "five guys",
    "smashburger",
    "shake shack",
    "culver's",
    "in-n-out",
    "sonic",
    "arbys",
    "hardee's",
    "carl's jr",
    "white castle",
    "steak n shake",
    "buffalo wild wings",
    "denny's",
    "ihop",
    "waffle house",
    "cracker barrel",
    "cheesecake factory",
    "panda express",
    "pf changs",
    "pei wei",
    "jason's deli",
    "firehouse subs",
    "jersey mike's",
    "jimmy john's",
    "potbelly",
    "quiznos",
    "mcallister's",
    "zaxby's",
    "canes",
    "raising cane's",
    "popeyes",
    "church's",
    "wingstop",
    "dairy queen",
    "a&w",
    "fuddruckers",
    "johnny rockets",
    "red robin",
    "ruby tuesday",
    "bj's",
    "yard house",
    "cheddar's",
    "bob evans",
    "perkins",
    "hooters",
    "texas roadhouse",
    "longhorn",
    "maggiano's",
    "carrabba's",
    "bonefish",
    "p.f. chang's",
    "papa murphy's",
    "cicis",
    "chuck e. cheese",
    "mod pizza",
    "blaze pizza",
    "marcos pizza",
    "hungry howies",
    "round table pizza",
    "jet's pizza",
    "village inn",
    "steak'n shake",
    "portillo's",
    "whataburger",
    "bojangles",
    "biscuitville",
    "bob evans",
    "friendly's",
    "perkins",
    "huddle house",
    "taco bueno",
    "taco john's",
    "fazoli's",
    "captain d's",
    "long john silver's",
    "boston market",
    "sweetgreen",
    "dig inn",
    "chopt",
    "salata",
    "tropical smoothie",
    "smoothie king",
    "jamba juice",
    "cold stone",
    "baskin robbins",
    "ben & jerry's",
    "dq grill",
    "freddy's",
    "jollibee",
    "habit burger",
    "bubba's 33",
    "steak 'n shake",
    "twin peaks",
    "hooters",
    "logans roadhouse",
    "golden corral",
    "old country buffet",
    "shoney's",
    "jolly bee",
    "habit grill",
    "elevation burger",
    "bgr the burger joint",
    "fatburger",
    "steak n shake",
    "bobby's burger palace",
    "burgerfi",
    "wayback burgers",
    "mooyah",
    "cheaphard",
    "mcdonalds",
    "burgerking",
    "wendys",
    "popeye's",
    "kiddie",
    "pf chang's",
    "magnolia",
    "cheesecake",
    "pf changs",
    "magento",
    "cava",
    "honeygrow",
    "sweetgreen",
    "mezza",
    "zoes kitchen",
    "tazikis",
    "garbanzo",
    "pita pit",
    "hummus",
    "falafel",
]



async def discover_restaurants(
    city: Optional[str] = None,
    bbox: Optional[Union[list[float], tuple[float, float, float, float]]] = None,
    limit: int = 200,
    cuisine: Optional[str] = None,
    local_only: bool = False,
    session: Optional[aiohttp.ClientSession] = None,
) -> list[dict]:
    """Discover restaurant POIs for a city using Nominatim + Overpass."""
    # If bbox is not provided, geocode the city
    if bbox is None:
        if city is None:
            return []
        bbox = await geocode_city(city, session=session)
    # Validate bbox is a tuple/list of 4 numbers
    if not (isinstance(bbox, (tuple, list)) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox)):
        return []
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"
    amenity_filter = '["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court"]'
    q = f"[out:json][timeout:60];(node{amenity_filter}({bbox_str});way{amenity_filter}({bbox_str});relation{amenity_filter}({bbox_str}););out center;"
    # --- DEBUG/LOGGING: Log Overpass QL query and bbox for troubleshooting ---
    print(f"[Overpass] Using bbox: {bbox}")
    print(f"[Overpass] Overpass QL query: {q}")


    # ---- CACHING & RATE LIMIT -------------------------------------------------
    CACHE_TTL = int(os.environ.get("OVERPASS_CACHE_TTL", 60 * 60 * 6))
    RATE_LIMIT_SECONDS = float(os.environ.get("OVERPASS_MIN_INTERVAL", 5.0))

    cache_dir = Path(__file__).parent / ".cache" / "overpass"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    def _cache_path_for_query(qstr: str) -> Path:
        h = hashlib.sha256(qstr.encode("utf-8")).hexdigest()
        return cache_dir / f"{h}.json"

    def _read_cache(qstr: str):
        p = _cache_path_for_query(qstr)
        if not p.exists():
            return None
        try:
            m = p.stat().st_mtime
            age = time.time() - m
            if age > CACHE_TTL:
                return None
            with p.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    def _write_cache(qstr: str, data):
        p = _cache_path_for_query(qstr)
        try:
            with p.open("w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except Exception:
            pass

    rate_file = cache_dir / "last_request_ts"

    def _ensure_rate_limit():
        try:
            last = float(rate_file.read_text()) if rate_file.exists() else 0.0
        except Exception:
            last = 0.0
        now = time.time()
        wait = RATE_LIMIT_SECONDS - (now - last)
        if wait > 0:
            time.sleep(wait)
        try:
            rate_file.write_text(str(time.time()))
        except Exception:
            pass

    headers = {"User-Agent": "CityGuides/1.0"}
    cached = _read_cache(q)
    if cached is not None:
        try:
            j = cached
        except Exception:
            j = None
    else:
        tried = []
        j = None
        for base_url in OVERPASS_URLS:
            try:
                _ensure_rate_limit()
                attempts = int(os.environ.get("OVERPASS_RETRIES", 2))
                for attempt in range(1, attempts + 1):
                    try:
                        own_session = False
                        if session is None:
                            session = aiohttp.ClientSession()
                            own_session = True
                        timeout = aiohttp.ClientTimeout(total=int(os.environ.get("OVERPASS_TIMEOUT", 20)))
                        async with session.post(base_url, data={"data": q}, headers=headers, timeout=timeout) as r:
                            if r.status != 200:
                                try:
                                    text = await r.text()
                                    if text.strip().startswith("<"):
                                        print(f"[Overpass ERROR XML] {text[:200]}...")
                                except Exception:
                                    pass
                                if own_session:
                                    await session.close()
                                continue
                            try:
                                j = await r.json()
                            except Exception:
                                text = await r.text()
                                print(f"[Overpass ERROR Non-JSON] {text[:200]}...")
                                if own_session:
                                    await session.close()
                                continue
                            _write_cache(q, j)
                            if own_session:
                                await session.close()
                            break
                    except Exception:
                        if attempt < attempts:
                            time.sleep(1 * attempt)
                        else:
                            raise
                if j is not None:
                    break
            except Exception:
                tried.append(base_url)
                continue

        if j is None:
            stale_p = _cache_path_for_query(q)
            if stale_p.exists():
                try:
                    with stale_p.open("r", encoding="utf-8") as fh:
                        j = json.load(fh)
                except Exception:
                    return []
            else:
                return []

    if j is None:
        return []
    elements = j.get("elements", [])
    elements = elements[:200]
    skip_reverse = len(elements) > 50
    out = []
    cuisine_token = _singularize(cuisine) if cuisine else None

    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("operator") or "Unnamed"
        if el["type"] == "node":
            lat = el.get("lat")
            lon = el.get("lon")
        else:
            center = el.get("center")
            if center:
                lat = center["lat"]
                lon = center["lon"]
            else:
                continue
        address = (
            tags.get("addr:full")
            or f"{tags.get('addr:housenumber','')} {tags.get('addr:street','')} {tags.get('addr:city','')} {tags.get('addr:postcode','')}".strip()
        )
        if not address:
            if skip_reverse:
                address = f"{lat}, {lon}"
            else:
                address = await reverse_geocode(lat, lon, session=session) or f"{lat}, {lon}"

        name_lower = name.lower()
        if local_only and any(chain.lower() in name_lower for chain in CHAIN_KEYWORDS):
            continue

        tags_str = ", ".join([f"{k}={v}" for k, v in tags.items()])
        searchable = " ".join([name_lower, tags_str.lower()])
        if cuisine_token:
            cuisine_tag = (tags.get("cuisine") or "").lower()
            match_in_tags = cuisine_token in searchable
            match_in_cuisine = cuisine_token in cuisine_tag
            match_reverse = cuisine_tag and _singularize(cuisine_tag) in cuisine_token
            if not (match_in_tags or match_in_cuisine or match_reverse):
                continue
        website = tags.get("website") or tags.get("contact:website")
        osm_type = el.get("type")
        osm_id = el.get("id")
        osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        entry = {
            "osm_id": osm_id,
            "name": name,
            "website": website,
            "osm_url": osm_url,
            "amenity": tags.get("amenity", ""),
            "cost": tags.get("cost", ""),
            "address": address,
            "lat": lat,
            "lon": lon,
            "tags": tags_str,
        }
        out.append(entry)

    def sort_key(entry):
        amenity = entry["amenity"]
        cost = entry["cost"]
        amenity_score = {"fast_food": 1, "cafe": 2, "restaurant": 3}.get(amenity, 4)
        cost_score = {"cheap": 1, "moderate": 2, "expensive": 3}.get(
            cost.lower() if cost else "", 2
        )
        return (amenity_score, cost_score)

    out.sort(key=sort_key)
    return out


async def async_discover_restaurants(city: Optional[str] = None, limit: int = 200, cuisine: Optional[str] = None, local_only: bool = False, bbox: Optional[Union[list[float], tuple[float, float, float, float]]] = None, session: Optional[aiohttp.ClientSession] = None):
    # Use async wrapper to call async_discover_pois
    res = await async_discover_pois(city, "restaurant", limit, local_only, bbox, session=session)
    if not res and city:
        # Try area-based Overpass query if bbox returns nothing
        # Get OSM relation id for city
        import logging
        params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
        headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
        own = False
        if session is None:
            session = aiohttp.ClientSession()
            own = True
        area_id = None
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
                if r.status == 200:
                    j = await r.json()
                    if j and j[0].get("osm_type") == "relation" and j[0].get("osm_id"):
                        area_id = 3600000000 + int(j[0]["osm_id"])
        except Exception:
            pass
        if area_id:
            # Build broader Overpass area query: include all amenities, tourism, and leisure
            q = f"""
            [out:json][timeout:60];
            area({area_id})->.searchArea;
            (
              node["amenity"](area.searchArea);
              way["amenity"](area.searchArea);
              relation["amenity"](area.searchArea);
              node["tourism"](area.searchArea);
              way["tourism"](area.searchArea);
              relation["tourism"](area.searchArea);
              node["leisure"](area.searchArea);
              way["leisure"](area.searchArea);
              relation["leisure"](area.searchArea);
            );
            out center;
            """
            logging.warning(f"[Overpass] Area fallback query for {city}: {q}")
            for base_url in OVERPASS_URLS:
                try:
                    timeout = aiohttp.ClientTimeout(total=30)
                    async with session.post(base_url, data={"data": q}, timeout=timeout) as resp:
                        logging.warning(f"[Overpass] Area fallback POST {base_url} status={resp.status}")
                        if resp.status == 200:
                            j = await resp.json()
                            elements = j.get("elements", [])
                            logging.warning(f"[Overpass] Area fallback returned {len(elements)} elements for {city}")
                            out = []
                            for el in elements:
                                tags = el.get("tags") or {}
                                name = tags.get("name") or tags.get("operator") or "Unnamed"
                                if el["type"] == "node":
                                    lat = el.get("lat")
                                    lon = el.get("lon")
                                else:
                                    center = el.get("center")
                                    if center:
                                        lat = center["lat"]
                                        lon = center["lon"]
                                    else:
                                        continue
                                address = tags.get("addr:full") or f"{tags.get('addr:housenumber','')} {tags.get('addr:street','')} {tags.get('addr:city','')} {tags.get('addr:postcode','')}",
                                entry = {
                                    "osm_id": el.get("id"),
                                    "name": name,
                                    "website": tags.get("website") or tags.get("contact:website"),
                                    "osm_url": f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
                                    "amenity": tags.get("amenity", ""),
                                    "cost": tags.get("cost", ""),
                                    "address": address,
                                    "lat": lat,
                                    "lon": lon,
                                    "tags": ", ".join([f"{k}={v}" for k, v in tags.items()]),
                                }
                                out.append(entry)
                            if out:
                                res = out
                                break
                        else:
                            logging.warning(f"[Overpass] Area fallback non-200 status: {resp.status}")
                    # Log any exceptions
                except Exception as e:
                    logging.warning(f"[Overpass] Area fallback error: {e}")
                    continue
        if own:
            await session.close()
    return res


async def discover_pois(city: Optional[str] = None, poi_type: str = "restaurant", limit: int = 200, local_only: bool = False, bbox: Optional[Union[list[float], tuple[float, float, float, float]]] = None, session: Optional[aiohttp.ClientSession] = None):
    """Discover POIs of various types for a city using Nominatim + Overpass.
    If bbox is provided, use it directly. Otherwise, geocode the city.

    Args:
        city: City name to search in
        poi_type: Type of POI ("restaurant", "historic", "museum", "park", etc.)
        limit: Maximum results to return
        local_only: Filter out chains (only applies to restaurants)
        bbox: Optional bounding box (south, west, north, east)

    Returns list of candidates with OSM data.
    """
    if bbox is None:
        if city is None:
            return []
        bbox = await geocode_city(city, session=session)
    # Validate bbox is a tuple/list of 4 numbers
    if not (isinstance(bbox, (tuple, list)) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox)):
        return []
    south, west, north, east = bbox
    # Overpass bbox format: south,west,north,east
    bbox_str = f"{south},{west},{north},{east}"

    # Define queries for different POI types
    poi_queries = {
        "restaurant": '["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court"]',
        "historic": '["tourism"="attraction"]',
        "museum": '["tourism"="museum"]',
        "park": '["leisure"="park"]',
        "market": '["amenity"="marketplace"]',
        "transport": '["amenity"~"bus_station|train_station|subway_entrance|ferry_terminal|airport"]',
        "family": '["leisure"~"playground|amusement_arcade|miniature_golf"]',
        "event": '["amenity"~"theatre|cinema|arts_centre|community_centre"]',
        "local": '["tourism"~"attraction"]',  # generic attractions
        "hidden": '["tourism"~"attraction"]',  # same as local
        "coffee": '["amenity"~"cafe|coffee_shop"]',
    }

    # Default to restaurant if unknown type
    amenity_filter = poi_queries.get(poi_type, poi_queries["restaurant"])

    q = f"[out:json][timeout:60];(node{amenity_filter}({bbox_str});way{amenity_filter}({bbox_str});relation{amenity_filter}({bbox_str}););out center;"

    # ---- CACHING & RATE LIMIT -------------------------------------------------
    CACHE_TTL = int(
        os.environ.get("OVERPASS_CACHE_TTL", 60 * 60 * 6)
    )  # 6 hours default
    RATE_LIMIT_SECONDS = float(
        os.environ.get("OVERPASS_MIN_INTERVAL", 5.0)
    )  # min seconds between requests

    cache_dir = Path(__file__).parent / ".cache" / "overpass"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    def _cache_path_for_query(qstr: str) -> Path:
        h = hashlib.sha256(qstr.encode("utf-8")).hexdigest()
        return cache_dir / f"{h}.json"

    def _read_cache(qstr: str):
        p = _cache_path_for_query(qstr)
        if not p.exists():
            return None
        try:
            m = p.stat().st_mtime
            age = time.time() - m
            if age > CACHE_TTL:
                return None
            with p.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    def _write_cache(qstr: str, data):
        p = _cache_path_for_query(qstr)
        try:
            with p.open("w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except Exception:
            pass

    # simple global rate limiter persisted to a file so separate runs share it
    rate_file = cache_dir / "last_request_ts"

    def _ensure_rate_limit():
        try:
            last = float(rate_file.read_text()) if rate_file.exists() else 0.0
        except Exception:
            last = 0.0
        now = time.time()
        wait = RATE_LIMIT_SECONDS - (now - last)
        if wait > 0:
            time.sleep(wait)
        try:
            rate_file.write_text(str(time.time()))
        except Exception:
            pass

    headers = {"User-Agent": "CityGuides/1.0"}
    # try cache first
    cached = _read_cache(q)
    if cached is not None:
        try:
            j = cached
        except Exception:
            j = None
    else:
        # Try multiple Overpass endpoints with retries/backoff to reduce 504s
        tried = []
        j = None
        for base_url in OVERPASS_URLS:
            try:
                _ensure_rate_limit()
                attempts = int(os.environ.get("OVERPASS_RETRIES", 2))
                for attempt in range(1, attempts + 1):
                    try:
                        own_session = False
                        if session is None:
                            session = aiohttp.ClientSession()
                            own_session = True
                        timeout = aiohttp.ClientTimeout(total=int(os.environ.get("OVERPASS_TIMEOUT", 20)))
                        async with session.post(base_url, data={"data": q}, headers=headers, timeout=timeout) as r:
                            if r.status != 200:
                                if own_session:
                                    await session.close()
                                continue
                            j = await r.json()
                            _write_cache(q, j)
                            if own_session:
                                await session.close()
                            break
                    except Exception:
                        if attempt < attempts:
                            time.sleep(1 * attempt)
                        else:
                            raise
                if j is not None:
                    break
            except Exception:
                tried.append(base_url)
                continue

        if j is None:
            # on failure, try to fall back to stale cache if available
            stale_p = _cache_path_for_query(q)
            if stale_p.exists():
                try:
                    with stale_p.open("r", encoding="utf-8") as fh:
                        j = json.load(fh)
                except Exception:
                    return []
            else:
                return []

    if j is None:
        return []
    elements = j.get("elements", [])
    # Limit elements to avoid processing too many and causing timeouts
    elements = elements[:200]
    out = []

    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("operator") or "Unnamed"

        # For historic sites, try to generate better names from tags
        if poi_type == "historic" and name == "Unnamed":
            # Try various tag fields for better names
            better_name = None
            if tags.get("inscription"):
                # Use first 50 chars of inscription as name
                inscription = tags["inscription"].strip()
                better_name = inscription[:50] + ("..." if len(inscription) > 50 else "")
            elif tags.get("description"):
                desc = tags["description"].strip()
                better_name = desc[:50] + ("..." if len(desc) > 50 else "")
            elif tags.get("memorial"):
                memorial_type = tags["memorial"].replace("_", " ").title()
                if tags.get("wikidata"):
                    better_name = f"{memorial_type} Memorial"
                else:
                    better_name = memorial_type
            elif tags.get("historic"):
                historic_type = tags["historic"].replace("_", " ").title()
                better_name = historic_type

            if better_name:
                name = better_name

        # Skip if still unnamed and no useful information
        if name == "Unnamed" and not any(tags.get(k) for k in ["inscription", "description", "memorial", "wikidata"]):
            continue

        # Get lat/lon
        if el["type"] == "node":
            lat = el.get("lat")
            lon = el.get("lon")
        else:
            center = el.get("center")
            if center:
                lat = center["lat"]
                lon = center["lon"]
            else:
                continue

        # Build address
        address = (
            tags.get("addr:full")
            or f"{tags.get('addr:housenumber','')} {tags.get('addr:street','')} {tags.get('addr:city','')} {tags.get('addr:postcode','')}".strip()
        )
        if not address:
            address = reverse_geocode(lat, lon) or f"{lat}, {lon}"

        # For non-restaurant POIs, skip chain filtering (doesn't apply)
        if poi_type == "restaurant" and local_only:
            name_lower = name.lower()
            if any(chain.lower() in name_lower for chain in CHAIN_KEYWORDS):
                continue

        website = tags.get("website") or tags.get("contact:website")
        osm_type = el.get("type")
        osm_id = el.get("id")
        osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"

        tags_str = ", ".join([f"{k}={v}" for k, v in tags.items()])

        entry = {
            "osm_id": osm_id,
            "name": name,
            "website": website,
            "osm_url": osm_url,
            "amenity": tags.get("amenity", ""),
            "historic": tags.get("historic", ""),
            "tourism": tags.get("tourism", ""),
            "leisure": tags.get("leisure", ""),
            "cost": tags.get("cost", ""),
            "address": address,
            "lat": lat,
            "lon": lon,
            "tags": tags_str,
        }
        out.append(entry)

    # Sort by relevance (prioritize named entries, then by type significance)
    def sort_key(entry):
        name = entry.get("name", "")
        historic_type = entry.get("historic", "")

        # Primary: Prefer named entries over unnamed
        name_score = 0 if name == "Unnamed" else 1

        # Secondary: Prefer more significant historic types
        type_priority = {
            "monument": 10, "castle": 9, "palace": 8, "church": 7, "cathedral": 7,
            "temple": 6, "mosque": 6, "museum": 5, "fort": 4, "tower": 3,
            "ruins": 2, "archaeological_site": 2, "memorial": 1
        }.get(historic_type, 0)

        return (-name_score, -type_priority, len(name))

    out.sort(key=sort_key, reverse=True)
    return out[:limit]


async def async_discover_pois(city: Optional[str] = None, poi_type: str = "restaurant", limit: int = 200, local_only: bool = False, bbox: Optional[Union[list[float], tuple[float, float, float, float]]] = None, session: Optional[aiohttp.ClientSession] = None):
    if bbox is None:
        if city is None:
            return []
        bbox = await async_geocode_city(city, session=session)
    if not bbox:
        return []
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"

    poi_queries = {
        "restaurant": '["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court"]',
        "historic": '["tourism"="attraction"]',
        "museum": '["tourism"="museum"]',
        "park": '["leisure"="park"]',
        "market": '["amenity"="marketplace"]',
        "transport": '["amenity"~"bus_station|train_station|subway_entrance|ferry_terminal|airport"]',
        "family": '["leisure"~"playground|amusement_arcade|miniature_golf"]',
        "event": '["amenity"~"theatre|cinema|arts_centre|community_centre"]',
        "local": '["tourism"~"attraction"]',
        "hidden": '["tourism"~"attraction"]',
        "coffee": '["amenity"~"cafe|coffee_shop"]',
    }

    amenity_filter = poi_queries.get(poi_type, poi_queries["restaurant"])
    q = f"[out:json][timeout:60];(node{amenity_filter}({bbox_str});way{amenity_filter}({bbox_str});relation{amenity_filter}({bbox_str}););out center;"

    CACHE_TTL = int(os.environ.get("OVERPASS_CACHE_TTL", 60 * 60 * 6))
    RATE_LIMIT_SECONDS = float(os.environ.get("OVERPASS_MIN_INTERVAL", 5.0))

    cache_dir = Path(__file__).parent / ".cache" / "overpass"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    def _cache_path_for_query(qstr: str) -> Path:
        h = hashlib.sha256(qstr.encode("utf-8")).hexdigest()
        return cache_dir / f"{h}.json"

    async def _read_cache(qstr: str):
        p = _cache_path_for_query(qstr)
        if not p.exists():
            return None
        try:
            m = p.stat().st_mtime
            age = time.time() - m
            if age > CACHE_TTL:
                return None
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    async def _write_cache(qstr: str, data):
        p = _cache_path_for_query(qstr)
        try:
            p.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass

    rate_file = cache_dir / "last_request_ts"

    async def _ensure_rate_limit():
        try:
            last = float(rate_file.read_text()) if rate_file.exists() else 0.0
        except Exception:
            last = 0.0
        now = time.time()
        wait = RATE_LIMIT_SECONDS - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            rate_file.write_text(str(time.time()))
        except Exception:
            pass

    headers = {"User-Agent": "CityGuides/1.0"}
    cached = await _read_cache(q)
    j = None
    if cached is not None:
        j = cached
    else:
        j = None
        for base_url in OVERPASS_URLS:
            try:
                await _ensure_rate_limit()
                attempts = int(os.environ.get("OVERPASS_RETRIES", 2))
                for attempt in range(1, attempts + 1):
                    try:
                        own_session = False
                        if session is None:
                            session = aiohttp.ClientSession()
                            own_session = True
                        timeout = aiohttp.ClientTimeout(total=int(os.environ.get("OVERPASS_TIMEOUT", 20)))
                        async with session.post(base_url, data={"data": q}, headers=headers, timeout=timeout) as r:
                            r.raise_for_status()
                            j = await r.json()
                            await _write_cache(q, j)
                            break
                    except Exception:
                        if attempt < attempts:
                            await asyncio.sleep(1 * attempt)
                        else:
                            raise
                if j is not None:
                    break
            except Exception:
                continue

        if j is None:
            stale_p = _cache_path_for_query(q)
            if stale_p.exists():
                try:
                    j = json.loads(stale_p.read_text(encoding="utf-8"))
                except Exception:
                    return []
            else:
                return []

    elements = j.get("elements", [])
    elements = elements[:200]
    skip_reverse = len(elements) > 50
    out = []

    cuisine_token = _singularize(None) if None else None

    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("operator") or "Unnamed"
        if poi_type == "historic" and name == "Unnamed":
            better_name = None
            if tags.get("inscription"):
                inscription = tags["inscription"].strip()
                better_name = inscription[:50] + ("..." if len(inscription) > 50 else "")
            elif tags.get("description"):
                desc = tags["description"].strip()
                better_name = desc[:50] + ("..." if len(desc) > 50 else "")
            elif tags.get("memorial"):
                memorial_type = tags["memorial"].replace("_", " ").title()
                if tags.get("wikidata"):
                    better_name = f"{memorial_type} Memorial"
                else:
                    better_name = memorial_type
            elif tags.get("historic"):
                historic_type = tags["historic"].replace("_", " ").title()
                better_name = historic_type

            if better_name:
                name = better_name

        if name == "Unnamed" and not any(tags.get(k) for k in ["inscription", "description", "memorial", "wikidata"]):
            continue

        if el["type"] == "node":
            lat = el.get("lat")
            lon = el.get("lon")
        else:
            center = el.get("center")
            if center:
                lat = center["lat"]
                lon = center["lon"]
            else:
                continue

        address = (
            tags.get("addr:full")
            or f"{tags.get('addr:housenumber','')} {tags.get('addr:street','')} {tags.get('addr:city','')} {tags.get('addr:postcode','')}".strip()
        )
        if not address:
            if skip_reverse:
                address = f"{lat}, {lon}"
            else:
                address = await async_reverse_geocode(lat, lon, session=session) or f"{lat}, {lon}"

        if poi_type == "restaurant" and local_only:
            name_lower = name.lower()
            if any(chain.lower() in name_lower for chain in CHAIN_KEYWORDS):
                continue

        website = tags.get("website") or tags.get("contact:website")
        osm_type = el.get("type")
        osm_id = el.get("id")
        osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        tags_str = ", ".join([f"{k}={v}" for k, v in tags.items()])

        entry = {
            "osm_id": osm_id,
            "name": name,
            "website": website,
            "osm_url": osm_url,
            "amenity": tags.get("amenity", ""),
            "historic": tags.get("historic", ""),
            "tourism": tags.get("tourism", ""),
            "leisure": tags.get("leisure", ""),
            "cost": tags.get("cost", ""),
            "address": address,
            "lat": lat,
            "lon": lon,
            "tags": tags_str,
        }
        out.append(entry)

    def sort_key(entry):
        name = entry.get("name", "")
        historic_type = entry.get("historic", "")
        name_score = 0 if name == "Unnamed" else 1
        type_priority = {
            "monument": 10, "castle": 9, "palace": 8, "church": 7, "cathedral": 7,
            "temple": 6, "mosque": 6, "museum": 5, "fort": 4, "tower": 3,
            "ruins": 2, "archaeological_site": 2, "memorial": 1
        }.get(historic_type, 0)
        return (-name_score, -type_priority, len(name))

    out.sort(key=sort_key, reverse=True)
    return out[:limit]
