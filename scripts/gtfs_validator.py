#!/usr/bin/env python3
"""GTFS data validator.

Validates GTFS data structure and integrity before importing.

Usage:
    python scripts/gtfs_validator.py /path/to/gtfs.zip
"""

import sys
import csv
import re
import zipfile
import logging
from dataclasses import dataclass, field
from datetime import datetime
from io import TextIOWrapper
from pathlib import Path
from typing import Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ValidationMetrics:
    """Metrics collected during validation."""
    stops_count: int = 0
    routes_count: int = 0
    trips_count: int = 0
    stop_times_count: int = 0
    calendar_entries: int = 0
    calendar_dates_entries: int = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class ValidationReport:
    """Results of GTFS validation."""
    is_valid: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    metrics: ValidationMetrics = field(default_factory=ValidationMetrics)

    def add_error(self, message: str):
        """Add an error (makes validation invalid)."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        """Add a warning (does not invalidate)."""
        self.warnings.append(message)

    def summary(self) -> str:
        """Get a brief summary of the validation."""
        m = self.metrics
        return (
            f"stops={m.stops_count}, routes={m.routes_count}, "
            f"trips={m.trips_count}, stop_times={m.stop_times_count}, "
            f"calendar={m.calendar_entries}+{m.calendar_dates_entries} dates, "
            f"range={m.start_date or '?'}..{m.end_date or '?'}"
        )

    def __str__(self) -> str:
        lines = []
        lines.append(f"Valid: {self.is_valid}")
        lines.append(f"Summary: {self.summary()}")

        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  - {err}")

        if self.warnings:
            lines.append("\nWarnings:")
            for warn in self.warnings:
                lines.append(f"  - {warn}")

        return "\n".join(lines)


class GTFSValidator:
    """Validates GTFS data structure and integrity."""

    # Required files and their required columns
    REQUIRED_FILES = {
        'stops.txt': ['stop_id', 'stop_name', 'stop_lat', 'stop_lon'],
        'routes.txt': ['route_id', 'route_short_name'],
        'trips.txt': ['route_id', 'service_id', 'trip_id'],
        'stop_times.txt': ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence'],
    }

    # At least one of these must exist
    CALENDAR_FILES = ['calendar.txt', 'calendar_dates.txt']

    # Time format regex: HH:MM:SS (allows >24h for night services)
    TIME_REGEX = re.compile(r'^([0-9]{1,2}):([0-5][0-9]):([0-5][0-9])$')

    # Date format regex: YYYYMMDD
    DATE_REGEX = re.compile(r'^[0-9]{8}$')

    def __init__(self, zip_path: str | Path):
        self.zip_path = Path(zip_path)
        self.report = ValidationReport()
        self._stop_ids: Set[str] = set()
        self._route_ids: Set[str] = set()
        self._trip_ids: Set[str] = set()
        self._service_ids: Set[str] = set()

    def validate(self) -> Tuple[bool, ValidationReport]:
        """Run all validations and return (is_valid, report)."""
        if not self.zip_path.exists():
            self.report.add_error(f"File not found: {self.zip_path}")
            return False, self.report

        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                self._validate_structure(zf)
                if self.report.is_valid:
                    self._validate_stops(zf)
                    self._validate_routes(zf)
                    self._validate_trips(zf)
                    self._validate_stop_times(zf)
                    self._validate_calendar(zf)
                    self._check_cross_references()
                    self._check_suspicious_data()
        except zipfile.BadZipFile:
            self.report.add_error("Invalid or corrupted ZIP file")
        except Exception as e:
            self.report.add_error(f"Validation error: {e}")

        return self.report.is_valid, self.report

    def _validate_structure(self, zf: zipfile.ZipFile):
        """Validate required files exist with required columns."""
        file_list = zf.namelist()

        # Check required files
        for filename, required_cols in self.REQUIRED_FILES.items():
            if filename not in file_list:
                self.report.add_error(f"Missing required file: {filename}")
                continue

            # Check columns
            with zf.open(filename) as f:
                reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
                if reader.fieldnames is None:
                    self.report.add_error(f"{filename}: Empty or invalid CSV")
                    continue

                fieldnames = [name.strip() for name in reader.fieldnames]
                missing = [col for col in required_cols if col not in fieldnames]
                if missing:
                    self.report.add_error(f"{filename}: Missing columns: {missing}")

        # Check calendar files (at least one must exist)
        has_calendar = any(f in file_list for f in self.CALENDAR_FILES)
        if not has_calendar:
            self.report.add_error(
                f"Missing calendar: need at least one of {self.CALENDAR_FILES}"
            )

    def _validate_stops(self, zf: zipfile.ZipFile):
        """Validate stops.txt data."""
        if 'stops.txt' not in zf.namelist():
            return

        count = 0
        invalid_coords = 0
        empty_names = 0

        with zf.open('stops.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
            reader.fieldnames = [name.strip() for name in reader.fieldnames]

            for row in reader:
                count += 1
                stop_id = row.get('stop_id', '').strip()

                if not stop_id:
                    self.report.add_error(f"stops.txt row {count}: Empty stop_id")
                    continue

                self._stop_ids.add(stop_id)

                # Check name
                stop_name = row.get('stop_name', '').strip()
                if not stop_name:
                    empty_names += 1

                # Check coordinates
                try:
                    lat = float(row.get('stop_lat', '0').strip())
                    lon = float(row.get('stop_lon', '0').strip())
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        invalid_coords += 1
                except (ValueError, TypeError):
                    invalid_coords += 1

        self.report.metrics.stops_count = count

        if empty_names > 0:
            self.report.add_warning(f"stops.txt: {empty_names} stops with empty names")
        if invalid_coords > 0:
            self.report.add_warning(f"stops.txt: {invalid_coords} stops with invalid coordinates")

    def _validate_routes(self, zf: zipfile.ZipFile):
        """Validate routes.txt data."""
        if 'routes.txt' not in zf.namelist():
            return

        count = 0
        empty_names = 0

        with zf.open('routes.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
            reader.fieldnames = [name.strip() for name in reader.fieldnames]

            for row in reader:
                count += 1
                route_id = row.get('route_id', '').strip()

                if not route_id:
                    self.report.add_error(f"routes.txt row {count}: Empty route_id")
                    continue

                self._route_ids.add(route_id)

                # Check short name
                short_name = row.get('route_short_name', '').strip()
                if not short_name:
                    empty_names += 1

        self.report.metrics.routes_count = count

        if empty_names > 0:
            self.report.add_warning(f"routes.txt: {empty_names} routes with empty short_name")

    def _validate_trips(self, zf: zipfile.ZipFile):
        """Validate trips.txt data."""
        if 'trips.txt' not in zf.namelist():
            return

        count = 0

        with zf.open('trips.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
            reader.fieldnames = [name.strip() for name in reader.fieldnames]

            for row in reader:
                count += 1
                trip_id = row.get('trip_id', '').strip()
                route_id = row.get('route_id', '').strip()
                service_id = row.get('service_id', '').strip()

                if not trip_id:
                    self.report.add_error(f"trips.txt row {count}: Empty trip_id")
                    continue

                self._trip_ids.add(trip_id)
                self._service_ids.add(service_id)

                # Store route references for cross-reference check
                if route_id:
                    self._trip_route_refs = getattr(self, '_trip_route_refs', {})
                    self._trip_route_refs[trip_id] = route_id

        self.report.metrics.trips_count = count

    def _validate_stop_times(self, zf: zipfile.ZipFile):
        """Validate stop_times.txt data."""
        if 'stop_times.txt' not in zf.namelist():
            return

        count = 0
        invalid_times = 0
        sample_invalid_times = []

        with zf.open('stop_times.txt') as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
            reader.fieldnames = [name.strip() for name in reader.fieldnames]

            for row in reader:
                count += 1
                trip_id = row.get('trip_id', '').strip()
                stop_id = row.get('stop_id', '').strip()

                if not trip_id or not stop_id:
                    if count <= 10:  # Only report first few
                        self.report.add_error(
                            f"stop_times.txt row {count}: Empty trip_id or stop_id"
                        )
                    continue

                # Store stop references for cross-reference check
                self._stop_time_stops = getattr(self, '_stop_time_stops', set())
                self._stop_time_stops.add(stop_id)

                self._stop_time_trips = getattr(self, '_stop_time_trips', set())
                self._stop_time_trips.add(trip_id)

                # Validate time format
                arrival = row.get('arrival_time', '').strip()
                departure = row.get('departure_time', '').strip()

                for time_str in [arrival, departure]:
                    if time_str and not self.TIME_REGEX.match(time_str):
                        invalid_times += 1
                        if len(sample_invalid_times) < 3:
                            sample_invalid_times.append(time_str)

        self.report.metrics.stop_times_count = count

        if invalid_times > 0:
            samples = ', '.join(sample_invalid_times)
            self.report.add_warning(
                f"stop_times.txt: {invalid_times} invalid time formats (e.g., {samples})"
            )

    def _validate_calendar(self, zf: zipfile.ZipFile):
        """Validate calendar.txt and calendar_dates.txt."""
        file_list = zf.namelist()
        min_date = None
        max_date = None

        # calendar.txt
        if 'calendar.txt' in file_list:
            count = 0
            invalid_dates = 0

            with zf.open('calendar.txt') as f:
                reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
                reader.fieldnames = [name.strip() for name in reader.fieldnames]

                for row in reader:
                    count += 1
                    service_id = row.get('service_id', '').strip()
                    if service_id:
                        self._service_ids.add(service_id)

                    start_date = row.get('start_date', '').strip()
                    end_date = row.get('end_date', '').strip()

                    for date_str in [start_date, end_date]:
                        if date_str:
                            if self.DATE_REGEX.match(date_str):
                                if min_date is None or date_str < min_date:
                                    min_date = date_str
                                if max_date is None or date_str > max_date:
                                    max_date = date_str
                            else:
                                invalid_dates += 1

            self.report.metrics.calendar_entries = count

            if invalid_dates > 0:
                self.report.add_warning(f"calendar.txt: {invalid_dates} invalid date formats")

        # calendar_dates.txt
        if 'calendar_dates.txt' in file_list:
            count = 0
            invalid_dates = 0

            with zf.open('calendar_dates.txt') as f:
                reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
                reader.fieldnames = [name.strip() for name in reader.fieldnames]

                for row in reader:
                    count += 1
                    service_id = row.get('service_id', '').strip()
                    if service_id:
                        self._service_ids.add(service_id)

                    date_str = row.get('date', '').strip()
                    if date_str:
                        if self.DATE_REGEX.match(date_str):
                            if min_date is None or date_str < min_date:
                                min_date = date_str
                            if max_date is None or date_str > max_date:
                                max_date = date_str
                        else:
                            invalid_dates += 1

            self.report.metrics.calendar_dates_entries = count

            if invalid_dates > 0:
                self.report.add_warning(f"calendar_dates.txt: {invalid_dates} invalid date formats")

        # Format dates for display
        if min_date:
            self.report.metrics.start_date = f"{min_date[:4]}-{min_date[4:6]}-{min_date[6:8]}"
        if max_date:
            self.report.metrics.end_date = f"{max_date[:4]}-{max_date[4:6]}-{max_date[6:8]}"

    def _check_cross_references(self):
        """Check cross-reference integrity."""
        # Check trips reference valid routes
        if hasattr(self, '_trip_route_refs'):
            invalid_routes = set()
            for trip_id, route_id in self._trip_route_refs.items():
                if route_id not in self._route_ids:
                    invalid_routes.add(route_id)

            if invalid_routes:
                sample = list(invalid_routes)[:3]
                self.report.add_warning(
                    f"trips.txt: {len(invalid_routes)} trips reference non-existent routes "
                    f"(e.g., {sample})"
                )

        # Check stop_times reference valid trips
        if hasattr(self, '_stop_time_trips'):
            invalid_trips = self._stop_time_trips - self._trip_ids
            if invalid_trips:
                sample = list(invalid_trips)[:3]
                self.report.add_warning(
                    f"stop_times.txt: References {len(invalid_trips)} non-existent trips "
                    f"(e.g., {sample})"
                )

        # Check stop_times reference valid stops
        if hasattr(self, '_stop_time_stops'):
            invalid_stops = self._stop_time_stops - self._stop_ids
            if invalid_stops:
                sample = list(invalid_stops)[:3]
                self.report.add_warning(
                    f"stop_times.txt: References {len(invalid_stops)} non-existent stops "
                    f"(e.g., {sample})"
                )

    def _check_suspicious_data(self):
        """Check for suspicious data patterns."""
        m = self.report.metrics

        # Check for zero counts
        if m.trips_count == 0:
            self.report.add_warning("No trips found in GTFS data")
        if m.stop_times_count == 0:
            self.report.add_warning("No stop_times found in GTFS data")

        # Check for expired data
        if m.end_date:
            try:
                end_dt = datetime.strptime(m.end_date, '%Y-%m-%d')
                if end_dt < datetime.now():
                    self.report.add_warning(
                        f"Calendar data has expired (end_date: {m.end_date})"
                    )
            except ValueError:
                pass

        # Check for future-only data
        if m.start_date:
            try:
                start_dt = datetime.strptime(m.start_date, '%Y-%m-%d')
                days_until_start = (start_dt - datetime.now()).days
                if days_until_start > 30:
                    self.report.add_warning(
                        f"Calendar data starts in the future ({m.start_date})"
                    )
            except ValueError:
                pass


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Validate GTFS data structure and integrity'
    )
    parser.add_argument('zip_path', help='Path to GTFS zip file to validate')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed validation output'
    )

    args = parser.parse_args()

    validator = GTFSValidator(args.zip_path)

    logger.info(f"Validating {args.zip_path}...")
    is_valid, report = validator.validate()

    print("\n" + "=" * 60)
    print("GTFS VALIDATION REPORT")
    print("=" * 60)
    print(report)
    print("=" * 60)

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
