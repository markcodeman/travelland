async function fetchRecommendations(city, neighborhood, query, prefs = {}) {
  const resp = await fetch('/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ city, neighborhood, q: query, preferences: prefs })
  });
  if (!resp.ok) throw new Error('Recommend failed');
  return resp.json();
}

// Example usage on category selection:
async function onCategorySelect(query) {
  // assume selectedCity and selectedNeighborhood available
  try {
    const recs = await fetchRecommendations(selectedCity?.name || document.getElementById('city').value, selectedNeighborhood, query);
    // recs is an array of objects with _metadata attached
    renderRecommendations(recs);
  } catch (err) {
    console.error(err);
  }
}