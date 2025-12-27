# Free Hosting Options for Flask Apps - 2025

## ✅ Best Free Options (Ranked)

### 1. **Render.com** ⭐ RECOMMENDED
- **Free Tier**: Yes, forever
- **Setup**: 5 minutes
- **Limits**: 
  - 750 hours/month (enough for 1 app running 24/7)
  - Sleeps after 15 min inactivity (wakes in ~30 sec)
  - 512 MB RAM
- **Pros**: 
  - ✅ Automatic HTTPS
  - ✅ Deploy from GitHub (auto-updates)
  - ✅ Custom domains supported
  - ✅ Very reliable
- **Cons**: 
  - ⚠️ Cold start delay (30-60 seconds)
- **Best for**: Production-quality free hosting
- **Deploy**: See [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md)

### 2. **Railway.app** ⭐⭐
- **Free Tier**: $5 credit/month (runs ~500 hours)
- **Setup**: 2 minutes (easiest!)
- **Limits**: 
  - $5 free credit/month
  - ~17 days of 24/7 uptime
  - 512 MB RAM
- **Pros**: 
  - ✅ Fastest deployment
  - ✅ Auto-detects Python
  - ✅ No cold starts
  - ✅ Great dashboard
- **Cons**: 
  - ⚠️ Credit expires monthly (not truly unlimited)
- **Best for**: Quick prototypes and demos

### 3. **PythonAnywhere**
- **Free Tier**: Yes, forever
- **Setup**: 10 minutes
- **Limits**: 
  - 1 web app
  - Daily restart required
  - Limited to 100k CPU seconds/day
  - yourapp.pythonanywhere.com domain
- **Pros**: 
  - ✅ Python-specific (no Docker needed)
  - ✅ Web-based console
  - ✅ Good documentation
- **Cons**: 
  - ⚠️ Must restart daily
  - ⚠️ No HTTPS on free tier custom domains
- **Best for**: Learning and simple apps

### 4. **Fly.io**
- **Free Tier**: Yes (limited)
- **Setup**: 10 minutes
- **Limits**: 
  - 3 shared VMs
  - 160 GB bandwidth/month
  - Requires credit card
- **Pros**: 
  - ✅ Global deployment
  - ✅ Fast performance
  - ✅ Docker-based
- **Cons**: 
  - ⚠️ Requires credit card
  - ⚠️ More complex setup
- **Best for**: Global apps needing low latency

### 5. **Vercel** (with Python Serverless)
- **Free Tier**: Yes, unlimited hobby projects
- **Setup**: 15 minutes
- **Limits**: 
  - 10 second function timeout
  - 100 GB bandwidth/month
- **Pros**: 
  - ✅ Extremely fast CDN
  - ✅ Automatic previews for PRs
  - ✅ Great for frontend + API
- **Cons**: 
  - ⚠️ Requires converting Flask to serverless functions
  - ⚠️ Not ideal for traditional Flask apps
- **Best for**: JAMstack apps with API routes

### 6. **Glitch.com**
- **Free Tier**: Yes, forever
- **Setup**: 5 minutes
- **Limits**: 
  - Sleeps after 5 min inactivity
  - 4000 requests/hour
  - 512 MB RAM
- **Pros**: 
  - ✅ Online code editor
  - ✅ Instant deployment
  - ✅ Great for learning
- **Cons**: 
  - ⚠️ Very aggressive sleeping (5 min)
  - ⚠️ Limited resources
- **Best for**: Quick experiments and learning

### 7. **Cyclic.sh**
- **Free Tier**: Yes
- **Setup**: 5 minutes
- **Limits**: 
  - 10,000 requests/month
  - 10 GB bandwidth/month
- **Pros**: 
  - ✅ AWS infrastructure
  - ✅ Fast deployment
- **Cons**: 
  - ⚠️ Better for Node.js (Python less documented)
- **Best for**: Small traffic apps

## ❌ No Longer Free

### Heroku
- **Status**: ❌ Discontinued free tier (Nov 2022)
- **Current**: $7/month minimum
- **Note**: Still excellent if you're willing to pay

## 🚀 Instant Testing (No Deployment)

### **Localtunnel** or **ngrok**
- **Free**: Yes
- **Setup**: 30 seconds
- **Usage**: 
  ```bash
  # Run your app
  python app.py
  
  # In another terminal
  npx localtunnel --port 5010
  # Or
  ngrok http 5010
  ```
- **Pros**: 
  - ✅ Instant public URL
  - ✅ Great for testing
  - ✅ No signup needed (localtunnel)
- **Cons**: 
  - ⚠️ URL changes each time
  - ⚠️ Must keep terminal open
- **Best for**: Quick iPhone testing NOW

## 📊 Comparison Table

| Platform | Free Forever | Setup Time | Cold Starts | Custom Domain | Auto-Deploy |
|----------|-------------|------------|-------------|---------------|-------------|
| **Render.com** | ✅ | 5 min | Yes (30s) | ✅ | ✅ |
| **Railway.app** | ⚠️ ($5/mo credit) | 2 min | No | ✅ | ✅ |
| **PythonAnywhere** | ✅ | 10 min | No | ⚠️ (no HTTPS) | ❌ |
| **Fly.io** | ✅ | 10 min | No | ✅ | ✅ |
| **Vercel** | ✅ | 15 min | No | ✅ | ✅ |
| **Glitch** | ✅ | 5 min | Yes (5 min) | ❌ | ✅ |
| **Localtunnel** | ✅ | 30 sec | No | ❌ | ❌ |

## 🎯 My Recommendation

**For your iPhone testing:**

1. **Immediate testing**: Use `npx localtunnel --port 5010` (30 seconds)
2. **Permanent hosting**: Deploy to **Render.com** (5 minutes, free forever)
3. **Multiple apps**: Use **Railway.app** ($5 credit runs both apps for ~8 days)

## 🔧 Quick Start Command

```bash
# Instant public URL (works on iPhone immediately)
cd city-guides
python app.py &
npx localtunnel --port 5010

# You'll get: https://random-word-123.loca.lt
# Open this URL on your iPhone Safari!
```

For permanent deployment, see [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md).
