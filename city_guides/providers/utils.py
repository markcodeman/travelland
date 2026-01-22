"""
Shared utilities for provider modules.
"""
import aiohttp
from typing import Optional
from contextlib import asynccontextmanager


@asynccontextmanager
async def get_session(session: Optional[aiohttp.ClientSession] = None):
    """Context manager for aiohttp session handling.

    If session is provided, yields it.
    If not, creates a new session and closes it after use.
    """
    if session is not None:
        yield session
    else:
        async with aiohttp.ClientSession() as new_session:
            yield new_session


class VenueNormalizer:
    """Base class for normalizing venue data from different providers."""

    @staticmethod
    def normalize_venue(name: str, address: str, lat: float, lon: float,
                       place_id: str = "", osm_url: str = "", tags: str = "",
                       rating: Optional[float] = None, source: str = "") -> dict:
        """Normalize a venue dict to standard format."""
        return {
            "name": name or "",
            "address": address or "",
            "latitude": lat,
            "longitude": lon,
            "place_id": place_id or "",
            "osm_url": osm_url or "",
            "tags": tags or "",
            "rating": rating,
            "source": source or "",
        }