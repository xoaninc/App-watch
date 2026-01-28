"""Walking route generation using OSRM and BRouter.

Generates realistic pedestrian routes between stops using routing services
that follow actual sidewalks, crosswalks, and paths.

Services tried in order:
1. OSRM (Open Source Routing Machine) - foot profile
2. BRouter - trekking profile (fallback)
"""

import json
import logging
from typing import List, Tuple, Optional
from math import radians, sin, cos, sqrt, atan2

import httpx

logger = logging.getLogger(__name__)

OSRM_URL = "https://router.project-osrm.org/route/v1/foot"
BROUTER_URL = "https://brouter.de/brouter"
REQUEST_TIMEOUT = 15.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two coordinates."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlam = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlam/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def _try_osrm(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> Optional[Tuple[List[Tuple[float, float]], int, int]]:
    """Try OSRM routing service."""
    url = f"{OSRM_URL}/{from_lon},{from_lat};{to_lon},{to_lat}?overview=full&geometries=geojson"

    try:
        response = httpx.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            return None

        data = response.json()
        if data.get('code') != 'Ok' or not data.get('routes'):
            return None

        route = data['routes'][0]
        coords_raw = route['geometry']['coordinates']

        # Convert from [lon, lat] to (lat, lon)
        coords = [(c[1], c[0]) for c in coords_raw]

        # OSRM returns distance in meters and duration in seconds
        distance_m = int(route.get('distance', 0))
        walk_time_s = int(route.get('duration', 0))

        return coords, distance_m, walk_time_s

    except Exception as e:
        logger.debug(f"OSRM error: {e}")
        return None


def _try_brouter(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> Optional[Tuple[List[Tuple[float, float]], int, int]]:
    """Try BRouter routing service."""
    url = f"{BROUTER_URL}?lonlats={from_lon},{from_lat}|{to_lon},{to_lat}&profile=trekking&format=geojson"

    try:
        response = httpx.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            return None

        data = response.json()
        feature = data['features'][0]
        coords_raw = feature['geometry']['coordinates']
        props = feature['properties']

        # Convert from [lon, lat] to (lat, lon)
        coords = [(c[1], c[0]) for c in coords_raw]

        distance_m = int(props.get('track-length', 0))
        walk_time_s = int(props.get('total-time', 0))

        # Estimate time if not provided (5 km/h walking speed)
        if walk_time_s == 0 and distance_m > 0:
            walk_time_s = int(distance_m / 1.39)

        return coords, distance_m, walk_time_s

    except Exception as e:
        logger.debug(f"BRouter error: {e}")
        return None


def generate_walking_route(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
) -> Optional[Tuple[List[Tuple[float, float]], int, int]]:
    """Generate a walking route between two points.

    Tries multiple routing services in order:
    1. BRouter (priority - better pedestrian paths)
    2. OSRM (fallback)

    Args:
        from_lat: Origin latitude
        from_lon: Origin longitude
        to_lat: Destination latitude
        to_lon: Destination longitude

    Returns:
        Tuple of (coordinates, distance_m, walk_time_s) or None if failed.
        coordinates is a list of (lat, lon) tuples.
    """
    # Try BRouter first (priority)
    result = _try_brouter(from_lat, from_lon, to_lat, to_lon)
    if result:
        return result

    # Fallback to OSRM
    result = _try_osrm(from_lat, from_lon, to_lat, to_lon)
    if result:
        return result

    logger.warning(f"All routing services failed for {from_lat},{from_lon} -> {to_lat},{to_lon}")
    return None


def coords_to_json(coords: List[Tuple[float, float]]) -> str:
    """Convert coordinates list to JSON string for storage."""
    return json.dumps([[lat, lon] for lat, lon in coords])


def json_to_coords(json_str: str) -> List[Tuple[float, float]]:
    """Parse JSON string to coordinates list."""
    data = json.loads(json_str)
    return [(lat, lon) for lat, lon in data]
