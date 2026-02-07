# Backwards-compatible shim: re-export the app from `city_guides.src.app`
from city_guides.src.app import *  # noqa: F401,F403

__all__ = [name for name in globals().keys() if not name.startswith('_')]
