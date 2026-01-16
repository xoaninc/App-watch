"""Province lookup using PostGIS spatial queries.

This module provides functions to determine which Spanish province
a given coordinate belongs to using accurate PostGIS polygon boundaries.
"""

from typing import Optional
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def get_province_by_coordinates(
    db: Session,
    lat: float,
    lon: float
) -> Optional[str]:
    """Get province name for given coordinates using PostGIS ST_Contains.

    Uses PostGIS spatial queries to determine which province contains
    the given coordinates.

    Args:
        db: SQLAlchemy database session
        lat: Latitude in decimal degrees (-90 to 90)
        lon: Longitude in decimal degrees (-180 to 180)

    Returns:
        Province name if found, None otherwise

    Raises:
        ValueError: If latitude or longitude are out of valid range

    Example:
        >>> get_province_by_coordinates(db, 40.4168, -3.7038)
        'Madrid'
    """
    if not (-90 <= lat <= 90):
        raise ValueError(f"Invalid latitude: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Invalid longitude: {lon}")

    try:
        # Create a point geometry and find containing province
        # ST_Contains(polygon, point) checks if point is inside polygon
        result = db.execute(
            text("""
                SELECT name
                FROM spanish_provinces
                WHERE ST_Contains(
                    geometry,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                )
                LIMIT 1
            """),
            {'lat': lat, 'lon': lon}
        ).fetchone()

        if result:
            return result[0]

        logger.debug(f"No province found for coordinates ({lat}, {lon})")
        return None

    except Exception as e:
        logger.error(f"Error querying province for ({lat}, {lon}): {e}")
        return None


def get_province_and_nucleo_by_coordinates(
    db: Session,
    lat: float,
    lon: float
) -> Optional[tuple]:
    """Get province name and nucleo for given coordinates.

    Uses PostGIS spatial queries to determine which province contains
    the given coordinates, then returns both province and its mapped nucleo.

    Args:
        db: SQLAlchemy database session
        lat: Latitude in decimal degrees (-90 to 90)
        lon: Longitude in decimal degrees (-180 to 180)

    Returns:
        Tuple of (province_name, nucleo_name) if found, None otherwise

    Raises:
        ValueError: If latitude or longitude are out of valid range

    Example:
        >>> get_province_and_nucleo_by_coordinates(db, 40.4168, -3.7038)
        ('Madrid', 'Madrid')
    """
    if not (-90 <= lat <= 90):
        raise ValueError(f"Invalid latitude: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Invalid longitude: {lon}")

    try:
        # Query province and its nucleo mapping
        result = db.execute(
            text("""
                SELECT name, nucleo_name
                FROM spanish_provinces
                WHERE ST_Contains(
                    geometry,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                )
                LIMIT 1
            """),
            {'lat': lat, 'lon': lon}
        ).fetchone()

        if result:
            province_name, nucleo_name = result
            return (province_name, nucleo_name)

        logger.debug(f"No province found for coordinates ({lat}, {lon})")
        return None

    except Exception as e:
        logger.error(f"Error querying province/nucleo for ({lat}, {lon}): {e}")
        return None


def batch_lookup_provinces(
    db: Session,
    coordinates: list[tuple[float, float]]
) -> list[Optional[str]]:
    """Look up provinces for multiple coordinates efficiently.

    Args:
        db: Database session
        coordinates: List of (lat, lon) tuples

    Returns:
        List of province names (None for not found)

    Example:
        >>> coords = [(40.42, -3.72), (41.38, 2.17)]
        >>> batch_lookup_provinces(db, coords)
        ['Madrid', 'Barcelona']
    """
    if not coordinates:
        return []

    # Process each coordinate
    results = []
    for lat, lon in coordinates:
        province = get_province_by_coordinates(db, lat, lon)
        results.append(province)

    return results
