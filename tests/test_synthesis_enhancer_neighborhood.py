import os
import sys
# Ensure project root is on path for imports when running tests directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from city_guides.src.synthesis_enhancer import SynthesisEnhancer


def test_ensure_includes_term_inserts_neighborhood():
    orig = (
        "Las Conchas is a small neighborhood in Tlaquepaque. "
        "We start in San Pedro Tlaquepaque, a typical and picturesque town, "
        "you will get to know its tourist area and the largest cantina in Mexico 'El Parían'"
    )
    initial = "We start in San Pedro Tlaquepaque, a typical and picturesque town, you will get to know its tourist area and the largest cantina in Mexico 'El Parían'"
    enriched = SynthesisEnhancer.ensure_includes_term(initial, orig, 'Las Conchas', fallback_sentence='Las Conchas is a neighborhood in Tlaquepaque.', max_length=200)
    assert 'Las Conchas' in enriched
