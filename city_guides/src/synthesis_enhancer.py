"""
Enhanced Synthesis Fallback Module for TravelLand
Provides stronger snippet extraction, language normalization, and safer trimming/attribution
"""

import re
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import hashlib

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
    def extract_venue_highlights(venue_data: Dict, sources: List[str]) -> Dict:
        """
        Extract highlights from multiple sources with confidence scoring

        Args:
            venue_data: Dict with venue information
            sources: List of source identifiers (e.g., ['osm', 'wikivoyage', 'ddgs'])

        Returns:
            Dict with extracted highlights and metadata
        """
        highlights = {
            'short_description': '',
            'highlight': '',
            'tags': [],
            'confidence': 'low',
            'sources_used': [],
            'language': 'en'
        }

        # Priority order for description extraction
        description_fields = [
            'description',
            'wikivoyage_snippet',
            'ddgs_snippet',
            'summary',
            'excerpt',
            'tags'
        ]

        # Extract description
        for field in description_fields:
            if field in venue_data and venue_data[field]:
                text = venue_data[field]
                if isinstance(text, list):
                    text = ', '.join(str(t) for t in text)

                snippet, lang = SynthesisEnhancer.extract_english_snippet(text, 140)
                if snippet:
                    highlights['short_description'] = snippet
                    highlights['language'] = lang
                    highlights['sources_used'].append(field)
                    break

        # Extract highlight (shorter, punchier)
        highlight_fields = ['amenity', 'tourism', 'tags', 'cuisine', 'historic']
        highlight_parts = []

        for field in highlight_fields:
            if field in venue_data and venue_data[field]:
                value = venue_data[field]
                if isinstance(value, str):
                    highlight_parts.append(value.replace('_', ' ').title())
                elif isinstance(value, list):
                    highlight_parts.extend([str(v).replace('_', ' ').title() for v in value[:2]])

        if highlight_parts:
            highlights['highlight'] = SynthesisEnhancer.safe_trim(
                ' • '.join(highlight_parts[:3]), 
                80
            )

        # Extract tags
        if 'tags' in venue_data:
            tags = venue_data['tags']
            if isinstance(tags, str):
                highlights['tags'] = [t.strip() for t in tags.split(',')][:5]
            elif isinstance(tags, list):
                highlights['tags'] = [str(t) for t in tags][:5]

        # Confidence scoring
        confidence_score = 0
        if highlights['short_description']:
            confidence_score += 40
        if highlights['highlight']:
            confidence_score += 30
        if highlights['tags']:
            confidence_score += 20
        if len(highlights['sources_used']) > 1:
            confidence_score += 10

        if confidence_score >= 70:
            highlights['confidence'] = 'high'
        elif confidence_score >= 40:
            highlights['confidence'] = 'medium'
        else:
            highlights['confidence'] = 'low'

        return highlights

    @staticmethod
    def synthesize_venues(candidates: List[Dict], max_venues: int = 8) -> List[Dict]:
        """
        Synthesize venue data from multiple sources with robust fallbacks

        Args:
            candidates: List of venue dicts from various sources
            max_venues: Maximum number of venues to return

        Returns:
            List of synthesized venue dicts with enriched metadata
        """
        synthesized = []
        seen_ids = set()

        for candidate in candidates:
            # Skip if already processed
            venue_id = candidate.get('id') or candidate.get('osm_id') or candidate.get('name')
            if not venue_id:
                continue

            # Create unique ID
            id_hash = hashlib.md5(str(venue_id).encode()).hexdigest()[:12]
            if id_hash in seen_ids:
                continue
            seen_ids.add(id_hash)

            # Determine sources
            sources = []
            if candidate.get('source'):
                sources.append(candidate['source'])
            if candidate.get('wikivoyage_snippet'):
                sources.append('wikivoyage')
            if candidate.get('ddgs_snippet'):
                sources.append('web')
            if not sources:
                sources = ['osm']

            # Extract highlights
            highlights = SynthesisEnhancer.extract_venue_highlights(candidate, sources)

            # Build synthesized venue
            synth_venue = {
                'id': venue_id,
                'name': candidate.get('name', 'Unnamed Location'),
                'lat': candidate.get('lat'),
                'lon': candidate.get('lon'),
                'address': candidate.get('address', ''),
                'short_description': highlights['short_description'],
                'highlight': highlights['highlight'],
                'tags': highlights['tags'],
                'sources': list(set(sources)),
                'confidence': highlights['confidence'],
                'language': highlights['language'],
                'osm_url': candidate.get('osm_url'),
                'website': candidate.get('website'),
                'synthesized_at': datetime.utcnow().isoformat(),
            }

            # Calculate relevance score
            score = 0.5  # Base score
            if highlights['confidence'] == 'high':
                score += 0.3
            elif highlights['confidence'] == 'medium':
                score += 0.15

            if len(sources) > 1:
                score += 0.1

            if synth_venue['website']:
                score += 0.05

            if highlights['language'] == 'en':
                score += 0.05

            synth_venue['score'] = min(score, 1.0)

            synthesized.append(synth_venue)

            if len(synthesized) >= max_venues:
                break

        # Sort by score descending
        synthesized.sort(key=lambda x: x['score'], reverse=True)

        return synthesized[:max_venues]

    @staticmethod
    def create_attribution(sources: List[str], venue_name: str) -> str:
        """
        Create safe attribution text for synthesized content

        Args:
            sources: List of source identifiers
            venue_name: Name of the venue

        Returns:
            Attribution string
        """
        if not sources:
            return f"Information about {venue_name}"

        source_names = {
            'osm': 'OpenStreetMap',
            'wikivoyage': 'Wikivoyage',
            'web': 'Web sources',
            'geoapify': 'Geoapify',
            'opentripmap': 'OpenTripMap',
            'mapillary': 'Mapillary'
        }

        readable_sources = [source_names.get(s, s.title()) for s in sources]

        if len(readable_sources) == 1:
            return f"Source: {readable_sources[0]}"
        elif len(readable_sources) == 2:
            return f"Sources: {readable_sources[0]} and {readable_sources[1]}"
        else:
            return f"Sources: {', '.join(readable_sources[:-1])}, and {readable_sources[-1]}"

    @staticmethod
    def generate_neighborhood_paragraph(neighborhood: str, city: str, features: Optional[List[str]] = None, max_length: int = 300) -> str:
        """
        Create a concise, informative, neutral English paragraph about a neighborhood.

        Uses optional features (list of short phrases) to make the paragraph specific. If no features
        are available, returns a short, factual paragraph that avoids boilerplate phrases like
        "known locally for its character" or "try searching for...".
        """
        if not neighborhood or not city:
            return ""

        nb = neighborhood.strip()
        ci = city.strip()

        if features:
            # Use up to 3 features
            f = [str(x).strip().rstrip('.') for x in features if x]
            f = f[:3]
            if f:
                # Join features naturally
                if len(f) == 1:
                    feats = f[0]
                elif len(f) == 2:
                    feats = f"{f[0]} and {f[1]}"
                else:
                    feats = f"{', '.join(f[:-1])}, and {f[-1]}"
                para = f"{nb} is a neighborhood in {ci} noted for {feats}. It is compact and easy to explore on foot, with local shops and eateries to discover."
                return SynthesisEnhancer.safe_trim(para, max_length)

        # If no specific features, provide a neutral, slightly richer default paragraph
        para = (
            f"{nb} is a neighborhood in {ci}. It features local markets, traditional architecture, and a selection of small cafés and shops. "
            "The area is pleasant to explore on foot and provides a taste of everyday local life."
        )
        return SynthesisEnhancer.safe_trim(para, max_length)

    @staticmethod
    def neutralize_tone(text: str, neighborhood: str = None, city: str = None, max_length: int = 400) -> str:
        """
        Convert first-person / promotional snippets into a neutral, travel-guide tone.

        Heuristics:
        - Replace leading first-person sentences starting with "I" or "We" with neutral sentences referencing the neighborhood or visitors.
        - Replace remaining first-person pronouns with neutral alternatives where safe.
        - Ensure the returned text mentions the neighborhood or city when available.
        """
        if not text:
            return text

        # Split into sentences
        sents = re.split(r'(?<=[.!?])\s+', text.strip())
        out_sents = []
        fp_pattern = re.compile(r"^(I|We|I'm|We're|I\b)\b", re.IGNORECASE)
        lead_verb_strip = re.compile(r"^(?:I|We|I'm|We're|I\s+was|We\s+were|I\s+embarked on|I\s+visited|I\s+experienced|I\s+went|I\s+explored|I\s+took)\s+", re.IGNORECASE)

        for s in sents:
            s = s.strip()
            if not s:
                continue
            # If sentence starts with first-person, rewrite to a safe neutral sentence
            if fp_pattern.match(s):
                low = s.lower()
                mentions = {
                    'walking': any(k in low for k in ['walk', 'walking', 'walks', 'walking tour', 'tour']),
                    'history': 'history' in low,
                    'beer': any(k in low for k in ['beer', 'brew', 'brewery', 'brews', 'breweries', 'craft beer'])
                }

                if neighborhood:
                    if mentions['walking'] and mentions['history']:
                        new = f"Visitors to {neighborhood} can take walking tours that highlight its history and local culture."
                    elif mentions['walking']:
                        new = f"Visitors to {neighborhood} can enjoy walking tours and explore the area on foot."
                    elif mentions['history'] and mentions['beer']:
                        new = f"{neighborhood} features historical sites and local spots for craft beer and refreshments."
                    elif mentions['history']:
                        new = f"{neighborhood} is known for its history and local points of interest."
                    elif mentions['beer']:
                        new = f"Visitors to {neighborhood} can find local craft beer and neighborhood eateries."
                    else:
                        new = f"Visitors to {neighborhood} can explore its history and local attractions."
                elif city:
                    new = f"Visitors to {city} can explore local points of interest in the {neighborhood or 'area'}."
                else:
                    new = "Visitors can explore local points of interest."

                out_sents.append(new)
                continue

            # Replace standalone first-person pronouns in the sentence with neutral terms
            s = re.sub(r"\bI\b", "visitors", s, flags=re.IGNORECASE)
            s = re.sub(r"\bwe\b", "visitors", s, flags=re.IGNORECASE)
            # Fix common 'visitors was' -> 'visitors were' and similar simple verb agreement problems
            s = re.sub(r"\bvisitors\s+was\b", "visitors were", s, flags=re.IGNORECASE)
            s = re.sub(r"\bvisitors\s+were\s+in\s+for\b", "visitors can expect", s, flags=re.IGNORECASE)
            out_sents.append(s)

        result = ' '.join(out_sents).strip()

        # Ensure neighborhood or city is mentioned, otherwise prepend a small neutral lead
        if neighborhood and neighborhood.lower() not in result.lower():
            result = (f"{neighborhood} is a neighborhood in {city}. " + result).strip() if city else (f"{neighborhood}. " + result).strip()

        # Final trim
        return SynthesisEnhancer.safe_trim(result, max_length)


# Test suite for synthesis enhancement
def test_synthesis_enhancement():
    """Test suite for synthesis fallback improvements"""

    enhancer = SynthesisEnhancer()

    # Test language detection
    print("=" * 80)
    print("LANGUAGE DETECTION TESTS")
    print("=" * 80)

    lang_tests = [
        ("This is an English sentence.", "en"),
        ("Este es un restaurante ubicado en el centro.", "es"),
        ("Este restaurante está localizado em Lisboa.", "pt"),
        ("Ce restaurant est situé à Paris.", "fr"),
        ("Das Restaurant befindet sich in Berlin.", "de"),
    ]

    for text, expected in lang_tests:
        detected = enhancer.detect_language(text)
        status = "✅" if detected == expected else "❌"
        print(f"{status} '{text[:50]}...' -> {detected} (expected: {expected})")

    # Test snippet extraction
    print("\n" + "=" * 80)
    print("SNIPPET EXTRACTION TESTS")
    print("=" * 80)

    snippet_tests = [
        {
            'text': "This is a beautiful historic landmark located in the heart of the city. It was built in 1850 and features stunning architecture. Visitors can explore the grounds daily from 9am to 5pm.",
            'max_length': 140,
            'should_contain': 'historic landmark'
        },
        {
            'text': "Este es un restaurante famoso. This restaurant is known for its excellent seafood and waterfront views. It has been serving locals since 1920.",
            'max_length': 140,
            'should_contain': 'restaurant'
        },
        {
            'text': "Ubicado en el centro histórico. Located in the historic center, this café offers traditional pastries and coffee.",
            'max_length': 100,
            'should_contain': 'café'
        }
    ]
    # New test for ensuring neighborhood inclusion (addresses 'Las' truncation cases)
    print("\n" + "=" * 80)
    print("NEIGHBORHOOD INCLUSION TEST")
    print("=" * 80)
    orig = "Las Conchas is a small neighborhood in Tlaquepaque. We start in San Pedro Tlaquepaque, a typical and picturesque town, you will get to know its tourist area and the largest cantina in Mexico \"El Parían\""
    initial = "We start in San Pedro Tlaquepaque, a typical and picturesque town, you will get to know its tourist area and the largest cantina in Mexico \"El Parían\""
    enriched = SynthesisEnhancer.ensure_includes_term(initial, orig, 'Las Conchas', fallback_sentence='Las Conchas is a neighborhood in Tlaquepaque.', max_length=200)
    status = '✅' if 'Las Conchas' in enriched else '❌'
    print(f"{status} ensure_includes_term -> '{enriched}'")
    for i, test in enumerate(snippet_tests, 1):
        snippet, lang = enhancer.extract_english_snippet(test['text'], test['max_length'])
        contains = test['should_contain'] in snippet.lower()
        status = "✅" if contains and len(snippet) <= test['max_length'] else "❌"
        print(f"\nTest {i}: {status}")
        print(f"  Original: {test['text'][:60]}...")
        print(f"  Snippet: {snippet}")
        print(f"  Language: {lang} | Length: {len(snippet)}/{test['max_length']}")

    # Test venue synthesis
    print("\n" + "=" * 80)
    print("VENUE SYNTHESIS TESTS")
    print("=" * 80)

    test_venues = [
        {
            'id': 'venue_1',
            'name': 'Historic Cathedral',
            'lat': 40.7128,
            'lon': -74.0060,
            'description': 'A beautiful 18th century cathedral with stunning Gothic architecture.',
            'tags': ['historic', 'religious', 'architecture'],
            'source': 'osm',
            'wikivoyage_snippet': 'One of the most visited landmarks in the city.'
        },
        {
            'id': 'venue_2',
            'name': 'Seaside Restaurant',
            'lat': 40.7580,
            'lon': -73.9855,
            'description': 'Este restaurante está ubicado en la costa. Fresh seafood with ocean views.',
            'tags': 'restaurant,seafood',
            'source': 'geoapify',
            'website': 'https://example.com'
        },
        {
            'id': 'venue_3',
            'name': 'City Park',
            'lat': 40.7829,
            'lon': -73.9654,
            'tags': ['park', 'recreation'],
            'source': 'osm'
        }
    ]

    synthesized = enhancer.synthesize_venues(test_venues, max_venues=8)

    print(f"\nSynthesized {len(synthesized)} venues:\n")

    for i, venue in enumerate(synthesized, 1):
        print(f"Venue {i}: {venue['name']}")
        print(f"  Description: {venue['short_description']}")
        print(f"  Highlight: {venue['highlight']}")
        print(f"  Confidence: {venue['confidence']} | Score: {venue['score']:.2f}")
        print(f"  Sources: {', '.join(venue['sources'])}")
        print(f"  Language: {venue['language']}")
        print(f"  Attribution: {enhancer.create_attribution(venue['sources'], venue['name'])}")
        print()

    print("=" * 80)
    print("SYNTHESIS ENHANCEMENT TESTS COMPLETE")
    print("=" * 80)

# Run tests when executed directly
if __name__ == '__main__':
    test_synthesis_enhancement()
