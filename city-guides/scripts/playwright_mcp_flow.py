#!/usr/bin/env python3
"""
playwright_mcp_flow.py

Automated GUI test: open the app, type 'Bangkok' into the predictive city field,
select the suggestion, open the hamburger menu and click the Currency link.
Saves a screenshot to /tmp/playwright_mcp_flow.png and prints final URL and page title.

Run: python3 city-guides/scripts/playwright_mcp_flow.py

If browsers are not installed, run: playwright install chromium
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError

URL = 'http://127.0.0.1:5000'

def run_flow(headful=True):
    with sync_playwright() as pw:
        browser = None
        try:
            browser = pw.chromium.launch(headless=not headful)
        except Exception as e:
            print(f"Failed to launch headful browser: {e}. Falling back to headless.")
            browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(8000)
        page.goto(URL)
        # wait for city input
        page.wait_for_selector('#city')
        city_input = page.query_selector('#city')
        city_input.click()
        # Type Bangkok slowly to trigger predictive
        page.fill('#city', '')
        for ch in 'Bangkok':
            city_input.type(ch, delay=120)
        # wait for suggestions
        try:
            page.wait_for_selector('.suggestion-item', timeout=5000)
            suggestions = page.query_selector_all('.suggestion-item')
            chosen = None
            for s in suggestions:
                txt = s.inner_text().strip()
                if 'Bangkok' in txt or 'Krung Thep' in txt:
                    chosen = s
                    break
            if not chosen and suggestions:
                chosen = suggestions[0]
            if chosen:
                chosen.click()
            else:
                print('No suggestion element found to click')
        except TimeoutError:
            print('Timed out waiting for suggestions')

        time.sleep(0.5)
        # Open hamburger and click currency link
        page.click('#hamburgerBtn')
        page.wait_for_selector('#hamburgerMenu')
        # currency link may include query param now
        href_sel = '#hamburgerMenu a[href*="/tools/currency"]'
        page.wait_for_selector(href_sel)
        page.click(href_sel)
        # wait for navigation
        try:
            page.wait_for_load_state('networkidle', timeout=7000)
        except Exception:
            pass
        out_file = Path('/tmp/playwright_mcp_flow.png')
        page.screenshot(path=str(out_file), full_page=True)
        print('Final URL:', page.url)
        print('Title:', page.title())
        browser.close()

if __name__ == '__main__':
    run_flow(headful=True)
