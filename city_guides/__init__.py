# Compatibility shim so tests can import modules as `city_guides.*`
# The real code lives in the `city-guides` directory (hyphen), which isn't a
# valid Python package name. This module extends the package path to include
# that directory so `import city_guides.overpass_provider` works in tests.
import os
from pathlib import Path

_this_dir = Path(__file__).resolve().parent
_other = (_this_dir.parent / 'city-guides')
if _other.exists():
    __path__.insert(0, str(_other))
else:
    # Fallback to existing layout if that dir missing
    __path__.insert(0, str(_this_dir))
