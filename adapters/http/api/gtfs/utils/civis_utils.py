"""CIVIS express service detection utilities.

CIVIS is a semi-direct/express service operated by Renfe Cercanías that only
stops at main stations, skipping intermediate stops to reduce travel time.

In Madrid Cercanías, CIVIS operates on:
- C2: Guadalajara - Chamartín (≤9 stops vs 15-19 normal)
- C3: Aranjuez - Chamartín (9 stops vs 13 normal)
- C10: Villalba/El Escorial - Chamartín (≤8 stops vs 14-18 normal)

CIVIS typically runs during rush hours:
- Morning: From suburbs towards Madrid
- Afternoon: From Madrid towards suburbs
"""

from typing import Optional, Tuple

# CIVIS branding
CIVIS_COLOR = "#2596be"
CIVIS_NAME = "CIVIS"

# Routes with CIVIS service and their stop count thresholds
# Format: route_id_pattern -> (max_stops_for_civis, route_long_name_pattern)
CIVIS_ROUTES = {
    # Madrid Cercanías
    "RENFE_C2_35": {"max_stops": 9, "name": "Guadalajara - Chamartín"},
    "RENFE_C3_36": {"max_stops": 9, "name": "Aranjuez - Chamartín"},
    "RENFE_C10_42": {"max_stops": 8, "name": "Villalba - Chamartín"},
}

# Alternative detection by route_short_name + network
# (route_short_name, network_id) -> max_stops_for_civis
CIVIS_BY_SHORT_NAME = {
    ("C2", 17): 9,   # Madrid network_id = 17
    ("C3", 17): 9,
    ("C10", 17): 8,
    ("C8a", 17): 8,  # C8a shares some CIVIS with C10
}


def detect_civis(
    route_id: str,
    route_short_name: str,
    stop_count: int,
    network_id: Optional[int] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Detect if a trip is a CIVIS express service.

    Args:
        route_id: The route ID (e.g., "RENFE_C2_35")
        route_short_name: The route short name (e.g., "C2")
        stop_count: Number of stops in the trip
        network_id: Optional network ID for disambiguation

    Returns:
        Tuple of (is_civis, express_name, express_color)
    """
    # Check by route_id first (most specific)
    if route_id in CIVIS_ROUTES:
        config = CIVIS_ROUTES[route_id]
        if stop_count <= config["max_stops"]:
            return True, CIVIS_NAME, CIVIS_COLOR

    # Check by route_short_name + network_id
    if network_id:
        key = (route_short_name, network_id)
        if key in CIVIS_BY_SHORT_NAME:
            max_stops = CIVIS_BY_SHORT_NAME[key]
            if stop_count <= max_stops:
                return True, CIVIS_NAME, CIVIS_COLOR

    # Not a CIVIS service
    return False, None, None


def get_civis_info() -> dict:
    """Get CIVIS branding info for frontend use.

    Returns:
        Dict with CIVIS color and name.
    """
    return {
        "name": CIVIS_NAME,
        "color": CIVIS_COLOR,
        "description": "Servicio semi-directo de Cercanías",
    }
