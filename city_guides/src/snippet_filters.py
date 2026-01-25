import re


def looks_like_ddgs_disambiguation_text(txt: str) -> bool:
    """Return True if DDGS/web snippet looks like a disambiguation/definition or promotional listing.
    Heuristics include:
      - contains 'may refer to', 'may also refer to', 'the Spanish word for', 'is the name of', 'is a surname', 'disambiguation'
      - contains explicit site markers like 'youtube.com', 'watch', 'video', 'tripadvisor', 'reviews' that are likely not concise neighborhood summaries
      - very short text with many commas or 'rating X' phrases
    """
    if not txt:
        return False
    low = txt.lower()
    bad_phrases = [
        'may refer to', 'may also refer', 'the spanish word for', 'is the name of', 'is a surname', 'disambiguation', 'may be',
        'may also be', 'may denote', 'may refer', 'see also'
    ]
    if any(p in low for p in bad_phrases):
        return True
    # Additional noisy patterns (UI fragments, 'Missing:', 'Show results')
    ui_noise = ['missing:', 'show results', 'show results with', 'looking to visit', 'top tips for', 'top tips', 'watch this video']
    if any(u in low for u in ui_noise):
        return True
    # Site-specific promotional markers or video markers
    if 'youtube.com' in low or ('watch' in low and 'video' in low) or 'tripadvisor' in low or 'reviews' in low:
        return True
    # Short listings with many commas (likely lists) or 'rating X' phrases
    if low.count(',') >= 3 and len(low) < 200:
        parts = [p.strip() for p in low.split(',')]
        short_parts = [p for p in parts if len(p) < 80]
        if len(short_parts) >= 3:
            return True
    if 'rating' in low and any(c.isdigit() for c in low):
        return True
    return False
