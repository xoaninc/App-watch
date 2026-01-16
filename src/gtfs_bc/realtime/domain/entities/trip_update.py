from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class StopTimeUpdate:
    """Update for a specific stop in a trip."""
    stop_id: str
    arrival_delay: Optional[int] = None  # Delay in seconds
    arrival_time: Optional[datetime] = None  # Predicted arrival time
    departure_delay: Optional[int] = None  # Delay in seconds
    departure_time: Optional[datetime] = None  # Predicted departure time

    @classmethod
    def from_gtfsrt_json(cls, data: dict) -> "StopTimeUpdate":
        """Create StopTimeUpdate from GTFS-RT JSON."""
        arrival = data.get("arrival", {})
        departure = data.get("departure", {})

        arrival_time = None
        if arrival.get("time"):
            arrival_time = datetime.fromtimestamp(int(arrival["time"]))

        departure_time = None
        if departure.get("time"):
            departure_time = datetime.fromtimestamp(int(departure["time"]))

        return cls(
            stop_id=data.get("stopId", ""),
            arrival_delay=arrival.get("delay"),
            arrival_time=arrival_time,
            departure_delay=departure.get("delay"),
            departure_time=departure_time,
        )


@dataclass
class TripUpdate:
    """GTFS-RT Trip Update entity.

    Represents delay information for a trip.
    """
    trip_id: str
    delay: int  # Overall delay in seconds
    timestamp: datetime
    stop_time_updates: List[StopTimeUpdate] = field(default_factory=list)
    vehicle_id: Optional[str] = None
    wheelchair_accessible: Optional[bool] = None

    @classmethod
    def from_gtfsrt_json(cls, entity: dict) -> "TripUpdate":
        """Create TripUpdate from GTFS-RT JSON entity."""
        trip_update = entity.get("tripUpdate", {})
        trip = trip_update.get("trip", {})
        vehicle = trip_update.get("vehicle", {})

        stop_time_updates = [
            StopTimeUpdate.from_gtfsrt_json(stu)
            for stu in trip_update.get("stopTimeUpdate", [])
        ]

        wheelchair = vehicle.get("wheelchairAccessible")
        wheelchair_accessible = None
        if wheelchair == "WHEELCHAIR_ACCESSIBLE":
            wheelchair_accessible = True
        elif wheelchair == "WHEELCHAIR_INACCESSIBLE":
            wheelchair_accessible = False

        return cls(
            trip_id=trip.get("tripId", ""),
            delay=trip_update.get("delay", 0),
            timestamp=datetime.now(),  # GTFS-RT doesn't always include timestamp
            stop_time_updates=stop_time_updates,
            vehicle_id=vehicle.get("id"),
            wheelchair_accessible=wheelchair_accessible,
        )

    @property
    def delay_minutes(self) -> int:
        """Get delay in minutes."""
        return self.delay // 60

    @property
    def is_delayed(self) -> bool:
        """Check if trip is delayed (more than 1 minute)."""
        return self.delay > 60
