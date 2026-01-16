from dataclasses import dataclass
from math import radians, cos, sin, asin, sqrt
from typing import Tuple


@dataclass(frozen=True)
class GeoPoint:
    """Geographic point with latitude and longitude."""
    latitude: float
    longitude: float

    def to_tuple(self) -> Tuple[float, float]:
        """Return as (lat, lon) tuple."""
        return (self.latitude, self.longitude)

    def distance_to(self, other: "GeoPoint") -> float:
        """Calculate distance to another point in meters using Haversine formula."""
        return haversine_distance(
            self.latitude, self.longitude,
            other.latitude, other.longitude
        )


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the distance between two points on Earth using the Haversine formula.

    Args:
        lat1: Latitude of first point in degrees
        lon1: Longitude of first point in degrees
        lat2: Latitude of second point in degrees
        lon2: Longitude of second point in degrees

    Returns:
        Distance in meters
    """
    # Earth's radius in meters
    R = 6_371_000

    # Convert degrees to radians
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    # Haversine formula
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * asin(sqrt(a))

    return R * c


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial bearing from point 1 to point 2.

    Returns:
        Bearing in degrees (0-360, where 0 is North)
    """
    from math import atan2, degrees

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lon = radians(lon2 - lon1)

    x = sin(delta_lon) * cos(lat2_rad)
    y = cos(lat1_rad) * sin(lat2_rad) - sin(lat1_rad) * cos(lat2_rad) * cos(delta_lon)

    initial_bearing = atan2(x, y)
    compass_bearing = (degrees(initial_bearing) + 360) % 360

    return compass_bearing
