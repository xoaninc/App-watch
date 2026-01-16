import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.gtfs_bc.eta.domain.entities import ETAResult, ConfidenceLevel, CalculationMethod
from src.gtfs_bc.eta.domain.value_objects import GeoPoint, haversine_distance
from src.gtfs_bc.eta.infrastructure.models import (
    TrackSegmentModel,
    SegmentStatsModel,
    VehiclePositionHistoryModel,
)
from src.gtfs_bc.eta.infrastructure.models.segment_stats import (
    get_hour_range,
    get_day_type,
)
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.trip.infrastructure.models import TripModel
from src.gtfs_bc.stop_time.infrastructure.models import StopTimeModel
from src.gtfs_bc.route.infrastructure.models import RouteModel
from src.gtfs_bc.realtime.infrastructure.models import (
    VehiclePositionModel,
    TripUpdateModel,
    StopTimeUpdateModel,
)

logger = logging.getLogger(__name__)


class ETACalculator:
    """Service for calculating Estimated Time of Arrival."""

    # Average train speed in km/h when no historical data available
    DEFAULT_SPEED_KMH = 60.0

    def __init__(self, db: Session):
        self.db = db

    def calculate_eta_for_stop(
        self,
        trip_id: str,
        stop_id: str,
    ) -> Optional[ETAResult]:
        """Calculate ETA for a specific trip at a specific stop.

        Uses the best available data source:
        1. TripUpdate delay (highest confidence)
        2. Vehicle position calculation (medium confidence)
        3. Scheduled time only (low confidence)
        """
        # Get trip and stop time info
        stop_time = (
            self.db.query(StopTimeModel)
            .filter(
                StopTimeModel.trip_id == trip_id,
                StopTimeModel.stop_id == stop_id,
            )
            .first()
        )

        if not stop_time:
            return None

        # Get scheduled arrival time for today
        now = datetime.now()
        scheduled_arrival = self._parse_gtfs_time(stop_time.arrival_time, now.date())

        # Try method 1: Use TripUpdate delay
        trip_update = self.db.query(TripUpdateModel).filter(
            TripUpdateModel.trip_id == trip_id
        ).first()

        if trip_update:
            # Check for specific stop time update
            stop_time_update = (
                self.db.query(StopTimeUpdateModel)
                .filter(
                    StopTimeUpdateModel.trip_id == trip_id,
                    StopTimeUpdateModel.stop_id == stop_id,
                )
                .first()
            )

            if stop_time_update and stop_time_update.arrival_delay is not None:
                delay = stop_time_update.arrival_delay
                estimated = scheduled_arrival + timedelta(seconds=delay)
                return ETAResult(
                    trip_id=trip_id,
                    stop_id=stop_id,
                    scheduled_arrival=scheduled_arrival,
                    estimated_arrival=estimated,
                    delay_seconds=delay,
                    confidence_level=ConfidenceLevel.HIGH,
                    calculation_method=CalculationMethod.DELAY_REPORTED,
                    calculated_at=now,
                    vehicle_id=trip_update.vehicle_id,
                )
            elif trip_update.delay != 0:
                # Use overall trip delay
                delay = trip_update.delay
                estimated = scheduled_arrival + timedelta(seconds=delay)
                return ETAResult(
                    trip_id=trip_id,
                    stop_id=stop_id,
                    scheduled_arrival=scheduled_arrival,
                    estimated_arrival=estimated,
                    delay_seconds=delay,
                    confidence_level=ConfidenceLevel.HIGH,
                    calculation_method=CalculationMethod.DELAY_REPORTED,
                    calculated_at=now,
                    vehicle_id=trip_update.vehicle_id,
                )

        # Try method 2: Calculate from vehicle position
        vehicle_position = (
            self.db.query(VehiclePositionModel)
            .filter(VehiclePositionModel.trip_id == trip_id)
            .first()
        )

        if vehicle_position:
            eta_from_position = self._calculate_eta_from_position(
                trip_id=trip_id,
                stop_id=stop_id,
                vehicle_position=vehicle_position,
                scheduled_arrival=scheduled_arrival,
            )
            if eta_from_position:
                return eta_from_position

        # Method 3: Return scheduled time only
        return ETAResult(
            trip_id=trip_id,
            stop_id=stop_id,
            scheduled_arrival=scheduled_arrival,
            estimated_arrival=scheduled_arrival,
            delay_seconds=0,
            confidence_level=ConfidenceLevel.LOW,
            calculation_method=CalculationMethod.SCHEDULED,
            calculated_at=now,
        )

    def _calculate_eta_from_position(
        self,
        trip_id: str,
        stop_id: str,
        vehicle_position: VehiclePositionModel,
        scheduled_arrival: datetime,
    ) -> Optional[ETAResult]:
        """Calculate ETA based on current vehicle position."""
        now = datetime.now()

        # Get target stop coordinates
        target_stop = self.db.query(StopModel).filter(StopModel.id == stop_id).first()
        if not target_stop:
            return None

        # Get current position
        current_pos = GeoPoint(vehicle_position.latitude, vehicle_position.longitude)
        target_pos = GeoPoint(target_stop.lat, target_stop.lon)

        # Calculate straight-line distance (approximation)
        distance_meters = current_pos.distance_to(target_pos)

        # Get trip's route to find historical speed
        trip = self.db.query(TripModel).filter(TripModel.id == trip_id).first()
        avg_speed = self._get_average_speed_for_route(trip.route_id if trip else None)

        # Calculate estimated travel time
        speed_ms = (avg_speed * 1000) / 3600  # Convert km/h to m/s
        travel_time_seconds = distance_meters / speed_ms if speed_ms > 0 else 0

        # Add buffer for stops (rough estimate: 30 seconds per intermediate stop)
        intermediate_stops = self._count_intermediate_stops(
            trip_id, vehicle_position.stop_id, stop_id
        )
        stop_buffer = intermediate_stops * 30

        total_time_seconds = int(travel_time_seconds + stop_buffer)
        estimated_arrival = now + timedelta(seconds=total_time_seconds)

        # Calculate delay compared to schedule
        delay_seconds = int((estimated_arrival - scheduled_arrival).total_seconds())

        return ETAResult(
            trip_id=trip_id,
            stop_id=stop_id,
            scheduled_arrival=scheduled_arrival,
            estimated_arrival=estimated_arrival,
            delay_seconds=delay_seconds,
            confidence_level=ConfidenceLevel.MEDIUM,
            calculation_method=CalculationMethod.POSITION_BASED,
            calculated_at=now,
            vehicle_id=vehicle_position.vehicle_id,
            distance_to_stop_meters=distance_meters,
            current_stop_id=vehicle_position.stop_id,
        )

    def _get_average_speed_for_route(self, route_id: Optional[str]) -> float:
        """Get average speed for a route from historical data."""
        if not route_id:
            return self.DEFAULT_SPEED_KMH

        # Try to get from track segments
        segment = (
            self.db.query(TrackSegmentModel)
            .filter(
                TrackSegmentModel.route_id == route_id,
                TrackSegmentModel.avg_speed_kmh.isnot(None),
            )
            .first()
        )

        if segment and segment.avg_speed_kmh:
            return segment.avg_speed_kmh

        return self.DEFAULT_SPEED_KMH

    def _count_intermediate_stops(
        self,
        trip_id: str,
        current_stop_id: Optional[str],
        target_stop_id: str,
    ) -> int:
        """Count the number of stops between current position and target."""
        if not current_stop_id:
            return 0

        # Get stop sequences
        current_seq = (
            self.db.query(StopTimeModel.stop_sequence)
            .filter(
                StopTimeModel.trip_id == trip_id,
                StopTimeModel.stop_id == current_stop_id,
            )
            .scalar()
        )

        target_seq = (
            self.db.query(StopTimeModel.stop_sequence)
            .filter(
                StopTimeModel.trip_id == trip_id,
                StopTimeModel.stop_id == target_stop_id,
            )
            .scalar()
        )

        if current_seq is None or target_seq is None:
            return 0

        return max(0, target_seq - current_seq - 1)

    def _parse_gtfs_time(self, time_str: str, date: datetime.date) -> datetime:
        """Parse GTFS time string (HH:MM:SS) to datetime.

        GTFS times can be > 24:00:00 for trips past midnight.
        """
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        seconds = int(parts[2]) if len(parts) > 2 else 0

        # Handle times past midnight
        days_offset = hours // 24
        hours = hours % 24

        base_dt = datetime.combine(date, datetime.min.time())
        return base_dt + timedelta(days=days_offset, hours=hours, minutes=minutes, seconds=seconds)

    def get_etas_for_stop(
        self,
        stop_id: str,
        limit: int = 10,
    ) -> List[ETAResult]:
        """Get ETAs for all upcoming arrivals at a stop."""
        now = datetime.now()
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second

        # Get upcoming stop times at this stop
        stop_times = (
            self.db.query(StopTimeModel, TripModel)
            .join(TripModel, StopTimeModel.trip_id == TripModel.id)
            .filter(
                StopTimeModel.stop_id == stop_id,
                StopTimeModel.arrival_seconds >= current_seconds,
            )
            .order_by(StopTimeModel.arrival_seconds)
            .limit(limit)
            .all()
        )

        results = []
        for stop_time, trip in stop_times:
            eta = self.calculate_eta_for_stop(trip.id, stop_id)
            if eta:
                results.append(eta)

        return results

    def get_eta_for_vehicle(
        self,
        vehicle_id: str,
        stop_id: str,
    ) -> Optional[ETAResult]:
        """Get ETA for a specific vehicle arriving at a stop."""
        vehicle = (
            self.db.query(VehiclePositionModel)
            .filter(VehiclePositionModel.vehicle_id == vehicle_id)
            .first()
        )

        if not vehicle:
            return None

        return self.calculate_eta_for_stop(vehicle.trip_id, stop_id)
