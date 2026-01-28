"""Multi-operator GTFS-RT fetcher.

Fetches GTFS-RT data from multiple operators with different formats:
- Protobuf: Metro Bilbao, Euskotren (standard GTFS-RT)
- JSON: Renfe, FGC (custom JSON format)
- Custom API: TMB Barcelona (iMetro API)

Usage:
    from src.gtfs_bc.realtime.infrastructure.services.multi_operator_fetcher import (
        MultiOperatorFetcher
    )

    fetcher = MultiOperatorFetcher(db)
    results = fetcher.fetch_all_operators()
"""

import json
import logging
from datetime import datetime, timedelta, date
import re
from typing import Dict, List, Optional, Any

import httpx
from google.transit import gtfs_realtime_pb2
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from src.gtfs_bc.realtime.domain.entities import (
    VehiclePosition, TripUpdate, StopTimeUpdate, Alert, AlertEntity,
    AlertCause, AlertEffect
)
from src.gtfs_bc.realtime.domain.entities.vehicle_position import VehicleStatus
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

logger = logging.getLogger(__name__)


# TMB API credentials (from environment variables)
import os
TMB_APP_ID = os.getenv('TMB_APP_ID', '')
TMB_APP_KEY = os.getenv('TMB_APP_KEY', '')

# Operator configurations with GTFS-RT endpoints
GTFS_RT_OPERATORS = {
    'metro_bilbao': {
        'name': 'Metro Bilbao',
        'format': 'protobuf',
        'vehicle_positions': 'https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfsrt_metro_bilbao_vehicle_positions.pb',
        'trip_updates': 'https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfsrt_metro_bilbao_trip_updates.pb',
        'alerts': 'https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfsrt_metro_bilbao_alerts.pb',
        'stop_id_prefix': 'METRO_BILBAO_',
        'trip_id_prefix': 'METRO_BILBAO_',
    },
    'euskotren': {
        'name': 'Euskotren',
        'format': 'protobuf',
        'vehicle_positions': 'https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfsrt_euskotren_vehicle_positions.pb',
        'trip_updates': 'https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfsrt_euskotren_trip_updates.pb',
        'alerts': 'https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfsrt_euskotren_alerts.pb',
        'stop_id_prefix': 'EUSKOTREN_',
        'trip_id_prefix': 'EUSKOTREN_',
    },
    'tmb_metro': {
        'name': 'TMB Metro Barcelona',
        'format': 'tmb_api',
        'stations_url': 'https://api.tmb.cat/v1/imetro/estacions',
        'stop_id_prefix': 'TMB_METRO_1.',  # Format: TMB_METRO_1.{station_code}
        'trip_id_prefix': 'TMB_METRO_1.',
    },
    'fgc': {
        'name': 'FGC',
        'format': 'protobuf',
        'vehicle_positions': 'https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/vehicle-positions-gtfs_realtime/files/d286964db2d107ecdb1344bf02f7b27b',
        'trip_updates': 'https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/trip-updates-gtfs_realtime/files/735985017f62fd33b2fe46e31ce53829',
        'alerts': 'https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/alerts-gtfs_realtime/files/02f92ddc6d2712788903e54468542936',
        'stop_id_prefix': 'FGC_',
        'trip_id_prefix': 'FGC_',
    },
    'metrovalencia': {
        'name': 'Metrovalencia',
        'format': 'metrovalencia_api',
        'stations_url': 'https://valencia.opendatasoft.com/api/explore/v2.1/catalog/datasets/fgv-estacions-estaciones/exports/json',
        'realtime_url': 'https://geoportal.valencia.es/geoportal-services/api/v1/salidas-metro.json',
        'stop_id_prefix': 'METROVALENCIA_',
        'trip_id_prefix': 'METROVALENCIA_',
    },
}


class MultiOperatorFetcher:
    """Fetches GTFS-RT data from multiple operators."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _extract_platform_from_stop_id(stop_id: str, operator: str = 'fgc', direction_id: Optional[int] = None) -> Optional[str]:
        """Extract platform number from stop_id based on operator format.

        Different operators encode platform differently:
        - FGC: stop_ids like PC1, PC2, AB1 where trailing digit is platform
        - Euskotren: stop_ids like 'ES:Euskotren:Quay:2621_Plataforma_Q1:' where Q1/Q2 is platform
        - Metro Bilbao: inferred from direction_id (1 or 2)

        Returns the platform number or None if not found.
        """
        if not stop_id:
            return None

        # Euskotren format: ES:Euskotren:Quay:2621_Plataforma_Q1:
        if operator == 'euskotren' or '_Plataforma_Q' in stop_id:
            match = re.search(r'_Plataforma_Q(\d+)', stop_id)
            if match:
                return match.group(1)
            return None

        # Metro Bilbao: infer platform from direction_id
        if operator == 'metro_bilbao':
            if direction_id is not None and direction_id in (1, 2):
                return str(direction_id)
            return None

        # FGC format: trailing digits (e.g., PC2 -> 2, AB1 -> 1)
        match = re.search(r'(\d+)$', stop_id)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_route_short_name(label: Optional[str], trip_id: Optional[str]) -> Optional[str]:
        """Extract route short name from vehicle label or trip_id.

        FGC format: label might contain line name like "L6", "S1", "R5"
        """
        if label:
            # Try to find line pattern in label (L1-L12, S1-S4, R5-R60)
            match = re.search(r'\b([LSR]\d{1,2})\b', label, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None

    def _record_platform_history(
        self,
        stop_id: str,
        platform: str,
        route_short_name: Optional[str],
        headsign: Optional[str],
        operator_prefix: str
    ) -> None:
        """Record platform usage for learning predictions (daily data).

        Uses UPSERT (ON CONFLICT DO UPDATE) to avoid race conditions.
        """
        try:
            if not route_short_name:
                return

            headsign = headsign or "Unknown"
            today = date.today()
            now = datetime.utcnow()

            # Use UPSERT to avoid race conditions
            from sqlalchemy.dialects.postgresql import insert
            stmt = insert(PlatformHistoryModel).values(
                stop_id=stop_id,
                route_short_name=route_short_name,
                headsign=headsign,
                platform=platform,
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
            logger.warning(f"Error recording platform history for {operator_prefix}: {e}")

    async def fetch_operator(self, operator_code: str) -> Dict[str, int]:
        """Fetch all GTFS-RT data for a specific operator.

        Returns dict with counts of each type fetched.
        """
        if operator_code not in GTFS_RT_OPERATORS:
            logger.error(f"Unknown operator: {operator_code}")
            return {'error': f'Unknown operator: {operator_code}'}

        config = GTFS_RT_OPERATORS[operator_code]
        logger.info(f"Fetching GTFS-RT for {config['name']}...")

        results = {
            'operator': operator_code,
            'vehicle_positions': 0,
            'trip_updates': 0,
            'alerts': 0,
        }

        try:
            if config['format'] == 'protobuf':
                results['vehicle_positions'] = await self._fetch_protobuf_vehicle_positions(config, operator_code)
                results['trip_updates'] = await self._fetch_protobuf_trip_updates(config, operator_code)
                results['alerts'] = await self._fetch_protobuf_alerts(config)
            elif config['format'] == 'json':
                results['vehicle_positions'] = await self._fetch_json_vehicle_positions(config)
                results['trip_updates'] = await self._fetch_json_trip_updates(config)
                results['alerts'] = await self._fetch_json_alerts(config)
            elif config['format'] == 'tmb_api':
                results['trip_updates'] = await self._fetch_tmb_predictions(config)
            elif config['format'] == 'metrovalencia_api':
                results['trip_updates'] = await self._fetch_metrovalencia_predictions(config)

            logger.info(f"Fetched from {config['name']}: "
                       f"{results['vehicle_positions']} positions, "
                       f"{results['trip_updates']} trip updates, "
                       f"{results['alerts']} alerts")

        except Exception as e:
            logger.error(f"Error fetching {config['name']}: {e}")
            results['error'] = str(e)

        return results

    def fetch_operator_sync(self, operator_code: str) -> Dict[str, int]:
        """Synchronous version of fetch_operator."""
        if operator_code not in GTFS_RT_OPERATORS:
            logger.error(f"Unknown operator: {operator_code}")
            return {'error': f'Unknown operator: {operator_code}'}

        config = GTFS_RT_OPERATORS[operator_code]
        logger.info(f"Fetching GTFS-RT for {config['name']}...")

        results = {
            'operator': operator_code,
            'vehicle_positions': 0,
            'trip_updates': 0,
            'alerts': 0,
        }

        try:
            if config['format'] == 'protobuf':
                results['vehicle_positions'] = self._fetch_protobuf_vehicle_positions_sync(config, operator_code)
                results['trip_updates'] = self._fetch_protobuf_trip_updates_sync(config, operator_code)
                results['alerts'] = self._fetch_protobuf_alerts_sync(config)
            elif config['format'] == 'json':
                results['vehicle_positions'] = self._fetch_json_vehicle_positions_sync(config)
                results['trip_updates'] = self._fetch_json_trip_updates_sync(config)
                results['alerts'] = self._fetch_json_alerts_sync(config)
            elif config['format'] == 'tmb_api':
                results['trip_updates'] = self._fetch_tmb_predictions_sync(config)
            elif config['format'] == 'metrovalencia_api':
                results['trip_updates'] = self._fetch_metrovalencia_predictions_sync(config)

            logger.info(f"Fetched from {config['name']}: "
                       f"{results['vehicle_positions']} positions, "
                       f"{results['trip_updates']} trip updates, "
                       f"{results['alerts']} alerts")

        except Exception as e:
            logger.error(f"Error fetching {config['name']}: {e}")
            results['error'] = str(e)

        return results

    async def fetch_all_operators(self) -> List[Dict[str, int]]:
        """Fetch GTFS-RT from all configured operators."""
        results = []
        for operator_code in GTFS_RT_OPERATORS:
            result = await self.fetch_operator(operator_code)
            results.append(result)
        return results

    def fetch_all_operators_sync(self, parallel: bool = True) -> List[Dict[str, int]]:
        """Synchronous version of fetch_all_operators.

        Args:
            parallel: If True, fetch from all operators in parallel using threads.
        """
        if not parallel:
            # Sequential fetching (legacy behavior)
            results = []
            for operator_code in GTFS_RT_OPERATORS:
                result = self.fetch_operator_sync(operator_code)
                results.append(result)
            return results

        # Parallel fetching using ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

        # Timeout per operator in seconds
        OPERATOR_TIMEOUT = 45

        results = []
        with ThreadPoolExecutor(max_workers=len(GTFS_RT_OPERATORS)) as executor:
            # Submit all fetch tasks
            future_to_operator = {
                executor.submit(self._fetch_operator_in_new_session, op): op
                for op in GTFS_RT_OPERATORS
            }

            # Collect results as they complete (with timeout)
            for future in as_completed(future_to_operator, timeout=OPERATOR_TIMEOUT * len(GTFS_RT_OPERATORS)):
                operator = future_to_operator[future]
                try:
                    result = future.result(timeout=OPERATOR_TIMEOUT)
                    results.append(result)
                except FuturesTimeoutError:
                    logger.error(f"Timeout fetching {operator} after {OPERATOR_TIMEOUT}s")
                    results.append({'operator': operator, 'error': f'timeout after {OPERATOR_TIMEOUT}s'})
                except Exception as e:
                    logger.error(f"Error fetching {operator} in parallel: {e}")
                    results.append({'operator': operator, 'error': str(e)})

        return results

    def _fetch_operator_in_new_session(self, operator_code: str) -> Dict[str, int]:
        """Fetch operator data using a new database session (for thread safety)."""
        from core.database import SessionLocal

        db = SessionLocal()
        try:
            # Create a new fetcher instance with the new session
            fetcher = MultiOperatorFetcher(db)
            return fetcher.fetch_operator_sync(operator_code)
        finally:
            db.close()

    # -------------------------------------------------------------------------
    # Protobuf fetchers (Metro Bilbao, Euskotren)
    # -------------------------------------------------------------------------

    async def _fetch_protobuf_vehicle_positions(self, config: dict, operator_code: str = 'fgc') -> int:
        """Fetch vehicle positions from protobuf endpoint."""
        url = config.get('vehicle_positions')
        if not url:
            return 0

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            return self._parse_protobuf_vehicle_positions(response.content, config, operator_code)

    def _fetch_protobuf_vehicle_positions_sync(self, config: dict, operator_code: str = 'fgc') -> int:
        """Sync version of _fetch_protobuf_vehicle_positions."""
        url = config.get('vehicle_positions')
        if not url:
            return 0

        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return self._parse_protobuf_vehicle_positions(response.content, config, operator_code)

    def _parse_protobuf_vehicle_positions(self, data: bytes, config: dict, operator_code: str = 'fgc') -> int:
        """Parse protobuf vehicle positions and store in DB."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(data)

        prefix = config.get('stop_id_prefix', '')
        trip_prefix = config.get('trip_id_prefix', '')
        count = 0

        for entity in feed.entity:
            if not entity.HasField('vehicle'):
                continue

            vp = entity.vehicle
            vehicle_id = f"{prefix}{vp.vehicle.id}" if vp.vehicle.id else f"{prefix}{entity.id}"

            # Map status
            status_map = {
                gtfs_realtime_pb2.VehiclePosition.INCOMING_AT: VehicleStatusEnum.INCOMING_AT,
                gtfs_realtime_pb2.VehiclePosition.STOPPED_AT: VehicleStatusEnum.STOPPED_AT,
                gtfs_realtime_pb2.VehiclePosition.IN_TRANSIT_TO: VehicleStatusEnum.IN_TRANSIT_TO,
            }
            status = status_map.get(vp.current_status, VehicleStatusEnum.IN_TRANSIT_TO)

            # Build stop_id with prefix
            raw_stop_id = vp.stop_id if vp.stop_id else None
            stop_id = f"{prefix}{raw_stop_id}" if raw_stop_id else None
            trip_id = f"{trip_prefix}{vp.trip.trip_id}" if vp.trip.trip_id else None

            # Get direction_id for platform inference (Metro Bilbao)
            direction_id = vp.trip.direction_id if vp.trip.direction_id else None

            # Extract platform from stop_id based on operator format
            platform = self._extract_platform_from_stop_id(raw_stop_id, operator_code, direction_id) if raw_stop_id else None

            # Get label and extract route_short_name
            label = vp.vehicle.label if vp.vehicle.label else None
            route_short_name = self._extract_route_short_name(label, trip_id)

            # Get headsign from trip descriptor if available
            headsign = vp.trip.route_id if vp.trip.route_id else None

            try:
                stmt = insert(VehiclePositionModel).values(
                    vehicle_id=vehicle_id,
                    trip_id=trip_id,
                    latitude=vp.position.latitude if vp.HasField('position') else 0.0,
                    longitude=vp.position.longitude if vp.HasField('position') else 0.0,
                    current_status=status,
                    stop_id=stop_id,
                    label=label,
                    platform=platform,
                    timestamp=datetime.fromtimestamp(vp.timestamp) if vp.timestamp else datetime.utcnow(),
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
                if status in (VehicleStatusEnum.STOPPED_AT, VehicleStatusEnum.INCOMING_AT) and stop_id and platform:
                    self._record_platform_history(
                        stop_id=stop_id,
                        platform=platform,
                        route_short_name=route_short_name,
                        headsign=headsign,
                        operator_prefix=prefix
                    )

                count += 1
            except Exception as e:
                logger.warning(f"Error inserting vehicle position: {e}")

        self.db.commit()
        return count

    async def _fetch_protobuf_trip_updates(self, config: dict, operator_code: str = 'fgc') -> int:
        """Fetch trip updates from protobuf endpoint."""
        url = config.get('trip_updates')
        if not url:
            return 0

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            return self._parse_protobuf_trip_updates(response.content, config, operator_code)

    def _fetch_protobuf_trip_updates_sync(self, config: dict, operator_code: str = 'fgc') -> int:
        """Sync version of _fetch_protobuf_trip_updates."""
        url = config.get('trip_updates')
        if not url:
            return 0

        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return self._parse_protobuf_trip_updates(response.content, config, operator_code)

    def _parse_protobuf_trip_updates(self, data: bytes, config: dict, operator_code: str = 'fgc') -> int:
        """Parse protobuf trip updates and store in DB."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(data)

        prefix = config.get('stop_id_prefix', '')
        trip_prefix = config.get('trip_id_prefix', '')
        count = 0

        for entity in feed.entity:
            if not entity.HasField('trip_update'):
                continue

            tu = entity.trip_update
            trip_id = f"{trip_prefix}{tu.trip.trip_id}" if tu.trip.trip_id else None

            if not trip_id:
                continue

            # Get direction_id for platform inference (Metro Bilbao)
            direction_id = tu.trip.direction_id if tu.trip.direction_id else None

            # Delete existing stop time updates for this trip
            self.db.query(StopTimeUpdateModel).filter(
                StopTimeUpdateModel.trip_id == trip_id
            ).delete()

            # Calculate overall delay from first stop time update
            delay = 0
            if tu.stop_time_update:
                first_stu = tu.stop_time_update[0]
                if first_stu.HasField('arrival'):
                    delay = first_stu.arrival.delay
                elif first_stu.HasField('departure'):
                    delay = first_stu.departure.delay

            try:
                stmt = insert(TripUpdateModel).values(
                    trip_id=trip_id,
                    delay=delay,
                    vehicle_id=f"{prefix}{tu.vehicle.id}" if tu.vehicle.id else None,
                    wheelchair_accessible=None,
                    timestamp=datetime.fromtimestamp(tu.timestamp) if tu.timestamp else datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["trip_id"],
                    set_={
                        "delay": stmt.excluded.delay,
                        "vehicle_id": stmt.excluded.vehicle_id,
                        "timestamp": stmt.excluded.timestamp,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                self.db.execute(stmt)

                # Insert stop time updates
                for stu in tu.stop_time_update:
                    raw_stop_id = stu.stop_id if stu.stop_id else None
                    stop_id = f"{prefix}{raw_stop_id}" if raw_stop_id else None

                    # Extract platform from stop_id based on operator format
                    platform = self._extract_platform_from_stop_id(raw_stop_id, operator_code, direction_id) if raw_stop_id else None

                    arrival_delay = stu.arrival.delay if stu.HasField('arrival') else None
                    arrival_time = datetime.fromtimestamp(stu.arrival.time) if stu.HasField('arrival') and stu.arrival.time else None
                    departure_delay = stu.departure.delay if stu.HasField('departure') else None
                    departure_time = datetime.fromtimestamp(stu.departure.time) if stu.HasField('departure') and stu.departure.time else None

                    stop_time_model = StopTimeUpdateModel(
                        trip_id=trip_id,
                        stop_id=stop_id,
                        arrival_delay=arrival_delay,
                        arrival_time=arrival_time,
                        departure_delay=departure_delay,
                        departure_time=departure_time,
                        platform=platform,
                    )
                    self.db.add(stop_time_model)

                count += 1
            except Exception as e:
                logger.warning(f"Error inserting trip update: {e}")

        self.db.commit()
        return count

    async def _fetch_protobuf_alerts(self, config: dict) -> int:
        """Fetch alerts from protobuf endpoint."""
        url = config.get('alerts')
        if not url:
            return 0

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            return self._parse_protobuf_alerts(response.content, config)

    def _fetch_protobuf_alerts_sync(self, config: dict) -> int:
        """Sync version of _fetch_protobuf_alerts."""
        url = config.get('alerts')
        if not url:
            return 0

        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return self._parse_protobuf_alerts(response.content, config)

    def _parse_protobuf_alerts(self, data: bytes, config: dict) -> int:
        """Parse protobuf alerts and store in DB."""
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(data)

        prefix = config.get('stop_id_prefix', '')
        count = 0

        # Map protobuf cause/effect to our enums
        cause_map = {
            gtfs_realtime_pb2.Alert.UNKNOWN_CAUSE: AlertCauseEnum.UNKNOWN_CAUSE,
            gtfs_realtime_pb2.Alert.OTHER_CAUSE: AlertCauseEnum.OTHER_CAUSE,
            gtfs_realtime_pb2.Alert.TECHNICAL_PROBLEM: AlertCauseEnum.TECHNICAL_PROBLEM,
            gtfs_realtime_pb2.Alert.STRIKE: AlertCauseEnum.STRIKE,
            gtfs_realtime_pb2.Alert.DEMONSTRATION: AlertCauseEnum.DEMONSTRATION,
            gtfs_realtime_pb2.Alert.ACCIDENT: AlertCauseEnum.ACCIDENT,
            gtfs_realtime_pb2.Alert.HOLIDAY: AlertCauseEnum.HOLIDAY,
            gtfs_realtime_pb2.Alert.WEATHER: AlertCauseEnum.WEATHER,
            gtfs_realtime_pb2.Alert.MAINTENANCE: AlertCauseEnum.MAINTENANCE,
            gtfs_realtime_pb2.Alert.CONSTRUCTION: AlertCauseEnum.CONSTRUCTION,
            gtfs_realtime_pb2.Alert.POLICE_ACTIVITY: AlertCauseEnum.POLICE_ACTIVITY,
            gtfs_realtime_pb2.Alert.MEDICAL_EMERGENCY: AlertCauseEnum.MEDICAL_EMERGENCY,
        }

        effect_map = {
            gtfs_realtime_pb2.Alert.NO_SERVICE: AlertEffectEnum.NO_SERVICE,
            gtfs_realtime_pb2.Alert.REDUCED_SERVICE: AlertEffectEnum.REDUCED_SERVICE,
            gtfs_realtime_pb2.Alert.SIGNIFICANT_DELAYS: AlertEffectEnum.SIGNIFICANT_DELAYS,
            gtfs_realtime_pb2.Alert.DETOUR: AlertEffectEnum.DETOUR,
            gtfs_realtime_pb2.Alert.ADDITIONAL_SERVICE: AlertEffectEnum.ADDITIONAL_SERVICE,
            gtfs_realtime_pb2.Alert.MODIFIED_SERVICE: AlertEffectEnum.MODIFIED_SERVICE,
            gtfs_realtime_pb2.Alert.OTHER_EFFECT: AlertEffectEnum.OTHER_EFFECT,
            gtfs_realtime_pb2.Alert.UNKNOWN_EFFECT: AlertEffectEnum.UNKNOWN_EFFECT,
            gtfs_realtime_pb2.Alert.STOP_MOVED: AlertEffectEnum.STOP_MOVED,
        }

        for entity in feed.entity:
            if not entity.HasField('alert'):
                continue

            alert = entity.alert
            alert_id = f"{prefix}{entity.id}"

            # Delete existing entities for this alert
            self.db.query(AlertEntityModel).filter(
                AlertEntityModel.alert_id == alert_id
            ).delete()

            # Get header and description text
            header_text = None
            description_text = None
            url_text = None

            if alert.header_text.translation:
                header_text = alert.header_text.translation[0].text
            if alert.description_text.translation:
                description_text = alert.description_text.translation[0].text
            if alert.url.translation:
                url_text = alert.url.translation[0].text

            # Get active period
            active_start = None
            active_end = None
            if alert.active_period:
                period = alert.active_period[0]
                if period.start:
                    active_start = datetime.fromtimestamp(period.start)
                if period.end:
                    active_end = datetime.fromtimestamp(period.end)

            cause = cause_map.get(alert.cause, AlertCauseEnum.UNKNOWN_CAUSE)
            effect = effect_map.get(alert.effect, AlertEffectEnum.UNKNOWN_EFFECT)

            try:
                stmt = insert(AlertModel).values(
                    alert_id=alert_id,
                    cause=cause,
                    effect=effect,
                    header_text=header_text,
                    description_text=description_text,
                    url=url_text,
                    active_period_start=active_start,
                    active_period_end=active_end,
                    timestamp=datetime.utcnow(),
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

                # Insert informed entities
                for ie in alert.informed_entity:
                    route_id = f"{prefix}{ie.route_id}" if ie.route_id else None
                    stop_id = f"{prefix}{ie.stop_id}" if ie.stop_id else None
                    trip_id = f"{prefix}{ie.trip.trip_id}" if ie.trip.trip_id else None

                    entity_model = AlertEntityModel(
                        alert_id=alert_id,
                        route_id=route_id,
                        route_short_name=None,  # Not available in protobuf
                        stop_id=stop_id,
                        trip_id=trip_id,
                        agency_id=ie.agency_id if ie.agency_id else None,
                        route_type=ie.route_type if ie.route_type else None,
                    )
                    self.db.add(entity_model)

                count += 1
            except Exception as e:
                logger.warning(f"Error inserting alert: {e}")

        self.db.commit()
        return count

    # -------------------------------------------------------------------------
    # JSON fetchers (FGC)
    # -------------------------------------------------------------------------

    async def _fetch_json_vehicle_positions(self, config: dict) -> int:
        """Fetch vehicle positions from JSON endpoint (FGC format)."""
        url = config.get('vehicle_positions')
        if not url:
            return 0

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return self._parse_json_vehicle_positions(response.json(), config)

    def _fetch_json_vehicle_positions_sync(self, config: dict) -> int:
        """Sync version of _fetch_json_vehicle_positions."""
        url = config.get('vehicle_positions')
        if not url:
            return 0

        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        return self._parse_json_vehicle_positions(response.json(), config)

    def _parse_json_vehicle_positions(self, data: List[dict], config: dict) -> int:
        """Parse FGC JSON vehicle positions and store in DB."""
        prefix = config.get('stop_id_prefix', '')
        trip_prefix = config.get('trip_id_prefix', '')
        count = 0

        for item in data:
            try:
                # FGC format: codi_tren, latitud, longitud, linia, etc.
                vehicle_id = f"{prefix}{item.get('codi_tren', item.get('id', ''))}"
                trip_id = f"{trip_prefix}{item.get('codi_servei', '')}" if item.get('codi_servei') else None

                lat = item.get('latitud', item.get('lat', 0))
                lon = item.get('longitud', item.get('lon', 0))

                stmt = insert(VehiclePositionModel).values(
                    vehicle_id=vehicle_id,
                    trip_id=trip_id,
                    latitude=float(lat) if lat else 0.0,
                    longitude=float(lon) if lon else 0.0,
                    current_status=VehicleStatusEnum.IN_TRANSIT_TO,
                    stop_id=None,
                    label=item.get('linia', item.get('nom_linia', '')),
                    platform=None,
                    timestamp=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["vehicle_id"],
                    set_={
                        "trip_id": stmt.excluded.trip_id,
                        "latitude": stmt.excluded.latitude,
                        "longitude": stmt.excluded.longitude,
                        "current_status": stmt.excluded.current_status,
                        "label": stmt.excluded.label,
                        "timestamp": stmt.excluded.timestamp,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                self.db.execute(stmt)
                count += 1
            except Exception as e:
                logger.warning(f"Error inserting FGC vehicle position: {e}")

        self.db.commit()
        return count

    async def _fetch_json_trip_updates(self, config: dict) -> int:
        """Fetch trip updates from JSON endpoint (FGC format)."""
        url = config.get('trip_updates')
        if not url:
            return 0

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                return self._parse_json_trip_updates(response.json(), config)
        except Exception as e:
            logger.warning(f"Error fetching FGC trip updates: {e}")
            return 0

    def _fetch_json_trip_updates_sync(self, config: dict) -> int:
        """Sync version of _fetch_json_trip_updates."""
        url = config.get('trip_updates')
        if not url:
            return 0

        try:
            response = httpx.get(url, timeout=30.0)
            response.raise_for_status()
            return self._parse_json_trip_updates(response.json(), config)
        except Exception as e:
            logger.warning(f"Error fetching FGC trip updates: {e}")
            return 0

    def _parse_json_trip_updates(self, data: List[dict], config: dict) -> int:
        """Parse FGC JSON trip updates and store in DB."""
        # FGC trip updates format may vary - implement based on actual data
        # For now, return 0 if not implemented
        logger.info("FGC trip updates parsing not fully implemented yet")
        return 0

    async def _fetch_json_alerts(self, config: dict) -> int:
        """Fetch alerts from JSON endpoint (FGC format)."""
        url = config.get('alerts')
        if not url:
            return 0

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                return self._parse_json_alerts(response.json(), config)
        except Exception as e:
            logger.warning(f"Error fetching FGC alerts: {e}")
            return 0

    def _fetch_json_alerts_sync(self, config: dict) -> int:
        """Sync version of _fetch_json_alerts."""
        url = config.get('alerts')
        if not url:
            return 0

        try:
            response = httpx.get(url, timeout=30.0)
            response.raise_for_status()
            return self._parse_json_alerts(response.json(), config)
        except Exception as e:
            logger.warning(f"Error fetching FGC alerts: {e}")
            return 0

    def _parse_json_alerts(self, data: List[dict], config: dict) -> int:
        """Parse FGC JSON alerts and store in DB."""
        prefix = config.get('stop_id_prefix', '')
        count = 0

        for item in data:
            try:
                alert_id = f"{prefix}{item.get('id', item.get('codi', ''))}"

                header = item.get('titol', item.get('header', ''))
                description = item.get('descripcio', item.get('description', ''))

                stmt = insert(AlertModel).values(
                    alert_id=alert_id,
                    cause=AlertCauseEnum.OTHER_CAUSE,
                    effect=AlertEffectEnum.OTHER_EFFECT,
                    header_text=header,
                    description_text=description,
                    url=item.get('url', None),
                    active_period_start=None,
                    active_period_end=None,
                    timestamp=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["alert_id"],
                    set_={
                        "header_text": stmt.excluded.header_text,
                        "description_text": stmt.excluded.description_text,
                        "url": stmt.excluded.url,
                        "timestamp": stmt.excluded.timestamp,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                self.db.execute(stmt)
                count += 1
            except Exception as e:
                logger.warning(f"Error inserting FGC alert: {e}")

        self.db.commit()
        return count

    # -------------------------------------------------------------------------
    # TMB iMetro API fetchers (Metro Barcelona)
    # -------------------------------------------------------------------------

    async def _fetch_tmb_predictions(self, config: dict) -> int:
        """Fetch predictions from TMB iMetro API."""
        url = config.get('stations_url')
        if not url:
            return 0

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params={'app_id': TMB_APP_ID, 'app_key': TMB_APP_KEY},
                timeout=30.0
            )
            response.raise_for_status()
            return self._parse_tmb_predictions(response.json(), config)

    def _fetch_tmb_predictions_sync(self, config: dict) -> int:
        """Sync version of _fetch_tmb_predictions."""
        url = config.get('stations_url')
        if not url:
            return 0

        response = httpx.get(
            url,
            params={'app_id': TMB_APP_ID, 'app_key': TMB_APP_KEY},
            timeout=30.0
        )
        response.raise_for_status()
        return self._parse_tmb_predictions(response.json(), config)

    def _parse_tmb_predictions(self, data: List[dict], config: dict) -> int:
        """Parse TMB iMetro API predictions and store in DB.

        TMB iMetro API returns a list of station predictions:
        [
            {
                "codi_linia": 1,
                "codi_via": 1,
                "codi_estacio": 111,
                "ocupacio_estacio_sortida": {"percentatge_ocupacio": 0},
                "propers_trens": [
                    {
                        "codi_servei": "118",
                        "temps_arribada": 1768730304000,  # Unix timestamp ms
                        "temps_restant": 224,  # seconds remaining
                        "codi_linia": 1,
                        "nom_linia": "L1",
                        "codi_trajecte": "0011",
                        "desti_trajecte": "Fondo",
                        "info_tren": {}
                    }
                ]
            }
        ]
        """
        prefix = config.get('stop_id_prefix', '')
        count = 0

        for station in data:
            station_id = station.get('codi_estacio')
            line_code = station.get('codi_linia')
            via = station.get('codi_via')

            if not station_id:
                continue

            stop_id = f"{prefix}{station_id}"
            trains = station.get('propers_trens', [])

            for train in trains:
                service_id = train.get('codi_servei', '')
                time_remaining = train.get('temps_restant')  # seconds
                arrival_timestamp = train.get('temps_arribada')  # ms timestamp
                line_name = train.get('nom_linia', '')
                destination = train.get('desti_trajecte', '')
                route_code = train.get('codi_trajecte', '')

                # Create a unique trip_id based on service, line, destination
                trip_id = f"{prefix}{service_id}_{line_name}_{route_code}"

                # Use time_remaining as the delay (arrival in X seconds)
                delay_seconds = int(time_remaining) if time_remaining is not None else 0

                try:
                    # Delete existing stop time updates for this trip
                    self.db.query(StopTimeUpdateModel).filter(
                        StopTimeUpdateModel.trip_id == trip_id
                    ).delete()

                    stmt = insert(TripUpdateModel).values(
                        trip_id=trip_id,
                        delay=delay_seconds,
                        vehicle_id=f"{prefix}train_{service_id}",
                        wheelchair_accessible=None,
                        timestamp=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["trip_id"],
                        set_={
                            "delay": stmt.excluded.delay,
                            "vehicle_id": stmt.excluded.vehicle_id,
                            "timestamp": stmt.excluded.timestamp,
                            "updated_at": stmt.excluded.updated_at,
                        },
                    )
                    self.db.execute(stmt)

                    # Store the prediction as stop time update
                    if arrival_timestamp:
                        arrival_time = datetime.fromtimestamp(arrival_timestamp / 1000)
                    elif time_remaining is not None:
                        arrival_time = datetime.utcnow() + timedelta(seconds=int(time_remaining))
                    else:
                        arrival_time = None

                    if arrival_time:
                        # Use codi_via as platform (1=direction A, 2=direction B)
                        platform = str(via) if via else None

                        # Extract occupancy data from info_tren
                        occupancy = None
                        occupancy_per_car = None
                        info_tren = train.get('info_tren', {})
                        if info_tren:
                            if 'percentatge_ocupacio' in info_tren:
                                occupancy = info_tren.get('percentatge_ocupacio')
                            if 'percentatge_ocupacio_cotxes' in info_tren:
                                # Store as JSON string
                                occupancy_per_car = json.dumps(info_tren.get('percentatge_ocupacio_cotxes'))

                        stop_time_model = StopTimeUpdateModel(
                            trip_id=trip_id,
                            stop_id=stop_id,
                            arrival_delay=delay_seconds,
                            arrival_time=arrival_time,
                            departure_delay=None,
                            departure_time=None,
                            platform=platform,
                            occupancy_percent=occupancy,
                            occupancy_per_car=occupancy_per_car,
                            headsign=destination,  # Store destination as headsign
                        )
                        self.db.add(stop_time_model)

                    count += 1
                except Exception as e:
                    logger.warning(f"Error inserting TMB prediction: {e}")

        self.db.commit()
        logger.info(f"Parsed {count} TMB predictions from {len(data)} station entries")
        return count

    # -------------------------------------------------------------------------
    # Metrovalencia API fetchers (Valencia Metro/Tram)
    # -------------------------------------------------------------------------

    async def _fetch_metrovalencia_predictions(self, config: dict) -> int:
        """Fetch predictions from Metrovalencia (FGV Valencia) API."""
        stations_url = config.get('stations_url')
        realtime_url = config.get('realtime_url')
        if not stations_url or not realtime_url:
            return 0

        async with httpx.AsyncClient() as client:
            # First get all stations
            stations_response = await client.get(stations_url, timeout=30.0)
            stations_response.raise_for_status()
            stations = stations_response.json()

            # Then fetch real-time data for each station
            return await self._fetch_metrovalencia_realtime_async(client, stations, realtime_url, config)

    def _fetch_metrovalencia_predictions_sync(self, config: dict) -> int:
        """Sync version of _fetch_metrovalencia_predictions."""
        stations_url = config.get('stations_url')
        realtime_url = config.get('realtime_url')
        if not stations_url or not realtime_url:
            return 0

        # Get all stations from Valencia OpenData
        stations_response = httpx.get(stations_url, timeout=30.0)
        stations_response.raise_for_status()
        stations = stations_response.json()

        # Fetch real-time data for each station
        return self._fetch_metrovalencia_realtime_sync(stations, realtime_url, config)

    async def _fetch_metrovalencia_realtime_async(
        self, client: httpx.AsyncClient, stations: List[dict], realtime_url: str, config: dict
    ) -> int:
        """Fetch real-time arrivals for all Metrovalencia stations (async)."""
        prefix = config.get('stop_id_prefix', '')
        count = 0

        for station in stations:
            station_code = station.get('codigo')
            if not station_code:
                continue

            try:
                response = await client.get(
                    realtime_url,
                    params={'estacion': station_code},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()

                arrivals = data.get('salidasMetro', [])
                count += self._parse_metrovalencia_arrivals(arrivals, station, config)

            except Exception as e:
                logger.debug(f"Error fetching Metrovalencia station {station_code}: {e}")

        self.db.commit()
        logger.info(f"Fetched {count} Metrovalencia predictions from {len(stations)} stations")
        return count

    def _fetch_metrovalencia_realtime_sync(
        self, stations: List[dict], realtime_url: str, config: dict
    ) -> int:
        """Fetch real-time arrivals for all Metrovalencia stations (sync)."""
        prefix = config.get('stop_id_prefix', '')
        count = 0

        for station in stations:
            station_code = station.get('codigo')
            if not station_code:
                continue

            try:
                response = httpx.get(
                    realtime_url,
                    params={'estacion': station_code},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()

                arrivals = data.get('salidasMetro', [])
                count += self._parse_metrovalencia_arrivals(arrivals, station, config)

            except Exception as e:
                logger.debug(f"Error fetching Metrovalencia station {station_code}: {e}")

        self.db.commit()
        logger.info(f"Fetched {count} Metrovalencia predictions from {len(stations)} stations")
        return count

    def _parse_metrovalencia_arrivals(
        self, arrivals: List[dict], station: dict, config: dict
    ) -> int:
        """Parse Metrovalencia arrivals and store in DB.

        Expected arrival format (when API returns data):
        {
            "linea": "L3",
            "destino": "Rafelbunyol",
            "minutos": 5,
            "via": 1,
            ...
        }

        Note: As of 2026-01, the geoportal API returns empty data.
        This parser is ready for when the API starts working.
        """
        prefix = config.get('stop_id_prefix', '')
        station_code = station.get('codigo', '')
        station_name = station.get('nombre', '')
        station_line = station.get('linea', '')

        stop_id = f"{prefix}{station_code}"
        count = 0

        for arrival in arrivals:
            try:
                line = arrival.get('linea', arrival.get('nom_linia', station_line))
                destination = arrival.get('destino', arrival.get('desti', ''))
                minutes = arrival.get('minutos', arrival.get('temps_restant'))
                via = arrival.get('via', arrival.get('codi_via'))

                if minutes is None:
                    continue

                # Convert minutes to seconds if needed
                if isinstance(minutes, (int, float)) and minutes < 100:
                    delay_seconds = int(minutes * 60)
                else:
                    delay_seconds = int(minutes)

                # Create unique trip_id
                trip_id = f"{prefix}{line}_{destination}_{station_code}"

                # Delete existing stop time updates for this trip
                self.db.query(StopTimeUpdateModel).filter(
                    StopTimeUpdateModel.trip_id == trip_id
                ).delete()

                stmt = insert(TripUpdateModel).values(
                    trip_id=trip_id,
                    delay=delay_seconds,
                    vehicle_id=f"{prefix}train_{line}",
                    wheelchair_accessible=None,
                    timestamp=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["trip_id"],
                    set_={
                        "delay": stmt.excluded.delay,
                        "vehicle_id": stmt.excluded.vehicle_id,
                        "timestamp": stmt.excluded.timestamp,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                self.db.execute(stmt)

                # Calculate arrival time
                arrival_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
                platform = str(via) if via else None

                stop_time_model = StopTimeUpdateModel(
                    trip_id=trip_id,
                    stop_id=stop_id,
                    arrival_delay=delay_seconds,
                    arrival_time=arrival_time,
                    departure_delay=None,
                    departure_time=None,
                    platform=platform,
                    headsign=destination,
                )
                self.db.add(stop_time_model)
                count += 1

            except Exception as e:
                logger.warning(f"Error parsing Metrovalencia arrival: {e}")

        return count


# CLI for testing
if __name__ == "__main__":
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent.parent.parent
    sys.path.insert(0, str(project_root))

    from core.database import SessionLocal

    logging.basicConfig(level=logging.INFO)

    db = SessionLocal()
    try:
        fetcher = MultiOperatorFetcher(db)

        if len(sys.argv) > 1:
            operator = sys.argv[1]
            result = fetcher.fetch_operator_sync(operator)
        else:
            print("Available operators:", list(GTFS_RT_OPERATORS.keys()))
            print("\nFetching all operators...")
            results = fetcher.fetch_all_operators_sync()
            for result in results:
                print(f"  {result}")
    finally:
        db.close()
