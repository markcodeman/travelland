import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask

app = Flask(__name__)

@app.route('/healthz')
def healthz():
    return 'OK'

@app.route('/api/smart-neighborhoods')
def smart_neighborhoods():
    return {'is_large_city': True, 'neighborhoods': [{'name': 'Test Neighborhood', 'description': 'A test area', 'type': 'culture'}]}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010)
