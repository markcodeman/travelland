from flask import Flask, render_template, request, jsonify
from rich.traceback import install as rich_traceback_install

rich_traceback_install()
from pathlib import Path
import json
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
import logging
import requests
import re
import time

_here = os.path.dirname(__file__)
# load local .env placed inside the city-guides folder (keeps keys out of repo root)
load_dotenv(dotenv_path=os.path.join(_here, ".env"))

import semantic
import overpass_provider
from overpass_provider import _singularize
import multi_provider
import image_provider

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Gate very verbose per-venue opening-hours debug logging behind an env flag so
# we can avoid huge log noise during searches. Set VERBOSE_OPEN_HOURS=1 to
# enable the old behaviour for debugging.
VERBOSE_OPEN_HOURS = os.getenv("VERBOSE_OPEN_HOURS", "0") == "1"

# Allow configuring cache TTLs via environment variables with sane defaults
CACHE_TTL_TELEPORT = int(os.getenv("CACHE_TTL_TELEPORT", 604800))  # default 1 week
CACHE_TTL_CITY_INFO = int(os.getenv("CACHE_TTL_CITY_INFO", 86400))  # default 1 day


app = Flask(__name__, static_folder="static", template_folder="templates")

# Small mapping of known transit provider links by city (best-effort)
PROVIDER_LINKS = {
    "london": [
        {"name": "TfL (official)", "url": "https://tfl.gov.uk"},
        {
            "name": "Google Transit (TfL)",
            "url": "https://www.google.com/maps/place/London+Underground",
        },
    ],
    "paris": [
        {"name": "RATP (official)", "url": "https://www.ratp.fr/en"},
        {"name": "SNCF (regional)", "url": "https://www.sncf.com/en"},
    ],
    "new york": [
        {"name": "MTA (official)", "url": "https://new.mta.info"},
        {
            "name": "NYC Subway map (Google)",
            "url": "https://www.google.com/maps/place/New+York+City+Subway",
        },
    ],
    "shanghai": [
        {"name": "Shanghai Metro (official)", "url": "http://service.shmetro.com"},
        {
            "name": "Metro / Transit info",
            "url": "https://www.travelchinaguide.com/cityguides/shanghai/transportation.htm",
        },
    ],
    "tokyo": [
        {"name": "Tokyo Metro (official)", "url": "https://www.tokyometro.jp/en/"},
    ],
    "default": [{"name": "Google Transit", "url": "https://www.google.com/maps"}],
}


def get_provider_links(city_name):
    if not city_name:
        return PROVIDER_LINKS.get("default")
    key = city_name.strip().lower()
    # try full match then substring match
    if key in PROVIDER_LINKS:
        return PROVIDER_LINKS[key]
    for k, v in PROVIDER_LINKS.items():
        if k != "default" and k in key:
            return v
    return PROVIDER_LINKS.get("default")


def shorten_place(name):
    """Return a compact display name for a possibly long place string.
    Strategy:
      - split on commas and examine tokens right-to-left
      - skip tokens that look like generic regions (e.g. 'Região', 'Region', 'Metropolitana', 'Southeast Region', country names)
      - prefer the first non-generic token from the right; fallback to the first token
    """
    if not name:
        return name
    try:
        toks = [t.strip() for t in name.split(",") if t.strip()]
        if not toks:
            return name.strip()
        generic = [
            "região",
            "regiao",
            "region",
            "metropolitana",
            "metropolitan",
            "região metropolitana",
            "região geográfica",
            "região geográfica intermediária",
            "southeast region",
            "north",
            "south",
            "east",
            "west",
            "region",
            "state",
            "country",
        ]
        # Prefer a non-generic token that looks like a city (contains accented chars or multiple words or is reasonably long).
        preferred = None
        for t in reversed(toks):
            tl = t.lower()
            skip = any(g in tl for g in generic)
            if skip:
                continue
            # heuristics for a good city token
            if (
                re.search(r"[àáâãäåéèêíïóôõöúçñ]", t.lower())
                or len(t.split()) > 1
                or len(t) > 6
            ):
                return t
            if not preferred:
                preferred = t
        if preferred:
            return preferred

        # fallback: prefer a token that contains accented characters or longer words
        def score_token(x):
            s = 0
            if re.search(r"[àáâãäåéèêíïóôõöúçñ]", x.lower()):
                s += 5
            s += len(x.split())
            return s

        best = max(toks, key=score_token)
        return best
    except Exception:
        return name


# Expose whether Groq API key is configured to templates
@app.context_processor
def inject_feature_flags():
    return {"GROQ_ENABLED": bool(os.getenv("GROQ_API_KEY"))}


def geocode_city(city):
    """Geocode a city name to (lat, lon) using Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city, "format": "json", "limit": 1}
    try:
        headers = {"User-Agent": "city-guides-app", "Accept-Language": "en"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"Geocoding failed: {e}")
    return None, None


def get_country_for_city(city):
    """Return country name for a given city using Nominatim (best-effort)."""
    if not city:
        return None
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
        # Request results in English where possible to prefer ASCII country names
        headers = {"User-Agent": "city-guides-app", "Accept-Language": "en"}
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        if data:
            addr = data[0].get("address", {})
            country = addr.get("country")
            # prefer an ASCII/English country name when possible; Nominatim sometimes returns
            # the localized/native country name (e.g. '中国') which may not work with downstream
            # services. Use the display_name fallback to extract an English name if needed.
            if country:
                try:
                    # if country contains non-ascii characters, try to derive an English name
                    if any(ord(ch) > 127 for ch in country):
                        display = data[0].get("display_name", "") or ""
                        parts = [p.strip() for p in display.split(",") if p.strip()]
                        if parts:
                            # last part of display_name is usually the country in English
                            candidate = parts[-1]
                            if any(c.isalpha() for c in candidate):
                                return candidate
                except Exception:
                    pass
            # fallback to country or country_code
            return country or addr.get("country_code")
    except Exception:
        pass
    return None


def get_currency_for_country(country):
    """Return the primary currency code (ISO 4217) for a given country name using restcountries API."""
    if not country:
        return None
    try:
        url = (
            f"https://restcountries.com/v3.1/name/{requests.utils.requote_uri(country)}"
        )
        resp = requests.get(
            url,
            params={"fields": "name,currencies"},
            headers={"User-Agent": "city-guides-app"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            # currencies is an object with codes as keys
            cur_obj = data[0].get("currencies") or {}
            if isinstance(cur_obj, dict) and cur_obj:
                # return first currency code
                for code in cur_obj.keys():
                    return code
    except Exception:
        pass
    return None


def get_currency_name(code):
    """Return a human-friendly currency name for an ISO 4217 code.
    Uses a small internal map and falls back to RestCountries lookup when possible.
    """
    if not code:
        return None
    code = code.strip().upper()
    names = {
        "USD": "US Dollar",
        "EUR": "Euro",
        "GBP": "Pound Sterling",
        "JPY": "Japanese Yen",
        "CAD": "Canadian Dollar",
        "AUD": "Australian Dollar",
        "MXN": "Mexican Peso",
        "CNY": "Chinese Yuan",
        "THB": "Thai Baht",
        "RUB": "Russian Ruble",
        "CUP": "Cuban Peso",
        "VES": "Venezuelan Bolívar",
        "KES": "Kenyan Shilling",
        "ZWL": "Zimbabwean Dollar",
        "PEN": "Peruvian Sol",
    }
    if code in names:
        return names[code]
    # try RestCountries API to resolve name
    try:
        url = f"https://restcountries.com/v3.1/currency/{requests.utils.requote_uri(code)}"
        resp = requests.get(
            url,
            params={"fields": "name,currencies"},
            headers={"User-Agent": "city-guides-app"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            cur_obj = data[0].get("currencies") or {}
            # currencies is dict mapping code -> {name, symbol}
            if isinstance(cur_obj, dict) and code in cur_obj:
                info = cur_obj.get(code)
                if isinstance(info, dict):
                    return info.get("name") or info.get("symbol") or code
    except Exception:
        pass
    return code


def _fetch_image_from_website(url):
    """Attempt to fetch an og:image or other image hint from a webpage.
    Returns absolute image URL or None.
    """
    try:
        headers = {"User-Agent": "TravelLand/1.0"}
        resp = requests.get(url, headers=headers, timeout=4)
        resp.raise_for_status()
        html = resp.text
        # look for og:image
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r'<meta[^>]+name=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
        if not m:
            m = re.search(
                r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE,
            )
        if m:
            img = m.group(1)
            # make absolute if needed
            try:
                p = urlparse(img)
                if not p.scheme:
                    base = urlparse(url)
                    img = f"{base.scheme}://{base.netloc}{img if img.startswith('/') else '/' + img}"
            except Exception:
                pass
            return img
    except Exception:
        return None
    return None


def get_cost_estimates(city, ttl_seconds=None):
    """Fetch average local prices for a city using Teleport free API with caching and a small local fallback.

    Returns a list of dicts: [{'label': 'Coffee', 'value': 12.5}, ...]
    """
    if not city:
        return []

    if ttl_seconds is None:
        ttl_seconds = CACHE_TTL_TELEPORT

    try:
        cache_dir = Path(_here) / ".cache" / "teleport_prices"
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = re.sub(r"[^a-z0-9]+", "_", city.strip().lower())
        cache_file = cache_dir / f"{key}.json"
        # return cached if fresh
        if cache_file.exists():
            try:
                raw = json.loads(cache_file.read_text())
                if raw.get("ts") and time.time() - raw["ts"] < ttl_seconds:
                    return raw.get("data", [])
            except Exception:
                pass

        # Try Teleport search -> city item -> urban area -> prices
        base = "https://api.teleport.org"
        try:
            s = requests.get(
                f"{base}/api/cities/",
                params={"search": city, "limit": 5},
                timeout=6,
                headers={"User-Agent": "city-guides-app"},
            )
            s.raise_for_status()
            j = s.json()
            results = j.get("_embedded", {}).get("city:search-results", [])
            city_item_href = None
            for r in results:
                href = r.get("_links", {}).get("city:item", {}).get("href")
                if href:
                    city_item_href = href
                    break
            if not city_item_href:
                raise RuntimeError("no city item from teleport")

            ci = requests.get(
                city_item_href, timeout=6, headers={"User-Agent": "city-guides-app"}
            )
            ci.raise_for_status()
            ci_j = ci.json()
            urban_href = ci_j.get("_links", {}).get("city:urban_area", {}).get("href")
            if not urban_href:
                # no urban area -> no prices available
                raise RuntimeError("no urban area")

            prices_href = urban_href.rstrip("/") + "/prices/"
            p = requests.get(
                prices_href, timeout=6, headers={"User-Agent": "city-guides-app"}
            )
            p.raise_for_status()
            p_j = p.json()

            items = []
            # Teleport responses typically include 'categories' -> each has 'data' list of items
            for cat in p_j.get("categories", []):
                for d in cat.get("data", []):
                    label = d.get("label") or d.get("id")
                    # find a numeric price in common keys
                    val = None
                    for k in (
                        "usd_value",
                        "currency_dollar_adjusted",
                        "price",
                        "amount",
                        "value",
                    ):
                        if k in d and isinstance(d[k], (int, float)):
                            val = float(d[k])
                            break
                    # some Teleport payloads nest price under 'prices' or similar
                    if val is None:
                        # try nested structures
                        for kk in d.keys():
                            vvv = d.get(kk)
                            if isinstance(vvv, (int, float)):
                                val = float(vvv)
                                break
                    if label and val is not None:
                        items.append({"label": label, "value": round(val, 2)})

            # prefer a short curated subset (coffee, beer, meal, taxi, hotel)
            keywords = ["coffee", "beer", "meal", "taxi", "hotel", "apartment", "rent"]
            selected = []
            lower_seen = set()
            for k in keywords:
                for it in items:
                    if (
                        k in it["label"].lower()
                        and it["label"].lower() not in lower_seen
                    ):
                        selected.append(it)
                        lower_seen.add(it["label"].lower())
                        break
            # if not selected, take first N items
            if not selected:
                selected = items[:8]

            # save cache
            try:
                cache_file.write_text(json.dumps({"ts": time.time(), "data": selected}))
            except Exception:
                pass
            return selected
        except Exception as e:
            logging.debug(f"Teleport fetch failed: {e}")
            # fall through to local fallback

        # Local fallback map keyed by country (best-effort)
        try:
            country = get_country_for_city(city) or ""
        except Exception:
            country = ""
        fb = {
            "china": [
                {"label": "Coffee (cafe)", "value": 20.0},
                {"label": "Local beer (0.5L)", "value": 12.0},
                {"label": "Meal (mid-range)", "value": 70.0},
                {"label": "Taxi start (local)", "value": 10.0},
                {"label": "Hotel (1 night, mid)", "value": 350.0},
            ],
            "russia": [
                {"label": "Coffee (cafe)", "value": 200.0},
                {"label": "Local beer (0.5L)", "value": 150.0},
                {"label": "Meal (mid-range)", "value": 700.0},
                {"label": "Taxi start (local)", "value": 100.0},
                {"label": "Hotel (1 night, mid)", "value": 4000.0},
            ],
            "cuba": [
                {"label": "Coffee (cafe)", "value": 50.0},
                {"label": "Local beer (0.5L)", "value": 60.0},
                {"label": "Meal (mid-range)", "value": 200.0},
                {"label": "Taxi (short)", "value": 80.0},
                {"label": "Hotel (1 night, mid)", "value": 2500.0},
            ],
            "portugal": [
                {"label": "Coffee (cafe)", "value": 1.6},
                {"label": "Local beer (0.5L)", "value": 2.0},
                {"label": "Meal (mid-range)", "value": 12.0},
                {"label": "Taxi start (local)", "value": 3.0},
                {"label": "Hotel (1 night, mid)", "value": 80.0},
            ],
            "united states": [
                {"label": "Coffee (cafe)", "value": 3.5},
                {"label": "Local beer (0.5L)", "value": 5.0},
                {"label": "Meal (mid-range)", "value": 20.0},
                {"label": "Taxi start (local)", "value": 3.0},
                {"label": "Hotel (1 night, mid)", "value": 140.0},
            ],
            "united kingdom": [
                {"label": "Coffee (cafe)", "value": 2.8},
                {"label": "Local beer (0.5L)", "value": 4.0},
                {"label": "Meal (mid-range)", "value": 15.0},
                {"label": "Taxi start (local)", "value": 3.5},
                {"label": "Hotel (1 night, mid)", "value": 120.0},
            ],
            "thailand": [
                {"label": "Coffee (cafe)", "value": 50.0},
                {"label": "Local beer (0.5L)", "value": 60.0},
                {"label": "Meal (mid-range)", "value": 250.0},
                {"label": "Taxi start (local)", "value": 35.0},
                {"label": "Hotel (1 night, mid)", "value": 1200.0},
            ],
        }
        lookup = (country or "").strip().lower()
        # sometimes country is a code; attempt to match common names
        for k in fb.keys():
            if k in lookup:
                try:
                    cache_file.write_text(
                        json.dumps({"ts": time.time(), "data": fb[k]})
                    )
                except Exception:
                    pass
                return fb[k]
        # nothing found
        return []
    except Exception:
        return []


def fetch_us_state_advisory(country):
    """Best-effort fetch of US State Dept travel advisory for a country.
    Returns dict {url, summary} or None.
    """
    if not country:
        return None
    # construct slug
    slug = country.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    urls = [
        f"https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/{slug}.html",
        f"https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/2020/{slug}.html",
    ]
    for u in urls:
        try:
            resp = requests.get(u, headers={"User-Agent": "TravelLand/1.0"}, timeout=8)
            if resp.status_code != 200:
                continue
            html = resp.text
            # try meta description
            m = re.search(
                r'<meta\s+name="description"\s+content="([^"]+)"', html, flags=re.I
            )
            summary = None
            if m:
                summary = m.group(1).strip()
            else:
                # try to find first paragraph
                m2 = re.search(r"<p[^>]*>(.*?)</p>", html, flags=re.I | re.S)
                if m2:
                    summary = re.sub(r"<[^>]+>", "", m2.group(1)).strip()
            return {"url": u, "summary": summary}
        except Exception:
            continue
    return None


def fetch_safety_section(city):
    """Attempt to extract a 'Safety' or 'Crime' section from Wikivoyage or Wikipedia.
    Fallbacks:
      - parse sectioned content via action=parse and look for headings containing keywords
      - use plaintext extracts and search for paragraphs mentioning keywords
      - as last resort, ask semantic.search_and_reason to synthesise tips
    Returns a string (possibly empty).
    """
    if not city:
        return ""
    keywords = [
        "safety",
        "crime",
        "security",
        "safety and security",
        "crime and safety",
    ]
    # Try Wikivoyage first, then Wikipedia
    sites = [
        ("https://en.wikivoyage.org/w/api.php"),
        ("https://en.wikipedia.org/w/api.php"),
    ]
    for api in sites:
        try:
            # fetch sections list
            params = {
                "action": "parse",
                "page": city,
                "prop": "sections",
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                api, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            data = resp.json()
            secs = data.get("parse", {}).get("sections", [])
            for s in secs:
                line = (s.get("line") or "").lower()
                for kw in keywords:
                    if kw in line:
                        idx = s.get("index")
                        # fetch that section's HTML and strip tags
                        params2 = {
                            "action": "parse",
                            "page": city,
                            "prop": "text",
                            "section": idx,
                            "format": "json",
                            "redirects": 1,
                        }
                        resp2 = requests.get(
                            api,
                            params=params2,
                            headers={"User-Agent": "TravelLand/1.0"},
                            timeout=8,
                        )
                        resp2.raise_for_status()
                        html = (
                            resp2.json().get("parse", {}).get("text", {}).get("*", "")
                        )
                        text = re.sub(r"<[^>]+>", "", html).strip()
                        if text:
                            return _sanitize_safety_text(text)
        except Exception:
            # ignore and try next source
            continue

    # Try plaintext extracts and look for paragraphs mentioning keywords
    try:
        for api in sites:
            params = {
                "action": "query",
                "prop": "extracts",
                "explaintext": True,
                "titles": city,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                api, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                extract = p.get("extract", "") or ""
                lower = extract.lower()
                for kw in keywords:
                    if kw in lower:
                        # try to return the paragraph containing the keyword
                        parts = re.split(r"\n\s*\n", extract)
                        for part in parts:
                            if kw in part.lower():
                                return _sanitize_safety_text(part.strip())
    except Exception:
        pass

    # Last resort: synthesise safety tips via semantic module
    try:
        q = f"Provide 5 concise crime and safety tips for travelers in {city}. Include common scams, areas to avoid, and nighttime safety."
        res = semantic.search_and_reason(q, city, mode="explorer")
        if isinstance(res, dict):
            out = str(res.get("answer") or res.get("text") or res)
        else:
            out = str(res)
        return _sanitize_safety_text(out)
    except Exception:
        return []


def _sanitize_safety_text(raw):
    """Sanitize safety text: remove salutations/persona intros and return concise sentences (up to 5).
    Heuristics:
      - remove leading lines that look like greetings or 'As Marco' intros
      - split into sentences and find the first sentence that looks like advice (starts with a verb or contains 'be', 'avoid', "don't")
      - return up to 5 sentences starting from that point
    """
    if not raw:
        return []
    try:
        text = raw.strip()
        # remove common greetings at start
        text = re.sub(
            r"^(\s*(buon giorno|bonjour|hello|hi|dear|greetings)[^\n]*\n)+",
            "",
            text,
            flags=re.I,
        )
        # remove lines that mention 'Marco' as persona
        text = re.sub(r"(?im)^.*\bmarco\b.*$", "", text)
        # collapse multiple newlines
        text = re.sub(r"\n{2,}", "\n", text).strip()

        # split into sentences (rough)
        sentences = re.findall(r"[^\.\!\?]+[\.\!\?]+", text)
        if not sentences:
            # fallback to line splits
            sentences = [s.strip() for s in text.split("\n") if s.strip()]

        # find first advisory-like sentence
        advice_idx = 0
        adv_regex = re.compile(
            r"^(Be|Avoid|Don't|Do not|Keep|Watch|Stay|Avoiding|Use caution|Exercise|Carry|Keep)\b",
            re.I,
        )
        for i, s in enumerate(sentences):
            if adv_regex.search(s.strip()):
                advice_idx = i
                break

        # take up to 5 sentences from advice_idx; if advice_idx==0, still take first 5
        chosen = sentences[advice_idx : advice_idx + 5]
        # final cleanup: remove ordinal lists like '1.' at the start of a sentence
        clean = [re.sub(r"^\s*\d+\.\s*", "", s).strip() for s in chosen]
        return clean
    except Exception:
        return [raw[:1000]]


@app.route("/weather", methods=["POST"])
def weather():
    payload = request.json or {}
    city = (payload.get("city") or "").strip()
    lat = payload.get("lat")
    lon = payload.get("lon")
    print(f"[WEATHER DEBUG] Incoming payload: {payload}")
    if not (lat and lon):
        if not city:
            print("[WEATHER ERROR] No city or lat/lon provided.")
            return jsonify({"error": "city or lat/lon required"}), 400
        lat, lon = geocode_city(city)
        print(f"[WEATHER DEBUG] Geocoded city '{city}' to lat/lon: {lat}, {lon}")
        if not (lat and lon):
            print(f"[WEATHER ERROR] Geocode failed for city: {city}")
            return jsonify({"error": "geocode_failed"}), 400
    try:
        # Open-Meteo API: https://open-meteo.com/en/docs
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "temperature_unit": "celsius",
            "windspeed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto",
        }
        print(f"[WEATHER DEBUG] Requesting Open-Meteo with params: {params}")
        resp = requests.get(url, params=params, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        weather = data.get("current_weather", {})
        print(f"[WEATHER DEBUG] Open-Meteo response: {weather}")
        return jsonify({"lat": lat, "lon": lon, "city": city, "weather": weather})
    except Exception as e:
        print(f"[WEATHER ERROR] Weather fetch failed: {e}")
        return jsonify({"error": "weather_fetch_failed", "details": str(e)}), 500


def get_weather(lat, lon):
    """Fetch current weather for given latitude and longitude using Open-Meteo API."""
    if not lat or not lon:
        return None
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "temperature_unit": "celsius",
            "windspeed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto",
        }
        resp = requests.get(url, params=params, timeout=6)
        resp.raise_for_status()
        data = resp.json().get("current_weather", {})
        return data
    except Exception:
        return None


def _compute_open_now(lat, lon, opening_hours_str):
    # Use a small local helper to avoid spamming debug logs unless explicitly enabled.
    def _ld(msg):
        if VERBOSE_OPEN_HOURS:
            logging.debug(msg)

    """Best-effort server-side opening_hours check.
    - Tries to resolve timezone from lat/lon using timezonefinder if available.
    - Supports simple OSM opening_hours patterns like '24/7' and 'Mo-Sa 09:00-18:00'; Su 10:00-16:00'.
    Returns (is_open: bool|None, next_change_iso: str|None)
    """
    if not opening_hours_str:
        _ld("No opening_hours_str provided. Returning (None, None).")
        return (None, None)

    s = opening_hours_str.strip()
    if not s:
        _ld("Empty opening_hours_str. Returning (None, None).")
        return (None, None)

    # Quick common check
    if "24/7" in s or "24h" in s or "24 hr" in s.lower():
        _ld("Detected 24/7 hours. Returning (True, None).")
        return (True, None)

    # Determine timezone (best-effort)
    tzname = None
    try:
        from timezonefinder import TimezoneFinder

        tf = TimezoneFinder()
        tzname = tf.timezone_at(lat=float(lat), lng=float(lon)) if lat and lon else None
    except Exception:
        tzname = None

    # If timezonefinder isn't available or didn't find a timezone, allow an
    # explicit override via FLASK_TZ (useful on hosts like Render that run in UTC).
    if not tzname:
        tz_env = os.getenv("FLASK_TZ") or os.getenv("DEFAULT_TZ")
        if tz_env:
            tzname = tz_env

    from datetime import datetime, time, timedelta

    try:
        from zoneinfo import ZoneInfo
    except Exception:
        ZoneInfo = None

    if tzname and ZoneInfo:
        try:
            now = datetime.now(ZoneInfo(tzname))
        except Exception:
            now = datetime.now()
    else:
        now = datetime.now()

    _ld(f"Parsed timezone: {tzname}")
    _ld(f"Current datetime: {now}")

    # Map short day names to weekday numbers
    days_map = {"mo": 0, "tu": 1, "we": 2, "th": 3, "fr": 4, "sa": 5, "su": 6}

    # Split alternatives by ';'
    parts = [p.strip() for p in s.split(";") if p.strip()]

    def parse_time(tstr):
        try:
            hh, mm = tstr.split(":")
            return time(int(hh), int(mm))
        except Exception:
            return None

    todays_matches = []
    for p in parts:
        # Example: 'Mo-Sa 09:00-18:00' or 'Su 10:00-16:00' or '09:00-18:00'
        tok = p.split()
        if len(tok) == 1 and "-" in tok[0] and ":" in tok[0]:
            # time only, applies every day
            days = list(range(0, 7))
            times = tok[0]
        elif len(tok) >= 2:
            daypart = tok[0]
            times = tok[1]
            days = []
            if "-" in daypart:
                a, b = daypart.split("-")
                a = a.lower()[:2]
                b = b.lower()[:2]
                if a in days_map and b in days_map:
                    ra = days_map[a]
                    rb = days_map[b]
                    if ra <= rb:
                        days = list(range(ra, rb + 1))
                    else:
                        days = list(range(ra, 7)) + list(range(0, rb + 1))
            else:
                # single day or comma-separated
                for d in daypart.split(","):
                    d = d.strip().lower()[:2]
                    if d in days_map:
                        days.append(days_map[d])
        else:
            continue

        if isinstance(times, str) and "-" in times:
            t1s, t2s = times.split("-", 1)
            t1 = parse_time(t1s)
            t2 = parse_time(t2s)
            if t1 and t2:
                if now.weekday() in days:
                    todays_matches.append((t1, t2))

    _ld(f"Today's matches: {todays_matches}")

    # Check if current time falls in any range
    for t1, t2 in todays_matches:
        _ld(f"Checking time range: {t1} - {t2}")
        dt = now.time()
        if t1 <= dt <= t2:
            _ld("Current time falls within range. Returning (True, None).")
            return (True, None)
        # Handle overnight ranges (e.g., 18:00-02:00)
        elif t1 > t2:
            # range spans midnight
            if dt >= t1 or dt <= t2:
                _ld(
                    "Current time falls within overnight range. Returning (True, None)."
                )
                return (True, None)

    _ld("No matching time range found. Returning (False, None).")
    return (False, None)


def _humanize_opening_hours(opening_hours_str):
    """Return a user-friendly hours string in 12-hour format if possible."""
    if not opening_hours_str:
        return None
    import re
    from datetime import time

    def fmt(tstr):
        try:
            hh, mm = tstr.split(":")
            t = time(int(hh), int(mm))
            return t.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")
        except Exception:
            return tstr

    pretty_parts = []
    for part in opening_hours_str.split(";"):
        part = part.strip()
        if not part:
            continue
        # replace ranges like 10:00-22:30 with 10:00 AM–10:30 PM
        part = re.sub(
            r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})",
            lambda m: f"{fmt(m.group(1))}–{fmt(m.group(2))}",
            part,
        )
        pretty_parts.append(part)
    return "; ".join(pretty_parts) if pretty_parts else None


@app.route("/")
def index():
    phone = "tel:+1-757-755-7505"  # Replace with dynamic value if needed
    return render_template("index.html", phone=phone)


@app.route("/transport")
def transport():
    city = request.args.get("city", "the city")
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    # fetch a banner image for the requested city (best-effort)
    try:
        banner = image_provider.get_banner_for_city(city)
        banner_url = banner.get("url") if banner else None
        banner_attr = banner.get("attribution") if banner else None
    except Exception:
        banner_url = None
        banner_attr = None
    # attempt to load any pre-generated transport JSON for this city
    data_dir = Path(__file__).resolve().parents[1] / "data"
    transport_payload = None
    try:
        for p in data_dir.glob("transport_*.json"):
            try:
                with p.open(encoding="utf-8") as f:
                    j = json.load(f)
                if city.lower() in (j.get("city") or "").lower():
                    transport_payload = j
                    break
            except Exception:
                continue
    except Exception:
        transport_payload = None

    # Quick guide via Wikivoyage (use transport payload if it already contains an extract)
    quick_guide = ""
    if transport_payload and transport_payload.get("wikivoyage_summary"):
        quick_guide = transport_payload.get("wikivoyage_summary")
    else:
        try:
            url = "https://en.wikivoyage.org/w/api.php"
            params = {
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": city,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                quick_guide = p.get("extract", "")
                break
        except Exception:
            quick_guide = ""
    # If Wikivoyage didn't have an extract, try Wikipedia as a fallback
    if not quick_guide:
        try:
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": city,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                quick_guide = p.get("extract", "")
                break
        except Exception:
            quick_guide = quick_guide or ""
    # Attempt to fetch a safety/crime section for server-side initial render
    try:
        initial_safety = fetch_safety_section(city) or []
    except Exception:
        initial_safety = []
    # Attempt to fetch US State Dept advisory for the city's country
    try:
        country = get_country_for_city(city)
        initial_us_advisory = fetch_us_state_advisory(country) if country else None
    except Exception:
        initial_us_advisory = None

    provider_links = (
        transport_payload.get("provider_links") if transport_payload else None
    ) or get_provider_links(city)

    city_display = shorten_place(city)
    return render_template(
        "transport.html",
        city=city,
        city_display=city_display,
        lat=lat,
        lon=lon,
        banner_url=banner_url,
        banner_attr=banner_attr,
        initial_quick_guide=quick_guide,
        initial_safety_tips=initial_safety,
        initial_us_advisory=initial_us_advisory,
        initial_provider_links=provider_links,
        initial_transport=transport_payload,
    )


@app.route("/api/transport")
def api_transport():
    """Return a transport JSON for a requested city.
    Searches files named data/transport_*.json and matches by city substring if provided.
    """
    city_q_raw = (request.args.get("city") or "").strip()
    city_q = city_q_raw.lower()
    data_dir = Path(__file__).resolve().parents[1] / "data"
    files = sorted(data_dir.glob("transport_*.json"))
    payload = None
    for p in files:
        try:
            with p.open(encoding="utf-8") as f:
                j = json.load(f)
            # attach provider links if missing
            try:
                j["provider_links"] = j.get("provider_links") or get_provider_links(
                    j.get("city") or city_q_raw
                )
            except Exception:
                pass
            if city_q and city_q in (j.get("city") or "").lower():
                # attach a compact display name
                try:
                    j["city_display"] = shorten_place(j.get("city") or city_q_raw)
                except Exception:
                    j["city_display"] = j.get("city")
                return jsonify(j)
            if payload is None:
                payload = j
        except Exception:
            continue

    # If a specific city was requested but we didn't find a pre-generated file,
    # return a best-effort minimal payload using geocoding + Wikivoyage extract so
    # the frontend can at least deep-link to Google and show a local quick guide.
    if city_q:
        lat, lon = geocode_city(city_q_raw)
        quick = ""
        try:
            url = "https://en.wikivoyage.org/w/api.php"
            params = {
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": city_q_raw,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                quick = p.get("extract", "")
                break
        except Exception:
            quick = ""

        minimal = {
            "city": city_q_raw,
            "city_display": shorten_place(city_q_raw),
            "generated_at": None,
            "center": {"lat": lat, "lon": lon},
            "wikivoyage_summary": quick,
            "stops": [],
            "stops_count": 0,
            "provider_links": get_provider_links(city_q_raw),
        }
        return jsonify(minimal)

    if payload:
        return jsonify(payload)
    return jsonify({"error": "no_transport_data"}), 404


def _get_city_info(city):
    """Helper function to gather city info from various sources."""
    if not city:
        return {}

    # geocode best-effort
    lat, lon = geocode_city(city)

    # Attempt to reuse existing transport data if present
    data_dir = Path(__file__).resolve().parents[1] / "data"
    transport = None
    try:
        for p in data_dir.glob("transport_*.json"):
            try:
                with p.open(encoding="utf-8") as f:
                    j = json.load(f)
                if city.lower() in (j.get("city") or "").lower():
                    transport = j
                    break
            except Exception:
                continue
    except Exception:
        transport = None

    # Quick guide via Wikivoyage
    quick_guide = ""
    try:
        url = "https://en.wikivoyage.org/w/api.php"
        params = {
            "action": "query",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "titles": city,
            "format": "json",
            "redirects": 1,
        }
        resp = requests.get(
            url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        for p in pages.values():
            quick_guide = p.get("extract", "")
            break
    except Exception:
        quick_guide = ""

    # fallback to Wikipedia if Wikivoyage is empty
    if not quick_guide:
        try:
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": city,
                "format": "json",
                "redirects": 1,
            }
            resp = requests.get(
                url, params=params, headers={"User-Agent": "TravelLand/1.0"}, timeout=8
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for p in pages.values():
                quick_guide = p.get("extract", "")
                break
        except Exception:
            quick_guide = quick_guide or ""

    # Marco recommendation via semantic module
    marco = None
    try:
        q = f"How do I get around {city}? Name the primary transit app or website used by locals and give 3 quick survival tips."
        # use existing semantic search_and_reason function
        marco = semantic.search_and_reason(q, city, mode="explorer")
    except Exception:
        marco = None

    # Safety / crime tips (best-effort extraction) -> list of bullets
    try:
        safety_list = fetch_safety_section(city) or []
    except Exception:
        safety_list = []

    google_link = None
    if lat and lon:
        google_link = f"https://www.google.com/maps/@{lat},{lon},13z/data=!5m1!1e2"
    else:
        google_link = f"https://www.google.com/maps/search/{requests.utils.requote_uri(city + ' public transport')}/data=!5m1!1e2"

    # Country-level US State Dept advisory (best-effort)
    us_advisory = None
    try:
        country = get_country_for_city(city)
        if country:
            us_advisory = fetch_us_state_advisory(country)
    except Exception:
        us_advisory = None

    result = {
        "city": city,
        "city_display": shorten_place(city),
        "lat": lat,
        "lon": lon,
        "google_map": google_link,
        "quick_guide": quick_guide,
        "marco": marco,
        "safety_tips": safety_list,
        "us_state_advisory": us_advisory,
        "transport_available": bool(transport),
        "transport": transport,
        "provider_links": (transport.get("provider_links") if transport else None)
        or get_provider_links(city),
    }
    return result


@app.route("/api/city_info")
def api_city_info():
    """Return quick info for any city: Marco recommendations, Google deep-link, quick guide.
    Falls back to transport JSON if available.
    """
    city = (request.args.get("city") or "").strip()
    if not city:
        return jsonify({"error": "city required"}), 400

    info = _get_city_info(city)
    return jsonify(info)


@app.route("/search", methods=["POST"])
def search():
    payload = request.json or {}
    logging.debug(f"[SEARCH DEBUG] Incoming payload: {payload}")
    city = (payload.get("city") or "").strip()
    user_lat = payload.get("user_lat")
    user_lon = payload.get("user_lon")
    budget = (payload.get("budget") or "").strip().lower()
    q = (payload.get("q") or "").strip().lower()
    import time

    t0 = time.time()
    results = []

    # Detect query intent
    food_keywords = [
        "food",
        "eat",
        "restaurant",
        "cuisine",
        "dining",
        "must eat",
        "must-try",
        "top food",
        "top eats",
        "best food",
        "food highlights",
    ]
    historic_keywords = [
        "historic",
        "history",
        "museum",
        "monument",
        "landmark",
        "sight",
        "sites",
        "attraction",
        "castle",
        "palace",
        "temple",
        "church",
        "cathedral",
        "ruins",
        "archaeological",
        "heritage",
    ]
    currency_keywords = [
        "currency",
        "exchange",
        "money",
        "convert",
        "usd",
        "eur",
        "dollar",
        "euro",
        "pound",
        "yen",
        "peso",
        "baht",
        "rub",
        "shilling",
        "sol",
        "bolivar",
    ]
    transport_keywords = [
        "transport",
        "metro",
        "subway",
        "bus",
        "train",
        "transit",
        "taxi",
        "ride",
        "tram",
        "underground",
    ]
    is_food_query = any(kw in (q or "") for kw in food_keywords)
    is_historic_query = any(kw in (q or "") for kw in historic_keywords)
    is_currency_query = any(kw in (q or "") for kw in currency_keywords)
    is_transport_query = any(kw in (q or "") for kw in transport_keywords)

    city_info = None
    cost_estimates = []
    weather_data = None

    # Only fetch city_info and cost_estimates if needed
    if is_currency_query:
        # For currency queries, fetch cost estimates and currency info
        cost_estimates = get_cost_estimates(city)
        city_info = _get_city_info(city)  # may include transport/currency info
    elif is_transport_query:
        # For transport queries, fetch city_info (which includes transport)
        city_info = _get_city_info(city)
    elif is_food_query or is_historic_query:
        # For food/venue/historic queries, skip cost/currency/transport enrichments for speed
        pass
    else:
        # Default: fetch city_info for general queries
        city_info = _get_city_info(city)
    # Option to include web/Searx results (default: False)
    include_web = bool(payload.get("include_web", True))
    # Normalize query string for cuisine/food search
    q_norm = (q or "").strip().lower().replace("-", " ").replace("_", " ")
    # Determine whether to exclude obvious chains. If the client explicitly
    # sends local_only, honor it. Otherwise, treat "top/best/must" food queries
    # as a request for local gems.
    if "local_only" in payload:
        local_only = bool(payload.get("local_only"))
    else:
        local_only = any(
            kw in q_norm for kw in ["top", "best", "must", "hidden gem", "local gems"]
        )
    # Special handling for 'top food' queries: try to extract Wikivoyage highlights first
    # Broadened: treat any food-related query as a generic food search
    is_food_query = any(kw in (q or "") for kw in food_keywords)
    wikivoyage_results = []
    t1 = time.time()
    print(f"[TIMING] After Wikivoyage setup: {t1-t0:.2f}s")
    if city and (is_food_query or is_historic_query) and include_web:

        def fetch_wikivoyage_section(city_name, section_keywords, section_type):
            # Strip country part for Wikivoyage lookup
            city_base = city_name.split(',')[0].strip()
            url = "https://en.wikivoyage.org/w/api.php"
            params = {
                "action": "parse",
                "page": city_base,
                "prop": "sections",
                "format": "json",
                "redirects": 1,
            }
            items = []
            logging.debug(f"Trying Wikivoyage {section_type} highlights for city: '{city_name}'")
            try:
                resp = requests.get(
                    url,
                    params=params,
                    headers={"User-Agent": "TravelLand/1.0"},
                    timeout=8,
                )
                resp.raise_for_status()
                data = resp.json()
                secs = data.get("parse", {}).get("sections", [])
                target_section_idx = None
                for s in secs:
                    line = (s.get("line") or "").lower()
                    if any(kw in line for kw in section_keywords):
                        target_section_idx = s.get("index")
                        break
                if not target_section_idx:
                    return items
                params2 = {
                    "action": "parse",
                    "page": city_base,
                    "prop": "text",
                    "section": target_section_idx,
                    "format": "json",
                    "redirects": 1,
                }
                resp2 = requests.get(
                    url,
                    params=params2,
                    headers={"User-Agent": "TravelLand/1.0"},
                    timeout=8,
                )
                resp2.raise_for_status()
                html = resp2.json().get("parse", {}).get("text", {}).get("*", "")
                highlights = re.findall(r"<li>(.*?)</li>", html, re.DOTALL)
                if not highlights:
                    highlights = re.split(r"<br ?/?>|\n|</p>", html)

                def clean_html(raw):
                    return re.sub(r"<[^>]+>", "", raw).strip()

                highlights = [clean_html(h) for h in highlights if clean_html(h)]
                for idx, h in enumerate(highlights):
                    items.append(
                        {
                            "id": f"wikivoyage-{section_type}-{idx}",
                            "city": city_name,
                            "name": h.split(".")[0][:60] if "." in h else h[:60],
                            "description": h,
                            "provider": "wikivoyage",
                            "tags": f"wikivoyage,{section_type}",
                            "address": "",
                            "latitude": None,
                            "longitude": None,
                            "website": "",
                            "osm_url": "",
                            "amenity": section_type,
                            "budget": "",
                            "price_range": "",
                            "phone": "",
                            "rating": None,
                            "opening_hours": "",
                            "opening_hours_pretty": "",
                            "open_now": None,
                            "next_change": None,
                        }
                    )
            except Exception as e:
                logging.debug(f"Wikivoyage {section_type} highlights failed for {city_name}: {e}")
            return items

        if is_food_query:
            wikivoyage_results = fetch_wikivoyage_section(city, [
                "eat", "food", "cuisine", "dining", "restaurants", "must eat", "must-try"
            ], "food")
        elif is_historic_query:
            wikivoyage_results = fetch_wikivoyage_section(city, [
                "see", "sight", "sights", "attractions", "historic", "landmarks", "monuments"
            ], "historic")

    if is_food_query or is_historic_query:
        t_real_start = time.time()
        # Respect the client/UI timeout. Some cities are slow on Overpass (Rome ~11s, Paris ~12s).
        # Give providers almost all available time, minus 1-2s buffer for processing.
        provider_timeout = None
        try:
            timeout_val = payload.get("timeout")
            if timeout_val:
                provider_timeout = float(timeout_val)
        except (ValueError, TypeError):
            provider_timeout = None
        if provider_timeout:
            # Use most of available time; only 2s buffer for processing
            provider_timeout = max(3.0, provider_timeout - 2.0)
        else:
            provider_timeout = 23.0  # Default: 23s for providers
        try:
            # Determine POI type based on query
            poi_type = "restaurant" if is_food_query else ("historic" if is_historic_query else "restaurant")
            print(f"[DEBUG] Query: '{q}', is_food: {is_food_query}, is_historic: {is_historic_query}, poi_type: {poi_type}")
            pois = multi_provider.discover_pois(
                city,
                poi_type=poi_type,
                limit=20,
                local_only=local_only if poi_type == "restaurant" else False,
                timeout=provider_timeout,
            )
            partial = False
            print(
                f"[DEBUG] multi_provider returned {len(pois)} {poi_type} venues for city '{city}'"
            )
        except Exception as e:
            print(f"[ERROR] Failed to fetch real venues: {e}")
            pois = []
            partial = True

        for poi in (pois or [])[:20]:
            amenity = poi.get("amenity", "")

            v_budget = poi.get("budget")
            price_range = poi.get("price_range")
            if not v_budget:
                v_budget = "mid"
                price_range = "$$"
                tags_lower = poi.get("tags", "").lower()
                if (
                    amenity in ["fast_food", "cafe", "food_court"]
                    or "cuisine=fast_food" in tags_lower
                    or "cost=cheap" in tags_lower
                ):
                    v_budget = "cheap"
                    price_range = "$"
            if budget and budget != "any" and v_budget != budget:
                continue

            desc = poi.get("description")
            tags_str = poi.get("tags", "").lower()
            if not desc:
                tags_dict = dict(
                    tag.split("=", 1)
                    for tag in poi.get("tags", "").split(", ")
                    if "=" in tag
                )
                cuisine = tags_dict.get("cuisine", "").replace(";", ", ")
                brand = tags_dict.get("brand", "")
                features = []
                if "outdoor_seating=yes" in tags_str:
                    features.append("outdoor seating")
                if "wheelchair=yes" in tags_str:
                    features.append("accessible")
                if "takeaway=yes" in tags_str:
                    features.append("takeaway available")
                if "delivery=yes" in tags_str:
                    features.append("delivery")
                if "opening_hours" in tags_dict:
                    features.append("listed hours")
                feature_text = f" with {', '.join(features)}" if features else ""

                if cuisine:
                    desc = f"{cuisine.title()} restaurant{feature_text}"
                    if brand:
                        desc = f"{brand} - {desc}"
                else:
                    desc = (
                        f"Restaurant ({amenity}){feature_text}"
                        if amenity
                        else f"Local venue{feature_text}"
                    )
                    if brand:
                        desc = f"{brand} - {desc}"

                hours_val = tags_dict.get("opening_hours", "").strip()
                if hours_val:
                    pretty_hours = _humanize_opening_hours(hours_val) or hours_val
                    desc += f". Hours: {pretty_hours}"
                else:
                    logging.debug("No valid hours found. Skipping hours display.")

            address = (poi.get("address") or "").strip() or None
            tags_dict = dict(
                tag.split("=", 1)
                for tag in poi.get("tags", "").split(", ")
                if "=" in tag
            )
            phone = tags_dict.get("phone") or tags_dict.get("contact:phone")
            if phone:
                phone = f"tel:{phone}"

            rating = poi.get("rating")
            hours = tags_dict.get("opening_hours") or tags_dict.get("hours") or ""
            pretty_hours = _humanize_opening_hours(hours) if hours else None
            try:
                is_open, next_change = _compute_open_now(
                    poi.get("lat"), poi.get("lon"), hours
                )
            except Exception:
                is_open, next_change = (None, None)

            venue = {
                "id": poi.get("osm_id", poi.get("id", "")),
                "city": city,
                "name": poi.get("name", "Unknown"),
                "budget": v_budget,
                "price_range": price_range,
                "description": desc,
                "tags": poi.get("tags", ""),
                "address": address,
                "latitude": poi.get("lat", 0),
                "longitude": poi.get("lon", 0),
                "website": poi.get("website", ""),
                "osm_url": poi.get("osm_url", ""),
                "amenity": amenity,
                "provider": poi.get("provider", "osm"),
                "phone": phone,
                "rating": rating,
                "opening_hours": hours,
                "opening_hours_pretty": pretty_hours,
                "open_now": is_open,
                "next_change": next_change,
            }
            results.append(venue)

        t_real_end = time.time()
        print(f"[TIMING] Real venue search: {t_real_end-t_real_start:.2f}s")

    t4 = time.time()
    print(f"[TIMING] Total (post-setup): {t4-t0:.2f}s")

    # If Wikivoyage results exist, prepend them for food queries
    if wikivoyage_results:
        results = wikivoyage_results + results

    print(f"SEARCH RESULTS: found {len(results)} venues")
    try:
        if user_lat and user_lon and results:

            def haversine_km(lat1, lon1, lat2, lon2):
                from math import radians, sin, cos, asin, sqrt

                lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
                dlat = radians(lat2 - lat1)
                dlon = radians(lon2 - lon1)
                a = (
                    sin(dlat / 2) ** 2
                    + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
                )
                c = 2 * asin(sqrt(a))
                return 6371.0 * c

            for v in results:
                try:
                    v["distance_km"] = round(
                        haversine_km(
                            user_lat,
                            user_lon,
                            v.get("latitude", 0),
                            v.get("longitude", 0),
                        ),
                        2,
                    )
                except Exception:
                    v["distance_km"] = None
            results.sort(
                key=lambda x: (
                    x.get("distance_km") if x.get("distance_km") is not None else 1e9
                )
            )
    except Exception:
        pass

    # ensure partial is defined
    partial = locals().get("partial", False)

    # If the client requested web enrichment (include_web) try to populate images
    try:
        if include_web:
            # limit external fetches to avoid blocking too long
            max_fetch = 8
            fetched = 0
            for v in results:
                if fetched >= max_fetch:
                    break
                if v.get("image"):
                    continue
                # prefer website field
                website = v.get("website") or v.get("osm_url")
                if website:
                    img = _fetch_image_from_website(website)
                    if img:
                        v["image"] = img
                        fetched += 1
    except Exception:
        pass

    # Use a thread pool to fetch images for venues that have a website but no image
    # This is a good candidate for parallelization because it involves network I/O
    # and can be slow.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    venues_to_enrich = [v for v in results if v.get("website") and not v.get("image")]
    if venues_to_enrich:
        enriched_data = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_venue = {
                executor.submit(_fetch_image_from_website, v["website"]): v
                for v in venues_to_enrich
            }
            for future in as_completed(future_to_venue):
                venue = future_to_venue[future]
                try:
                    image_url = future.result()
                    if image_url:
                        enriched_data[venue["id"]] = {"image": image_url}
                except Exception as exc:
                    # Log errors but don't crash
                    logging.warning(
                        f"Image enrichment failed for {venue.get('website')}: {exc}"
                    )

        # Update venues with enriched data
        for venue in results:
            if venue["id"] in enriched_data:
                venue.update(enriched_data[venue["id"]])

    # Final response prep
    response_data = {
        "venues": results,
        "city_info": city_info,
        "partial": partial,
        "weather": weather_data,
        "transport": get_provider_links(city),
        "costs": cost_estimates,
    }
    return jsonify(response_data)


@app.route("/ingest", methods=["POST"])
def ingest():
    payload = request.json or {}
    urls = payload.get("urls") or []
    if isinstance(urls, str):
        urls = [urls]
    # basic validation: allow only http/https
    valid = []
    for u in urls:
        try:
            p = urlparse(u)
            if p.scheme in ("http", "https"):
                valid.append(u)
        except Exception:
            continue
    if not valid:
        return jsonify({"error": "no valid urls provided"}), 400
    n = semantic.ingest_urls(valid)
    return jsonify({"indexed_chunks": n, "urls": valid})


@app.route("/poi-discover", methods=["POST"])
def poi_discover():
    payload = request.json or {}
    city = payload.get("city") or payload.get("location") or ""
    if not city:
        return jsonify({"error": "city required"}), 400
    # discover via orchestrated providers (OSM + Places)
    try:
        candidates = multi_provider.discover_restaurants(
            city,
            limit=200,
            local_only=bool(payload.get("local_only", False)),
            timeout=(
                float(payload.get("timeout", 12.0)) if payload.get("timeout") else 12.0
            ),
        )
    except Exception as e:
        return jsonify({"error": "discover_failed", "details": str(e)}), 500
    return jsonify({"count": len(candidates), "candidates": candidates})


@app.route("/semantic-search", methods=["POST"])
def ai_reason():
    print("AI REASON ROUTE CALLED")
    payload = request.json or {}
    q = payload.get("q", "").strip()
    city = payload.get("city", "").strip()  # optional
    mode = payload.get("mode", "explorer")  # default to explorer
    venues = payload.get("venues", [])  # venues from UI context
    if not q:
        return jsonify({"error": "query required"}), 400
    weather = payload.get("weather")
    try:
        answer = semantic.search_and_reason(
            q, city if city else None, mode, context_venues=venues, weather=weather
        )
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/convert", methods=["POST"])
def convert_currency():
    payload = request.json or {}
    amount = float(payload.get("amount", 0))
    from_curr = payload.get("from", "USD")
    to_curr = payload.get("to", "EUR")
    try:
        result = semantic.convert_currency(amount, from_curr, to_curr)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/version", methods=["GET"])
def version():
    """Return deployed commit and presence of key environment variables for debugging."""
    import subprocess, os

    commit = None
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=os.path.dirname(__file__)
            )
            .decode()
            .strip()
        )
    except Exception:
        commit = os.getenv("GIT_COMMIT") or "unknown"

    env_flags = {
        "OPENTRIPMAP_KEY_set": bool(os.getenv("OPENTRIPMAP_KEY")),
        "GROQ_API_KEY_set": bool(os.getenv("GROQ_API_KEY")),
        "SEARX_INSTANCES_set": bool(os.getenv("SEARX_INSTANCES")),
    }
    return jsonify({"commit": commit, "env": env_flags})


@app.route("/tools/currency", methods=["GET"])
def tools_currency():
    # Optional city param to auto-detect local currency
    city = request.args.get("city")
    initial_currency = None
    initial_country = None
    if city:
        try:
            country = get_country_for_city(city)
            initial_country = country
            if country:
                cur = get_currency_for_country(country)
                initial_currency = cur
        except Exception:
            initial_currency = None
    initial_currency_name = None
    try:
        if initial_currency:
            initial_currency_name = get_currency_name(initial_currency)
    except Exception:
        initial_currency_name = None
    # Basic ATM tips (server-side) — short list
    atm_tips = [
        "Use bank-branded ATMs when possible — independent ATMs often charge higher fees.",
        "Check the fee and exchange rate shown on the ATM before accepting the transaction.",
        "Avoid ATMs in poorly lit or isolated areas, and prefer those inside banks or malls.",
        "For small purchases, consider using a card at shops to avoid ATM fees.",
    ]
    # Country-specific payment acceptance notes
    payment_notes_map = {
        "Cuba": [
            "Card acceptance in Cuba is limited; many places are cash-only.",
            "US bank cards and services like Zelle will not currently work — carry sufficient cash and local-denominated notes.",
            "Exchange currency at official casas de cambio or banks; avoid airport exchange desks with poor rates.",
        ],
        "Portugal": [
            "Some independent ATMs (Euronet) charge high fees and offer poor exchange rates.",
            "Prefer withdrawing from bank-branded ATMs to avoid dynamic fees.",
            "Check with your bank about international ATM fees and set a daily withdrawal limit accordingly.",
        ],
        "default": [
            "Check with your bank whether your card will work abroad and notify them before travel.",
            "Carry a small amount of local cash for markets/taxis where cards may not be accepted.",
            "Avoid dynamic currency conversion prompts on ATMs and receipts — choose local currency to get a fairer rate.",
        ],
    }
    # Expand with more country-specific notes
    payment_notes_map.update(
        {
            "Russia": [
                "Card networks and international payment services may be restricted; cash is often preferred.",
                "ATMs may charge higher fees; use bank-branded ATMs where possible.",
            ],
            "Venezuela": [
                "Severe cash and currency controls exist; exchange markets can be informal and risky.",
                "Use official exchange points where possible and avoid street exchangers.",
            ],
            "Myanmar": [
                "Card acceptance is limited outside major hotels; cash is necessary in many places.",
                "Carry small denominations and be aware of potential counterfeit notes.",
            ],
            "Nicaragua": [
                "US dollar cash is commonly accepted in tourist areas but local Córdoba is used widely; have both if possible.",
                "ATMs can be scarce outside cities.",
            ],
            "Kenya": [
                "Mobile money (M-Pesa) is widely used — many vendors accept it instead of cards.",
                "ATMs are available in cities; carry small cash in rural areas.",
            ],
            "Zimbabwe": [
                "Currency situation can be complex; cash and mobile payments may vary—check local guidance.",
                "Carry multiple payment methods if possible.",
            ],
            "Peru": [
                "Major cards are accepted in Lima and tourist areas; smaller towns may be cash-only.",
                "Avoid withdrawing large sums at once; prefer bank ATMs.",
            ],
        }
    )
    initial_payment_notes = None
    try:
        if initial_country:
            # prefer exact match, else default
            notes = (
                payment_notes_map.get(initial_country)
                or payment_notes_map.get(initial_country.split(",")[0])
                or payment_notes_map.get("default")
            )
        else:
            notes = payment_notes_map.get("default")
        initial_payment_notes = notes
    except Exception:
        initial_payment_notes = payment_notes_map.get("default")
    # Attempt to fetch average local prices (Teleport) for initial display
    try:
        initial_costs = get_cost_estimates(city) if city else []
    except Exception:
        initial_costs = []
    return render_template(
        "convert.html",
        initial_currency=initial_currency,
        initial_currency_name=initial_currency_name,
        initial_country=initial_country,
        initial_atm_tips=atm_tips,
        initial_payment_notes=initial_payment_notes,
        initial_costs=initial_costs,
    )


if __name__ == "__main__":
    # Prefer standard env vars used by many hosts (Render/Heroku/etc.), but
    # default to 5010 to match project docs and avoid UI/port mismatches.
    port = int(os.getenv("PORT") or os.getenv("FLASK_PORT") or 5010)
    app.run(host="0.0.0.0", port=port)
