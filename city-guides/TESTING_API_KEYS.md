# Testing Google Places API Keys

This guide explains how to test your actual Google Places API key to ensure it works correctly with the Travelland application.

## Quick Test Methods

### Method 1: Using the Test Script (Recommended)

The easiest way to test your API key is using the provided test script:

```bash
# Set your API key in the environment
export GOOGLE_PLACES_API_KEY="your_actual_api_key_here"

# Run the test script
python test_google_places.py
```

Expected output if successful:
```
✓ GOOGLE_PLACES_API_KEY is set
✓ Successfully retrieved X restaurants
Sample results with restaurant names, ratings, and addresses
```

### Method 2: Using a .env File (Local Development)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your actual API key:
   ```
   GOOGLE_PLACES_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   ```

3. Run the test script (it will automatically load from .env):
   ```bash
   python test_google_places.py
   ```

### Method 3: Using Render.com Environment Variables

1. Go to your Render.com dashboard
2. Select your service
3. Go to "Environment" tab
4. Add a new environment variable:
   - Key: `GOOGLE_PLACES_API_KEY`
   - Value: Your actual API key
5. Save and redeploy

To test on Render.com:
- Check the deployment logs for any API errors
- Use the application UI and check the "Use Google Places" checkbox
- Search for restaurants in a city (e.g., "New York")

### Method 4: Manual API Testing

Test your key directly with curl:

```bash
# Test Geocoding API
curl "https://maps.googleapis.com/maps/api/geocode/json?address=New+York&key=YOUR_API_KEY_HERE"

# Test Places API
curl "https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=40.7128,-74.0060&radius=5000&type=restaurant&key=YOUR_API_KEY_HERE"
```

## What to Look For

### Successful Response
```json
{
  "status": "OK",
  "results": [...]
}
```

### Common Errors

#### 1. Invalid API Key
```json
{
  "status": "REQUEST_DENIED",
  "error_message": "The provided API key is invalid."
}
```
**Solution**: Double-check your API key in Google Cloud Console

#### 2. API Not Enabled
```json
{
  "status": "REQUEST_DENIED",
  "error_message": "This API project is not authorized to use this API."
}
```
**Solution**: Enable "Places API" and "Geocoding API" in Google Cloud Console

#### 3. Billing Not Enabled
```json
{
  "status": "REQUEST_DENIED",
  "error_message": "You must enable Billing on the Google Cloud Project"
}
```
**Solution**: Enable billing in Google Cloud Console (Note: Google provides $200 free credit monthly)

#### 4. Over Quota
```json
{
  "status": "OVER_QUERY_LIMIT",
  "error_message": "You have exceeded your daily request quota for this API."
}
```
**Solution**: Wait 24 hours or upgrade your quota in Google Cloud Console

#### 5. API Key Restrictions
```json
{
  "status": "REQUEST_DENIED",
  "error_message": "API keys with referer restrictions cannot be used with this API."
}
```
**Solution**: Remove or adjust API key restrictions in Google Cloud Console

## Interactive Testing with the Application

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Open http://127.0.0.1:5010 in your browser

3. In the search interface:
   - Check the "Use Google Places" checkbox
   - Enter a city (e.g., "New York", "London", "Tokyo")
   - Click "Search"

4. Verify the results show:
   - Restaurant names
   - Star ratings (⭐)
   - Review counts
   - Addresses
   - Phone numbers (if available)
   - Websites (if available)

## Testing Different Scenarios

### Test 1: Basic Search
```python
# In Python console
from places_provider import discover_restaurants_places
results = discover_restaurants_places("New York", limit=5)
print(f"Found {len(results)} restaurants")
for r in results:
    print(f"- {r['name']}: {r['rating']}/5 stars")
```

### Test 2: Cuisine Filter
```python
from places_provider import discover_restaurants_places
results = discover_restaurants_places("Paris", cuisine="italian", limit=5)
print(f"Found {len(results)} Italian restaurants in Paris")
```

### Test 3: Budget Filter
```python
from places_provider import discover_restaurants_places
results = discover_restaurants_places("Tokyo", limit=20)
cheap_restaurants = [r for r in results if r['budget'] == 'cheap']
print(f"Found {len(cheap_restaurants)} cheap restaurants")
```

### Test 4: Custom Radius
```python
from places_provider import discover_restaurants_places
results = discover_restaurants_places("London", limit=10, radius=2000)  # 2km radius
print(f"Found {len(results)} restaurants within 2km")
```

## API Key Setup Checklist

- [ ] Created Google Cloud Project
- [ ] Enabled Places API
- [ ] Enabled Geocoding API
- [ ] Created API Key
- [ ] (Optional) Set up billing for higher quotas
- [ ] (Optional) Restricted API key to specific APIs
- [ ] Added API key to .env file or Render.com environment
- [ ] Tested with test_google_places.py
- [ ] Tested in the application UI

## Monitoring API Usage

To monitor your API usage and avoid unexpected charges:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Go to "APIs & Services" > "Dashboard"
4. Click on "Places API" or "Geocoding API"
5. View usage charts and quotas

## Cost Estimation

Google Places API pricing (as of 2024):
- Nearby Search: $32 per 1,000 requests
- Place Details: $17 per 1,000 requests
- Geocoding: $5 per 1,000 requests

**Note**: Google provides $200 in free monthly credit, which covers:
- ~6,250 Nearby Search requests
- ~11,764 Place Details requests
- ~40,000 Geocoding requests

For typical usage (10-20 requests per user), the free tier is usually sufficient.

## Troubleshooting

If tests fail, check:
1. API key is correctly set (no extra spaces or quotes)
2. APIs are enabled in Google Cloud Console
3. Billing is enabled (required even for free tier)
4. No API restrictions are blocking requests
5. You haven't exceeded quota limits
6. Internet connection is working

For more help, check the application logs or Google Cloud Console error messages.
