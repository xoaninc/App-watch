#!/usr/bin/env python3
"""Generic GTFS importer for multiple transit operators.

This script can import GTFS data from any operator defined in operators_config.py.

Usage:
    # Import a specific operator from URL
    python scripts/import_gtfs_generic.py metro_malaga

    # Import from local file
    python scripts/import_gtfs_generic.py metro_valencia --file /path/to/gtfs.zip

    # Import multiple operators
    python scripts/import_gtfs_generic.py metro_malaga metro_bilbao fgc

    # Import all auto-importable operators
    python scripts/import_gtfs_generic.py --all

    # List available operators
    python scripts/import_gtfs_generic.py --list

    # Dry run (don't write to database)
    python scripts/import_gtfs_generic.py metro_malaga --dry-run
"""

import sys
import os
import csv
import zipfile
import logging
import argparse
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from io import TextIOWrapper
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database import SessionLocal
from scripts.operators_config import (
    OPERATORS, OperatorConfig, AuthMethod,
    get_operator, get_auto_importable_operators
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 5000


@dataclass
class ImportStats:
    """Statistics from an import operation."""
    operator: str
    agency_created: bool = False
    routes_created: int = 0
    routes_updated: int = 0
    stops_created: int = 0
    stops_updated: int = 0
    trips_created: int = 0
    stop_times_created: int = 0
    calendar_created: int = 0
    calendar_dates_created: int = 0
    shapes_created: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class GTFSGenericImporter:
    """Generic GTFS importer that works with any operator."""

    def __init__(self, db: Session, config: OperatorConfig, dry_run: bool = False):
        self.db = db
        self.config = config
        self.dry_run = dry_run
        self.stats = ImportStats(operator=config.code)
        self._stop_id_mapping: Dict[str, str] = {}  # gtfs_id -> our_id
        self._route_id_mapping: Dict[str, str] = {}  # gtfs_id -> our_id
        self._trip_ids: set = set()  # Track imported trip IDs

    def _make_stop_id(self, gtfs_stop_id: str) -> str:
        """Create our stop ID from GTFS stop_id."""
        prefix = self.config.code.upper()
        return f"{prefix}_{gtfs_stop_id}"

    def _make_route_id(self, gtfs_route_id: str) -> str:
        """Create our route ID from GTFS route_id."""
        prefix = self.config.code.upper()
        return f"{prefix}_{gtfs_route_id}"

    def download_gtfs(self, target_path: Path) -> bool:
        """Download GTFS zip from operator URL."""
        if not self.config.gtfs_url:
            logger.error(f"No GTFS URL configured for {self.config.code}")
            return False

        logger.info(f"Downloading GTFS from {self.config.gtfs_url}")

        try:
            headers = {}

            # Handle API key authentication
            url = self.config.gtfs_url
            if self.config.auth_method == AuthMethod.API_KEY:
                if self.config.api_id and self.config.api_key:
                    # Add API credentials to URL
                    separator = '&' if '?' in url else '?'
                    url = f"{url}{separator}app_id={self.config.api_id}&app_key={self.config.api_key}"

            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()

                with open(target_path, 'wb') as f:
                    f.write(response.content)

            logger.info(f"Downloaded GTFS to {target_path} ({target_path.stat().st_size / 1024:.1f} KB)")
            return True

        except httpx.HTTPError as e:
            logger.error(f"HTTP error downloading GTFS: {e}")
            return False
        except Exception as e:
            logger.error(f"Error downloading GTFS: {e}")
            return False

    def _read_csv_from_zip(self, zf: zipfile.ZipFile, filename: str) -> List[dict]:
        """Read a CSV file from the GTFS zip."""
        try:
            with zf.open(filename) as f:
                reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8-sig'))
                # Strip whitespace from field names
                if reader.fieldnames:
                    reader.fieldnames = [name.strip() for name in reader.fieldnames]
                return list(reader)
        except KeyError:
            logger.warning(f"File {filename} not found in GTFS zip")
            return []

    def import_agency(self, zf: zipfile.ZipFile) -> Optional[str]:
        """Import agency from GTFS."""
        rows = self._read_csv_from_zip(zf, 'agency.txt')

        if not rows:
            # Create agency from config
            agency_id = self.config.agency_id or self.config.code.upper()
            agency_name = self.config.agency_name or self.config.name
            agency_url = self.config.agency_url or ''
        else:
            # Use first agency from GTFS
            row = rows[0]
            agency_id = row.get('agency_id', '').strip() or self.config.agency_id or self.config.code.upper()
            agency_name = row.get('agency_name', '').strip() or self.config.name
            agency_url = row.get('agency_url', '').strip() or self.config.agency_url or ''

        # Prefix agency_id with operator code to avoid conflicts
        our_agency_id = f"{self.config.code.upper()}_{agency_id}" if not agency_id.startswith(self.config.code.upper()) else agency_id

        logger.info(f"Importing agency: {our_agency_id} ({agency_name})")

        if not self.dry_run:
            self.db.execute(
                text("""
                    INSERT INTO gtfs_agencies (id, name, url, timezone, lang)
                    VALUES (:id, :name, :url, :timezone, :lang)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        url = EXCLUDED.url
                """),
                {
                    'id': our_agency_id,
                    'name': agency_name,
                    'url': agency_url,
                    'timezone': 'Europe/Madrid',
                    'lang': 'es',
                }
            )
            self.db.commit()
            self.stats.agency_created = True

        return our_agency_id

    def import_stops(self, zf: zipfile.ZipFile) -> int:
        """Import stops from GTFS."""
        rows = self._read_csv_from_zip(zf, 'stops.txt')

        if not rows:
            logger.warning("No stops found in GTFS")
            return 0

        logger.info(f"Importing {len(rows)} stops...")

        batch = []
        for row in rows:
            gtfs_stop_id = row.get('stop_id', '').strip()
            if not gtfs_stop_id:
                continue

            our_stop_id = self._make_stop_id(gtfs_stop_id)
            self._stop_id_mapping[gtfs_stop_id] = our_stop_id

            # Parse location_type (default 0 = stop/platform)
            location_type = int(row.get('location_type', '0') or '0')

            batch.append({
                'id': our_stop_id,
                'name': row.get('stop_name', '').strip(),
                'lat': float(row.get('stop_lat', '0').strip() or '0'),
                'lon': float(row.get('stop_lon', '0').strip() or '0'),
                'code': row.get('stop_code', '').strip() or None,
                'description': row.get('stop_desc', '').strip() or None,
                'zone_id': row.get('zone_id', '').strip() or None,
                'url': row.get('stop_url', '').strip() or None,
                'location_type': location_type,
                'parent_station_id': None,  # Set later
                'wheelchair_boarding': int(row.get('wheelchair_boarding', '0') or '0'),
                'platform_code': row.get('platform_code', '').strip() or None,
                'nucleo_id': self.config.nucleo_id,
                'lineas': '',  # Will be populated later
            })

            if len(batch) >= BATCH_SIZE:
                if not self.dry_run:
                    self._insert_stops_batch(batch)
                self.stats.stops_created += len(batch)
                batch = []

        if batch:
            if not self.dry_run:
                self._insert_stops_batch(batch)
            self.stats.stops_created += len(batch)

        # Update parent station references
        self._update_parent_stations(zf)

        logger.info(f"Imported {self.stats.stops_created} stops")
        return self.stats.stops_created

    def _insert_stops_batch(self, batch: List[dict]):
        """Insert a batch of stops."""
        self.db.execute(
            text("""
                INSERT INTO gtfs_stops
                (id, name, lat, lon, code, description, zone_id, url, location_type,
                 parent_station_id, wheelchair_boarding, platform_code, nucleo_id, lineas)
                VALUES (:id, :name, :lat, :lon, :code, :description, :zone_id, :url,
                        :location_type, :parent_station_id, :wheelchair_boarding,
                        :platform_code, :nucleo_id, :lineas)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    lat = EXCLUDED.lat,
                    lon = EXCLUDED.lon,
                    location_type = EXCLUDED.location_type,
                    wheelchair_boarding = EXCLUDED.wheelchair_boarding,
                    nucleo_id = EXCLUDED.nucleo_id
            """),
            batch
        )
        self.db.commit()

    def _update_parent_stations(self, zf: zipfile.ZipFile):
        """Update parent_station_id references."""
        rows = self._read_csv_from_zip(zf, 'stops.txt')

        updates = []
        for row in rows:
            gtfs_stop_id = row.get('stop_id', '').strip()
            parent_station = row.get('parent_station', '').strip()

            if parent_station and parent_station in self._stop_id_mapping:
                our_stop_id = self._stop_id_mapping[gtfs_stop_id]
                our_parent_id = self._stop_id_mapping[parent_station]
                updates.append({'stop_id': our_stop_id, 'parent_id': our_parent_id})

        if updates and not self.dry_run:
            for update in updates:
                self.db.execute(
                    text("UPDATE gtfs_stops SET parent_station_id = :parent_id WHERE id = :stop_id"),
                    update
                )
            self.db.commit()
            logger.info(f"Updated {len(updates)} parent station references")

    def import_routes(self, zf: zipfile.ZipFile, agency_id: str) -> int:
        """Import routes from GTFS."""
        rows = self._read_csv_from_zip(zf, 'routes.txt')

        if not rows:
            logger.warning("No routes found in GTFS")
            return 0

        logger.info(f"Importing {len(rows)} routes...")

        batch = []
        for row in rows:
            gtfs_route_id = row.get('route_id', '').strip()
            if not gtfs_route_id:
                continue

            our_route_id = self._make_route_id(gtfs_route_id)
            self._route_id_mapping[gtfs_route_id] = our_route_id

            # Parse route type
            route_type = int(row.get('route_type', str(self.config.route_type)).strip() or str(self.config.route_type))

            # Parse colors (remove # if present)
            color = row.get('route_color', '').strip().lstrip('#') or self.config.color
            text_color = row.get('route_text_color', '').strip().lstrip('#') or self.config.text_color

            batch.append({
                'id': our_route_id,
                'agency_id': agency_id,
                'short_name': row.get('route_short_name', '').strip() or gtfs_route_id,
                'long_name': row.get('route_long_name', '').strip() or row.get('route_short_name', '').strip() or gtfs_route_id,
                'route_type': route_type,
                'color': color,
                'text_color': text_color,
                'description': row.get('route_desc', '').strip() or None,
                'url': row.get('route_url', '').strip() or None,
                'sort_order': int(row.get('route_sort_order', '0') or '0'),
                'nucleo_id': self.config.nucleo_id,
            })

        if batch:
            if not self.dry_run:
                self.db.execute(
                    text("""
                        INSERT INTO gtfs_routes
                        (id, agency_id, short_name, long_name, route_type, color, text_color,
                         description, url, sort_order, nucleo_id)
                        VALUES (:id, :agency_id, :short_name, :long_name, :route_type, :color,
                                :text_color, :description, :url, :sort_order, :nucleo_id)
                        ON CONFLICT (id) DO UPDATE SET
                            short_name = EXCLUDED.short_name,
                            long_name = EXCLUDED.long_name,
                            route_type = EXCLUDED.route_type,
                            color = EXCLUDED.color,
                            text_color = EXCLUDED.text_color,
                            nucleo_id = EXCLUDED.nucleo_id
                    """),
                    batch
                )
                self.db.commit()
            self.stats.routes_created = len(batch)

        logger.info(f"Imported {len(batch)} routes")
        return len(batch)

    def import_calendar(self, zf: zipfile.ZipFile) -> int:
        """Import calendar from GTFS."""
        rows = self._read_csv_from_zip(zf, 'calendar.txt')

        if not rows:
            logger.info("No calendar.txt found, checking calendar_dates.txt...")
            return 0

        logger.info(f"Importing {len(rows)} calendar entries...")

        batch = []
        for row in rows:
            service_id = row.get('service_id', '').strip()
            if not service_id:
                continue

            # Prefix service_id with operator code
            our_service_id = f"{self.config.code.upper()}_{service_id}"

            # Parse dates
            start_date = row.get('start_date', '').strip()
            end_date = row.get('end_date', '').strip()

            if len(start_date) == 8:
                start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            if len(end_date) == 8:
                end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

            batch.append({
                'service_id': our_service_id,
                'monday': row.get('monday', '0').strip() == '1',
                'tuesday': row.get('tuesday', '0').strip() == '1',
                'wednesday': row.get('wednesday', '0').strip() == '1',
                'thursday': row.get('thursday', '0').strip() == '1',
                'friday': row.get('friday', '0').strip() == '1',
                'saturday': row.get('saturday', '0').strip() == '1',
                'sunday': row.get('sunday', '0').strip() == '1',
                'start_date': start_date,
                'end_date': end_date,
            })

        if batch:
            if not self.dry_run:
                self.db.execute(
                    text("""
                        INSERT INTO gtfs_calendar
                        (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                         start_date, end_date)
                        VALUES (:service_id, :monday, :tuesday, :wednesday, :thursday, :friday,
                                :saturday, :sunday, :start_date, :end_date)
                        ON CONFLICT (service_id) DO UPDATE SET
                            monday = EXCLUDED.monday,
                            tuesday = EXCLUDED.tuesday,
                            wednesday = EXCLUDED.wednesday,
                            thursday = EXCLUDED.thursday,
                            friday = EXCLUDED.friday,
                            saturday = EXCLUDED.saturday,
                            sunday = EXCLUDED.sunday,
                            start_date = EXCLUDED.start_date,
                            end_date = EXCLUDED.end_date
                    """),
                    batch
                )
                self.db.commit()
            self.stats.calendar_created = len(batch)

        logger.info(f"Imported {len(batch)} calendar entries")
        return len(batch)

    def import_calendar_dates(self, zf: zipfile.ZipFile) -> int:
        """Import calendar_dates from GTFS."""
        rows = self._read_csv_from_zip(zf, 'calendar_dates.txt')

        if not rows:
            return 0

        logger.info(f"Importing {len(rows)} calendar_dates entries...")

        # First, collect all unique service_ids and create calendar entries for those
        # that don't exist (some GTFS feeds only use calendar_dates without calendar.txt)
        unique_service_ids = set()
        for row in rows:
            service_id = row.get('service_id', '').strip()
            if service_id:
                unique_service_ids.add(f"{self.config.code.upper()}_{service_id}")

        if unique_service_ids and not self.dry_run:
            self._ensure_calendar_entries_exist(unique_service_ids)

        batch = []
        for row in rows:
            service_id = row.get('service_id', '').strip()
            date_str = row.get('date', '').strip()
            exception_type = row.get('exception_type', '1').strip()

            if not service_id or not date_str:
                continue

            our_service_id = f"{self.config.code.upper()}_{service_id}"

            # Parse date
            if len(date_str) == 8:
                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

            batch.append({
                'service_id': our_service_id,
                'date': date_str,
                'exception_type': int(exception_type),
            })

            if len(batch) >= BATCH_SIZE:
                if not self.dry_run:
                    self._insert_calendar_dates_batch(batch)
                self.stats.calendar_dates_created += len(batch)
                batch = []

        if batch:
            if not self.dry_run:
                self._insert_calendar_dates_batch(batch)
            self.stats.calendar_dates_created += len(batch)

        logger.info(f"Imported {self.stats.calendar_dates_created} calendar_dates entries")
        return self.stats.calendar_dates_created

    def _ensure_calendar_entries_exist(self, service_ids: set):
        """Create placeholder calendar entries for service_ids that don't exist.

        Some GTFS feeds only use calendar_dates.txt without calendar.txt.
        We need to create calendar entries to satisfy the foreign key constraint.
        """
        # Get existing service_ids
        result = self.db.execute(
            text("SELECT service_id FROM gtfs_calendar WHERE service_id = ANY(:ids)"),
            {'ids': list(service_ids)}
        )
        existing = {row[0] for row in result}

        missing = service_ids - existing
        if not missing:
            return

        logger.info(f"Creating {len(missing)} placeholder calendar entries for calendar_dates...")

        # Create placeholder entries (all days = False, dates set to reasonable defaults)
        batch = []
        for service_id in missing:
            batch.append({
                'service_id': service_id,
                'monday': False,
                'tuesday': False,
                'wednesday': False,
                'thursday': False,
                'friday': False,
                'saturday': False,
                'sunday': False,
                'start_date': '2025-01-01',
                'end_date': '2026-12-31',
            })

        if batch:
            self.db.execute(
                text("""
                    INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                    VALUES (:service_id, :monday, :tuesday, :wednesday, :thursday, :friday, :saturday, :sunday, :start_date, :end_date)
                    ON CONFLICT (service_id) DO NOTHING
                """),
                batch
            )
            self.db.commit()

    def _insert_calendar_dates_batch(self, batch: List[dict]):
        """Insert a batch of calendar_dates."""
        self.db.execute(
            text("""
                INSERT INTO gtfs_calendar_dates (service_id, date, exception_type)
                VALUES (:service_id, :date, :exception_type)
                ON CONFLICT (service_id, date) DO UPDATE SET
                    exception_type = EXCLUDED.exception_type
            """),
            batch
        )
        self.db.commit()

    def import_trips(self, zf: zipfile.ZipFile) -> int:
        """Import trips from GTFS."""
        rows = self._read_csv_from_zip(zf, 'trips.txt')

        if not rows:
            logger.warning("No trips found in GTFS")
            return 0

        logger.info(f"Importing {len(rows)} trips...")

        batch = []
        skipped = 0
        for row in rows:
            gtfs_route_id = row.get('route_id', '').strip()
            gtfs_trip_id = row.get('trip_id', '').strip()
            service_id = row.get('service_id', '').strip()

            if not gtfs_trip_id or not gtfs_route_id:
                continue

            # Check if route exists
            our_route_id = self._route_id_mapping.get(gtfs_route_id)
            if not our_route_id:
                skipped += 1
                continue

            # Create our IDs
            our_trip_id = f"{self.config.code.upper()}_{gtfs_trip_id}"
            our_service_id = f"{self.config.code.upper()}_{service_id}" if service_id else None

            self._trip_ids.add(our_trip_id)

            batch.append({
                'id': our_trip_id,
                'route_id': our_route_id,
                'service_id': our_service_id,
                'headsign': row.get('trip_headsign', '').strip() or None,
                'short_name': row.get('trip_short_name', '').strip() or None,
                'direction_id': int(row.get('direction_id', '0') or '0'),
                'block_id': row.get('block_id', '').strip() or None,
                'shape_id': row.get('shape_id', '').strip() or None,
                'wheelchair_accessible': int(row.get('wheelchair_accessible', '0') or '0'),
                'bikes_allowed': int(row.get('bikes_allowed', '0') or '0'),
            })

            if len(batch) >= BATCH_SIZE:
                if not self.dry_run:
                    self._insert_trips_batch(batch)
                self.stats.trips_created += len(batch)
                batch = []

        if batch:
            if not self.dry_run:
                self._insert_trips_batch(batch)
            self.stats.trips_created += len(batch)

        if skipped:
            logger.warning(f"Skipped {skipped} trips (route not found)")

        logger.info(f"Imported {self.stats.trips_created} trips")
        return self.stats.trips_created

    def _insert_trips_batch(self, batch: List[dict]):
        """Insert a batch of trips."""
        self.db.execute(
            text("""
                INSERT INTO gtfs_trips
                (id, route_id, service_id, headsign, short_name, direction_id,
                 block_id, shape_id, wheelchair_accessible, bikes_allowed)
                VALUES (:id, :route_id, :service_id, :headsign, :short_name, :direction_id,
                        :block_id, :shape_id, :wheelchair_accessible, :bikes_allowed)
                ON CONFLICT (id) DO UPDATE SET
                    route_id = EXCLUDED.route_id,
                    service_id = EXCLUDED.service_id,
                    headsign = EXCLUDED.headsign,
                    direction_id = EXCLUDED.direction_id
            """),
            batch
        )
        self.db.commit()

    def import_stop_times(self, zf: zipfile.ZipFile) -> int:
        """Import stop_times from GTFS."""
        rows = self._read_csv_from_zip(zf, 'stop_times.txt')

        if not rows:
            logger.warning("No stop_times found in GTFS")
            return 0

        logger.info(f"Importing {len(rows)} stop_times (this may take a while)...")

        batch = []
        skipped_trip = 0
        skipped_stop = 0

        for i, row in enumerate(rows):
            gtfs_trip_id = row.get('trip_id', '').strip()
            gtfs_stop_id = row.get('stop_id', '').strip()

            our_trip_id = f"{self.config.code.upper()}_{gtfs_trip_id}"
            our_stop_id = self._stop_id_mapping.get(gtfs_stop_id)

            # Skip if trip not imported
            if our_trip_id not in self._trip_ids:
                skipped_trip += 1
                continue

            # Skip if stop not found
            if not our_stop_id:
                skipped_stop += 1
                continue

            arrival_time = row.get('arrival_time', '').strip()
            departure_time = row.get('departure_time', '').strip()

            batch.append({
                'trip_id': our_trip_id,
                'stop_id': our_stop_id,
                'stop_sequence': int(row.get('stop_sequence', '0').strip() or '0'),
                'arrival_time': arrival_time,
                'departure_time': departure_time,
                'arrival_seconds': self._time_to_seconds(arrival_time),
                'departure_seconds': self._time_to_seconds(departure_time),
                'stop_headsign': row.get('stop_headsign', '').strip() or None,
                'pickup_type': int(row.get('pickup_type', '0') or '0'),
                'drop_off_type': int(row.get('drop_off_type', '0') or '0'),
                'shape_dist_traveled': float(row.get('shape_dist_traveled', '0') or '0') if row.get('shape_dist_traveled', '').strip() else None,
                'timepoint': int(row.get('timepoint', '1') or '1'),
            })

            if len(batch) >= BATCH_SIZE:
                if not self.dry_run:
                    self._insert_stop_times_batch(batch)
                self.stats.stop_times_created += len(batch)
                batch = []

                if self.stats.stop_times_created % 50000 == 0:
                    logger.info(f"  Progress: {self.stats.stop_times_created:,} stop_times...")

        if batch:
            if not self.dry_run:
                self._insert_stop_times_batch(batch)
            self.stats.stop_times_created += len(batch)

        if skipped_trip:
            logger.warning(f"Skipped {skipped_trip} stop_times (trip not found)")
        if skipped_stop:
            logger.warning(f"Skipped {skipped_stop} stop_times (stop not found)")

        logger.info(f"Imported {self.stats.stop_times_created:,} stop_times")
        return self.stats.stop_times_created

    def _insert_stop_times_batch(self, batch: List[dict]):
        """Insert a batch of stop_times."""
        self.db.execute(
            text("""
                INSERT INTO gtfs_stop_times
                (trip_id, stop_id, stop_sequence, arrival_time, departure_time,
                 arrival_seconds, departure_seconds, stop_headsign, pickup_type,
                 drop_off_type, shape_dist_traveled, timepoint)
                VALUES (:trip_id, :stop_id, :stop_sequence, :arrival_time, :departure_time,
                        :arrival_seconds, :departure_seconds, :stop_headsign, :pickup_type,
                        :drop_off_type, :shape_dist_traveled, :timepoint)
                ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
                    stop_id = EXCLUDED.stop_id,
                    arrival_time = EXCLUDED.arrival_time,
                    departure_time = EXCLUDED.departure_time,
                    arrival_seconds = EXCLUDED.arrival_seconds,
                    departure_seconds = EXCLUDED.departure_seconds
            """),
            batch
        )
        self.db.commit()

    @staticmethod
    def _time_to_seconds(time_str: str) -> int:
        """Convert HH:MM:SS to seconds since midnight."""
        if not time_str:
            return 0
        parts = time_str.strip().split(':')
        if len(parts) != 3:
            return 0
        try:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except ValueError:
            return 0

    def update_stop_lines(self):
        """Update the 'lineas' field for each stop based on routes serving it."""
        if self.dry_run:
            return

        logger.info("Updating stop lines...")

        # Get routes per stop from stop_times
        result = self.db.execute(text("""
            SELECT DISTINCT st.stop_id, r.short_name
            FROM gtfs_stop_times st
            JOIN gtfs_trips t ON st.trip_id = t.id
            JOIN gtfs_routes r ON t.route_id = r.id
            WHERE st.stop_id LIKE :prefix
        """), {'prefix': f"{self.config.code.upper()}_%"})

        stop_lines: Dict[str, set] = {}
        for row in result:
            stop_id, short_name = row
            if stop_id not in stop_lines:
                stop_lines[stop_id] = set()
            stop_lines[stop_id].add(short_name)

        # Update stops
        for stop_id, lines in stop_lines.items():
            lineas_str = ','.join(sorted(lines))
            self.db.execute(
                text("UPDATE gtfs_stops SET lineas = :lineas WHERE id = :stop_id"),
                {'lineas': lineas_str, 'stop_id': stop_id}
            )

        self.db.commit()
        logger.info(f"Updated lines for {len(stop_lines)} stops")

    def run(self, gtfs_path: Optional[Path] = None) -> ImportStats:
        """Run the full import process."""
        logger.info("=" * 60)
        logger.info(f"IMPORTING: {self.config.name}")
        logger.info("=" * 60)

        start_time = datetime.now()

        # Get GTFS file
        temp_dir = None
        if gtfs_path and gtfs_path.exists():
            zip_path = gtfs_path
        elif self.config.gtfs_url and self.config.auth_method != AuthMethod.MANUAL:
            temp_dir = tempfile.mkdtemp()
            zip_path = Path(temp_dir) / "gtfs.zip"
            if not self.download_gtfs(zip_path):
                raise RuntimeError("Failed to download GTFS")
        else:
            raise RuntimeError(
                f"No GTFS file provided and cannot auto-download for {self.config.code}. "
                f"Use --file /path/to/gtfs.zip"
            )

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # List files in zip
                logger.info(f"GTFS files: {zf.namelist()}")

                # Import in order
                agency_id = self.import_agency(zf)
                self.import_stops(zf)
                self.import_routes(zf, agency_id)
                self.import_calendar(zf)
                self.import_calendar_dates(zf)
                self.import_trips(zf)
                self.import_stop_times(zf)
                self.update_stop_lines()

        finally:
            if temp_dir:
                shutil.rmtree(temp_dir)

        elapsed = datetime.now() - start_time

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info(f"IMPORT COMPLETE: {self.config.name}")
        logger.info("=" * 60)
        logger.info(f"Agency: {'created' if self.stats.agency_created else 'updated'}")
        logger.info(f"Stops: {self.stats.stops_created}")
        logger.info(f"Routes: {self.stats.routes_created}")
        logger.info(f"Calendar: {self.stats.calendar_created}")
        logger.info(f"Calendar dates: {self.stats.calendar_dates_created}")
        logger.info(f"Trips: {self.stats.trips_created}")
        logger.info(f"Stop times: {self.stats.stop_times_created:,}")
        logger.info(f"Elapsed: {elapsed}")
        logger.info("=" * 60)

        return self.stats


def list_operators():
    """Print list of available operators."""
    print("\n" + "=" * 70)
    print("AVAILABLE OPERATORS")
    print("=" * 70)
    print(f"{'Code':<25} {'Name':<30} {'Auth':<10} {'RT'}")
    print("-" * 70)

    for code, op in sorted(OPERATORS.items()):
        has_rt = "Yes" if op.gtfs_rt else "No"
        auth = op.auth_method.value
        print(f"{code:<25} {op.name:<30} {auth:<10} {has_rt}")

    print("-" * 70)
    print(f"Total: {len(OPERATORS)} operators")

    auto = get_auto_importable_operators()
    print(f"\nAuto-importable (no manual download): {len(auto)}")
    print("  " + ", ".join(op.code for op in auto))


def main():
    parser = argparse.ArgumentParser(
        description='Import GTFS data from transit operators',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s metro_malaga                    # Import Metro Málaga from URL
  %(prog)s metro_valencia --file gtfs.zip  # Import from local file
  %(prog)s metro_bilbao fgc euskotren      # Import multiple operators
  %(prog)s --all                           # Import all auto-importable
  %(prog)s --list                          # List available operators
        """
    )

    parser.add_argument(
        'operators',
        nargs='*',
        help='Operator codes to import (e.g., metro_malaga, tmb_metro)'
    )
    parser.add_argument(
        '--file', '-f',
        type=Path,
        help='Path to local GTFS zip file'
    )
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Import all auto-importable operators'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available operators'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Parse GTFS without writing to database'
    )

    args = parser.parse_args()

    if args.list:
        list_operators()
        return 0

    # Determine which operators to import
    if args.all:
        operators = get_auto_importable_operators()
    elif args.operators:
        operators = []
        for code in args.operators:
            op = get_operator(code)
            if not op:
                logger.error(f"Unknown operator: {code}")
                logger.info("Use --list to see available operators")
                return 1
            operators.append(op)
    else:
        parser.print_help()
        return 1

    if not operators:
        logger.error("No operators to import")
        return 1

    # If using --file, only one operator allowed
    if args.file and len(operators) > 1:
        logger.error("--file can only be used with a single operator")
        return 1

    # Import each operator
    db = SessionLocal()
    all_stats = []

    try:
        for op in operators:
            logger.info(f"\n{'#' * 70}")
            logger.info(f"# Processing: {op.name}")
            logger.info(f"{'#' * 70}\n")

            try:
                importer = GTFSGenericImporter(db, op, dry_run=args.dry_run)
                stats = importer.run(gtfs_path=args.file)
                all_stats.append(stats)
            except Exception as e:
                logger.error(f"Failed to import {op.code}: {e}")
                import traceback
                traceback.print_exc()
                all_stats.append(ImportStats(operator=op.code, errors=[str(e)]))

        # Final summary
        print("\n" + "=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)
        for stats in all_stats:
            status = "OK" if not stats.errors else f"ERROR: {stats.errors[0]}"
            print(f"  {stats.operator}: {status}")
            if not stats.errors:
                print(f"    Stops: {stats.stops_created}, Routes: {stats.routes_created}, "
                      f"Trips: {stats.trips_created}, Stop times: {stats.stop_times_created:,}")
        print("=" * 70)

    except Exception as e:
        logger.error(f"Import failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
