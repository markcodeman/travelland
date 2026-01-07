# City Microguides — Budget Picks

Discover affordable restaurants and places with real-time data from OpenStreetMap, OpenTripMap, and DuckDuckGo.

## ✨ Features

- **Multi-Provider search**: Orchestrates Overpass (OSM), DuckDuckGo, and OpenTripMap for high-quality data.
- **Up to 200 Results**: Broader venue coverage for better exploration.
- **Budget Filtering**: Find affordable gems (under $20), moderate favorites ($20-50), or explore all options.
- **Local Gems Only**: Filter out major chains to find authentic local eateries.
- **5 Result Optimization**: Based on Miller's Law for optimal cognitive load (7±2 items).
- **🧭 Marco AI Chat**: Personalized local tips powered by Groq and Llama 3.1.
- **Production Ready**: Dynamic PORT binding, host='0.0.0.0', and production mode.

## 🚀 Quick Start

### Local Development

1. Clone and navigate:
```bash
cd city-guides
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
# Create a `.env` file in this directory and add your keys
# Example:
# GROQ_API_KEY=your_key_here
# OPENTRIPMAP_KEY=your_key_here
```

4. Run:
```bash
python app.py
```

Open http://127.0.0.1:5010

### Render.com Deployment

See `QUICK_START.md` for full deployment guide.

**Quick steps:**
1. Set `GROQ_API_KEY` and `OPENTRIPMAP_KEY` in Render.com Environment variables
2. Deploy (auto-deploys on push to main)
3. Test the "Use Google Places" checkbox!

## 🧪 Testing

Run the test suite:
```bash
python test_integration.py    # Structure validation
python test_google_places.py  # API integration test
python test_max_results.py    # Verify 5 results config
```

## 📖 Documentation

- **QUICK_START.md** - Quick deployment guide (start here!)
- **DEPLOY_NOW.md** - Detailed deployment steps
- **TESTING_API_KEYS.md** - API key setup and testing
- **RENDER_SETUP.md** - Complete Render.com configuration
- **Environment variables** - create a `.env` file with the required keys (see `QUICK_START.md`)

## 🔒 API Requirements

## ⚠️ Nominatim usage

This project uses the OpenStreetMap Nominatim API client-side for lightweight city/place autocomplete. Nominatim terms require a valid HTTP Referer or User-Agent and fair-use (rate limits). For production use consider hosting your own instance or using a commercial geocoding provider if you expect heavy traffic.

Client requests are debounced and limited to a few suggestions to reduce impact on the public Nominatim service.

**Required for Google Places features:**
- Google Places API Key (free tier: 28,000+ requests/month)
- Enable "Places API (New)" in Google Cloud Console

**Optional for AI features:**
- GROQ_API_KEY for Marco's Explorer chat
- OPENTRIPMAP_KEY for additional POI data

## 🎯 What's New in This Version

### From PR #2:
- ✅ "Use Google Places" checkbox toggle
- ✅ 5 results optimization (psychology-based UX)
- ✅ Expanded cuisine support
- ✅ Render.com deployment fixes
- ✅ Comprehensive test suite

### From PR #3:
- ✅ 200 result capacity (up from 50)
- ✅ Price level mapping (Google Places price_level → budget categories)
- ✅ Fixed Google Maps links (removed markdown double-processing)
- ✅ 60s timeout for complex queries (up from 30s)
- ✅ Real ratings and review counts
- ✅ Better error handling

## 🌐 Live Demo

Check out the Render.com deployment for a live example of Google Places integration in action!

---

**Questions?** Open an issue or check the documentation files!