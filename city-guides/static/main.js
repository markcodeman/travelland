// ============================================================
// TRAVELLAND - Main JavaScript
// Flow: City → Neighborhood → Category → Search
// ============================================================

const DEFAULT_IMAGE = '/static/img/placeholder.png';
const API_BASE = (() => {
  try {
    if (window.TRAVELLAND_API_BASE) return String(window.TRAVELLAND_API_BASE).replace(/\/$/, '');
    const isLocalhost = ['127.0.0.1', 'localhost'].includes(window.location.hostname);
    const port = window.location.port;
    if (isLocalhost && port && port !== '5010') return 'http://127.0.0.1:5010';
  } catch (e) { }
  return '';
})();

// ============================================================
// GLOBAL STATE
// ============================================================
let selectedCity = null;
let selectedNeighborhood = null;
let selectedCategory = null;
let currentVenues = [];
let currentWeather = null;

// ============================================================
// CATEGORY CHIPS (Step 3)
// ============================================================
const CATEGORIES = [
  { label: "🍽️ Top food", query: "restaurant", color: "orange" },
  { label: "🏛️ Historic sites", query: "historic", color: "amber" },
  { label: "🚍 Public transport", query: "transport", color: "blue" },
  { label: "🛒 Local markets", query: "market", color: "green" },
  { label: "👪 Family friendly", query: "family", color: "pink" },
  { label: "🎉 Popular events", query: "event", color: "purple" },
  { label: "💎 Hidden gems", query: "hidden", color: "indigo" },
  { label: "☕ Coffee & tea", query: "coffee", color: "yellow" },
  { label: "🌳 Parks & nature", query: "park", color: "emerald" }
];

function renderCategoryChips() {
  const container = document.getElementById('suggestionChips');
  if (!container) return;

  container.innerHTML = CATEGORIES.map(cat => `
    <button 
      type="button"
      class="category-chip px-3 py-2 rounded-full text-sm font-medium border-2 transition-all
             bg-${cat.color}-50 border-${cat.color}-200 text-${cat.color}-700
             hover:bg-${cat.color}-100 hover:border-${cat.color}-400"
      data-query="${cat.query}"
    >
      ${cat.label}
    </button>
  `).join('');

  container.querySelectorAll('.category-chip').forEach(chip => {
    chip.addEventListener('click', (e) => {
      selectCategory(e.target.dataset.query, e.target);
    });
  });
}

function selectCategory(query, chipElement) {
  document.querySelectorAll('.category-chip').forEach(c => {
    c.classList.remove('ring-2', 'ring-offset-2', 'ring-blue-500', 'bg-blue-500', 'text-white');
  });

  if (chipElement) {
    chipElement.classList.add('ring-2', 'ring-offset-2', 'ring-blue-500');
  }

  selectedCategory = query;

  const queryInput = document.getElementById('query');
  if (queryInput) queryInput.value = query;

  console.log('[Category] Selected:', query);
  updateSearchButtonState();
  
  // Auto-search if neighborhood is selected
  if (selectedNeighborhood) {
    performSearch();
  }
}

function disableCategoryChips() {
  const container = document.getElementById('suggestionChips');
  if (container) {
    container.style.opacity = '0.4';
    container.style.pointerEvents = 'none';
  }
  selectedCategory = null;
  document.querySelectorAll('.category-chip').forEach(c => {
    c.classList.remove('ring-2', 'ring-offset-2', 'ring-blue-500');
  });
  updateSearchButtonState();
}

function enableCategoryChips() {
  const container = document.getElementById('suggestionChips');
  if (container) {
    container.style.opacity = '1';
    container.style.pointerEvents = 'auto';
  }
}

// ============================================================
// CITY SEARCH (Step 1)
// ============================================================
const cityInput = document.getElementById('city');
const suggestionsEl = document.getElementById('city-suggestions');

function hideCitySuggestions() {
  if (suggestionsEl) {
    suggestionsEl.style.display = 'none';
    suggestionsEl.classList.add('hidden');
  }
}

function showCitySuggestions(items) {
  if (!suggestionsEl || !items || items.length === 0) {
    hideCitySuggestions();
    return;
  }

  window._citySuggestions = items;
  suggestionsEl.innerHTML = items.map(it => `
    <div class="suggestion-item px-4 py-3 hover:bg-blue-50 cursor-pointer border-b border-gray-100 last:border-0" 
         data-lat="${it.lat}" data-lon="${it.lon}">
      <span class="text-gray-800">${it.display_name}</span>
    </div>
  `).join('');
  suggestionsEl.style.display = 'block';
  suggestionsEl.classList.remove('hidden');
}

async function fetchCitySuggestions(q) {
  const url = `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=6&accept-language=en&q=${encodeURIComponent(q)}`;
  const resp = await fetch(url, {
    headers: { 'Accept': 'application/json', 'User-Agent': 'city-guides/1.0' }
  });
  return resp.json();
}

// City input listeners (only if element exists)
if (cityInput) {
  console.log('[Init] City input found, attaching listeners');
  let debounceTimer = null;

  cityInput.addEventListener('input', (e) => {
    const v = e.target.value.trim();
    if (debounceTimer) clearTimeout(debounceTimer);

    if (!v || v.length < 3) {
      hideCitySuggestions();
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const items = await fetchCitySuggestions(v);
        showCitySuggestions(items);
      } catch (err) {
        console.warn('Nominatim error', err);
        hideCitySuggestions();
      }
    }, 300);
  });

  document.addEventListener('click', (ev) => {
    const el = ev.target.closest('.suggestion-item');

    if (el) {
      const lat = el.dataset.lat;
      const lon = el.dataset.lon;
      const items = window._citySuggestions || [];
      const selected = items.find(it => it.lat === lat && it.lon === lon);

      let cityCountry = el.textContent.trim();

      if (selected?.address) {
        const addr = selected.address;
        const city = addr.city || addr.town || addr.village || addr.hamlet || addr.county || addr.state || '';
        const country = addr.country || '';
        if (city && country) cityCountry = `${city}, ${country}`;
        else if (city) cityCountry = city;
      }

      cityInput.value = cityCountry;
      selectedCity = { name: cityCountry, lat, lon };
      hideCitySuggestions();

      document.getElementById('user_lat').value = lat;
      document.getElementById('user_lon').value = lon;

      console.log('[City] Selected:', cityCountry);

      disableCategoryChips();
      fetchAndRenderNeighborhoods(cityCountry, lat, lon);
      updateSearchButtonState();

    } else if (ev.target !== cityInput && !ev.target.closest('#city-suggestions')) {
      hideCitySuggestions();
    }
  });
} // <-- IF BLOCK ENDS HERE - Functions below are GLOBAL

// ============================================================
// NEIGHBORHOOD DISCOVERY (Step 2) - GLOBAL SCOPE
// ============================================================
async function fetchAndRenderNeighborhoods(city, lat, lon) {
  console.log('[Fetch] Starting fetch for city:', city, 'lat:', lat, 'lon:', lon);
  const container = document.getElementById('neighborhoodControls');
  if (!container) {
    console.error('[Fetch] Container not found');
    return;
  }

  container.classList.remove('hidden');
  container.innerHTML = `
    <div class="flex items-center text-gray-500 text-sm">
      <svg class="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      Loading neighborhoods...
    </div>
  `;

  try {
    let url = `${API_BASE}/neighborhoods?`;
    if (city) url += `city=${encodeURIComponent(city)}&`;
    if (lat && lon) url += `lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`;

    const resp = await fetch(url);
    if (!resp.ok) throw new Error('Failed to fetch neighborhoods');

    const data = await resp.json();
    const neighborhoods = data.neighborhoods || [];
    console.log('[Fetch] Fetched neighborhoods:', neighborhoods);

    renderNeighborhoodDiscovery(neighborhoods, city);
    enableCategoryChips();

  } catch (err) {
    console.warn('[Neighborhoods] Fetch failed:', err);
    container.innerHTML = `
      <p class="text-gray-500 text-sm">
        Couldn't load neighborhoods. You can still search all areas!
      </p>
    `;
    selectedNeighborhood = 'all';
    enableCategoryChips();
    updateSearchButtonState();
  }
}

function renderNeighborhoodDiscovery(neighborhoods, cityName) {
  const container = document.getElementById('neighborhoodControls');
  if (!container) return;

  const count = neighborhoods.length;
  const displayCity = cityName?.split(',')[0] || 'this city';

  if (count === 0) {
    container.innerHTML = `
      <div class="neighborhood-discovery bg-gray-50 rounded-lg p-4">
        <p class="text-sm font-medium text-gray-700 mb-2">🏘️ Explore ${displayCity}</p>
        <p class="text-xs text-gray-500 mb-3">
          No specific neighborhoods found for this city in our data. You can still search the entire area!
        </p>
        <div class="marco-help mt-3 pt-4 border-t border-gray-200">
          <div class="flex items-center justify-between">
            <p class="text-sm text-gray-700">🤔 Not sure where to go?</p>
            <button type="button" id="askMarcoBtn" class="ml-3 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md font-semibold shadow">Ask Marco for a recommendation →</button>
          </div>
        </div>
      </div>
    `;
    selectedNeighborhood = 'all';
    updateSearchButtonState();
    return;
  }

  container.innerHTML = `
    <div class="neighborhood-discovery bg-gray-50 rounded-lg p-4">
      <p class="text-sm font-medium text-gray-700 mb-3">🏘️ Explore ${displayCity}</p>
      
      <div class="neighborhood-presets flex flex-wrap gap-2 mb-3">
        <button type="button" class="preset-btn px-3 py-1.5 rounded-full text-xs font-medium border transition bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100" data-filter="tourist">🎯 Tourist Hotspots</button>
        <button type="button" class="preset-btn px-3 py-1.5 rounded-full text-xs font-medium border transition bg-green-50 border-green-200 text-green-700 hover:bg-green-100" data-filter="local">🏠 Local Vibes</button>
        <button type="button" class="preset-btn px-3 py-1.5 rounded-full text-xs font-medium border transition bg-orange-50 border-orange-200 text-orange-700 hover:bg-orange-100" data-filter="food">🍽️ Foodie Areas</button>
        <button type="button" class="preset-btn px-3 py-1.5 rounded-full text-xs font-medium border transition bg-purple-50 border-purple-200 text-purple-700 hover:bg-purple-100" data-filter="nightlife">🌙 Nightlife</button>
        <button type="button" class="preset-btn px-3 py-1.5 rounded-full text-xs font-medium border transition bg-teal-50 border-teal-200 text-teal-700 hover:bg-teal-100" data-filter="budget">💰 Budget-Friendly</button>
      </div>
      
      <div id="neighborhoodSuggestion" class="hidden mb-3"></div>
      
      <div class="neighborhood-dropdown">
        <label class="text-xs text-gray-500 mb-1 block">Or choose a specific area:</label>
        <select id="neighborhoodSelect" class="w-full md:w-80 p-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 bg-white">
          <option value="all">🌐 All Areas (${count} neighborhoods)</option>
          ${neighborhoods.map(n => `<option value='${JSON.stringify(n).replace(/'/g, "&#39;")}'>${n.name}</option>`).join('')}
        </select>
      </div>
      
      <div class="marco-help mt-3 pt-4 border-t border-gray-200">
        <div class="flex items-center justify-between">
          <p class="text-sm text-gray-700">🤔 Not sure where to go?</p>
          <button type="button" id="askMarcoBtn" class="ml-3 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md font-semibold shadow">Ask Marco for a recommendation →</button>
        </div>
      </div>
    </div>
  `;

  window._neighborhoodData = neighborhoods;

  const select = document.getElementById('neighborhoodSelect');
  if (select) {
    select.addEventListener('change', async (e) => {
      clearPresetSelection();
      const val = e.target.value;
      if (val === 'all') {
        selectedNeighborhood = 'all';
      } else {
        try { selectedNeighborhood = JSON.parse(val); }
        catch (err) { selectedNeighborhood = 'all'; }
      }
      console.log('[Neighborhood] Selected:', selectedNeighborhood === 'all' ? 'All Areas' : selectedNeighborhood?.name);
      updateSearchButtonState();
      
      // Auto-search if category is selected
      if (selectedCategory) {
        await performSearch();
      }
    });
  }

  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      handlePresetClick(e.target.dataset.filter, neighborhoods);
    });
  });

  const marcoBtn = document.getElementById('askMarcoBtn');
  if (marcoBtn) {
    marcoBtn.addEventListener('click', () => openMarcoWithNeighborhoodQuestion(displayCity));
  }

  selectedNeighborhood = 'all';
  updateSearchButtonState();
}

function handlePresetClick(filter, neighborhoods) {
  clearPresetSelection();

  const btn = document.querySelector(`.preset-btn[data-filter="${filter}"]`);
  if (btn) btn.classList.add('ring-2', 'ring-offset-1', 'ring-blue-500');

  const keywords = {
    tourist: ['centro', 'center', 'old town', 'historic', 'downtown', 'central', 'plaza', 'cathedral'],
    local: ['residential', 'village', 'local', 'authentic', 'traditional', 'bairro', 'barrio'],
    food: ['market', 'mercado', 'food', 'gastro', 'chinatown'],
    nightlife: ['night', 'club', 'bar', 'party', 'soho'],
    budget: ['student', 'university', 'budget', 'affordable']
  }[filter] || [];

  let matches = neighborhoods.filter(n => keywords.some(kw => n.name.toLowerCase().includes(kw)));
  if (matches.length === 0) matches = neighborhoods.slice(0, 3);

  showNeighborhoodSuggestion(filter, matches);
}

function showNeighborhoodSuggestion(filter, matches) {
  const labels = {
    tourist: '🎯 Tourist Hotspots',
    local: '🏠 Local Vibes',
    food: '🍽️ Foodie Areas',
    nightlife: '🌙 Nightlife',
    budget: '💰 Budget-Friendly'
  };

  const container = document.getElementById('neighborhoodSuggestion');
  if (!container) return;

  container.classList.remove('hidden');
  container.innerHTML = `
    <div class="bg-blue-50 rounded-lg p-3 border border-blue-200">
      <p class="text-sm font-medium text-blue-800 mb-2">${labels[filter]} - Try these:</p>
      <div class="flex flex-wrap gap-2">
        ${matches.slice(0, 5).map(n => `
          <button type="button" class="suggestion-chip px-3 py-1 rounded-full text-sm bg-white border border-blue-300 hover:bg-blue-100 text-blue-700 transition" data-neighborhood='${JSON.stringify(n).replace(/'/g, "&#39;")}'>${n.name}</button>
        `).join('')}
      </div>
    </div>
  `;

  container.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', (e) => {
      const data = e.target.dataset.neighborhood;
      try {
        selectedNeighborhood = JSON.parse(data);
        const select = document.getElementById('neighborhoodSelect');
        if (select) select.value = data;

        container.querySelectorAll('.suggestion-chip').forEach(c => {
          c.classList.remove('bg-blue-500', 'text-white');
          c.classList.add('bg-white', 'text-blue-700');
        });
        e.target.classList.remove('bg-white', 'text-blue-700');
        e.target.classList.add('bg-blue-500', 'text-white');

        console.log('[Neighborhood] Selected from suggestion:', selectedNeighborhood.name);
        updateSearchButtonState();
      } catch (err) {
        console.warn('Failed to parse neighborhood', err);
      }
    });
  });
}

function clearPresetSelection() {
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.classList.remove('ring-2', 'ring-offset-1', 'ring-blue-500');
  });
  const suggestion = document.getElementById('neighborhoodSuggestion');
  if (suggestion) suggestion.classList.add('hidden');
}

function openMarcoWithNeighborhoodQuestion(cityName) {
  const marcoChat = document.getElementById('marcoChat');
  if (marcoChat) marcoChat.classList.add('open');

  const chatInput = document.getElementById('chatInput');
  if (chatInput) {
    chatInput.value = `I'm visiting ${cityName} but don't know the neighborhoods. What area would you recommend?`;
    chatInput.focus();
    // Ensure input and send button are enabled so user can send the prefilled question
    chatInput.disabled = false;
    const chatSend = document.getElementById('chatSend');
    if (chatSend) chatSend.disabled = false;
  }
}

// ============================================================
// SEARCH BUTTON STATE - GLOBAL SCOPE
// ============================================================
function updateSearchButtonState() {
  const searchBtn = document.getElementById('searchBtn');
  const searchHint = document.getElementById('searchHint');
  const cityInputEl = document.getElementById('city');

  const hasCity = selectedCity !== null || (cityInputEl && cityInputEl.value.trim().length > 0);
  const hasCategory = selectedCategory !== null;

  const canSearch = hasCity && hasCategory;

  if (searchBtn) searchBtn.disabled = !canSearch;

  if (searchHint) {
    if (!hasCity) {
      searchHint.textContent = '👆 Start by entering a city above';
    } else if (!hasCategory) {
      searchHint.textContent = '👆 Now pick what you\'re looking for';
    } else {
      searchHint.textContent = '✅ Ready to search!';
    }
  }
}

// ============================================================
// SEARCH HANDLER - GLOBAL SCOPE
// ============================================================
document.getElementById('searchBtn')?.addEventListener('click', async () => {
  await performSearch();
});

// Extracted search function
async function performSearch() {
  const cityInputEl = document.getElementById('city');
  const city = cityInputEl?.value?.trim() || '';
  const query = selectedCategory || '';
  const lat = document.getElementById('user_lat')?.value;
  const lon = document.getElementById('user_lon')?.value;

  console.log('[Search] selectedNeighborhood:', selectedNeighborhood);

  if (!city || !query) {
    alert('Please select a city and category');
    return;
  }

  const resEl = document.getElementById('results');
  if (!resEl) return;

  resEl.innerHTML = `
    <div class="flex items-center justify-center py-12">
      <svg class="animate-spin h-8 w-8 text-blue-500 mr-3" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      <span class="text-gray-600">Searching for ${query} in ${selectedNeighborhood && selectedNeighborhood !== 'all' ? selectedNeighborhood.name + ', ' + city : city}...</span>
    </div>
  `;

  try {
    const payload = {
      city,
      q: query,
      user_lat: lat,
      user_lon: lon,
      max_results: 15,
      // reduce timeout to prefer faster responses; providers will return partial results
      timeout: 12
    };

    if (selectedNeighborhood && selectedNeighborhood !== 'all') {
      payload.neighborhood = {
        id: selectedNeighborhood.id,
        bbox: selectedNeighborhood.bbox
      };
    }

    const resp = await fetch(`${API_BASE}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!resp.ok) throw new Error(`Search failed (HTTP ${resp.status})`);

    const data = await resp.json();
    renderResults(data, city);

  } catch (err) {
    resEl.innerHTML = `<div class="text-red-500 p-4">Error: ${err.message}</div>`;
  }
}

// ============================================================
// RESULTS RENDERING - GLOBAL SCOPE
// ============================================================
function renderResults(data, city) {
  const resEl = document.getElementById('results');
  if (!resEl || !data.venues) return;

  const venues = data.venues;
  currentVenues = venues;
  
  // Update Marco chat state based on whether venues were found
  const chatInput = document.getElementById('chatInput');
  const chatSend = document.getElementById('chatSend');
  
  if (venues.length === 0) {
    // Disable Marco when no results
    const marcoFab = document.getElementById('marcoFab');
    if (marcoFab) marcoFab.classList.add('hidden');
    
    if (chatInput) {
      chatInput.disabled = true;
      chatInput.placeholder = 'No venues found - try another category';
    }
    if (chatSend) chatSend.disabled = true;
    if (window.updateChatChips) window.updateChatChips(); // Disable chips too
    
    resEl.innerHTML = '<div class="text-gray-500 p-4 text-center"><p>No results found in our data sources.</p><p class="text-sm mt-2">Try a different category or check <a href="https://maps.google.com" target="_blank" class="text-blue-600 hover:underline">Google Maps</a> for more options.</p></div>';
    return;
  }
  
  // Enable Marco when venues are loaded
  const marcoFab = document.getElementById('marcoFab');
  if (marcoFab) marcoFab.classList.remove('hidden');
  
  if (chatInput) {
    chatInput.disabled = false;
    chatInput.placeholder = 'Ask me anything about these venues...';
  }
  if (chatSend) chatSend.disabled = false;
  if (window.updateChatChips) window.updateChatChips(); // Enable chips too

  resEl.innerHTML = `
    <div class="results-header mb-4">
      <h2 class="text-lg font-semibold text-gray-800">Found ${venues.length} places</h2>
    </div>
    <div class="results-grid">
      ${venues.map(v => renderVenueCard(v, city)).join('')}
    </div>
  `;
}

function getGoogleMapsUrl(venue, cityName) {
  const city = cityName?.split(',')[0]?.trim() || '';
  const country = cityName?.split(',')[1]?.trim() || '';

  if (venue.name && venue.name !== 'Unnamed') {
    const searchQuery = [venue.name, city, country].filter(Boolean).join(' ');
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(searchQuery)}`;
  }

  if (venue.lat && venue.lon) {
    return `https://www.google.com/maps?q=${venue.lat},${venue.lon}`;
  }

  return null;
}

function renderVenueCard(v, city) {
  const imgUrl = v.image || v.banner_url || v.thumbnail || DEFAULT_IMAGE;
  const mapsUrl = getGoogleMapsUrl(v, city || v.city);

  let addressHtml = '';
  if (v.display_address) {
    addressHtml = `<p class="text-sm text-gray-500 mb-2">📍 ${v.display_address}</p>`;
  }

  return `
    <div class="venue-card bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition">
      <img src="${imgUrl}" alt="${v.name}" class="w-full h-40 object-cover" onerror="this.src='${DEFAULT_IMAGE}'"/>
      <div class="p-4">
        <h3 class="font-semibold text-gray-800 mb-1">${v.name}</h3>
        ${addressHtml}
        ${v.description ? `<p class="text-sm text-gray-600 mb-3 line-clamp-2">${v.description}</p>` : ''}
        <div class="flex flex-wrap gap-2 mt-2">
          ${v.website ? `<a href="${v.website}" target="_blank" class="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100">🌐 Website</a>` : ''}
          ${mapsUrl ? `<a href="${mapsUrl}" target="_blank" class="text-xs px-2 py-1 bg-green-50 text-green-600 rounded hover:bg-green-100">🗺️ Directions</a>` : ''}
          ${v.phone ? `<a href="tel:${v.phone}" class="text-xs px-2 py-1 bg-gray-50 text-gray-600 rounded hover:bg-gray-100">📞 Call</a>` : ''}
        </div>
      </div>
    </div>
  `;
}

// ============================================================
// INITIALIZE - GLOBAL SCOPE
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  renderCategoryChips();
  updateSearchButtonState();

  // Chat functionality
  const marcoFab = document.getElementById('marcoFab');
  const marcoChat = document.getElementById('marcoChat');
  const closeChat = document.getElementById('closeChat');
  const chatInput = document.getElementById('chatInput');
  const chatSend = document.getElementById('chatSend');
  const chatMessages = document.getElementById('chatMessages');

  // Hide Marco FAB initially - only show after venues are found
  if (marcoFab) {
    marcoFab.classList.add('hidden');
    marcoFab.addEventListener('click', () => {
      marcoChat.classList.add('open');
    });
  }

  if (closeChat) {
    closeChat.addEventListener('click', () => {
      marcoChat.classList.remove('open');
    });
  }

  function sendChatMessage() {
    console.log('Send button clicked');
    const message = chatInput.value.trim();
    if (!message) return;

    // Allow sending even when venues are not yet loaded. The backend can respond without venue context.

    // Add user message
    addChatMessage('user', message);
    chatInput.value = '';

    // Send to backend with a typing indicator while waiting
    const typingId = showBotTyping();
    fetch(`${API_BASE}/semantic-search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        q: message,
        city: selectedCity?.name || document.getElementById('city')?.value?.trim(),
        venues: currentVenues.slice(0, 10), // Send current venues context
        weather: currentWeather
      })
    })
    .then(resp => resp.json())
    .then(data => {
      removeBotTyping(typingId);
      addChatMessage('bot', data.answer || 'Sorry, I couldn\'t process that.');
      // If backend returned neighborhood suggestions, render them as quick chips
      if (data.neighborhoods && Array.isArray(data.neighborhoods) && data.neighborhoods.length > 0) {
        renderChatNeighborhoodSuggestions(data.neighborhoods);
      }
    })
    .catch(err => {
      removeBotTyping(typingId);
      console.error('Chat error:', err);
      addChatMessage('bot', 'Error: ' + err.message);
    });
  }

  if (chatSend) {
    console.log('Chat send button found');
    chatSend.addEventListener('click', sendChatMessage);
    chatSend.disabled = true; // Initially disabled until venues loaded
  } else {
    console.log('Chat send button not found');
  }

  if (chatInput) {
    chatInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendChatMessage();
    });
    // Initially disabled - enable only when venues are loaded
    chatInput.disabled = true;
    chatInput.placeholder = 'Select a neighborhood first...';
  }

  if (chatSend) {
    chatSend.disabled = true;
  }

  function addChatMessage(type, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${type}`;
    msgDiv.textContent = text;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // Typing / thinking indicator helpers
  function showBotTyping() {
    const id = `bot-typing-${Date.now()}`;
    const container = document.createElement('div');
    container.className = 'message bot typing';
    container.id = id;
    container.innerHTML = `
      <div class="flex items-center gap-2 text-sm text-gray-600 p-2">
        <svg class="animate-spin h-4 w-4 text-blue-500" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        <span>Thinking…</span>
      </div>
    `.trim();
    chatMessages.appendChild(container);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
  }

  function removeBotTyping(id) {
    try {
      const el = document.getElementById(id);
      if (el && el.parentNode) el.parentNode.removeChild(el);
    } catch (e) {
      // ignore
    }
  }

  function renderChatNeighborhoodSuggestions(neighborhoods) {
    const container = document.createElement('div');
    container.className = 'chat-neighborhood-suggestions p-2';

    const title = document.createElement('div');
    title.className = 'text-sm text-gray-600 mb-2';
    title.textContent = 'Neighborhood suggestions:';
    container.appendChild(title);

    const row = document.createElement('div');
    row.className = 'flex flex-wrap gap-2';

    neighborhoods.slice(0, 8).forEach(n => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'px-3 py-1 rounded-full text-sm bg-white border border-blue-200 text-blue-700 hover:bg-blue-100 transition';
      btn.textContent = n.name || (n.slug || 'unknown');
      btn.dataset.neighborhood = JSON.stringify(n);
      btn.addEventListener('click', (e) => {
        try {
          const nd = JSON.parse(e.currentTarget.dataset.neighborhood);
          selectedNeighborhood = nd;
          const select = document.getElementById('neighborhoodSelect');
          if (select) {
            // try to set select to matching option (stringified) if present
            const optVal = JSON.stringify(nd).replace(/'/g, "&#39;");
            const found = Array.from(select.options).find(o => o.value === optVal || o.text === nd.name);
            if (found) select.value = found.value;
          }
          updateSearchButtonState();
          // Auto-search if a category is already selected
          if (selectedCategory) performSearch();
          // Ensure chat input/send are enabled and focused so user can follow up immediately
          const chatInput = document.getElementById('chatInput');
          const chatSend = document.getElementById('chatSend');
          if (chatInput) {
            chatInput.disabled = false;
            chatInput.focus();
          }
          if (chatSend) chatSend.disabled = false;
          console.log('[Chat] Neighborhood chip clicked:', nd.name);
          addChatMessage('bot', `Selected neighborhood: ${nd.name}`);
        } catch (err) {
          console.warn('Failed to apply neighborhood suggestion', err);
        }
      });
      row.appendChild(btn);
    });

    container.appendChild(row);
    chatMessages.appendChild(container);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // Chat chips
  const chatChips = document.getElementById('chatChips');
  if (chatChips) {
    const chips = [
      "What's the best neighborhood for food?",
      "Any romantic spots?",
      "Where can I find coffee?",
      "Suggest a family-friendly activity"
    ];
    chatChips.innerHTML = chips.map(chip => `<button class="chat-chip" disabled>${chip}</button>`).join('');
    
    // Chips are initially disabled - enabled only when venues load
    const updateChips = () => {
      chatChips.querySelectorAll('.chat-chip').forEach(btn => {
        // Enable chips if we have venues OR a selected neighborhood (so users can ask neighborhood-level questions)
        const enabled = currentVenues.length > 0 || !!selectedNeighborhood;
        btn.disabled = !enabled;
        btn.style.opacity = enabled ? '1' : '0.5';
        btn.style.cursor = enabled ? 'pointer' : 'not-allowed';

        // Use onclick assignment to avoid stacking multiple listeners
        btn.onclick = () => {
          // Fill input and trigger send regardless of whether venues are loaded; backend will handle empty venues
          if (chatInput) {
            chatInput.value = btn.textContent;
          }
          sendChatMessage();
        };
      });
    };
    
    updateChips();
    // Re-run updateChips whenever venues change (override renderResults to call this)
    window.updateChatChips = updateChips;
  }

  document.getElementById('toggleSearchArea')?.addEventListener('click', () => {
    const citySection = document.querySelector('.city-input-section');
    const neighborhoodSection = document.getElementById('neighborhoodControls');
    const categorySection = document.querySelector('.category-section');
    const toggleBtn = document.getElementById('toggleSearchArea');

    const isMinimized = citySection && citySection.style.display === 'none';

    if (isMinimized) {
      if (citySection) citySection.style.display = 'block';
      if (neighborhoodSection) neighborhoodSection.style.display = selectedCity ? 'block' : 'none';
      if (categorySection) categorySection.style.display = 'block';
      if (toggleBtn) toggleBtn.textContent = 'Minimize Search';
    } else {
      if (citySection) citySection.style.display = 'none';
      if (neighborhoodSection) neighborhoodSection.style.display = 'none';
      if (categorySection) categorySection.style.display = 'none';
      if (toggleBtn) toggleBtn.textContent = 'Expand Search';
    }
  });
});