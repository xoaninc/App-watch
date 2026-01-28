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
    # Occupancy info (GTFS-RT OccupancyStatus)
    # 0=EMPTY, 1=MANY_SEATS, 2=FEW_SEATS, 3=STANDING_ONLY,
    # 4=CRUSHED, 5=FULL, 6=NOT_ACCEPTING, 7=NO_DATA, 8=NOT_BOARDABLE
    occupancy_status: Optional[int] = None
    occupancy_percentage: Optional[int] = None  # 0-100
    occupancy_per_car: Optional[List[int]] = None  # Per-carriage occupancy
    # Express service info (CIVIS semi-direct trains)
    is_express: bool = False
    express_name: Optional[str] = None  # "CIVIS" for Madrid Cercanías
    express_color: Optional[str] = None  # "#2596be" for CIVIS


class CompactDepartureResponse(BaseModel):
    """Compact departure for widgets/Siri (<100 bytes per item)."""
    line: str  # route_short_name
    color: Optional[str]  # route_color
    dest: Optional[str]  # headsign (truncated)
    mins: int  # minutes_until (realtime if available)
    plat: Optional[str] = None  # platform
    delay: bool = False  # is_delayed
    occ: Optional[int] = None  # occupancy_status (0-8)
    exp: bool = False  # is_express (CIVIS)
    exp_color: Optional[str] = None  # express_color "#2596be"


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
