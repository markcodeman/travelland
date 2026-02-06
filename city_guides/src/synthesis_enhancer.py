"""
Enhanced Synthesis Fallback Module for TravelLand
Provides stronger snippet extraction, language normalization, and safer trimming/attribution
"""

import re
from typing import List, Optional, Tuple

# Import persistence functions lazily to break circular import
_persistence_loaded = False
_load_weights = None
_save_weights = None

def _ensure_persistence():
    global _persistence_loaded, _load_weights, _save_weights
    if not _persistence_loaded:
        try:
            from persistence import load_weights, save_weights
            _load_weights, _save_weights = load_weights, save_weights
        except ImportError:
            from city_guides.src.persistence import load_weights, save_weights
            _load_weights, _save_weights = load_weights, save_weights
        _persistence_loaded = True
    return _load_weights, _save_weights

# Module-level access functions
def load_weights(*args, **kwargs):
    lw, _ = _ensure_persistence()
    return lw(*args, **kwargs)

def save_weights(*args, **kwargs):
    _, sw = _ensure_persistence()
    return sw(*args, **kwargs)

class SynthesisEnhancer:
    """
    Robust synthesis fallback with multi-source snippet extraction and English normalization
    """

    # Language detection patterns (simple heuristic-based)
    LANGUAGE_PATTERNS = {
        'es': r'[áéíóúñ¿¡]',  # Spanish
        'pt': r'[ãõçâêô]',    # Portuguese
        'fr': r'[àâæçéèêëïîôùûü]',  # French
        'de': r'[äöüß]',      # German
    }

    # Common non-English phrases to detect
    NON_ENGLISH_PHRASES = [
        'ubicado en', 'situado en', 'localizado',  # Spanish
        'localizado em', 'situado em',  # Portuguese
        'situé à', 'se trouve',  # French
        'befindet sich', 'liegt in',  # German
    ]

    # Translation hints for common terms
    TRANSLATION_HINTS = {
        'es': {
            'ubicado en': 'located in',
            'situado en': 'situated in',
            'cerca de': 'near',
            'conocido por': 'known for',
            'famoso por': 'famous for',
        },
        'pt': {
            'localizado em': 'located in',
            'situado em': 'situated in',
            'perto de': 'near',
            'conhecido por': 'known for',
            'famoso por': 'famous for',
        }
    }

    @staticmethod
    def detect_language(text: str) -> str:
        """
        Detect language of text (returns 'en' for English, or language code)
        """
        if not text:
            return 'en'

        text_lower = text.lower()

        # Check for non-English phrases
        for phrase in SynthesisEnhancer.NON_ENGLISH_PHRASES:
            if phrase in text_lower:
                # Determine which language
                for lang, pattern in SynthesisEnhancer.LANGUAGE_PATTERNS.items():
                    if re.search(pattern, text, re.IGNORECASE):
                        return lang
                return 'unknown'

        # Check character patterns
        for lang, pattern in SynthesisEnhancer.LANGUAGE_PATTERNS.items():
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            if matches > 3:  # Threshold for language detection
                return lang

        return 'en'

    @staticmethod
    def extract_english_snippet(text: str, max_length: int = 140) -> Tuple[str, str]:
        """
        Extract English snippet from text, with language detection

        Returns:
            (snippet, detected_language)
        """
        if not text:
            return ("", "en")

        detected_lang = SynthesisEnhancer.detect_language(text)

        # If English, extract directly
        if detected_lang == 'en':
            snippet = SynthesisEnhancer.safe_trim(text, max_length)
            return (snippet, 'en')

        # For non-English, try to find English sentences
        sentences = re.split(r'[.!?]+', text)
        english_sentences = []

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if SynthesisEnhancer.detect_language(sent) == 'en':
                english_sentences.append(sent)

        if english_sentences:
            # Use English sentences
            combined = '. '.join(english_sentences)
            snippet = SynthesisEnhancer.safe_trim(combined, max_length)
            return (snippet, 'en')

        # Fallback: apply basic translation hints
        translated = text
        if detected_lang in SynthesisEnhancer.TRANSLATION_HINTS:
            for orig, trans in SynthesisEnhancer.TRANSLATION_HINTS[detected_lang].items():
                translated = re.sub(re.escape(orig), trans, translated, flags=re.IGNORECASE)

        snippet = SynthesisEnhancer.safe_trim(translated, max_length)
        return (snippet, detected_lang)

    @staticmethod
    def ensure_includes_term(snippet: str, original_text: str, term: str, fallback_sentence: str = None, max_length: int = 140) -> str:
        """
        Ensure the returned snippet includes the specified term (e.g., neighborhood name or leading article like 'Las').

        Strategy:
        - If term is present in snippet (case-insensitive), return snippet unchanged.
        - Else search original_text for a sentence containing term and prepend or replace snippet with that sentence (trimmed).
        - Else, look for pattern of term followed by a capitalized word (e.g., 'Las Conchas') and use that phrase.
        - If nothing is found, optionally prepend a fallback_sentence (e.g., '<term> is a neighborhood in ...') and trim.
        """
        if not snippet:
            snippet = ''
        if not term:
            return SynthesisEnhancer.safe_trim(snippet, max_length)

        term_norm = term.lower()
        if term_norm in (snippet or '').lower():
            return SynthesisEnhancer.safe_trim(snippet, max_length)

        # Try to find a sentence in original_text that mentions the term
        if original_text:
            sentences = re.split(r'(?<=[.!?])\s+', original_text)
            for sent in sentences:
                if term_norm in sent.lower():
                    sent = sent.strip()
                    # If sentence is long, trim it
                    sent_snip = SynthesisEnhancer.safe_trim(sent, max_length)
                    # Prefer sentence + existing snippet if space allows
                    combined = (sent_snip + ' ' + snippet).strip()
                    return SynthesisEnhancer.safe_trim(combined, max_length)

            # If no sentence match, try to find 'term + ProperNoun' e.g., 'Las Conchas'
            m = re.search(r'(' + re.escape(term) + r'\s+[A-ZÀ-ÖØ-Þ][\w\-]+)', original_text)
            if m:
                found = m.group(1).strip()
                combined = (found + '. ' + snippet).strip()
                return SynthesisEnhancer.safe_trim(combined, max_length)

        # As a last resort, prepend fallback if provided
        if fallback_sentence:
            combined = (fallback_sentence.strip() + ' ' + snippet).strip()
            return SynthesisEnhancer.safe_trim(combined, max_length)

        # Nothing we can find; return trimmed original snippet
        return SynthesisEnhancer.safe_trim(snippet, max_length)

    @staticmethod
    def safe_trim(text: str, max_length: int = 140, ellipsis: str = '...') -> str:
        """
        Safely trim text to max_length, breaking at sentence or word boundaries
        """
        if not text or len(text) <= max_length:
            return text.strip()

        # Try to break at sentence boundary
        sentences = re.split(r'([.!?]+\s+)', text)
        result = ""

        for i, part in enumerate(sentences):
            if len(result + part) <= max_length - len(ellipsis):
                result += part
            else:
                break

        if result and not result.endswith(('.', '!', '?')):
            # Break at word boundary
            words = result.split()
            result = ' '.join(words[:-1]) if len(words) > 1 else words[0]

        return (result.strip() + ellipsis).strip()

    @staticmethod
    def extract_image_attributions(text: str):
        """Extract lines like 'Image via X (url)' from a block of text.
        Returns (clean_text, attributions) where attributions is a list of dicts {provider, url}.
        """
        if not text:
            return text, []
        atts = []
        patt = re.compile(r"(?im)^\s*Image\s+via\s+([^\(\n]+)(?:\s*\((https?://[^\)\n]+)\))?\s*$")
        def _collect(m):
            provider = m.group(1).strip()
            url = m.group(2).strip() if m.group(2) else None
            atts.append({'provider': provider, 'url': url})
            return ''
        clean = patt.sub(lambda m: _collect(m) or '', text).strip()
        seen = set()
        uniq = []
        for a in atts:
            key = (a.get('url') or '').strip().lower() or a.get('provider','').strip().lower()
            if key and key not in seen:
                seen.add(key)
                uniq.append(a)
        return clean, uniq

    @staticmethod
    def generate_neighborhood_paragraph(neighborhood: str, city: str, features: Optional[List[str]] = None, max_length: int = 240) -> str:
        """
        Generate a concise neighborhood paragraph that includes the neighborhood and city.
        If `features` are provided, mention one or two of them.
        """
        if not neighborhood or not city:
            return ''

        parts = []
        parts.append(f"{neighborhood} is a neighborhood in {city}.")

        if features:
            # use up to two features for brevity
            chosen = [f.strip() for f in features if f and f.strip()][:2]
            if chosen:
                if len(chosen) == 1:
                    parts.append(f"It's known for {chosen[0]}.")
                else:
                    parts.append(f"It's known for {chosen[0]} and {chosen[1]}.")
        else:
            parts.append("It has local attractions worth exploring.")

        paragraph = ' '.join(parts)
        paragraph = SynthesisEnhancer.ensure_includes_term(paragraph, paragraph, neighborhood, fallback_sentence=f"{neighborhood} is a neighborhood in {city}.", max_length=max_length)
        return SynthesisEnhancer.safe_trim(paragraph, max_length)

    @staticmethod
    def neutralize_tone(text: str, neighborhood: Optional[str] = None, city: Optional[str] = None, max_length: int = 200) -> str:
        """
        Remove first-person tone and personalize output to include neighborhood/city when provided.
        This is a lightweight neutralizer (not an LLM). It removes obvious first-person pronouns
        and replaces possessives with neutral forms.
        """
        if not text:
            base = ''
        else:
            base = text.strip()

        # Remove first-person pronouns/phrases (simple heuristics)
        # Remove standalone 'I'/'We' at sentence starts and common contractions
        base = re.sub(r"\bI\b", "", base)
        base = re.sub(r"\bI'm\b", "", base, flags=re.IGNORECASE)
        base = re.sub(r"\bI've\b", "", base, flags=re.IGNORECASE)
        base = re.sub(r"\bWe\b", "", base)
        base = re.sub(r"\bWe're\b", "", base, flags=re.IGNORECASE)
        base = re.sub(r"\bWe've\b", "", base, flags=re.IGNORECASE)

        # Replace possessives 'my'/'our' with neutral 'the'
        base = re.sub(r"\bmy\b", "the", base, flags=re.IGNORECASE)
        base = re.sub(r"\bour\b", "the", base, flags=re.IGNORECASE)

        # Collapse extra whitespace created by removals
        base = re.sub(r"\s{2,}", " ", base).strip()

        # Ensure neighborhood/city are present and avoid overly generic closing lines
        if neighborhood:
            base = SynthesisEnhancer.ensure_includes_term(base, base, neighborhood, fallback_sentence=f"{neighborhood} is a neighborhood in {city or ''}.")


        # Replace generic praise clauses with a neutral paraphrase even if keywords exist
        low = (text or '').lower()
        has_food = 'food' in low or 'restaurant' in low or 'dining' in low
        has_atmos = 'atmosphere' in low or 'atmospheric' in low or 'atmos' in low
        has_unforgettable = 'unforgettable' in low or 'amazing' in low or 'incredible' in low

        # If original is overly generic and praises 'local food and atmosphere', rewrite it
        if has_food and has_atmos:
            templates_fa = [
                "The neighborhood offers notable local food and a lively atmosphere.",
                "The area features local eateries and a strong neighborhood atmosphere.",
                "Visitors will find local dining options and a vibrant atmosphere.",
            ]
            idx = abs(hash((neighborhood or '') + (city or '') + base)) % len(templates_fa)
            replacement = templates_fa[idx]
            # Remove common superlatives then append replacement
            base = re.sub(r"\b(unforgettable|amazing|incredible|fantastic|wonderful)\b[\.\!\,\s]*", "", base, flags=re.IGNORECASE)
            # Try to remove trailing generic clause fragments
            base = re.sub(r"(the\s+local\s+food\s+and\s+atmosphere[\.,!]*)", '', base, flags=re.IGNORECASE)
            base = base.strip()
            # Remove orphan leading verb fragments left after pronoun removal (e.g., 'loved walking... when visited...')
            base = re.sub(r'^[a-z]+[^\.\n]*?(?:when|while|as|during)[^\.\n]*[\.]?', '', base, flags=re.IGNORECASE).strip()
            # Remove leading or trailing isolated copula fragments like 'were.' or 'was.'
            base = re.sub(r'^\s*(?:were|was|is|are)[\.\,\s]*', '', base, flags=re.IGNORECASE).strip()
            base = re.sub(r'\b(?:were|was|is|are)[\.\,\s]*$', '', base, flags=re.IGNORECASE).strip()
            if base:
                base = base.rstrip('. ,') + '. ' + replacement
            else:
                base = replacement
        elif has_food and not has_atmos:
            templates_f = [
                "The area has local eateries and dining options.",
                "Local dining options are a notable feature of the neighborhood.",
            ]
            idx = abs(hash((neighborhood or '') + (city or '') + base)) % len(templates_f)
            replacement = templates_f[idx]
            base = re.sub(r"\b(unforgettable|amazing|incredible)\b[\.\!\,\s]*", "", base, flags=re.IGNORECASE)
            base = re.sub(r"(the\s+local\s+food[\.,!]*)", '', base, flags=re.IGNORECASE).strip()
            base = re.sub(r'^[a-z]+[^\.\n]*?(?:when|while|as|during)[^\.\n]*[\.]?', '', base, flags=re.IGNORECASE).strip()
            base = re.sub(r'^\s*(?:were|was|is|are)[\.\,\s]*', '', base, flags=re.IGNORECASE).strip()
            base = re.sub(r'\b(?:were|was|is|are)[\.\,\s]*$', '', base, flags=re.IGNORECASE).strip()
            base = (base.rstrip('. ,') + '. ' + replacement) if base else replacement
        elif has_atmos and not has_food:
            templates_a = [
                "The neighborhood is noted for its atmosphere and local character.",
                "The area has a distinctive local atmosphere worth exploring.",
            ]
            idx = abs(hash((neighborhood or '') + (city or '') + base)) % len(templates_a)
            replacement = templates_a[idx]
            base = re.sub(r"\b(unforgettable|amazing|incredible)\b[\.\!\,\s]*", "", base, flags=re.IGNORECASE)
            base = re.sub(r"(the\s+local\s+atmosphere[\.,!]*)", '', base, flags=re.IGNORECASE).strip()
            base = re.sub(r'^[a-z]+[^\.\n]*?(?:when|while|as|during)[^\.\n]*[\.]?', '', base, flags=re.IGNORECASE).strip()
            base = re.sub(r'^\s*(?:were|was|is|are)[\.\,\s]*', '', base, flags=re.IGNORECASE).strip()
            base = re.sub(r'\b(?:were|was|is|are)[\.\,\s]*$', '', base, flags=re.IGNORECASE).strip()
            base = (base.rstrip('. ,') + '. ' + replacement) if base else replacement
        else:
            # Provide a cautious, varied phrasing if original lacked specifics
            templates = [
                "Walking through {neighborhood} in {city} reveals a lively local character.",
                "{neighborhood} in {city} is known for its local atmosphere and points of interest.",
                "Visitors to {neighborhood} in {city} will find a mix of local sights and neighborhood charm.",
                "{neighborhood} in {city} features a variety of local streets and notable spots to explore.",
            ]
            seed = (neighborhood or '') + '|' + (city or '') + '|' + (base or '')
            idx = abs(hash(seed)) % len(templates)
            try:
                summary = templates[idx].format(neighborhood=neighborhood or '', city=city or '')
            except Exception:
                summary = f"{neighborhood} is a neighborhood in {city or ''}."
            if len(base) < 40:
                base = summary

        # Final safe trim
        return SynthesisEnhancer.safe_trim(base, max_length)

    @staticmethod
    def create_attribution(provider: Optional[str] = None, url: Optional[str] = None) -> str:
        """
        Create attribution string for sources
        """
        if provider and url:
            return f"Source: {provider} ({url})"
        elif provider:
            return f"Source: {provider}"
        elif url:
            return f"Source: {url}"
        else:
            return "Source: OpenStreetMap"
