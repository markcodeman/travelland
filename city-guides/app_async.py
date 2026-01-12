import asyncio
import os
from quart import Quart, render_template, request, jsonify
import aiohttp
import redis.asyncio as aioredis

app = Quart(__name__, static_folder="static", template_folder="templates")

# Global clients set up in startup
aiohttp_session: aiohttp.ClientSession | None = None
redis_client: aioredis.Redis | None = None


@app.before_serving
async def startup():
    global aiohttp_session, redis_client
    aiohttp_session = aiohttp.ClientSession(headers={"User-Agent": "city-guides-async"})
    try:
        redis_client = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        await redis_client.ping()
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
        async with aiohttp_session.get(url, params=params, timeout=10) as resp:
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
        async with aiohttp_session.get(url, params=coerced_params, timeout=10) as resp:
            resp.raise_for_status()
            data = await resp.json()
            weather = data.get("current_weather", {})
            return jsonify({"lat": lat, "lon": lon, "city": city, "weather": weather})
    except Exception as e:
        return jsonify({"error": "weather_fetch_failed", "details": str(e)}), 500


if __name__ == "__main__":
    # Run using Quart dev server for quick smoke testing
    port = int(os.getenv("PORT") or 5011)
    app.run(host="0.0.0.0", port=port)
