# Quick Start Guide - Travelland City Guides

## 🚀 Deploy in 2 Minutes

### Prerequisites
- Google Places API Key ([Get one here](https://console.cloud.google.com/apis/credentials))
- Render.com account (free tier works great!)

### Step 1: Set API Key in Render
1. Go to your Render.com dashboard
2. Select your service (or create one following DEPLOY_NOW.md)
3. Go to **Environment** tab
4. Add: `GOOGLE_PLACES_API_KEY` = your_api_key_here
5. Click **Save Changes**

### Step 2: Deploy
- If auto-deploy is enabled: **Done!** ✅
- If not: Click **Manual Deploy** → **Deploy latest commit**

### Step 3: Test
1. Open your app URL
2. Check the ☑️ **"Use Google Places"** checkbox
3. Search for a city (e.g., "Tokyo")
4. See ⭐ ratings, 📞 phone numbers, and $$ price levels!

## 🧪 Local Development

### Setup
```bash
cd city-guides
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GOOGLE_PLACES_API_KEY
python app.py
```

### Test the Features
```bash
# Run all tests
python test_integration.py
python test_google_places.py
python test_max_results.py
```

## ✨ Features

### From PR #2:
- ✅ "Use Google Places" checkbox in UI
- ✅ 5 results optimization (optimal cognitive load)
- ✅ Expanded cuisines: Irish, Indian, Thai, Vietnamese, Greek, Spanish, German, British
- ✅ Render.com deployment ready (dynamic PORT, host='0.0.0.0')
- ✅ Comprehensive testing suite

### From PR #3:
- ✅ 200 result limit (increased from 50)
- ✅ Price level mapping: 0-1→cheap($), 2→mid($$), 3-4→expensive($$$-$$$$)
- ✅ Fixed Google Maps links (no more broken HTML)
- ✅ 60s Overpass timeout (increased from 30s)
- ✅ Real ratings and review counts from Google Places
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
