"""
Enhanced Synthesis Fallback Module for TravelLand
Provides stronger snippet extraction, language normalization, and safer trimming/attribution
"""

import re
from typing import List, Optional, Tuple, Dict

# No persistence imports needed - this module is self-contained

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
    def ensure_includes_term(snippet: str, original_text: str, term: str, fallback_sentence: Optional[str] = None, max_length: int = 140) -> str:
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

        # If no sentence fits, truncate the first sentence at word boundary
        if not result:
            first_sentence = sentences[0] if sentences else text
            if len(first_sentence) > max_length - len(ellipsis):
                # Find last space before the limit
                last_space = first_sentence.rfind(' ', 0, max_length - len(ellipsis) + 1)
                if last_space != -1:
                    result = first_sentence[:last_space].strip()
                else:
                    # No space found, hard truncate at limit
                    result = first_sentence[:max_length - len(ellipsis)].strip()
            else:
                result = first_sentence.strip()
        elif not result.endswith(('.', '!', '?')):
            # Break at word boundary for incomplete sentence
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
    def generate_neighborhood_paragraph(neighborhood: str, city: str, features: Optional[List[str]] = None, max_length: int = 500) -> str:
        """
        Generate a base paragraph about a neighborhood using available features.
        This is a local fallback when no external API data is available.
        """
        if not neighborhood or not city:
            return ""

        parts = [f"{neighborhood} is a neighborhood in {city}."]

        if features:
            feature_str = ", ".join(features[:5])
            parts.append(f"It is known for {feature_str}.")

        parts.append(f"Visitors to {neighborhood} can explore local streets, shops, and dining options that reflect the character of {city}.")

        paragraph = " ".join(parts)
        if len(paragraph) > max_length:
            paragraph = SynthesisEnhancer.safe_trim(paragraph, max_length)
        return paragraph

    @staticmethod
    def generate_neighborhood_content(neighborhood: str, city: str, features: Optional[List[str]] = None, max_length: int = 500) -> Dict[str, str]:
        """
        Generate structured neighborhood content with tagline, fun fact, and exploration.
        Enhanced version that returns structured data instead of just a paragraph.
        """
        if not neighborhood or not city:
            return {
                'tagline': f'Discover unique attractions and local experiences.',
                'fun_fact': 'This location has fascinating local history and culture waiting to be discovered!',
                'exploration': f'Explore and uncover the unique experiences that make this place special!'
            }

        # Generate base paragraph
        paragraph = SynthesisEnhancer.generate_neighborhood_paragraph(neighborhood, city, features, max_length)
        
        # Extract structured content from the paragraph
        structured_content = SynthesisEnhancer._extract_structured_content(neighborhood, city, paragraph)
        
        return structured_content

    @staticmethod
    def _extract_structured_content(neighborhood: str, city: str, paragraph: str) -> Dict[str, str]:
        """Extract structured content from a paragraph"""
        # Dynamic content extraction based on real paragraph content
        content_lower = paragraph.lower()
        neighborhood_lower = neighborhood.lower()
        city_lower = city.lower()
        
        # Extract key themes and facts from the paragraph
        tagline = SynthesisEnhancer._extract_tagline(neighborhood, city, paragraph)
        fun_fact = SynthesisEnhancer._extract_fun_fact(neighborhood, city, paragraph)
        exploration = SynthesisEnhancer._extract_exploration(neighborhood, city, paragraph)
        
        return {
            'tagline': tagline,
            'fun_fact': fun_fact,
            'exploration': exploration
        }

    @staticmethod
    def _extract_tagline(neighborhood: str, city: str, paragraph: str) -> str:
        """Extract a compelling tagline from the paragraph"""
        # Look for key descriptive phrases
        if 'known for' in paragraph:
            parts = paragraph.split('known for')
            if len(parts) > 1:
                after_known = parts[1].strip().split('.')[0].strip()
                return f"{neighborhood} is known for {after_known}."
        
        # Look for descriptive phrases
        descriptive_words = ['famous for', 'features', 'offers', 'boasts', 'includes', 'home to']
        for word in descriptive_words:
            if word in paragraph:
                parts = paragraph.split(word)
                if len(parts) > 1:
                    after_word = parts[1].strip().split('.')[0].strip()
                    return f"{neighborhood} is {word} {after_word}."
        
        # Fallback to first sentence
        sentences = paragraph.split('.')
        if len(sentences) > 0 and len(sentences[0].strip()) > 10:
            return sentences[0].strip() + '.'
        
        return f"Discover unique attractions and local experiences in {neighborhood}."

    @staticmethod
    def _extract_fun_fact(neighborhood: str, city: str, paragraph: str) -> str:
        """Extract an interesting fact from the paragraph"""
        # Look for numerical facts
        import re
        
        # Find numbers and statistics
        number_patterns = [
            r'(\d+(?:,\d+)*(?:\s*(?:million|billion|thousand|percent|%))\s*[\w\s]+)',
            r'(\d+(?:\.\d+)*)\s*(?:meters|feet|years|ago|since|established|founded|built)',
            r'over\s+(\d+(?:,\d+)*\s*[\w\s]+)',
            r'(\d+(?:,\d+)*)\s*(?:people|visitors|residents|shops|stores)'
        ]
        
        for pattern in number_patterns:
            matches = re.search(pattern, paragraph, re.IGNORECASE)
            if matches:
                fact = matches.group(0)
                return f"{neighborhood} {fact.strip()}!"
        
        # Look for superlatives
        superlative_patterns = [
            r'(?:the\s+)?(?:world\'s|city\'s|country\'s|area\'s|district\'s)\s+(?:largest|busiest|oldest|newest|tallest|most\s+\w+)',
            r'(?:one\s+of\s+the\s+|a\s+)',
            r'(?:famous|well-known|renowned|notable|popular)'
        ]
        
        for pattern in superlative_patterns:
            matches = re.search(pattern, paragraph, re.IGNORECASE)
            if matches:
                fact = matches.group(0)
                return f"{neighborhood} {fact.strip()}!"
        
        # Look for unique characteristics
        unique_patterns = [
            r'(?:home\s+to|features|boasts|includes|contains)',
            r'(?:founded\s+in|established\s+in|built\s+in)',
            r'(?:located\s+in|situated\s+in|found\s+in)'
        ]
        
        for pattern in unique_patterns:
            matches = re.search(pattern, paragraph, re.IGNORECASE)
            if matches:
                fact = matches.group(0)
                return f"{neighborhood} {fact.strip()}!"
        
        return f"{neighborhood} has fascinating local history and culture waiting to be discovered!"

    @staticmethod
    def _extract_exploration(neighborhood: str, city: str, paragraph: str) -> str:
        """Extract exploration suggestions from the paragraph"""
        # Look for action words and experiences
        action_words = ['explore', 'discover', 'experience', 'enjoy', 'visit', 'find', 'see']
        experience_words = ['restaurants', 'attractions', 'shops', 'museums', 'parks', 'beaches', 'landmarks', 'culture', 'nightlife']
        
        exploration_text = []
        
        # Find action + experience combinations
        for action in action_words:
            for experience in experience_words:
                if action in paragraph.lower() and experience in paragraph.lower():
                    exploration_text.append(f"{action} {experience}")
        
        if exploration_text:
            return f"From {', '.join(exploration_text[:3])}, {neighborhood} offers unique experiences for every traveler."
        
        # Fallback to generic exploration
        return f"Explore {neighborhood} and uncover the unique experiences that make this {city} neighborhood special!"

    @staticmethod
    def neutralize_tone(text: str, neighborhood: Optional[str] = None, city: Optional[str] = None, max_length: int = 500) -> str:
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
