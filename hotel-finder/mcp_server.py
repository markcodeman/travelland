"""Minimal local MCP-like server for testing Playwright integration.

This lightweight server advertises a couple of mock tools and accepts
execute requests. It's intentionally simple and meant for development only.
"""
from flask import Flask, jsonify, request
from playwright.sync_api import sync_playwright
import atexit

app = Flask(__name__)

# Playwright state
_playwright = None
_browser = None
_page = None

def get_page():
    global _playwright, _browser, _page
    if _page is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
        _page = _browser.new_page()
    return _page

def cleanup():
    global _playwright, _browser
    if _browser:
        _browser.close()
    if _playwright:
        _playwright.stop()

atexit.register(cleanup)

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
def list_tools():
    return jsonify({'tools': TOOLS})


@app.route('/mcp/execute', methods=['POST'])
def execute_tool():
    data = request.json or {}
    tool_id = data.get('tool_id')
    params = data.get('params', {})
    if not tool_id:
        return jsonify({'error': 'tool_id required'}), 400
    
    try:
        page = get_page()
        
        if tool_id == 'navigate':
            url = params.get('url')
            if not url:
                return jsonify({'error': 'url required'}), 400
            page.goto(url)
            return jsonify({'status': 'ok', 'result': f'Navigated to {url}'})
            
        if tool_id == 'type_text':
            selector = params.get('selector')
            text = params.get('text')
            if not selector or text is None:
                return jsonify({'error': 'selector and text required'}), 400
            page.fill(selector, text)
            return jsonify({'status': 'ok', 'result': f'Typed text into {selector}'})
            
        if tool_id == 'click':
            selector = params.get('selector')
            if not selector:
                return jsonify({'error': 'selector required'}), 400
            page.click(selector)
            return jsonify({'status': 'ok', 'result': f'Clicked {selector}'})
            
        if tool_id == 'get_content':
            selector = params.get('selector')
            if not selector:
                return jsonify({'error': 'selector required'}), 400
            content = page.inner_text(selector)
            return jsonify({'status': 'ok', 'result': content})
            
        return jsonify({'error': 'unknown_tool'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run(port: int = 8766):
    app.run(host='127.0.0.1', port=port, debug=False, threaded=False)


if __name__ == '__main__':
    run()
