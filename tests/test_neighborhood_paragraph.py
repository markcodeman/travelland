import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from city_guides.src.synthesis_enhancer import SynthesisEnhancer


def test_generate_neighborhood_paragraph_basic():
    p = SynthesisEnhancer.generate_neighborhood_paragraph('Las Nueve Esquinas', 'Tlaquepaque')
    assert 'Las Nueve Esquinas' in p
    assert 'Tlaquepaque' in p
    assert 'try searching' not in p
    assert 'known locally for its character' not in p


def test_generate_neighborhood_paragraph_with_features():
    p = SynthesisEnhancer.generate_neighborhood_paragraph('Analco', 'Guadalajara', features=['historic center', 'craft breweries', 'walking tours'])
    assert 'historic center' in p or 'craft breweries' in p
    assert 'Analco' in p
