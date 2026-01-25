import inspect
import sys
import os

# Ensure tests work when run from repository root by adding project root to sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_overpass_provider_shim_exists_and_reexports():
    # Ensure the top-level shim exists and re-exports the providers implementation
    import city_guides.overpass_provider as shim
    src = inspect.getsource(shim)
    assert 'from city_guides.providers.overpass_provider import *' in src, "Top-level shim should re-export from 'city_guides.providers.overpass_provider'"

    # Ensure canonical implementation exists and provides expected Geoapify helpers
    import city_guides.providers.overpass_provider as impl
    assert hasattr(impl, 'geoapify_geocode_city') or hasattr(impl, 'geoapify_discover_pois'), \
        "Canonical provider implementation should expose geoapify helper functions"
