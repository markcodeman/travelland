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

### Option 1: Local Network (Same WiFi)

Both apps can be tested on your iPhone when on the same WiFi:

1. **Ensure same WiFi network**: Your iPhone and computer must be on the same WiFi network
2. **Get your network IP**: Run `python get_network_ip.py` from the root directory
3. **Access from iPhone**: Open Safari and navigate to the displayed URLs
   - City Guides: `http://[YOUR-IP]:5010`
   - Hotel Finder: `http://[YOUR-IP]:5000`

### Option 2: Deploy Online (Access Anywhere)

Deploy to a free hosting service for access from anywhere:

- **Render.com** (Recommended): See [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md) for step-by-step instructions
- **Railway.app**: Connect GitHub repo and auto-deploy
- **Instant Testing**: Use `npx localtunnel --port 5010` to create public URL

See [HOSTING_OPTIONS.md](HOSTING_OPTIONS.md) for all deployment options.

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