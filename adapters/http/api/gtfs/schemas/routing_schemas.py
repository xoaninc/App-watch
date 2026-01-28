"""Routing/Journey planner response schemas.

These schemas define the structure of route planning responses,
including multi-segment journeys with transfers.

Updated: 2026-01-27 - RAPTOR implementation with Pareto-optimal alternatives
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
    mode: str  # "metro", "cercanias", "tram", "walking", etc.

    # Line info (only for transit segments)
    line_id: Optional[str] = None
    line_name: Optional[str] = None
    line_color: Optional[str] = None
    headsign: Optional[str] = None

    # Origin and destination
    origin: JourneyStopResponse
    destination: JourneyStopResponse

    # Timing - NEW: actual departure/arrival timestamps
    departure: str  # ISO8601 datetime
    arrival: str    # ISO8601 datetime
    duration_minutes: int

    # Intermediate stops (only for transit segments)
    intermediate_stops: List[JourneyStopResponse] = []

    # Distance (mainly for walking segments)
    distance_meters: Optional[int] = None

    # Shape coordinates (normalized if requested)
    coordinates: List[JourneyCoordinate] = []

    # NEW: Suggested camera heading for 3D animations (degrees, 0-360)
    suggested_heading: float = 0.0

    # Occupancy info (GTFS-RT OccupancyStatus) - only for transit segments
    # 0=EMPTY, 1=MANY_SEATS, 2=FEW_SEATS, 3=STANDING_ONLY,
    # 4=CRUSHED, 5=FULL, 6=NOT_ACCEPTING, 7=NO_DATA, 8=NOT_BOARDABLE
    occupancy_status: Optional[int] = None
    occupancy_percentage: Optional[int] = None  # 0-100


class JourneyResponse(BaseModel):
    """Complete journey from origin to destination.

    A journey consists of one or more segments, which can be
    transit rides or walking transfers.

    NEW in RAPTOR: includes actual departure/arrival timestamps
    """
    # Timing - NEW: actual timestamps
    departure: str  # ISO8601 datetime
    arrival: str    # ISO8601 datetime

    # Summary
    duration_minutes: int
    transfers: int
    walking_minutes: int

    # Detailed segments
    segments: List[JourneySegmentResponse]


class JourneyAlertResponse(BaseModel):
    """An alert affecting routes in the journey."""
    id: str
    line_id: str
    line_name: str
    message: str
    severity: str  # "info", "warning", "error"
    active_from: Optional[str] = None  # ISO8601 datetime
    active_until: Optional[str] = None  # ISO8601 datetime


class RoutePlannerResponse(BaseModel):
    """Response from the route planner endpoint.

    NEW in RAPTOR:
    - `journeys` array replaces single `journey`
    - Contains Pareto-optimal alternatives (varying by time vs transfers)
    - Includes active alerts for routes used
    """
    success: bool
    message: Optional[str] = None

    # NEW: Array of Pareto-optimal journeys (replaces single journey)
    journeys: List[JourneyResponse] = []

    # NEW: Active alerts for routes used in journeys
    alerts: List[JourneyAlertResponse] = []


# =============================================================================
# LEGACY SCHEMAS - Kept for backwards compatibility during transition
# =============================================================================

class LegacyJourneySegmentResponse(BaseModel):
    """Legacy segment format (for backwards compatibility)."""
    type: str
    transport_mode: str  # Note: new format uses 'mode'

    line_id: Optional[str] = None
    line_name: Optional[str] = None
    line_color: Optional[str] = None
    headsign: Optional[str] = None

    origin: JourneyStopResponse
    destination: JourneyStopResponse
    intermediate_stops: List[JourneyStopResponse] = []
    duration_minutes: int
    distance_meters: Optional[int] = None
    coordinates: List[JourneyCoordinate] = []


class LegacyJourneyResponse(BaseModel):
    """Legacy journey format (for backwards compatibility)."""
    origin: JourneyStopResponse
    destination: JourneyStopResponse
    total_duration_minutes: int
    total_walking_minutes: int
    total_transit_minutes: int
    transfer_count: int
    segments: List[LegacyJourneySegmentResponse]


class LegacyRoutePlannerResponse(BaseModel):
    """Legacy route planner response (for backwards compatibility)."""
    success: bool
    message: Optional[str] = None
    journey: Optional[LegacyJourneyResponse] = None
    alternatives: List[LegacyJourneyResponse] = []
