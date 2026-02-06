# Deployment Guide - Render.com

## 🚀 Quick Deploy (Current Setup)

### Render Dashboard Settings

**Service Configuration:**
- **Root Directory**: `./` (repo root)
- **Build Command**:
  ```bash
  pip install --no-cache-dir -r requirements.txt && mkdir -p city_guides/static && mkdir -p ../city_guides/static && cd frontend && npm ci && npm run build && cp -R dist/. ../city_guides/static/ && cp public/marcos.png ../city_guides/static/ || true
  ```
- **Start Command**: `bash start_server.sh`
- **Environment**: `Python 3`
- **Region**: `Oregon` (or closest to users)

### Files Required (all in repo root):
- ✅ `requirements.txt` - Python dependencies
- ✅ `render.yaml` - Render configuration
- ✅ `start_server.sh` - Server startup script
- ✅ `frontend/` - Vite React frontend
- ✅ `city_guides/` - Flask/Quart backend

---

## 📋 Step-by-Step Deployment

### Step 1: Connect Repository
1. Go to [Render.com Dashboard](https://dashboard.render.com/)
2. Click **New +** → **Web Service**
3. Connect GitHub → Select `travelland` repository

### Step 2: Configure Service
Use settings from **Quick Deploy** section above

### Step 3: Environment Variables
Add these in Dashboard → Environment:
```
GROQ_API_KEY=your_groq_key
OPENTRIPMAP_KEY=your_opentripmap_key
```

### Step 4: Deploy
Click **Create Web Service** → wait 2-5 minutes

---

## 🔧 Files Explained

### render.yaml
Render Blueprint configuration with all settings defined. Render should auto-detect this file.

### start_server.sh
Activates Render's venv and starts Hypercorn server:
```bash
#!/bin/bash
source /opt/render/project/src/.venv/bin/activate
cd /opt/render/project/src
export PYTHONPATH=/opt/render/project/src:$PYTHONPATH
hypercorn city_guides.src.app:app --bind 0.0.0.0:$PORT
```

### requirements.txt
Contains all Python dependencies (Flask, Quart, Hypercorn, etc.)

---

## 🧪 Verify Deployment

1. Open your app URL
2. Search for a city
3. Test local gems toggle
4. Chat with Marco 🧭

---

## 🔄 Redeployment

### Auto-Deploy
Push to `main` branch → Render auto-deploys

### Manual Deploy
Dashboard → Manual Deploy → Deploy latest commit

---

## 🐛 Troubleshooting

### "No module named hypercorn"
- ✅ Verify `requirements.txt` has `hypercorn>=0.14.0`
- ✅ Build command installs: `pip install -r requirements.txt`
- ✅ Start script activates venv: `source .venv/bin/activate`

### Build fails
- Check Dashboard → Logs for errors
- Verify all files are committed: `git status`

### Port binding error
- Start script uses `$PORT` from Render environment

---

## 📁 Project Structure

```
travelland/
├── requirements.txt          # Python deps (ROOT)
├── render.yaml               # Render config (ROOT)
├── start_server.sh           # Startup script (ROOT)
├── frontend/                 # Vite React app
│   ├── package.json
│   └── src/
├── city_guides/              # Flask/Quart backend
│   ├── requirements.txt       # Backup deps
│   ├── src/
│   │   └── app.py            # Main app
│   └── static/               # Built frontend files
└── tests/
```

---

**🎉 Deployment complete!**
