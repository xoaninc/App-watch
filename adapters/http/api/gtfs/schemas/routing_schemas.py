"""Routing/Journey planner response schemas.

These schemas define the structure of route planning responses,
including multi-segment journeys with transfers.
"""

from typing import Optional, List
from pydantic import BaseModel


class JourneyStopResponse(BaseModel):
    """A stop within a journey segment."""
    id: str
    name: str
    lat: float
    lon: float


class JourneyCoordinate(BaseModel):
    """A coordinate point in a journey segment shape."""
    lat: float
    lon: float


class JourneySegmentResponse(BaseModel):
    """A single segment of a journey (transit ride or walking transfer).

    Segments are the building blocks of a journey. Each segment represents
    either:
    - A transit ride on a single line (type="transit")
    - A walking transfer between stations (type="walking")
    """
    type: str  # "transit" or "walking"
    transport_mode: str  # "metro", "cercanias", "tram", "walking", etc.

    # Line info (only for transit segments)
    line_id: Optional[str] = None
    line_name: Optional[str] = None
    line_color: Optional[str] = None
    headsign: Optional[str] = None

    # Origin and destination
    origin: JourneyStopResponse
    destination: JourneyStopResponse

    # Intermediate stops (only for transit segments)
    intermediate_stops: List[JourneyStopResponse] = []

    # Timing
    duration_minutes: int

    # Distance (mainly for walking segments)
    distance_meters: Optional[int] = None

    # Shape coordinates (normalized if requested)
    coordinates: List[JourneyCoordinate] = []


class JourneyResponse(BaseModel):
    """Complete journey from origin to destination.

    A journey consists of one or more segments, which can be
    transit rides or walking transfers.
    """
    # Origin and destination
    origin: JourneyStopResponse
    destination: JourneyStopResponse

    # Summary
    total_duration_minutes: int
    total_walking_minutes: int
    total_transit_minutes: int
    transfer_count: int

    # Detailed segments
    segments: List[JourneySegmentResponse]


class RoutePlannerResponse(BaseModel):
    """Response from the route planner endpoint.

    Contains the best journey found, or an error message if no route exists.
    """
    success: bool
    message: Optional[str] = None
    journey: Optional[JourneyResponse] = None

    # Alternative journeys (future enhancement)
    alternatives: List[JourneyResponse] = []
