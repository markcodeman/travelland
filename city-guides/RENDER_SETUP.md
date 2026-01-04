# Render.com Setup Guide

## 🚀 Complete Render.com Configuration

### Prerequisites
- GitHub account
- Render.com account (sign up at https://render.com)
- Google Places API key

---

## Part 1: First-Time Setup

### 1. Connect GitHub to Render

1. Go to https://dashboard.render.com
2. Click **New +** → **Web Service**
3. Click **Connect GitHub** (if not already connected)
4. Authorize Render to access your repositories
5. Select **Only select repositories** → Choose `travelland`
6. Click **Install**

### 2. Create Web Service

**Repository Configuration:**
- **Repository**: `markcodeman/travelland`
- **Branch**: `main` (or your deployment branch)

**Service Configuration:**
- **Name**: `travelland-city-guides` (choose any name)
- **Region**: Select closest to your users (e.g., Oregon, Frankfurt)
- **Root Directory**: `city-guides` ⚠️ **IMPORTANT!**
- **Runtime**: `Python 3`

**Build Settings:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python app.py`

**Instance Type:**
- **Free** (750 hours/month - perfect for testing!)
- Upgrade to **Starter** ($7/month) for always-on service

---

## Part 2: Environment Variables

Click the **Environment** tab and add these variables:

### Required:
```
GOOGLE_PLACES_API_KEY=AIzaSyBxxxxxxxxxxxxxxxxxx
FLASK_ENV=production
```

### Optional (for AI features):
```
GROQ_API_KEY=your_groq_key
OPENTRIPMAP_KEY=your_opentripmap_key
```

**⚠️ Important Notes:**
- Click **Add** after each variable
- Don't use quotes around values
- Click **Save Changes** at the bottom

---

## Part 3: Advanced Settings (Optional)

### Auto-Deploy:
- ✅ **Enabled by default** - Auto-deploys on git push
- Disable if you want manual control

### Health Check:
- **Path**: `/` (default)
- Render will ping this URL to verify app is running

### Custom Domain:
1. Click **Settings** → **Custom Domain**
2. Add your domain (e.g., `guides.yourdomain.com`)
3. Update DNS records as shown

---

## Part 4: Deploy!

### Initial Deployment:
1. Review all settings
2. Click **Create Web Service** button
3. Wait 2-5 minutes for build
4. Your app will be live at: `https://your-service-name.onrender.com`

### Subsequent Deploys:
- **Auto**: Push to main branch → Auto-deploys
- **Manual**: Dashboard → **Manual Deploy** → **Deploy latest commit**

---

## 🔍 Monitoring & Debugging

### View Logs:
1. Go to your service in dashboard
2. Click **Logs** tab
3. See real-time output from your app

**Common log patterns:**
```
Running on http://0.0.0.0:10000  ← App started successfully
Error fetching: ...              ← API errors (check keys)
127.0.0.1 - - [timestamp]       ← HTTP requests
```

### Check Service Status:
- **Dashboard** → Your service
- Look for green **Live** indicator
- Check **Events** tab for deployment history

### Restart Service:
- **Manual Deploy** → **Clear build cache & deploy**
- Useful if service is stuck or not responding

---

## 🐛 Troubleshooting

### Build Fails:
**Check:**
1. `requirements.txt` exists in `city-guides/` directory
2. Root Directory is set to `city-guides`
3. Build logs show the actual error
4. All package names are spelled correctly

**Common fixes:**
```bash
# Locally test build
cd city-guides
pip install -r requirements.txt
```

### App Won't Start:
**Check:**
1. Start Command is `python app.py`
2. PORT environment variable is used in app.py:
   ```python
   port = int(os.getenv('PORT', 5010))
   app.run(host='0.0.0.0', port=port)
   ```
3. Logs don't show Python errors

### 503 Service Unavailable:
**Solutions:**
1. Wait 2-3 minutes (app is starting)
2. Check logs for errors
3. Restart service
4. Verify health check endpoint works

### Google Places Not Working:
**Check:**
1. `GOOGLE_PLACES_API_KEY` is set in Environment
2. API key is valid (test locally first)
3. Places API is enabled in Google Cloud
4. Logs don't show API errors

---

## 💰 Pricing & Limits

### Free Tier:
- ✅ 750 hours/month (enough for one always-on service)
- ✅ Sleeps after 15 min of inactivity
- ✅ 50ms cold start
- ✅ Custom domains
- ✅ Automatic SSL

### Starter ($7/month):
- Always on
- No cold starts
- More CPU/memory
- Email support

### Professional ($25/month):
- Even more resources
- Priority support
- Faster builds

**Recommendation**: Start with Free tier, upgrade if needed

---

## 🔒 Security Best Practices

### API Keys:
- ✅ Store in Environment variables (not code)
- ✅ Use API key restrictions in Google Cloud
- ✅ Never commit keys to GitHub
- ✅ Rotate keys periodically

### App Security:
- ✅ Use `debug=False` in production
- ✅ Keep dependencies updated
- ✅ Monitor error logs
- ✅ Set up budget alerts

---

## 📊 Performance Tips

### Optimize Response Time:
1. Enable caching for API responses
2. Use CDN for static assets
3. Implement database indexing (if using DB)
4. Reduce API calls where possible

### Monitor Performance:
- Check **Metrics** tab in Render
- View response times
- Track memory/CPU usage
- Set up alerts for anomalies

---

## ✅ Post-Deployment Checklist

After deploying, verify:
- [ ] App loads at Render URL
- [ ] OSM search works (default, no checkbox)
- [ ] Google Places checkbox appears
- [ ] Google Places search returns results with ratings
- [ ] Price levels display correctly
- [ ] Google Maps links are clickable
- [ ] Phone numbers show up (Google Places)
- [ ] No errors in logs
- [ ] Response times are acceptable (<2s)

---

## 🔄 Maintenance

### Weekly:
- Check service health
- Review error logs
- Monitor API usage

### Monthly:
- Review API costs
- Update dependencies if needed
- Check for security updates

### As Needed:
- Restart service if issues occur
- Update environment variables
- Redeploy after code changes

---

**Need help?** Check other documentation files or open an issue!
