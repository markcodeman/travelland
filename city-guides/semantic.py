import os
import requests
from bs4 import BeautifulSoup
import math
import re
import logging

import search_provider
import duckduckgo_provider

# Simple in-memory vector store + ingestion that prefers Groq.ai embeddings
GROQ_EMBEDDING_ENDPOINT = 'https://api.groq.ai/v1/embeddings'

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


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
        results = [{'score': float(s), 'meta': m} for s, m in scores[:top_k]]
        logging.debug(f"Search results: {results}")
        return results


INDEX = InMemoryIndex()


def convert_currency(amount, from_curr, to_curr):
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{from_curr.upper()}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rate = data['rates'].get(to_curr.upper())
        if rate:
            converted = amount * rate
            return f"{amount} {from_curr.upper()} = {converted:.2f} {to_curr.upper()}"
        else:
            return "Currency not supported."
    except Exception as e:
        return f"Error: {str(e)}"


def _fetch_text(url, timeout=8):
    try:
        headers = {'User-Agent': 'CityGuidesBot/1.0 (+https://example.com)'}
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        # remove scripts/styles
        for s in soup(['script', 'style', 'noscript']):
            s.decompose()
        text = ' '.join(p.get_text(separator=' ', strip=True) for p in soup.find_all(['p', 'h1','h2','h3','li']))
        return text
    except Exception:
        return ''


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
        return ''
    s = ' '.join(text.split())
    if len(s) <= n:
        return s
    return s[:n].rsplit(' ', 1)[0] + '...'


def summarize_results(results, max_items=3):
    """Create a short, human-readable summary of search results to keep prompts small."""
    if not results:
        return ''
    items = []
    for r in results[:max_items]:
        title = r.get('title') or r.get('name') or ''
        snippet = r.get('snippet') or r.get('description') or ''
        url = r.get('url') or r.get('link') or ''
        brief = _shorten(snippet, 180)
        line = f"- {title}: {brief} {f'({url})' if url else ''}"
        items.append(line)
    return '\n'.join(items)


def _get_api_key():
    return os.getenv('GROQ_API_KEY')

def _embed_with_groq(text):
    # call Groq.ai embeddings endpoint (best-effort)
    key = _get_api_key()
    try:
        if not key:
            raise RuntimeError('no groq key')
        headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        payload = {'model': 'embed-english-v1', 'input': text}
        r = requests.post(GROQ_EMBEDDING_ENDPOINT, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        j = r.json()
        # expected: {'data':[{'embedding': [...]}, ...]}
        if isinstance(j, dict) and 'data' in j and len(j['data']) > 0 and 'embedding' in j['data'][0]:
            return j['data'][0]['embedding']
    except Exception:
        pass
    return None


def _fallback_embedding(text, dim=128):
    # deterministic, simple hash-based fallback embedding for demos
    vec = [0.0] * dim
    words = (text or '').split()
    for i, w in enumerate(words):
        h = 0
        for c in w:
            h = (h * 131 + ord(c)) & 0xFFFFFFFF
        idx = h % dim
        vec[idx] += 1.0
    # normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def embed_text(text):
    emb = _embed_with_groq(text)
    if emb and isinstance(emb, list):
        return emb
    return _fallback_embedding(text)


def ingest_urls(urls):
    """Fetch pages, chunk and index them in-memory. Returns number indexed."""
    count = 0
    for url in urls:
        txt = _fetch_text(url)
        if not txt:
            continue
        chunks = _chunk_text(txt)
        for i, c in enumerate(chunks):
            emb = embed_text(c)
            meta = {'source': url, 'snippet': c[:500], 'chunk_index': i}
            INDEX.add(emb, meta)
            count += 1
    return count


def semantic_search(query, top_k=5):
    q_emb = embed_text(query)
    return INDEX.search(q_emb, top_k=top_k)


def search_and_reason(query, city=None, mode='explorer', context_venues=None, weather=None):
    """Search the web and use Groq to reason about the query.
    
    mode: 'explorer' for themed responses, 'rational' for straightforward responses
    context_venues: optional list of venues already showing in the UI
    """

    # Check for currency conversion
    if 'convert' in query.lower() or 'currency' in query.lower():
        match = re.search(r'(\d+(?:\.\d+)?)\s*([A-Z]{3})\s*to\s*([A-Z]{3})', query, re.IGNORECASE)
        if match:
            amount = float(match.group(1))
            from_curr = match.group(2)
            to_curr = match.group(3)
            result = convert_currency(amount, from_curr, to_curr)
            if mode == 'explorer':
                return f"Ahoy! 🪙 As your trusty currency converter, here's the exchange: {result}. Safe travels with your coins!"
            else:
                return f"Currency conversion: {result}"
        else:
            if mode == 'explorer':
                return "Arrr, I couldn't parse that currency request. Try 'convert 100 USD to EUR'!"
            else:
                return "Unable to parse currency conversion request. Please use format like 'convert 100 USD to EUR'."

    # Check for weather questions
    weather_keywords = ['weather', 'temperature', 'forecast', 'wind', 'rain', 'sunny', 'cloudy', 'humidity', 'umbrella', 'jacket', 'coat', 'wear', 'outdoor']
    if any(w in query.lower() for w in weather_keywords):
        # Use provided weather data if available
        if weather:
            icons = {
                0: 'Clear ☀️', 1: 'Mainly clear 🌤️', 2: 'Partly cloudy ⛅', 3: 'Overcast ☁️', 45: 'Fog 🌫️', 48: 'Depositing rime fog 🌫️',
                51: 'Light drizzle 🌦️', 53: 'Moderate drizzle 🌦️', 55: 'Dense drizzle 🌦️', 56: 'Light freezing drizzle 🌧️', 57: 'Dense freezing drizzle 🌧️',
                61: 'Slight rain 🌦️', 63: 'Moderate rain 🌦️', 65: 'Heavy rain 🌧️', 66: 'Light freezing rain 🌧️', 67: 'Heavy freezing rain 🌧️',
                71: 'Slight snow fall 🌨️', 73: 'Moderate snow fall 🌨️', 75: 'Heavy snow fall ❄️', 77: 'Snow grains ❄️', 80: 'Slight rain showers 🌧️', 81: 'Moderate rain showers 🌧️', 82: 'Violent rain showers 🌧️',
                85: 'Slight snow showers 🌨️', 86: 'Heavy snow showers 🌨️', 95: 'Thunderstorm ⛈️', 96: 'Thunderstorm with slight hail ⛈️', 99: 'Thunderstorm with heavy hail ⛈️'
            }
            summary = icons.get(weather.get('weathercode'), 'Unknown')
            details = f"{weather.get('temperature_c')}°C / {weather.get('temperature_f')}°F, Wind {weather.get('wind_kmh')} km/h / {weather.get('wind_mph')} mph"
            
            # If it's a simple weather check, return immediately. 
            # If it's more complex (like "should I bring an umbrella?"), we'll let it fall through to the AI.
            simple_weather_check = any(w in query.lower() for w in ['weather', 'temperature', 'forecast', 'forecasts']) and len(query.split()) < 5
            if simple_weather_check:
                if mode == 'explorer':
                    return f"Ahoy! 🧭 The current weather in {city or 'this city'} is: {summary}. {details}. Safe travels! - Marco"
                else:
                    return f"Current weather in {city or 'this city'}: {summary}. {details}."
    
    # Determine if this is a query about the visible results
    screen_keywords = ['these', 'visible', 'listed', 'on screen', 'above', 'results']
    is_screen_query = any(k in query.lower() for k in screen_keywords)
    
    # We always try to get some web context unless it's strictly a screen query
    results = []
    if not is_screen_query or not context_venues:
        results = search_provider.searx_search(query, max_results=5, city=city)
        if not results:
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    ddg_results = ddgs.text(f"{query} {city or ''}", max_results=3)
                    results = [{'title': r['title'], 'url': r['href'], 'snippet': r['body']} for r in ddg_results]
            except Exception: pass

    # Build a concise summary of web results to keep the LLM prompt small
    context = summarize_results(results)

    ui_context = ''
    if context_venues:
        ui_lines = [f"- {v.get('name')} | {v.get('address')} | {v.get('description')}" for v in context_venues]
        ui_context = "VENUES ON SCREEN:\n" + "\n".join(ui_lines)

    weather_context = ""
    if weather:
        icons = {
            0: 'Clear ☀️', 1: 'Mainly clear 🌤️', 2: 'Partly cloudy ⛅', 3: 'Overcast ☁️', 45: 'Fog 🌫️', 48: 'Depositing rime fog 🌫️',
            51: 'Light drizzle 🌦️', 53: 'Moderate drizzle 🌦️', 55: 'Dense drizzle 🌦️', 56: 'Light freezing drizzle 🌧️', 57: 'Dense freezing drizzle 🌧️',
            61: 'Slight rain 🌦️', 63: 'Moderate rain 🌦️', 65: 'Heavy rain 🌧️', 66: 'Light freezing rain 🌧️', 67: 'Heavy freezing rain 🌧️',
            71: 'Slight snow fall 🌨️', 73: 'Moderate snow fall 🌨️', 75: 'Heavy snow fall ❄️', 77: 'Snow grains ❄️', 80: 'Slight rain showers 🌧️', 81: 'Moderate rain showers 🌧️', 82: 'Violent rain showers 🌧️',
            85: 'Slight snow showers 🌨️', 86: 'Heavy snow showers 🌨️', 95: 'Thunderstorm ⛈️', 96: 'Thunderstorm with slight hail ⛈️', 99: 'Thunderstorm with heavy hail ⛈️'
        }
        w_summary = icons.get(weather.get('weathercode'), 'Unknown')
        weather_context = f"\nCURRENT WEATHER IN {city or 'the city'}:\n{w_summary}, {weather.get('temperature_c')}°C / {weather.get('temperature_f')}°F, Wind {weather.get('wind_kmh')} km/h.\n"

    if mode == 'explorer':
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
    
    try:
        key = _get_api_key()
        print(f"DEBUG: Calling Groq for query: {query}")
        print(f"DEBUG: Context Venues Count: {len(context_venues) if context_venues else 0}")
        
        if not key:
            print("DEBUG: No GROQ_API_KEY found in environment")
            raise Exception("No API Key")

        # Respect service limits: truncate overly large prompts to avoid 413 errors
        MAX_PROMPT_CHARS = 1200
        if len(prompt) > MAX_PROMPT_CHARS:
            print(f"DEBUG: Prompt too long ({len(prompt)} chars), truncating to {MAX_PROMPT_CHARS}")
            prompt = prompt[:MAX_PROMPT_CHARS] + "\n\n[TRUNCATED]"

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant", 
                "messages": [{"role": "user", "content": prompt}], 
                "max_tokens": 256,
                "temperature": 0.7
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"DEBUG: Groq API Error {response.status_code}: {response.text}")
        
        if response.status_code == 200:
            res_data = response.json()
            answer = res_data["choices"][0]["message"]["content"]
            if answer.strip(): 
                return answer.strip()
            
        # Smarter fallback if AI fails
        if context_venues:
            # Pick a random one for variety if we're hitting fallbacks
            import random
            # Filter out generic ones or use a wider pool
            pool = context_venues[:5] if len(context_venues) >= 5 else context_venues
            v = random.choice(pool) 
            name = v.get('name', 'this spot')
            return f"Ahoy! 🧭 My compass is spinning, but looking at our map, **{name}** stands out! Based on my logs, it should be a fine spot for your quest. Safe travels! - Marco"
        
        return "Ahoy! 🪙 My explorer's eyes are tired. Try searching for a specific place above first! - Marco"
    except Exception as e:
        print(f"DEBUG: Groq Exception: {e}")
        if context_venues:
            return f"Ahoy! 🧭 My compass is spinning, but **{context_venues[0].get('name')}** on your screen looks like a treasure! - Marco"
        return "Ahoy! 🪙 My explorer's eyes are tired. - Marco"

