"""Centralized API schemas for GTFS endpoints."""

import logging

logger = logging.getLogger(__name__)

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
    WalkingShapePoint,
    AccessResponse,
    StopAccessesResponse,
    VestibuleResponse,
    StopVestibulesResponse,
)

from .departure_schemas import (
    TrainPositionSchema,
    DepartureResponse,
    CompactDepartureResponse,
    CompactDeparturesWrapper,
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

from .routing_schemas import (
    JourneyStopResponse,
    JourneyCoordinate,
    JourneySegmentResponse,
    JourneyResponse,
    JourneyAlertResponse,
    RoutePlannerResponse,
)

# Re-export JourneyAlertResponse for direct import
__all_routing__ = [
    "JourneyStopResponse",
    "JourneyCoordinate",
    "JourneySegmentResponse",
    "JourneyResponse",
    "JourneyAlertResponse",
    "RoutePlannerResponse",
]

# Required schemas that must exist for the API to function
REQUIRED_SCHEMAS = [
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
    "AccessResponse",
    "StopAccessesResponse",
    "VestibuleResponse",
    "StopVestibulesResponse",
    # Departure schemas
    "TrainPositionSchema",
    "DepartureResponse",
    "CompactDepartureResponse",
    "CompactDeparturesWrapper",
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
    # Routing schemas
    "JourneyStopResponse",
    "JourneyCoordinate",
    "JourneySegmentResponse",
    "JourneyResponse",
    "JourneyAlertResponse",
    "RoutePlannerResponse",
]

# Export all required schemas
__all__ = REQUIRED_SCHEMAS


def validate_schemas() -> bool:
    """Validate that all required schemas are available.

    This function checks that all schemas listed in REQUIRED_SCHEMAS
    are properly imported and accessible. Called at module load time.

    Returns:
        True if all schemas are valid

    Raises:
        ImportError: If any required schema is missing
    """
    import sys
    current_module = sys.modules[__name__]

    missing = []
    for schema_name in REQUIRED_SCHEMAS:
        if not hasattr(current_module, schema_name):
            missing.append(schema_name)

    if missing:
        error_msg = f"Missing required schemas: {', '.join(missing)}"
        logger.error(error_msg)
        raise ImportError(error_msg)

    logger.debug(f"Schema validation passed: {len(REQUIRED_SCHEMAS)} schemas loaded")
    return True


# Validate schemas at import time
validate_schemas()
