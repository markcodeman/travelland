# Deployment Guide - Render.com

## 📦 Step-by-Step Deployment

### Method 1: Auto-Deploy from GitHub (Recommended)

#### Step 1: Connect Repository
1. Go to [Render.com Dashboard](https://dashboard.render.com/)
2. Click **New +** → **Web Service**
3. Connect your GitHub account if not already connected
4. Select your `travelland` repository

#### Step 2: Configure Service
Fill in these settings:

**Basic Settings:**
- **Name**: `travelland-city-guides` (or your preferred name)
- **Region**: Choose closest to your users
- **Branch**: `main` (or your deployment branch)
- **Root Directory**: `city-guides`
- **Runtime**: `Python 3`

**Build & Deploy Settings:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python app.py`

**Instance Type:**
- Select **Free** tier (works great for this app!)

#### Step 3: Environment Variables
Click **Environment** tab and add:

```
GOOGLE_PLACES_API_KEY=your_api_key_here
FLASK_ENV=production
```

Optional (if using AI features):
```
GROQ_API_KEY=your_groq_key_here
OPENTRIPMAP_KEY=your_opentripmap_key_here
```

#### Step 4: Deploy
1. Click **Create Web Service**
2. Wait 2-5 minutes for deployment
3. Your app will be live at: `https://your-service-name.onrender.com`

---

### Method 2: Manual Deploy via Dashboard

If auto-deploy is disabled:

1. Go to your service in Render dashboard
2. Click **Manual Deploy** dropdown
3. Select **Deploy latest commit**
4. Wait for deployment to complete

---

## 🧪 Verify Deployment

### Test Checklist:
1. ✅ Open your app URL
2. ✅ Search for a city without checking "Use Google Places" (tests OSM)
3. ✅ Check the "Use Google Places" checkbox
4. ✅ Search for "Tokyo" (tests Google Places)
5. ✅ Verify you see:
   - ⭐ Star ratings
   - Review counts
   - Price levels ($, $$, $$$, $$$$)
   - Phone numbers
   - Clickable Google Maps links

---

## 🔧 Troubleshooting

### Issue: 503 Service Unavailable
**Solution**: Wait 2-3 minutes. Render takes time to build and start the app.

### Issue: No Google Places data showing
**Solutions**:
1. Verify `GOOGLE_PLACES_API_KEY` is set in Environment variables
2. Check that Google Places API is enabled in Google Cloud Console
3. Verify API key restrictions aren't blocking requests
4. Check Render logs for errors: Dashboard → Logs

### Issue: Port binding error
**Solution**: Ensure `app.py` uses:
```python
port = int(os.getenv('PORT', 5010))
app.run(host='0.0.0.0', port=port, debug=False)
```

### Issue: Build fails
**Solutions**:
1. Verify `requirements.txt` exists in `city-guides/` directory
2. Check that all packages are spelled correctly
3. View build logs for specific error messages

---

## 📊 Monitoring

### View Logs:
1. Go to your service in Render dashboard
2. Click **Logs** tab
3. See real-time application logs

### Restart Service:
1. Go to your service settings
2. Click **Manual Deploy** → **Clear build cache & deploy**

---

## 🚀 Production Checklist

Before going live, verify:
- [ ] `GOOGLE_PLACES_API_KEY` is set
- [ ] API key has correct restrictions
- [ ] `FLASK_ENV=production` is set
- [ ] Auto-deploy is configured (if desired)
- [ ] Health checks are passing
- [ ] All tests pass: `python test_integration.py`
- [ ] App loads in browser
- [ ] Google Places checkbox works
- [ ] Search returns results with ratings

---

## 💰 Cost Estimate

**Render.com Free Tier:**
- ✅ 750 hours/month free
- ✅ Automatic SSL
- ✅ Custom domains
- ✅ More than enough for testing and small-scale use

**Google Places API Free Tier:**
- ✅ $200 credit/month
- ✅ ~28,000 requests/month free
- ✅ Only pay if you exceed free tier

**Total Monthly Cost**: $0 for most users! 🎉

---

## 🔄 Updates & Redeployment

### Auto-Deploy:
- Push to `main` branch
- Render automatically builds and deploys
- Wait 2-5 minutes

### Manual Deploy:
- Dashboard → Manual Deploy → Deploy latest commit
- Wait for build to complete

---

**Need help?** Check `TROUBLESHOOTING.md` or open an issue on GitHub!
