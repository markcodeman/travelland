# Quick Deployment Guide

You've already added `GOOGLE_PLACES_API_KEY` to Render.com. Now just deploy the code!

## Option 1: Automatic Deploy (Recommended)

If you have auto-deploy enabled on Render.com:

1. **Merge this PR** to your main branch
2. Render.com will **automatically deploy** the changes
3. Wait 2-5 minutes for deployment to complete
4. Done! ✓

## Option 2: Manual Deploy from Render.com Dashboard

If auto-deploy is not enabled:

1. Go to [Render.com Dashboard](https://dashboard.render.com/)
2. Select your **travelland** service
3. Click the **"Manual Deploy"** button
4. Select **"Deploy latest commit"**
5. Wait for deployment to complete (check the Logs tab)
6. Done! ✓

## Option 3: Deploy Specific Branch

To deploy this PR branch before merging:

1. Go to your Render.com service
2. Go to **Settings** tab
3. Under **"Build & Deploy"**, change the **Branch** to: `copilot/add-google-places-api-key`
4. Save changes - this will trigger a deploy
5. Once tested and working, merge the PR and change branch back to `main`

## Verify Deployment

After deployment completes:

### 1. Check the Logs
- Go to "Logs" tab in Render.com
- Look for: ✓ No errors about missing API key
- The app should start successfully

### 2. Test in the Browser
1. Open your Render.com app URL: `https://your-app.onrender.com`
2. Look for the **"Use Google Places"** checkbox in the search interface
3. Check the checkbox
4. Enter a city name (e.g., "Tokyo" or "Paris")
5. Click Search
6. You should see restaurants with **⭐ ratings** and reviews!

### 3. Quick API Test
```bash
# Replace YOUR_APP_URL with your actual Render.com URL
curl -X POST https://YOUR_APP_URL/search \
  -H "Content-Type: application/json" \
  -d '{"city": "New York", "provider": "google", "limit": 3}'
```

Expected: JSON response with venues that have `rating` and `user_ratings_total` fields.

## Troubleshooting

### If deployment fails:
- Check Render.com logs for error messages
- Make sure `requirements.txt` is being read (it should install Flask, requests, etc.)
- Verify the start command is correct (usually `python app.py` or similar)

### If "Use Google Places" checkbox doesn't appear:
- Clear browser cache and refresh
- Check browser console for JavaScript errors
- Verify the deployment actually completed

### If checkbox appears but no results:
- Check Render.com logs for API errors
- Verify `GOOGLE_PLACES_API_KEY` is set (go to Environment tab)
- Make sure the API key has Places API and Geocoding API enabled in Google Cloud Console

## Current Status

✓ API key already added to Render.com environment variables  
✓ Code changes ready in this PR  
⏳ **Next step: Deploy!** (merge PR or manual deploy)  
⏳ Test in browser with "Use Google Places" checkbox  

## What Happens After Deploy

The application will now support **two data sources**:

1. **OpenStreetMap (Default)** - Free, unchecked
2. **Google Places** - Premium data, when checkbox is checked

Users can toggle between them for each search!

---

**Ready to deploy? Merge this PR or click Manual Deploy on Render.com!** 🚀
