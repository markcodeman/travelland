"""
Caching utilities for providers.
"""
from typing import Tuple


def bbox_overlaps(cache_bbox: Tuple[float, float, float, float],
                  request_bbox: Tuple[float, float, float, float]) -> bool:
    """Check if cache_bbox overlaps with request_bbox.

    Args:
        cache_bbox: (min_lat, min_lon, max_lat, max_lon)
        request_bbox: (min_lat, min_lon, max_lat, max_lon)

    Returns:
        True if bboxes overlap
    """
    c_south, c_west, c_north, c_east = cache_bbox
    r_south, r_west, r_north, r_east = request_bbox

    # Check for overlap
    return (c_south <= r_north and c_north >= r_south and
            c_west <= r_east and c_east >= r_west)