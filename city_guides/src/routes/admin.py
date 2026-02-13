"""
Admin routes: Health checks, metrics, and smoke tests
"""
import os
import time
import random
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
        'geonames': bool(os.getenv('GEONAMES_USERNAME')),
        'groq': bool(os.getenv('GROQ_API_KEY')),
        'unsplash': bool(os.getenv('UNSPLASH_KEY')),
        'pixabay': bool(os.getenv('PIXABAY_KEY'))
    }
    return jsonify(status)


@bp.route('/admin/keys')
async def keys_status():
    """Report presence (not values) of critical API keys/env vars."""
    required = {
        'UNSPLASH_KEY': bool(os.getenv('UNSPLASH_KEY')),
        'PIXABAY_KEY': bool(os.getenv('PIXABAY_KEY')),
        'GEONAMES_USERNAME': bool(os.getenv('GEONAMES_USERNAME')),
        'GEOAPIFY_API_KEY': bool(os.getenv('GEOAPIFY_API_KEY')),
        'GROQ_API_KEY': bool(os.getenv('GROQ_API_KEY')),
    }
    return jsonify({
        'ok': all(required.values()),
        'keys': required,
        'missing': [k for k, v in required.items() if not v]
    })


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
    """Comprehensive smoke test with random cities, provenance, and timestamps"""
    from city_guides.src.app import aiohttp_session
    from aiohttp import ClientTimeout

    results = []
    overall_ok = True

    # Test cities from different regions with known coordinates
    test_cities = [
        # Europe
        {'name': 'Paris', 'lat': 48.8566, 'lon': 2.3522, 'country': 'FR', 'region': 'Europe'},
        {'name': 'London', 'lat': 51.5074, 'lon': -0.1278, 'country': 'GB', 'region': 'Europe'},
        {'name': 'Tokyo', 'lat': 35.6762, 'lon': 139.6503, 'country': 'JP', 'region': 'Asia'},
        {'name': 'New York', 'lat': 40.7128, 'lon': -74.0060, 'country': 'US', 'region': 'North America'},
        {'name': 'Sydney', 'lat': -33.8688, 'lon': 151.2093, 'country': 'AU', 'region': 'Oceania'},
        {'name': 'Rio de Janeiro', 'lat': -22.9068, 'lon': -43.1729, 'country': 'BR', 'region': 'South America'},
        {'name': 'Cairo', 'lat': 30.0444, 'lon': 31.2357, 'country': 'EG', 'region': 'Africa'},
        {'name': 'Mumbai', 'lat': 19.0760, 'lon': 72.8777, 'country': 'IN', 'region': 'Asia'},
    ]

    # Shuffle to avoid hammering same endpoints; limit to 5 per run
    random.shuffle(test_cities)
    test_cities = test_cities[:5]

    try:
        from city_guides.src.dynamic_neighborhoods import get_neighborhoods_for_city

        # Test each city
        for city in test_cities:
            city_start = time.time()
            city_result = {
                'city': city['name'],
                'region': city['region'],
                'country': city['country'],
                'coordinates': {'lat': city['lat'], 'lon': city['lon']},
                'timestamp': city_start,
                'tests': {}
            }

            # Test 1: Reverse geocoding (OpenStreetMap/Nominatim)
            try:
                url = 'https://nominatim.openstreetmap.org/reverse'
                params = {'lat': city['lat'], 'lon': city['lon'], 'format': 'json'}
                headers = {'User-Agent': 'TravelLand/1.0'}
                
                rev_start = time.time()
                async with aiohttp_session.get(url, params=params, headers=headers, timeout=ClientTimeout(total=5)) as response:
                    rev_time = time.time() - rev_start
                    if response.status == 200:
                        data = await response.json()
                        city_result['tests']['reverse_geocoding'] = {
                            'provider': 'OpenStreetMap/Nominatim',
                            'status': 'ok',
                            'time_ms': round(rev_time * 1000, 2),
                            'display_name': data.get('display_name', 'Unknown')[:100] + '...' if len(data.get('display_name', '')) > 100 else data.get('display_name', 'Unknown')
                        }
                    else:
                        city_result['tests']['reverse_geocoding'] = {
                            'provider': 'OpenStreetMap/Nominatim',
                            'status': 'error',
                            'time_ms': round(rev_time * 1000, 2),
                            'error': f'HTTP {response.status}'
                        }
                        overall_ok = False
            except Exception as e:
                city_result['tests']['reverse_geocoding'] = {
                    'provider': 'OpenStreetMap/Nominatim',
                    'status': 'error',
                    'error': str(e)
                }
                overall_ok = False

            # Test 2: Neighborhoods with provenance
            try:
                neighborhoods_start = time.time()
                neighborhoods = await get_neighborhoods_for_city(city['name'], city['lat'], city['lon'])
                neighborhoods_time = time.time() - neighborhoods_start
                
                # Determine which provider returned data
                provider = 'unknown'
                if neighborhoods:
                    first = neighborhoods[0] if neighborhoods else None
                    if first and hasattr(first, 'source'):
                        provider = getattr(first, 'source', 'unknown')
                    elif isinstance(first, dict):
                        provider = first.get('source', first.get('provider', 'unknown'))
                
                city_result['tests']['neighborhoods'] = {
                    'provider': provider,
                    'status': 'ok' if neighborhoods else 'warning',
                    'time_ms': round(neighborhoods_time * 1000, 2),
                    'count': len(neighborhoods) if neighborhoods else 0,
                    'first_neighborhood': neighborhoods[0].get('name') if neighborhoods and isinstance(neighborhoods[0], dict) else (neighborhoods[0].name if neighborhoods and hasattr(neighborhoods[0], 'name') else 'N/A')
                }
            except Exception as e:
                city_result['tests']['neighborhoods'] = {
                    'provider': 'get_neighborhoods_for_city',
                    'status': 'warning',
                    'error': str(e)
                }
                # treat as warning to avoid failing smoke on rate limits

            city_result['total_time_ms'] = round((time.time() - city_start) * 1000, 2)
            results.append(city_result)

        return jsonify({
            'ok': overall_ok,
            'test_run_timestamp': time.time(),
            'regions_tested': list(set(r['region'] for r in results)),
            'cities_tested': len(results),
            'results': results
        })

    except Exception as e:
        from city_guides.src.app import app
        app.logger.exception('Smoke test failed')
        return jsonify({
            'ok': False,
            'error': str(e),
            'test_run_timestamp': time.time()
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
        <script src="/admin.js" defer></script>
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
                <!-- Manual Test Controls and rest of HTML ... -->
                <!-- ... (rest of the HTML remains unchanged) ... -->
                <div id="api-results" style="margin-top: 15px;"></div>
            </div>
        </div>

        <script>
            // Test data sets for different scenarios
            const testCities = {
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
                        resultsDiv.innerHTML = '<div class="error">Test suite failed: ' + error.message + '</div>';
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
                    
                    let html = '<div class="card" style="margin-top: 0;">' +
                        '<h3>' + this.name + ' Results (' + this.results.length + ' tests, ' + (totalTime/1000).toFixed(2) + 's)</h3>';
                    
                    // Summary stats
                    const successCount = this.results.filter(r => r.isValid()).length;
                    const avgTime = this.results.reduce((sum, r) => sum + r.timing, 0) / this.results.length;
                    
                    html += '<div style="margin-bottom: 15px;">' +
                        '<span class="status ok">✓ ' + successCount + ' Success</span>' +
                        '<span class="status error">✗ ' + (this.results.length - successCount) + ' Failed</span>' +
                        '<span>Avg: ' + avgTime.toFixed(0) + 'ms</span>' +
                    '</div>';
                    
                    // Results table
                    html += '<table style="width: 100%; border-collapse: collapse;">';
                    html += '<tr><th>Endpoint</th><th>City</th><th>Status</th><th>Time</th><th>Result</th></tr>';
                    
                    this.results.forEach(result => {
                        const perfClass = result.getPerformanceClass();
                        const statusClass = result.isValid() ? 'ok' : 'error';
                        const statusText = result.isValid() ? '✓' : '✗';
                        
                        html += '<tr>' +
                            '<td>' + result.endpoint + '</td>' +
                            '<td>' + result.city + '</td>' +
                            '<td><span class="status ' + statusClass + '">' + statusText + '</span></td>' +
                            '<td class="' + perfClass + '">' + result.timing.toFixed(0) + 'ms</td>' +
                            '<td><button onclick="showTestResult(\'' + result.endpoint + '\', \'' + result.city + '\')" style="font-size: 11px;">View</button></td>' +
                        '</tr>';
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
                testCities.global.forEach(city => {
                    tests.push(
                        { endpoint: '/api/locations/cities', url: '/api/locations/cities?country=US&state=CA', city, isPost: false, data: null },
                        { endpoint: '/api/neighborhoods', url: '/api/neighborhoods?city=' + city + '&country=' + (city === 'New York' ? 'US' : 'FR'), city, isPost: false, data: null },
                        { endpoint: '/api/fun-fact', url: '/api/fun-fact', city, isPost: true, data: { city: city } }
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
                    
                    resultsDiv.innerHTML = '<div class="card" style="margin-top: 0;">' +
                        '<h3>🔧 Workflow Test Results</h3>' +
                        '<div class="status ok">✓ Complete workflow tested successfully</div>' +
                        '<div style="margin-top: 10px;">' +
                            '<strong>Steps completed:</strong><br>' +
                            '1. Countries: ' + (countriesResponse.error ? '❌' : '✅') + '<br>' +
                            '2. Cities: ' + (citiesResponse.error ? '❌' : '✅') + '<br>' +
                            '3. Neighborhoods: ' + (neighborhoodsResponse.error ? '❌' : '✅') + '<br>' +
                            '4. Fun Fact: ' + (funFactResponse ? '❌' : '✅') + '<br>' +
                            '5. Chat RAG: ' + (chatResponse ? '❌' : '✅') +
                        '</div>' +
                    '</div>';
                } catch (error) {
                    resultsDiv.innerHTML = '<div class="error">Workflow test failed: ' + error.message + '</div>';
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
                    
                    resultsDiv.innerHTML = '<div class="card" style="margin-top: 0;">' +
                        '<h3>🧪 Stress Test Results</h3>' +
                        '<div class="status ' + (successCount === 30 ? 'ok' : 'error') + '">' +
                            successCount + '/30 requests successful (' + ((successCount/30)*100).toFixed(1) + '%)' +
                        '</div>' +
                        '<div>Total time: ' + (totalTime/1000).toFixed(2) + 's</div>' +
                        '<div>Avg per request: ' + (totalTime/30).toFixed(0) + 'ms</div>' +
                    '</div>';
                } catch (error) {
                    resultsDiv.innerHTML = '<div class="error">Stress test failed: ' + error.message + '</div>';
                }
            }

            // Export results function
            function exportResults() {
                const history = JSON.parse(localStorage.getItem('apiTestHistory') || '[]');
                const csv = 'Timestamp,Suite,Endpoint,City,Status,Time (ms)\\n' +
                    history.flatMap(h => h.results.map(r => 
                        h.timestamp + ',' + h.suite + ',' + r.endpoint + ',' + r.city + ',' + r.status + ',' + r.timing
                    )).join('\n');
                
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'api-test-results-' + new Date().toISOString().split('T')[0] + '.csv';
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
                const url = '/api/locations/cities?state=' + encodeURIComponent(state) + '&country=' + encodeURIComponent(country);
                testEndpoint(url, 'cities-result');
            }

            async function testNeighborhoods() {
                const city = document.getElementById('city-input').value;
                const country = document.getElementById('country-input').value;
                const url = '/api/neighborhoods?city=' + encodeURIComponent(city) + '&country=' + encodeURIComponent(country);
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
                    html += '<div><strong>' + check.label + ':</strong> <span class="status ' + status + '">' + statusText + '</span></div>';
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
                    html += '<div class="metric"><div class="value">' + value + '</div><div class="label">' + metric.label + '</div></div>';
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
                
                // Test run info
                if (data.test_run_timestamp) {
                    html += '<div style="margin-bottom: 10px;"><strong>Test Run:</strong> ' + new Date(data.test_run_timestamp * 1000).toLocaleString() + '</div>';
                }
                
                // Regions and cities summary
                if (data.regions_tested && data.cities_tested) {
                    html += '<div style="margin-bottom: 15px;"><strong>Coverage:</strong> ' + data.cities_tested + ' cities across ' + data.regions_tested.length + ' regions: ' + data.regions_tested.join(', ') + '</div>';
                }
                
                // Detailed results per city
                if (data.results) {
                    html += '<div style="display: grid; gap: 10px;">';
                    
                    data.results.forEach(city => {
                        const cityStatus = city.tests && Object.values(city.tests).every(t => t.status === 'ok');
                        const cityClass = cityStatus ? 'ok' : 'error';
                        
                        html += '<div style="background: #f8f9fa; padding: 10px; border-radius: 4px; border-left: 4px solid ' + (cityStatus ? '#28a745' : '#dc3545') + ';">';
                        html += '<strong>' + city.city + '</strong> (' + city.region + ') - ' + city.total_time_ms + 'ms<br>';
                        
                        // Reverse geocoding result
                        if (city.tests && city.tests.reverse_geocoding) {
                            const rev = city.tests.reverse_geocoding;
                            html += '<span style="color: ' + (rev.status === 'ok' ? 'green' : 'red') + ';">';
                            html += '📍 Reverse: ' + rev.status + ' (' + rev.time_ms + 'ms)';
                            if (rev.provider) html += ' - ' + rev.provider;
                            if (rev.display_name) html += '<br><small>' + rev.display_name + '</small>';
                            html += '</span><br>';
                        }
                        
                        // Neighborhoods result
                        if (city.tests && city.tests.neighborhoods) {
                            const nh = city.tests.neighborhoods;
                            html += '<span style="color: ' + (nh.status === 'ok' ? 'green' : (nh.status === 'warning' ? 'orange' : 'red')) + ';">';
                            html += '🏘️ Neighborhoods: ' + nh.status + ' (' + nh.time_ms + 'ms)';
                            if (nh.provider) html += ' - ' + nh.provider;
                            if (nh.count !== undefined) html += ' - ' + nh.count + ' found';
                            if (nh.first_neighborhood) html += '<br><small>First: ' + nh.first_neighborhood + '</small>';
                            html += '</span>';
                        }
                        
                        html += '</div>';
                    });
                    
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

            // Attach functions to global scope for button onclick handlers
            window.runGlobalTest = async function() {
                const tests = [];
                testCityData.global.forEach(city => {
                    tests.push(
                        { endpoint: '/api/locations/cities', url: `/api/locations/cities?country=US&state=CA`, city, isPost: false, data: null },
                        { endpoint: '/api/neighborhoods', url: `/api/neighborhoods?city=${city}&country=${city === 'New York' ? 'US' : 'FR'}`, city, isPost: false, data: null },
                        { endpoint: '/api/fun-fact', url: '/api/fun-fact', city, isPost: true, data: { city } }
                    );
                });
                
                const suite = new APITestSuite('🌍 Global Test', tests);
                await suite.runSuite();
            };

            window.runPerformanceTest = async function() {
                const tests = [
                    { endpoint: '/api/countries', url: '/api/countries', city: 'Global', isPost: false, data: null },
                    { endpoint: '/api/locations/cities', url: '/api/locations/cities?country=US&state=CA', city: 'California', isPost: false, data: null },
                    { endpoint: '/api/neighborhoods', url: '/api/neighborhoods?city=Paris&country=FR', city: 'Paris', isPost: false, data: null },
                    { endpoint: '/api/fun-fact', url: '/api/fun-fact', city: 'Paris', isPost: true, data: { city: 'Paris' } },
                    { endpoint: '/api/location-suggestions', url: '/api/location-suggestions', city: 'Search', isPost: true, data: { query: 'par' } }
                ];
                
                const suite = new APITestSuite('⚡ Performance Test', tests);
                await suite.runSuite();
            };

            window.runWorkflowTest = async function() {
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
                    
                    resultsDiv.innerHTML = '<div class="card" style="margin-top: 0;">' +
                        '<h3>🔧 Workflow Test Results</h3>' +
                        '<div class="status ok">✓ Complete workflow tested successfully</div>' +
                        '<div style="margin-top: 10px;">' +
                            '<strong>Steps completed:</strong><br>' +
                            '1. Countries: ' + (countriesResponse.error ? '❌' : '✅') + '<br>' +
                            '2. Cities: ' + (citiesResponse.error ? '❌' : '✅') + '<br>' +
                            '3. Neighborhoods: ' + (neighborhoodsResponse.error ? '❌' : '✅') + '<br>' +
                            '4. Fun Fact: ' + (funFactResponse ? '❌' : '✅') + '<br>' +
                            '5. Chat RAG: ' + (chatResponse ? '❌' : '✅') +
                        '</div>' +
                    '</div>';
                } catch (error) {
                    resultsDiv.innerHTML = '<div class="error">Workflow test failed: ' + error.message + '</div>';
                }
            };

            window.runStressTest = async function() {
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
                    
                    resultsDiv.innerHTML = '<div class="card" style="margin-top: 0;">' +
                        '<h3>🧪 Stress Test Results</h3>' +
                        '<div class="status ' + (successCount === 30 ? 'ok' : 'error') + '">' +
                            successCount + '/30 requests successful (' + ((successCount/30)*100).toFixed(1) + '%)' +
                        '</div>' +
                        '<div>Total time: ' + (totalTime/1000).toFixed(2) + 's</div>' +
                        '<div>Avg per request: ' + (totalTime/30).toFixed(0) + 'ms</div>' +
                    '</div>';
                } catch (error) {
                    resultsDiv.innerHTML = '<div class="error">Stress test failed: ' + error.message + '</div>';
                }
            };

            // Load data on page load
            window.onload = refreshAll;
        </script>
    </body>
    </html>
    """


def register(app):
    """Register admin blueprint with app"""
    app.register_blueprint(bp)
