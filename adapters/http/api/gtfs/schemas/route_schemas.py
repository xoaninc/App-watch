"""Route-related response schemas."""

from typing import Optional, List
from pydantic import BaseModel


class RouteResponse(BaseModel):
    id: str
    short_name: str
    long_name: str
    route_type: int
    color: Optional[str]
    text_color: Optional[str]
    agency_id: str
    network_id: Optional[str]
    description: Optional[str] = None
    is_circular: bool = False

    class Config:
        from_attributes = True


class RouteFrequencyResponse(BaseModel):
    """Frequency data for a route (Metro, ML, Tranvía)."""
    trip_id: Optional[str] = None
    route_id: Optional[str] = None
    day_type: str  # 'weekday', 'saturday', 'sunday'
    start_time: str  # HH:MM:SS format
    end_time: str  # HH:MM:SS format
    headway_secs: int  # Interval between trains in seconds
    headway_minutes: Optional[float] = None

    class Config:
        from_attributes = True


class DayOperatingHours(BaseModel):
    """Operating hours for a single day type."""
    first_departure: Optional[str]  # HH:MM:SS format
    last_departure: Optional[str]  # HH:MM:SS format
    total_trips: int


class RouteOperatingHoursResponse(BaseModel):
    """Operating hours for a route (derived from stop_times for Cercanías)."""
    route_id: str
    route_short_name: str
    weekday: Optional[DayOperatingHours]  # Monday-Thursday
    friday: Optional[DayOperatingHours]   # Friday (extended hours)
    saturday: Optional[DayOperatingHours]
    sunday: Optional[DayOperatingHours]
    is_suspended: bool = False
    suspension_message: Optional[str] = None


class ShapePointResponse(BaseModel):
    """A single point in a route shape."""
    lat: float
    lon: float
    sequence: int


class RouteShapeResponse(BaseModel):
    """Shape (path) of a route for drawing on maps."""
    route_id: str
    route_short_name: str
    shape: List[ShapePointResponse]
