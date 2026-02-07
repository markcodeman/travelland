# Backwards-compatible shim. Tests and older imports may refer to
# `city_guides.overpass_provider`; re-export the canonical implementation
# from `city_guides.providers.overpass_provider`.
from city_guides.providers.overpass_provider import *  # noqa: F401,F403

__all__ = [name for name in globals().keys() if not name.startswith('_')]
