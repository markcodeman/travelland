import pytest
import math
from city_guides.src.persistence import haversine_km

def test_haversine_km_accuracy():
    # NYC (40.7128, -74.0060) to Newark (40.7357, -74.1724) ~14km
    d = haversine_km(40.7128, -74.0060, 40.7357, -74.1724)
    assert 12 < d < 16

def test_conservative_bbox():
    # Should produce a ~10km bbox around center
    lat, lon = 40.7128, -74.0060
    radius_km = 10
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    bbox = [lon - dlon, lat - dlat, lon + dlon, lat + dlat]
    # Check bbox spans ~20km in both directions
    width_km = haversine_km(lat, lon - dlon, lat, lon + dlon)
    height_km = haversine_km(lat - dlat, lon, lat + dlat, lon)
    assert 18 < width_km < 22
    assert 18 < height_km < 22
