let currentVenues = [];

document.getElementById('searchBtn').addEventListener('click', async () => {
  const city = document.getElementById('city').value;
  const budget = document.getElementById('budget').value;
  const q = document.getElementById('q').value;
  const localOnly = document.getElementById('localOnly').checked;
  const resEl = document.getElementById('results');
  resEl.innerHTML = '<div class="loading">Searching…</div>';
  try {
    const resp = await fetch('/search', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({city, budget, q, localOnly})
    });
    const j = await resp.json();
    if (!j || !j.venues) {
      resEl.innerHTML = '<div class="error">No results.</div>';
      return;
    }
    currentVenues = j.venues; // Store globally for Marco context
    
    // Marco Chimes in when search results appear
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
      card += `<h3>${v.name} <span class="tag">${v.price_range}</span></h3>`;
      
      // Add rating if available
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
      
      // Add phone if available
      if (v.phone) {
        card += `<p><strong>Phone:</strong> ${v.phone}</p>`;
      }
      
      if (v.website) {
        card += `<p><a href="${v.website}" target="_blank" rel="noopener">Visit Website</a></p>`;
      } else if (v.osm_url) {
        card += `<p><a href="${v.osm_url}" target="_blank" rel="noopener">View on Map</a></p>`;
      }
      
      card += `</div>`;
      return card;
    }).join('');
  } catch (e) {
    resEl.innerHTML = `<div class="error">Error: ${e.message}</div>`;
  }
});

// Marco Chat Toggle Logic
const marcoFab = document.getElementById('marcoFab');
const marcoChat = document.getElementById('marcoChat');
const closeChat = document.getElementById('closeChat');
const chatInput = document.getElementById('chatInput');
const chatSend = document.getElementById('chatSend');
const chatMessages = document.getElementById('chatMessages');
const chatChips = document.getElementById('chatChips');

const DEFAULT_CHIPS = [
  "Kid friendly?",
  "Best view?",
  "Romantic?",
  "Open late?"
];

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

// Initial chips
renderChips();

if (marcoFab) {
  marcoFab.addEventListener('click', () => {
    marcoChat.classList.toggle('open');
    // Hide nudge once clicked
    const nudge = document.querySelector('.marco-nudge');
    if (nudge) nudge.style.display = 'none';
    
    if (marcoChat.classList.contains('open')) {
      chatInput.focus();
    }
  });
}

if (closeChat) {
  closeChat.addEventListener('click', () => {
    marcoChat.classList.remove('open');
  });
}

function markdownToHtml(text) {
  let html = text;
  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italics
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // URLs
  html = html.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  return html.replace(/\n/g, '<br>');
}

function appendChat(sender, text) {
  const div = document.createElement('div');
  div.className = sender === 'You' ? 'message user' : 'message bot';
  const processedText = markdownToHtml(String(text));
  div.innerHTML = processedText;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

if (chatSend && chatInput) {
  chatSend.addEventListener('click', async () => {
    const q = chatInput.value.trim();
    if (!q) return;

    // Try to get current city from the main search bar to provide context to Marco
    const currentCity = document.getElementById('city').value.trim();
    
    appendChat('You', q);
    chatInput.value = '';
    
    const loadingMessage = document.createElement('div');
    loadingMessage.className = 'message bot';
    loadingMessage.textContent = 'Thinking...';
    chatMessages.appendChild(loadingMessage);

    try {
      // Pick top 10 current venues to avoid context bloat
      const contextualVenues = currentVenues.slice(0, 10);
      
      const resp = await fetch('/semantic-search', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          q, 
          city: currentCity, 
          mode: 'explorer',
          venues: contextualVenues
        })
      });
      const j = await resp.json();
      
      chatMessages.removeChild(loadingMessage);

      if (j.error) {
        appendChat('AI', `Marco here: I had a bit of trouble finding that. ${j.error}`);
      } else if (j.answer) {
        appendChat('AI', j.answer);
      } else {
        appendChat('AI', "I'm not quite sure about that one, partner. Try asking about local food or sights!");
      }
    } catch (e) {
      chatMessages.removeChild(loadingMessage);
      appendChat('AI', `Marco here: My explorer's compass is spinning! (Error: ${e.message})`);
    }
  });

  chatInput.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      chatSend.click();
    }
  });
}

// Currency converter
const convertBtn = document.getElementById('convertBtn');
const convertResult = document.getElementById('convertResult');
if (convertBtn && convertResult) {
  convertBtn.addEventListener('click', async () => {
    const amount = parseFloat(document.getElementById('amount').value);
    const fromCurr = document.getElementById('fromCurr').value;
    const toCurr = document.getElementById('toCurr').value;
    if (!amount || amount <= 0) {
      convertResult.innerHTML = '<div class="error">Please enter a valid amount.</div>';
      return;
    }
    convertResult.innerHTML = '<div class="loading">Converting…</div>';
    try {
      const resp = await fetch('/convert', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({amount, from: fromCurr, to: toCurr})
      });
      const j = await resp.json();
      if (j.result) {
        convertResult.innerHTML = `<div class="success">${j.result}</div>`;
      } else {
        convertResult.innerHTML = `<div class="error">${j.error}</div>`;
      }
    } catch (e) {
      convertResult.innerHTML = `<div class="error">Error: ${e.message}</div>`;
    }
  });
}

// Yelp cheap restaurants button
// Yelp integration removed

// kick off default search
document.getElementById('searchBtn').click();
