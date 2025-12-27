# Deploy to Render.com for iPhone Testing

## Quick Deploy (5 minutes)

### City Guides App

1. **Go to** https://render.com and sign up with GitHub
2. **Click** "New +" → **"Web Service"** (NOT "Static Site")
   - ✅ **Choose "Web Service"** - for Flask apps with Python backend
   - ❌ Don't choose "Static Site" - that's for HTML/CSS/JS only
3. **Connect** your `markcodeman/travelland` repository
4. **Configure:**
   - Name: `travelland-city-guides`
   - Root Directory: `city-guides`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`
   - Plan: `Free`

5. **Click** "Create Web Service"

**Your app will be live at:** `https://travelland-city-guides.onrender.com`

### Hotel Finder App

Repeat the same steps with:
   - **Choose "Web Service"** (NOT "Static Site")
   - Name: `travelland-hotel-finder`
   - Root Directory: `hotel-finder`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`

**Your app will be live at:** `https://travelland-hotel-finder.onrender.com`

## Access from iPhone

Simply open Safari on your iPhone and navigate to the URLs above. The apps will work exactly as they do locally, with full functionality!

## Notes

- **Free tier** may take 30-60 seconds to "wake up" if inactive
- **HTTPS** is automatic and works great on iPhone
- **No local setup needed** - deploy once, access anywhere
- Apps will auto-update when you push to GitHub

## Alternative: Railway.app

Even faster deployment:

1. Go to https://railway.app
2. "Start a New Project" → "Deploy from GitHub"
3. Select repo → It auto-detects and deploys both apps
4. Each app gets a URL like `https://your-app.up.railway.app`

## For Instant Testing (No Deployment)

Use ngrok/localtunnel to expose local app to internet:

```bash
# Terminal 1: Run app
cd city-guides
python app.py

# Terminal 2: Expose to internet
npx localtunnel --port 5010
```

Opens URL like `https://random-word.loca.lt` - works instantly on iPhone!
