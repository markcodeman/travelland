// Default placeholder image (real PNG file)
const DEFAULT_IMAGE = '/static/img/placeholder.png';

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
        // Optionally, show a visual cue or shake the city input
        if (cityInput) {
          cityInput.classList.add('ring', 'ring-red-400');
          setTimeout(() => cityInput.classList.remove('ring', 'ring-red-400'), 600);
        }
        return;
      }
      let chipText = label;
      let searchText = chipText;
      if (city) {
        searchText = `${chipText} in ${city}`;
      }
      if (queryInput) queryInput.value = searchText;
      document.getElementById('searchBtn').click();
    };
    suggestionChipsEl.appendChild(btn);
  });
}
renderSuggestionChips();
let currentVenues = [];
let currentWeather = null;

// --- Nominatim autocomplete helpers ---

const cityInput = document.getElementById('city');
const queryInput = document.getElementById('query');
const searchBtn = document.getElementById('searchBtn');
const suggestionsEl = document.getElementById('city-suggestions');
let nominatimTimeout = null;

const debounce = (func, delay) => {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), delay);
    };
};

function updateQueryEnabledState() {
  const cityVal = cityInput && cityInput.value.trim();
  const enabled = !!cityVal;
  if (queryInput) {
    queryInput.disabled = !enabled;
    // Dynamic placeholder
    if (cityVal) {
      queryInput.placeholder = `Try Historic sites in ${cityVal}`;
    } else {
      queryInput.placeholder = 'Try Historic sites in Guadalajara';
    }
  }
  if (searchBtn) searchBtn.disabled = !enabled;
}
if (cityInput) {
    cityInput.addEventListener('input', updateQueryEnabledState);
    // Also run on page load
    updateQueryEnabledState();
}

function hideCitySuggestions() {
  if (suggestionsEl) suggestionsEl.style.display = 'none';
}

function showCitySuggestions(items) {
  if (!suggestionsEl) return;
  if (!items || items.length === 0) {
    hideCitySuggestions();
    return;
  }
  window.lastCitySuggestions = items;
  suggestionsEl.innerHTML = items.map(it => {
    const display = it.display_name;
    return `<div class="suggestion-item px-3 py-2 hover:bg-gray-100 cursor-pointer" data-lat="${it.lat}" data-lon="${it.lon}">${display}</div>`;
  }).join('');
  suggestionsEl.style.display = 'block';
}

function fetchCitySuggestions(q) {
  // request English results to prefer ASCII country names
  const url = `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=6&accept-language=en&q=${encodeURIComponent(q)}`;
  return fetch(url, {headers: {'Accept': 'application/json'}}).then(r => r.json());
}

if (cityInput) {
  const debouncedFetch = debounce(async (value) => {
    try {
      const items = await fetchCitySuggestions(value);
      showCitySuggestions(items);
    } catch (err) {
      hideCitySuggestions();
      console.warn('Nominatim error', err);
    }
  }, 300);

  cityInput.addEventListener('input', (e) => {
    const v = e.target.value.trim();
    if (!v || v.length < 3) {
      hideCitySuggestions();
      return;
    }
    debouncedFetch(v);
  });

  document.addEventListener('click', (ev) => {
    const el = ev.target.closest && ev.target.closest('.suggestion-item');
    if (el) {
      const lat = el.getAttribute('data-lat');
      const lon = el.getAttribute('data-lon');
      let selectedItem = null;
      if (window.lastCitySuggestions && Array.isArray(window.lastCitySuggestions)) {
        selectedItem = window.lastCitySuggestions.find(it => it.lat === lat && it.lon === lon);
      }
      let cityCountry = el.textContent || el.innerText;
      if (selectedItem && selectedItem.address) {
        const addr = selectedItem.address;
        const city = addr.city || addr.town || addr.village || addr.hamlet || '';
        const country = addr.country || '';
        if (city && country) cityCountry = `${city}, ${country}`;
        else if (city) cityCountry = city;
        else if (country) cityCountry = country;
      }
      cityInput.value = cityCountry;
      hideCitySuggestions();
      let hfLat = document.getElementById('user_lat');
      let hfLon = document.getElementById('user_lon');
      if (!hfLat) {
        hfLat = document.createElement('input'); hfLat.type = 'hidden'; hfLat.id = 'user_lat'; hfLat.name = 'user_lat'; document.body.appendChild(hfLat);
      }
      if (!hfLon) {
        hfLon = document.createElement('input'); hfLon.type = 'hidden'; hfLon.id = 'user_lon'; hfLon.name = 'user_lon'; document.body.appendChild(hfLon);
      }
      hfLat.value = lat;
      hfLon.value = lon;
      updateTransportLink();
      try{ updateCurrencyLink(); }catch(e){}
      // DO NOT trigger search here!
    } else if (ev.target !== cityInput && !ev.target.closest('#city-suggestions')) {
      hideCitySuggestions();
    }
  });
}

document.getElementById('searchBtn').addEventListener('click', async () => {
  let city = (document.getElementById('city').value || '').trim();
  let query = document.getElementById('query') ? document.getElementById('query').value : '';

  // Helpful fallback: if user typed "<query> in <city>" into the query box, infer the city.
  if (!city) {
    const m = String(query || '').match(/\bin\s+([^,].+)$/i);
    if (m && m[1]) {
      city = m[1].trim();
      const cityEl = document.getElementById('city');
      if (cityEl) cityEl.value = city;
      updateQueryEnabledState();
    }
  }

  if (!city) {
    const resEl = document.getElementById('results');
    if (resEl) resEl.innerHTML = '<div class="error">Please enter a city first (e.g. “Lisbon, Portugal”).</div>';
    return;
  }

  // Normalize for Wikivoyage food highlights: if query contains 'top food', send 'top food' to backend
  if (/top food/i.test(query)) {
    query = 'top food';
  }
  const user_lat = document.getElementById('user_lat') ? document.getElementById('user_lat').value : undefined;
  const user_lon = document.getElementById('user_lon') ? document.getElementById('user_lon').value : undefined;
  const resEl = document.getElementById('results');
  if (!resEl) return;
  // Show a contextual spinner while searching
  resEl.innerHTML = getContextualSpinner(query);
  try {
    // abortable fetch with client-side timeout to avoid hanging the UI when backend is slow
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), timeoutMs);
    const resp = await fetch(`${API_BASE}/search`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      signal: controller.signal,
      body: JSON.stringify({city, q: query, user_lat, user_lon, max_results: 15, timeout: 25})
    });
    clearTimeout(tid);
    if (!resp.ok) {
      const txt = await resp.text().catch(() => '');
      throw new Error(`Search failed (HTTP ${resp.status}). ${txt ? txt.slice(0, 200) : ''}`);
    }
    const j = await resp.json();
    console.log('[DEBUG] /search response:', j);
    if (!j || !j.venues) {
      resEl.innerHTML = '<div class="error">No results.</div>';
      return;
    }
    // Separate Wikivoyage and real venues
    const wikivoyageVenues = j.venues.filter(v => v.provider === 'wikivoyage');
    const realVenues = j.venues.filter(v => v.provider !== 'wikivoyage');
    currentVenues = realVenues;
    const nudge = document.querySelector('.marco-nudge');
    if (nudge) {
      nudge.textContent = `🧭 Found ${realVenues.length} spots! Ask me which is best!`;
      nudge.style.background = '#4CAF50';
      nudge.style.color = 'white';
      nudge.style.display = 'block';
    }
    if (wikivoyageVenues.length === 0 && realVenues.length === 0) {
      resEl.innerHTML = '<div class="error">No venues found. Try a different city or budget.</div>';
      return;
    }
    let html = '';
    if (wikivoyageVenues.length > 0) {
      html += `<div class="wikivoyage-section"><h2>🍽️ Local Food Highlights (Wikivoyage)</h2>`;
      html += wikivoyageVenues.map(v => {
        const imgUrl = v.image || v.banner_url || '/static/img/dummy-img.png';
        return `<div class="card wikivoyage-card"><img class="card-img" src="${imgUrl}" alt="${v.name}" loading="lazy" onerror="this.onerror=null;this.src='/static/img/dummy-img.png'"/><h3>${v.name}</h3><p>${v.description}</p></div>`;
      }).join('');
      html += '</div>';
    }
    if (realVenues.length > 0) {
      html += `<div class="realvenues-section"><h2>🍴 Real Venues</h2>`;
      html += realVenues.map(v => {
        let card = `<div class="card">`;
        // Thumbnail (prefer venue-provided image, then fallback to banner or default placeholder)
        try {
          let imgUrl = (v.image || '').trim() || (v.banner_url || '').trim() || (v.thumbnail || '').trim();
          // Ensure we don't use empty strings; default to placeholder
          if (!imgUrl) {
            imgUrl = DEFAULT_IMAGE;
          }
          // Use a safer onerror handler with proper escaping
          const safeDefault = DEFAULT_IMAGE.replace(/'/g, "\\'");
          card += `<img class="card-img" src="${imgUrl}" alt="${v.name}" loading="lazy" onerror="if(this.src!=='${safeDefault}') this.src='${safeDefault}'"/>`;
        } catch (e) {
          card += `<img class="card-img" src="${DEFAULT_IMAGE}" alt="${v.name}" loading="lazy"/>`;
        }
        let badgeHtml = '';
        if (v.open_now === true) {
          badgeHtml = `<span class="open-badge" title="Open now">Open</span>`;
        } else if (v.open_now === false) {
          badgeHtml = `<span class="closed-badge" title="Closed now">Closed</span>`;
        } else {
          badgeHtml = `<span class="unknown-badge" title="Hours unknown">Hours</span>`;
        }
        card += `<h3>${v.name} ${badgeHtml} <span class="tag">${v.price_range}</span></h3>`;
        if (v.rating) {
          const stars = '⭐'.repeat(Math.min(5, Math.ceil(v.rating)));
          card += `<p class="meta">${stars} ${v.rating}/5</p>`;
        }
        if (v.address) {
          if (v.address.includes('Found via Web Search') || v.address.includes('Found via Web')) {
            card += `<p class="meta">${v.address}</p>`;
          } else {
            const mapUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(v.name + ' ' + v.address)}`;
            card += `<p class="meta"><a href="${mapUrl}" target="_blank" rel="noopener" class="address-link">📍 ${v.address}</a></p>`;
          }
        }
        card += `<p>${v.description}</p>`;
        if (v.opening_hours_pretty || v.opening_hours) {
          card += `<p class="meta"><strong>Hours:</strong> ${v.opening_hours_pretty || v.opening_hours}</p>`;
        }
        if (v.phone) {
          try {
            const plain = v.phone.replace(/^tel:/i, '');
            card += `<p><strong>Phone:</strong> <a href="${v.phone}" class="phone-link">${plain}</a></p>`;
          } catch (e) {
            card += `<p><strong>Phone:</strong> ${v.phone}</p>`;
          }
        }
        if (v.website) {
          card += `<p><a href="${v.website}" target="_blank" rel="noopener">Visit Website</a></p>`;
        } else if (v.osm_url) {
          card += `<p><a href="${v.osm_url}" target="_blank" rel="noopener">View on Map</a></p>`;
        }
        if (v.next_change) {
          try {
            const when = new Date(v.next_change).toLocaleString();
            card += `<p class="meta"><em>Next change:</em> ${when}</p>`;
          } catch (e) {
            card += `<p class="meta"><em>Next change:</em> ${v.next_change}</p>`;
          }
        }
        card += `</div>`;
        return card;
      }).join('');
      html += '</div>';
    }
    // If backend indicated partial results, show a banner and a 'Load more' button
    if (j.partial) {
      html = `<div class="partial-banner">Partial results — more coming <button id="loadMoreBtn" class="load-more-btn">Load more</button></div>` + html;
    }
    resEl.innerHTML = html;
    if (j.partial) {
      const loadBtn = document.getElementById('loadMoreBtn');
      if (loadBtn) {
        loadBtn.addEventListener('click', async () => {
          loadBtn.disabled = true;
          loadBtn.textContent = 'Loading…';
          // Try up to 5 times, waiting for background enrichment to populate the cache
          const maxAttempts = 5;
          let attempt = 0;
          let lastResponse = null;
          while (attempt < maxAttempts) {
            attempt += 1;
            try {
              const controller2 = new AbortController();
              const timeoutMs2 = 20000; // allow longer for cache/enrichment
              const tid2 = setTimeout(() => controller2.abort(), timeoutMs2);
              const resp2 = await fetch(`${API_BASE}/search`, {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                signal: controller2.signal,
                body: JSON.stringify({city, q: query, user_lat, user_lon, max_results: 50, timeout: 25})
              });
              clearTimeout(tid2);
              const j2 = await resp2.json();
              lastResponse = j2;
              if (!j2) break;
              // if partial is false, render and stop
              if (!j2.partial) {
                // reuse rendering logic by simulating a fresh response
                // simple approach: replace results with full payload
                const evt = new CustomEvent('search:replaceResults', {detail: j2});
                document.dispatchEvent(evt);
                loadBtn.textContent = 'Done';
                loadBtn.disabled = false;
                return;
              }
            } catch (e) {
              console.warn('Load more attempt failed', e);
            }
            // wait a bit before retry
            await new Promise(r => setTimeout(r, 2000));
          }
          // if we reach here, either still partial or failed
          loadBtn.textContent = 'Try again later';
          loadBtn.disabled = false;
          if (lastResponse && lastResponse.venues) {
            const evt = new CustomEvent('search:replaceResults', {detail: lastResponse});
            document.dispatchEvent(evt);
          }
        });
      }
    }
  } catch (e) {
    if (resEl) {
      if (e.name === 'AbortError') resEl.innerHTML = `<div class="error">Search timed out after ${Math.round(timeoutMs/1000)}s. Try a narrower query or press Search.</div>`;
      else resEl.innerHTML = `<div class="error">Error: ${e.message}</div>`;
    }
  }
});

// Return HTML for a contextual spinner based on query/category
function getContextualSpinner(query) {
  const q = (query || '').toLowerCase();
  let emoji = '🔎';
  let label = 'Searching…';
  if (/food|eat|restaurant|cuisine|dining|coffee|coffee & tea|top food|top eats/.test(q)) { emoji = '🍽️'; label = 'Finding local eats…'; }
  else if (/transport|transit|metro|bus|train|taxi/.test(q)) { emoji = '🚍'; label = 'Checking transit & routes…'; }
  else if (/historic|history|museum|sites|sights/.test(q)) { emoji = '🏛️'; label = 'Uncovering historic sites…'; }
  else if (/market|markets|shopping/.test(q)) { emoji = '🛒'; label = 'Looking for local markets…'; }
  else if (/park|nature|hike|outdoor/.test(q)) { emoji = '🌳'; label = 'Finding parks & nature…'; }
  else if (/event|events|concert|festival/.test(q)) { emoji = '🎉'; label = 'Searching events & happenings…'; }
  else if (/family|kid|kids|family friendly/.test(q)) { emoji = '👪'; label = 'Looking for family-friendly spots…'; }
  else if (/hidden|gems|local favorites|local/.test(q)) { emoji = '💎'; label = 'Hunting hidden gems…'; }

  return `
    <div class="search-spinner">
      <div class="spinner-ring" aria-hidden="true"></div>
      <div class="spinner-text">${emoji} ${label}</div>
    </div>
  `;
}

// Listener to replace results when load-more fetch returns a payload
document.addEventListener('search:replaceResults', (ev) => {
  const j = ev.detail;
  const resEl = document.getElementById('results');
  if (!resEl) return;
  // simple re-render: reuse the same logic as above for venues display
  // build html for wikivoyage and real venues
  const wikivoyageVenues = j.venues.filter(v => v.provider === 'wikivoyage');
  const realVenues = j.venues.filter(v => v.provider !== 'wikivoyage');
  let html = '';
  if (wikivoyageVenues.length > 0) {
    html += `<div class="wikivoyage-section"><h2>🍽️ Local Food Highlights (Wikivoyage)</h2>`;
    html += wikivoyageVenues.map(v => {
      const imgUrl = v.image || v.banner_url || '/static/img/dummy-img.png';
      return `<div class="card wikivoyage-card"><img class="card-img" src="${imgUrl}" alt="${v.name}" loading="lazy" onerror="this.onerror=null;this.src='/static/img/dummy-img.png'"/><h3>${v.name}</h3><p>${v.description}</p></div>`;
    }).join('');
    html += '</div>';
  }
  if (realVenues.length > 0) {
    html += `<div class="realvenues-section"><h2>🍴 Real Venues</h2>`;
    html += realVenues.map(v => {
      try {
        const imgUrl = v.image || v.banner_url || v.thumbnail || '/static/img/dummy-img.png';
        return `<div class="card"><img class="card-img" src="${imgUrl}" alt="${v.name}" loading="lazy" onerror="this.onerror=null;this.src='/static/img/dummy-img.png'"/><h3>${v.name}</h3><p>${v.description || ''}</p></div>`;
      } catch (e) { return `<div class="card"><img class="card-img" src="/static/img/dummy-img.png" alt="${v.name}" loading="lazy" onerror="this.onerror=null;this.src='/static/img/dummy-img.png'"/><h3>${v.name}</h3><p>${v.description || ''}</p></div>`; }
    }).join('');
    html += '</div>';
  }
  resEl.innerHTML = html;
});

// Marco Chat logic
const marcoFab = document.getElementById('marcoFab');
const marcoChat = document.getElementById('marcoChat');
const closeChat = document.getElementById('closeChat');
const chatInput = document.getElementById('chatInput');
const chatSend = document.getElementById('chatSend');
const chatMessages = document.getElementById('chatMessages');
const chatChips = document.getElementById('chatChips');

const DEFAULT_CHIPS = ["Kid friendly?", "Best view?", "Romantic?", "Open late?"];

function renderChips(chips = DEFAULT_CHIPS) {
  if (!chatChips) return;
  chatChips.innerHTML = '';
  chips.forEach(text => {
    const btn = document.createElement('div');
    btn.className = 'chat-chip';
    btn.textContent = text;
    btn.onclick = () => {
      chatInput.value = `Of these results, which is ${text.toLowerCase().replace('?','')}`;
      chatSend.click();
    };
    chatChips.appendChild(btn);
  });
}
renderChips();

if (marcoFab) {
  marcoFab.addEventListener('click', () => {
    marcoChat.classList.toggle('open');
    const nudge = document.querySelector('.marco-nudge');
    if (nudge) nudge.style.display = 'none';
    if (marcoChat.classList.contains('open')) chatInput.focus();
  });
}
if (closeChat) {
  closeChat.addEventListener('click', () => marcoChat.classList.remove('open'));
}

function markdownToHtml(text) {
  let html = text;
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  return html.replace(/\n/g, '<br>');
}

function appendChat(sender, text) {
  const div = document.createElement('div');
  div.className = sender === 'You' ? 'message user' : 'message bot';
  div.innerHTML = markdownToHtml(String(text));
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

if (chatSend && chatInput) {
  chatSend.addEventListener('click', async () => {
    const q = chatInput.value.trim();
    if (!q) return;
    const currentCity = document.getElementById('city').value.trim();
    appendChat('You', q);
    chatInput.value = '';
    const loadingMessage = document.createElement('div');
    loadingMessage.className = 'message bot';
    loadingMessage.textContent = 'Thinking...';
    chatMessages.appendChild(loadingMessage);
    try {
      const resp = await fetch('/semantic-search', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          q, 
          city: currentCity, 
          mode: 'explorer',
          venues: currentVenues.slice(0, 10),
          weather: currentWeather
        })
      });
      const j = await resp.json();
      chatMessages.removeChild(loadingMessage);
      if (j.error) appendChat('AI', `Marco here: I had a bit of trouble finding that. ${j.error}`);
      else if (j.answer) appendChat('AI', j.answer);
      else appendChat('AI', "I'm not quite sure about that one, partner. Try asking about local food or sights!");
    } catch (e) {
      chatMessages.removeChild(loadingMessage);
      appendChat('AI', `Marco here: My explorer's compass is spinning! (Error: ${e.message})`);
    }
  });
  chatInput.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); chatSend.click(); } });
}

// Currency converter
document.addEventListener('DOMContentLoaded', () => {
  const convertBtn = document.getElementById('convertBtn');
  const convertResult = document.getElementById('convertResult');
  if (convertBtn && convertResult) {
    convertBtn.addEventListener('click', async () => {
      const amountEl = document.getElementById('amount');
      const amount = amountEl ? parseFloat(amountEl.value) : 0;
      const fromCurr = document.getElementById('fromCurr').value;
      const toCurr = document.getElementById('toCurr').value;
      if (!amount || amount <= 0) { convertResult.innerHTML = '<div class="error">Valid amount required.</div>'; return; }
      convertResult.innerHTML = '<div class="loading">Converting…</div>';
      try {
        const resp = await fetch('/convert', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({amount, from: fromCurr, to: toCurr}) });
        const j = await resp.json();
        convertResult.innerHTML = j.result ? `<div class="success">${j.result}</div>` : `<div class="error">${j.error}</div>`;
      } catch (e) { convertResult.innerHTML = `<div class="error">Error: ${e.message}</div>`; }
    });
  }
});

// Weather widget
function showWeatherWidget(data) {
  const widget = document.getElementById('weather');
  const icon = document.getElementById('weather-icon');
  const summary = document.getElementById('weather-summary');
  const details = document.getElementById('weather-details');
  if (!widget || !icon || !summary || !details) return;
  widget.style.display = 'flex';
  icon.textContent = data.icon || '☀️';
  summary.textContent = data.summary || 'Clear sky';
  details.textContent = data.details || '';
}

async function fetchAndShowWeather(city, lat, lon) {
  const widget = document.getElementById('weather');
  if (!widget) return;
  if (!city || city.trim().length < 2) {
    showWeatherWidget({icon: '🌍', summary: 'Search for a city to see weather', details: ''});
    return;
  }
  showWeatherWidget({icon: '⏳', summary: 'Loading…', details: ''});
  try {
    const resp = await fetch('/weather', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(lat && lon ? {lat, lon, city} : {city})
    });
    const j = await resp.json();
    if (j.error || !j.weather) {
      showWeatherWidget({icon: '❓', summary: 'Weather unavailable', details: ''});
      currentWeather = null;
      return;
    }
    const w = j.weather;
    currentWeather = {
      temperature_c: w.temperature,
      temperature_f: Math.round((w.temperature * 9/5) + 32),
      wind_kmh: w.windspeed,
      wind_mph: Math.round(w.windspeed / 1.60934),
      weathercode: w.weathercode
    };
    const code = w.weathercode;
    const icons = {
      0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️', 45: '🌫️', 48: '🌫️',
      51: '🌦️', 53: '🌦️', 55: '🌦️', 56: '🌧️', 57: '🌧️',
      61: '🌦️', 63: '🌦️', 65: '🌧️', 66: '🌧️', 67: '🌧️',
      71: '🌨️', 73: '🌨️', 75: '❄️', 77: '❄️', 80: '🌧️', 81: '🌧️', 82: '🌧️',
      85: '🌨️', 86: '🌨️', 95: '⛈️', 96: '⛈️', 99: '⛈️'
    };
    const icon = icons[code] || '❓';
    const tempC = w.temperature;
    const tempF = Math.round((tempC * 9/5) + 32);
    const wind = w.windspeed;
    const windMph = Math.round(wind / 1.60934);
    showWeatherWidget({
      icon,
      summary: `Weather: ${icon}`,
      details: `${tempC}°C / ${tempF}°F, Wind ${wind} km/h / ${windMph} mph`
    });
  } catch (e) { showWeatherWidget({icon: '❌', summary: 'Weather error', details: ''}); }
}

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

const mainSearchBtn = document.getElementById('searchBtn');
if (mainSearchBtn) {
  const origHandler = mainSearchBtn.onclick;
  mainSearchBtn.addEventListener('click', async () => {
    const city = document.getElementById('city').value;
    const user_lat = document.getElementById('user_lat') ? document.getElementById('user_lat').value : undefined;
    const user_lon = document.getElementById('user_lon') ? document.getElementById('user_lon').value : undefined;
    fetchAndShowWeather(city, user_lat, user_lon);
    updateTransportLink();
    try{ updateCurrencyLink(); }catch(e){}
    if (typeof origHandler === 'function') origHandler();
  });
  // Do not trigger an automatic search on page load (prevents unexpected long searches).
  // Still update links on load.
  updateTransportLink();
  try{ updateCurrencyLink(); }catch(e){}
}

// Auto-search debounce: when the user types in the query box, optionally trigger a search
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
      if (ev.key === 'ArrowDown') {
        ev.preventDefault(); focused = Math.min(focused + 1, items.length - 1);
        items.forEach((it,i)=> it.classList.toggle('focused', i===focused));
      } else if (ev.key === 'ArrowUp') {
        ev.preventDefault(); focused = Math.max(focused - 1, 0);
        items.forEach((it,i)=> it.classList.toggle('focused', i===focused));
      } else if (ev.key === 'Enter') {
        const el = items[focused] || items[0];
        if (el) { el.click(); ev.preventDefault(); }
      }
    });
    suggestionsEl.addEventListener('mouseover', (ev) => {
      const it = ev.target.closest && ev.target.closest('.suggestion-item');
      if (!it) return;
      const items = suggestionsEl.querySelectorAll('.suggestion-item');
      items.forEach((el,i)=> el.classList.toggle('focused', el===it));
      focused = Array.from(items).indexOf(it);
    });
  }
})();
