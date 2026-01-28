"""Occupancy utilities for GTFS-RT OccupancyStatus.

GTFS-RT OccupancyStatus enum values:
    EMPTY = 0                      # Vacío o casi vacío
    MANY_SEATS_AVAILABLE = 1       # Muchos asientos libres
    FEW_SEATS_AVAILABLE = 2        # Pocos asientos libres
    STANDING_ROOM_ONLY = 3         # Solo de pie
    CRUSHED_STANDING_ROOM_ONLY = 4 # Lleno, difícil entrar
    FULL = 5                       # Lleno, no admite más pasajeros
    NOT_ACCEPTING_PASSENGERS = 6   # No admite pasajeros
    NO_DATA_AVAILABLE = 7          # Sin datos
    NOT_BOARDABLE = 8              # No se puede subir (averías, etc.)
"""

from typing import Optional, List
import json


# OccupancyStatus enum values
EMPTY = 0
MANY_SEATS_AVAILABLE = 1
FEW_SEATS_AVAILABLE = 2
STANDING_ROOM_ONLY = 3
CRUSHED_STANDING_ROOM_ONLY = 4
FULL = 5
NOT_ACCEPTING_PASSENGERS = 6
NO_DATA_AVAILABLE = 7
NOT_BOARDABLE = 8


def percentage_to_status(percentage: Optional[int]) -> Optional[int]:
    """Convert occupancy percentage (0-100) to OccupancyStatus enum.

    Args:
        percentage: Occupancy percentage (0-100), or None if unknown

    Returns:
        OccupancyStatus enum value (0-8), or None if input is None
    """
    if percentage is None:
        return None

    if percentage <= 10:
        return EMPTY
    elif percentage <= 30:
        return MANY_SEATS_AVAILABLE
    elif percentage <= 50:
        return FEW_SEATS_AVAILABLE
    elif percentage <= 70:
        return STANDING_ROOM_ONLY
    elif percentage <= 85:
        return CRUSHED_STANDING_ROOM_ONLY
    else:
        return FULL


def status_to_percentage(status: Optional[int]) -> Optional[int]:
    """Convert OccupancyStatus enum to approximate percentage.

    Args:
        status: OccupancyStatus enum value (0-8)

    Returns:
        Approximate percentage (0-100), or None if status is None or NO_DATA
    """
    if status is None:
        return None

    mapping = {
        EMPTY: 5,
        MANY_SEATS_AVAILABLE: 25,
        FEW_SEATS_AVAILABLE: 45,
        STANDING_ROOM_ONLY: 65,
        CRUSHED_STANDING_ROOM_ONLY: 80,
        FULL: 95,
        NOT_ACCEPTING_PASSENGERS: 100,
        NO_DATA_AVAILABLE: None,
        NOT_BOARDABLE: None,
    }
    return mapping.get(status)


def estimate_occupancy_by_time(hour: int, is_weekend: bool = False) -> int:
    """Estimate occupancy status based on time of day.

    Uses heuristic based on typical transit patterns:
    - Morning rush (7-9): High occupancy
    - Evening rush (18-20): High occupancy
    - Midday: Medium occupancy
    - Night: Low occupancy
    - Weekend: Generally lower

    Args:
        hour: Hour of day (0-23)
        is_weekend: True if Saturday or Sunday

    Returns:
        OccupancyStatus enum value (0-3)
    """
    if is_weekend:
        # Weekends are generally less crowded
        if hour in [11, 12, 13, 18, 19]:
            return FEW_SEATS_AVAILABLE
        elif hour in [10, 14, 15, 16, 17, 20]:
            return MANY_SEATS_AVAILABLE
        else:
            return EMPTY

    # Weekday patterns
    if hour in [7, 8, 18, 19]:
        # Peak rush hours
        return STANDING_ROOM_ONLY
    elif hour in [9, 17, 20]:
        # Shoulder hours
        return FEW_SEATS_AVAILABLE
    elif hour in [6, 10, 11, 12, 13, 14, 15, 16, 21]:
        # Off-peak daytime
        return MANY_SEATS_AVAILABLE
    else:
        # Night hours (22-5)
        return EMPTY


def parse_occupancy_per_car(occupancy_json: Optional[str]) -> Optional[List[int]]:
    """Parse JSON array of per-carriage occupancy.

    Args:
        occupancy_json: JSON string like "[60, 65, 70, 62]"

    Returns:
        List of integers, or None if parsing fails
    """
    if not occupancy_json:
        return None

    try:
        data = json.loads(occupancy_json)
        if isinstance(data, list):
            return [int(x) if x is not None else None for x in data]
        return None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def get_occupancy_label(status: Optional[int]) -> str:
    """Get human-readable label for occupancy status.

    Args:
        status: OccupancyStatus enum value

    Returns:
        Human-readable string
    """
    if status is None:
        return "Unknown"

    labels = {
        EMPTY: "Empty",
        MANY_SEATS_AVAILABLE: "Many seats",
        FEW_SEATS_AVAILABLE: "Few seats",
        STANDING_ROOM_ONLY: "Standing only",
        CRUSHED_STANDING_ROOM_ONLY: "Very crowded",
        FULL: "Full",
        NOT_ACCEPTING_PASSENGERS: "Not accepting",
        NO_DATA_AVAILABLE: "No data",
        NOT_BOARDABLE: "Not boardable",
    }
    return labels.get(status, "Unknown")
