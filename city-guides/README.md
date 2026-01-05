# City Microguides — Budget Picks

Discover affordable restaurants and places with real-time data from OpenStreetMap and Google Places.

## ✨ Features

- **Dual Data Sources**: Toggle between OpenStreetMap (default, free) and Google Places (enhanced data)
- **Up to 200 Results**: Broader venue coverage for better exploration
- **Real Ratings & Reviews**: ⭐ Star ratings and user review counts from Google Places
- **Price Level Mapping**: Clear price indicators ($, $$, $$$, $$$$) from Google Places API
- **Expanded Cuisines**: Support for Irish, Indian, Thai, Vietnamese, Greek, Spanish, German, British, and more
- **Budget Filtering**: Find places under $15 (cheap), $15-30 (mid), or explore all options
- **5 Result Optimization**: Based on Miller's Law for optimal cognitive load (7±2 items)
- **Production Ready**: Dynamic PORT binding, host='0.0.0.0', and production mode
- **Enhanced Data**: Phone numbers, websites, and accurate addresses from Google Places

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
# Create a `.env` file in this directory and add your `GOOGLE_PLACES_API_KEY`
# Example:
# GOOGLE_PLACES_API_KEY=your_api_key_here
```

4. Run:
```bash
python app.py
```

Open http://127.0.0.1:5010

### Render.com Deployment

See `QUICK_START.md` for full deployment guide.

**Quick steps:**
1. Set `GOOGLE_PLACES_API_KEY` in Render.com Environment variables
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