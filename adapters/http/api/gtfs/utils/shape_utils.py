"""Shape utility functions for GTFS API.

Provides spherical interpolation (slerp) for normalizing route shapes,
ensuring no gaps exceed a maximum distance threshold.
"""

import math
from typing import List, Tuple


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in meters.

    Uses the Haversine formula for accurate geodesic distance calculation.

    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)

    Returns:
        Distance in meters
    """
    R = 6371000  # Earth radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def slerp_interpolate(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    t: float
) -> Tuple[float, float]:
    """Spherical linear interpolation between two points on Earth.

    Interpolates along the great-circle arc between two points,
    producing geodesically accurate intermediate positions.

    Args:
        lat1, lon1: Start point coordinates (degrees)
        lat2, lon2: End point coordinates (degrees)
        t: Interpolation factor (0.0 = start, 1.0 = end)

    Returns:
        Tuple of (lat, lon) for the interpolated point
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Convert to 3D Cartesian coordinates
    x1 = math.cos(lat1_rad) * math.cos(lon1_rad)
    y1 = math.cos(lat1_rad) * math.sin(lon1_rad)
    z1 = math.sin(lat1_rad)

    x2 = math.cos(lat2_rad) * math.cos(lon2_rad)
    y2 = math.cos(lat2_rad) * math.sin(lon2_rad)
    z2 = math.sin(lat2_rad)

    # Calculate the angle between the two points
    dot = x1 * x2 + y1 * y2 + z1 * z2
    dot = max(-1.0, min(1.0, dot))  # Clamp to [-1, 1] for numerical stability
    omega = math.acos(dot)

    # Handle case where points are very close (avoid division by zero)
    if omega < 1e-10:
        return lat1, lon1

    sin_omega = math.sin(omega)

    # SLERP formula
    a = math.sin((1 - t) * omega) / sin_omega
    b = math.sin(t * omega) / sin_omega

    x = a * x1 + b * x2
    y = a * y1 + b * y2
    z = a * z1 + b * z2

    # Convert back to lat/lon
    lat = math.degrees(math.atan2(z, math.sqrt(x * x + y * y)))
    lon = math.degrees(math.atan2(y, x))

    return lat, lon


def normalize_shape(
    points: List[Tuple[float, float, int]],
    max_gap_meters: float = 50.0
) -> List[Tuple[float, float, int]]:
    """Normalize a shape by interpolating points where gaps exceed max distance.

    Takes a list of shape points and adds intermediate points using spherical
    interpolation (slerp) wherever the distance between consecutive points
    exceeds the maximum gap threshold.

    Args:
        points: List of (lat, lon, sequence) tuples, ordered by sequence
        max_gap_meters: Maximum allowed distance between consecutive points

    Returns:
        List of (lat, lon, sequence) tuples with interpolated points added.
        Sequences are renumbered starting from 1.
    """
    if len(points) < 2:
        return points

    result = []
    new_sequence = 1

    for i in range(len(points)):
        lat1, lon1, _ = points[i]

        # Add current point
        result.append((lat1, lon1, new_sequence))
        new_sequence += 1

        # If not the last point, check if we need to interpolate
        if i < len(points) - 1:
            lat2, lon2, _ = points[i + 1]
            distance = haversine_distance(lat1, lon1, lat2, lon2)

            if distance > max_gap_meters:
                # Calculate how many intermediate points we need
                num_segments = math.ceil(distance / max_gap_meters)

                # Add interpolated points
                for j in range(1, num_segments):
                    t = j / num_segments
                    interp_lat, interp_lon = slerp_interpolate(lat1, lon1, lat2, lon2, t)
                    result.append((interp_lat, interp_lon, new_sequence))
                    new_sequence += 1

    return result
