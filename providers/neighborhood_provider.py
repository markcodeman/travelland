# Backwards-compatibility shim: re-export the implementation from
# `city_guides.providers.neighborhood_provider`
from city_guides.providers.neighborhood_provider import *  # noqa: F401,F403

__all__ = [name for name in globals().keys() if not name.startswith('_')]
