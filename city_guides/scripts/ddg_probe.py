#!/usr/bin/env python3
"""Simple DuckDuckGo SERP probe

Usage:
  python scripts/ddg_probe.py "london burgers" --count 10

Installs:
  pip install duckduckgo_search

Returns JSON array of results with title, snippet, href.
"""
import sys
import json
import argparse
import requests


def search(query, count=10):
    results = []
    # Try duckduckgo_search (or ddgs) first, fall back to Instant Answer API on error
    DDGS_cls = None
    try:
        from duckduckgo_search import DDGS as DDGS_cls
    except Exception:
        try:
            from ddgs import DDGS as DDGS_cls
        except Exception:
            DDGS_cls = None

    if DDGS_cls:
        try:
            with DDGS_cls() as ddgs:
                for r in ddgs.text(query, timelimit=5):
                    results.append({
                        'title': r.get('title'),
                        'snippet': r.get('body') or r.get('snippet'),
                        'href': r.get('href') or r.get('url')
                    })
                    if len(results) >= count:
                        break
            # If we got hits, return them; otherwise fall through to try alternative APIs
            if results:
                return results
        except Exception:
            # fallthrough to instant-answer API
            pass
    # If DDGS returned nothing, try the simpler ddg() helper which sometimes works
    if not results:
        try:
            from duckduckgo_search import ddg
            ddg_hits = ddg(query, max_results=count)
            for r in ddg_hits:
                results.append({
                    'title': r.get('title'),
                    'snippet': r.get('body') or r.get('snippet') or r.get('text'),
                    'href': r.get('href') or r.get('url')
                })
            if results:
                return results
        except Exception:
            pass
    # Final fallback: fetch DuckDuckGo's lightweight HTML results and parse with BeautifulSoup
    if not results:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}
            resp = requests.post('https://html.duckduckgo.com/html/', data={'q': query}, headers=headers, timeout=8)
            if resp.status_code == 200 and resp.text:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                for div in soup.select('div.result'):
                    a = div.select_one('a.result__a')
                    if not a:
                        # try older selector
                        a = div.find('a')
                    title = a.get_text(strip=True) if a else ''
                    href = a.get('href') if a else ''
                    snippet_el = div.select_one('.result__snippet') or div.select_one('.snippet')
                    snippet = snippet_el.get_text(' ', strip=True) if snippet_el else ''
                    if href:
                        results.append({'title': title, 'url': href, 'snippet': snippet})
                    if len(results) >= count:
                        break
            if results:
                return results
        except Exception:
            pass
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('query', help='Search query')
    parser.add_argument('--count', type=int, default=10)
    args = parser.parse_args()
    out = search(args.query, args.count)
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
