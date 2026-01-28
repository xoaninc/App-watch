"""Departure and trip response schemas."""

from typing import Optional, List
from pydantic import BaseModel


class TrainPositionSchema(BaseModel):
    """Current position of the train."""
    latitude: float
    longitude: float
    current_stop_name: str
    status: str  # STOPPED_AT, IN_TRANSIT_TO, INCOMING_AT
    progress_percent: float
    estimated: bool = True  # True if calculated from schedule, False if from GTFS-RT


class DepartureResponse(BaseModel):
    trip_id: str
    route_id: str
    route_short_name: str
    route_color: Optional[str]
    headsign: Optional[str]
    departure_time: str
    departure_seconds: int
    minutes_until: int
    stop_sequence: int
    # Platform/track info
    platform: Optional[str] = None
    platform_estimated: bool = False
    # Realtime delay fields
    delay_seconds: Optional[int] = None
    realtime_departure_time: Optional[str] = None
    realtime_minutes_until: Optional[int] = None
    is_delayed: bool = False
    # Train position
    train_position: Optional[TrainPositionSchema] = None
    # Frequency-based estimation
    frequency_based: bool = False
    headway_secs: Optional[int] = None


class CompactDepartureResponse(BaseModel):
    """Compact departure for widgets/Siri (<100 bytes per item)."""
    line: str  # route_short_name
    color: Optional[str]  # route_color
    dest: Optional[str]  # headsign (truncated)
    mins: int  # minutes_until (realtime if available)
    plat: Optional[str] = None  # platform
    delay: bool = False  # is_delayed


class TripStopResponse(BaseModel):
    stop_id: str
    stop_name: str
    arrival_time: str
    departure_time: str
    stop_sequence: int
    stop_lat: float
    stop_lon: float


class TripDetailResponse(BaseModel):
    id: str
    route_id: str
    route_short_name: str
    route_long_name: str
    route_color: Optional[str]
    headsign: Optional[str]
    direction_id: Optional[int]
    stops: List[TripStopResponse]


class AgencyResponse(BaseModel):
    id: str
    name: str
    url: Optional[str]
    timezone: str
    lang: Optional[str]
    phone: Optional[str]

    class Config:
        from_attributes = True
