# Quick Start Guide - Travelland City Guides

## 🚀 Deploy in 2 Minutes

### Prerequisites
- Groq AI API Key ([Get one here](https://console.groq.com/)) - *Optional, for Marco AI*
- OpenTripMap API Key ([Get one here](https://opentripmap.io/product)) - *Optional, for enhanced data*
- Render.com account (free tier works great!)

### Step 1: Set API Keys in Render
1. Go to your Render.com dashboard
2. Select your service (or create one following DEPLOY_NOW.md)
3. Go to **Environment** tab
4. Add: `GROQ_API_KEY` = your_api_key_here
5. Add: `OPENTRIPMAP_KEY` = your_api_key_here
6. Click **Save Changes**

### Step 2: Deploy
- If auto-deploy is enabled: **Done!** ✅
- If not: Click **Manual Deploy** → **Deploy latest commit**

### Step 3: Test
1. Open your app URL
2. Check the ☑️ **"Local Gems Only"** checkbox
3. Search for a city (e.g., "Tokyo")
4. See local spots, 🧭 Marco AI tips, and budget-filtered eats!

## 🧪 Local Development

### Setup
```bash
cd city-guides
pip install -r requirements.txt
# Create a `.env` file in this directory and add your API keys
# Example:
# GROQ_API_KEY=your_key_here
# OPENTRIPMAP_KEY=your_key_here
python app.py
```

### Test the Features
```bash
# Run all tests
python test_integration.py
python test_max_results.py
```

## ✨ Features

### From PR #2:
- ✅ Multi-provider search (Overpass, OpenTripMap, DuckDuckGo)
- ✅ 5 results optimization (optimal cognitive load)
- ✅ Expanded cuisines: Irish, Indian, Thai, Vietnamese, Greek, Spanish, German, British
- ✅ Render.com deployment ready (dynamic PORT, host='0.0.0.0')
- ✅ Comprehensive testing suite

### From PR #3:
- ✅ 200 result limit (increased from 50)
- ✅ Price level heuristics from OSM and search snippets
- ✅ Fixed map links (no more broken HTML)
- ✅ 60s Overpass timeout (increased from 30s)
- ✅ Integrated 🧭 Marco AI for local tips
- ✅ Better error handling with user-friendly messages

## 🔒 API Key Info

- **Free Tier**: 28,000+ requests/month
- **Cost**: $0 for most users
- **Enable APIs**: Places API (New), Maps JavaScript API
- **Restrict Key**: Add your domain to allowed referrers

## 📖 Need More Help?

- Deployment: See `DEPLOY_NOW.md`
- API Key Testing: See `TESTING_API_KEYS.md`
- Render Setup: See `RENDER_SETUP.md`
- Pre-deploy Checks: See `PRE_DEPLOY_CHECKLIST.md`

## 🎯 Expected Results

After deployment, users can:
1. Toggle between OpenStreetMap (default, free) and Google Places data
2. See up to 200 venues per search
3. View real ratings (⭐), review counts, and price levels
4. Get phone numbers and websites for venues
5. Use expanded cuisine filters
6. Click working Google Maps links

---

**Questions?** Check the other documentation files or open an issue!
