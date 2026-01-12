// Default placeholder image (real PNG file)
const DEFAULT_IMAGE = '/static/img/placeholder.png';

// Global state for neighborhood selection
let selectedNeighborhood = null;

// Global timeout for client-side search requests (25s max; some cities are slow on Overpass)
// Backend will return partial results within ~8s, then keep adding more if time permits
const timeoutMs = 25000;

// API base:
// - Default: same-origin (''), works when the page is served by Flask.
// - Dev fallback: if you're serving the HTML from another local port (e.g. Live Server),
//   route API calls to the Flask dev server on 5010.
const API_BASE = (() => {
  try {
    if (window.TRAVELLAND_API_BASE) return String(window.TRAVELLAND_API_BASE).replace(/\/$/, '');
    const isLocalhost = ['127.0.0.1', 'localhost'].includes(window.location.hostname);
    const port = window.location.port;
    if (isLocalhost && port && port !== '5010') return 'http://127.0.0.1:5010';
  } catch (e) {}
  return '';
})();

// --- Suggestion Chips Logic ---
const suggestionChipsEl = document.getElementById('suggestionChips');
const SUGGESTION_CHIPS = [
  { label: "Top food", query: "restaurant" },
  { label: "Historic sites", query: "historic" },
  { label: "Public transport", query: "transport" },
  { label: "Local markets", query: "market" },
  { label: "Family friendly", query: "family" },
  { label: "Popular events", query: "event" },
  { label: "Local favorites", query: "local" },
  { label: "Hidden gems", query: "hidden" },
  { label: "Coffee & tea", query: "coffee" },
  { label: "Parks & nature", query: "park" }
];

function renderSuggestionChips(chips = SUGGESTION_CHIPS) {
  if (!suggestionChipsEl) return;
  suggestionChipsEl.innerHTML = '';
  chips.forEach(({label, query}) => {
    const btn = document.createElement('button');
    btn.className = 'px-3 py-1 rounded-full bg-blue-100 hover:bg-blue-200 text-blue-800 font-semibold text-sm transition';
    btn.textContent = label;
    btn.onclick = () => {
      const queryInput = document.getElementById('query');
      const cityInput = document.getElementById('city');
      let city = cityInput && cityInput.value ? cityInput.value.trim() : '';
      if (!city) {
        // Prefer a non-blocking fallback: use the input placeholder if present.
        // This avoids modal prompts which some browsers block and can appear like "nothing happened".
        const placeholderCity = cityInput && cityInput.placeholder ? cityInput.placeholder.trim() : '';
        if (placeholderCity) {
          city = placeholderCity;
          if (cityInput) cityInput.value = city;
          try { updateQueryEnabledState(); } catch (e) {}
        } else {
          // Last resort: prompt the user (kept for interactive flows)
          const prompted = window.prompt('Enter a city (e.g. "Lisbon, Portugal")');
          if (prompted && prompted.trim()) {
            city = prompted.trim();
            if (cityInput) cityInput.value = city;
            try { updateQueryEnabledState(); } catch (e) {}
          } else {
            // visual cue if user cancels
            if (cityInput) {
              cityInput.classList.add('ring', 'ring-red-400');
              setTimeout(() => cityInput.classList.remove('ring', 'ring-red-400'), 600);
            }
            return;
          }
        }
      }
      let chipText = label;
      let searchText = chipText;
      if (city) {
        searchText = `${chipText} in ${city}`;
      }
      if (queryInput) queryInput.value = searchText;
      // Ensure UI state updates before auto-search
      try { updateQueryEnabledState(); } catch(e){}
      // Explicitly enable the button as a robust fallback, then auto-search
      const searchBtn = document.getElementById('searchBtn');
      if (searchBtn) {
        try { searchBtn.disabled = false; } catch(e){}
        searchBtn.click();
      }
    };
    suggestionChipsEl.appendChild(btn);
  });
}
renderSuggestionChips();

// Ensure chip clicks always refresh the enabled/disabled state for the Search button.
// Some browsers or race conditions can leave the button disabled when a user clicks
// a chip and then manually clicks Search. A delegated handler guarantees the UI
// state is re-evaluated immediately after any chip click.
document.addEventListener('click', (ev) => {
  try {
    updateQueryEnabledState();
  } catch (e) {}
});

// --- Nominatim autocomplete helpers ---

/**
 * ⚠️ PROTECTED FILE - DO NOT MODIFY WITHOUT REVIEW
 * City autocomplete using Nominatim
 * Last working: Jan 12, 2026
 */

const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search';

const citySearchModule = {
    timeout: null,

    init() {
        const cityInput = document.getElementById('city');
        const suggestionsEl = document.getElementById('city-suggestions');
        if (!cityInput || !suggestionsEl) return;

        cityInput.addEventListener('input', (e) => this.handleInput(e, suggestionsEl));
        document.addEventListener('click', (e) => this.handleClickOutside(e, cityInput, suggestionsEl));
    },

    handleInput(e, suggestionsEl) {
        const value = e.target.value.trim();
        if (this.timeout) clearTimeout(this.timeout);

        if (!value || value.length < 3) {
            this.hideSuggestions(suggestionsEl);
            return;
        }

        this.timeout = setTimeout(() => this.fetchSuggestions(value, suggestionsEl), 300);
    },

    async fetchSuggestions(query, suggestionsEl) {
        try {
            const url = `${NOMINATIM_URL}?format=json&addressdetails=1&limit=6&accept-language=en&q=${encodeURIComponent(query)}`;
            const resp = await fetch(url, {
                headers: { 'Accept': 'application/json', 'User-Agent': 'city-guides/1.0' }
            });
            const items = await resp.json();
            this.showSuggestions(items, suggestionsEl);
        } catch (err) {
            console.warn('Nominatim error:', err);
            this.hideSuggestions(suggestionsEl);
        }
    },

    showSuggestions(items, suggestionsEl) {
        if (!items || items.length === 0) {
            this.hideSuggestions(suggestionsEl);
            return;
        }

        window._citySuggestions = items;
        suggestionsEl.innerHTML = items.map(it => `
            <div class="suggestion-item px-3 py-2 hover:bg-gray-100 cursor-pointer"
                 data-lat="${it.lat}" data-lon="${it.lon}">
                ${it.display_name}
            </div>
        `).join('');
        suggestionsEl.style.display = 'block';
    },

    hideSuggestions(suggestionsEl) {
        if (suggestionsEl) suggestionsEl.style.display = 'none';
    },

    handleClickOutside(e, cityInput, suggestionsEl) {
        const suggestionItem = e.target.closest('.suggestion-item');

        if (suggestionItem) {
            this.selectCity(suggestionItem, cityInput, suggestionsEl);
        } else if (e.target !== cityInput && !e.target.closest('#city-suggestions')) {
            this.hideSuggestions(suggestionsEl);
        }
    },

    selectCity(el, cityInput, suggestionsEl) {
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
        this.hideSuggestions(suggestionsEl);

        // Store lat/lon
        this.setHiddenField('user_lat', lat);
        this.setHiddenField('user_lon', lon);

        // Trigger neighborhood fetch
        if (typeof fetchAndRenderNeighborhoods === 'function') {
            fetchAndRenderNeighborhoods(cityCountry, lat, lon);
        }

        // Update other UI elements
        if (typeof updateQueryEnabledState === 'function') updateQueryEnabledState();
        if (typeof updateTransportLink === 'function') updateTransportLink();
    },

    setHiddenField(id, value) {
        let field = document.getElementById(id);
        if (!field) {
            field = document.createElement('input');
            field.type = 'hidden';
            field.id = id;
            field.name = id;
            document.body.appendChild(field);
        }
        field.value = value;
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => citySearchModule.init());

// --- End of city search module ---

// Query state management
const queryInput = document.getElementById('query');
const searchBtn = document.getElementById('searchBtn');

function updateQueryEnabledState() {
  const cityInput = document.getElementById('city');
  const cityVal = cityInput && cityInput.value.trim();
  const queryVal = queryInput && queryInput.value.trim();
  // Enable search only if: city has value AND (query has value OR placeholder suggests action)
  const hasCity = !!cityVal || (cityInput && cityInput.placeholder && cityInput.placeholder.includes('Guadalajara'));
  const hasQuery = !!queryVal;
  const enabled = hasCity && hasQuery; // Must have BOTH city and explicit query
  if (queryInput) {
    queryInput.disabled = !hasCity;
    // Dynamic placeholder
    if (cityVal) {
      queryInput.placeholder = `Try Historic sites in ${cityVal}`;
    } else {
      queryInput.placeholder = 'Try Historic sites in Guadalajara';
    }
  }
  if (searchBtn) searchBtn.disabled = !enabled;
}

if (queryInput) {
    queryInput.addEventListener('input', updateQueryEnabledState);
}

// Initialize query state on page load
document.addEventListener('DOMContentLoaded', () => {
  updateQueryEnabledState();
});

// Neighborhood helper elements and state
const neighborhoodsListEl = document.getElementById('neighborhoodList');
const neighborhoodPreviewEl = document.getElementById('neighborhoodPreview');

async function fetchAndRenderNeighborhoods(city, lat, lon) {
  if (!city && !(lat && lon)) return;
  let url = `${API_BASE}/neighborhoods?`;
  if (city) {
    url += `city=${encodeURIComponent(city)}&`;
  }
  if (lat && lon) {
    url += `lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`;
  }
  try {
    console.log('[DEBUG] fetchAndRenderNeighborhoods url=', url);
    const resp = await fetch(url);
    console.log('[DEBUG] /neighborhoods resp ok=', resp.ok, 'status=', resp.status);
    if (!resp.ok) throw new Error('neighborhoods lookup failed');
    const j = await resp.json();
    console.log('[DEBUG] /neighborhoods payload=', j);
    const n = j && j.neighborhoods ? j.neighborhoods : [];
    renderNeighborhoodChips(n);
  } catch (e) {
    console.warn('Neighborhoods fetch failed', e);
    if (neighborhoodsListEl) neighborhoodsListEl.innerHTML = '';
    if (neighborhoodPreviewEl) neighborhoodPreviewEl.innerHTML = '';
    const ctrl = document.getElementById('neighborhoodControls'); if (ctrl) ctrl.style.display = 'none';
  }
}

// after a short pause. Only triggers if a city is selected (to avoid empty searches).
let searchDebounce = null;
if (queryInput) {
  queryInput.addEventListener('input', (ev) => {
    const q = ev.target.value.trim();
    if (searchDebounce) clearTimeout(searchDebounce);
    // require a city and some query text to auto-search
    const cityVal = cityInput && cityInput.value ? cityInput.value.trim() : '';
    if (!cityVal || q.length === 0) return;
    searchDebounce = setTimeout(() => {
      // perform the search but don't override explicit user intent; leave the button enabled
      const btn = document.getElementById('searchBtn');
      if (btn && !btn.disabled) btn.click();
    }, 700);
  });
  // Enter key on query triggers immediate search
  queryInput.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      if (searchDebounce) clearTimeout(searchDebounce);
      const btn = document.getElementById('searchBtn');
      if (btn && !btn.disabled) btn.click();
    }
  });
}

// Collapse / expand search area
document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn = document.getElementById('toggleSearchBtn');
  const searchSection = document.querySelector('.search-section');
  if (toggleBtn && searchSection) {
    toggleBtn.addEventListener('click', () => {
      const collapsed = searchSection.classList.toggle('collapsed');
      // Update button text and aria-expanded
      toggleBtn.setAttribute('aria-expanded', (!collapsed).toString());
      toggleBtn.textContent = collapsed ? '▼ Expand ▼' : '▴ Collapse ▴';
    });
  }
});

(() => {
  const hamb = document.getElementById('hamburgerBtn');
  const menu = document.getElementById('hamburgerMenu');
  if (hamb && menu) {
    hamb.addEventListener('click', (ev) => {
      ev.stopPropagation();
      menu.style.display = (menu.style.display === 'block') ? 'none' : 'block';
    });
    document.addEventListener('click', (ev) => { if (ev.target && ev.target.closest && !ev.target.closest('#hamburgerMenu') && ev.target !== hamb) menu.style.display = 'none'; });
    document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') menu.style.display = 'none'; });
  }

  if (cityInput && suggestionsEl) {
    let focused = -1;
    cityInput.addEventListener('keydown', (ev) => {
      const items = suggestionsEl.querySelectorAll('.suggestion-item');
      if (!items || items.length === 0) return;
    });
  }
});

function updateTransportLink() {
  const city = document.getElementById('city').value.trim();
  const lat = document.getElementById('user_lat') ? document.getElementById('user_lat').value : '';
  const lon = document.getElementById('user_lon') ? document.getElementById('user_lon').value : '';
  const link = document.getElementById('transportLink');
  if (link && city) {
    link.href = `/transport?city=${encodeURIComponent(city)}&lat=${lat}&lon=${lon}`;
  }
}

function updateCurrencyLink() {
  const city = document.getElementById('city').value.trim();
  const hambCurrency = document.querySelector('#hamburgerMenu a[href="/tools/currency"]');
  if (hambCurrency) {
    if (city) {
      hambCurrency.href = `/tools/currency?city=${encodeURIComponent(city)}`;
    } else {
      hambCurrency.href = '/tools/currency';
    }
  }
}

/**
 * Render neighborhoods with discovery presets + dropdown + Marco fallback
 */
function renderNeighborhoodChips(neighborhoods) {
    let container = document.getElementById('neighborhoodControls');
    
    if (!container) {
        container = document.createElement('div');
        container.id = 'neighborhoodControls';
        container.className = 'neighborhood-controls mt-4';
        const insertAfter = document.getElementById('suggestionChips') 
            || document.querySelector('.search-form');
        if (insertAfter) insertAfter.insertAdjacentElement('afterend', container);
    }
    
    container.innerHTML = '';
    
    if (!neighborhoods || neighborhoods.length === 0) {
        container.innerHTML = '<p class="text-gray-500 italic text-sm">No neighborhoods found</p>';
        return;
    }
    
    const count = neighborhoods.length;
    const cityName = document.getElementById('city')?.value?.split(',')[0] || 'this city';
    
    console.log(`[Neighborhoods] Rendering discovery UI with ${count} areas`);
    
    // Build the discovery UI
    container.innerHTML = `
        <div class="neighborhood-discovery">
            <!-- Header -->
            <p class="text-sm font-medium text-gray-700 mb-2">
                📍 Explore ${cityName}
            </p>
            
            <!-- Quick Presets (Option 4) -->
            <div class="neighborhood-presets flex flex-wrap gap-2 mb-3">
                <button type="button" class="preset-btn px-3 py-1.5 rounded-full text-sm border border-blue-300 bg-blue-50 hover:bg-blue-100 text-blue-700 transition" data-filter="tourist">
                    🎯 Tourist Hotspots
                </button>
                <button type="button" class="preset-btn px-3 py-1.5 rounded-full text-sm border border-green-300 bg-green-50 hover:bg-green-100 text-green-700 transition" data-filter="local">
                    🏠 Local Vibes
                </button>
                <button type="button" class="preset-btn px-3 py-1.5 rounded-full text-sm border border-orange-300 bg-orange-50 hover:bg-orange-100 text-orange-700 transition" data-filter="food">
                    🍽️ Foodie Areas
                </button>
                <button type="button" class="preset-btn px-3 py-1.5 rounded-full text-sm border border-purple-300 bg-purple-50 hover:bg-purple-100 text-purple-700 transition" data-filter="nightlife">
                    🌙 Nightlife
                </button>
                <button type="button" class="preset-btn px-3 py-1.5 rounded-full text-sm border border-teal-300 bg-teal-50 hover:bg-teal-100 text-teal-700 transition" data-filter="budget">
                    💰 Budget-Friendly
                </button>
            </div>
            
            <!-- Dropdown (Option 2) -->
            <div class="neighborhood-dropdown">
                <label class="text-xs text-gray-500 mb-1 block">Or choose a specific area:</label>
                <select id="neighborhoodSelect" 
                        class="w-full md:w-80 p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white">
                    <option value="">-- Select neighborhood --</option>
                    <option value="all">🌐 All Areas (${count} total)</option>
                    ${neighborhoods.map(n => 
                        `<option value='${JSON.stringify(n).replace(/'/g, "&#39;")}'>${n.name}</option>`
                    ).join('')}
                </select>
            </div>
            
            <!-- Marco Fallback -->
            <div class="marco-help mt-3 p-2 bg-gray-50 rounded-lg border border-gray-200">
                <p class="text-xs text-gray-600">
                    🤔 <strong>Not sure where to go?</strong>
                    <button type="button" id="askMarcoBtn" class="text-blue-600 hover:underline ml-1">
                        Ask Marco for a recommendation →
                    </button>
                </p>
            </div>
        </div>
    `;
    
    // Store neighborhoods for filtering
    window._neighborhoodData = neighborhoods;
    
    // Handle dropdown selection
    const select = document.getElementById('neighborhoodSelect');
    if (select) {
        select.addEventListener('change', (e) => {
            const val = e.target.value;
            clearPresetSelection();
            
            if (val === '') {
                selectedNeighborhood = null;
            } else if (val === 'all') {
                selectedNeighborhood = 'all';
            } else {
                try { 
                    selectedNeighborhood = JSON.parse(val); 
                } catch (err) { 
                    selectedNeighborhood = val; 
                }
            }
            console.log('[Neighborhoods] Selected:', selectedNeighborhood === 'all' ? 'All Areas' : selectedNeighborhood?.name);
            updateSearchButtonState();
        });
    }
    
    // Handle preset buttons
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const filter = e.target.dataset.filter;
            handlePresetClick(filter, neighborhoods);
        });
    });
    
    // Handle Marco button
    const marcoBtn = document.getElementById('askMarcoBtn');
    if (marcoBtn) {
        marcoBtn.addEventListener('click', () => {
            openMarcoWithNeighborhoodQuestion(cityName);
        });
    }
    
    selectedNeighborhood = null;
    updateSearchButtonState();
}

/**
 * Handle preset button clicks - suggest relevant neighborhoods
 */
function handlePresetClick(filter, neighborhoods) {
    // Clear previous selection
    clearPresetSelection();
    
    // Highlight clicked preset
    const clickedBtn = document.querySelector(`.preset-btn[data-filter="${filter}"]`);
    if (clickedBtn) {
        clickedBtn.classList.add('ring-2', 'ring-offset-1', 'ring-blue-500');
    }
    
    // Keywords for each filter type
    const filterKeywords = {
        tourist: ['centro', 'center', 'old town', 'historic', 'downtown', 'central', 'main', 'plaza', 'square', 'cathedral', 'castle', 'palace', 'museum'],
        local: ['residential', 'village', 'local', 'authentic', 'traditional', 'neighborhood', 'barrio', 'bairro', 'quartier'],
        food: ['market', 'mercado', 'food', 'restaurant', 'gastro', 'culinary', 'chinatown', 'little italy'],
        nightlife: ['night', 'club', 'bar', 'party', 'entertainment', 'soho', 'downtown'],
        budget: ['student', 'university', 'budget', 'affordable', 'cheap', 'backpack']
    };
    
    const keywords = filterKeywords[filter] || [];
    
    // Find matching neighborhoods
    let matches = neighborhoods.filter(n => {
        const name = n.name.toLowerCase();
        return keywords.some(kw => name.includes(kw));
    });
    
    // If no matches, pick first 3 as "recommended"
    if (matches.length === 0) {
        matches = neighborhoods.slice(0, 3);
    }
    
    // Show suggestion
    showNeighborhoodSuggestion(filter, matches);
}

/**
 * Show a suggestion based on preset selection
 */
function showNeighborhoodSuggestion(filter, matches) {
    const filterLabels = {
        tourist: '🎯 Tourist Hotspots',
        local: '🏠 Local Vibes',
        food: '🍽️ Foodie Areas',
        nightlife: '🌙 Nightlife',
        budget: '💰 Budget-Friendly'
    };
    
    // Create or update suggestion area
    let suggestionEl = document.getElementById('neighborhoodSuggestion');
    if (!suggestionEl) {
        suggestionEl = document.createElement('div');
        suggestionEl.id = 'neighborhoodSuggestion';
        suggestionEl.className = 'mt-2 p-3 bg-blue-50 rounded-lg border border-blue-200';
        const dropdown = document.querySelector('.neighborhood-dropdown');
        if (dropdown) dropdown.insertAdjacentElement('beforebegin', suggestionEl);
    }
    
    if (matches.length === 0) {
        suggestionEl.innerHTML = `
            <p class="text-sm text-gray-600">
                No specific ${filterLabels[filter]} areas found. Try "All Areas" or 
                <button type="button" class="text-blue-600 hover:underline" onclick="document.getElementById('askMarcoBtn').click()">ask Marco</button>!
            </p>
        `;
        return;
    }
    
    suggestionEl.innerHTML = `
        <p class="text-sm font-medium text-blue-800 mb-2">
            ${filterLabels[filter]} - Suggested areas:
        </p>
        <div class="flex flex-wrap gap-2">
            ${matches.slice(0, 5).map(n => `
                <button type="button" 
                        class="suggestion-chip px-3 py-1 rounded-full text-sm bg-white border border-blue-300 hover:bg-blue-100 text-blue-700"
                        data-neighborhood='${JSON.stringify(n).replace(/'/g, "&#39;")}'>
                    ${n.name}
                </button>
            `).join('')}
        </div>
    `;
    
    // Add click handlers for suggestion chips
    suggestionEl.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', (e) => {
            const data = e.target.dataset.neighborhood;
            try {
                selectedNeighborhood = JSON.parse(data);
                // Update dropdown to match
                const select = document.getElementById('neighborhoodSelect');
                if (select) {
                    select.value = data;
                }
                // Highlight selected chip
                suggestionEl.querySelectorAll('.suggestion-chip').forEach(c => {
                    c.classList.remove('bg-blue-500', 'text-white');
                    c.classList.add('bg-white', 'text-blue-700');
                });
                e.target.classList.remove('bg-white', 'text-blue-700');
                e.target.classList.add('bg-blue-500', 'text-white');
                
                console.log('[Neighborhoods] Selected from suggestion:', selectedNeighborhood.name);
                updateSearchButtonState();
            } catch (err) {
                console.warn('Failed to parse neighborhood', err);
            }
        });
    });
}

/**
 * Clear preset button selection
 */
function clearPresetSelection() {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.remove('ring-2', 'ring-offset-1', 'ring-blue-500');
    });
}

/**
 * Open Marco chat with a neighborhood question
 */
function openMarcoWithNeighborhoodQuestion(cityName) {
    // Open Marco chat
    const marcoChat = document.getElementById('marcoChat');
    if (marcoChat) {
        marcoChat.classList.add('open');
    }
    
    // Pre-fill the question
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.value = `I'm visiting ${cityName} but I don't know the neighborhoods. Can you recommend the best area for me based on what I'm looking for?`;
        chatInput.focus();
    }
    
    // Add a helpful prompt in chat
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        const helpMsg = document.createElement('div');
        helpMsg.className = 'message bot';
        helpMsg.innerHTML = `
            <strong>Marco here! 🧭</strong><br>
            Tell me what you're looking for in ${cityName}:<br>
            • Historic sites & culture?<br>
            • Best local food scene?<br>
            • Nightlife & entertainment?<br>
            • Family-friendly areas?<br>
            • Budget-friendly spots?<br><br>
            I'll suggest the perfect neighborhood for you!
        `;
        chatMessages.appendChild(helpMsg);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

/**
 * Update hidden form inputs for neighborhood selection
 */
function updateNeighborhoodHiddenInputs(neighborhood) {
    try {
        const cityInput = document.getElementById('city');
        const form = (cityInput && cityInput.form) || document.getElementById('search-form') || document.querySelector('form');
        
        if (!form) return;
        
        // Ensure hidden inputs exist
        let idInput = document.getElementById('neighborhood_id');
        if (!idInput) {
            idInput = document.createElement('input');
            idInput.type = 'hidden';
            idInput.id = 'neighborhood_id';
            idInput.name = 'neighborhood_id';
            form.appendChild(idInput);
        }
        
        let bboxInput = document.getElementById('neighborhood_bbox');
        if (!bboxInput) {
            bboxInput = document.createElement('input');
            bboxInput.type = 'hidden';
            bboxInput.id = 'neighborhood_bbox';
            bboxInput.name = 'neighborhood_bbox';
            form.appendChild(bboxInput);
        }
        
        // Update values
        if (neighborhood && typeof neighborhood === 'object') {
            idInput.value = neighborhood.id || '';
            const bbox = neighborhood.bbox;
            bboxInput.value = Array.isArray(bbox) ? bbox.join(',') : (bbox || '');
        } else {
            idInput.value = '';
            bboxInput.value = '';
        }
    } catch (e) {
        console.warn('[Neighborhoods] Failed to update hidden inputs:', e);
    }
}

/**
 * Enable/disable search button based on neighborhood state
 */
function updateSearchButtonState() {
    const searchBtn = document.getElementById('searchBtn');
    const cityInput = document.getElementById('city');
    const queryInput = document.getElementById('query');
    
    const hasCity = cityInput && cityInput.value.trim();
    const hasQuery = queryInput && queryInput.value.trim();
    const isDropdown = !!document.getElementById('neighborhoodSearch');
    const hasNeighborhood = !isDropdown || selectedNeighborhood !== null;
    
    if (searchBtn) {
        const enabled = hasCity && hasQuery && hasNeighborhood;
        searchBtn.disabled = !enabled;
        
        if (!hasNeighborhood && isDropdown) {
            searchBtn.title = 'Select a neighborhood first';
        } else if (!hasCity) {
            searchBtn.title = 'Enter a city first';
        } else if (!hasQuery) {
            searchBtn.title = 'Select a category or enter a search query';
        } else {
            searchBtn.title = '';
        }
    }
}