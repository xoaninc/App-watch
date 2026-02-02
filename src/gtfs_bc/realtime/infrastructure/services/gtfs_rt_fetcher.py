import logging
import re
import json
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
from core.config import settings

logger = logging.getLogger(__name__)


class GTFSRealtimeFetcher:
    """Service to fetch and store GTFS-RT data from Renfe."""

    # Renfe GTFS-RT endpoints (JSON format)
    VEHICLE_POSITIONS_URL = "https://gtfsrt.renfe.com/vehicle_positions.json"
    TRIP_UPDATES_URL = "https://gtfsrt.renfe.com/trip_updates.json"
    ALERTS_URL = "https://gtfsrt.renfe.com/alerts.json"

    # Prefix for Renfe stop IDs to match static GTFS data in BD
    RENFE_PREFIX = "RENFE_"

    # Mapping for stop IDs that need to be translated to different ones
    # RT visor may return old/different codes than static GTFS
    STOP_ID_MAPPING = {
        "5222": "16403",  # Avilés-CIM → Avilés (C3 Asturias)
    }

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
        """Add RENFE_ prefix to stop_id, applying any ID mappings first."""
        if not stop_id:
            return stop_id
        # Apply mapping if exists (e.g., 5222 → 16403)
        mapped_id = self.STOP_ID_MAPPING.get(stop_id, stop_id)
        return self._add_prefix(mapped_id)

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
        # NOTE: trip_id must NOT have prefix to match static GTFS trips table
        stop_id = self._add_prefix(vp.stop_id)
        vehicle_id = self._add_prefix(vp.vehicle_id)
        trip_id = vp.trip_id  # Keep original trip_id WITHOUT prefix

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
        # NOTE: trip_id must NOT have prefix to match static GTFS trips table
        trip_id = tu.trip_id  # Keep original trip_id WITHOUT prefix
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
        """Insert or update an alert with AI enrichment."""
        # Add RENFE_ prefix to alert_id for consistency with other operators
        alert_id = self._add_prefix(alert.alert_id)

        # Check if alert already exists and has AI analysis
        existing_alert = self.db.query(AlertModel).filter(
            AlertModel.alert_id == alert_id
        ).first()
        
        # Only run AI if: (1) new alert, or (2) description changed
        should_enrich = False
        if not existing_alert:
            should_enrich = True
            logger.info(f"[AlertAI] New alert {alert_id}, will enrich with AI")
        elif existing_alert.description_text != alert.description_text:
            should_enrich = True
            logger.info(f"[AlertAI] Alert {alert_id} text changed, will re-enrich")
        
        # AI enrichment
        ai_severity = None
        ai_status = None
        ai_summary = None
        ai_affected_segments = None
        ai_processed_at = None
        
        if should_enrich and settings.GROQ_API_KEY:
            try:
                from src.gtfs_bc.realtime.infrastructure.services.ai_alert_classifier import AIAlertClassifier
                
                classifier = AIAlertClassifier(settings)
                analysis = classifier.analyze_single_alert(
                    alert_id=alert_id,
                    header_text=alert.header_text or "",
                    description_text=alert.description_text or ""
                )
                
                ai_severity = analysis.severity
                ai_status = analysis.status
                ai_summary = analysis.reason  # Use AI-generated summary
                ai_affected_segments = json.dumps(analysis.affected_segments) if analysis.affected_segments else None
                ai_processed_at = datetime.utcnow()
                
                logger.info(f"[AlertAI] {alert_id}: {ai_status} / {ai_severity} - {ai_summary}")
                
            except Exception as e:
                logger.error(f"[AlertAI] Error enriching alert {alert_id}: {e}")
        elif existing_alert:
            # Preserve existing AI analysis
            ai_severity = existing_alert.ai_severity
            ai_status = existing_alert.ai_status
            ai_summary = existing_alert.ai_summary
            ai_affected_segments = existing_alert.ai_affected_segments
            ai_processed_at = existing_alert.ai_processed_at

        # Delete existing alert entities for this alert
        self.db.query(AlertEntityModel).filter(
            AlertEntityModel.alert_id == alert_id
        ).delete()

        # Map domain enums to DB enums
        cause_enum = AlertCauseEnum(alert.cause.value)
        effect_enum = AlertEffectEnum(alert.effect.value)

        # Upsert the alert with AI enrichment
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
            ai_severity=ai_severity,
            ai_status=ai_status,
            ai_summary=ai_summary,
            ai_affected_segments=ai_affected_segments,
            ai_processed_at=ai_processed_at,
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
                "ai_severity": stmt.excluded.ai_severity,
                "ai_status": stmt.excluded.ai_status,
                "ai_summary": stmt.excluded.ai_summary,
                "ai_affected_segments": stmt.excluded.ai_affected_segments,
                "ai_processed_at": stmt.excluded.ai_processed_at,
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

    def _fetch_platforms_from_visor(self) -> int:
        """Fetch platform data from Renfe's web visor for stations with missing platforms.

        The GTFS-RT feed doesn't include platforms for some stations (e.g., María Zambrano).
        The web visor at tiempo-real.renfe.com provides this data for trains that are
        close to arriving.

        This method:
        1. Finds stop_time_updates without platform info
        2. Queries the visor API for those stations
        3. Updates platforms when available

        Returns the number of platforms fetched from visor.
        """
        from sqlalchemy import func

        # Get stations with stop_time_updates that don't have platform
        # Group by stop_id to avoid querying the same station multiple times
        stations_needing_platform = (
            self.db.query(StopTimeUpdateModel.stop_id)
            .filter(StopTimeUpdateModel.platform.is_(None))
            .distinct()
            .all()
        )

        if not stations_needing_platform:
            return 0

        count = 0
        visor_base_url = "https://tiempo-real.renfe.com/renfe-json-cutter/write/salidas/estacion"

        for (stop_id,) in stations_needing_platform:
            # Extract the numeric stop code (remove RENFE_ prefix if present)
            stop_code = stop_id.replace("RENFE_", "") if stop_id.startswith("RENFE_") else stop_id

            try:
                response = httpx.get(
                    f"{visor_base_url}/{stop_code}.json",
                    timeout=10.0,
                    headers={"User-Agent": "RenfeServer/1.0"}
                )
                if response.status_code != 200:
                    continue

                data = response.json()
                salidas = data.get("estacion", {}).get("salidas", [])

                for salida in salidas:
                    via = salida.get("via")
                    if not via:
                        continue

                    trip_id_raw = salida.get("tripId")
                    if not trip_id_raw:
                        continue

                    # Add RENFE_ prefix to trip_id
                    trip_id = self._add_prefix(trip_id_raw)

                    # Update stop_time_update with platform
                    updated = (
                        self.db.query(StopTimeUpdateModel)
                        .filter(StopTimeUpdateModel.trip_id == trip_id)
                        .filter(StopTimeUpdateModel.stop_id == stop_id)
                        .filter(StopTimeUpdateModel.platform.is_(None))
                        .update({"platform": str(via)}, synchronize_session=False)
                    )

                    if updated > 0:
                        count += updated

                        # Also record in platform_history for future predictions
                        linea = salida.get("linea", "")
                        destino = salida.get("destinoNombre", "Unknown")
                        today = date.today()
                        now = datetime.utcnow()

                        stmt = insert(PlatformHistoryModel).values(
                            stop_id=stop_id,
                            route_short_name=linea,
                            headsign=destino,
                            platform=str(via),
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

            except httpx.HTTPError as e:
                logger.debug(f"Error fetching visor data for {stop_code}: {e}")
            except Exception as e:
                logger.warning(f"Error processing visor data for {stop_code}: {e}")

        if count > 0:
            self.db.commit()
            logger.info(f"Fetched {count} platforms from visor web")

        return count

    def _log_stations_needing_manual_platforms(self) -> None:
        """Log stations that have departures but no platform data.

        Creates/updates a JSON file with stations that need manual platform assignment.
        This helps identify stations where Renfe doesn't provide platform info.
        """
        import json
        import os
        from sqlalchemy import func, text

        try:
            # Find Renfe stops with stop_time_updates but no platform and no history
            sql = text("""
                WITH stops_without_platform AS (
                    SELECT DISTINCT stu.stop_id
                    FROM gtfs_rt_stop_time_updates stu
                    WHERE stu.stop_id LIKE 'RENFE_%'
                      AND stu.platform IS NULL
                ),
                stops_with_history AS (
                    SELECT DISTINCT stop_id
                    FROM gtfs_rt_platform_history
                    WHERE stop_id LIKE 'RENFE_%'
                      AND count >= 3
                )
                SELECT swp.stop_id
                FROM stops_without_platform swp
                LEFT JOIN stops_with_history swh ON swp.stop_id = swh.stop_id
                WHERE swh.stop_id IS NULL
            """)

            result = self.db.execute(sql)
            stops_needing_platforms = [r[0] for r in result.fetchall()]

            if not stops_needing_platforms:
                return

            # Load existing file or create new
            filepath = "data/revision_manual_vias.json"
            os.makedirs("data", exist_ok=True)

            existing_data = {}
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        existing_data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    existing_data = {}

            # Update with new stops
            updated = False
            from src.gtfs_bc.stop.infrastructure.models import StopModel

            for stop_id in stops_needing_platforms:
                if stop_id not in existing_data:
                    # Get stop name from database
                    stop = self.db.query(StopModel).filter(StopModel.id == stop_id).first()
                    stop_name = stop.name if stop else None
                    in_gtfs_static = stop is not None

                    existing_data[stop_id] = {
                        "name": stop_name or "NO EXISTE EN GTFS ESTÁTICO",
                        "in_gtfs_static": in_gtfs_static,
                        "first_seen": datetime.utcnow().isoformat(),
                        "status": "pending",
                        "suggested_platform": None,
                        "notes": "Esta estación no existe en nuestro GTFS estático" if not in_gtfs_static else ""
                    }
                    updated = True

                    if in_gtfs_static:
                        logger.info(f"Added {stop_id} ({stop_name}) to revision_manual_vias.json - needs platform")
                    else:
                        logger.warning(f"Added {stop_id} to revision_manual_vias.json - NOT IN GTFS STATIC")

            if updated:
                with open(filepath, "w") as f:
                    json.dump(existing_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.warning(f"Error logging stations needing manual platforms: {e}")

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

        # Delete alerts without end date that haven't been updated in 12 hours
        # These are likely alerts that Renfe stopped sending but didn't set an end date
        sql_alerts_stale = text("""
            DELETE FROM gtfs_rt_alerts
            WHERE active_period_end IS NULL
              AND updated_at < NOW() - INTERVAL '12 hours'
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

        # Fetch platforms from visor web for stations missing in GTFS-RT
        platform_from_visor = self._fetch_platforms_from_visor()

        # Predict platforms from historical data for remaining stop_time_updates
        platform_predictions = self._predict_platforms_from_history()

        # Log stations that still need manual platform assignment
        self._log_stations_needing_manual_platforms()

        return {
            "vehicle_positions": vehicle_count,
            "trip_updates": trip_count,
            "alerts": alerts_count,
            "platform_correlations": platform_correlations,
            "platform_from_visor": platform_from_visor,
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
                    # (e.g., Madrid C4 vs Bilbao C4). GTFS route_id format has network code.
                    # Could be: 10T0036C5 (old format) or RENFE_30T0001C1 (new format)
                    if network_id:
                        query = query.filter(
                            (AlertEntityModel.route_id.like(f"{network_id}%")) |
                            (AlertEntityModel.route_id.like(f"%{network_id}%"))
                        )
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
