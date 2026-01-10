#!/usr/bin/env python3
"""
teleport_snapshot.py

Cron-friendly script to prefetch Teleport city price data and warm the local cache used by
`get_cost_estimates` in `city-guides/app.py`.

Usage:
  python teleport_snapshot.py Shanghai London "New York"
  python teleport_snapshot.py --file cities.txt

Cron example (run daily at 03:30):
30 3 * * * /usr/bin/python3 /path/to/city-guides/scripts/teleport_snapshot.py Shanghai London Havana >> /var/log/teleport_snapshot.log 2>&1

This script imports `get_cost_estimates` from the app to ensure caching is written the same way.
"""
import argparse
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def get_cost_estimates_local(city, ttl_seconds=604800):
    """Standalone copy of the Teleport-fetch+cache+fallback logic used by the app.
    This avoids importing Flask/app dependencies when running as a cron job.
    """
    if not city:
        return []
    try:
        cache_dir = ROOT / "city-guides" / ".cache" / "teleport_prices"
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = re.sub(r"[^a-z0-9]+", "_", city.strip().lower())
        cache_file = cache_dir / f"{key}.json"
        # return cached if fresh
        if cache_file.exists():
            try:
                raw = json.loads(cache_file.read_text())
                if raw.get("ts") and time.time() - raw["ts"] < ttl_seconds:
                    return raw.get("data", [])
            except Exception:
                pass

        base = "https://api.teleport.org"
        try:
            s = requests.get(
                f"{base}/api/cities/",
                params={"search": city, "limit": 5},
                timeout=6,
                headers={"User-Agent": "city-guides-snapshot"},
            )
            s.raise_for_status()
            j = s.json()
            results = j.get("_embedded", {}).get("city:search-results", [])
            city_item_href = None
            for r in results:
                href = r.get("_links", {}).get("city:item", {}).get("href")
                if href:
                    city_item_href = href
                    break
            if not city_item_href:
                raise RuntimeError("no city item from teleport")

            ci = requests.get(
                city_item_href,
                timeout=6,
                headers={"User-Agent": "city-guides-snapshot"},
            )
            ci.raise_for_status()
            ci_j = ci.json()
            urban_href = ci_j.get("_links", {}).get("city:urban_area", {}).get("href")
            if not urban_href:
                raise RuntimeError("no urban area")

            prices_href = urban_href.rstrip("/") + "/prices/"
            p = requests.get(
                prices_href, timeout=6, headers={"User-Agent": "city-guides-snapshot"}
            )
            p.raise_for_status()
            p_j = p.json()

            items = []
            for cat in p_j.get("categories", []):
                for d in cat.get("data", []):
                    label = d.get("label") or d.get("id")
                    val = None
                    for k in (
                        "usd_value",
                        "currency_dollar_adjusted",
                        "price",
                        "amount",
                        "value",
                    ):
                        if k in d and isinstance(d[k], (int, float)):
                            val = float(d[k])
                            break
                    if val is None:
                        for kk in d.keys():
                            vvv = d.get(kk)
                            if isinstance(vvv, (int, float)):
                                val = float(vvv)
                                break
                    if label and val is not None:
                        items.append({"label": label, "value": round(val, 2)})

            keywords = ["coffee", "beer", "meal", "taxi", "hotel", "apartment", "rent"]
            selected = []
            lower_seen = set()
            for k in keywords:
                for it in items:
                    if (
                        k in it["label"].lower()
                        and it["label"].lower() not in lower_seen
                    ):
                        selected.append(it)
                        lower_seen.add(it["label"].lower())
                        break
            if not selected:
                selected = items[:8]

            try:
                cache_file.write_text(json.dumps({"ts": time.time(), "data": selected}))
            except Exception:
                pass
            return selected
        except Exception as e:
            print(f"Teleport fetch failed for {city}: {e}")

        # fallback map
        try:
            # best-effort country detection using a lightweight Nominatim call
            url = "https://nominatim.openstreetmap.org/search"
            params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
            headers = {"User-Agent": "city-guides-snapshot", "Accept-Language": "en"}
            r = requests.get(url, params=params, headers=headers, timeout=6)
            country = ""
            try:
                r.raise_for_status()
                data = r.json()
                if data:
                    addr = data[0].get("address", {})
                    country = addr.get("country", "") or addr.get("country_code", "")
            except Exception:
                country = ""
        except Exception:
            country = ""

        fb = {
            "china": [
                {"label": "Coffee (cafe)", "value": 20.0},
                {"label": "Local beer (0.5L)", "value": 12.0},
                {"label": "Meal (mid-range)", "value": 70.0},
                {"label": "Taxi start (local)", "value": 10.0},
                {"label": "Hotel (1 night, mid)", "value": 350.0},
            ],
            "russia": [
                {"label": "Coffee (cafe)", "value": 200.0},
                {"label": "Local beer (0.5L)", "value": 150.0},
                {"label": "Meal (mid-range)", "value": 700.0},
                {"label": "Taxi start (local)", "value": 100.0},
                {"label": "Hotel (1 night, mid)", "value": 4000.0},
            ],
            "cuba": [
                {"label": "Coffee (cafe)", "value": 50.0},
                {"label": "Local beer (0.5L)", "value": 60.0},
                {"label": "Meal (mid-range)", "value": 200.0},
                {"label": "Taxi (short)", "value": 80.0},
                {"label": "Hotel (1 night, mid)", "value": 2500.0},
            ],
            "portugal": [
                {"label": "Coffee (cafe)", "value": 1.6},
                {"label": "Local beer (0.5L)", "value": 2.0},
                {"label": "Meal (mid-range)", "value": 12.0},
                {"label": "Taxi start (local)", "value": 3.0},
                {"label": "Hotel (1 night, mid)", "value": 80.0},
            ],
            "united states": [
                {"label": "Coffee (cafe)", "value": 3.5},
                {"label": "Local beer (0.5L)", "value": 5.0},
                {"label": "Meal (mid-range)", "value": 20.0},
                {"label": "Taxi start (local)", "value": 3.0},
                {"label": "Hotel (1 night, mid)", "value": 140.0},
            ],
            "united kingdom": [
                {"label": "Coffee (cafe)", "value": 2.8},
                {"label": "Local beer (0.5L)", "value": 4.0},
                {"label": "Meal (mid-range)", "value": 15.0},
                {"label": "Taxi start (local)", "value": 3.5},
                {"label": "Hotel (1 night, mid)", "value": 120.0},
            ],
            "thailand": [
                {"label": "Coffee (cafe)", "value": 50.0},
                {"label": "Local beer (0.5L)", "value": 60.0},
                {"label": "Meal (mid-range)", "value": 250.0},
                {"label": "Taxi start (local)", "value": 35.0},
                {"label": "Hotel (1 night, mid)", "value": 1200.0},
            ],
        }
        lookup = (country or "").strip().lower()
        for k in fb.keys():
            if k in lookup:
                try:
                    cache_file.write_text(
                        json.dumps({"ts": time.time(), "data": fb[k]})
                    )
                except Exception:
                    pass
                return fb[k]
        return []
    except Exception:
        return []


def load_cities_from_file(path):
    p = Path(path)
    if not p.exists():
        return []
    with p.open() as fh:
        return [
            line.strip() for line in fh if line.strip() and not line.startswith("#")
        ]


def main():
    parser = argparse.ArgumentParser(
        description="Warm Teleport price cache for a set of cities"
    )
    parser.add_argument("cities", nargs="*", help="City names to fetch")
    parser.add_argument("--file", "-f", help="File with one city per line")
    parser.add_argument(
        "--delay", type=float, default=1.5, help="Seconds to wait between requests"
    )
    args = parser.parse_args()

    cities = list(args.cities or [])
    if args.file:
        cities += load_cities_from_file(args.file)

    # sensible defaults if nothing provided
    if not cities:
        cities = [
            "London",
            "Paris",
            "New York",
            "Shanghai",
            "Tokyo",
            "Havana",
            "Moscow",
            "Lisbon",
        ]

    print(f"Warming Teleport cache for {len(cities)} cities")
    for i, c in enumerate(cities, 1):
        try:
            print(f"[{i}/{len(cities)}] Fetching: {c}")
            res = get_cost_estimates_local(c)
            if res:
                print(f"  got {len(res)} items")
            else:
                print("  no items (fallback or empty)")
        except Exception as e:
            print(f"  error fetching {c}: {e}")
        if i != len(cities):
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
