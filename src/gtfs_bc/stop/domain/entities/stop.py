from dataclasses import dataclass
from typing import Optional
from enum import IntEnum


class LocationType(IntEnum):
    """GTFS Location types."""
    STOP = 0  # Stop or platform
    STATION = 1  # Station
    ENTRANCE_EXIT = 2  # Station entrance/exit
    GENERIC_NODE = 3  # Generic node
    BOARDING_AREA = 4  # Boarding area


@dataclass
class Stop:
    """GTFS Stop entity - represents a stop/station."""

    id: str
    name: str
    lat: float
    lon: float
    code: Optional[str] = None
    desc: Optional[str] = None
    zone_id: Optional[str] = None
    url: Optional[str] = None
    location_type: LocationType = LocationType.STOP
    parent_station_id: Optional[str] = None
    timezone: Optional[str] = None
    wheelchair_boarding: Optional[int] = None
    platform_code: Optional[str] = None
    province: Optional[str] = None

    @classmethod
    def from_gtfs(cls, row: dict) -> "Stop":
        """Create Stop from GTFS CSV row."""
        return cls(
            id=row.get("stop_id", ""),
            name=row.get("stop_name", ""),
            lat=float(row.get("stop_lat", 0)),
            lon=float(row.get("stop_lon", 0)),
            code=row.get("stop_code"),
            desc=row.get("stop_desc"),
            zone_id=row.get("zone_id"),
            url=row.get("stop_url"),
            location_type=LocationType(int(row.get("location_type", 0) or 0)),
            parent_station_id=row.get("parent_station") or None,
            timezone=row.get("stop_timezone"),
            wheelchair_boarding=int(row["wheelchair_boarding"]) if row.get("wheelchair_boarding") else None,
            platform_code=row.get("platform_code"),
            province=row.get("province"),
        )
