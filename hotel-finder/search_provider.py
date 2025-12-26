import requests
import os
import re
import time
import random
from datetime import datetime

# Simple searxng-based search provider prototype
# Configure instances via SEARX_INSTANCES environment variable (comma-separated)
DEFAULT_INSTANCES = [
    # A broader default list of public searxng instances (may vary in availability)
    'https://searx.tiekoetter.com',
    'https://searx.org',
    'https://searx.be',
    'https://searx.space',
    'https://searx.eu',
    'https://searx.ng',
    'https://searx.fandom.com',
    'https://searx.science',
    'https://searx.sethforprivacy.com',
    'https://searx.fdf.org',
    'https://searx.disroot.org',
    'https://searx.kitsune.dev',
]

PRICE_RE = re.compile(r'(?:(?:\$|€|£|¥)\s?[0-9,]+(?:\.[0-9]+)?)|(?:[0-9,]+(?:\.[0-9]+)?\s?(?:USD|EUR|GBP|JPY))', re.IGNORECASE)

# Additional permissive numeric regex (captures numbers like '120/night', 'from 120', 'from $120')
NUM_RE = re.compile(r'(?:from\s*)?(?:\$|USD)?\s?([0-9]{1,3}(?:[0-9,]*)(?:\.[0-9]+)?)(?:\s*(?:/night|per night|a night|night))?', re.IGNORECASE)

def _get_instances_from_env():
    env = os.getenv('SEARX_INSTANCES')
    if not env:
        return DEFAULT_INSTANCES
    return [u.strip() for u in env.split(',') if u.strip()]

def _parse_price_from_text(text):
    if not text:
        return None, None
    # 1) Try exact currency symbol/code matches
    m = PRICE_RE.search(text)
    if m:
        s = m.group(0)
        # find amount and currency within the matched substring
        # e.g. '$120.50' or '120 USD'
        digits = re.search(r'([0-9,]+(?:\.[0-9]+)?)', s)
        code = re.search(r'(USD|EUR|GBP|JPY|\$|€|£|¥)', s, re.IGNORECASE)
        if digits:
            amt = float(digits.group(1).replace(',', ''))
            sym = code.group(0) if code else ''
            sym_map = {'$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY'}
            cur = sym_map.get(sym.upper(), sym.upper()) if sym else 'USD'
            # normalize codes like '$' -> USD
            if cur in ['$', '€', '£', '¥']:
                cur = sym_map.get(cur, 'USD')
            return amt, cur.upper()

    # 2) Try permissive numeric patterns (e.g., 'from 120', '120/night', 'per night 120 USD')
    m2 = NUM_RE.search(text)
    if m2:
        try:
            amt = float(m2.group(1).replace(',', ''))
            # attempt to pick currency code elsewhere in text
            code_search = re.search(r'(USD|EUR|GBP|JPY)', text, re.IGNORECASE)
            cur = code_search.group(1).upper() if code_search else 'USD'
            return amt, cur
        except Exception:
            return None, None

    # 3) fallback: look for reversed order like '120 USD'
    m3 = re.search(r'([0-9,]+(?:\.[0-9]+)?)\s?(USD|EUR|GBP|JPY)', text, re.IGNORECASE)
    if m3:
        amt = float(m3.group(1).replace(',', ''))
        cur = m3.group(2).upper()
        return amt, cur

    return None, None

def searx_search_hotels(city_code, check_in, check_out, adults=1, max_results=100):
    """Query multiple public searxng instances and return normalized hotel offers.

    This is a best-effort scraper of SERP snippets and is intended for prototyping only.
    """
    instances = _get_instances_from_env()
    query = f"hotel {city_code} checkin {check_in} checkout {check_out} adults {adults}"
    offers = []

    # compute nights
    try:
        nights = max(1, (datetime.strptime(check_out, '%Y-%m-%d') - datetime.strptime(check_in, '%Y-%m-%d')).days)
    except Exception:
        nights = 1

    seen = set()
    session = requests.Session()
    # Friendly headers to reduce blocks
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    }

    # Try a few query variants to surface price snippets from different sites
    query_variants = [
        query,
        query + ' price',
        f'hotel {city_code} price per night',
        query + ' booking.com',
        query + ' expedia',
    ]

    for inst in instances:
        try:
            url = inst.rstrip('/') + '/search'
            # try multiple query patterns per instance
            for q in query_variants:
                params = {'q': q, 'format': 'json'}
                # basic retry/backoff per-instance
                resp = None
                for attempt in range(3):
                    try:
                        resp = session.get(url, params=params, headers=headers, timeout=8)
                        if resp.status_code == 200:
                            break
                        if resp.status_code in (403, 429):
                            break
                    except requests.exceptions.RequestException:
                        time.sleep((2 ** attempt) + random.random())
                        continue
                if not resp or resp.status_code != 200:
                    # try next query variant
                    continue
                j = resp.json()
                results = j.get('results') or []
                # proceed to process results for this query
                for r in results:
                    title = r.get('title') or ''
                    link = r.get('url') or r.get('id') or ''
                    snippet = r.get('content') or r.get('snippet') or ''

                    key = (link or title).strip()
                    if not key or key in seen:
                        continue
                    seen.add(key)
            # basic retry/backoff per-instance
            resp = None
            for attempt in range(3):
                try:
                    resp = session.get(url, params=params, headers=headers, timeout=8)
                    if resp.status_code == 200:
                        break
                    # if rate limited or forbidden, break early for this instance
                    if resp.status_code in (403, 429):
                        break
                except requests.exceptions.RequestException:
                    # exponential backoff with jitter
                    time.sleep((2 ** attempt) + random.random())
                    continue
            if not resp or resp.status_code != 200:
                continue
                # if we got here, we already processed results for this successful query variant
                for r in results:
                    title = r.get('title') or ''
                    link = r.get('url') or r.get('id') or ''
                    snippet = r.get('content') or r.get('snippet') or ''

                    key = (link or title).strip()
                    if not key or key in seen:
                        continue
                    seen.add(key)

                    amt, cur = _parse_price_from_text(snippet + ' ' + title)

                    if amt is None:
                        # skip entries without a parsed price for now
                        continue

                    total_price = round(amt, 2)
                    hotelspec = {
                        'name': title or 'Hotel',
                        'hotel_id': None,
                        'base_price': round((total_price) / nights, 2),
                        'taxes': 0.0,
                        'total_price': total_price,
                        'nights': nights,
                        'total_per_night': round(total_price / nights, 2),
                        'currency': cur or 'USD',
                        'room_type': None,
                        'description': snippet or title,
                        'check_in': check_in,
                        'check_out': check_out,
                        'cancellation': 'Unknown',
                        'breakfast_included': False,
                        'source': link,
                        'provider': inst,
                    }
                    offers.append(hotelspec)
                    if len(offers) >= max_results:
                        break
        except Exception:
            continue
        if len(offers) >= max_results:
            break

    # sort cheapest first
    offers.sort(key=lambda x: x['total_price'])
    return {'hotels': offers, 'count': len(offers)}


def searx_raw_queries(city_code, check_in, check_out, adults=1, max_instances=5):
    """Return raw JSON responses from each searx instance for debugging."""
    instances = _get_instances_from_env()[:max_instances]
    query = f"hotel {city_code} checkin {check_in} checkout {check_out} adults {adults}"
    raw = []
    for inst in instances:
        try:
            url = inst.rstrip('/') + '/search'
            params = {'q': query, 'format': 'json'}
            resp = requests.get(url, params=params, timeout=8)
            entry = {
                'instance': inst,
                'status_code': resp.status_code,
                'json': None
            }
            try:
                entry['json'] = resp.json()
            except Exception:
                entry['json'] = None
            raw.append(entry)
        except Exception as e:
            raw.append({'instance': inst, 'status_code': None, 'error': str(e)})
    return raw
