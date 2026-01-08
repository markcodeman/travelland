let currentVenues = [];
let currentWeather = null;

// --- Nominatim autocomplete helpers ---
const cityInput = document.getElementById('city');
const suggestionsEl = document.getElementById('city-suggestions');
let nominatimTimeout = null;

function hideCitySuggestions() {
  if (suggestionsEl) suggestionsEl.style.display = 'none';
}

function showCitySuggestions(items) {
  if (!suggestionsEl) return;
  if (!items || items.length === 0) {
    hideCitySuggestions();
    return;
  }
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
  cityInput.addEventListener('input', (e) => {
    const v = e.target.value.trim();
    if (nominatimTimeout) clearTimeout(nominatimTimeout);
    if (!v || v.length < 3) {
      hideCitySuggestions();
      return;
    }
    nominatimTimeout = setTimeout(async () => {
      try {
        const items = await fetchCitySuggestions(v);
        showCitySuggestions(items);
      } catch (err) {
        hideCitySuggestions();
        console.warn('Nominatim error', err);
      }
    }, 300);
  });

  document.addEventListener('click', (ev) => {
    const el = ev.target.closest && ev.target.closest('.suggestion-item');
    if (el) {
      const display = el.textContent || el.innerText;
      const lat = el.getAttribute('data-lat');
      const lon = el.getAttribute('data-lon');
      cityInput.value = display;
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
    } else if (ev.target !== cityInput && !ev.target.closest('#city-suggestions')) {
      hideCitySuggestions();
    }
  });
}

document.getElementById('searchBtn').addEventListener('click', async () => {
  const city = document.getElementById('city').value;
  const user_lat = document.getElementById('user_lat') ? document.getElementById('user_lat').value : undefined;
  const user_lon = document.getElementById('user_lon') ? document.getElementById('user_lon').value : undefined;
  const budget = document.getElementById('budget').value;
  const q = document.getElementById('q').value;
  const localOnly = document.getElementById('localOnly').checked;
  const resEl = document.getElementById('results');
  if (!resEl) return;
  resEl.innerHTML = '<div class="loading">Searching…</div>';
  try {
    const resp = await fetch('/search', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({city, budget, q, localOnly, user_lat, user_lon})
    });
    const j = await resp.json();
    if (!j || !j.venues) {
      resEl.innerHTML = '<div class="error">No results.</div>';
      return;
    }
    currentVenues = j.venues;
    const nudge = document.querySelector('.marco-nudge');
    if (nudge) {
      nudge.textContent = `🧭 Found ${j.venues.length} spots! Ask me which is best!`;
      nudge.style.background = '#4CAF50';
      nudge.style.color = 'white';
      nudge.style.display = 'block';
    }
    if (j.venues.length === 0) {
      resEl.innerHTML = '<div class="error">No venues found. Try a different city or budget.</div>';
      return;
    }
    resEl.innerHTML = j.venues.map(v => {
      let card = `<div class="card">`;
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
  } catch (e) {
    if (resEl) resEl.innerHTML = `<div class="error">Error: ${e.message}</div>`;
  }
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
  // Initial search
  mainSearchBtn.click();
  updateTransportLink();
  try{ updateCurrencyLink(); }catch(e){}
}

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
