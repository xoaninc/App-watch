"""Route utility functions for GTFS API."""

import re as regex_module
from typing import Optional

# Prefixes for networks with real GTFS-RT data (don't filter by operating hours)
GTFS_RT_PREFIXES = (
    "RENFE_",        # Cercanías RENFE
    "TMB_METRO_",    # Metro Barcelona
    "FGC_",          # FGC
    "EUSKOTREN_",    # Euskotren
    "METRO_BILBAO_", # Metro Bilbao
)


def is_static_gtfs_route(route_id: str) -> bool:
    """Check if a route uses static GTFS (no real-time data).

    Routes with GTFS-RT don't need operating hours filtering since
    real-time data already reflects actual service.
    """
    return not any(route_id.startswith(prefix) for prefix in GTFS_RT_PREFIXES)


def is_route_operating(db, route_id: str, current_seconds: int, day_type: str, RouteFrequencyModel) -> bool:
    """Check if a route is currently operating based on its frequency schedule.

    Returns True if current time is within operating hours, False otherwise.
    For routes without frequency data, returns True (assume always operating).
    """
    # Get frequencies for this route and day type
    frequencies = db.query(RouteFrequencyModel).filter(
        RouteFrequencyModel.route_id == route_id,
        RouteFrequencyModel.day_type == day_type
    ).all()

    if not frequencies:
        # No frequency data - assume always operating (or use stop_times)
        return True

    def parse_time_to_seconds(time_val) -> int:
        """Parse time (TIME or VARCHAR like '25:30:00') to seconds."""
        if hasattr(time_val, 'hour'):
            # It's a time object
            return time_val.hour * 3600 + time_val.minute * 60 + time_val.second
        else:
            # It's a string like "25:30:00"
            parts = str(time_val).split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    # First pass: find max_end from ALL entries (including aggregates)
    max_end = None
    for freq in frequencies:
        end_secs = parse_time_to_seconds(freq.end_time)
        if max_end is None or end_secs > max_end:
            max_end = end_secs

    # Second pass: find min_start from NON-aggregate entries only
    min_start = None
    for freq in frequencies:
        start_secs = parse_time_to_seconds(freq.start_time)
        end_secs = parse_time_to_seconds(freq.end_time)

        # Skip aggregates (00:00:00 to 25:00:00+) for min_start calculation
        is_aggregate = start_secs == 0 and end_secs >= 25 * 3600
        if is_aggregate:
            continue

        if min_start is None or start_secs < min_start:
            min_start = start_secs

    # If no valid min_start found (only aggregates), use default opening time
    if min_start is None:
        min_start = 6 * 3600  # Default to 6:00 AM

    if max_end is None:
        return True  # No valid data

    # Check if current time is within operating hours
    if max_end > 24 * 3600:
        # Service runs past midnight
        late_night_cutoff = max_end - 24 * 3600
        if current_seconds >= min_start or current_seconds <= late_night_cutoff:
            return True
    else:
        # Normal hours
        if min_start <= current_seconds <= max_end:
            return True

    return False


def has_real_cercanias(cor_cercanias: Optional[str]) -> bool:
    """Check if cor_cercanias contains real Cercanías lines (C* or R* patterns).

    Filters out Euskotren lines (E1, E2, TR) which may appear in cor_cercanias
    but are not actually Renfe Cercanías.

    Args:
        cor_cercanias: Comma-separated list of Cercanías lines (e.g., "C1, C3, R2")

    Returns:
        True if any line matches C* or R* pattern (Cercanías/Rodalies Renfe)
    """
    if not cor_cercanias:
        return False
    lines = [line.strip() for line in cor_cercanias.split(',')]
    for line in lines:
        # Match C1, C2, R1, R2, etc. (Renfe Cercanías/Rodalies)
        if regex_module.match(r'^[CR]\d', line):
            return True
    return False
