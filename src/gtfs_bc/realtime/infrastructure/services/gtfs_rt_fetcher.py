import logging
import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from src.gtfs_bc.realtime.domain.entities import VehiclePosition, TripUpdate, StopTimeUpdate, Alert
from src.gtfs_bc.realtime.infrastructure.models import (
    VehiclePositionModel,
    TripUpdateModel,
    StopTimeUpdateModel,
    VehicleStatusEnum,
    AlertModel,
    AlertEntityModel,
    AlertCauseEnum,
    AlertEffectEnum,
    PlatformHistoryModel,
)
from src.gtfs_bc.trip.infrastructure.models import TripModel
from src.gtfs_bc.route.infrastructure.models import RouteModel

logger = logging.getLogger(__name__)


class GTFSRealtimeFetcher:
    """Service to fetch and store GTFS-RT data from Renfe."""

    # Renfe GTFS-RT endpoints (JSON format)
    VEHICLE_POSITIONS_URL = "https://gtfsrt.renfe.com/vehicle_positions.json"
    TRIP_UPDATES_URL = "https://gtfsrt.renfe.com/trip_updates.json"
    ALERTS_URL = "https://gtfsrt.renfe.com/alerts.json"

    # Prefix for Renfe stop IDs to match static GTFS data in BD
    RENFE_PREFIX = "RENFE_"

    def __init__(self, db: Session):
        self.db = db

    def _add_prefix(self, id_value: str) -> str:
        """Add RENFE_ prefix to any ID to match static GTFS data in BD."""
        if not id_value:
            return id_value
        if id_value.startswith(self.RENFE_PREFIX):
            return id_value
        return f"{self.RENFE_PREFIX}{id_value}"

    def _add_stop_prefix(self, stop_id: str) -> str:
        """Add RENFE_ prefix to stop_id (alias for _add_prefix)."""
        return self._add_prefix(stop_id)

    # Madrid Cercanías routes that need variant detection based on destination
    # C4 and C8 don't exist as services - only C4a/C4b and C8a/C8b do
    # See: scripts/GTFS_IMPORT_CHANGES.md for documentation

    # Destinations that indicate variant "b" (if not matched, default to "a")
    ROUTE_B_DESTINATIONS = {
        'C4': ['colmenar', 'viejo'],           # C4b: Colmenar Viejo
        'C8': ['cercedilla'],                   # C8b: Cercedilla (Cotos es C9)
    }

    @staticmethod
    def _determine_route_variant(short_name: str, headsign: Optional[str]) -> str:
        """Determine the correct route variant (a/b) based on destination.

        Madrid C4 and C8 lines split into variants:
        - C4a: Alcobendas-San Sebastián de los Reyes
        - C4b: Colmenar Viejo
        - C8a: Santa María de la Alameda-Peguerinos / El Escorial
        - C8b: Cercedilla / Cotos

        Returns the correct variant (C4a, C4b, C8a, C8b) or original if not C4/C8.
        """
        if short_name not in GTFSRealtimeFetcher.ROUTE_B_DESTINATIONS:
            return short_name

        # Check if headsign matches any "b" variant destination
        if headsign:
            headsign_lower = headsign.lower()
            for dest_keyword in GTFSRealtimeFetcher.ROUTE_B_DESTINATIONS[short_name]:
                if dest_keyword in headsign_lower:
                    return f"{short_name}b"

        # Default to "a" variant
        return f"{short_name}a"

    @staticmethod
    def _extract_route_short_name(route_id: Optional[str], headsign: Optional[str] = None) -> Optional[str]:
        """Extract route short_name from GTFS-RT route_id.

        GTFS-RT route_id formats:
        - {nucleo}T{code}C{line} (e.g., 30T0024C5 -> C5) for Cercanías
        - {nucleo}T{code}T{line} (e.g., 31T0009T1 -> T1) for Tranvía/other lines
        - {nucleo}T{code}R{line} (e.g., 51T0025R2 -> R2) for Rodalies Catalunya
        Returns the line name like C1, C5, C8a, T1, R2, etc.

        For C4 and C8 (Madrid), determines variant based on headsign:
        - C4 + "Colmenar" → C4b, otherwise C4a
        - C8 + "Cercedilla" → C8b, otherwise C8a (Cotos es C9)
        """
        if not route_id:
            return None
        # Match pattern ending with C, T, or R followed by line number/letter
        match = re.search(r'([CTR])([0-9]+[a-z]?)$', route_id, re.IGNORECASE)
        if match:
            short_name = f"{match.group(1).upper()}{match.group(2)}"
            # Determine variant for C4/C8 based on headsign
            return GTFSRealtimeFetcher._determine_route_variant(short_name, headsign)
        return None

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

        # Add RENFE_ prefix to IDs to match static GTFS data and other operators
        stop_id = self._add_prefix(vp.stop_id)
        vehicle_id = self._add_prefix(vp.vehicle_id)
        trip_id = self._add_prefix(vp.trip_id)

        stmt = insert(VehiclePositionModel).values(
            vehicle_id=vehicle_id,
            trip_id=trip_id,
            latitude=vp.latitude,
            longitude=vp.longitude,
            current_status=status_enum,
            stop_id=stop_id,
            label=vp.label,
            platform=vp.platform,
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
                "platform": stmt.excluded.platform,
                "timestamp": stmt.excluded.timestamp,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        self.db.execute(stmt)

        # Record platform history when train is at or approaching a station
        # Include INCOMING_AT for networks like Cádiz that don't report STOPPED_AT
        if vp.current_status.value in ("STOPPED_AT", "INCOMING_AT") and vp.stop_id and vp.platform:
            self._record_platform_history(vp)

    def _record_platform_history(self, vp: VehiclePosition) -> None:
        """Record platform usage for learning predictions (daily data).

        Uses UPSERT (ON CONFLICT DO UPDATE) to avoid race conditions.
        """
        try:
            # Extract route short name from label (e.g., "C7-21811-PLATF.(1)" -> "C7")
            route_short_name = None
            if vp.label:
                parts = vp.label.split("-")
                if parts:
                    route_short_name = parts[0]

            if not route_short_name:
                return

            # Get headsign from trip (ensure never None)
            # Add RENFE_ prefix to match static GTFS data in BD
            trip_id = self._add_prefix(vp.trip_id)
            trip = self.db.query(TripModel).filter(TripModel.id == trip_id).first()
            headsign = (trip.headsign if trip and trip.headsign else None) or "Unknown"

            # Determine variant for C4/C8 based on headsign
            route_short_name = self._determine_route_variant(route_short_name, headsign)

            # Add RENFE_ prefix to stop_id to match static GTFS data
            stop_id = self._add_stop_prefix(vp.stop_id)
            today = date.today()
            now = datetime.utcnow()

            # Use UPSERT to avoid race conditions
            from sqlalchemy.dialects.postgresql import insert
            stmt = insert(PlatformHistoryModel).values(
                stop_id=stop_id,
                route_short_name=route_short_name,
                headsign=headsign,
                platform=vp.platform,
                count=1,
                observation_date=today,
                last_seen=now,
            )
            stmt = stmt.on_conflict_do_update(
                constraint='uq_platform_history_business_key',
                set_={
                    'count': PlatformHistoryModel.count + 1,
                    'last_seen': now,
                }
            )
            self.db.execute(stmt)
        except Exception as e:
            logger.warning(f"Error recording platform history: {e}")

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
        # Add RENFE_ prefix to IDs to match static GTFS data and other operators
        trip_id = self._add_prefix(tu.trip_id)
        vehicle_id = self._add_prefix(tu.vehicle_id)

        # First, delete existing stop time updates for this trip
        self.db.query(StopTimeUpdateModel).filter(
            StopTimeUpdateModel.trip_id == trip_id
        ).delete()

        # Upsert the trip update
        stmt = insert(TripUpdateModel).values(
            trip_id=trip_id,
            delay=tu.delay,
            vehicle_id=vehicle_id,
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
                trip_id=trip_id,
                stop_id=self._add_stop_prefix(stu.stop_id),  # Add RENFE_ prefix
                arrival_delay=stu.arrival_delay,
                arrival_time=stu.arrival_time,
                departure_delay=stu.departure_delay,
                departure_time=stu.departure_time,
            )
            self.db.add(stop_time_model)

    def fetch_and_store_alerts_sync(self) -> int:
        """Fetch alerts from Renfe API and store in database.

        Returns the number of alerts updated.
        """
        try:
            response = httpx.get(self.ALERTS_URL, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            entities = data.get("entity", [])
            logger.info(f"Fetched {len(entities)} alerts from Renfe")

            count = 0
            for entity in entities:
                try:
                    alert = Alert.from_gtfsrt_json(entity)
                    self._upsert_alert(alert)
                    count += 1
                except Exception as e:
                    logger.warning(f"Error processing alert: {e}")

            self.db.commit()
            return count

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching alerts: {e}")
            raise

    def _upsert_alert(self, alert: Alert) -> None:
        """Insert or update an alert."""
        # Add RENFE_ prefix to alert_id for consistency with other operators
        alert_id = self._add_prefix(alert.alert_id)

        # Delete existing alert entities for this alert
        self.db.query(AlertEntityModel).filter(
            AlertEntityModel.alert_id == alert_id
        ).delete()

        # Map domain enums to DB enums
        cause_enum = AlertCauseEnum(alert.cause.value)
        effect_enum = AlertEffectEnum(alert.effect.value)

        # Upsert the alert
        stmt = insert(AlertModel).values(
            alert_id=alert_id,
            cause=cause_enum,
            effect=effect_enum,
            header_text=alert.header_text,
            description_text=alert.description_text,
            url=alert.url,
            active_period_start=alert.active_period_start,
            active_period_end=alert.active_period_end,
            timestamp=alert.timestamp,
            updated_at=datetime.utcnow(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["alert_id"],
            set_={
                "cause": stmt.excluded.cause,
                "effect": stmt.excluded.effect,
                "header_text": stmt.excluded.header_text,
                "description_text": stmt.excluded.description_text,
                "url": stmt.excluded.url,
                "active_period_start": stmt.excluded.active_period_start,
                "active_period_end": stmt.excluded.active_period_end,
                "timestamp": stmt.excluded.timestamp,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        self.db.execute(stmt)

        # Insert informed entities with RENFE_ prefix for consistency
        for ie in alert.informed_entities:
            route_id = self._add_prefix(ie.route_id)
            trip_id = self._add_prefix(ie.trip_id)

            entity_model = AlertEntityModel(
                alert_id=alert_id,
                route_id=route_id,
                route_short_name=self._extract_route_short_name(ie.route_id),  # Use original for parsing
                stop_id=self._add_stop_prefix(ie.stop_id) if ie.stop_id else None,
                trip_id=trip_id,
                agency_id=ie.agency_id,
                route_type=ie.route_type,
            )
            self.db.add(entity_model)

    def _correlate_platforms_from_vehicle_positions(self) -> int:
        """Correlate platforms from vehicle_positions to stop_time_updates.

        Renfe's trip_updates don't include platform info, but vehicle_positions do.
        This method updates stop_time_updates with platform info from matching
        vehicle_positions for the same trip_id and stop_id.

        Uses a single bulk UPDATE query for efficiency.

        Returns the number of stop_time_updates updated.
        """
        from sqlalchemy import text

        # Use a single UPDATE ... FROM query (PostgreSQL syntax)
        # This is much faster than running individual queries for each vehicle position
        sql = text("""
            UPDATE gtfs_rt_stop_time_updates stu
            SET platform = vp.platform
            FROM gtfs_rt_vehicle_positions vp
            WHERE stu.trip_id = vp.trip_id
              AND stu.stop_id = vp.stop_id
              AND stu.platform IS NULL
              AND vp.platform IS NOT NULL
              AND vp.stop_id IS NOT NULL
        """)

        result = self.db.execute(sql)
        count = result.rowcount

        if count > 0:
            self.db.commit()
            logger.info(f"Correlated {count} stop_time_updates with platform from vehicle_positions")

        return count

    def _predict_platforms_from_history(self) -> int:
        """Predict platforms for stop_time_updates using historical data.

        Uses platform_history to predict the most likely platform for each
        stop_id + route combination based on historical observations.

        Returns the number of stop_time_updates updated with predictions.
        """
        from sqlalchemy import func

        # Get stop_time_updates without platform
        stus_without_platform = (
            self.db.query(StopTimeUpdateModel)
            .filter(StopTimeUpdateModel.platform.is_(None))
            .all()
        )

        if not stus_without_platform:
            return 0

        count = 0
        for stu in stus_without_platform:
            # Get the route_short_name from the trip
            trip = self.db.query(TripModel).filter(TripModel.id == stu.trip_id).first()
            if not trip:
                continue

            route_short_name = self._extract_route_short_name(trip.route_id)
            if not route_short_name:
                continue

            # Find the most common platform for this stop_id + route_short_name
            most_common = (
                self.db.query(
                    PlatformHistoryModel.platform,
                    func.sum(PlatformHistoryModel.count).label('total')
                )
                .filter(PlatformHistoryModel.stop_id == stu.stop_id)
                .filter(PlatformHistoryModel.route_short_name == route_short_name)
                .group_by(PlatformHistoryModel.platform)
                .order_by(func.sum(PlatformHistoryModel.count).desc())
                .first()
            )

            if most_common and most_common.total >= 3:  # Minimum 3 observations
                stu.platform = most_common.platform
                count += 1

        if count > 0:
            self.db.commit()
            logger.info(f"Predicted {count} platforms from historical data")

        return count

    def _cleanup_stale_realtime_data(self) -> dict:
        """Clean up stale GTFS-RT data that's no longer being updated.

        Removes:
        - trip_updates and stop_time_updates for trips > 2 hours old
        - alerts with active_period_end in the past
        - alerts without active_period_end that haven't been updated in 24 hours

        Returns dict with counts of deleted records.
        """
        from sqlalchemy import text

        # Delete trip_updates older than 2 hours (trips that ended)
        # This also cascades to stop_time_updates via foreign key
        sql_trip_updates = text("""
            DELETE FROM gtfs_rt_trip_updates
            WHERE updated_at < NOW() - INTERVAL '2 hours'
        """)
        result_tu = self.db.execute(sql_trip_updates)
        tu_count = result_tu.rowcount

        # Delete orphaned stop_time_updates (shouldn't exist due to cascade, but cleanup anyway)
        sql_stu = text("""
            DELETE FROM gtfs_rt_stop_time_updates
            WHERE trip_id NOT IN (SELECT trip_id FROM gtfs_rt_trip_updates)
        """)
        result_stu = self.db.execute(sql_stu)
        stu_count = result_stu.rowcount

        # Delete alerts that have expired (active_period_end in the past)
        sql_alerts_expired = text("""
            DELETE FROM gtfs_rt_alerts
            WHERE active_period_end IS NOT NULL
              AND active_period_end < NOW()
        """)
        result_alerts_exp = self.db.execute(sql_alerts_expired)
        alerts_expired_count = result_alerts_exp.rowcount

        # Delete alerts without end date that haven't been updated in 24 hours
        # These are likely alerts that Renfe stopped sending but didn't set an end date
        sql_alerts_stale = text("""
            DELETE FROM gtfs_rt_alerts
            WHERE active_period_end IS NULL
              AND updated_at < NOW() - INTERVAL '24 hours'
              AND source != 'manual'
        """)
        result_alerts_stale = self.db.execute(sql_alerts_stale)
        alerts_stale_count = result_alerts_stale.rowcount

        if tu_count > 0 or stu_count > 0 or alerts_expired_count > 0 or alerts_stale_count > 0:
            self.db.commit()
            logger.info(
                f"Cleaned up {tu_count} trip_updates, {stu_count} stop_time_updates, "
                f"{alerts_expired_count} expired alerts, {alerts_stale_count} stale alerts"
            )

        return {
            "trip_updates_deleted": tu_count,
            "stop_time_updates_deleted": stu_count,
            "alerts_expired_deleted": alerts_expired_count,
            "alerts_stale_deleted": alerts_stale_count,
        }

    def fetch_all_sync(self) -> Dict[str, int]:
        """Fetch vehicle positions, trip updates, and alerts synchronously.

        Returns a dict with counts of each type.
        """
        # Clean up stale data first
        self._cleanup_stale_realtime_data()

        vehicle_count = self.fetch_and_store_vehicle_positions_sync()
        trip_count = self.fetch_and_store_trip_updates_sync()
        alerts_count = self.fetch_and_store_alerts_sync()

        # Correlate platforms from vehicle_positions to stop_time_updates
        platform_correlations = self._correlate_platforms_from_vehicle_positions()

        # Predict platforms from historical data for remaining stop_time_updates
        platform_predictions = self._predict_platforms_from_history()

        return {
            "vehicle_positions": vehicle_count,
            "trip_updates": trip_count,
            "alerts": alerts_count,
            "platform_correlations": platform_correlations,
            "platform_predictions": platform_predictions,
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

    def get_alerts(
        self,
        route_id: Optional[str] = None,
        stop_id: Optional[str] = None,
        active_only: bool = True,
    ) -> List[AlertModel]:
        """Get alerts with optional filters.

        Args:
            route_id: Filter by affected route (supports both our format RENFE_C4a_67
                      and original GTFS format 10T0036C5)
            stop_id: Filter by affected stop
            active_only: Only return currently active alerts (default True)
        """
        query = self.db.query(AlertModel)

        if active_only:
            now = datetime.utcnow()
            query = query.filter(
                (AlertModel.active_period_start.is_(None)) | (AlertModel.active_period_start <= now),
                (AlertModel.active_period_end.is_(None)) | (AlertModel.active_period_end >= now),
            )

        if route_id or stop_id:
            # Join with entities if filtering
            query = query.join(AlertModel.informed_entities)
            if route_id:
                # Check if route_id is in our format (e.g., RENFE_C4a_67)
                # Alerts store the original GTFS route_id (e.g., 10T0036C5) but also
                # store route_short_name (e.g., C4a). Map our format to short_name.
                route_short_name = None
                network_id = None
                if route_id.startswith(('RENFE_', 'FGC_', 'EUSKOTREN_', 'METRO_BILBAO_', 'TMB_')):
                    # Look up the route to get its short_name and network_id
                    route = self.db.query(RouteModel).filter(RouteModel.id == route_id).first()
                    if route:
                        route_short_name = route.short_name
                        network_id = route.network_id

                if route_short_name:
                    # Search by route_short_name (matches C4a, C5, etc.)
                    query = query.filter(AlertEntityModel.route_short_name == route_short_name)
                    # Also filter by network to avoid mixing alerts from different networks
                    # (e.g., Madrid C4 vs Bilbao C4). GTFS route_id starts with network code.
                    if network_id:
                        # GTFS route_id format: {network}T{code}C{line} (e.g., 10T0036C5)
                        query = query.filter(AlertEntityModel.route_id.like(f"{network_id}%"))
                else:
                    # Fallback: search by original route_id
                    query = query.filter(AlertEntityModel.route_id == route_id)
            if stop_id:
                query = query.filter(AlertEntityModel.stop_id == stop_id)

        return query.distinct().all()

    def get_alerts_for_route(self, route_id: str) -> List[AlertModel]:
        """Get all active alerts for a specific route."""
        return self.get_alerts(route_id=route_id, active_only=True)

    def get_alerts_for_stop(self, stop_id: str) -> List[AlertModel]:
        """Get all active alerts for a specific stop."""
        return self.get_alerts(stop_id=stop_id, active_only=True)
