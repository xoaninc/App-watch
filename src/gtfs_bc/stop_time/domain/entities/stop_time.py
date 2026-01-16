from dataclasses import dataclass
from typing import Optional


@dataclass
class StopTime:
    """GTFS StopTime entity - represents a stop time in a trip."""

    trip_id: str
    stop_id: str
    stop_sequence: int
    arrival_time: str  # HH:MM:SS format (can be > 24:00:00)
    departure_time: str
    stop_headsign: Optional[str] = None
    pickup_type: int = 0  # 0 = regular, 1 = no pickup, 2 = phone agency, 3 = coordinate with driver
    drop_off_type: int = 0
    shape_dist_traveled: Optional[float] = None
    timepoint: int = 1  # 0 = approximate, 1 = exact

    @classmethod
    def from_gtfs(cls, row: dict) -> "StopTime":
        """Create StopTime from GTFS CSV row."""
        return cls(
            trip_id=row.get("trip_id", ""),
            stop_id=row.get("stop_id", ""),
            stop_sequence=int(row.get("stop_sequence", 0)),
            arrival_time=row.get("arrival_time", ""),
            departure_time=row.get("departure_time", ""),
            stop_headsign=row.get("stop_headsign"),
            pickup_type=int(row.get("pickup_type", 0) or 0),
            drop_off_type=int(row.get("drop_off_type", 0) or 0),
            shape_dist_traveled=float(row["shape_dist_traveled"]) if row.get("shape_dist_traveled") else None,
            timepoint=int(row.get("timepoint", 1) or 1),
        )

    def arrival_seconds(self) -> int:
        """Convert arrival time to seconds since midnight."""
        return self._time_to_seconds(self.arrival_time)

    def departure_seconds(self) -> int:
        """Convert departure time to seconds since midnight."""
        return self._time_to_seconds(self.departure_time)

    @staticmethod
    def _time_to_seconds(time_str: str) -> int:
        """Convert HH:MM:SS to seconds. Handles times > 24:00:00."""
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2]) if len(parts) > 2 else 0
        return hours * 3600 + minutes * 60 + seconds
