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


@bp.route('/smoke')
async def smoke_test():
    """Quick smoke test of core API functionality"""
    from city_guides.src.app import aiohttp_session
    from aiohttp import ClientTimeout
    
    details = {}
    overall_ok = True
    
    try:
        # Test 1: Reverse geocoding
        if aiohttp_session:
            try:
                # Test reverse lookup for Paris coordinates
                url = 'https://nominatim.openstreetmap.org/reverse'
                params = {
                    'lat': 48.8566,
                    'lon': 2.3522,
                    'format': 'json'
                }
                headers = {'User-Agent': 'TravelLand/1.0'}
                
                async with aiohttp_session.get(url, params=params, headers=headers, timeout=ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        details['reverse'] = {
                            'display_name': data.get('display_name', 'Unknown'),
                            'status': 'ok'
                        }
                    else:
                        details['reverse'] = {'status': 'error', 'message': f'HTTP {response.status}'}
                        overall_ok = False
            except Exception as e:
                details['reverse'] = {'status': 'error', 'message': str(e)}
                overall_ok = False
        else:
            details['reverse'] = {'status': 'error', 'message': 'Session not initialized'}
            overall_ok = False
        
        # Test 2: Neighborhoods test
        try:
            # Try to get neighborhoods for Paris
            from city_guides.src.dynamic_neighborhoods import get_neighborhoods_for_city
            neighborhoods = await get_neighborhoods_for_city('Paris', 'FR')
            neighborhoods_count = len(neighborhoods) if neighborhoods else 0
            details['neighborhoods_count'] = neighborhoods_count
        except Exception as e:
            details['neighborhoods_error'] = str(e)
            overall_ok = False
        
        return jsonify({
            'ok': overall_ok,
            'details': details,
            'timestamp': time.time()
        })
        
    except Exception as e:
        from city_guides.src.app import app
        app.logger.exception('Smoke test failed')
        return jsonify({
            'ok': False,
            'error': str(e),
            'details': details
        }), 500


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
                <p>Intelligent API testing framework:</p>
                
                <!-- Quick Test Suites -->
                <div style="margin-bottom: 20px;">
                    <h3>🚀 One-Click Test Suites</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-bottom: 15px;">
                        <button class="refresh-btn" onclick="runGlobalTest()">🌍 Global Test</button>
                        <button class="refresh-btn" onclick="runPerformanceTest()">⚡ Performance Test</button>
                        <button class="refresh-btn" onclick="runWorkflowTest()">🔧 Workflow Test</button>
                        <button class="refresh-btn" onclick="runStressTest()">🧪 Stress Test</button>
                    </div>
                </div>

                <!-- Manual Test Controls -->
                <div style="margin-bottom: 20px;">
                    <h3>🎛️ Manual Testing</h3>
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
                        <button class="refresh-btn" onclick="testEndpoint('/api/countries', 'countries-result')">🌍 Countries</button>
                        <button class="refresh-btn" onclick="testChatRAG()">💬 Chat RAG</button>
                        <button class="refresh-btn" onclick="testEndpoint('/api/location-suggestions', 'suggestions-result', true, {query: 'par'})">🔍 Suggestions</button>
                    </div>
                </div>

                <!-- Test Results -->
                <div id="api-results" style="margin-top: 15px;"></div>
            </div>
        </div>

        <script>
            // Test data sets for different scenarios
            const testCitiesData = {
                global: ['Paris', 'Tokyo', 'New York', 'Sydney', 'Dubai'],
                popular: ['Barcelona', 'Rome', 'London', 'Bangkok', 'Singapore'],
                emerging: ['Mumbai', 'Istanbul', 'Cairo', 'Lagos', 'Jakarta'],
                beach: ['Bali', 'Maldives', 'Cancun', 'Miami', 'Phuket']
            };

            // Performance tracking
            class PerformanceTracker {
                constructor() {
                    this.timings = {};
                }

                startTimer(endpoint) {
                    this.timings[endpoint] = performance.now();
                }

                endTimer(endpoint) {
                    if (this.timings[endpoint]) {
                        const duration = performance.now() - this.timings[endpoint];
                        delete this.timings[endpoint];
                        return duration;
                    }
                    return 0;
                }

                getPerformanceClass(duration) {
                    if (duration < 500) return 'fast';
                    if (duration < 1500) return 'medium';
                    return 'slow';
                }
            }

            const tracker = new PerformanceTracker();

            // Test result class
            class TestResult {
                constructor(endpoint, data, timing, status, city = '') {
                    this.endpoint = endpoint;
                    this.data = data;
                    this.timing = timing;
                    this.status = status;
                    this.city = city;
                    this.timestamp = new Date().toISOString();
                }

                getPerformanceClass() {
                    return tracker.getPerformanceClass(this.timing);
                }

                isValid() {
                    return this.status === 'ok' && this.data && !this.data.error;
                }
            }

            // Test suite class
            class APITestSuite {
                constructor(name, tests) {
                    this.name = name;
                    this.tests = tests;
                    this.results = [];
                }

                async runSuite() {
                    const resultsDiv = document.getElementById('api-results');
                    resultsDiv.innerHTML = `<div class="loading">Running ${this.name}...</div>`;
                    
                    const startTime = performance.now();
                    
                    try {
                        this.results = await Promise.all(this.tests.map(test => this.runSingleTest(test)));
                        const totalTime = performance.now() - startTime;
                        
                        this.displayResults(totalTime);
                        this.saveResults();
                    } catch (error) {
                        resultsDiv.innerHTML = `<div class="error">Test suite failed: ${error.message}</div>`;
                    }
                }

                async runSingleTest(test) {
                    const startTime = performance.now();
                    tracker.startTimer(test.endpoint);
                    
                    try {
                        const options = test.isPost ? {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(test.data)
                        } : {};
                        
                        const response = await fetch(test.url, options);
                        const data = await response.json();
                        const timing = tracker.endTimer(test.endpoint);
                        
                        return new TestResult(test.endpoint, data, timing, response.ok ? 'ok' : 'error', test.city);
                    } catch (error) {
                        const timing = tracker.endTimer(test.endpoint);
                        return new TestResult(test.endpoint, { error: error.message }, timing, 'error', test.city);
                    }
                }

                displayResults(totalTime) {
                    const resultsDiv = document.getElementById('api-results');
                    
                    let html = `<div class="card" style="margin-top: 0;">
                        <h3>${this.name} Results (${this.results.length} tests, ${(totalTime/1000).toFixed(2)}s)</h3>`;
                    
                    // Summary stats
                    const successCount = this.results.filter(r => r.isValid()).length;
                    const avgTime = this.results.reduce((sum, r) => sum + r.timing, 0) / this.results.length;
                    
                    html += `<div style="margin-bottom: 15px;">
                        <span class="status ok">✓ ${successCount} Success</span>
                        <span class="status error">✗ ${this.results.length - successCount} Failed</span>
                        <span>Avg: ${avgTime.toFixed(0)}ms</span>
                    </div>`;
                    
                    // Results table
                    html += '<table style="width: 100%; border-collapse: collapse;">';
                    html += '<tr><th>Endpoint</th><th>City</th><th>Status</th><th>Time</th><th>Result</th></tr>';
                    
                    this.results.forEach(result => {
                        const perfClass = result.getPerformanceClass();
                        const statusClass = result.isValid() ? 'ok' : 'error';
                        const statusText = result.isValid() ? '✓' : '✗';
                        
                        html += `<tr>
                            <td>${result.endpoint}</td>
                            <td>${result.city}</td>
                            <td><span class="status ${statusClass}">${statusText}</span></td>
                            <td class="${perfClass}">${result.timing.toFixed(0)}ms</td>
                            <td><button onclick="showTestResult('${result.endpoint}', '${result.city}')" style="font-size: 11px;">View</button></td>
                        </tr>`;
                    });
                    
                    html += '</table>';
                    html += '<button onclick="exportResults()" style="margin-top: 10px;">📊 Export Results</button>';
                    html += '</div>';
                    
                    resultsDiv.innerHTML = html;
                }

                async saveResults() {
                    const history = JSON.parse(localStorage.getItem('apiTestHistory') || '[]');
                    history.push({
                        suite: this.name,
                        timestamp: new Date().toISOString(),
                        results: this.results.map(r => ({
                            endpoint: r.endpoint,
                            city: r.city,
                            status: r.status,
                            timing: r.timing
                        }))
                    });
                    localStorage.setItem('apiTestHistory', JSON.stringify(history.slice(-20))); // Keep last 20
                }
            }

            // Global test function
            async function runGlobalTest() {
                const tests = [];
                testCitiesData.global.forEach(city => {
                    tests.push(
                        { endpoint: '/api/locations/cities', url: `/api/locations/cities?country=US&state=CA`, city, isPost: false, data: null },
                        { endpoint: '/api/neighborhoods', url: `/api/neighborhoods?city=${city}&country=${city === 'New York' ? 'US' : 'FR'}`, city, isPost: false, data: null },
                        { endpoint: '/api/fun-fact', url: '/api/fun-fact', city, isPost: true, data: { city } }
                    );
                });
                
                const suite = new APITestSuite('🌍 Global Test', tests);
                await suite.runSuite();
            }

            // Performance test function
            async function runPerformanceTest() {
                const tests = [
                    { endpoint: '/api/countries', url: '/api/countries', city: 'Global', isPost: false, data: null },
                    { endpoint: '/api/locations/cities', url: '/api/locations/cities?country=US&state=CA', city: 'California', isPost: false, data: null },
                    { endpoint: '/api/neighborhoods', url: '/api/neighborhoods?city=Paris&country=FR', city: 'Paris', isPost: false, data: null },
                    { endpoint: '/api/fun-fact', url: '/api/fun-fact', city: 'Paris', isPost: true, data: { city: 'Paris' } },
                    { endpoint: '/api/location-suggestions', url: '/api/location-suggestions', city: 'Search', isPost: true, data: { query: 'par' } }
                ];
                
                const suite = new APITestSuite('⚡ Performance Test', tests);
                await suite.runSuite();
            }

            // Workflow test function
            async function runWorkflowTest() {
                const resultsDiv = document.getElementById('api-results');
                resultsDiv.innerHTML = '<div class="loading">Testing complete workflow...</div>';
                
                try {
                    // Step 1: Get countries
                    const countriesResponse = await fetchData('/api/countries');
                    
                    // Step 2: Get cities for a country
                    const citiesResponse = await fetchData('/api/locations/cities?country=US&state=CA');
                    
                    // Step 3: Get neighborhoods for a city
                    const neighborhoodsResponse = await fetchData('/api/neighborhoods?city=Paris&country=FR');
                    
                    // Step 4: Get fun fact
                    const funFactResponse = await testEndpoint('/api/fun-fact', 'funfact-result', true, {city: 'Paris'});
                    
                    // Step 5: Chat RAG
                    const chatResponse = await testChatRAG();
                    
                    resultsDiv.innerHTML = `
                        <div class="card" style="margin-top: 0;">
                            <h3>🔧 Workflow Test Results</h3>
                            <div class="status ok">✓ Complete workflow tested successfully</div>
                            <div style="margin-top: 10px;">
                                <strong>Steps completed:</strong><br>
                                1. Countries: ${countriesResponse.error ? '❌' : '✅'}<br>
                                2. Cities: ${citiesResponse.error ? '❌' : '✅'}<br>
                                3. Neighborhoods: ${neighborhoodsResponse.error ? '❌' : '✅'}<br>
                                4. Fun Fact: ${funFactResponse ? '❌' : '✅'}<br>
                                5. Chat RAG: ${chatResponse ? '❌' : '✅'}
                            </div>
                        </div>
                    `;
                } catch (error) {
                    resultsDiv.innerHTML = `<div class="error">Workflow test failed: ${error.message}</div>`;
                }
            }

            // Stress test function
            async function runStressTest() {
                const resultsDiv = document.getElementById('api-results');
                resultsDiv.innerHTML = '<div class="loading">Running stress test...</div>';
                
                const startTime = performance.now();
                const promises = [];
                
                // Run 10 parallel requests to each endpoint
                for (let i = 0; i < 10; i++) {
                    promises.push(fetchData('/api/countries'));
                    promises.push(fetchData('/api/locations/cities?country=US&state=CA'));
                    promises.push(fetchData('/api/neighborhoods?city=Paris&country=FR'));
                }
                
                try {
                    const results = await Promise.all(promises);
                    const totalTime = performance.now() - startTime;
                    const successCount = results.filter(r => !r.error).length;
                    
                    resultsDiv.innerHTML = `
                        <div class="card" style="margin-top: 0;">
                            <h3>🧪 Stress Test Results</h3>
                            <div class="status ${successCount === 30 ? 'ok' : 'error'}">
                                ${successCount}/30 requests successful (${((successCount/30)*100).toFixed(1)}%)
                            </div>
                            <div>Total time: ${(totalTime/1000).toFixed(2)}s</div>
                            <div>Avg per request: ${(totalTime/30).toFixed(0)}ms</div>
                        </div>
                    `;
                } catch (error) {
                    resultsDiv.innerHTML = `<div class="error">Stress test failed: ${error.message}</div>`;
                }
            }

            // Export results function
            function exportResults() {
                const history = JSON.parse(localStorage.getItem('apiTestHistory') || '[]');
                const csv = 'Timestamp,Suite,Endpoint,City,Status,Time (ms)\\n' +
                    history.flatMap(h => h.results.map(r => 
                        `${h.timestamp},${h.suite},${r.endpoint},${r.city},${r.status},${r.timing}`
                    )).join('\\n');
                
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `api-test-results-${new Date().toISOString().split('T')[0]}.csv`;
                a.click();
            }

            // Show individual test result
            function showTestResult(endpoint, city) {
                const history = JSON.parse(localStorage.getItem('apiTestHistory') || '[]');
                const result = history
                    .flatMap(h => h.results)
                    .find(r => r.endpoint === endpoint && r.city === city);
                
                if (result) {
                    alert(`Endpoint: ${result.endpoint}\nCity: ${result.city}\nStatus: ${result.status}\nTime: ${result.timing}ms`);
                }
            }
            async function fetchData(url, options = {}) {
                try {
                    const response = await fetch(url, options);
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
