document.getElementById('searchBtn').addEventListener('click', async () => {
  const city = document.getElementById('city').value;
  const budget = document.getElementById('budget').value;
  const q = document.getElementById('q').value;
  const googlePlacesCheckbox = document.getElementById('useGooglePlaces');
  const useGooglePlaces = googlePlacesCheckbox ? googlePlacesCheckbox.checked : false;
  const provider = useGooglePlaces ? 'google' : 'osm';
  const resEl = document.getElementById('results');
  resEl.innerHTML = '<div class="loading">Searching…</div>';
  try {
    const resp = await fetch('/search', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({city, budget, q, provider})
    });
    const j = await resp.json();
    if (!j || !j.venues) {
      resEl.innerHTML = '<div class="error">No results.</div>';
      return;
    }
    if (j.venues.length === 0) {
      resEl.innerHTML = '<div class="error">No venues found. Try a different city or budget.</div>';
      return;
    }
    resEl.innerHTML = j.venues.map(v => `
      <div class="card">
        <h3>${v.name} <span class="tag">${v.price_range}</span></h3>
        ${v.address ? `<p class="meta">${v.address}</p>` : ''}
        <p>${v.description}</p>
        ${v.rating ? `<p class="meta">⭐ ${v.rating}/5 (${v.user_ratings_total || 0} reviews)</p>` : ''}
        ${v.website ? `<p><a href="${v.website}" target="_blank" rel="noopener">Visit Website</a></p>` : ''}
        ${!v.website && v.osm_url ? `<p><a href="${v.osm_url}" target="_blank" rel="noopener">View on Map</a></p>` : ''}
        ${v.phone ? `<p>📞 ${v.phone}</p>` : ''}
      </div>
    `).join('');
  } catch (e) {
    resEl.innerHTML = `<div class="error">Error: ${e.message}</div>`;
  }
});

// Chat/query UI
const chatSend = document.getElementById('chatSend');
const chatInput = document.getElementById('chatInput');
const chatMessages = document.getElementById('chatMessages');
function markdownToHtml(text) {
  let html = text;
  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italics
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // Simple table conversion
  if (html.includes('|') && html.includes('---')) {
    const lines = html.split('\n');
    let inTable = false;
    let tableHtml = '<table class="chat-table">';
    for (let line of lines) {
      if (line.trim().startsWith('|') && !line.includes('---')) {
        const cells = line.split('|').slice(1, -1).map(c => c.trim());
        tableHtml += '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>';
        inTable = true;
      } else if (inTable && !line.trim()) {
        break;
      }
    }
    tableHtml += '</table>';
    // Replace the table part
    const tableStart = html.indexOf('|');
    const tableEnd = html.lastIndexOf('|') + 1;
    html = html.substring(0, tableStart) + tableHtml + html.substring(tableEnd);
  }
  // URLs
  html = html.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  return html.replace(/\n/g, '<br>');
}

function appendChat(sender, text) {
  const div = document.createElement('div');
  div.className = sender === 'You' ? 'message user' : 'message ai';
  const displayName = sender === 'AI' ? 'Marco' : sender;
  const processedText = markdownToHtml(String(text));
  div.innerHTML = `<strong>${displayName}:</strong> ${processedText}`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

if (chatSend && chatInput) {
  chatSend.addEventListener('click', async () => {
    const q = chatInput.value.trim();
    if (!q) return;
    const city = document.getElementById('chatCity').value.trim();  // get city
    appendChat('You', q);
    chatInput.value = '';
    appendChat('AI', 'Searching...');
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
      const resp = await fetch('/semantic-search', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({q, city, mode: 'explorer'}),
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      const j = await resp.json();
      // remove the 'Searching...' placeholder
      const last = chatMessages.lastChild;
      if (last && last.textContent && last.textContent.includes('Searching')) {
        chatMessages.removeChild(last);
      }
      if (j.error) {
        appendChat('AI', `Error: ${j.error}`);
        return;
      }
      if (j.answer) {
        appendChat('AI', j.answer);
      } else {
        appendChat('AI', 'No answer found.');
      }
    } catch (e) {
      appendChat('AI', `Error: ${e.message}`);
    }
  });
  // also allow Enter key
  chatInput.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      chatSend.click();
    }
  });
}

// Clear chat button
const clearChat = document.getElementById('clearChat');
if (clearChat) {
  clearChat.addEventListener('click', () => {
    chatMessages.innerHTML = '';
    chatInput.value = '';
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
