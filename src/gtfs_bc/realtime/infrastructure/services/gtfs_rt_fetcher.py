import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from src.gtfs_bc.realtime.domain.entities import VehiclePosition, TripUpdate, StopTimeUpdate
from src.gtfs_bc.realtime.infrastructure.models import (
    VehiclePositionModel,
    TripUpdateModel,
    StopTimeUpdateModel,
    VehicleStatusEnum,
)

logger = logging.getLogger(__name__)


class GTFSRealtimeFetcher:
    """Service to fetch and store GTFS-RT data from Renfe."""

    # Renfe GTFS-RT endpoints
    VEHICLE_POSITIONS_URL = "https://gtfsrt.renfe.com/vehicle_positions.json"
    TRIP_UPDATES_URL = "https://gtfsrt.renfe.com/trip_updates.json"

    def __init__(self, db: Session):
        self.db = db

    async def fetch_and_store_vehicle_positions(self) -> int:
        """Fetch vehicle positions from Renfe API and store in database.

        Returns the number of vehicle positions updated.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.VEHICLE_POSITIONS_URL, timeout=30.0)
                response.raise_for_status()
                data = response.json()

            entities = data.get("entity", [])
            logger.info(f"Fetched {len(entities)} vehicle positions from Renfe")

            count = 0
            for entity in entities:
                try:
                    vp = VehiclePosition.from_gtfsrt_json(entity)
                    self._upsert_vehicle_position(vp)
                    count += 1
                except Exception as e:
                    logger.warning(f"Error processing vehicle position: {e}")

            self.db.commit()
            return count

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching vehicle positions: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching vehicle positions: {e}")
            raise

    def fetch_and_store_vehicle_positions_sync(self) -> int:
        """Synchronous version of fetch_and_store_vehicle_positions."""
        try:
            response = httpx.get(self.VEHICLE_POSITIONS_URL, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            entities = data.get("entity", [])
            logger.info(f"Fetched {len(entities)} vehicle positions from Renfe")

            count = 0
            for entity in entities:
                try:
                    vp = VehiclePosition.from_gtfsrt_json(entity)
                    self._upsert_vehicle_position(vp)
                    count += 1
                except Exception as e:
                    logger.warning(f"Error processing vehicle position: {e}")

            self.db.commit()
            return count

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching vehicle positions: {e}")
            raise

    def _upsert_vehicle_position(self, vp: VehiclePosition) -> None:
        """Insert or update a vehicle position."""
        status_enum = VehicleStatusEnum(vp.current_status.value)

        stmt = insert(VehiclePositionModel).values(
            vehicle_id=vp.vehicle_id,
            trip_id=vp.trip_id,
            latitude=vp.latitude,
            longitude=vp.longitude,
            current_status=status_enum,
            stop_id=vp.stop_id,
            label=vp.label,
            timestamp=vp.timestamp,
            updated_at=datetime.utcnow(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["vehicle_id"],
            set_={
                "trip_id": stmt.excluded.trip_id,
                "latitude": stmt.excluded.latitude,
                "longitude": stmt.excluded.longitude,
                "current_status": stmt.excluded.current_status,
                "stop_id": stmt.excluded.stop_id,
                "label": stmt.excluded.label,
                "timestamp": stmt.excluded.timestamp,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        self.db.execute(stmt)

    async def fetch_and_store_trip_updates(self) -> int:
        """Fetch trip updates from Renfe API and store in database.

        Returns the number of trip updates processed.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.TRIP_UPDATES_URL, timeout=30.0)
                response.raise_for_status()
                data = response.json()

            entities = data.get("entity", [])
            logger.info(f"Fetched {len(entities)} trip updates from Renfe")

            count = 0
            for entity in entities:
                try:
                    tu = TripUpdate.from_gtfsrt_json(entity)
                    self._upsert_trip_update(tu)
                    count += 1
                except Exception as e:
                    logger.warning(f"Error processing trip update: {e}")

            self.db.commit()
            return count

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching trip updates: {e}")
            raise

    def fetch_and_store_trip_updates_sync(self) -> int:
        """Synchronous version of fetch_and_store_trip_updates."""
        try:
            response = httpx.get(self.TRIP_UPDATES_URL, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            entities = data.get("entity", [])
            logger.info(f"Fetched {len(entities)} trip updates from Renfe")

            count = 0
            for entity in entities:
                try:
                    tu = TripUpdate.from_gtfsrt_json(entity)
                    self._upsert_trip_update(tu)
                    count += 1
                except Exception as e:
                    logger.warning(f"Error processing trip update: {e}")

            self.db.commit()
            return count

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching trip updates: {e}")
            raise

    def _upsert_trip_update(self, tu: TripUpdate) -> None:
        """Insert or update a trip update and its stop time updates."""
        # First, delete existing stop time updates for this trip
        self.db.query(StopTimeUpdateModel).filter(
            StopTimeUpdateModel.trip_id == tu.trip_id
        ).delete()

        # Upsert the trip update
        stmt = insert(TripUpdateModel).values(
            trip_id=tu.trip_id,
            delay=tu.delay,
            vehicle_id=tu.vehicle_id,
            wheelchair_accessible=tu.wheelchair_accessible,
            timestamp=tu.timestamp,
            updated_at=datetime.utcnow(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["trip_id"],
            set_={
                "delay": stmt.excluded.delay,
                "vehicle_id": stmt.excluded.vehicle_id,
                "wheelchair_accessible": stmt.excluded.wheelchair_accessible,
                "timestamp": stmt.excluded.timestamp,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        self.db.execute(stmt)

        # Insert stop time updates
        for stu in tu.stop_time_updates:
            stop_time_model = StopTimeUpdateModel(
                trip_id=tu.trip_id,
                stop_id=stu.stop_id,
                arrival_delay=stu.arrival_delay,
                arrival_time=stu.arrival_time,
                departure_delay=stu.departure_delay,
                departure_time=stu.departure_time,
            )
            self.db.add(stop_time_model)

    def fetch_all_sync(self) -> Dict[str, int]:
        """Fetch both vehicle positions and trip updates synchronously.

        Returns a dict with counts of each type.
        """
        vehicle_count = self.fetch_and_store_vehicle_positions_sync()
        trip_count = self.fetch_and_store_trip_updates_sync()
        return {
            "vehicle_positions": vehicle_count,
            "trip_updates": trip_count,
        }

    def get_vehicle_positions(
        self,
        stop_id: Optional[str] = None,
        trip_id: Optional[str] = None,
    ) -> List[VehiclePositionModel]:
        """Get vehicle positions with optional filters."""
        query = self.db.query(VehiclePositionModel)
        if stop_id:
            query = query.filter(VehiclePositionModel.stop_id == stop_id)
        if trip_id:
            query = query.filter(VehiclePositionModel.trip_id == trip_id)
        return query.all()

    def get_trip_updates(
        self,
        min_delay: Optional[int] = None,
        trip_id: Optional[str] = None,
    ) -> List[TripUpdateModel]:
        """Get trip updates with optional filters."""
        query = self.db.query(TripUpdateModel)
        if min_delay is not None:
            query = query.filter(TripUpdateModel.delay >= min_delay)
        if trip_id:
            query = query.filter(TripUpdateModel.trip_id == trip_id)
        return query.order_by(TripUpdateModel.delay.desc()).all()

    def get_delays_for_stop(self, stop_id: str) -> List[Dict[str, Any]]:
        """Get all delays for a specific stop.

        Returns list of dicts with trip_id, delay, arrival_time.
        """
        stop_time_updates = (
            self.db.query(StopTimeUpdateModel)
            .filter(StopTimeUpdateModel.stop_id == stop_id)
            .all()
        )
        result = []
        for stu in stop_time_updates:
            result.append({
                "trip_id": stu.trip_id,
                "stop_id": stu.stop_id,
                "arrival_delay": stu.arrival_delay,
                "arrival_time": stu.arrival_time,
                "departure_delay": stu.departure_delay,
                "departure_time": stu.departure_time,
            })
        return result
