// TravelLand Admin Dashboard JavaScript (migrated from admin.py)
// All functions are attached to window for global access

// Test data sets for different scenarios
const testCityData = {
    global: ['Paris', 'Tokyo', 'New York', 'Sydney', 'Dubai'],
    popular: ['Barcelona', 'Rome', 'London', 'Bangkok', 'Singapore'],
    emerging: ['Mumbai', 'Istanbul', 'Cairo', 'Lagos', 'Jakarta'],
    beach: ['Bali', 'Maldives', 'Cancun', 'Miami', 'Phuket']
};

class PerformanceTracker {
    constructor() { this.timings = {}; }
    startTimer(endpoint) { this.timings[endpoint] = performance.now(); }
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

// --- Health status ---
async function fetchHealth() {
    try {
        const resp = await fetch('/healthz');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        return await resp.json();
    } catch (e) {
        return { error: e.message };
    }
}

async function renderHealthStatus() {
    const container = document.querySelector('.container');
    if (!container) return;
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = '<h2>System Health</h2><div class="loading">Checking health...</div>';
    container.prepend(card);

    const data = await fetchHealth();
    if (data.error) {
        card.innerHTML = `<h2>System Health</h2><div class="error">${data.error}</div>`;
        return;
    }

    const serverTime = data.time ? new Date(data.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'n/a';

    const booleanRows = ['app','ready','redis','geoapify','geonames','groq','unsplash','pixabay']
      .filter(k => k in data)
      .map(k => {
        const val = !!data[k];
        const cls = val ? 'ok' : 'error';
        const label = val ? 'OK' : 'FAIL';
        const name = k.toUpperCase();
        return `<tr><td>${name}</td><td><span class="status ${cls}">${label}</span></td></tr>`;
      }).join('');

    card.innerHTML = `
      <h2>System Health</h2>
      <div style="margin-bottom:10px;">
        <span class="status ${(!data.redis ? 'warning' : 'ok')}">${(!data.redis ? 'Degraded' : 'Healthy')}</span>
        <span style="margin-left:8px; font-size:12px; color:#666;">Server Time: ${serverTime}</span>
      </div>
      <table style="width:100%; border-collapse: collapse;">
        <tr><th style="text-align:left;">Component</th><th style="text-align:left;">Status</th></tr>
        ${booleanRows}
      </table>
    `;
}

// --- Key status ---
async function fetchKeysStatus() {
    try {
        const resp = await fetch('/admin/keys');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        return await resp.json();
    } catch (e) {
        return { ok: false, error: e.message, keys: {}, missing: [] };
    }
}

async function renderKeysStatus() {
    const container = document.querySelector('.container');
    if (!container) return;
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = '<h2>API Keys</h2><div class="loading">Checking keys...</div>';
    container.prepend(card);

    const data = await fetchKeysStatus();
    if (data.error) {
        card.innerHTML = `<h2>API Keys</h2><div class="error">${data.error}</div>`;
        return;
    }

    const rows = Object.entries(data.keys || {}).map(([k, v]) => {
        const cls = v ? 'ok' : 'error';
        const label = v ? 'present' : 'missing';
        return `<tr><td>${k}</td><td><span class="status ${cls}">${label}</span></td></tr>`;
    }).join('');

    card.innerHTML = `
      <h2>API Keys</h2>
      <div style="margin-bottom:10px;">
        <span class="status ${data.ok ? 'ok' : 'warning'}">${data.ok ? 'All present' : 'Missing keys'}</span>
        ${data.missing && data.missing.length ? '<span style="margin-left:8px; font-size:12px; color:#856404;">Missing: ' + data.missing.join(', ') + '</span>' : ''}
      </div>
      <table style="width:100%; border-collapse: collapse;">
        <tr><th style="text-align:left;">Key</th><th style="text-align:left;">Status</th></tr>
        ${rows}
      </table>
    `;
}

class TestResult {
    constructor(endpoint, data, timing, status, city = '') {
        this.endpoint = endpoint;
        this.data = data;
        this.timing = timing;
        this.status = status;
        this.city = city;
        this.timestamp = new Date().toISOString();
    }
    getPerformanceClass() { return tracker.getPerformanceClass(this.timing); }
    isValid() { return this.status === 'ok' && this.data && !this.data.error; }
}

class APITestSuite {
    constructor(name, tests) {
        this.name = name;
        this.tests = tests;
        this.results = [];
    }
    async runSuite() {
        const resultsDiv = document.getElementById('api-results');
        resultsDiv.innerHTML = '<div class="loading">Running ' + this.name + '...</div>';
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
            return new TestResult(test.endpoint, data, response.ok ? 'ok' : 'error', timing, test.city);
        } catch (error) {
            const timing = tracker.endTimer(test.endpoint);
            return new TestResult(test.endpoint, { error: error.message }, 'error', timing, test.city);
        }
    }
    displayResults(totalTime) {
        const resultsDiv = document.getElementById('api-results');
        let html = '<div class="card" style="margin-top: 0;">' +
            '<h3>' + this.name + ' Results (' + this.results.length + ' tests, ' + (totalTime/1000).toFixed(2) + 's)</h3>';
        const successCount = this.results.filter(r => r.isValid()).length;
        const avgTime = this.results.reduce((sum, r) => sum + r.timing, 0) / this.results.length;
        html += '<div style="margin-bottom: 15px;">' +
            '<span class="status ok">OK ' + successCount + ' Success</span>' +
            '<span class="status error">✗ ' + (this.results.length - successCount) + ' Failed</span>' +
            '<span>Avg: ' + avgTime.toFixed(0) + 'ms</span>' +
        '</div>';
        html += '<table style="width: 100%; border-collapse: collapse;">';
        html += '<tr><th>Endpoint</th><th>City</th><th>Status</th><th>Time</th><th>Result</th></tr>';
        this.results.forEach(result => {
            const perfClass = result.getPerformanceClass();
            const statusClass = result.isValid() ? 'ok' : 'error';
            const statusText = result.isValid() ? 'OK' : 'FAIL';
            html += '<tr>' +
                '<td>' + result.endpoint + '</td>' +
                '<td>' + result.city + '</td>' +
                '<td><span class="status ' + statusClass + '">' + statusText + '</span></td>' +
                '<td class="' + perfClass + '">' + Number(result.timing).toFixed(0) + 'ms</td>' +
                '<td><button onclick="showTestResult(\'' + result.endpoint + '\', \'" + result.city + "\')" style="font-size: 11px;">View</button></td>' +
            '</tr>';
        });
        html += '</table>';
        html += '<button onclick="exportResults()" style="margin-top: 10px;">Export Results</button>';
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
        localStorage.setItem('apiTestHistory', JSON.stringify(history.slice(-20)));
    }
}

// --- Test functions ---
async function runGlobalTest() {
    const tests = [];
    testCityData.global.forEach(city => {
        tests.push(
            { endpoint: '/api/locations/cities', url: '/api/locations/cities?country=US&state=CA', city, isPost: false, data: null },
            { endpoint: '/api/neighborhoods', url: '/api/neighborhoods?city=' + city + '&country=' + (city === 'New York' ? 'US' : 'FR'), city, isPost: false, data: null },
            { endpoint: '/api/fun-fact', url: '/api/fun-fact', city, isPost: true, data: { city: city } }
        );
    });
    const suite = new APITestSuite('Global Test', tests);
    await suite.runSuite();
}

async function runPerformanceTest() {
    const tests = [
        { endpoint: '/api/countries', url: '/api/countries', city: 'Global', isPost: false, data: null },
        { endpoint: '/api/locations/cities', url: '/api/locations/cities?country=US&state=CA', city: 'California', isPost: false, data: null },
        { endpoint: '/api/neighborhoods', url: '/api/neighborhoods?city=Paris&country=FR', city: 'Paris', isPost: false, data: null },
        { endpoint: '/api/fun-fact', url: '/api/fun-fact', city: 'Paris', isPost: true, data: { city: 'Paris' } },
        { endpoint: '/api/location-suggestions', url: '/api/location-suggestions', city: 'Search', isPost: true, data: { query: 'par' } }
    ];
    const suite = new APITestSuite('Performance Test', tests);
    await suite.runSuite();
}

async function runWorkflowTest() {
    const resultsDiv = document.getElementById('api-results');
    resultsDiv.innerHTML = '<div class="loading">Testing complete workflow (real frontend flow)...</div>';
    try {
        // 1. Fetch countries
        const countries = await fetchData('/api/countries');
        const country = Array.isArray(countries) && countries.length > 0 ? countries[0] : { code: 'US' };
        // 2. Fetch states for that country
        const states = await fetchData(`/api/locations/states?countryCode=${country.code}`);
        const state = Array.isArray(states) && states.length > 0 ? states[0] : { code: 'CA' };
        // 3. Fetch cities for that state
        const cities = await fetchData(`/api/locations/cities?countryCode=${country.code}&stateCode=${state.code}`);
        const city = Array.isArray(cities) && cities.length > 0 ? cities[0] : { name: 'Paris' };
        // 4. Fetch neighborhoods for that city
        const neighborhoods = await fetchData(`/api/neighborhoods?city=${encodeURIComponent(city.name)}&country=${country.code}`);
        // 5. Fetch fun fact for that city
        const funFact = await fetchData('/api/fun-fact', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ city: city.name })
        });
        // 6. Fetch chat RAG for that city
        const chat = await fetchData('/api/chat/rag', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: `Hello, can you tell me about ${city.name}?`,
                city: city.name,
                country: country.code
            })
        });
        resultsDiv.innerHTML = '<div class="card" style="margin-top: 0;">' +
            '<h3>Workflow Test Results (Real API Flow)</h3>' +
            '<div class="status ok">OK Complete workflow tested as frontend would</div>' +
            '<div style="margin-top: 10px;">' +
                '<strong>Steps completed:</strong><br>' +
                '1. Countries: ' + (countries.error ? 'FAIL' : 'OK') + '<br>' +
                '<pre class="json-data">' + JSON.stringify(countries, null, 2) + '</pre>' +
                '2. States: ' + (states.error ? 'FAIL' : 'OK') + '<br>' +
                '<pre class="json-data">' + JSON.stringify(states, null, 2) + '</pre>' +
                '3. Cities: ' + (cities.error ? 'FAIL' : 'OK') + '<br>' +
                '<pre class="json-data">' + JSON.stringify(cities, null, 2) + '</pre>' +
                '4. Neighborhoods: ' + (neighborhoods.error ? 'FAIL' : 'OK') + '<br>' +
                '<pre class="json-data">' + JSON.stringify(neighborhoods, null, 2) + '</pre>' +
                '5. Fun Fact: ' + (funFact.error ? 'FAIL' : 'OK') + '<br>' +
                '<pre class="json-data">' + JSON.stringify(funFact, null, 2) + '</pre>' +
                '6. Chat RAG: ' + (chat.error ? 'FAIL' : 'OK') + '<br>' +
                '<pre class="json-data">' + JSON.stringify(chat, null, 2) + '</pre>' +
            '</div>' +
        '</div>';
    } catch (error) {
        resultsDiv.innerHTML = '<div class="error">Workflow test failed: ' + error.message + '</div>';
    }
}

async function runStressTest() {
    const resultsDiv = document.getElementById('api-results');
    resultsDiv.innerHTML = '<div class="loading">Running stress test...</div>';
    const startTime = performance.now();
    const promises = [];
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
            '<h3>Stress Test Results</h3>' +
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

// --- Utility and manual test functions ---
function exportResults() {
    const history = JSON.parse(localStorage.getItem('apiTestHistory') || '[]');
    const csv = 'Timestamp,Suite,Endpoint,City,Status,Time (ms)\n' +
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

function showTestResult(endpoint, city) {
    const history = JSON.parse(localStorage.getItem('apiTestHistory') || '[]');
    const result = history.flatMap(h => h.results).find(r => r.endpoint === endpoint && r.city === city);
    if (result) {
        alert('Endpoint: ' + result.endpoint + '\nCity: ' + result.city + '\nStatus: ' + result.status + '\nTime: ' + result.timing + 'ms');
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
    html += '<div class="status ' + status + '">' + (status === 'ok' ? 'SUCCESS' : 'ERROR') + '</div>';
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
        html += '<div class="status ' + status + '">' + (status === 'ok' ? 'SUCCESS' : 'ERROR') + '</div>';
        html += '<div class="json-data">' + JSON.stringify(data, null, 2) + '</div>';
        html += '</div>';
        resultsDiv.innerHTML = html;
    } catch (error) {
        resultsDiv.innerHTML = '<div class="card" style="margin-top: 0;"><h3>Test Result: Chat RAG</h3><div class="status error">ERROR</div><div class="error">Error: ' + error.message + '</div></div>';
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
        const statusText = value ? 'OK' : 'FAIL';
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
    const counters = data.counters || {};
    const latencies = data.latencies || {};
    const totalRequests = Object.values(counters).reduce((a, b) => a + b, 0);
    const searchRequests = Object.entries(counters).filter(([k]) => k.includes('req.api.search')).reduce((a, [, v]) => a + v, 0);
    const chatRequests = Object.entries(counters).filter(([k]) => k.includes('req.api.chat')).reduce((a, [, v]) => a + v, 0);
    const errorCount = Object.entries(counters).filter(([k]) => k.includes('.status.500')).reduce((a, [, v]) => a + v, 0);

    const topEndpoints = Object.entries(counters)
      .filter(([k]) => k.startsWith('req.') && k.endsWith('.count'))
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);

    let html = '<div class="metrics">';
    [
      { label: 'Total Requests', value: totalRequests },
      { label: 'Search Requests', value: searchRequests },
      { label: 'Chat Requests', value: chatRequests },
      { label: '5xx Errors', value: errorCount }
    ].forEach(m => {
      html += '<div class="metric"><div class="value">' + m.value + '</div><div class="label">' + m.label + '</div></div>';
    });
    html += '</div>';

    if (topEndpoints.length) {
      html += '<div class="card" style="margin-top:10px;"><h3>Top Endpoints</h3><table style="width:100%; border-collapse: collapse;">';
      html += '<tr><th style="text-align:left;">Endpoint</th><th style="text-align:left;">Count</th></tr>';
      topEndpoints.forEach(([k, v]) => {
        const name = k.replace('req.', '').replace('.count', '').replace(/\./g, '/');
        html += `<tr><td>${name}</td><td>${v}</td></tr>`;
      });
      html += '</table></div>';
    }

    if (Object.keys(latencies).length) {
      html += '<div class="card" style="margin-top:10px;"><h3>Latency (p50)</h3><table style="width:100%; border-collapse: collapse;">';
      html += '<tr><th style="text-align:left;">Endpoint</th><th style="text-align:left;">p50 ms</th><th style="text-align:left;">Count</th></tr>';
      Object.entries(latencies).slice(0, 8).forEach(([k, v]) => {
        const name = k.replace('req.', '').replace('.latency_ms', '').replace(/\./g, '/');
        html += `<tr><td>${name}</td><td>${v.p50_ms?.toFixed ? v.p50_ms.toFixed(0) : v.p50_ms}</td><td>${v.count}</td></tr>`;
      });
      html += '</table></div>';
    }

    html += '<details style="margin-top: 15px;"><summary>Raw Metrics Data</summary>';
    html += '<pre class="json-data">' + JSON.stringify(data, null, 2) + '</pre>';
    html += '</details>';
    return html;
}

function formatSmoke(data) {
    if (data.error) return '<div class="error">Smoke test failed: ' + data.error + '</div>';
    const header = `<div class="status ${data.ok ? 'ok' : 'warning'}">${data.ok ? 'PASS' : 'WARN'}</div>`;
    const meta = `<div style="color:#555; margin-bottom:8px;">Cities: ${data.cities_tested || 0} | Regions: ${(data.regions_tested || []).join(', ')}</div>`;
    const cards = (data.results || []).map(r => {
        const n = r.tests?.neighborhoods || {};
        const rev = r.tests?.reverse_geocoding || {};
        return `
          <div class="card" style="margin-top:10px;">
            <h3>${r.city} (${r.region})</h3>
            <div style="display:flex; gap:12px; flex-wrap:wrap; font-size:14px;">
              <div><strong>Neighborhoods:</strong> <span class="status ${n.status || 'warning'}">${n.status || 'unknown'}</span> • ${n.count || 0} found${n.first_neighborhood ? ` • first: ${n.first_neighborhood}` : ''} • ${n.time_ms ? `${n.time_ms.toFixed ? n.time_ms.toFixed(0) : n.time_ms} ms` : ''}</div>
              <div><strong>Reverse geocode:</strong> <span class="status ${rev.status || 'warning'}">${rev.status || 'unknown'}</span> • ${rev.provider || ''} • ${rev.time_ms ? `${rev.time_ms.toFixed ? rev.time_ms.toFixed(0) : rev.time_ms} ms` : ''}</div>
            </div>
          </div>`;
    }).join('');
    return `<div class="card"><h2>Smoke Test</h2>${header}${meta}${cards}</div>`;
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
// Attach all functions to window for global access
window.runGlobalTest = runGlobalTest;
window.runPerformanceTest = runPerformanceTest;
window.runWorkflowTest = runWorkflowTest;
window.runStressTest = runStressTest;
window.testChatRAG = testChatRAG;
window.testCities = testCities;
window.testNeighborhoods = testNeighborhoods;
window.testFunFact = testFunFact;
window.testEndpoint = testEndpoint;
window.exportResults = exportResults;
window.showTestResult = showTestResult;
window.fetchData = fetchData;
window.loadHealth = loadHealth;
window.loadMetrics = loadMetrics;
window.loadSmoke = loadSmoke;
window.refreshAll = refreshAll;
window.onload = refreshAll;
