from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from src.gtfs_bc.realtime.infrastructure.services.gtfs_rt_fetcher import GTFSRealtimeFetcher


router = APIRouter(prefix="/gtfs/realtime", tags=["GTFS Realtime"])


# Response schemas
class PositionSchema(BaseModel):
    latitude: float
    longitude: float


class VehiclePositionResponse(BaseModel):
    vehicle_id: str
    trip_id: str
    position: PositionSchema
    current_status: str
    stop_id: Optional[str]
    label: Optional[str]
    timestamp: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TripUpdateResponse(BaseModel):
    trip_id: str
    delay: int
    delay_minutes: int
    is_delayed: bool
    vehicle_id: Optional[str]
    wheelchair_accessible: Optional[bool]
    timestamp: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class StopDelayResponse(BaseModel):
    trip_id: str
    stop_id: str
    arrival_delay: Optional[int]
    arrival_time: Optional[datetime]
    departure_delay: Optional[int]
    departure_time: Optional[datetime]


class FetchResponse(BaseModel):
    vehicle_positions: int
    trip_updates: int
    message: str


@router.post("/fetch", response_model=FetchResponse)
def fetch_realtime_data(db: Session = Depends(get_db)):
    """Fetch latest GTFS-RT data from Renfe API.

    This endpoint triggers a fetch of both vehicle positions and trip updates
    from Renfe's GTFS-RT API and stores them in the database.
    """
    fetcher = GTFSRealtimeFetcher(db)
    try:
        result = fetcher.fetch_all_sync()
        return FetchResponse(
            vehicle_positions=result["vehicle_positions"],
            trip_updates=result["trip_updates"],
            message="GTFS-RT data fetched and stored successfully",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching GTFS-RT data: {str(e)}")


@router.get("/vehicles", response_model=List[VehiclePositionResponse])
def get_vehicle_positions(
    stop_id: Optional[str] = Query(None, description="Filter by stop ID"),
    trip_id: Optional[str] = Query(None, description="Filter by trip ID"),
    db: Session = Depends(get_db),
):
    """Get current vehicle positions.

    Optionally filter by stop_id or trip_id.
    """
    fetcher = GTFSRealtimeFetcher(db)
    vehicles = fetcher.get_vehicle_positions(stop_id=stop_id, trip_id=trip_id)

    return [
        VehiclePositionResponse(
            vehicle_id=v.vehicle_id,
            trip_id=v.trip_id,
            position=PositionSchema(latitude=v.latitude, longitude=v.longitude),
            current_status=v.current_status.value,
            stop_id=v.stop_id,
            label=v.label,
            timestamp=v.timestamp,
            updated_at=v.updated_at,
        )
        for v in vehicles
    ]


@router.get("/delays", response_model=List[TripUpdateResponse])
def get_trip_delays(
    min_delay: Optional[int] = Query(None, description="Minimum delay in seconds"),
    trip_id: Optional[str] = Query(None, description="Filter by trip ID"),
    db: Session = Depends(get_db),
):
    """Get trip delays.

    Optionally filter by minimum delay or trip_id.
    Results are sorted by delay descending.
    """
    fetcher = GTFSRealtimeFetcher(db)
    updates = fetcher.get_trip_updates(min_delay=min_delay, trip_id=trip_id)

    return [
        TripUpdateResponse(
            trip_id=u.trip_id,
            delay=u.delay,
            delay_minutes=u.delay_minutes,
            is_delayed=u.is_delayed,
            vehicle_id=u.vehicle_id,
            wheelchair_accessible=u.wheelchair_accessible,
            timestamp=u.timestamp,
            updated_at=u.updated_at,
        )
        for u in updates
    ]


@router.get("/stops/{stop_id}/delays", response_model=List[StopDelayResponse])
def get_delays_for_stop(
    stop_id: str,
    db: Session = Depends(get_db),
):
    """Get all delays for a specific stop.

    Returns all trips that have delay information for this stop.
    """
    fetcher = GTFSRealtimeFetcher(db)
    delays = fetcher.get_delays_for_stop(stop_id)

    return [
        StopDelayResponse(
            trip_id=d["trip_id"],
            stop_id=d["stop_id"],
            arrival_delay=d["arrival_delay"],
            arrival_time=d["arrival_time"],
            departure_delay=d["departure_delay"],
            departure_time=d["departure_time"],
        )
        for d in delays
    ]


@router.get("/vehicles/{vehicle_id}", response_model=VehiclePositionResponse)
def get_vehicle_position(
    vehicle_id: str,
    db: Session = Depends(get_db),
):
    """Get position for a specific vehicle."""
    fetcher = GTFSRealtimeFetcher(db)
    vehicles = fetcher.get_vehicle_positions()
    vehicle = next((v for v in vehicles if v.vehicle_id == vehicle_id), None)

    if not vehicle:
        raise HTTPException(status_code=404, detail=f"Vehicle {vehicle_id} not found")

    return VehiclePositionResponse(
        vehicle_id=vehicle.vehicle_id,
        trip_id=vehicle.trip_id,
        position=PositionSchema(latitude=vehicle.latitude, longitude=vehicle.longitude),
        current_status=vehicle.current_status.value,
        stop_id=vehicle.stop_id,
        label=vehicle.label,
        timestamp=vehicle.timestamp,
        updated_at=vehicle.updated_at,
    )
