import sys
import os
import threading
import time
from playwright.sync_api import sync_playwright

# Ensure project root is on path so we can import mcp_server
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import os

# target URL and headless flag can be controlled via env vars
URL = os.getenv('TARGET_URL', 'http://127.0.0.1:5010')
HEADLESS = os.getenv('HEADLESS', 'true').lower() == 'true'


def start_mcp_server():
    """Start local mcp_server in a background thread."""
    from mcp_server import app

    def _run():
        app.run(host='127.0.0.1', port=8765, debug=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    # give it a moment to bind
    time.sleep(0.5)
    return t


def run():
    # Start MCP server for Playwright to query
    start_mcp_server()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        print('Opening', URL)
        page.goto(URL, timeout=15000)
        # reload to avoid stale template/static mismatch on dev server
        page.reload()
        page.wait_for_selector('#city', timeout=10000)
        # Ensure live POI is unchecked for a deterministic micro-search
        try:
            if page.is_checked('#usePoi'):
                page.uncheck('#usePoi')
        except Exception:
            pass
        page.fill('#city', 'NYC')
        page.fill('#q', '')

        # Example: call MCP list endpoint from page context
        try:
            tools = page.evaluate("() => fetch('http://127.0.0.1:8765/mcp/list').then(r=>r.json())")
            print('MCP tools announced:', tools.get('tools') and len(tools.get('tools')))
        except Exception:
            print('Could not fetch MCP list from page context; will proceed')

        # Click search and wait for results
        page.click('#searchBtn')
        # wait for either results count or an error (more generous timeout)
        try:
            page.wait_for_selector('#results .card, .error', timeout=30000)
        except Exception as ex:
            print('Timeout waiting for results; page snapshot below:')
            try:
                print(page.content()[:4000])
            except Exception:
                pass
            raise
        cards = page.query_selector_all('#results .card')
        print('Found cards:', len(cards))
        if cards:
            # print first card summary
            first = cards[0]
            title = first.query_selector('h3').inner_text() if first.query_selector('h3') else ''
            desc = first.query_selector('.full').inner_text() if first.query_selector('.full') else ''
            print('First:', title)
            if desc:
                print('Desc (snippet):', desc[:200])

        # Now demonstrate AI ingest
        print('Demonstrating AI ingest...')
        page.fill('#ingestUrls', 'https://en.wikipedia.org/wiki/New_York_City')
        page.click('#ingestBtn')
        # Wait for ingest to complete (status update)
        try:
            page.wait_for_function("document.getElementById('ingestStatus').innerText.includes('ingested') || document.getElementById('ingestStatus').innerText.includes('error')", timeout=30000)
            status = page.inner_text('#ingestStatus')
            print('Ingest status:', status)
        except Exception:
            print('Ingest timeout or no status update')

        # Now demonstrate semantic search via chat
        print('Demonstrating semantic search...')
        page.fill('#chatInput', 'best cheap restaurants in NYC')
        page.click('#chatSend')
        # Wait for chat response
        try:
            page.wait_for_selector('#chatMessages .message', timeout=30000)
            messages = page.query_selector_all('#chatMessages .message')
            print('Chat messages:', len(messages))
            if messages:
                last_msg = messages[-1].inner_text()
                print('Last chat message (snippet):', last_msg[:300])
        except Exception:
            print('Chat response timeout')

        browser.close()


if __name__ == '__main__':
    try:
        run()
    except Exception as e:
        print('Playwright run failed:', e, file=sys.stderr)
        sys.exit(2)
