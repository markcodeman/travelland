"""
Shared utilities for provider modules.
"""
import aiohttp
import logging
from typing import Optional, Tuple, Dict, Any
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


# HTTP client wrapper for consistent requests across providers
async def http_get(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
    session: Optional[aiohttp.ClientSession] = None
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Unified HTTP GET with error handling and logging.
    
    Args:
        url: The URL to request
        params: Query parameters
        headers: Request headers
        timeout: Request timeout in seconds
        session: Optional aiohttp session to reuse
        
    Returns:
        Tuple of (response_data, error_message)
        - response_data: Parsed JSON response or None if error
        - error_message: Error string or None if successful
    """
    try:
        async with get_session(session) as sess:
            async with sess.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                resp.raise_for_status()
                # Try to parse JSON, return raw text if not JSON
                try:
                    return await resp.json(), None
                except:
                    text = await resp.text()
                    return text, None
    except aiohttp.ClientError as e:
        logging.error(f"HTTP GET {url} failed: {e}")
        return None, str(e)
    except Exception as e:
        logging.error(f"Unexpected error in HTTP GET {url}: {e}")
        return None, str(e)


async def http_post(
    url: str,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
    session: Optional[aiohttp.ClientSession] = None
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Unified HTTP POST with error handling and logging.
    
    Args:
        url: The URL to request
        json_data: JSON payload
        params: Query parameters
        headers: Request headers
        timeout: Request timeout in seconds
        session: Optional aiohttp session to reuse
        
    Returns:
        Tuple of (response_data, error_message)
    """
    try:
        async with get_session(session) as sess:
            async with sess.post(url, json=json_data, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                resp.raise_for_status()
                try:
                    return await resp.json(), None
                except:
                    text = await resp.text()
                    return text, None
    except aiohttp.ClientError as e:
        logging.error(f"HTTP POST {url} failed: {e}")
        return None, str(e)
    except Exception as e:
        logging.error(f"Unexpected error in HTTP POST {url}: {e}")
        return None, str(e)