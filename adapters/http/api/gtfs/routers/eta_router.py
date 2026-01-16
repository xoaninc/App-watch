from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from src.gtfs_bc.eta.infrastructure.services.eta_calculator import ETACalculator


router = APIRouter(prefix="/gtfs/eta", tags=["ETA Calculation"])


class ETAResponse(BaseModel):
    trip_id: str
    stop_id: str
    scheduled_arrival: datetime
    estimated_arrival: datetime
    delay_seconds: int
    delay_minutes: int
    is_delayed: bool
    is_on_time: bool
    confidence_level: str
    calculation_method: str
    vehicle_id: Optional[str]
    distance_to_stop_meters: Optional[float]
    current_stop_id: Optional[str]
    calculated_at: datetime


class StopETAResponse(BaseModel):
    stop_id: str
    stop_name: Optional[str]
    arrivals: List[ETAResponse]


@router.get("/trips/{trip_id}/stops/{stop_id}", response_model=ETAResponse)
def get_eta_for_trip_stop(
    trip_id: str,
    stop_id: str,
    db: Session = Depends(get_db),
):
    """Get ETA for a specific trip at a specific stop.

    Returns the estimated arrival time with confidence level and calculation method.
    """
    calculator = ETACalculator(db)
    eta = calculator.calculate_eta_for_stop(trip_id, stop_id)

    if not eta:
        raise HTTPException(
            status_code=404,
            detail=f"No ETA found for trip {trip_id} at stop {stop_id}"
        )

    return ETAResponse(
        trip_id=eta.trip_id,
        stop_id=eta.stop_id,
        scheduled_arrival=eta.scheduled_arrival,
        estimated_arrival=eta.estimated_arrival,
        delay_seconds=eta.delay_seconds,
        delay_minutes=eta.delay_minutes,
        is_delayed=eta.is_delayed,
        is_on_time=eta.is_on_time,
        confidence_level=eta.confidence_level.value,
        calculation_method=eta.calculation_method.value,
        vehicle_id=eta.vehicle_id,
        distance_to_stop_meters=eta.distance_to_stop_meters,
        current_stop_id=eta.current_stop_id,
        calculated_at=eta.calculated_at,
    )


@router.get("/stops/{stop_id}", response_model=List[ETAResponse])
def get_etas_for_stop(
    stop_id: str,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of arrivals"),
    db: Session = Depends(get_db),
):
    """Get ETAs for all upcoming arrivals at a stop.

    Returns a list of estimated arrivals sorted by time.
    """
    calculator = ETACalculator(db)
    etas = calculator.get_etas_for_stop(stop_id, limit=limit)

    if not etas:
        raise HTTPException(
            status_code=404,
            detail=f"No upcoming arrivals found for stop {stop_id}"
        )

    return [
        ETAResponse(
            trip_id=eta.trip_id,
            stop_id=eta.stop_id,
            scheduled_arrival=eta.scheduled_arrival,
            estimated_arrival=eta.estimated_arrival,
            delay_seconds=eta.delay_seconds,
            delay_minutes=eta.delay_minutes,
            is_delayed=eta.is_delayed,
            is_on_time=eta.is_on_time,
            confidence_level=eta.confidence_level.value,
            calculation_method=eta.calculation_method.value,
            vehicle_id=eta.vehicle_id,
            distance_to_stop_meters=eta.distance_to_stop_meters,
            current_stop_id=eta.current_stop_id,
            calculated_at=eta.calculated_at,
        )
        for eta in etas
    ]


@router.get("/vehicles/{vehicle_id}/stops/{stop_id}", response_model=ETAResponse)
def get_eta_for_vehicle(
    vehicle_id: str,
    stop_id: str,
    db: Session = Depends(get_db),
):
    """Get ETA for a specific vehicle arriving at a stop.

    Uses the vehicle's current position and trip to calculate ETA.
    """
    calculator = ETACalculator(db)
    eta = calculator.get_eta_for_vehicle(vehicle_id, stop_id)

    if not eta:
        raise HTTPException(
            status_code=404,
            detail=f"No ETA found for vehicle {vehicle_id} at stop {stop_id}"
        )

    return ETAResponse(
        trip_id=eta.trip_id,
        stop_id=eta.stop_id,
        scheduled_arrival=eta.scheduled_arrival,
        estimated_arrival=eta.estimated_arrival,
        delay_seconds=eta.delay_seconds,
        delay_minutes=eta.delay_minutes,
        is_delayed=eta.is_delayed,
        is_on_time=eta.is_on_time,
        confidence_level=eta.confidence_level.value,
        calculation_method=eta.calculation_method.value,
        vehicle_id=eta.vehicle_id,
        distance_to_stop_meters=eta.distance_to_stop_meters,
        current_stop_id=eta.current_stop_id,
        calculated_at=eta.calculated_at,
    )
