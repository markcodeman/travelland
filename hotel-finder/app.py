from flask import Flask, render_template, request, jsonify
import search_provider

app = Flask(__name__, static_folder='static', template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    payload = request.json or {}
    city_code = payload.get('city_code', '').strip().upper()
    check_in = payload.get('check_in', '').strip()
    check_out = payload.get('check_out', '').strip()
    adults = int(payload.get('adults', 1))
    
    if not city_code or not check_in or not check_out:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        results = search_provider.searx_search_hotels(city_code, check_in, check_out, adults)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
