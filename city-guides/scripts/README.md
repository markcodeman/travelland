PowerShell helper scripts for local checks

run_places_check.ps1
- Runs the one-off Places check (scripts/check_places.py) using the repo venv python.
- Usage: Open PowerShell in the `city-guides` folder and run:
  .\scripts\run_places_check.ps1

run_smoke.ps1
- Starts `app.py` in background, runs the Playwright smoke test (`tests/playwright_local_smoke.py`), then stops the server.
- Usage: Open PowerShell in the `city-guides` folder and run:
  .\scripts\run_smoke.ps1

Notes
- Ensure `.env` is available and contains `GOOGLE_PLACES_API_KEY` for real Places checks.
- These scripts are minimal conveniences for local development and are safe to run (they don't push to any external services).
