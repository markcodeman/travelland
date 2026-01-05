from playwright.sync_api import sync_playwright
import time

URL = 'http://127.0.0.1:5010'

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=15000)
        # Wait for UI to initialize
        time.sleep(1)
        # Ensure the search UI is visible (some builds hide it in a collapsible)
        try:
            page.evaluate("() => { const s = document.querySelector('.wrap.hidden'); if (s) s.classList.remove('hidden'); }")
            print('Unhid search UI')
        except Exception as e:
            print('Could not unhide search UI:', e)

        page.fill('#city', 'Guadalajara')
        page.click('#searchBtn')
        # Wait briefly, then inspect DOM directly for debug
        page.wait_for_timeout(500)
        try:
            count = page.evaluate("() => document.querySelectorAll('.card').length")
            print('DOM .card count (direct):', count)
            if count == 0:
                # dump raw results container to debug
                html = page.evaluate("() => document.querySelector('#results').innerHTML")
                print('results HTML preview:', html[:500])
            page.wait_for_selector('.card', timeout=10000)
            venues = page.query_selector_all('.card')
            print(f'Found {len(venues)} venue(s)')
            for i, v in enumerate(venues[:10]):
                print(f"{i+1}: {v.inner_text()[:120].replace('\n', ' ')}")
        except Exception as e:
            # If search failed, dump any error node
            err = page.query_selector('.error')
            if err:
                print('Error message on page:', err.inner_text())
            else:
                print('No results and no explicit error:', str(e))
        # Also test Marco chat quick query
        page.fill('#chatCity', 'Guadalajara')
        page.fill('#chatInput', 'best tacos')
        page.click('#chatSend')
        # Wait for AI reply
        try:
            page.wait_for_selector('.chat-messages .message.ai', timeout=20000)
            msgs = page.query_selector_all('.chat-messages .message.ai')
            print('AI replies:', msgs[-1].inner_text())
        except Exception as e:
            print('No AI reply:', str(e))
        browser.close()

if __name__ == '__main__':
    run()
