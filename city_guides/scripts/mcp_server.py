"""Minimal local MCP-like server for testing Playwright integration (Quart version)."""
from quart import Quart, jsonify, request
try:
    from playwright.async_api import async_playwright
    _playwright_available = True
except Exception:
    async_playwright = None
    _playwright_available = False

app = Quart(__name__)

# Playwright state
_playwright = None
_browser = None
_page = None

async def get_page():
    global _playwright, _browser, _page
    if _page is None:
        if not _playwright_available or async_playwright is None:
            raise RuntimeError("Playwright is not installed or async_playwright is None. Install it with: pip install playwright and run 'playwright install'")
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=False)
        _page = await _browser.new_page()
    return _page

async def cleanup():
    global _playwright, _browser
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()

# Simple in-memory tool registry
TOOLS = [
    {
        'id': 'navigate',
        'title': 'Navigate',
        'description': 'Navigate to a URL',
        'inputs': {'url': 'string'},
    },
    {
        'id': 'type_text',
        'title': 'Type Text',
        'description': 'Type text into a selector',
        'inputs': {'selector': 'string', 'text': 'string'},
    },
    {
        'id': 'click',
        'title': 'Click',
        'description': 'Click an element',
        'inputs': {'selector': 'string'},
    },
    {
        'id': 'get_content',
        'title': 'Get Content',
        'description': 'Get the text content of an element',
        'inputs': {'selector': 'string'},
    }
]

@app.route('/mcp/list', methods=['GET'])
async def list_tools():
    return jsonify({'tools': TOOLS})

@app.route('/mcp/execute', methods=['POST'])
async def execute_tool():
    data = await request.get_json(force=True)
    tool_id = data.get('tool_id')
    params = data.get('params', {})
    if not tool_id:
        return jsonify({'error': 'tool_id required'}), 400
    try:
        page = await get_page()
        if tool_id == 'navigate':
            url = params.get('url')
            if not url:
                return jsonify({'error': 'url required'}), 400
            await page.goto(url)
            return jsonify({'status': 'ok', 'result': f'Navigated to {url}'})
        if tool_id == 'type_text':
            selector = params.get('selector')
            text = params.get('text')
            if not selector or text is None:
                return jsonify({'error': 'selector and text required'}), 400
            await page.fill(selector, "")  # Clear field first
            await page.type(selector, text)  # Simulate real keystrokes
            await page.dispatch_event(selector, "input")  # Trigger input event for predictive search
            return jsonify({'status': 'ok', 'result': f'Typed text into {selector} with input event'})
        if tool_id == 'click':
            selector = params.get('selector')
            if not selector:
                return jsonify({'error': 'selector required'}), 400
            await page.click(selector)
            return jsonify({'status': 'ok', 'result': f'Clicked {selector}'})
        if tool_id == 'get_content':
            selector = params.get('selector')
            if not selector:
                return jsonify({'error': 'selector required'}), 400
            content = await page.inner_text(selector)
            return jsonify({'status': 'ok', 'result': content})
        return jsonify({'error': 'unknown_tool'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/mcp/launch', methods=['POST'])
async def launch_browser():
    global _playwright, _browser, _page
    try:
        if not _playwright_available or async_playwright is None:
            return jsonify({'error': 'Playwright not available'}), 500
        # Clean up any previous browser/page
        if _browser:
            await _browser.close()
        if _playwright:
            await _playwright.stop()
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=False)
        _page = await _browser.new_page()
        return jsonify({'status': 'ok', 'result': 'Browser launched'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run(port: int = 8766):
    app.run(host='127.0.0.1', port=port)

if __name__ == '__main__':
    run()

