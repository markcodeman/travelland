import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from city_guides.src.snippet_filters import looks_like_ddgs_disambiguation_text as _looks_like_ddgs_disambiguation_text


def test_ddgs_disambiguation_phrases():
    assert _looks_like_ddgs_disambiguation_text('Revolución may refer to several things, including...')
    assert _looks_like_ddgs_disambiguation_text('The Spanish word for revolution, Revolución, may refer to...')
    assert _looks_like_ddgs_disambiguation_text('Watch this video on youtube.com about Revolución')
    assert _looks_like_ddgs_disambiguation_text('Rating 5.0 (8) Reviews, Attractions, Restaurants')
    assert _looks_like_ddgs_disambiguation_text('Missing: Revolucion, | Show results with: Revolucion')
    assert not _looks_like_ddgs_disambiguation_text('Visitors to Revolución enjoy walking tours and historic sites')
