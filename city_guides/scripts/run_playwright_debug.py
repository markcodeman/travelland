from playwright.sync_api import sync_playwright
import requests
import json
import os
import time

OUT_DIR = os.path.join(os.path.dirname(__file__), "../tmp/playwright_debug")
OUT_DIR = os.path.abspath(OUT_DIR)
os.makedirs(OUT_DIR, exist_ok=True)

console_messages = []
network_events = []

url = "http://127.0.0.1:5010/"

with sync_playwright() as p:
    # Run headless in this environment; slow_mo kept small to make traces easier to follow
    # Try launching Chromium with no-sandbox flags (helps in some CI/container setups)
    browser = p.chromium.launch(headless=True, slow_mo=50, args=["--no-sandbox", "--disable-setuid-sandbox"]) 
    context = browser.new_context(viewport={"width":1280, "height":800})
    page = context.new_page()

    def on_console(msg):
        console_messages.append({
            'type': msg.type,
            'text': msg.text,
            'location': msg.location
        })

    def on_request(request):
        network_events.append({
            'event': 'request',
            'url': request.url,
            'method': request.method,
            'post_data': request.post_data
        })

    def on_response(response):
        try:
            body = None
            if response.request.resource_type == 'xhr' or '/search' in response.url:
                try:
                    body = response.json()
                except Exception:
                    try:
                        body = response.text()
                    except Exception:
                        body = '<non-json body>'
        except Exception:
            body = None
        network_events.append({
            'event': 'response',
            'url': response.url,
            'status': response.status,
            'body': body
        })

    page.on("console", on_console)
    page.on("request", on_request)
    page.on("response", on_response)

    print(f"Checking server URL from Python: {url}")
    try:
        r = requests.get(url, timeout=5)
        print('HTTP check status:', r.status_code)
    except Exception as e:
        print('HTTP check failed:', e)

    print(f"Opening in browser: {url}")
    page.goto(url, wait_until='networkidle')
    time.sleep(0.5)

    # Try clicking the Blackfriars neighborhood, Top food category, then Search
    selectors = [
        "text=Blackfriars",
        "text=Top food",
        "text=Search",
        "role=button[name=Search]",
        "#search-button",
    ]

    def click_first_match(sel_list):
        for s in sel_list:
            try:
                el = page.locator(s)
                if el.count() > 0:
                    el.first.click()
                    print(f"Clicked selector: {s}")
                    return True
            except Exception:
                # ignore and continue
                pass
        return False

    # Attempt to select neighborhood by clicking visible text
    clicked = click_first_match(["text=Blackfriars", "text=Blackfriars (London)", "#neighborhoods"]) 
    time.sleep(0.3)
    # Click category
    click_first_match(["text=Top food", "text=Top Food", "text=Food"])
    time.sleep(0.3)
    # Click search
    if not click_first_match(["text=Search", "role=button[name=Search]", "#search-button"]):
        # fallback: press Enter
        page.keyboard.press("Enter")

    # Ensure a /search request is triggered. If UI clicks didn't trigger it, call performSearch() in-page.
    # Then poll captured network_events for a /search response (POST to /search) and collect its body.
    json_body = None

    # If we haven't observed any /search activity yet, attempt an in-page performSearch()
    def saw_search_response(events):
        for ev in events:
            try:
                if ev.get('event') == 'response' and '/search' in ev.get('url', ''):
                    return ev
            except Exception:
                pass
        return None

    # Give UI a brief moment to react to clicks
    time.sleep(0.5)

    # If no search response observed, try invoking performSearch() in-page
    if not saw_search_response(network_events):
        try:
            page.evaluate("""
                try {
                    // Ensure city and category inputs are set so performSearch() runs
                    const cityEl = document.getElementById('city');
                    if (cityEl && !cityEl.value) cityEl.value = 'London';
                    // assign to the lexical globals used by the page script
                    try { selectedCategory = 'restaurant'; } catch(e) { window.selectedCategory = 'restaurant'; }
                    const qEl = document.getElementById('query'); if (qEl) qEl.value = 'restaurant';
                    try { selectedNeighborhood = 'all'; } catch(e) { window.selectedNeighborhood = 'all'; }
                    if (typeof performSearch === 'function') performSearch();
                } catch (e) { console.warn('playwright-trigger performSearch failed', e); }
            """)
        except Exception:
            pass

    # Poll for up to 30s for a /search response to appear in network_events
    deadline = time.time() + 30.0
    found = None
    while time.time() < deadline:
        found = saw_search_response(network_events)
        if found:
            json_body = found.get('body')
            break
        time.sleep(0.2)

    if not found:
        # If we saw the /search request but not the response (browser fetch may not have been captured),
        # replay the same POST from Python to capture the server response.
        req_ev = None
        for ev in network_events:
            try:
                if ev.get('event') == 'request' and '/search' in ev.get('url', '') and ev.get('method') == 'POST':
                    req_ev = ev
                    break
            except Exception:
                pass

        if req_ev and req_ev.get('post_data'):
            try:
                # attempt to POST the same payload to the server and capture the JSON response
                r = requests.post(req_ev['url'], headers={'Content-Type': 'application/json'}, data=req_ev['post_data'], timeout=30)
                try:
                    json_body = r.json()
                except Exception:
                    json_body = {'error': 'response not json', 'text': r.text}
            except Exception as e:
                json_body = {'error': 'failed to replay /search request from Python', 'exception': str(e)}
        else:
            json_body = {'error': 'no /search response detected', 'exception': 'timed out waiting for /search in network events', 'network_events_count': len(network_events)}

    # Always write outputs even if something failed
    try:
        with open(os.path.join(OUT_DIR, 'console.json'), 'w') as f:
            json.dump(console_messages, f, indent=2)
    except Exception:
        pass

    try:
        with open(os.path.join(OUT_DIR, 'network.json'), 'w') as f:
            json.dump(network_events, f, indent=2)
    except Exception:
        pass

    try:
        with open(os.path.join(OUT_DIR, 'search_response.json'), 'w') as f:
            json.dump(json_body, f, indent=2)
    except Exception:
        pass

    screenshot_path = os.path.join(OUT_DIR, 'after_search.png')
    try:
        page.screenshot(path=screenshot_path, full_page=True)
    except Exception:
        pass

    print('Saved console.json, network.json, search_response.json, and screenshot (where possible)')

    try:
        browser.close()
    except Exception:
        pass
