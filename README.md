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

### 🎯 If You're ON iPhone Right Now

**You can't run terminal commands on iPhone.** Instead:

1. **Deploy to free hosting** (no terminal needed!)
   - Open **Render.com** in Safari and deploy via GitHub
   - Or use **Railway.app** for one-click deployment
   - See **[IPHONE_TESTING_GUIDE.md](IPHONE_TESTING_GUIDE.md)** for step-by-step browser-only instructions

2. **Get permanent URLs** to test:
   - `https://your-app.onrender.com` (works immediately on iPhone)
   - Full guide: [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md)

### 💻 If You Have a Computer

#### Option 1: Instant Testing (30 seconds) ⚡
**Requires:** Mac/Windows/Linux computer with terminal

Get a public URL immediately with localtunnel:
```bash
cd city-guides
python app.py &
npx localtunnel --port 5010
# Opens URL like: https://random-word-123.loca.lt
# Open this URL on your iPhone Safari!
```

#### Option 2: Local Network (Same WiFi)
**Requires:** Computer and iPhone on same WiFi

Both apps can be tested on your iPhone when on the same WiFi:

1. **Ensure same WiFi network**: Your iPhone and computer must be on the same WiFi network
2. **Get your network IP**: Run `python get_network_ip.py` from the root directory
3. **Access from iPhone**: Open Safari and navigate to the displayed URLs
   - City Guides: `http://[YOUR-IP]:5010`
   - Hotel Finder: `http://[YOUR-IP]:5000`

#### Option 3: Deploy for Free (Access Anywhere) 🌍
**Requires:** Web browser only (works from iPhone!)

Deploy to a free hosting service for permanent access:

- **Render.com** (Recommended): Free forever, browser-based deployment
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