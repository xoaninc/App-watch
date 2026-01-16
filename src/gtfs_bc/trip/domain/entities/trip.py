from dataclasses import dataclass
from typing import Optional


@dataclass
class Trip:
    """GTFS Trip entity - represents a scheduled trip."""

    id: str
    route_id: str
    service_id: str
    headsign: Optional[str] = None
    short_name: Optional[str] = None
    direction_id: Optional[int] = None  # 0 = outbound, 1 = inbound
    block_id: Optional[str] = None
    shape_id: Optional[str] = None
    wheelchair_accessible: Optional[int] = None
    bikes_allowed: Optional[int] = None

    @classmethod
    def from_gtfs(cls, row: dict) -> "Trip":
        """Create Trip from GTFS CSV row."""
        return cls(
            id=row.get("trip_id", ""),
            route_id=row.get("route_id", ""),
            service_id=row.get("service_id", ""),
            headsign=row.get("trip_headsign"),
            short_name=row.get("trip_short_name"),
            direction_id=int(row["direction_id"]) if row.get("direction_id") else None,
            block_id=row.get("block_id"),
            shape_id=row.get("shape_id"),
            wheelchair_accessible=int(row["wheelchair_accessible"]) if row.get("wheelchair_accessible") else None,
            bikes_allowed=int(row["bikes_allowed"]) if row.get("bikes_allowed") else None,
        )
