from dotenv import load_dotenv, find_dotenv
import os
import sys

path = find_dotenv()
print('found dotenv at:', path)
# Try both dotenv and manual parse (fallback to ensure env present)
if path:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()
            print('dotenv preview (len):', len(data))
            # manual parse
            for line in data.splitlines():
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == 'GOOGLE_PLACES_API_KEY' and v:
                        os.environ['GOOGLE_PLACES_API_KEY'] = v
    except Exception as e:
        print('could not read dotenv:', e)

load_dotenv(path)
print('Note: Google Places checks are disabled by project policy. Use `python scripts/seed_osm.py` to seed OSM cache for offline testing. Exiting.')
sys.exit(0)

