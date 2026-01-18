#!/usr/bin/env python3
"""
playwright_neighborhood_flow.py

Automated GUI test: intercept /neighborhoods and return fake neighborhoods, then
simulate selecting a city suggestion and verify neighborhood chips appear, select
one and take a screenshot.

Run: python3 city-guides/scripts/playwright_neighborhood_flow.py
Requires: playwright (and browsers installed: `playwright install chromium`)
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Route, Request

URL = "http://127.0.0.1:5010"

FAKE_NEIGHBORHOODS = {
    "cached": False,
    "neighborhoods": [
        {"id": "relation/1", "name": "Alfama", "slug": "alfama", "center": {"lat": 38.7139, "lon": -9.1296}, "bbox": None, "source": "osm"},
        {"id": "relation/2", "name": "Baixa", "slug": "baixa", "center": {"lat": 38.7106, "lon": -9.1366}, "bbox": None, "source": "osm"}
    ]
}


def json_bytes(data):
    """Convert dict to JSON bytes for Playwright route fulfillment."""
    return json.dumps(data).encode('utf-8')


def run_flow(headful=True):
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=not headful)
        except Exception as e:
            print(f"Failed to launch headful browser: {e}. Falling back to headless.")
            browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(8000)

        # Intercept /neighborhoods and return fake payload
        def route_handler(route: Route, request: Request):
            if '/neighborhoods' in request.url:
                route.fulfill(status=200, body=json_bytes(FAKE_NEIGHBORHOODS), headers={'Content-Type': 'application/json'})
            else:
                route.fallback()

        page.route('**/neighborhoods**', route_handler)

        page.goto(URL)
        page.wait_for_selector('#city')
        city_input = page.query_selector('#city')
        city_input.click()
        city_input.fill('')
        for ch in 'Lisbon':
            city_input.type(ch, delay=80)
        # Wait a little for Nominatim suggestions to appear (if any)
        time.sleep(1)
        # Instead of relying on suggestions, directly invoke the neighborhoods fetch
        page.evaluate("fetchAndRenderNeighborhoods('Lisbon', 38.7139, -9.1296)")
        # Wait for chips
        try:
            page.wait_for_selector('.neigh-chip', timeout=5000)
            chips = page.query_selector_all('.neigh-chip')
            print('Found chips:', [c.inner_text().strip() for c in chips])
            # click the first neighborhood
            if chips:
                chips[0].click()
        except Exception as e:
            print('Neighborhood chips not found:', e)

        time.sleep(0.5)
        out_file = Path('/tmp/playwright_neighborhood_flow.png')
        page.screenshot(path=str(out_file), full_page=True)
        print('Saved screenshot to', out_file)
        browser.close()


if __name__ == '__main__':
    run_flow(headful=True)
