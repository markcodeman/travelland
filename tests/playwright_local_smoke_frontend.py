from playwright.sync_api import sync_playwright
import sys

URL = 'http://127.0.0.1:5174'

def run_check():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(URL, timeout=15000)
        except Exception as e:
            print('Failed to open frontend URL:', e)
            browser.close()
            return 2

        # wait for weather display to render or for the hero area to appear
        try:
            page.wait_for_selector('.weather-display, .hero', timeout=8000)
        except Exception:
            print('Weather UI did not appear in time')
            browser.close()
            return 3

        # check for explicit error text
        try:
            err = page.query_selector("text=Unable to determine coordinates")
            if err:
                print('Found weather error text on page:', err.inner_text())
                browser.close()
                return 4
        except Exception:
            # ignore selector errors
            pass

        # check that we have a temperature shown (approximate check: degree symbol)
        try:
            temp = page.query_selector('.weather-temp')
            if temp:
                txt = temp.inner_text().strip()
                print('Weather temp text:', txt)
                browser.close()
                return 0
            else:
                print('No .weather-temp element found')
                browser.close()
                return 5
        except Exception as e:
            print('Error reading weather element:', e)
            browser.close()
            return 6

if __name__ == '__main__':
    rc = run_check()
    sys.exit(rc)
