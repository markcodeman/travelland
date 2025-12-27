# travelland

A collection of travel-related web applications for finding hotels and city guides.

## Projects

### 1. Hotel Finder 🏨
Transparent hotel search engine with no hidden fees.
- Location: `hotel-finder/`
- Port: 5000
- [Read more](hotel-finder/README.md)

### 2. City Guides 🗺️
Budget-friendly city venue discovery with real-time data.
- Location: `city-guides/`
- Port: 5010
- [Read more](city-guides/README.md)

## Testing on iPhone 📱

### Option 1: Instant Testing (30 seconds) ⚡
Get a public URL immediately with localtunnel:
```bash
cd city-guides
python app.py &
npx localtunnel --port 5010
# Opens URL like: https://random-word-123.loca.lt
# Open this URL on your iPhone Safari!
```

### Option 2: Local Network (Same WiFi)
Both apps can be tested on your iPhone when on the same WiFi:

1. **Ensure same WiFi network**: Your iPhone and computer must be on the same WiFi network
2. **Get your network IP**: Run `python get_network_ip.py` from the root directory
3. **Access from iPhone**: Open Safari and navigate to the displayed URLs
   - City Guides: `http://[YOUR-IP]:5010`
   - Hotel Finder: `http://[YOUR-IP]:5000`

### Option 3: Deploy for Free (Access Anywhere) 🌍
Deploy to a free hosting service for permanent access:

- **Render.com** (Recommended): Free forever, see [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md)
- **Railway.app**: $5 credit/month, auto-deploys from GitHub
- **PythonAnywhere**: Free tier, Python-specific

**See [FREE_HOSTING.md](FREE_HOSTING.md) for complete comparison of all free options.**

## Quick Start

```bash
# For City Guides
cd city-guides
python app.py

# For Hotel Finder
cd hotel-finder
python app.py

# Get network IP for mobile testing
python get_network_ip.py
```