import re


def looks_like_ddgs_disambiguation_text(txt: str) -> bool:
    """Return True if DDGS/web snippet looks like a disambiguation/definition or promotional listing.
    Heuristics include:
      - contains 'may refer to', 'may also refer to', 'the Spanish word for', 'is the name of', 'is a surname', 'disambiguation'
      - contains explicit site markers like 'youtube.com', 'watch', 'video', 'tripadvisor', 'reviews' that are likely not concise neighborhood summaries
      - very short text with many commas or 'rating X' phrases
      - architectural, art history, or definition topics that aren't neighborhood-specific
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
    
    # Filter out architectural, art history, and definition topics
    irrelevant_topics = [
        'architecture', 'architectural style', 'gothic architecture', 'gothic style',
        'art period', 'art movement', 'historical period', 'medieval',
        'definition', 'meaning of', 'what is', 'etymology', 'origin of the word',
        'clothing brand', 'snack brand', 'food product', 'company', 'manufacturer',
        'music genre', 'literary genre', 'film genre', 'book', 'novel', 'movie'
    ]
    if any(topic in low for topic in irrelevant_topics):
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


# --- DDGS domain blocklist helpers ---
from urllib.parse import urlparse


def _get_domain(href: str) -> str:
    """Return normalized domain for an href (lowercased, no port)."""
    if not href:
        return ''
    try:
        p = urlparse(href)
        host = (p.netloc or href).lower()
        # strip port
        if ':' in host:
            host = host.split(':', 1)[0]
        return host
    except Exception:
        return href.lower()


def is_blocked_ddgs_domain(href: str, blocked_domains: list) -> bool:
    """Return True if href belongs to one of the blocked domains.
    blocked_domains can be like ['tripsavvy.com','tripadvisor.com'] and subdomains are matched as well.
    """
    if not href:
        return False
    domain = _get_domain(href)
    for b in (blocked_domains or []):
        b = b.strip().lower()
        if not b:
            continue
        if domain == b or domain.endswith('.' + b):
            return True
    return False


def filter_ddgs_results(results: list, blocked_domains: list) -> tuple:
    """Filter a list of ddgs result dicts into (allowed, blocked).
    Each result is expected to have a 'href' or 'url' field.
    """
    allowed = []
    blocked = []
    for r in results:
        href = r.get('href') or r.get('url') or ''
        if is_blocked_ddgs_domain(href, blocked_domains):
            blocked.append(r)
        else:
            allowed.append(r)
    return allowed, blocked
    if low.count(',') >= 3 and len(low) < 200:
        parts = [p.strip() for p in low.split(',')]
        short_parts = [p for p in parts if len(p) < 80]
        if len(short_parts) >= 3:
            return True
    if 'rating' in low and any(c.isdigit() for c in low):
        return True
    return False
