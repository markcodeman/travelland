import requests
import time
import os
import json
import hashlib
from pathlib import Path
from urllib.parse import urlencode

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def reverse_geocode(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        j = r.json()
        return j.get("display_name", "")
    except Exception:
        return ""


def geocode_city(city):
    params = {"q": city, "format": "json", "limit": 1}
    headers = {"User-Agent": "CityGuides/1.0", "Accept-Language": "en"}
    r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    j = r.json()
    if not j:
        return None
    entry = j[0]
    # return bbox as (south, west, north, east)
    bbox = entry.get("boundingbox")
    if bbox and len(bbox) == 4:
        south, north, west, east = (
            float(bbox[0]),
            float(bbox[1]),
            float(bbox[2]),
            float(bbox[3]),
        )
        # Overpass expects south,west,north,east
        return (south, west, north, east)
    return None


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


def discover_restaurants(city, limit=200, cuisine=None, local_only=False):
    """Discover restaurant POIs for a city using Nominatim + Overpass.
    We no longer force a cuisine= filter into the Overpass query because many
    POIs don't set cuisine tags. Instead we fetch amenities and perform
    name/tag matching in Python. If `cuisine` is provided it is used as a
    post-filter (with simple plural handling).

    Returns list of candidates with possible website or OSM url.
    """
    bbox = geocode_city(city)
    if not bbox:
        return []
    south, west, north, east = bbox
    # Overpass bbox format: south,west,north,east
    bbox_str = f"{south},{west},{north},{east}"
    # query nodes/ways/relations with amenity=restaurant, fast_food, cafe, etc.
    amenity_filter = '["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court"]'
    # Do NOT add a cuisine filter to the Overpass query — we'll match name/tags
    # in Python to be more flexible (many POIs don't set cuisine tags).
    q = f"[out:json][timeout:60];(node{amenity_filter}({bbox_str});way{amenity_filter}({bbox_str});relation{amenity_filter}({bbox_str}););out center;"
    # ---- CACHING & RATE LIMIT -------------------------------------------------
    # Use an on-disk cache (per-query hash) to avoid repeated heavy Overpass
    # queries and a simple global rate limiter to avoid spamming the API.
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
            # sleep to respect rate limit
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
                # exponential backoff for each endpoint attempt
                attempts = int(os.environ.get("OVERPASS_RETRIES", 2))
                for attempt in range(1, attempts + 1):
                    try:
                        # shorten default Overpass timeout to 20s for interactive queries
                        r = requests.post(
                            base_url,
                            data={"data": q},
                            headers=headers,
                            timeout=int(os.environ.get("OVERPASS_TIMEOUT", 20)),
                        )
                        r.raise_for_status()
                        j = r.json()
                        _write_cache(q, j)
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
                # continue to next endpoint
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
    elements = j.get("elements", [])
    out = []
    # prepare cuisine matching token (singularized)
    cuisine_token = _singularize(cuisine) if cuisine else None

    # Process all elements, not just the first 'limit' because filtering will reduce count
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("operator") or "Unnamed"
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
        # Skip slow reverse geocoding for now to keep it dynamic and fast
        if not address:
            address = f"{lat}, {lon}"

        # Filter chains if "Local Only" is requested
        name_lower = name.lower()
        if local_only and any(chain.lower() in name_lower for chain in CHAIN_KEYWORDS):
            continue

        # Post-filter by cuisine/name/tag matching when requested.
        # Build a searchable text blob from name and tags.
        tags_str = ", ".join([f"{k}={v}" for k, v in tags.items()])
        searchable = " ".join([name_lower, tags_str.lower()])
        if cuisine_token:
            # also check cuisine tag specifically
            cuisine_tag = (tags.get("cuisine") or "").lower()
            # Ensure we don't match empty strings
            match_in_tags = cuisine_token in searchable
            match_in_cuisine = cuisine_token in cuisine_tag
            match_reverse = cuisine_tag and _singularize(cuisine_tag) in cuisine_token

            if not (match_in_tags or match_in_cuisine or match_reverse):
                # no match for requested cuisine, skip
                continue
        website = tags.get("website") or tags.get("contact:website")
        osm_type = el.get("type")  # node/way/relation
        osm_id = el.get("id")
        osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        # keep tags_str as built above
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

    # Sort for budget-friendly: prioritize cheaper amenities and cost
    def sort_key(entry):
        amenity = entry["amenity"]
        cost = entry["cost"]
        # Amenity priority: fast_food=1, cafe=2, restaurant=3, others=4
        amenity_score = {"fast_food": 1, "cafe": 2, "restaurant": 3}.get(amenity, 4)
        # Cost score: cheap=1, moderate=2, expensive=3, unknown=2 (assume moderate)
        cost_score = {"cheap": 1, "moderate": 2, "expensive": 3}.get(
            cost.lower() if cost else "", 2
        )
        return (amenity_score, cost_score)

    out.sort(key=sort_key)
    return out
