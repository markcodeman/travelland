import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, Any, cast
from quart import Quart, render_template, request, jsonify
import aiohttp
from aiohttp import ClientTimeout
import redis.asyncio as aioredis

# Add repository root to sys.path for city_guides imports
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

app = Quart(__name__, static_folder="static", template_folder="templates")

# New endpoint: Serve Chesapeake neighborhoods from cleaned CSV
@app.route("/neighborhoods_csv", methods=["GET"])
async def neighborhoods_csv():
    import pandas as pd
    csv_path = os.path.join(os.path.dirname(__file__), "../data/ChesapeakeNeighborhoods_cleaned.csv")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return jsonify({"error": f"Failed to load CSV: {e}"}), 500

    # Optional filters
    sector = request.args.get("sector")
    name = request.args.get("name")
    min_area = request.args.get("min_area", type=float)
    max_area = request.args.get("max_area", type=float)

    filtered = df.copy()
    if sector:
        filtered = filtered[filtered["SECTOR"] == sector]
    if name:
        filtered = filtered[filtered["NBRHD_NAME"].str.contains(name, case=False, na=False)]
    if min_area is not None:
        filtered = filtered[filtered["SHAPESTArea"] >= min_area]
    if max_area is not None:
        filtered = filtered[filtered["SHAPESTArea"] <= max_area]

    neighborhoods = filtered.to_dict(orient="records")
    return jsonify({"neighborhoods": neighborhoods})
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, Any, cast
from quart import Quart, render_template, request, jsonify
import aiohttp
from aiohttp import ClientTimeout
import redis.asyncio as aioredis

# Add repository root to sys.path for city_guides imports
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

app = Quart(__name__, static_folder="static", template_folder="templates")

# Global clients set up in startup
aiohttp_session: Optional[aiohttp.ClientSession] = None
redis_client: Optional[aioredis.Redis] = None


def get_http_session() -> aiohttp.ClientSession:
    assert aiohttp_session is not None, "HTTP session not initialized"
    return aiohttp_session


def get_redis_client() -> aioredis.Redis:
    assert redis_client is not None, "Redis client not initialized"
    return redis_client


@app.before_serving
async def startup():
    global aiohttp_session, redis_client
    aiohttp_session = aiohttp.ClientSession(headers={"User-Agent": "city-guides-async"})
    try:
        redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        # redis-py's type stubs may declare ping() as returning bool; cast to Any
        # so the await doesn't raise a static type error in Pylance.
        await cast(Any, redis_client).ping()
        app.logger.info("✅ Redis connected")
    except Exception:
        redis_client = None
        app.logger.warning("Redis not available; running without cache")


@app.after_serving
async def shutdown():
    global aiohttp_session, redis_client
    if aiohttp_session:
        await aiohttp_session.close()
    if redis_client:
        await redis_client.close()


@app.route("/", methods=["GET"])
async def index():
    # render the same index.html from templates for quick smoke test
    return await render_template("index.html")


async def geocode_city_async(city: str):
    """Geocode city using Nominatim via aiohttp."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city, "format": "json", "limit": 1}
    try:
        session = get_http_session()
        timeout = ClientTimeout(total=10)
        async with session.get(url, params=params, timeout=timeout) as resp:
            data = await resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None, None
    return None, None


@app.route("/weather", methods=["POST"])
async def weather():
    payload = await request.get_json(force=True)
    city = (payload.get("city") or "").strip()
    lat = payload.get("lat")
    lon = payload.get("lon")
    if not (lat and lon):
        if not city:
            return jsonify({"error": "city or lat/lon required"}), 400
        lat, lon = await geocode_city_async(city)
        if not (lat and lon):
            return jsonify({"error": "geocode_failed"}), 400

    # Query Open-Meteo async
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "temperature_unit": "celsius",
            "windspeed_unit": "kmh",
            "precipitation_unit": "mm",
            "timezone": "auto",
        }
        # coerce boolean params to lowercase strings (some APIs disallow raw booleans)
        coerced_params = {}
        for k, v in params.items():
            if isinstance(v, bool):
                coerced_params[k] = str(v).lower()
            else:
                coerced_params[k] = v
        session = get_http_session()
        timeout = ClientTimeout(total=10)
        async with session.get(url, params=coerced_params, timeout=timeout) as resp:
            resp.raise_for_status()
            data = await resp.json()
            weather = data.get("current_weather", {})
            return jsonify({"lat": lat, "lon": lon, "city": city, "weather": weather})
    except Exception as e:
        return jsonify({"error": "weather_fetch_failed", "details": str(e)}), 500


@app.route("/neighborhoods", methods=["GET"])
async def neighborhoods():
    # Import the provider package; editors may not resolve this path in-workspace,
    # so silence missing-import warnings from Pylance where necessary.
    try:
        import city_guides.multi_provider as multi_provider  # type: ignore[reportMissingImports]
    except Exception:  # pragma: no cover - runtime fallback
        import importlib
        multi_provider = importlib.import_module("city_guides.multi_provider")
    
    city = request.args.get("city", type=str)
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    lang = request.args.get("lang", default="en", type=str)
    # Prefer city, but allow lat/lon fallback
    try:
        # Use async_get_neighborhoods from multi_provider
        neighborhoods = await multi_provider.async_get_neighborhoods(city=city, lat=lat, lon=lon, lang=lang, session=get_http_session())
        return jsonify({"neighborhoods": neighborhoods})
    except Exception as e:
        app.logger.warning(f"Neighborhoods fetch failed: {e}")
        return jsonify({"neighborhoods": [], "error": str(e)}), 500


@app.route("/search", methods=["POST"])
async def search():
    payload = await request.get_json(silent=True) or {}
    # Proxy to the existing synchronous _search_impl in the main app module to reuse logic
    try:
        try:
            import city_guides.app as sync_app_module  # type: ignore[reportMissingImports]
        except Exception:  # pragma: no cover - runtime fallback
            import importlib
            sync_app_module = importlib.import_module("city_guides.app")

        # ensure sync app module has a usable aiohttp session if it expects one
        try:
            setattr(sync_app_module, "aiohttp_session", get_http_session())
        except Exception:
            pass

        def _search_sync(p):
            return sync_app_module._search_impl(p)

        result = await asyncio.to_thread(_search_sync, payload)
        return jsonify(result)
    except Exception as e:
        app.logger.exception("Search proxy failed")
        return jsonify({"error": "search_failed", "details": str(e)}), 500



# New endpoint: Serve Chesapeake neighborhoods from cleaned CSV
@app.route("/neighborhoods_csv", methods=["GET"])
async def neighborhoods_csv():
    import pandas as pd
    csv_path = os.path.join(os.path.dirname(__file__), "../data/ChesapeakeNeighborhoods_cleaned.csv")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return jsonify({"error": f"Failed to load CSV: {e}"}), 500

    # Optional filters
    sector = request.args.get("sector")
    name = request.args.get("name")
    min_area = request.args.get("min_area", type=float)
    max_area = request.args.get("max_area", type=float)

    filtered = df.copy()
    if sector:
        filtered = filtered[filtered["SECTOR"] == sector]
    if name:
        filtered = filtered[filtered["NBRHD_NAME"].str.contains(name, case=False, na=False)]
    if min_area is not None:
        filtered = filtered[filtered["SHAPESTArea"] >= min_area]
    if max_area is not None:
        filtered = filtered[filtered["SHAPESTArea"] <= max_area]

    # Convert to records for JSON response
    neighborhoods = filtered.to_dict(orient="records")
    return jsonify({"neighborhoods": neighborhoods})

if __name__ == "__main__":
    # Run using Quart dev server for quick smoke testing
    port = int(os.getenv("PORT") or 5011)
    app.run(host="0.0.0.0", port=port)
