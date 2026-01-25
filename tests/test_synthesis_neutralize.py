import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from city_guides.src.synthesis_enhancer import SynthesisEnhancer


def test_neutralize_analco_sample():
    sample = "I embarked on the Barrio de Analco Walking Tour. With history and craft beer on the agenda, I was in for an unforgettable experience."
    neutral = SynthesisEnhancer.neutralize_tone(sample, neighborhood='Analco', city='Guadalajara')
    # Should not contain first-person pronouns 'I' or 'We' and should mention neighborhood
    assert 'I ' not in neutral and 'We ' not in neutral
    assert 'Analco' in neutral
