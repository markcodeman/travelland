"""
Enhanced Neighborhood Disambiguation Module for TravelLand
Handles problematic cases like Las Conchas, La Perla with robust heuristics
"""

import re
from typing import Optional, List, Dict, Tuple
from difflib import SequenceMatcher
import unicodedata

class NeighborhoodDisambiguator:
    """
    Robust neighborhood name disambiguation with multi-level heuristics
    """

    # Known problematic neighborhoods with canonical forms
    CANONICAL_NAMES = {
        # Puerto Rico
        'la perla': 'La Perla',
        'laperla': 'La Perla',
        'perla': 'La Perla',

        # Mexico (Rocky Point area)
        'las conchas': 'Las Conchas',
        'lasconchas': 'Las Conchas',
        'conchas': 'Las Conchas',

        # Rio de Janeiro
        'santa teresa': 'Santa Teresa',
        'santateresa': 'Santa Teresa',
        'vidigal': 'Vidigal',

        # Common patterns
        'barra da tijuca': 'Barra da Tijuca',
        'barradatijuca': 'Barra da Tijuca',
        'jardim botanico': 'Jardim Botânico',
        'jardimbotanico': 'Jardim Botânico',
        # Generic common names that often lose accents
        'revolucion': 'Revolución',
        'revolución': 'Revolución',
    }

    # City-specific neighborhood validation
    CITY_NEIGHBORHOODS = {
        'Rio de Janeiro': {
            'valid': ['Copacabana', 'Ipanema', 'Leblon', 'Santa Teresa', 'Barra da Tijuca', 
                     'Lapa', 'Botafogo', 'Jardim Botânico', 'Gamboa', 'Leme', 'Vidigal',
                     'Rocinha', 'Tijuca', 'Centro', 'Flamengo', 'Urca'],
            'aliases': {
                'barra': 'Barra da Tijuca',
                'jardim': 'Jardim Botânico',
                'santa': 'Santa Teresa'
            }
        },
        'San Juan': {
            'valid': ['La Perla', 'Old San Juan', 'Condado', 'Santurce', 'Miramar', 
                     'Hato Rey', 'Río Piedras', 'Ocean Park'],
            'aliases': {
                'perla': 'La Perla',
                'viejo san juan': 'Old San Juan',
                'old town': 'Old San Juan'
            }
        },
        'Puerto Peñasco': {
            'valid': ['Las Conchas', 'Sandy Beach', 'Cholla Bay', 'Centro', 
                     'Mirador', 'Encanto'],
            'aliases': {
                'conchas': 'Las Conchas',
                'sandy': 'Sandy Beach',
                'cholla': 'Cholla Bay'
            }
        },
        'Tlaquepaque': {
            'valid': ['Centro', 'El Refugio', 'La Guadalupana', 'San Pedrito', 
                     'Santa Anita', 'Artesanos'],
            'aliases': {
                'centro historico': 'Centro',
                'downtown': 'Centro'
            }
        }
    }

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for comparison: lowercase, remove accents, strip whitespace"""
        if not text:
            return ""
        # Remove accents
        text = unicodedata.normalize('NFKD', text)
        text = ''.join([c for c in text if not unicodedata.combining(c)])
        # Lowercase and strip
        text = text.lower().strip()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text

    @staticmethod
    def similarity_score(a: str, b: str) -> float:
        """Calculate similarity between two strings (0.0 to 1.0)"""
        return SequenceMatcher(None, a, b).ratio()

    @classmethod
    def canonicalize(cls, neighborhood: str, city: Optional[str] = None) -> str:
        """
        Return canonical form of neighborhood name

        Args:
            neighborhood: Raw neighborhood name
            city: Optional city context for disambiguation

        Returns:
            Canonical neighborhood name
        """
        if not neighborhood:
            return ""

        normalized = cls.normalize_text(neighborhood)

        # Check direct canonical mapping
        if normalized in cls.CANONICAL_NAMES:
            return cls.CANONICAL_NAMES[normalized]

        # Check city-specific aliases
        if city and city in cls.CITY_NEIGHBORHOODS:
            city_data = cls.CITY_NEIGHBORHOODS[city]
            if normalized in city_data.get('aliases', {}):
                return city_data['aliases'][normalized]

        # Fuzzy match against city known neighborhoods (help with misspellings)
        if city and city in cls.CITY_NEIGHBORHOODS:
            valid_neighborhoods = cls.CITY_NEIGHBORHOODS[city]['valid']
            best = None
            best_score = 0.0
            for v in valid_neighborhoods:
                score = cls.similarity_score(normalized, cls.normalize_text(v))
                if score > best_score:
                    best_score = score
                    best = v
            # If sufficiently similar, return the canonical valid name
            if best and best_score >= 0.75:
                return best

        # Return title-cased original if no match
        return neighborhood.strip().title()

    @classmethod
    def validate_neighborhood(cls, neighborhood: str, city: str, 
                            confidence_threshold: float = 0.75) -> Tuple[bool, float, Optional[str]]:
        """
        Validate neighborhood belongs to city with confidence score

        Args:
            neighborhood: Neighborhood name to validate
            city: City name
            confidence_threshold: Minimum confidence for validation (0.0-1.0)

        Returns:
            (is_valid, confidence_score, suggested_canonical_name)
        """
        if not neighborhood or not city:
            return (False, 0.0, None)

        canonical = cls.canonicalize(neighborhood, city)
        normalized = cls.normalize_text(canonical)

        # Check if city has known neighborhoods
        if city not in cls.CITY_NEIGHBORHOODS:
            # Unknown city - accept with medium confidence
            return (True, 0.6, canonical)

        city_data = cls.CITY_NEIGHBORHOODS[city]
        valid_neighborhoods = city_data['valid']

        # Exact match (normalized)
        for valid in valid_neighborhoods:
            if cls.normalize_text(valid) == normalized:
                return (True, 1.0, valid)

        # Fuzzy match with confidence scoring
        best_match = None
        best_score = 0.0

        for valid in valid_neighborhoods:
            score = cls.similarity_score(normalized, cls.normalize_text(valid))
            if score > best_score:
                best_score = score
                best_match = valid

        # Return validation based on threshold
        is_valid = best_score >= confidence_threshold
        return (is_valid, best_score, best_match if is_valid else None)

    @classmethod
    def deduplicate_neighborhoods(cls, neighborhoods: List[str], 
                                 city: Optional[str] = None) -> List[str]:
        """
        Remove duplicate neighborhoods using canonical forms

        Args:
            neighborhoods: List of neighborhood names (may have duplicates)
            city: Optional city context

        Returns:
            Deduplicated list with canonical names
        """
        seen = set()
        result = []

        for n in neighborhoods:
            canonical = cls.canonicalize(n, city)
            normalized = cls.normalize_text(canonical)

            if normalized not in seen:
                seen.add(normalized)
                result.append(canonical)

        return result

    @classmethod
    def rank_neighborhoods(cls, neighborhoods: List[Dict], city: str,
                          user_query: Optional[str] = None) -> List[Dict]:
        """
        Rank neighborhoods by relevance and confidence

        Args:
            neighborhoods: List of neighborhood dicts with 'name' key
            city: City context
            user_query: Optional user search query for relevance scoring

        Returns:
            Sorted list with confidence scores added
        """
        scored = []

        for n in neighborhoods:
            name = n.get('name') or n.get('display_name') or n.get('label', '')
            if not name:
                continue

            # Validate and get confidence
            is_valid, confidence, canonical = cls.validate_neighborhood(name, city)

            # Query relevance scoring
            query_score = 0.0
            if user_query:
                query_norm = cls.normalize_text(user_query)
                name_norm = cls.normalize_text(name)
                query_score = cls.similarity_score(query_norm, name_norm)

            # Combined score: 70% validation confidence + 30% query relevance
            combined_score = (confidence * 0.7) + (query_score * 0.3)

            scored.append({
                **n,
                'canonical_name': canonical or name,
                'confidence': confidence,
                'query_relevance': query_score,
                'combined_score': combined_score,
                'is_valid': is_valid
            })

        # Sort by combined score descending
        scored.sort(key=lambda x: x['combined_score'], reverse=True)
        return scored


# Test suite for problematic cases
def test_neighborhood_disambiguation():
    """Test suite for Las Conchas, La Perla, and other edge cases"""

    disamb = NeighborhoodDisambiguator()

    tests = [
        # Las Conchas variations
        {
            'input': 'las conchas',
            'city': 'Puerto Peñasco',
            'expected_canonical': 'Las Conchas',
            'expected_valid': True,
            'min_confidence': 0.9
        },
        {
            'input': 'LasConchas',
            'city': 'Puerto Peñasco',
            'expected_canonical': 'Las Conchas',
            'expected_valid': True,
            'min_confidence': 0.9
        },
        {
            'input': 'conchas',
            'city': 'Puerto Peñasco',
            'expected_canonical': 'Las Conchas',
            'expected_valid': True,
            'min_confidence': 0.9
        },

        # La Perla variations
        {
            'input': 'la perla',
            'city': 'San Juan',
            'expected_canonical': 'La Perla',
            'expected_valid': True,
            'min_confidence': 0.9
        },
        {
            'input': 'LaPerla',
            'city': 'San Juan',
            'expected_canonical': 'La Perla',
            'expected_valid': True,
            'min_confidence': 0.9
        },
        {
            'input': 'perla',
            'city': 'San Juan',
            'expected_canonical': 'La Perla',
            'expected_valid': True,
            'min_confidence': 0.9
        },

        # Rio neighborhoods with accents
        {
            'input': 'jardim botanico',
            'city': 'Rio de Janeiro',
            'expected_canonical': 'Jardim Botânico',
            'expected_valid': True,
            'min_confidence': 0.9
        },
        {
            'input': 'barra da tijuca',
            'city': 'Rio de Janeiro',
            'expected_canonical': 'Barra da Tijuca',
            'expected_valid': True,
            'min_confidence': 0.9
        },

        # Invalid neighborhood for city
        {
            'input': 'Las Conchas',
            'city': 'Rio de Janeiro',
            'expected_valid': False,
            'max_confidence': 0.7
        },

        # Fuzzy match
        {
            'input': 'Copacabanna',  # misspelled
            'city': 'Rio de Janeiro',
            'expected_canonical': 'Copacabana',
            'expected_valid': True,
            'min_confidence': 0.75
        }
    ]

    results = []
    passed = 0
    failed = 0

    for i, test in enumerate(tests, 1):
        input_name = test['input']
        city = test['city']

        # Test canonicalization
        canonical = disamb.canonicalize(input_name, city)

        # Test validation
        is_valid, confidence, suggested = disamb.validate_neighborhood(input_name, city)

        # Check expectations
        test_passed = True
        issues = []

        if 'expected_canonical' in test and canonical != test['expected_canonical']:
            test_passed = False
            issues.append(f"Expected canonical '{test['expected_canonical']}', got '{canonical}'")

        if 'expected_valid' in test and is_valid != test['expected_valid']:
            test_passed = False
            issues.append(f"Expected valid={test['expected_valid']}, got {is_valid}")

        if 'min_confidence' in test and confidence < test['min_confidence']:
            test_passed = False
            issues.append(f"Confidence {confidence:.2f} below minimum {test['min_confidence']}")

        if 'max_confidence' in test and confidence > test['max_confidence']:
            test_passed = False
            issues.append(f"Confidence {confidence:.2f} above maximum {test['max_confidence']}")

        if test_passed:
            passed += 1
            status = "✅ PASS"
        else:
            failed += 1
            status = "❌ FAIL"

        results.append({
            'test_num': i,
            'status': status,
            'input': input_name,
            'city': city,
            'canonical': canonical,
            'is_valid': is_valid,
            'confidence': f"{confidence:.2f}",
            'suggested': suggested,
            'issues': issues
        })

    # Print results
    print("=" * 80)
    print("NEIGHBORHOOD DISAMBIGUATION TEST RESULTS")
    print("=" * 80)
    print(f"\nTotal Tests: {len(tests)} | Passed: {passed} | Failed: {failed}\n")

    for r in results:
        print(f"\nTest #{r['test_num']}: {r['status']}")
        print(f"  Input: '{r['input']}' in {r['city']}")
        print(f"  Canonical: '{r['canonical']}'")
        print(f"  Valid: {r['is_valid']} | Confidence: {r['confidence']}")
        if r['suggested']:
            print(f"  Suggested: '{r['suggested']}'")
        if r['issues']:
            print(f"  Issues: {', '.join(r['issues'])}")

    print("\n" + "=" * 80)
    print(f"SUMMARY: {passed}/{len(tests)} tests passed ({100*passed//len(tests)}%)")
    print("=" * 80)

    return passed == len(tests)

# Run tests when executed directly
if __name__ == '__main__':
    ok = test_neighborhood_disambiguation()
    if not ok:
        raise SystemExit(1)
