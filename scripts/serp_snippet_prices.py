#!/usr/bin/env python3
"""Quick SERP-snippet price extractor (fast, lower-quality).

Uses the existing `combined_search` / `duckduckgo_search` from
`search_provider` to fetch web results, parses titles+snippets for price
mentions using `_parse_price_from_text`, and prints per-result matches and
an aggregated summary (min/max/count per currency).

This is intentionally lightweight and fast — it only inspects SERP titles
and snippets (no page visits).
"""
import argparse
import json
import os
import sys
from statistics import mean
from typing import List, Dict, Any

# Ensure project root is on sys.path so we can import local modules when running
# this script from the scripts/ directory.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from search_provider import combined_search, _parse_price_from_text


def extract_from_results(results: List[Dict[str, Any]]):
    hits = []
    for r in results:
        title = (r.get('title') or '')
        snippet = (r.get('snippet') or '')
        url = r.get('url') or r.get('website') or ''
        text = ' '.join([title, snippet])
        amt, cur = _parse_price_from_text(text)
        entry = {
            'title': title,
            'url': url,
            'snippet': snippet,
            'parsed_amount': None,
            'currency': None,
        }
        if amt is not None:
            entry['parsed_amount'] = round(amt, 2)
            entry['currency'] = (cur or 'USD')
        hits.append(entry)
    return hits


def aggregate(hits: List[Dict[str, Any]]):
    by_currency = {}
    for h in hits:
        if h['parsed_amount'] is None:
            continue
        cur = h['currency']
        val = h['parsed_amount']
        s = by_currency.setdefault(cur, {'values': [], 'count': 0})
        s['values'].append(val)
        s['count'] += 1
    summary = {}
    for cur, data in by_currency.items():
        vals = data['values']
        summary[cur] = {
            'count': data['count'],
            'min': round(min(vals), 2),
            'max': round(max(vals), 2),
            'mean': round(mean(vals), 2),
            'sample_values': sorted(vals)[:10]
        }
    return summary


def main():
    p = argparse.ArgumentParser(description='SERP snippet price extractor')
    p.add_argument('--query', '-q', required=True, help='Search query')
    p.add_argument('--city', '-c', default=None, help='Optional city name to favor OSM results')
    p.add_argument('--max', type=int, default=10, help='Max results to fetch')
    args = p.parse_args()

    results = combined_search(args.query, city=args.city, max_results=args.max)
    hits = extract_from_results(results)
    summary = aggregate(hits)

    out = {
        'query': args.query,
        'city': args.city,
        'fetched_results': len(results),
        'parsed_hits': [h for h in hits if h['parsed_amount'] is not None],
        'summary': summary,
    }
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
