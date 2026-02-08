"""
Enhanced RAG-based recommender for TravelLand
Integrates with existing semantic.py for structured venue recommendations
"""

import os
import json
import aiohttp
from typing import List, Dict, Optional
import logging

# Configure logging
logger = logging.getLogger(__name__)


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"

# Auto-detect latest available model
async def get_latest_groq_model() -> str:
    """Get the latest available Groq model, preferring Llama 3.3 70B"""
    if not GROQ_API_KEY:
        return "llama-3.1-8b-instant"  # fallback
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Accept-Encoding": "identity"}
            async with session.get(GROQ_MODELS_URL, headers=headers) as resp:
                if resp.status == 200:
                    models = await resp.json()
                    # Prefer Llama 3.3 70B, then 3.1 70B, then 3.1 8B
                    preferred_models = [
                        "llama-3.3-70b-versatile",
                        "llama-3.1-70b-versatile", 
                        "llama-3.1-8b-instant"
                    ]
                    
                    available_models = [m['id'] for m in models.get('data', [])]
                    for model in preferred_models:
                        if model in available_models:
                            logger.info(f"[traveland_rag] Using model: {model}")
                            return model
                    
                    # Fallback to first available model
                    if available_models:
                        logger.info(f"[traveland_rag] Using fallback model: {available_models[0]}")
                        return available_models[0]
    except Exception as e:
        logger.warning(f"[traveland_rag] Failed to detect models: {e}")
    
    return "llama-3.1-8b-instant"  # ultimate fallback

GROQ_MODEL = "llama-3.3-70b-versatile"  # will be updated at runtime

# Debug logging for RAG availability
if not GROQ_API_KEY:
    logger.warning("[traveland_rag] GROQ_API_KEY is not set in environment!")
else:
    logger.info(f"[traveland_rag] GROQ_API_KEY loaded: {GROQ_API_KEY[:6]}... (length: {len(GROQ_API_KEY)})")

class TravelLandRecommender:
    """RAG-based recommender adapted for TravelLand's venue/neighborhood system"""

    def __init__(self, session: aiohttp.ClientSession = None):
        self.api_key = GROQ_API_KEY
        self.model = GROQ_MODEL  # will be updated dynamically
        self.session = session  # Shared aiohttp session for connection reuse
        # Local synthesizer fallback (keeps outputs usable when Groq fails)
        try:
            from city_guides.src.synthesis_enhancer import SynthesisEnhancer
            self.synthesizer = SynthesisEnhancer()
        except Exception:
            self.synthesizer = None

    async def update_model(self):
        """Update to the latest available model"""
        self.model = await get_latest_groq_model()


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
        elif recommendation_type == "synthesis":
            # Strict synthesis prompt: instruct model to return structured enrichment for UI
            return (
                "You are a travel synthesis assistant. Given a list of candidate venues (with id, name, lat, lon, and osm_url) and optional short Wikivoyage snippets, "
                "return STRICT JSON (an array) of up to 8 synthesized venue objects. Each object MUST include: 'id' (must match a provided candidate id), 'name', "
                "'short_description' (<=140 chars), 'highlight' (<=80 chars), 'sources' (array e.g. [\"osm\",\"wikivoyage\"]), 'score' (0..1), and 'confidence' (low|medium|high). "
                "Do NOT invent or modify authoritative fields such as latitude, longitude, or osm_url. If you cannot confidently synthesize an item, omit it. "
                "Return JSON only (no prose)."
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

    async def call_groq_chat(self, messages: List[Dict], timeout: int = 6) -> Optional[Dict]:
        """Call GROQ API with async aiohttp for speed - 6s timeout for snappy UX"""
        if not self.api_key:
            logger.warning("GROQ_API_KEY not configured")
            return None

        # Auto-detect model on first call if still using default
        if self.model == "llama-3.3-70b-versatile":
            await self.update_model()

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 400,  # Reduced from 512 for speed
            "temperature": 0.2
        }

        # Log what Groq is being asked to do
        print(f"[GROQ_DEBUG] === Groq Call Started ===")
        print(f"[GROQ_DEBUG] Model: {self.model}")
        print(f"[GROQ_DEBUG] Messages being sent:")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            print(f"[GROQ_DEBUG]   Message {i+1} ({role}): {content[:200]}{'...' if len(content) > 200 else ''}")
        
        logger.info(f"[GROQ_DEBUG] === Groq Call Started ===")
        logger.info(f"[GROQ_DEBUG] Model: {self.model}")
        logger.info(f"[GROQ_DEBUG] Messages being sent:")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            logger.info(f"[GROQ_DEBUG]   Message {i+1} ({role}): {content[:200]}{'...' if len(content) > 200 else ''}")

        try:
            session = self.session or aiohttp.ClientSession()
            try:
                headers["Accept-Encoding"] = "identity"  # Avoid brotli compression
                async with session.post(GROQ_CHAT_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    resp.raise_for_status()
                    result = await resp.json()
                    
                    # Log Groq's response
                    print(f"[GROQ_DEBUG] Raw response received: {result}")
                    if 'choices' in result and len(result['choices']) > 0:
                        response_content = result['choices'][0]['message']['content']
                        print(f"[GROQ_DEBUG] Groq's thinking/response:")
                        print(f"[GROQ_DEBUG]   {response_content}")
                        print(f"[GROQ_DEBUG] === Groq Call Completed ===")
                        logger.info(f"[GROQ_DEBUG] Groq's thinking/response:")
                        logger.info(f"[GROQ_DEBUG]   {response_content}")
                        logger.info(f"[GROQ_DEBUG] === Groq Call Completed ===")
                    else:
                        print(f"[GROQ_DEBUG] Unexpected response format: {result}")
                        logger.warning(f"[GROQ_DEBUG] Unexpected response format: {result}")
                    
                    return result
            finally:
                if not self.session:
                    await session.close()
        except Exception as e:
            logger.error(f"GROQ API call failed: {e}")
            logger.error(f"[GROQ_DEBUG] === Groq Call Failed ===")
            return None

    async def recommend_synthesis_enhanced(self, user_context: Dict, candidates: List[Dict]) -> List[Dict]:
        """
        Enhanced synthesis flow:
          - Try RAG synthesis via Groq
          - Validate and normalize results
          - Fallback to local synthesis (SynthesisEnhancer) when Groq fails or returns invalid output
        """
        # Try the existing RAG path first
        try:
            sys_msg = {"role": "system", "content": self.build_system_prompt("synthesis")}
            user_msg = {"role": "user", "content": self.build_user_prompt(user_context, candidates, "synthesis")}
            resp = await self.call_groq_chat([sys_msg, user_msg], timeout=10)
            if resp:
                raw = resp["choices"][0]["message"]["content"]
                try:
                    recs = json.loads(raw)
                    validated = self._validate_and_normalize_synthesis(recs, candidates)
                    if validated:
                        logger.info(f"RAG synthesis produced {len(validated)} validated items")
                        return validated
                    else:
                        logger.warning("RAG synthesis produced no validated items; falling back")
                except json.JSONDecodeError:
                    logger.warning("RAG synthesis returned non-JSON response; falling back")
        except Exception as e:
            logger.exception(f"RAG synthesis step failed: {e}")

        # Local fallback
        if self.synthesizer:
            logger.info("Falling back to local synthesizer for synthesis output")
            return self.synthesizer.synthesize_venues(candidates, max_venues=8)

        return []

    def _validate_and_normalize_synthesis(self, recs: List[Dict], candidates: List[Dict]) -> List[Dict]:
        """
        Validate RAG synthesis output and apply safety rules
        """
        id_to_cand = {c.get('id') or c.get('name'): c for c in candidates}
        validated = []

        for r in recs:
            vid = r.get('id')
            if not vid or vid not in id_to_cand:
                logger.warning(f"Skipping synthesis item with invalid id: {vid}")
                continue

            # Ensure English description
            if 'short_description' in r and r['short_description'] and self.synthesizer:
                snippet, lang = self.synthesizer.extract_english_snippet(r['short_description'], 140)
                r['short_description'] = snippet
                r['detected_language'] = lang
                if lang != 'en':
                    logger.warning(f"Non-English description detected for {vid}: {lang}")

            if 'highlight' in r and r['highlight'] and self.synthesizer:
                if len(r['highlight']) > 80:
                    r['highlight'] = self.synthesizer.safe_trim(r['highlight'], 80)

            if 'sources' not in r or not isinstance(r['sources'], list):
                r['sources'] = ['osm']

            r['attribution'] = self.synthesizer.create_attribution(r['sources'], r.get('name', 'this location')) if self.synthesizer else 'Source: OpenStreetMap'

            if 'confidence' not in r or r['confidence'] not in ['low','medium','high']:
                r['confidence'] = 'medium'

            validated.append(r)

        return validated

    async def recommend_with_rag(self, user_context: Dict, candidates: List[Dict],
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

        resp = await self.call_groq_chat([sys_msg, user_msg], timeout=10)
        if not resp:
            return []

        # Extract model text
        raw = ""
        try:
            raw = resp["choices"][0]["message"]["content"]
            logger.debug(f"Groq model raw response: {raw}")
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
            logger.error(f"Groq model raw response (for debug): {raw}")
            return []

# Global instance for use in semantic.py - will be updated with shared session in app.py
recommender = TravelLandRecommender()

def recommend_venues_rag(user_context: Dict, candidates: List[Dict]) -> List[Dict]:
    """Convenience function for venue recommendations"""
    return recommender.recommend_with_rag(user_context, candidates, "venues")

def recommend_neighborhoods_rag(user_context: Dict, candidates: List[Dict]) -> List[Dict]:
    """Convenience function for neighborhood recommendations"""
    return recommender.recommend_with_rag(user_context, candidates, "neighborhoods")


def recommend_synthesis(user_context: Dict, candidates: List[Dict]) -> List[Dict]:
    """Convenience wrapper for synthesis-style outputs (strict UI enrichment schema)
    Enhanced behavior: try RAG synthesis, validate/normalize, then fallback to local synthesis if necessary.
    """
    # Prefer the enhanced synthesis path if available on the recommender
    if hasattr(recommender, 'recommend_synthesis_enhanced'):
        try:
            return recommender.recommend_synthesis_enhanced(user_context, candidates)
        except Exception:
            # fallback to original RAG path
            return recommender.recommend_with_rag(user_context, candidates, "synthesis")
    return recommender.recommend_with_rag(user_context, candidates, "synthesis")