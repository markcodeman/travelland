"""Fetch lightweight live transport + quick-guide data for London using free services.

Outputs a JSON file at `data/transport_london.json` (relative to repo root).

Sources used when API keys are NOT present:
- Nominatim (geocoding)
- Overpass API (OSM POIs/stops)
- Wikivoyage (guide summary)

If TfL or OpenTripMap keys are provided via environment, those will be used
for richer data.
"""

from pathlib import Path
import os
import time
import json
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT.parent / "data" / "transport_london.json"

HEADERS = {"User-Agent": "TravelLand/1.0 (fetcher)", "Accept-Language": "en"}


def geocode_city(city_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city_name, "format": "json", "limit": 1, "accept-language": "en"}
    r = requests.get(url, params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    items = r.json()
    if not items:
        raise RuntimeError("geocode failed for %s" % city_name)
    item = items[0]
    return float(item["lat"]), float(item["lon"])


def fetch_wikivoyage_summary(city_title="London"):
    url = "https://en.wikivoyage.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "titles": city_title,
        "format": "json",
        "redirects": 1,
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    pages = data.get("query", {}).get("pages", {})
    for p in pages.values():
        return p.get("extract", "")
    return ""


def fetch_overpass_transit(lat, lon, radius=1500):
    # Find nearby public_transport stops (bus_stop, stop_position, station)
    q = f"[out:json][timeout:25];(node(around:{radius},{lat},{lon})[public_transport];node(around:{radius},{lat},{lon})[highway=bus_stop];node(around:{radius},{lat},{lon})[railway=station];);out center;"
    url = "https://overpass-api.de/api/interpreter"
    r = requests.post(
        url,
        data=q.encode("utf-8"),
        headers={**HEADERS, "Content-Type": "text/plain"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    stops = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        stops.append(
            {
                "id": el.get("id"),
                "type": el.get("type"),
                "lat": el.get("lat") or el.get("center", {}).get("lat"),
                "lon": el.get("lon") or el.get("center", {}).get("lon"),
                "name": tags.get("name") or tags.get("ref") or "",
                "tags": tags,
            }
        )
    return stops


def fetch_opentripmap_pois(lat, lon, radius=1000, apikey=None, limit=20):
    if not apikey:
        return []
    try:
        url = "https://api.opentripmap.com/0.1/en/places/radius"
        params = {
            "radius": radius,
            "lon": lon,
            "lat": lat,
            "apikey": apikey,
            "limit": limit,
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        res = r.json()
        pois = []
        for it in res.get("features", []):
            props = it.get("properties", {})
            geom = it.get("geometry", {})
            coords = geom.get("coordinates", [None, None])
            pois.append(
                {
                    "id": props.get("xid"),
                    "name": props.get("name"),
                    "kinds": props.get("kinds"),
                    "lat": coords[1],
                    "lon": coords[0],
                }
            )
        return pois
    except Exception:
        return []


def build_payload(city_name="Greater London, England, United Kingdom"):
    lat, lon = geocode_city(city_name)
    summary = fetch_wikivoyage_summary("London")
    stops = fetch_overpass_transit(lat, lon, radius=2500)
    otm_key = os.environ.get("OPENTRIPMAP_KEY")
    pois = fetch_opentripmap_pois(lat, lon, radius=2000, apikey=otm_key, limit=30)

    payload = {
        "city": city_name,
        "center": {"lat": lat, "lon": lon},
        "wikivoyage_summary": summary,
        "stops": stops,
        "pois": pois,
        "generated_at": int(time.time()),
    }
    return payload


def save_payload(payload, out_path=OUT_PATH):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(out_path)


def main():
    city = os.environ.get("TARGET_CITY", "Greater London, England, United Kingdom")
    print(f"Fetching data for: {city}")
    payload = build_payload(city)
    save_payload(payload)
    print(f"Wrote: {OUT_PATH}")


if __name__ == "__main__":
    main()
