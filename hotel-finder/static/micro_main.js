document.getElementById('searchBtn').addEventListener('click', async () => {
  const city = document.getElementById('city').value;
  const usePoi = document.getElementById('usePoi').checked;
  const budget = document.getElementById('budget').value;
  const q = document.getElementById('q').value;
  const resEl = document.getElementById('results');
  resEl.innerHTML = '<div class="loading">Searching…</div>';
  try {
    let j;
    if (usePoi) {
      const resp = await fetch('/poi-search', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({city, radius: 10000})
      });
      j = await resp.json();
      if (!j || !j.venues) {
        resEl.innerHTML = '<div class="error">No POIs found. Try a different city or uncheck "Use live POI".</div>';
        document.getElementById('resultsCount').innerText = '';
        return;
      }
      if (j.venues.length === 0) {
        resEl.innerHTML = '<div class="error">No POIs found. Try a different city or uncheck "Use live POI".</div>';
        document.getElementById('resultsCount').innerText = '0 results';
        return;
      }
      document.getElementById('resultsCount').innerText = `${j.venues.length} results`;
      resEl.innerHTML = j.venues.map((v, idx) => `
        <div class="card" data-idx="${idx}">
          <h3>${v.name} <span class="tag">${v.budget || ''}</span></h3>
          <p class="meta">${v.description ? v.description.substring(0,120) : ''}</p>
          <div class="full" style="display:none">${v.description ? v.description : ''}</div>
          <p><a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((v.lat||v.latitude) + ',' + (v.lon||v.longitude))}" target="_blank">Open in Maps</a></p>
        </div>
      `).join('');
      // add click-to-expand
      Array.from(document.querySelectorAll('#results .card')).forEach(c => {
        c.addEventListener('click', (ev) => {
          const full = c.querySelector('.full');
          if (!full) return;
          full.style.display = full.style.display === 'none' ? 'block' : 'none';
        });
      });
    } else {
      const resp = await fetch('/micro-search', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({city, budget, q})
      });
      j = await resp.json();
      if (!j || !j.venues) {
        resEl.innerHTML = '<div class="error">No results.</div>';
        document.getElementById('resultsCount').innerText = '';
        return;
      }
      if (j.venues.length === 0) {
        resEl.innerHTML = '<div class="error">No venues found. Try a different city or budget.</div>';
        document.getElementById('resultsCount').innerText = '0 results';
        return;
      }
      document.getElementById('resultsCount').innerText = `${j.venues.length} results`;
      resEl.innerHTML = j.venues.map((v, idx) => `
        <div class="card" data-idx="${idx}">
          <h3>${v.name} <span class="tag">${v.price_range || v.budget || ''}</span></h3>
          <p class="meta">${v.address || ''} • ${v.tags || ''}</p>
          <div class="full" style="display:none">${v.description || ''}</div>
          <p><a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((v.latitude||v.lat) + ',' + (v.longitude||v.lon))}" target="_blank">Open in Maps</a></p>
        </div>
      `).join('');
      Array.from(document.querySelectorAll('#results .card')).forEach(c => {
        c.addEventListener('click', (ev) => {
          const full = c.querySelector('.full');
          if (!full) return;
          full.style.display = full.style.display === 'none' ? 'block' : 'none';
        });
      });
    }
  } catch (e) {
    resEl.innerHTML = `<div class="error">Error: ${e.message}</div>`;
  }
});

// default search
document.getElementById('searchBtn').click();
