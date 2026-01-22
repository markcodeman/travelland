Public Transport page — no-key mode

This project intentionally uses a "no-key" default for the Public Transport hub.

What works without keys:
- "Open Google Transit Map" deep-link (opens Google Maps Transit view) — no API key required.
- Fare calculator UI — purely client-side arithmetic.
- Marco transit tips via `/semantic-search` will attempt to use the AI if `GROQ_API_KEY` is present; otherwise, the code falls back to friendly generic tips (no key required to view the page).
- Nominatim geocoding/autocomplete and Open-Meteo for weather are keyless services (observe their usage policies and rate limits).

Optional upgrades that require API keys:
- Embedding interactive Google Maps with the JS API (requires API key & billing).
- Using official transit authority APIs (varies by city; most require API keys or registration).

How to enable optional APIs (summary):
1. Add keys to a `.env` file (create one at project root):
   GROQ_API_KEY=your_groq_key
   GOOGLE_MAPS_API_KEY=your_google_key
2. Update the front-end template to include Google Maps JS when `GOOGLE_MAPS_API_KEY` is set.
3. Implement server-side proxies for any transit API that requires secret keys.

If you want, I can implement optional support behind feature flags so the default stays keyless.