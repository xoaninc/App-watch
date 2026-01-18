# Models registry for Alembic autogenerate
# Import all SQLAlchemy models here so Alembic can detect them

# GTFS BC models
from src.gtfs_bc.agency.infrastructure.models import AgencyModel
from src.gtfs_bc.route.infrastructure.models import RouteModel
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.trip.infrastructure.models import TripModel
from src.gtfs_bc.stop_time.infrastructure.models import StopTimeModel
from src.gtfs_bc.calendar.infrastructure.models import CalendarModel, CalendarDateModel
from src.gtfs_bc.shape.infrastructure.models import ShapeModel, ShapePointModel
from src.gtfs_bc.feed.infrastructure.models import FeedImportModel
from src.gtfs_bc.stop_route_sequence.infrastructure.models import StopRouteSequenceModel

# GTFS-RT models
from src.gtfs_bc.realtime.infrastructure.models import (
    VehiclePositionModel,
    TripUpdateModel,
    StopTimeUpdateModel,
)

# ETA models
from src.gtfs_bc.eta.infrastructure.models import (
    TrackSegmentModel,
    SegmentStatsModel,
    VehiclePositionHistoryModel,
)

# Network models
from src.gtfs_bc.network.infrastructure.models import NetworkModel, NetworkProvinceModel

__all__ = [
    # GTFS BC
    "AgencyModel",
    "RouteModel",
    "StopModel",
    "TripModel",
    "StopTimeModel",
    "CalendarModel",
    "CalendarDateModel",
    "ShapeModel",
    "ShapePointModel",
    "FeedImportModel",
    "StopRouteSequenceModel",
    # GTFS-RT
    "VehiclePositionModel",
    "TripUpdateModel",
    "StopTimeUpdateModel",
    # ETA
    "TrackSegmentModel",
    "SegmentStatsModel",
    "VehiclePositionHistoryModel",
    # Network
    "NetworkModel",
    "NetworkProvinceModel",
]
