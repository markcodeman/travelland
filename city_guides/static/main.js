// ============================================================
// TRAVELLAND - Main JavaScript
// Flow: City → Neighborhood → Category → Search
// ============================================================
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
// ============================================================
// GLOBAL STATE
// ============================================================
let selectedCity = null;
let selectedNeighborhood = null;
let selectedCategory = null;
let currentVenues = [];
let currentWeather = null;
// Fetch weather for a city (by lat/lon) using Open-Meteo (no API key needed)
async function fetchWeatherForCity(cityName, lat = null, lon = null) {
  try {
    if (!(lat && lon)) {
      // If lat/lon not provided, cannot fetch weather from Open-Meteo
      return null;
    }
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error('Weather fetch failed');
    const data = await resp.json();
    const weather = data.current_weather || {};
    // Return a simple weather summary object
    return {
      summary: weather.weathercode !== undefined ? `Code ${weather.weathercode}` : '',
      temp: weather.temperature ?? null,
      icon: '', // Open-Meteo does not provide icons directly
      raw: weather
    };
  } catch (err) {
    console.warn('[Weather] Fetch failed:', err);
    return null;
  }
}
let currentNeighborhoods = []; // Store available neighborhoods for AI recommendations

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

      // Make the context string more natural and less obvious
      // e.g., 'Old Town, ABQ: Top Food'
      function abbreviateCity(name) {
        if (!name) return '';
        const map = {
          'Albuquerque': 'ABQ',
          'New York': 'NYC',
          'San Francisco': 'SF',
          'Los Angeles': 'LA',
          'Washington': 'DC',
          'Rio de Janeiro': 'Rio de Janeiro' // Never abbreviate
        };
        const base = name.split(',')[0].trim();
        // Only abbreviate if in map, otherwise use full base name
        return map[base] || base;
      }
      const city = selectedCity?.name ? abbreviateCity(selectedCity.name) : '';
      const neighborhood = selectedNeighborhood && selectedNeighborhood !== 'all' && selectedNeighborhood.name ? selectedNeighborhood.name.split(',')[0].trim() : '';
      const catLabel = chip.textContent.trim().replace(/[^A-Za-z0-9 ]/g, '').replace(/\s+/g, ' ').replace(/(^| )\w/g, l => l.toUpperCase());
      let context = '';
      if (neighborhood) context += neighborhood;
      if (city) context += (neighborhood ? ', ' : '') + city;
      if (catLabel) context += (context ? ': ' : '') + catLabel;

      // Set the input value to the context string for both chat UIs
      const chatInput = document.getElementById('chatInput');
      const chatInputExpanded = document.getElementById('chatInputExpanded');
      if (chatInput && context) chatInput.value = context;
      if (chatInputExpanded && context) chatInputExpanded.value = context;
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
  updateAskMarcoButtonState();

  // Always perform a fresh search and update weather before opening chat
  if (selectedNeighborhood) {
    performSearch().then(async () => {
      await updateWeatherWidget();
      openMarcoChat();
    });
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
  updateAskMarcoButtonState();
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

    // Update button state when input changes
    updateAskMarcoButtonState();

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
        let city = addr.city || addr.town || addr.village || addr.hamlet || addr.county || addr.state || '';
        const country = addr.country || '';

        // Canonicalization: Map known edge cases
        if (city === 'City of London' && country === 'United Kingdom') {
          city = 'London';
        }
        if (city === 'Região Metropolitana do Rio de Janeiro' && country === 'Brazil') {
          city = 'Rio de Janeiro';
        }

        // If city is a long hierarchical string, extract the first 'Rio de Janeiro' and use it
        if (city && country && city.includes('Rio de Janeiro') && country === 'Brazil') {
          // Split by comma, trim, find first 'Rio de Janeiro'
          const parts = city.split(',').map(s => s.trim());
          const rioIdx = parts.findIndex(p => p === 'Rio de Janeiro');
          if (rioIdx !== -1) {
            city = 'Rio de Janeiro';
          }
        }

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
      updateAskMarcoButtonState();
      // Always update weather widget after city selection
      updateWeatherWidget();
// Update the weather widget for the selected city
async function updateWeatherWidget() {
  const weatherSection = document.getElementById('weather');
  const weatherSummary = document.getElementById('weather-summary');
  const weatherDetails = document.getElementById('weather-details');
  const weatherIcon = document.getElementById('weather-icon');
  if (!selectedCity || !selectedCity.lat || !selectedCity.lon) {
    if (weatherSection) weatherSection.style.display = 'none';
    return;
  }
  const weather = await fetchWeatherForCity(selectedCity.name, selectedCity.lat, selectedCity.lon);
  if (!weather || weather.temp === null) {
    if (weatherSection) weatherSection.style.display = 'none';
    return;
  }
  // Map Open-Meteo weather codes to human-friendly descriptions
  const weatherCodeMap = {
    0: 'Clear sky',
    1: 'Mainly clear',
    2: 'Partly cloudy',
    3: 'Overcast',
    45: 'Fog',
    48: 'Depositing rime fog',
    51: 'Light drizzle',
    53: 'Drizzle',
    55: 'Dense drizzle',
    56: 'Freezing drizzle',
    57: 'Dense freezing drizzle',
    61: 'Slight rain',
    63: 'Rain',
    65: 'Heavy rain',
    66: 'Freezing rain',
    67: 'Heavy freezing rain',
    71: 'Slight snow fall',
    73: 'Snow fall',
    75: 'Heavy snow fall',
    77: 'Snow grains',
    80: 'Slight rain showers',
    81: 'Rain showers',
    82: 'Violent rain showers',
    85: 'Slight snow showers',
    86: 'Heavy snow showers',
    95: 'Thunderstorm',
    96: 'Thunderstorm with hail',
    99: 'Thunderstorm with heavy hail'
  };
  let summary = weather.summary;
  const codeMatch = /Code (\d+)/.exec(summary);
  if (codeMatch) {
    const code = parseInt(codeMatch[1], 10);
    summary = weatherCodeMap[code] || `Weather code ${code}`;
  }
  if (weatherSection) weatherSection.style.display = 'flex';
  if (weatherSummary) weatherSummary.textContent = `Current: ${weather.temp}°C`;
  if (weatherDetails) weatherDetails.textContent = summary;
  if (weatherIcon) weatherIcon.textContent = '🌤️'; // Placeholder icon
}

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

    // Store neighborhoods globally for AI recommendations
    currentNeighborhoods = neighborhoods;

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
    updateAskMarcoButtonState();
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
      </div>
    `;
    selectedNeighborhood = 'all';
    updateAskMarcoButtonState();
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
      updateAskMarcoButtonState();
      
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

  selectedNeighborhood = 'all';
  updateAskMarcoButtonState();
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
        updateAskMarcoButtonState();
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
// ASK MARCO BUTTON STATE - GLOBAL SCOPE
// ============================================================
function updateAskMarcoButtonState() {
  const askMarcoBtn = document.getElementById('askMarcoBtn');
  const marcoHint = document.getElementById('marcoHint');
  const cityInputEl = document.getElementById('city');

  const hasCity = selectedCity !== null || (cityInputEl && cityInputEl.value.trim().length > 0);
  const canAsk = hasCity;

  console.log('[Button State] selectedCity:', selectedCity, 'cityInput value:', cityInputEl?.value, 'hasCity:', hasCity, 'canAsk:', canAsk);

  if (askMarcoBtn) askMarcoBtn.disabled = !canAsk;

  if (marcoHint) {
    if (!hasCity) {
      marcoHint.textContent = '👆 Start by entering a city above';
    } else {
      marcoHint.textContent = '✅ Ready to chat with Marco!';
    }
  }
}

// ============================================================
// ASK MARCO HANDLER - GLOBAL SCOPE
// ============================================================
document.getElementById('askMarcoBtn')?.addEventListener('click', async () => {
  await openMarcoChat(true);
});

// Function to open and initialize Marco chat
async function openMarcoChat(autoSend = false) {
  const marcoChatSection = document.getElementById('marcoChatSection');
  const cityInputEl = document.getElementById('city');
  const city = cityInputEl?.value?.trim() || '';

  if (!city) {
    alert('Please enter a city first');
    return;
  }

  // Show the expanded chat
  if (marcoChatSection) {
    marcoChatSection.style.display = 'block';
    marcoChatSection.scrollIntoView({ behavior: 'smooth' });
    // Initialize expanded chat event listeners now that it's visible
    initializeExpandedChat();
    // Prefill chat with a default question if city is selected and input is empty
    const chatInput = document.getElementById('chatInputExpanded');
    let justPrefilled = false;
    if (chatInput && !chatInput.value.trim() && city) {
      let prompt = `I'm visiting ${city}`;
      if (selectedNeighborhood && selectedNeighborhood !== 'all' && selectedNeighborhood.name) {
        prompt += `, interested in ${selectedNeighborhood.name}`;
      }
      if (selectedCategory) {
        // Find the category label from CATEGORIES
        const catObj = CATEGORIES.find(c => c.query === selectedCategory);
        if (catObj && catObj.label) {
          prompt += `, and looking for ${catObj.label}`;
        }
      }
      prompt += '. What area or activities would you recommend?';
      chatInput.value = prompt;
      justPrefilled = true;
    }
    if (chatInput) {
      setTimeout(() => {
        chatInput.focus();
      }, 500);
      // Enlarge chat input for better editing
      chatInput.style.minHeight = '48px';
      chatInput.style.fontSize = '1.1em';
      chatInput.style.padding = '10px';
    }
  }

  // Load neighborhoods for the selected city if not already loaded
  if (!currentNeighborhoods || currentNeighborhoods.length === 0) {
    await loadNeighborhoodsForCity(city);
  }
}

// Initialize expanded chat event listeners
function initializeExpandedChat() {
  // Expanded Chat Event Listeners
  const chatInputExpanded = document.getElementById('chatInputExpanded');
  const chatSendExpanded = document.getElementById('chatSendExpanded');

  if (chatSendExpanded && !chatSendExpanded.hasEventListener) {
    console.log('Expanded chat send button found, adding listener');
    chatSendExpanded.addEventListener('click', sendExpandedChatMessage);
    chatSendExpanded.hasEventListener = true; // Mark as having listener
  } else if (chatSendExpanded) {
    console.log('Expanded chat send button already has listener');
  } else {
    console.log('Expanded chat send button not found');
  }

  if (chatInputExpanded && !chatInputExpanded.hasEventListener) {
    chatInputExpanded.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendExpandedChatMessage();
    });
    chatInputExpanded.hasEventListener = true; // Mark as having listener
  }

  // Expanded Chat Chips
  const chatChipsExpanded = document.getElementById('chatChipsExpanded');
  if (chatChipsExpanded) {
    // Clear existing chips
    chatChipsExpanded.innerHTML = '';
    
    const chips = [
      "What's the best neighborhood for food?",
      "Any romantic spots?",
      "Where can I find coffee?",
      "Suggest a family-friendly activity",
      "Recommend a neighborhood for me"
    ];
    chatChipsExpanded.innerHTML = chips.map(chip => `<button class="chat-chip">${chip}</button>`).join('');

    // Add click handlers for expanded chat chips
    chatChipsExpanded.querySelectorAll('.chat-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        if (chatInputExpanded) {
          chatInputExpanded.value = btn.textContent;
        }
        sendExpandedChatMessage();
      });
    });
  }
}

async function performSearch() {
  const query = document.getElementById('query')?.value?.trim();
  const city = document.getElementById('city')?.value?.trim();
  const lat = document.getElementById('user_lat')?.value;
  const lon = document.getElementById('user_lon')?.value;
  const resEl = document.getElementById('results');

  if (!city || !query) {
    alert('Please select a city and category');
    return;
  }

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
      timeout: 12
    };

    // Neighborhood filtering is now frontend-only; do not send to backend

    const resp = await fetch(`${API_BASE}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!resp.ok) throw new Error(`Search failed (HTTP ${resp.status})`);

    let data = await resp.json();

    // If a specific neighborhood is selected, filter venues client-side
    if (selectedNeighborhood && selectedNeighborhood !== 'all' && selectedNeighborhood.bbox && Array.isArray(data.venues)) {
      const bbox = selectedNeighborhood.bbox;
      // bbox: [minLon, minLat, maxLon, maxLat]
      data.venues = data.venues.filter(v => {
        if (!v.lon || !v.lat) return false;
        const lonF = parseFloat(v.lon);
        const latF = parseFloat(v.lat);
        return lonF >= bbox[0] && lonF <= bbox[2] && latF >= bbox[1] && latF <= bbox[3];
      });
    }

    renderResults(data, city);

  } catch (err) {
    resEl.innerHTML = `<div class=\"text-red-500 p-4\">Error: ${err.message}</div>`;
  }
}

// ============================================================
// RESULTS RENDERING - GLOBAL SCOPE
// ============================================================
function renderResults(data, city) {
  const resEl = document.getElementById('results');
  // Debugging: log incoming data so UI issues are easier to spot
  try { console.debug('[renderResults] incoming data:', data); } catch (e) {}
  if (!resEl) return;
  if (!data || !data.venues) {
    // show a visible debug message instead of silently failing
    resEl.innerHTML = `<div class="text-yellow-600 p-4">No venues payload received from server. Check console/network for response body.</div>`;
    return;
  }

  const venues = data.venues;
  currentVenues = venues;
  console.log('[renderResults] venues array:', venues); // Added debug log
  
  // Update expanded chat state - always enabled since we focus on chat now
  const chatInputExpanded = document.getElementById('chatInputExpanded');
  const chatSendExpanded = document.getElementById('chatSendExpanded');

  // Chat is always enabled - users can ask questions even without venues loaded
    
  resEl.innerHTML = '<div class="text-gray-500 p-4 text-center"><p>No results found in our data sources.</p><p class="text-sm mt-2">Try a different category or check <a href="https://maps.google.com" target="_blank" class="text-blue-600 hover:underline">Google Maps</a> for more options.</p></div>';
    
    // If no venues but we have Wikivoyage data, show it
    if (data.wikivoyage && data.wikivoyage.length > 0) {
      renderWikivoyage(data.wikivoyage);
    }
    
    return;
  
  // No need to render venue results anymore - chat takes precedence
  resEl.innerHTML = `
    <div class="text-center py-8 text-gray-600">
      <p>💬 Use the "Ask Marco" button above to chat with our AI travel guide!</p>
      <p class="text-sm mt-2">Marco can help you discover neighborhoods and get personalized recommendations.</p>
    </div>
  `;
  console.log('[renderResults] HTML set to results element'); // Added debug log
}

function renderWikivoyage(wikivoyageData) {
  const resEl = document.getElementById('results');
  if (!resEl) return;
  
  const html = wikivoyageData.map(section => `
    <div class="wikivoyage-section bg-white rounded-lg shadow-md p-6 mb-4">
      <h3 class="text-lg font-semibold text-gray-800 mb-2">${section.title || section.section}</h3>
      <div class="text-gray-700">${section.content || 'No content available'}</div>
    </div>
  `).join('');
  
  resEl.innerHTML += html; // Append to existing content
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
  updateAskMarcoButtonState();

  // ============================================================
  // EXPANDED MARCO CHAT FUNCTIONALITY - GLOBAL SCOPE
  // ============================================================
});

async function sendExpandedChatMessage() {
  console.log('Expanded chat send button clicked');
  const chatInput = document.getElementById('chatInputExpanded');
  const message = chatInput.value.trim();
  if (!message) return;

  // Add user message
  addExpandedChatMessage('user', message);
  chatInput.value = '';

  // Fetch weather if not set or city changed
  let cityName = selectedCity?.name || document.getElementById('city')?.value?.trim();
  let lat = selectedCity?.lat;
  let lon = selectedCity?.lon;
  if (cityName && (!currentWeather || currentWeather.city !== cityName)) {
    currentWeather = await fetchWeatherForCity(cityName, lat, lon);
    if (currentWeather) currentWeather.city = cityName;
  }

  // Send to backend with a typing indicator while waiting
  const typingId = showExpandedBotTyping();
  console.log('[Expanded Chat] Sending message with neighborhoods:', currentNeighborhoods ? currentNeighborhoods.length : 0, 'actual value:', currentNeighborhoods);
  // Always send up to 10 venues if available, even if not on screen
  fetch(`${API_BASE}/semantic-search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      q: message,
      city: cityName,
      venues: (Array.isArray(currentVenues) && currentVenues.length > 0) ? currentVenues.slice(0, 10) : [],
      neighborhoods: currentNeighborhoods,
      weather: currentWeather
    })
  })
  .then(resp => resp.json())
  .then(data => {
    removeExpandedBotTyping(typingId);
    addExpandedChatMessage('bot', data.answer || 'Sorry, I couldn\'t process that.');
    // If backend returned neighborhood suggestions, render them as quick chips
    if (data.neighborhoods && Array.isArray(data.neighborhoods) && data.neighborhoods.length > 0) {
      renderExpandedChatNeighborhoodSuggestions(data.neighborhoods);
    }
  })
  .catch(err => {
    removeExpandedBotTyping(typingId);
    console.error('Expanded chat error:', err);
    addExpandedChatMessage('bot', 'Error: ' + err.message);
  });
}

function addExpandedChatMessage(type, text) {
  const chatMessages = document.getElementById('chatMessagesExpanded');
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${type}`;
  if (type === 'bot') {
    // Format bot text for readability
    let formatted = text;
    // Split into paragraphs by double newlines or emoji bullets
    formatted = formatted.replace(/\n\n|\n/g, '<br><br>');
    // Highlight and link neighborhood names
    const places = [
      { name: 'Temple', maps: 'https://www.google.com/maps/search/?api=1&query=Temple+London', img: null },
      { name: 'West Smithfield', maps: 'https://www.google.com/maps/search/?api=1&query=West+Smithfield+London', img: null },
      { name: 'Blackfriars', maps: 'https://www.google.com/maps/search/?api=1&query=Blackfriars+London', img: null },
      { name: 'Leadenhall Market', maps: 'https://www.google.com/maps/search/?api=1&query=Leadenhall+Market+London', img: 'https://upload.wikimedia.org/wikipedia/commons/6/6e/Leadenhall_Market_2011.jpg' }
    ];
    let imageHtml = '';
    for (const place of places) {
      // Link all case-insensitive matches of place name
      const linkHtml = `<a href="${place.maps}" target="_blank" style="text-decoration:underline;color:#2563eb"><strong>${place.name}</strong> <span style="font-size:0.9em">🔗</span></a>`;
      // Use regex with 'gi' flag for global, case-insensitive replacement
      formatted = formatted.replace(new RegExp(place.name, 'gi'), linkHtml);
      // Show image for first mentioned place with image (case-insensitive)
      if (!imageHtml && place.img && new RegExp(place.name, 'i').test(text)) {
        imageHtml = `<div style="margin-bottom:8px"><img src="${place.img}" alt="${place.name}" style="max-width:120px;border-radius:8px;box-shadow:0 2px 8px #ccc"/></div>`;
      }
    }
    // Add extra spacing before emoji bullets
    formatted = formatted.replace(/(🍴️|🔥️|🌍️|🔜|🔔|🏛️|🍽️|☕️|🎉|💎|🌳)/g, '<br>$1');
    msgDiv.innerHTML = imageHtml + formatted;
  } else {
    msgDiv.textContent = text;
  }
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Typing indicator for expanded chat
function showExpandedBotTyping() {
  const id = `bot-typing-${Date.now()}`;
  const chatMessages = document.getElementById('chatMessagesExpanded');
  const container = document.createElement('div');
  container.className = 'message bot typing';
  container.id = id;
  container.innerHTML = `
    <div class="flex items-center gap-2 text-sm text-gray-600 p-2">
      <div class="flex gap-1">
        <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
        <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
        <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
      </div>
      <span>Marco is thinking...</span>
    </div>
  `;
  chatMessages.appendChild(container);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return id;
}

function removeExpandedBotTyping(typingId) {
  const container = document.getElementById(typingId);
  if (container) container.remove();
}

function renderExpandedChatNeighborhoodSuggestions(neighborhoods) {
  const chipsContainer = document.getElementById('chatChipsExpanded');
  if (!chipsContainer) return;

  chipsContainer.innerHTML = '';

  neighborhoods.slice(0, 6).forEach(neighborhood => {
    const chip = document.createElement('button');
    chip.className = 'chat-chip';
    chip.textContent = neighborhood.name || neighborhood;
    chip.addEventListener('click', () => {
      // Set this neighborhood as selected and trigger chat
      selectedNeighborhood = neighborhood;
      document.getElementById('neighborhood_id').value = neighborhood.id || neighborhood.name;
      if (neighborhood.bbox) {
        document.getElementById('neighborhood_bbox').value = JSON.stringify(neighborhood.bbox);
      }
      addExpandedChatMessage('user', `Tell me about ${neighborhood.name || neighborhood}`);
      sendExpandedChatMessage();
    });
    chipsContainer.appendChild(chip);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  // Expanded Chat Chips
  const chatChipsExpanded = document.getElementById('chatChipsExpanded');
  if (chatChipsExpanded) {
    const chips = [
      "What's the best neighborhood for food?",
      "Any romantic spots?",
      "Where can I find coffee?",
      "Suggest a family-friendly activity",
      "Recommend a neighborhood for me"
    ];
    chatChipsExpanded.innerHTML = chips.map(chip => `<button class="chat-chip">${chip}</button>`).join('');

    // Add click handlers for expanded chat chips
    chatChipsExpanded.querySelectorAll('.chat-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        if (chatInputExpanded) {
          chatInputExpanded.value = btn.textContent;
        }
        sendExpandedChatMessage();
      });
    });
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