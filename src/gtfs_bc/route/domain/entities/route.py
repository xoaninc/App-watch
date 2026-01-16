from dataclasses import dataclass
from typing import Optional
from enum import IntEnum


class RouteType(IntEnum):
    """GTFS Route types."""
    TRAM = 0
    SUBWAY = 1
    RAIL = 2
    BUS = 3
    FERRY = 4
    CABLE_TRAM = 5
    AERIAL_LIFT = 6
    FUNICULAR = 7
    TROLLEYBUS = 11
    MONORAIL = 12


@dataclass
class Route:
    """GTFS Route entity - represents a transit route/line."""

    id: str
    agency_id: str
    short_name: str
    long_name: str
    route_type: RouteType
    color: Optional[str] = None
    text_color: Optional[str] = None
    desc: Optional[str] = None
    url: Optional[str] = None
    sort_order: Optional[int] = None

    @classmethod
    def from_gtfs(cls, row: dict) -> "Route":
        """Create Route from GTFS CSV row."""
        return cls(
            id=row.get("route_id", ""),
            agency_id=row.get("agency_id", ""),
            short_name=row.get("route_short_name", ""),
            long_name=row.get("route_long_name", ""),
            route_type=RouteType(int(row.get("route_type", 2))),
            color=row.get("route_color"),
            text_color=row.get("route_text_color"),
            desc=row.get("route_desc"),
            url=row.get("route_url"),
            sort_order=int(row["route_sort_order"]) if row.get("route_sort_order") else None,
        )
