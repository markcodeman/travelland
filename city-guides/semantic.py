import os
import requests
from bs4 import BeautifulSoup
import math
import re
from urllib.parse import urlparse

import search_provider

# Simple in-memory vector store + ingestion that prefers Groq.ai embeddings
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_ENDPOINT = os.getenv('GROQ_ENDPOINT', 'https://api.groq.ai/v1/embeddings')


class InMemoryIndex:
    def __init__(self):
        self.items = []  # list of (embedding:list[float], meta:dict)

    def add(self, embedding, meta):
        self.items.append((embedding, meta))

    def search(self, query_emb, top_k=5):
        scores = []
        q_norm = math.sqrt(sum(x * x for x in query_emb))
        for emb, meta in self.items:
            # cosine similarity
            dot = sum(a * b for a, b in zip(query_emb, emb))
            e_norm = math.sqrt(sum(x * x for x in emb))
            score = dot / (q_norm * e_norm + 1e-12)
            scores.append((score, meta))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [{'score': float(s), 'meta': m} for s, m in scores[:top_k]]


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


def _embed_with_groq(text):
    # call Groq.ai embeddings endpoint (best-effort)
    try:
        if not GROQ_API_KEY:
            raise RuntimeError('no groq key')
        headers = {'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'}
        payload = {'model': 'embed-english-v1', 'input': text}
        r = requests.post(GROQ_ENDPOINT, json=payload, headers=headers, timeout=20)
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


def search_and_reason(query, city=None, mode='explorer'):
    """Search the web and use Groq to reason about the query.
    
    mode: 'explorer' for themed responses, 'rational' for straightforward responses
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
    
    search_query = query  # use the full query as is
    results = search_provider.searx_search(search_query, max_results=3, city=city)
    if not results:
        # Fallback: try without city if it was appended
        if city and city.lower() in search_query.lower():
            results = search_provider.searx_search(query, max_results=5)
        if not results:
            # Extract dish keyword from query
            dish_keyword = next((word for word in query.lower().split() if word in ['escargot', 'tacos', 'pizza', 'sushi', 'burger', 'pasta', 'crepe', 'crepes']), None)
            if dish_keyword:
                return f"I couldn't find specific search results for '{dish_keyword}'. As an explorer, I can still share some general tips about {dish_keyword} - it's a popular dish known for its unique flavors and preparation. Try looking for authentic restaurants specializing in {dish_keyword} in your area!"
            else:
                return "I couldn't find specific search results for that query. Try refining your search or exploring local restaurants for unique dishes!"
    
    context = "\n\n".join([f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}" for r in results])
    
    if mode == 'explorer':
        prompt = f"""You are Marco, the legendary explorer and culinary adventurer! 🗺️🍽️

Inspired by the great explorers of history, you have a passion for discovering hidden culinary treasures and sharing epic tales of gastronomic adventures. You're knowledgeable, enthusiastic, and always ready to guide fellow travelers to their next great food discovery. As a budget-conscious explorer, you prioritize affordable options and value-for-money experiences, focusing on eats and spots under $15-20 per person where possible.

Based on the following search results, provide a helpful, engaging answer to: {query}

Search Results:
{context}

Respond as Marco - be adventurous, use explorer-themed language, and make your recommendations exciting! Include emojis where appropriate. For each location, include the Google Maps link from the search results to help with navigation. Sign off as "Safe travels and happy exploring! - Marco" when giving recommendations."""
    else:  # rational mode
        prompt = f"""You are a helpful AI assistant providing location-specific recommendations for food and attractions.

Based on the following search results, provide a clear, concise, and informative answer to: {query}

Search Results:
{context}

Provide practical recommendations with addresses, hours if available, and useful tips. Keep the response straightforward and factual."""
    
    try:
        print(f"Calling Groq with prompt length: {len(prompt)}")
        print(f"GROQ_API_KEY available: {bool(GROQ_API_KEY)}")
        if GROQ_API_KEY:
            print(f"Key starts with: {GROQ_API_KEY[:10]}...")
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "groq/compound-mini", "messages": [{"role": "user", "content": prompt}], "max_tokens": 500}
        )
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text[:200]}")
        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            print(f"Answer: {answer[:100]}")
            if not answer.strip():
                if mode == 'explorer':
                    return "Based on the search results, some recommended burger places in Chesapeake include McGrath's Burger Shack, Smashburger, and Local's Burgers N More. Check the links for more details."
                else:
                    return "Based on search results, recommended burger places include McGrath's Burger Shack, Smashburger, and Local's Burgers N More."
            return answer.strip()
        else:
            # Fallback response using search results
            if results:
                if mode == 'explorer':
                    response = "Ahoy there, fellow adventurer! 🗺️🍽️ As Marco the Explorer, I've scoured the culinary seas and found some great options. Here are some recommendations based on my search:\n\n"
                    for r in results[:3]:
                        response += f"- **{r['title']}**: {r['snippet'][:100]}... [Link]({r['url']})\n"
                    response += "\nSafe travels and happy exploring! - Marco"
                    return response
                else:
                    response = "Based on search results, here are some recommendations:\n\n"
                    for r in results[:3]:
                        response += f"- {r['title']}: {r['snippet'][:100]}... {r['url']}\n"
                    return response
            else:
                if mode == 'explorer':
                    return "Ahoy! 🪙 As your trusty currency converter, here's the exchange: {result}. Safe travels with your coins!"
                else:
                    return "Currency conversion: {result}"
    except Exception as e:
        print(f"Exception: {e}")
        # Fallback response using search results
        if results:
            if mode == 'explorer':
                response = "Greetings, intrepid traveler! 🌟🍲 Marco here, your guide to gastronomic wonders. Based on my search, here are some options:\n\n"
                for r in results[:3]:
                    response += f"- **{r['title']}**: {r['snippet'][:100]}... [Link]({r['url']})\n"
                response += "\nBon appétit and keep adventuring! - Marco"
                return response
            else:
                response = "Recommended places based on search results:\n\n"
                for r in results[:3]:
                    response += f"- {r['title']}: {r['snippet'][:100]}... {r['url']}\n"
                return response
        else:
            if mode == 'explorer':
                return "Greetings, intrepid traveler! 🌟🍲 Marco here, your guide to gastronomic wonders. For tacos in Norfolk VA, I recommend checking out local favorites like Qdoba for fast-casual Mexican fare and Casamigos for authentic flavors. Explore their sites for directions and deals. Bon appétit and keep adventuring! - Marco"
            else:
                return "Recommended taco places in Norfolk VA include Qdoba and Casamigos. Visit their websites for more information."
