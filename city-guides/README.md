City Microguides — Budget Picks

Quick prototype: local JSON dataset with searchable city venues by budget.

## Features

- 🍕 Restaurant and venue discovery using:
  - **OpenStreetMap (Overpass API)** - Default, free, open data
  - **Google Places API** - Premium data with ratings, reviews, and more details
- 🤖 AI-powered travel assistant (Marco the Explorer)
- 💱 Currency converter
- 🔍 Semantic search capabilities

## Setup

1. Activate your venv (or use system Python).

   In PowerShell:

   & 'C:\\Users\\markm\\OneDrive\\Desktop\\Mturk\\venv\\Scripts\\Activate.ps1'

2. Install requirements:

   pip install -r requirements.txt

3. Configure environment variables:

   Copy `.env.example` to `.env` and add your API keys:
   
   ```
   GOOGLE_PLACES_API_KEY=your_api_key_here
   GROQ_API_KEY=your_groq_key_here
   ```

   For Render.com deployment, add these as environment variables in your service settings.

4. Run app:

   python app.py

Open http://127.0.0.1:5010

## Google Places API Integration

### Getting an API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Places API** and **Geocoding API**
4. Create credentials (API Key)
5. Add the API key to your `.env` file or Render.com environment variables

### Using Google Places

In the UI, check the **"Use Google Places"** checkbox to use Google Places API instead of OpenStreetMap.

Or programmatically, send `provider: "google"` in your API request:

```javascript
fetch('/search', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    city: 'New York',
    budget: 'cheap',
    provider: 'google'
  })
})
```

### Testing Your API Key

See [TESTING_API_KEYS.md](TESTING_API_KEYS.md) for comprehensive testing guide.

#### Quick Test Options

**Option 1: Interactive Testing (Recommended)**
```bash
python test_api_key_interactive.py
```

This will guide you through:
- Checking if your API key is set
- Testing the Geocoding API
- Testing the Places API
- Running the full integration

**Option 2: Basic Test**
```bash
python test_google_places.py
```

**Option 3: Quick Command Line Test**
```bash
# Test a specific city
python test_api_key_interactive.py "New York"

# Test with cuisine filter
python test_api_key_interactive.py "Paris" "italian"
```

**Option 4: Test in Python Console**
```python
from places_provider import discover_restaurants_places
results = discover_restaurants_places("Tokyo", cuisine="sushi", limit=5)
for r in results:
    print(f"{r['name']}: {r['rating']}/5 stars")
```

For troubleshooting and detailed testing scenarios, see [TESTING_API_KEYS.md](TESTING_API_KEYS.md).

## Data Sources

- **OpenStreetMap**: Free, community-driven geographic data
- **Google Places**: Commercial API with detailed business information, ratings, and reviews
- Data: `data/venues.json` contains curated sample venues (if using local data mode)