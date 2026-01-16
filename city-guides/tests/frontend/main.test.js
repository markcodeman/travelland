/**
 * Smoke test for city-guides/static/main.js
 * - Loads the script into a JSDOM document
 * - Calls renderCategoryChips() and asserts category chips were rendered
 */

const fs = require('fs');
const path = require('path');
require('isomorphic-fetch');

describe('renderCategoryChips', () => {
  it('renders category buttons into #suggestionChips', () => {
    // Minimal DOM expected by main.js
    const html = `
      <div id="suggestionChips"></div>
      <input id="city" />
      <div id="searchHint"></div>
      <button id="searchBtn"></button>
      <div id="neighborhoodControls"></div>
      <div id="results"></div>
      <div id="marcoFab"></div>
      <div id="marcoChat"></div>
      <div id="chatMessages"></div>
      <div id="chatChips"></div>
    `;

    // Create a JSDOM instance and inject minimal HTML
    const { JSDOM } = require('jsdom');
    const dom = new JSDOM(html, { runScripts: "dangerously", resources: "usable" });
    const window = dom.window;
    const document = window.document;

    // Read the frontend script
    const scriptPath = path.resolve(__dirname, '../../../city-guides/static/main.js');
    const scriptSrc = fs.readFileSync(scriptPath, 'utf8');

    // Inject the script into the JSDOM document so it runs in the page context
    const scriptEl = document.createElement('script');
    scriptEl.textContent = scriptSrc;
    document.body.appendChild(scriptEl);

    // The script defines global functions (renderCategoryChips) in the page context.
    // Give the script a moment to initialize (synchronous append executes immediately).
    const renderFn = window.renderCategoryChips || document.defaultView?.renderCategoryChips;
    expect(typeof renderFn).toBe('function');

    // Call it and assert results in DOM
    renderFn();

    const chips = document.querySelectorAll('.category-chip');
    expect(chips.length).toBeGreaterThan(0);

    // Check the first chip has label text and data-query attribute
    const first = chips[0];
    expect(first.textContent.length).toBeGreaterThan(0);
    expect(first.getAttribute('data-query')).toBeTruthy();
  });

  it('performs search and renders results', async () => {
    // Set up DOM elements required by performSearch
    const html = `
      <div id="suggestionChips"></div>
      <input id="city" value="New York" />
      <input id="user_lat" value="40.743" />
      <input id="user_lon" value="-73.918" />
      <div id="searchHint"></div>
      <button id="searchBtn"></button>
      <div id="neighborhoodControls"></div>
      <div id="results"></div>
      <div id="marcoFab"></div>
      <div id="marcoChat"></div>
      <div id="chatMessages"></div>
      <div id="chatChips"></div>
    `;

    const { JSDOM } = require('jsdom');
    const dom = new JSDOM(html, { runScripts: "dangerously", resources: "usable" });
    const window = dom.window;
    const document = window.document;
    global.window = window;
    global.document = document;

    // Set up fetch for JSDOM
    window.fetch = global.fetch;

    // Set window.location to simulate localhost for API_BASE
    window.location = { hostname: '127.0.0.1', port: '5010', protocol: 'http:' };
    window.TRAVELLAND_API_BASE = 'http://127.0.0.1:5010';

    // Load the script
    const scriptPath = path.resolve(__dirname, '../../../city-guides/static/main.js');
    const scriptSrc = fs.readFileSync(scriptPath, 'utf8');
    const scriptEl = document.createElement('script');
    scriptEl.textContent = scriptSrc;
    document.body.appendChild(scriptEl);

    // Wait for script to initialize
    await new Promise(resolve => setTimeout(resolve, 10));

    console.log('window.performSearch:', typeof window.performSearch);

    // Call renderCategoryChips to create chips
    window.renderCategoryChips();

    // Simulate selecting a category
    window.selectCategory('restaurant');

    // Simulate selecting a neighborhood (Sunnyside)
    window.selectedNeighborhood = {
      id: 'sunnyside',
      name: 'Sunnyside',
      bbox: [-73.935, 40.737, -73.905, 40.757]  // Approximate Sunnyside bbox
    };

    // Call performSearch
    await window.eval('performSearch()');

    // Log the results for debugging
    const resultsEl = document.getElementById('results');
    console.log('Results HTML:', resultsEl.innerHTML.substring(0, 500));

    // Assert results are rendered (check for venue cards or no results message)
    expect(resultsEl.innerHTML).toBeTruthy();
    expect(resultsEl.innerHTML.length).toBeGreaterThan(0);
  });
});