"""Minimal local MCP-like server for testing Playwright integration.

This lightweight server advertises a couple of mock tools and accepts
execute requests. It's intentionally simple and meant for development only.
"""
from flask import Flask, jsonify, request

app = Flask(__name__)

# Simple in-memory tool registry
TOOLS = [
    {
        'id': 'open_url',
        'title': 'Open URL',
        'description': 'Instruct browser to open a URL',
        'inputs': {'url': 'string'},
    },
    {
        'id': 'echo',
        'title': 'Echo',
        'description': 'Return the provided payload',
        'inputs': {'payload': 'any'},
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
    if tool_id == 'open_url':
        url = params.get('url')
        if not url:
            return jsonify({'error': 'url required'}), 400
        # For local testing we just acknowledge; the Playwright script itself
        # will actually open the URL in the browser.
        return jsonify({'status': 'ok', 'result': f'ack:open:{url}'})
    if tool_id == 'echo':
        return jsonify({'status': 'ok', 'result': params.get('payload')})
    return jsonify({'error': 'unknown_tool'}), 404


def run(port: int = 8765):
    app.run(host='127.0.0.1', port=port, debug=False)


if __name__ == '__main__':
    run()
