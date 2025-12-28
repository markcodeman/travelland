# Quick Setup Guide for Render.com

This guide helps you quickly set up Google Places API on Render.com.

## Step-by-Step Setup

### 1. Get Your Google Places API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "Travelland App")
3. Click "Enable APIs and Services"
4. Search for and enable:
   - **Places API**
   - **Geocoding API**
5. Go to "Credentials" → "Create Credentials" → "API Key"
6. Copy your API key (starts with `AIza...`)

### 2. Configure Render.com

1. Log in to [Render.com](https://render.com/)
2. Select your Travelland service
3. Go to the **"Environment"** tab
4. Click **"Add Environment Variable"**
5. Add:
   - **Key**: `GOOGLE_PLACES_API_KEY`
   - **Value**: Your API key (paste the key from step 1)
6. Click **"Save Changes"**

### 3. Deploy/Redeploy

- Render will automatically redeploy with the new environment variable
- Wait for deployment to complete (check the "Logs" tab)

### 4. Test Your Deployment

1. Open your Render.com app URL (e.g., `https://your-app.onrender.com`)
2. In the search interface, check the **"Use Google Places"** checkbox
3. Enter a city name (e.g., "New York")
4. Click "Search"
5. You should see restaurants with ratings and reviews!

## Verification

### Check Logs on Render.com

In the "Logs" tab, look for:
- ✓ No errors about "GOOGLE_PLACES_API_KEY not set"
- ✓ Successful API responses (if you see "status: OK")

### Test with curl

```bash
# Replace YOUR_RENDER_URL with your actual Render.com URL
curl -X POST https://YOUR_RENDER_URL/search \
  -H "Content-Type: application/json" \
  -d '{"city": "New York", "provider": "google"}'
```

Expected response should include venues with ratings.

## Common Issues

### Issue: "GOOGLE_PLACES_API_KEY environment variable not set"

**Solution**: 
- Check that you added the environment variable in Render.com
- Make sure there are no typos in the variable name
- Redeploy the service after adding the variable

### Issue: "REQUEST_DENIED" in logs

**Solution**:
- Make sure you enabled both "Places API" and "Geocoding API"
- Check that billing is enabled in Google Cloud Console
- Verify your API key is correct

### Issue: "OVER_QUERY_LIMIT"

**Solution**:
- You've exceeded your free quota ($200/month credit)
- Wait 24 hours or upgrade your quota in Google Cloud Console

### Issue: No results showing

**Solution**:
- Check that "Use Google Places" checkbox is checked
- Try a different city name (use full names like "New York" not "NYC")
- Check browser console for JavaScript errors

## Optional: Restrict API Key (Recommended for Production)

To prevent unauthorized use of your API key:

1. Go to Google Cloud Console → Credentials
2. Click on your API key
3. Under "Application restrictions":
   - Select "HTTP referrers (web sites)"
   - Add your Render.com URL: `https://your-app.onrender.com/*`
4. Under "API restrictions":
   - Select "Restrict key"
   - Choose: "Places API" and "Geocoding API"
5. Save

## Monitoring Usage

Monitor your API usage to avoid unexpected charges:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Go to "APIs & Services" → "Dashboard"
4. View usage charts for Places API and Geocoding API

**Free tier**: $200 credit per month covers thousands of requests for most small apps.

## Support

For issues:
- Check `TESTING_API_KEYS.md` for detailed troubleshooting
- Review Render.com logs for error messages
- Check Google Cloud Console for API errors

## Quick Checklist

- [ ] Created Google Cloud Project
- [ ] Enabled Places API
- [ ] Enabled Geocoding API  
- [ ] Created API Key
- [ ] Added `GOOGLE_PLACES_API_KEY` to Render.com environment variables
- [ ] Redeployed service on Render.com
- [ ] Tested in the web interface with "Use Google Places" checked
- [ ] Verified results show ratings and reviews

Done! Your Google Places integration is now live on Render.com! 🎉
