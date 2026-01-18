# Testing API Keys (Groq & OpenTripMap)

## 🧪 Quick API Key Test

### Method 1: Test Groq API (for Marco AI)

Run this command to test your Groq key:

```bash
cd city-guides
python -c "
import os
import requests
from dotenv import load_dotenv

load_dotenv()
key = os.getenv('GROQ_API_KEY')

if not key:
    print('❌ GROQ_API_KEY not found in environment')
    exit(1)

print(f'✓ Key found: {key[:10]}...')

headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
payload = {
    'model': 'llama-3.1-8b-instant',
    'messages': [{'role': 'user', 'content': 'Say hello in explorer theme'}]
}
try:
    r = requests.post('https://api.groq.com/openai/v1/chat/completions', json=payload, headers=headers)
    r.raise_for_status()
    print('✓ Groq API works!')
    print('→ Response:', r.json()['choices'][0]['message']['content'])
except Exception as e:
    print(f'❌ Groq Error: {e}')
"
```

### Method 2: Test OpenTripMap (for Enhanced Venue Data)

```bash
cd city-guides
python -c "
import os
import requests
from dotenv import load_dotenv

load_dotenv()
key = os.getenv('OPENTRIPMAP_KEY')

if not key:
    print('❌ OPENTRIPMAP_KEY not found in environment')
    exit(1)

params = {'apikey': key, 'lat': 51.5074, 'lon': -0.1278, 'radius': 1000, 'kinds': 'restaurants'}
try:
    r = requests.get('https://api.opentripmap.com/0.1/en/places/radius', params=params)
    r.raise_for_status()
    print('✓ OpenTripMap API works!')
    print(f'→ Found {len(r.json().get(\"features\", []))} locations in London')
except Exception as e:
    print(f'❌ OpenTripMap Error: {e}')
"
```

---

## 🔑 Getting Your API Keys

### Groq API (Intelligence)
1. Go to [Groq Cloud Console](https://console.groq.com/)
2. Create an account
3. Go to **API Keys** and create one
4. Copy to your `.env` as `GROQ_API_KEY`

### OpenTripMap (Venue Ratings/Details)
1. Go to [OpenTripMap API](https://opentripmap.io/product)
2. Sign up for a free API key
3. Copy to your `.env` as `OPENTRIPMAP_KEY`

---

## 🔧 Troubleshooting

### Key Not Loading
Ensure your `.env` file is in the `city-guides/` folder, NOT the root folder.
The app loads it from `city-guides/.env`.

### Rate Limits
Free keys have limits. If you see 429 errors, wait a minute before retrying.
DuckDuckGo and Overpass (OSM) do not require keys but are also rate-limited.

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
