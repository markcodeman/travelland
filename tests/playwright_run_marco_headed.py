#!/usr/bin/env python3
"""Run a headed Playwright flow that opens the frontend, selects a city/neighborhood,
opens the Marco chat modal, sends a sample query, and captures the assistant reply.

Saves a screenshot to /tmp/marco_headed.png and prints the assistant response text.
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError

FRONTEND_URL = "http://localhost:5174"


def run(headful=True, city_name="San Francisco", query="best coffee nearby"):
    out_file = Path("/tmp/marco_headed.png")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headful)
        page = browser.new_page()
        page.set_default_timeout(10000)
        print(f"Opening {FRONTEND_URL} ...")
        page.goto(FRONTEND_URL)

        # Wait for city input and type city
        try:
            page.wait_for_selector('#city', timeout=8000)
            city_input = page.query_selector('#city')
            city_input.click()
            page.fill('#city', '')
            for ch in city_name:
                city_input.type(ch, delay=80)
            # wait for suggestion items
            page.wait_for_selector('.suggestion-item', timeout=5000)
            suggestions = page.query_selector_all('.suggestion-item')
            if suggestions:
                suggestions[0].click()
            else:
                city_input.press('Enter')
        except TimeoutError:
            print('City input or suggestions not found; continuing...')

        time.sleep(0.8)
        # Try to pick a neighborhood if available
        try:
            if page.query_selector('#neighborhood'):
                nb = page.query_selector('#neighborhood')
                nb.click()
                # pick first suggestion if present
                page.wait_for_timeout(400)
                sels = page.query_selector_all('.suggestion-item')
                if sels and len(sels) > 0:
                    sels[0].click()
        except Exception:
            pass

        time.sleep(0.5)
        # Click Explore with Marco button
        try:
            # button text contains 'Explore with Marco'
            page.click('text="Explore with Marco"')
        except Exception:
            # fallback: click any button that opens Marco (aria/emoji)
            try:
                page.click('button:has-text("Marco")')
            except Exception:
                print('Could not open Marco modal')

        # Wait for modal and send a query
        try:
            page.wait_for_selector('.marco-modal', timeout=5000)
            # fill input and send
            page.fill('.marco-input input', query)
            page.click('.marco-input button')
            # wait for assistant reply to appear
            page.wait_for_selector('.marco-msg.assistant', timeout=10000)
            # get last assistant message
            msgs = page.query_selector_all('.marco-msg.assistant')
            last = msgs[-1].inner_text() if msgs else ''
            # screenshot
            page.screenshot(path=str(out_file), full_page=True)
            print('Assistant reply:')
            print(last[:1000])
        except TimeoutError:
            print('Timed out while waiting for Marco reply')

        browser.close()


if __name__ == '__main__':
    run(headful=True)
