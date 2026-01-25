import pytest
from city_guides.src.synthesis_enhancer import SynthesisEnhancer
import city_guides.src.app as app


def test_extract_image_attributions_strips_and_returns():
    txt = "Santa Tere is a neighborhood in Guadalajara. Visitors to Santa Tere can enjoy walking tours and explore the area on foot.\n\nImage via Wikimedia/Wikipedia (https://en.wikipedia.org/?curid=33197492)\nImage via Wikimedia/Wikipedia (https://en.wikipedia.org/?curid=33197492)"
    clean, atts = SynthesisEnhancer.extract_image_attributions(txt)
    assert 'Image via' not in clean
    assert 'Santa Tere' in clean
    assert isinstance(atts, list)
    assert len(atts) == 1
    assert atts[0]['url'] == 'https://en.wikipedia.org/?curid=33197492'


def test_is_relevant_wikimedia_image_filters_trophy():
    wik_img = {'remote_url': 'https://upload.wikimedia.org/wikipedia/commons/0/0a/John_Doe_trophy.jpg', 'page_title': 'John Doe holding the trophy'}
    assert not app._is_relevant_wikimedia_image(wik_img, 'Guadalajara, Mexico', 'Santa Tere')


def test_is_relevant_wikimedia_image_keeps_skyline():
    wik_img = {'remote_url': 'https://upload.wikimedia.org/wikipedia/commons/6/67/Guadalajara_Skyline.jpeg', 'page_title': 'Guadalajara skyline at dusk'}
    assert app._is_relevant_wikimedia_image(wik_img, 'Guadalajara, Mexico', 'Santa Tere')


def test_is_relevant_wikimedia_image_filters_performer():
    wik_img = {'remote_url': 'https://upload.wikimedia.org/wikipedia/commons/e/ee/Peso_Pluma_performing.png', 'page_title': 'Peso Pluma, performing in Monterrey (2024)'}
    assert not app._is_relevant_wikimedia_image(wik_img, 'Guadalajara, Mexico', 'Santa Tere')

