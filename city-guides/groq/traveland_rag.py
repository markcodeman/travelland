"""
Enhanced RAG-based recommender for TravelLand
Integrates with existing semantic.py for structured venue recommendations
"""

import os
import json
import requests
from typing import List, Dict, Optional
import logging

# Configure logging
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

class TravelLandRecommender:
    """RAG-based recommender adapted for TravelLand's venue/neighborhood system"""

    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.model = GROQ_MODEL

    def build_system_prompt(self, recommendation_type: str = "venues") -> str:
        """Build system prompt based on recommendation type"""
        if recommendation_type == "venues":
            return (
                "You are a travel recommendation assistant for a city guide app. "
                "Given a short list of candidate venues with metadata, produce a JSON array of up to 6 recommendations ranked by relevance. "
                "Return JSON only (no explanatory text). Use only the candidate venues provided (do not invent new ones). "
                "Each item must reference the venue 'id' exactly as provided, include a numeric 'score' 0..1, a one-line 'reason', "
                "an array of 'tags', and a 'confidence' field (low/medium/high)."
            )
        else:  # neighborhoods
            return (
                "You are a neighborhood recommendation assistant. "
                "Given candidate neighborhoods, produce a JSON array of up to 4 recommendations. "
                "Return JSON only. Each item must include 'id', 'score' 0..1, 'reason', 'tags', and 'confidence'."
            )

    def build_user_prompt(self, user_context: Dict, candidates: List[Dict], recommendation_type: str = "venues") -> str:
        """Build user prompt with context and candidates"""
        # Keep each candidate short to reduce tokens
        cand_lines = []
        for v in candidates:
            if recommendation_type == "venues":
                cand_lines.append(json.dumps({
                    "id": v.get("id"),
                    "name": v.get("name"),
                    "address": v.get("address", ""),
                    "lat": v.get("lat"),
                    "lon": v.get("lon"),
                    "tags": (v.get("tags") or [])[:5],
                    "desc": (v.get("description") or "")[:200],  # limit length
                    "source": v.get("source")
                }))
            else:  # neighborhoods
                cand_lines.append(json.dumps({
                    "id": v.get("id") or v.get("name"),
                    "name": v.get("name"),
                    "lat": v.get("center", {}).get("lat"),
                    "lon": v.get("center", {}).get("lon"),
                    "tags": ["neighborhood"]
                }))

        user = {
            "user_intent": user_context.get("q", ""),
            "city": user_context.get("city"),
            "neighborhood": user_context.get("neighborhood"),
            "preferences": user_context.get("preferences", {}),
            "candidates_count": len(candidates),
            "candidates": cand_lines
        }

        # Add weather context if available
        if user_context.get("weather"):
            weather = user_context["weather"]
            user["weather"] = {
                "condition": weather.get("weathercode"),
                "temperature_c": weather.get("temperature_c"),
                "wind_kmh": weather.get("wind_kmh")
            }

        return json.dumps(user, ensure_ascii=False)

    def call_groq_chat(self, messages: List[Dict], timeout: int = 20) -> Optional[Dict]:
        """Call GROQ API with error handling"""
        if not self.api_key:
            logger.warning("GROQ_API_KEY not configured")
            return None

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.2
        }

        try:
            r = requests.post(GROQ_CHAT_URL, json=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"GROQ API call failed: {e}")
            return None

    def recommend_with_rag(self, user_context: Dict, candidates: List[Dict],
                          recommendation_type: str = "venues") -> List[Dict]:
        """
        Main RAG recommendation method

        Args:
            user_context: {city, neighborhood, q, preferences, weather}
            candidates: list of venue/neighborhood metadata dicts
            recommendation_type: "venues" or "neighborhoods"

        Returns:
            list of recommended items with structured metadata
        """
        if not candidates:
            return []

        sys_msg = {"role": "system", "content": self.build_system_prompt(recommendation_type)}
        user_msg = {"role": "user", "content": self.build_user_prompt(user_context, candidates, recommendation_type)}

        resp = self.call_groq_chat([sys_msg, user_msg])
        if not resp:
            return []

        # Extract model text
        raw = ""
        try:
            raw = resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error(f"Unexpected GROQ response format: {e}")
            return []

        # Parse JSON response
        try:
            recs = json.loads(raw)
            # Validate and attach canonical metadata
            id_to_cand = {c.get("id") or c.get("name"): c for c in candidates}
            out = []
            for r in recs:
                vid = r.get("id")
                if not vid or vid not in id_to_cand:
                    logger.warning(f"Model recommended unknown id: {vid}")
                    r["_unverified"] = True
                    r["_metadata"] = r.get("_raw", None)
                else:
                    r["_unverified"] = False
                    r["_metadata"] = id_to_cand[vid]
                out.append(r)
            return out
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GROQ response as JSON: {e}")
            return []

# Global instance for use in semantic.py
recommender = TravelLandRecommender()

def recommend_venues_rag(user_context: Dict, candidates: List[Dict]) -> List[Dict]:
    """Convenience function for venue recommendations"""
    return recommender.recommend_with_rag(user_context, candidates, "venues")

def recommend_neighborhoods_rag(user_context: Dict, candidates: List[Dict]) -> List[Dict]:
    """Convenience function for neighborhood recommendations"""
    return recommender.recommend_with_rag(user_context, candidates, "neighborhoods")