# Testing Google Places API Key

## 🧪 Quick API Key Test

### Method 1: Interactive Test Script

Run this command to test your API key:

```bash
cd city-guides
python -c "
import os
from dotenv import load_dotenv
import googlemaps

load_dotenv()
key = os.getenv('GOOGLE_PLACES_API_KEY')

if not key:
    print('❌ GOOGLE_PLACES_API_KEY not found in environment')
    print('→ Create .env file with: GOOGLE_PLACES_API_KEY=your_key_here')
    exit(1)

print(f'✓ API key found: {key[:10]}...{key[-4:]}')

try:
    gmaps = googlemaps.Client(key=key)
    result = gmaps.places('restaurants in Tokyo')
    
    if result.get('status') == 'OK':
        print('✓ API key works! Found results')
        print(f'→ {len(result.get(\"results\", []))} places returned')
    else:
        print(f'⚠ API returned status: {result.get(\"status\")}')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

### Method 2: Run Test Suite

```bash
cd city-guides
python test_google_places.py
```

Expected output:
```
✓ Testing Google Places provider import...
  ✓ places_provider imported successfully
✓ Testing googlemaps package...
  ✓ googlemaps package available
✓ Testing API key environment...
  ✓ GOOGLE_PLACES_API_KEY is set
  → Key: AIzaSyBxxx...xyz1
...
✓ All Google Places tests passed!
```

---

## 🔑 Getting Your API Key

### Step 1: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Name it (e.g., "Travelland")
4. Click **Create**

### Step 2: Enable APIs
1. Go to **APIs & Services** → **Library**
2. Search for and enable:
   - **Places API (New)** ✅
   - **Maps JavaScript API** ✅ (optional, for map features)

### Step 3: Create API Key
1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **API Key**
3. Copy your API key (looks like: `AIzaSyBxxxxxxxxxxxxxxxxxxxxx`)
4. Click **Restrict Key** (recommended)

### Step 4: Restrict Your Key (Optional but Recommended)
1. **Application restrictions**:
   - Choose **HTTP referrers (web sites)**
   - Add your domains:
     - `https://your-app.onrender.com/*`
     - `http://localhost:5010/*` (for local testing)

2. **API restrictions**:
   - Choose **Restrict key**
   - Select:
     - Places API (New)
     - Maps JavaScript API

3. Click **Save**

---

## 🧪 Test API Key Locally

### Setup .env file:
```bash
cd city-guides
# Create a `.env` file in this directory and add your key
# Example:
# GOOGLE_PLACES_API_KEY=AIzaSyBxxxxxxxxxxxxxxxxxxxxx
# FLASK_ENV=development
# PORT=5010
```

Your `.env` should look like:
```
GOOGLE_PLACES_API_KEY=AIzaSyBxxxxxxxxxxxxxxxxxxxxx
FLASK_ENV=development
PORT=5010
```

### Run the App:
```bash
python app.py
```

### Test in Browser:
1. Open http://localhost:5010
2. Check ☑️ "Use Google Places"
3. Search "Tokyo restaurants"
4. You should see:
   - ⭐ Star ratings
   - Review counts
   - Price levels
   - Phone numbers

---

## 🚨 Common Issues

### Issue: "GOOGLE_PLACES_API_KEY not found"
**Solution**:
```bash
# Check if .env exists
ls -la .env

# Check if key is set
cat .env | grep GOOGLE_PLACES_API_KEY

# Verify it's loaded
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('GOOGLE_PLACES_API_KEY'))"
```

### Issue: "API key not valid"
**Solutions**:
1. Verify key in Google Cloud Console
2. Check that Places API is enabled
3. Remove any restrictions temporarily to test
4. Wait 5 minutes after creating key (propagation delay)

### Issue: "REQUEST_DENIED"
**Solutions**:
1. Enable "Places API (New)" in Google Cloud Console
2. Check billing is enabled (free tier is fine)
3. Verify API key restrictions aren't too strict

### Issue: "OVER_QUERY_LIMIT"
**Solution**: You've exceeded free tier (28,000 requests/month)
- Wait until next month
- Upgrade to paid tier
- Implement caching to reduce API calls

---

## 📊 Monitor API Usage

### Check Usage:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Dashboard**
3. Click on **Places API**
4. View **Metrics** tab to see:
   - Requests per day
   - Errors
   - Latency

### Set Budget Alerts:
1. Go to **Billing** → **Budgets & alerts**
2. Click **Create Budget**
3. Set limit (e.g., $10/month)
4. Add email notification

---

## 💡 Tips

### For Development:
- Use `.env` file for local API key
- Never commit `.env` to git
- Add `.env` to `.gitignore` (already done)

### For Production:
- Set API key in Render.com environment variables
- Restrict key to your production domain
- Monitor usage regularly
- Set budget alerts

### For Testing:
- Use separate API key for testing
- Implement caching to reduce API calls
- Consider mock data for unit tests

---

## ✅ Verification Checklist

Before deploying:
- [ ] API key works locally
- [ ] test_google_places.py passes
- [ ] Places API is enabled in Google Cloud
- [ ] Billing is set up (even for free tier)
- [ ] API key is restricted (optional but recommended)
- [ ] Budget alerts are configured
- [ ] .env is in .gitignore
- [ ] Key is set in Render.com environment

---

**Need more help?** Check `QUICK_START.md` or open an issue!
