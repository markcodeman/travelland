# Render.com Deployment - Which Option to Choose?

When deploying on Render.com, you'll see two main options:

## ✅ Choose "Web Service" (For Your Flask Apps)

**What it is:**
- Dynamic web applications with backend code
- Runs Python, Node.js, Go, Ruby, etc.
- Has server-side processing
- Handles API requests

**Use for:**
- ✅ City Guides app (Flask + Python backend)
- ✅ Hotel Finder app (Flask + Python backend)
- ✅ Any app with `app.py` or server code
- ✅ Apps that need to process data, make API calls, run databases

**Configuration needed:**
```
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: python app.py
```

## ❌ Don't Choose "Static Site" (Not for Flask Apps)

**What it is:**
- Static HTML/CSS/JavaScript only
- No server-side code
- Just files served by a CDN
- Like GitHub Pages

**Use for:**
- Static HTML websites
- React/Vue/Angular builds (after building to static files)
- Documentation sites
- Blogs with static site generators (Hugo, Jekyll)

**Why it won't work for your apps:**
- ❌ Can't run Python/Flask
- ❌ Can't execute `app.py`
- ❌ No backend API endpoints
- ❌ No server-side processing

## Quick Answer

**For city-guides and hotel-finder:**
👉 **Choose "Web Service"** - These are Flask apps that need Python backend

## Summary

| Feature | Web Service | Static Site |
|---------|------------|-------------|
| Python/Flask | ✅ Yes | ❌ No |
| Backend APIs | ✅ Yes | ❌ No |
| Server Processing | ✅ Yes | ❌ No |
| HTML/CSS/JS Only | ✅ Yes | ✅ Yes |
| Use for Flask | ✅ YES | ❌ NO |
| Your Apps | ✅ **Use This** | ❌ Don't Use |

## Still Confused?

**Simple rule:** If your app has a `.py` file that needs to run (like `app.py`), choose **"Web Service"**.
