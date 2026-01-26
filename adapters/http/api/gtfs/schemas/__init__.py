"""Centralized API schemas for GTFS endpoints."""

from .route_schemas import (
    RouteResponse,
    RouteFrequencyResponse,
    DayOperatingHours,
    RouteOperatingHoursResponse,
    ShapePointResponse,
    RouteShapeResponse,
)

from .stop_schemas import (
    StopResponse,
    RouteStopResponse,
    PlatformResponse,
    StopPlatformsResponse,
    CorrespondenceResponse,
    StopCorrespondencesResponse,
)

from .departure_schemas import (
    TrainPositionSchema,
    DepartureResponse,
    TripStopResponse,
    TripDetailResponse,
    AgencyResponse,
)

from .realtime_schemas import (
    PositionSchema,
    VehiclePositionResponse,
    TripUpdateResponse,
    StopDelayResponse,
    AlertEntityResponse,
    AlertResponse,
    FetchResponse,
    EstimatedPositionResponse,
    SchedulerStatusResponse,
    FrequencyPeriodResponse,
    RealtimeRouteFrequencyResponse,
    CurrentFrequencyResponse,
    CreateAlertRequest,
    CreateAlertResponse,
)

from .import_schemas import ImportStatusResponse

__all__ = [
    # Route schemas
    "RouteResponse",
    "RouteFrequencyResponse",
    "DayOperatingHours",
    "RouteOperatingHoursResponse",
    "ShapePointResponse",
    "RouteShapeResponse",
    # Stop schemas
    "StopResponse",
    "RouteStopResponse",
    "PlatformResponse",
    "StopPlatformsResponse",
    "CorrespondenceResponse",
    "StopCorrespondencesResponse",
    # Departure schemas
    "TrainPositionSchema",
    "DepartureResponse",
    "TripStopResponse",
    "TripDetailResponse",
    "AgencyResponse",
    # Realtime schemas
    "PositionSchema",
    "VehiclePositionResponse",
    "TripUpdateResponse",
    "StopDelayResponse",
    "AlertEntityResponse",
    "AlertResponse",
    "FetchResponse",
    "EstimatedPositionResponse",
    "SchedulerStatusResponse",
    "FrequencyPeriodResponse",
    "RealtimeRouteFrequencyResponse",
    "CurrentFrequencyResponse",
    "CreateAlertRequest",
    "CreateAlertResponse",
    # Import schemas
    "ImportStatusResponse",
]
