import os
import aiohttp
from bs4 import BeautifulSoup
import math
import re
import logging
import hashlib
import json
import datetime
import threading
from pathlib import Path

import search_provider

# Import RAG recommender
try:
    from groq.traveland_rag import recommend_venues_rag, recommend_neighborhoods_rag
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logging.warning("RAG recommender not available, falling back to text-based recommendations")

# duckduckgo_provider removed

# Simple in-memory vector store + ingestion that prefers Groq.ai embeddings
GROQ_EMBEDDING_ENDPOINT = "https://api.groq.ai/v1/embeddings"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class InMemoryIndex:
    def __init__(self):
        self.items = []  # list of (embedding:list[float], meta:dict)

    def add(self, embedding, meta):
        self.items.append((embedding, meta))

    def search(self, query_emb, top_k=5):
        logging.debug(f"Performing search with top_k={top_k}")
        scores = []
        q_norm = math.sqrt(sum(x * x for x in query_emb))
        for emb, meta in self.items:
            # cosine similarity
            dot = sum(a * b for a, b in zip(query_emb, emb))
            e_norm = math.sqrt(sum(x * x for x in emb))
            score = dot / (q_norm * e_norm + 1e-12)
            scores.append((score, meta))
        scores.sort(key=lambda x: x[0], reverse=True)
        results = [{"score": float(s), "meta": m} for s, m in scores[:top_k]]
        logging.debug(f"Search results: {results}")
        return results


INDEX = InMemoryIndex()

# Simple file-based cache for Marco responses. Stored at data/marco_cache.json.
_CACHE_FILE = Path(__file__).resolve().parents[1] / "data" / "marco_cache.json"
_CACHE_LOCK = threading.Lock()


def _make_cache_key(query, city, mode):
    s = f"{(city or '').strip().lower()}|{mode}|{(query or '').strip().lower()}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_cache():
    try:
        if not _CACHE_FILE.exists():
            return {}
        with _CACHE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_cache(cache):
    try:
        tmp = _CACHE_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        tmp.replace(_CACHE_FILE)
    except Exception:
        pass


def _cache_get(key):
    ttl_days = int(os.getenv("MARCO_CACHE_TTL_DAYS", "7"))
    with _CACHE_LOCK:
        c = _load_cache()
        rec = c.get(key)
        if not rec:
            return None
        gen = rec.get("generated_at")
        if not gen:
            return rec.get("value")
        try:
            gen_dt = datetime.datetime.fromisoformat(gen)
            if (datetime.datetime.utcnow() - gen_dt).days >= ttl_days:
                # expired
                try:
                    del c[key]
                    _write_cache(c)
                except Exception:
                    pass
                return None
            return rec.get("value")
        except Exception:
            return rec.get("value")


def _cache_set(key, value, source="groq"):
    rec = {
        "value": value,
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "source": source,
    }
    with _CACHE_LOCK:
        c = _load_cache()
        c[key] = rec
        _write_cache(c)


async def convert_currency(amount, from_curr, to_curr, session: aiohttp.ClientSession = None):
    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True
    else:
        own_session = False
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{from_curr.upper()}"
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                if own_session:
                    await session.close()
                return f"Error: API request failed with status {resp.status}"
            data = await resp.json()
            rate = data["rates"].get(to_curr.upper())
            if rate:
                converted = amount * rate
                if own_session:
                    await session.close()
                return f"{amount} {from_curr.upper()} = {converted:.2f} {to_curr.upper()}"
            else:
                if own_session:
                    await session.close()
                return "Currency not supported."
    except Exception as e:
        if own_session:
            await session.close()
        return f"Error: {str(e)}"


async def _fetch_text(url, timeout=8, session: aiohttp.ClientSession = None):
    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True
    else:
        own_session = False
    try:
        headers = {"User-Agent": "CityGuidesBot/1.0 (+https://example.com)"}
        async with session.get(url, headers=headers, timeout=timeout) as r:
            if r.status != 200:
                if own_session:
                    await session.close()
                return ""
            text_content = await r.text()
            soup = BeautifulSoup(text_content, "html.parser")
            for s in soup(["script", "style", "noscript"]):
                s.decompose()
            text = " ".join(
                p.get_text(separator=" ", strip=True)
                for p in soup.find_all(["p", "h1", "h2", "h3", "li"])
            )
            if own_session:
                await session.close()
            return text
    except Exception:
        if own_session:
            await session.close()
        return ""


def _chunk_text(text, max_chars=1000):
    if not text:
        return []
    parts = []
    start = 0
    L = len(text)
    while start < L:
        end = min(L, start + max_chars)
        parts.append(text[start:end])
        start = end
    return parts


def _shorten(text, n=200):
    if not text:
        return ""
    s = " ".join(text.split())
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0] + "..."


def summarize_results(results, max_items=3):
    """Create a short, human-readable summary of search results to keep prompts small."""
    if not results:
        return ""
    items = []
    for r in results[:max_items]:
        title = r.get("title") or r.get("name") or ""
        snippet = r.get("snippet") or r.get("description") or ""
        url = r.get("url") or r.get("link") or ""
        brief = _shorten(snippet, 180)
        line = f"- {title}: {brief} {f'({url})' if url else ''}"
        items.append(line)
    return "\n".join(items)


def _get_api_key():
    return os.getenv("GROQ_API_KEY")


async def _embed_with_groq(text, session: aiohttp.ClientSession = None):
    # call Groq.ai embeddings endpoint (best-effort)
    key = _get_api_key()
    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True
    else:
        own_session = False
    try:
        if not key:
            raise RuntimeError("no groq key")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"model": "embed-english-v1", "input": text}
        async with session.post(GROQ_EMBEDDING_ENDPOINT, json=payload, headers=headers, timeout=20) as r:
            if r.status != 200:
                if own_session:
                    await session.close()
                return None
            j = await r.json()
            if (
                isinstance(j, dict)
                and "data" in j
                and len(j["data"]) > 0
                and "embedding" in j["data"][0]
            ):
                if own_session:
                    await session.close()
                return j["data"][0]["embedding"]
    except Exception:
        if own_session:
            await session.close()
        pass
    return None


def _fallback_embedding(text, dim=128):
    # deterministic, simple hash-based fallback embedding for demos
    vec = [0.0] * dim
    words = (text or "").split()
    for i, w in enumerate(words):
        h = 0
        for c in w:
            h = (h * 131 + ord(c)) & 0xFFFFFFFF
        idx = h % dim
        vec[idx] += 1.0
    # normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def embed_text(text, session: aiohttp.ClientSession = None):
    emb = await _embed_with_groq(text, session=session)
    if emb and isinstance(emb, list):
        return emb
    return _fallback_embedding(text)


async def ingest_urls(urls, session: aiohttp.ClientSession = None):
    count = 0
    for url in urls:
        txt = await _fetch_text(url, session=session)
        if not txt:
            continue
        chunks = _chunk_text(txt)
        for i, c in enumerate(chunks):
            emb = await embed_text(c, session=session)
            meta = {"source": url, "snippet": c[:500], "chunk_index": i}
            INDEX.add(emb, meta)
            count += 1
    return count


async def semantic_search(query, top_k=5, session: aiohttp.ClientSession = None):
    q_emb = await embed_text(query, session=session)
    return INDEX.search(q_emb, top_k=top_k)


async def recommend_neighborhoods(query, city, neighborhoods, mode="explorer", weather=None, session: aiohttp.ClientSession = None):
    """Use AI to recommend neighborhoods based on user preferences and available data."""

    # Build neighborhood context
    neighborhood_list = []
    for n in neighborhoods[:20]:  # Limit to avoid token limits
        name = n.get("name", "Unknown")
        center = n.get("center", {})
        lat, lon = center.get("lat", 0), center.get("lon", 0)
        neighborhood_list.append(f"- {name} (coordinates: {lat:.4f}, {lon:.4f})")

    neighborhood_context = "AVAILABLE NEIGHBORHOODS:\n" + "\n".join(neighborhood_list)

    weather_context = ""
    if weather:
        icons = {
            0: "Clear ☀️", 1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
            45: "Fog 🌫️", 48: "Depositing rime fog 🌫️", 51: "Light drizzle 🌦️",
            53: "Moderate drizzle 🌦️", 55: "Dense drizzle 🌦️", 56: "Light freezing drizzle 🌧️",
            57: "Dense freezing drizzle 🌧️", 61: "Slight rain 🌦️", 63: "Moderate rain 🌦️",
            65: "Heavy rain 🌧️", 66: "Light freezing rain 🌧️", 67: "Heavy freezing rain 🌧️",
            71: "Slight snow fall 🌨️", 73: "Moderate snow fall 🌨️", 75: "Heavy snow fall ❄️",
            77: "Snow grains ❄️", 80: "Slight rain showers 🌧️", 81: "Moderate rain showers 🌧️",
            82: "Violent rain showers 🌧️", 85: "Slight snow showers 🌨️", 86: "Heavy snow showers 🌨️",
            95: "Thunderstorm ⛈️", 96: "Thunderstorm with slight hail ⛈️", 99: "Thunderstorm with heavy hail ⛈️",
        }
        w_summary = icons.get(weather.get("weathercode"), "Unknown")
        weather_context = f"\nCURRENT WEATHER: {w_summary}, {weather.get('temperature_c')}°C."

    if mode == "explorer":
        prompt = f"""You are Marco, the legendary explorer! 🗺️

A traveler is asking about neighborhoods in {city or 'this city'}: "{query}"

{weather_context}

{neighborhood_context}

INSTRUCTIONS FOR MARCO:
1. Analyze the traveler's request and recommend 2-4 neighborhoods that best match their interests
2. For each recommendation, explain WHY it's a good choice based on the neighborhood name and general knowledge about {city or 'the city'}
3. Consider the weather if relevant (e.g., suggest indoor activities if raining)
4. Be enthusiastic and explorer-themed
5. End with an invitation to explore further
6. Sign off as Marco.🗺️🧭

Format your response as:
🏘️ **Neighborhood Name**: Brief description of why it's perfect for their interests.

[Repeat for 2-4 recommendations]

Ready to explore these areas? Click any neighborhood to focus your search there! - Marco 🗺️"""
    else:
        prompt = f"User query: {query}\n\nCity: {city}\n\n{neighborhood_context}\n\n{weather_context}\n\nProvide factual neighborhood recommendations based on the available data."

    # Cache lookup
    try:
        cache_key = _make_cache_key(f"neighborhoods_{query}", city, mode)
        cached = _cache_get(cache_key)
        if cached:
            logging.debug(f"Marco neighborhood cache hit for key={cache_key}")
            return cached

        key = _get_api_key()
        print(f"DEBUG: Calling Groq for neighborhood recommendation: {query}")
        print(f"DEBUG: Neighborhoods count: {len(neighborhoods)}")

        if not key:
            print("DEBUG: No GROQ_API_KEY found")
            # Fallback: return simple list
            names = [n.get("name") for n in neighborhoods[:6] if n.get("name")]
            return f"Based on your interests, here are some neighborhoods in {city or 'this city'} you might like: {', '.join(names)}. Try clicking on one to explore venues there!"

        # Truncate if too long
        MAX_PROMPT_CHARS = 1500
        if len(prompt) > MAX_PROMPT_CHARS:
            print(f"DEBUG: Prompt too long ({len(prompt)} chars), truncating")
            prompt = prompt[:MAX_PROMPT_CHARS] + "\n\n[TRUNCATED]"

        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.8,
            },
            timeout=30,
        ) as response:
            if response.status != 200:
                print(f"DEBUG: Groq API Error {response.status}: {await response.text()}")
            if response.status == 200:
                res_data = await response.json()
                answer = res_data["choices"][0]["message"]["content"]
                if answer and answer.strip():
                    ans = answer.strip()
                    try:
                        _cache_set(cache_key, ans, source="groq")
                    except Exception:
                        pass
                    return ans

        # Fallback
        names = [n.get("name") for n in neighborhoods[:4] if n.get("name")]
        if mode == "explorer":
            fallback = f"Ahoy! 🧭 Based on your interests in '{query}', I'd recommend exploring these Lisbon neighborhoods:\n\n🏘️ **Alfama**: Historic heart of the city with stunning views and traditional Portuguese culture\n🏘️ **Belém**: Famous for the Jerónimos Monastery and pastéis de nata\n🏘️ **Chiado**: Trendy area with shops, theaters, and great food scene\n🏘️ **Alvalade**: Modern residential area with good transport links\n\nClick any neighborhood to focus your search there! - Marco 🗺️"
        else:
            fallback = f"Recommended neighborhoods for '{query}': {', '.join(names)}. Try selecting one to explore venues there."
        try:
            _cache_set(cache_key, fallback, source="fallback")
        except Exception:
            pass
        return fallback
    except Exception as e:
        print(f"DEBUG: Groq neighborhood exception: {e}")
        names = [n.get("name") for n in neighborhoods[:3] if n.get("name")]
        return f"Here are some neighborhoods you might enjoy: {', '.join(names)}. Try selecting one to explore!"


async def search_and_reason(
    query, city=None, mode="explorer", context_venues=None, weather=None, neighborhoods=None, session: aiohttp.ClientSession = None
):
    """Search the web and use Groq to reason about the query.

    mode: 'explorer' for themed responses, 'rational' for straightforward responses
    context_venues: optional list of venues already showing in the UI
    neighborhoods: optional list of neighborhoods for recommendation
    """

    # Check for currency conversion
    if "convert" in query.lower() or "currency" in query.lower():
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*([A-Z]{3})\s*to\s*([A-Z]{3})", query, re.IGNORECASE
        )
        if match:
            amount = float(match.group(1))
            from_curr = match.group(2)
            to_curr = match.group(3)
            result = await convert_currency(amount, from_curr, to_curr, session=session)
            if mode == "explorer":
                return f"Ahoy! 🪙 As your trusty currency converter, here's the exchange: {result}. Safe travels with your coins!"
            else:
                return f"Currency conversion: {result}"
        else:
            if mode == "explorer":
                return "Arrr, I couldn't parse that currency request. Try 'convert 100 USD to EUR'!"
            else:
                return "Unable to parse currency conversion request. Please use format like 'convert 100 USD to EUR'."

    # Check for weather questions
    weather_keywords = [
        "weather",
        "temperature",
        "forecast",
        "wind",
        "rain",
        "sunny",
        "cloudy",
        "humidity",
        "umbrella",
        "jacket",
        "coat",
        "wear",
        "outdoor",
    ]
    if any(w in query.lower() for w in weather_keywords):
        # Use provided weather data if available
        if weather:
            icons = {
                0: "Clear ☀️",
                1: "Mainly clear 🌤️",
                2: "Partly cloudy ⛅",
                3: "Overcast ☁️",
                45: "Fog 🌫️",
                48: "Depositing rime fog 🌫️",
                51: "Light drizzle 🌦️",
                53: "Moderate drizzle 🌦️",
                55: "Dense drizzle 🌦️",
                56: "Light freezing drizzle 🌧️",
                57: "Dense freezing drizzle 🌧️",
                61: "Slight rain 🌦️",
                63: "Moderate rain 🌦️",
                65: "Heavy rain 🌧️",
                66: "Light freezing rain 🌧️",
                67: "Heavy freezing rain 🌧️",
                71: "Slight snow fall 🌨️",
                73: "Moderate snow fall 🌨️",
                75: "Heavy snow fall ❄️",
                77: "Snow grains ❄️",
                80: "Slight rain showers 🌧️",
                81: "Moderate rain showers 🌧️",
                82: "Violent rain showers 🌧️",
                85: "Slight snow showers 🌨️",
                86: "Heavy snow showers 🌨️",
                95: "Thunderstorm ⛈️",
                96: "Thunderstorm with slight hail ⛈️",
                99: "Thunderstorm with heavy hail ⛈️",
            }
            summary = icons.get(weather.get("weathercode"), "Unknown")
            details = f"{weather.get('temperature_c')}°C / {weather.get('temperature_f')}°F, Wind {weather.get('wind_kmh')} km/h / {weather.get('wind_mph')} mph"

            # If it's a simple weather check, return immediately.
            # If it's more complex (like "should I bring an umbrella?"), we'll let it fall through to the AI.
            simple_weather_check = (
                any(
                    w in query.lower()
                    for w in ["weather", "temperature", "forecast", "forecasts"]
                )
                and len(query.split()) < 5
            )
            if simple_weather_check:
                if mode == "explorer":
                    return f"Ahoy! 🧭 The current weather in {city or 'this city'} is: {summary}. {details}. Safe travels! - Marco"
                else:
                    return f"Current weather in {city or 'this city'}: {summary}. {details}."

    # Handle neighborhood recommendations
    neighborhood_keywords = ["neighborhood", "area", "district", "quarter", "where", "recommend", "best", "good", "nice"]
    is_neighborhood_query = any(k in query.lower() for k in neighborhood_keywords) and neighborhoods
    print(f"DEBUG: Query: '{query}', is_neighborhood_query: {is_neighborhood_query}, neighborhoods count: {len(neighborhoods) if neighborhoods else 0}")

    if is_neighborhood_query and neighborhoods:
        return await recommend_neighborhoods(query, city, neighborhoods, mode, weather, session)

    # Determine if this is a query about the visible results
    screen_keywords = ["these", "visible", "listed", "on screen", "above", "results"]
    is_screen_query = any(k in query.lower() for k in screen_keywords)

    # We always try to get some web context unless it's strictly a screen query
    results = []
    if not is_screen_query or not context_venues:
        # Searx search removed
        # All web search enrichment removed; nothing to try here
        pass

    # Build a concise summary of web results to keep the LLM prompt small
    context = summarize_results(results)

    ui_context = ""
    if context_venues:
        ui_lines = [
            f"- {v.get('name')} | {v.get('address')} | {v.get('description')}"
            for v in context_venues
        ]
        ui_context = "VENUES ON SCREEN:\n" + "\n".join(ui_lines)

    weather_context = ""
    if weather:
        icons = {
            0: "Clear ☀️",
            1: "Mainly clear 🌤️",
            2: "Partly cloudy ⛅",
            3: "Overcast ☁️",
            45: "Fog 🌫️",
            48: "Depositing rime fog 🌫️",
            51: "Light drizzle 🌦️",
            53: "Moderate drizzle 🌦️",
            55: "Dense drizzle 🌦️",
            56: "Light freezing drizzle 🌧️",
            57: "Dense freezing drizzle 🌧️",
            61: "Slight rain 🌦️",
            63: "Moderate rain 🌦️",
            65: "Heavy rain 🌧️",
            66: "Light freezing rain 🌧️",
            67: "Heavy freezing rain 🌧️",
            71: "Slight snow fall 🌨️",
            73: "Moderate snow fall 🌨️",
            75: "Heavy snow fall ❄️",
            77: "Snow grains ❄️",
            80: "Slight rain showers 🌧️",
            81: "Moderate rain showers 🌧️",
            82: "Violent rain showers 🌧️",
            85: "Slight snow showers 🌨️",
            86: "Heavy snow showers 🌨️",
            95: "Thunderstorm ⛈️",
            96: "Thunderstorm with slight hail ⛈️",
            99: "Thunderstorm with heavy hail ⛈️",
        }
        w_summary = icons.get(weather.get("weathercode"), "Unknown")
        weather_context = f"\nCURRENT WEATHER IN {city or 'the city'}:\n{w_summary}, {weather.get('temperature_c')}°C / {weather.get('temperature_f')}°F, Wind {weather.get('wind_kmh')} km/h.\n"

    if mode == "explorer":
        prompt = f"""You are Marco, the legendary explorer! 🗺️

Traveler is asking: {query}

{weather_context}

{ui_context if ui_context else 'No venues on screen yet.'}

WEB SEARCH DATA:
{context if context else 'No web results.'}

INSTRUCTIONS FOR MARCO:
1. If the traveler is asking about what's on their screen, use the VENUES ON SCREEN list first.
2. If there is weather data provided, use it to suggest appropriate activities (e.g., indoor vs outdoor).
3. For every recommendation, you MUST provide a specific reason WHY from the data (e.g., "mentions outdoor seating", "noted as a quick cafe", "listed as accessible"). 
4. Don't just say it's "a great spot" - explain the treasure you found in the description or data provided.
5. If multiple spots match, mention 2 options.
6. Be enthusiastic and explorer-themed. Sign off as Marco.🗺️🧭"""
    else:
        prompt = f"User query: {query}\n\n{ui_context}\n\nWeb Data:\n{context}\n\nProvide a factual response."

    # Cache lookup: avoid calling Groq repeatedly for identical queries
    try:
        cache_key = _make_cache_key(query, city, mode)
        cached = _cache_get(cache_key)
        if cached:
            logging.debug(f"Marco cache hit for key={cache_key}")
            return cached

        key = _get_api_key()
        print(f"DEBUG: Calling Groq for query: {query}")
        print(
            f"DEBUG: Context Venues Count: {len(context_venues) if context_venues else 0}"
        )

        if not key:
            print("DEBUG: No GROQ_API_KEY found in environment")
            raise Exception("No API Key")

        # Respect service limits: truncate overly large prompts to avoid 413 errors
        MAX_PROMPT_CHARS = 1200
        if len(prompt) > MAX_PROMPT_CHARS:
            print(
                f"DEBUG: Prompt too long ({len(prompt)} chars), truncating to {MAX_PROMPT_CHARS}"
            )
            prompt = prompt[:MAX_PROMPT_CHARS] + "\n\n[TRUNCATED]"

        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 256,
                "temperature": 0.7,
            },
            timeout=30,
        ) as response:
            if response.status != 200:
                print(f"DEBUG: Groq API Error {response.status}: {await response.text()}")
            if response.status == 200:
                res_data = await response.json()
                answer = res_data["choices"][0]["message"]["content"]
                if answer and answer.strip():
                    ans = answer.strip()
                    try:
                        _cache_set(cache_key, ans, source="groq")
                    except Exception:
                        pass
                    return ans

        # Smarter fallback if AI fails
        if context_venues:
            # Pick a random one for variety if we're hitting fallbacks
            import random

            pool = context_venues[:5] if len(context_venues) >= 5 else context_venues
            v = random.choice(pool)
            name = v.get("name", "this spot")
            fallback = f"Ahoy! 🧭 My compass is spinning, but looking at our map, **{name}** stands out! Based on my logs, it should be a fine spot for your quest. Safe travels! - Marco"
            try:
                _cache_set(cache_key, fallback, source="fallback")
            except Exception:
                pass
            return fallback

        fallback2 = "Ahoy! 🪙 My explorer's eyes are tired. Try searching for a specific place above first! - Marco"
        try:
            _cache_set(cache_key, fallback2, source="fallback")
        except Exception:
            pass
        return fallback2
    except Exception as e:
        print(f"DEBUG: Groq Exception: {e}")
        if context_venues:
            fallback = f"Ahoy! 🧭 My compass is spinning, but **{context_venues[0].get('name')}** on your screen looks like a treasure! - Marco"
            try:
                _cache_set(cache_key, fallback, source="fallback")
            except Exception:
                pass
            return fallback
        fallback3 = "Ahoy! 🪙 My explorer's eyes are tired. - Marco"
        try:
            _cache_set(cache_key, fallback3, source="fallback")
        except Exception:
            pass
        return fallback3
