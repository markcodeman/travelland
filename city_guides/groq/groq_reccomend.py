"""
Groq-based recommender: RAG pattern using pre-retrieved candidate venues.
This is a minimal example. Adapt embedding/retrieval to your vector DB and project conventions.
"""

import os
import json
import requests
from typing import List, Dict

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"  # per repo testing notes
GROQ_MODEL = "llama-3.1-8b-instant"  # choose appropriate model

def build_system_prompt():
    return (
        "You are a guest-experience assistant for a travel app. "
        "Given a short list of candidate venues with metadata, produce a JSON array of up to 6 recommendations ranked by relevance. "
        "Return JSON only (no explanatory text). Use only the candidate venues provided (do not invent new ones). "
        "Each item must reference the venue 'id' exactly as provided, include a numeric 'score' 0..1, a one-line 'reason', "
        "an array of 'tags', and a 'confidence' field (low/medium/high)."
    )

def build_user_prompt(user_context: Dict, candidates: List[Dict]) -> str:
    # Keep each candidate short to reduce tokens
    cand_lines = []
    for v in candidates:
        cand_lines.append(json.dumps({
            "id": v.get("id"),
            "name": v.get("name"),
            "lat": v.get("lat"),
            "lon": v.get("lon"),
            "tags": (v.get("tags") or [])[:5],
            "desc": (v.get("description") or "")[:280],  # limit length
            "source": v.get("source")
        }))
    user = {
        "user_intent": user_context.get("q", ""),
        "city": user_context.get("city"),
        "neighborhood": user_context.get("neighborhood"),
        "preferences": user_context.get("preferences", {}),
        "candidates_count": len(candidates),
        "candidates": cand_lines
    }
    return json.dumps(user, ensure_ascii=False)

def call_groq_chat(messages: List[Dict], timeout=20) -> Dict:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.2
    }
    r = requests.post(GROQ_CHAT_URL, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

def recommend_with_groq(user_context: Dict, candidates: List[Dict]) -> List[Dict]:
    """
    user_context: {city, neighborhood, q, preferences}
    candidates: list of venue metadata dicts (should be prefiltered by spatial/distance and limited to N)
    returns: list of recommended items (structured)
    """
    sys_msg = {"role": "system", "content": build_system_prompt()}
    user_msg = {"role": "user", "content": build_user_prompt(user_context, candidates)}

    resp = call_groq_chat([sys_msg, user_msg])
    # Extract model text (depends on Groq response shape; similar to OpenAI-style)
    raw = ""
    try:
        raw = resp["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError("Unexpected Groq response format")

    # Be defensive: model should return JSON array. Try to parse.
    try:
        recs = json.loads(raw)
        # Validate structure and attach canonical metadata from candidates
        id_to_cand = {c["id"]: c for c in candidates}
        out = []
        for r in recs:
            vid = r.get("id")
            if not vid or vid not in id_to_cand:
                # Model invented or referred to unknown id — mark as unverified or skip
                r["_unverified"] = True
                r["_metadata"] = r.get("_raw", None)
            else:
                r["_unverified"] = False
                r["_metadata"] = id_to_cand[vid]
            out.append(r)
        return out
    except Exception as e:
        # If parse fails, don't crash — fallback to simple ranking (e.g., by distance or return empty)
        return []

# Example usage (in your app route)
# user_context = {"city": "Lisbon", "q": "romantic dinner", "preferences": {"budget":"mid"}}
# candidates = retrieve_candidates(user_context)  # from vector DB / spatial filter
# recs = recommend_with_groq(user_context, candidates)