"""
Admin routes: Health checks, metrics, and smoke tests
"""
import os
import time
import asyncio
from quart import Blueprint, jsonify

# Import dependencies from parent app
from city_guides.src.metrics import get_metrics as get_metrics_dict
from city_guides.providers import multi_provider

bp = Blueprint('admin', __name__)


@bp.route('/healthz')
async def healthz():
    """Lightweight health endpoint returning component status."""
    # Import app globals
    from city_guides.src.app import aiohttp_session, redis_client
    
    status = {
        'app': 'ok',
        'time': time.time(),
        'ready': bool(aiohttp_session is not None),
        'redis': bool(redis_client is not None),
        'geoapify': bool(os.getenv('GEOAPIFY_API_KEY')),
        'geonames': bool(os.getenv('GEONAMES_USERNAME'))
    }
    return jsonify(status)


@bp.route('/metrics/json')
async def metrics_json():
    """Return simple JSON metrics (counters and latency summaries)"""
    try:
        metrics = await get_metrics_dict()
        return jsonify(metrics)
    except Exception:
        from city_guides.src.app import app
        app.logger.exception('Failed to get metrics')
        return jsonify({'error': 'failed to fetch metrics'}), 500


@bp.route('/admin')
async def admin():
    """Serve interactive admin dashboard HTML page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TravelLand Admin Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { color: #333; text-align: center; margin-bottom: 30px; }
            .card { background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .card h2 { color: #007bff; margin-top: 0; }
            .status { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
            .status.ok { background: #d4edda; color: #155724; }
            .status.error { background: #f8d7da; color: #721c24; }
            .status.warning { background: #fff3cd; color: #856404; }
            .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
            .metric { background: #f8f9fa; padding: 15px; border-radius: 6px; text-align: center; }
            .metric .value { font-size: 24px; font-weight: bold; color: #007bff; }
            .metric .label { font-size: 14px; color: #666; margin-top: 5px; }
            .json-data { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 15px; margin-top: 10px; font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; }
            .loading { color: #666; font-style: italic; }
            .error { color: #dc3545; }
            .refresh-btn { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 10px 0; }
            .refresh-btn:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 TravelLand Admin Dashboard</h1>
            
            <button class="refresh-btn" onclick="refreshAll()">🔄 Refresh All</button>
            
            <div class="card">
                <h2>🏥 System Health</h2>
                <div id="health-status" class="loading">Loading health status...</div>
                <div id="health-data" class="json-data" style="display: none;"></div>
            </div>
            
            <div class="card">
                <h2>📊 System Metrics</h2>
                <div id="metrics-content" class="loading">Loading metrics...</div>
            </div>
            
            <div class="card">
                <h2>🧪 Smoke Test</h2>
                <div id="smoke-status" class="loading">Loading smoke test...</div>
                <div id="smoke-data" class="json-data" style="display: none;"></div>
            </div>
            
            <div class="card">
                <h2>🏙️ API Tests</h2>
                <p>Test cities and neighborhoods anywhere in the world:</p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 15px;">
                    <div><label>Country:</label><input type="text" id="country-input" placeholder="US" value="US"></div>
                    <div><label>State:</label><input type="text" id="state-input" placeholder="CA" value="CA"></div>
                    <div><label>City:</label><input type="text" id="city-input" placeholder="Paris" value="Paris"></div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-bottom: 15px;">
                    <button class="refresh-btn" onclick="testCities()">🏙️ Cities</button>
                    <button class="refresh-btn" onclick="testNeighborhoods()">🏘️ Neighborhoods</button>
                    <button class="refresh-btn" onclick="testFunFact()">🎭 Fun Fact</button>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-bottom: 15px;">
                    <button class="refresh-btn" onclick="testEndpoint('/api/countries', 'countries-result')">� Countries</button>
                    <button class="refresh-btn" onclick="testChatRAG()">💬 Chat RAG</button>
                    <button class="refresh-btn" onclick="testEndpoint('/api/location-suggestions', 'suggestions-result', true, {query: 'par'})">🔍 Suggestions</button>
                </div>
                <div id="api-results" style="margin-top: 15px;"></div>
            </div>
        </div>

        <script>
            async function fetchData(url) {
                try {
                    const response = await fetch(url);
                    return await response.json();
                } catch (error) {
                    return { error: error.message };
                }
            }

            async function testEndpoint(url, resultId, isPost = false, postData = null) {
                const resultsDiv = document.getElementById('api-results');
                resultsDiv.innerHTML = '<div class="loading">Testing ' + url + '...</div>';
                
                let options = {};
                if (isPost) {
                    options = {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(postData)
                    };
                }
                
                const data = await fetchData(url, options);
                const status = data.error ? 'error' : 'ok';
                
                let html = '<div class="card" style="margin-top: 0;"><h3>Test Result: ' + url + '</h3>';
                html += '<div class="status ' + status + '">' + (status === 'ok' ? '✓ SUCCESS' : '✗ ERROR') + '</div>';
                
                if (data.error) {
                    html += '<div class="error">Error: ' + data.error + '</div>';
                } else {
                    html += '<div class="json-data">' + JSON.stringify(data, null, 2) + '</div>';
                }
                
                html += '</div>';
                resultsDiv.innerHTML = html;
            }

            async function testCities() {
                const country = document.getElementById('country-input').value;
                const state = document.getElementById('state-input').value;
                const url = `/api/locations/cities?state=${encodeURIComponent(state)}&country=${encodeURIComponent(country)}`;
                testEndpoint(url, 'cities-result');
            }

            async function testNeighborhoods() {
                const city = document.getElementById('city-input').value;
                const country = document.getElementById('country-input').value;
                const url = `/api/neighborhoods?city=${encodeURIComponent(city)}&country=${encodeURIComponent(country)}`;
                testEndpoint(url, 'neighborhoods-result');
            }

            async function testFunFact() {
                const city = document.getElementById('city-input').value;
                const url = '/api/fun-fact';
                testEndpoint(url, 'funfact-result', true, {city: city});
            }

            async function testChatRAG() {
                const resultsDiv = document.getElementById('api-results');
                resultsDiv.innerHTML = '<div class="loading">Testing Chat RAG...</div>';
                
                try {
                    const response = await fetch('/api/chat/rag', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            query: "Hello, can you tell me about Paris?",
                            city: "Paris",
                            country: "FR"
                        })
                    });
                    
                    const data = await response.json();
                    const status = response.ok ? 'ok' : 'error';
                    
                    let html = '<div class="card" style="margin-top: 0;"><h3>Test Result: Chat RAG</h3>';
                    html += '<div class="status ' + status + '">' + (status === 'ok' ? '✓ SUCCESS' : '✗ ERROR') + '</div>';
                    html += '<div class="json-data">' + JSON.stringify(data, null, 2) + '</div>';
                    html += '</div>';
                    
                    resultsDiv.innerHTML = html;
                } catch (error) {
                    resultsDiv.innerHTML = '<div class="card" style="margin-top: 0;"><h3>Test Result: Chat RAG</h3><div class="status error">✗ ERROR</div><div class="error">Error: ' + error.message + '</div></div>';
                }
            }

            function formatHealth(data) {
                let html = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 15px;">';
                
                const checks = [
                    { key: 'app', label: 'App Status' },
                    { key: 'ready', label: 'Session Ready' },
                    { key: 'redis', label: 'Redis' },
                    { key: 'geoapify', label: 'Geoapify API' },
                    { key: 'geonames', label: 'GeoNames API' }
                ];
                
                checks.forEach(check => {
                    const value = data[check.key];
                    const status = value ? 'ok' : 'error';
                    const statusText = value ? '✓ OK' : '✗ FAIL';
                    html += `<div><strong>${check.label}:</strong> <span class="status ${status}">${statusText}</span></div>`;
                });
                
                html += '</div>';
                html += '<div><strong>Server Time:</strong> ' + new Date(data.time * 1000).toLocaleString() + '</div>';
                return html;
            }

            function formatMetrics(data) {
                if (data.error) {
                    return '<div class="error">Error loading metrics: ' + data.error + '</div>';
                }
                
                let html = '<div class="metrics">';
                
                // Extract some key metrics
                const metrics = [
                    { key: 'total_requests', label: 'Total Requests' },
                    { key: 'search_requests', label: 'Search Requests' },
                    { key: 'chat_requests', label: 'Chat Requests' },
                    { key: 'error_count', label: 'Errors' }
                ];
                
                metrics.forEach(metric => {
                    const value = data[metric.key] || 0;
                    html += `<div class="metric"><div class="value">${value}</div><div class="label">${metric.label}</div></div>`;
                });
                
                html += '</div>';
                
                // Add raw JSON
                html += '<details style="margin-top: 15px;"><summary>Raw Metrics Data</summary>';
                html += '<pre class="json-data">' + JSON.stringify(data, null, 2) + '</pre>';
                html += '</details>';
                
                return html;
            }

            function formatSmoke(data) {
                const status = data.ok ? 'ok' : 'error';
                const statusText = data.ok ? '✓ PASS' : '✗ FAIL';
                
                let html = '<div style="margin-bottom: 15px;"><strong>Overall Status:</strong> <span class="status ' + status + '">' + statusText + '</span></div>';
                
                if (data.details) {
                    html += '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;">';
                    
                    if (data.details.reverse) {
                        const rev = data.details.reverse;
                        html += '<div><strong>Reverse Lookup:</strong> ' + (rev.display_name ? '✓ ' + rev.display_name : '✗ Failed') + '</div>';
                    }
                    
                    if (data.details.neighborhoods_count !== undefined) {
                        html += '<div><strong>Neighborhoods:</strong> ' + data.details.neighborhoods_count + ' found</div>';
                    }
                    
                    html += '</div>';
                }
                
                return html;
            }

            async function loadHealth() {
                const element = document.getElementById('health-status');
                const dataElement = document.getElementById('health-data');
                
                element.innerHTML = 'Loading health status...';
                const data = await fetchData('/healthz');
                
                if (data.error) {
                    element.innerHTML = '<div class="error">Error: ' + data.error + '</div>';
                } else {
                    element.innerHTML = formatHealth(data);
                    dataElement.textContent = JSON.stringify(data, null, 2);
                    dataElement.style.display = 'block';
                }
            }

            async function loadMetrics() {
                const element = document.getElementById('metrics-content');
                element.innerHTML = 'Loading metrics...';
                const data = await fetchData('/metrics/json');
                element.innerHTML = formatMetrics(data);
            }

            async function loadSmoke() {
                const element = document.getElementById('smoke-status');
                const dataElement = document.getElementById('smoke-data');
                
                element.innerHTML = 'Loading smoke test...';
                const data = await fetchData('/smoke');
                
                if (data.error) {
                    element.innerHTML = '<div class="error">Error: ' + data.error + '</div>';
                } else {
                    element.innerHTML = formatSmoke(data);
                    dataElement.textContent = JSON.stringify(data, null, 2);
                    dataElement.style.display = 'block';
                }
            }

            async function refreshAll() {
                await Promise.all([loadHealth(), loadMetrics(), loadSmoke()]);
            }

            // Load data on page load
            window.onload = refreshAll;
        </script>
    </body>
    </html>
    """


def register(app):
    """Register admin blueprint with app"""
    app.register_blueprint(bp)
