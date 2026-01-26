#!/usr/bin/env python3
"""Import platform coordinates and correspondences from CSV.

This script reads estaciones_espana_completo.csv and:
1. Updates line_transfer with platform coordinates
2. Updates gtfs_stops.cor_* fields
3. Stores discrepancies for manual review when DB and CSV values differ

Usage:
    python scripts/import_platform_coords.py [--dry-run]
"""

import sys
import csv
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database import SessionLocal
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.transfer.infrastructure.models import LineTransferModel, CorrespondenceDiscrepancyModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# CSV file path
CSV_PATH = project_root / "docs" / "estaciones_espana_completo.csv"

# Mapping from CSV network names to DB stop prefixes
NETWORK_TO_PREFIX = {
    "Euskotren": "EUSKOTREN_",
    "FGC": "FGC_",
    "Metro Bilbao": "METRO_BILBAO_",
    "Metro Madrid": "METRO_",
    "Renfe Cercanías": "RENFE_",
}

# Mapping from CSV column names to DB field names
COR_FIELD_MAPPING = {
    "cor_metro_bilbao": "cor_metro",
    "cor_metro_madrid": "cor_metro",
    "cor_fgc": "cor_cercanias",  # FGC goes in cor_cercanias for non-FGC stops
    "cor_renfe_cercanias": "cor_cercanias",
    "cor_euskotren": "cor_cercanias",  # Euskotren lines go in cor_cercanias
}


def parse_platform_coords(coords_str: str) -> Dict[str, List[Tuple[float, float]]]:
    """Parse platform_coords_by_line string into dict of line -> [(lat, lon), ...].

    Format: "L1:[40.123,-3.456|40.124,-3.457]; L2:[40.125,-3.458]"
    """
    result = {}
    if not coords_str:
        return result

    # Split by semicolon, then parse each line's coords
    parts = coords_str.split(";")
    for part in parts:
        part = part.strip()
        if not part or ":" not in part:
            continue

        # Extract line name and coords
        match = re.match(r'([^:]+):\[([^\]]+)\]', part)
        if not match:
            continue

        line_name = match.group(1).strip()
        coords_part = match.group(2).strip()

        # Parse coordinates (may have multiple separated by |)
        coords_list = []
        for coord_pair in coords_part.split("|"):
            coord_pair = coord_pair.strip()
            if "," in coord_pair:
                try:
                    lat_str, lon_str = coord_pair.split(",")
                    lat = float(lat_str.strip())
                    lon = float(lon_str.strip())
                    coords_list.append((lat, lon))
                except ValueError:
                    continue

        if coords_list:
            result[line_name] = coords_list

    return result


def parse_correspondence(cor_str: str) -> Dict[str, int]:
    """Parse correspondence string like "Abando (86m)" into dict.

    Returns: {"Abando": 86} (name -> distance in meters)
    """
    result = {}
    if not cor_str:
        return result

    # Split by semicolon for multiple correspondences
    parts = cor_str.split(";")
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract name and distance: "Name (123m)"
        match = re.match(r'(.+?)\s*\((\d+)m\)', part)
        if match:
            name = match.group(1).strip()
            distance = int(match.group(2))
            result[name] = distance

    return result


def normalize_lines(lines_str: str) -> Set[str]:
    """Normalize a lines string into a set of line names."""
    if not lines_str:
        return set()

    # Split by comma or semicolon
    lines = re.split(r'[,;]', lines_str)
    return {line.strip() for line in lines if line.strip()}


def find_stop_in_db(db, stop_name: str, network: str) -> Optional[StopModel]:
    """Find a stop in the database by name and network."""
    prefix = NETWORK_TO_PREFIX.get(network)
    if not prefix:
        return None

    # Try exact match first
    stop = db.query(StopModel).filter(
        StopModel.id.like(f"{prefix}%"),
        StopModel.name.ilike(stop_name)
    ).first()

    if stop:
        return stop

    # Try partial match
    stop = db.query(StopModel).filter(
        StopModel.id.like(f"{prefix}%"),
        StopModel.name.ilike(f"%{stop_name}%")
    ).first()

    return stop


def check_and_record_discrepancy(
    db,
    stop: StopModel,
    field: str,
    db_value: Optional[str],
    csv_value: Optional[str],
    dry_run: bool = False
) -> bool:
    """Compare DB and CSV values, record discrepancy if different.

    Returns True if there was a discrepancy.
    """
    # Normalize both values for comparison
    db_lines = normalize_lines(db_value)
    csv_lines = normalize_lines(csv_value)

    if db_lines == csv_lines:
        return False

    # Determine discrepancy type
    if not db_lines and csv_lines:
        discrepancy_type = "missing_in_db"
    elif db_lines and not csv_lines:
        discrepancy_type = "missing_in_csv"
    else:
        discrepancy_type = "different"

    logger.warning(
        f"Discrepancy in {stop.name}.{field}: "
        f"DB='{db_value}' vs CSV='{csv_value}'"
    )

    if not dry_run:
        # Check if this discrepancy already exists
        existing = db.query(CorrespondenceDiscrepancyModel).filter(
            CorrespondenceDiscrepancyModel.stop_id == stop.id,
            CorrespondenceDiscrepancyModel.field == field,
            CorrespondenceDiscrepancyModel.reviewed == False
        ).first()

        if not existing:
            discrepancy = CorrespondenceDiscrepancyModel(
                stop_id=stop.id,
                stop_name=stop.name,
                field=field,
                value_in_db=db_value,
                value_in_csv=csv_value,
                discrepancy_type=discrepancy_type
            )
            db.add(discrepancy)

    return True


def import_from_csv(dry_run: bool = False):
    """Main import function."""
    if not CSV_PATH.exists():
        logger.error(f"CSV file not found: {CSV_PATH}")
        return

    db = SessionLocal()

    stats = {
        "rows_processed": 0,
        "stops_found": 0,
        "stops_not_found": 0,
        "discrepancies_found": 0,
        "cor_fields_updated": 0,
        "line_transfers_created": 0,
    }

    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                stats["rows_processed"] += 1

                network = row.get("network", "")
                stop_name = row.get("stop_name", "")
                lines = row.get("lines", "")
                platform_coords = row.get("platform_coords_by_line", "")

                if not network or not stop_name:
                    continue

                # Find stop in DB
                stop = find_stop_in_db(db, stop_name, network)

                if not stop:
                    stats["stops_not_found"] += 1
                    logger.debug(f"Stop not found: {network} - {stop_name}")
                    continue

                stats["stops_found"] += 1

                # Check correspondences for discrepancies
                # Process each cor_* field from CSV
                for csv_col, db_field in COR_FIELD_MAPPING.items():
                    csv_value = row.get(csv_col, "")
                    if not csv_value:
                        continue

                    # Parse correspondence to get just the names (without distances)
                    cor_dict = parse_correspondence(csv_value)
                    csv_cor_names = ", ".join(sorted(cor_dict.keys()))

                    db_value = getattr(stop, db_field, None)

                    if check_and_record_discrepancy(db, stop, db_field, db_value, csv_cor_names, dry_run):
                        stats["discrepancies_found"] += 1

                # Parse platform coordinates
                coords_by_line = parse_platform_coords(platform_coords)

                # Update line_transfer with coordinates
                # For each correspondence in the CSV, create/update line_transfer entries
                for csv_col in ["cor_metro_bilbao", "cor_metro_madrid", "cor_fgc", "cor_renfe_cercanias", "cor_euskotren"]:
                    csv_value = row.get(csv_col, "")
                    if not csv_value:
                        continue

                    cor_dict = parse_correspondence(csv_value)

                    for cor_name, distance in cor_dict.items():
                        # Find the target stop
                        target_stop = db.query(StopModel).filter(
                            StopModel.name.ilike(f"%{cor_name}%")
                        ).first()

                        if not target_stop:
                            continue

                        # Get coordinates for the lines at this stop
                        for line_name, coords_list in coords_by_line.items():
                            if not coords_list:
                                continue

                            # Use first coordinate for this line
                            from_lat, from_lon = coords_list[0]

                            if not dry_run:
                                # Check if transfer already exists
                                existing = db.query(LineTransferModel).filter(
                                    LineTransferModel.from_stop_id == stop.id,
                                    LineTransferModel.to_stop_id == target_stop.id,
                                    LineTransferModel.from_line == line_name
                                ).first()

                                if existing:
                                    # Update coordinates
                                    existing.from_lat = from_lat
                                    existing.from_lon = from_lon
                                else:
                                    # Create new transfer
                                    transfer = LineTransferModel(
                                        from_stop_id=stop.id,
                                        to_stop_id=target_stop.id,
                                        from_stop_name=stop.name,
                                        to_stop_name=target_stop.name,
                                        from_line=line_name,
                                        from_lat=from_lat,
                                        from_lon=from_lon,
                                        min_transfer_time=distance * 60 // 80,  # Estimate: 80m/min walking
                                        transfer_type=2,  # Minimum time required
                                        source="csv_import"
                                    )
                                    db.add(transfer)
                                    stats["line_transfers_created"] += 1

                # Commit every 100 rows
                if stats["rows_processed"] % 100 == 0:
                    if not dry_run:
                        db.commit()
                    logger.info(f"Processed {stats['rows_processed']} rows...")

        if not dry_run:
            db.commit()

        logger.info("=" * 50)
        logger.info("IMPORT COMPLETE")
        logger.info("=" * 50)
        logger.info(f"Rows processed: {stats['rows_processed']}")
        logger.info(f"Stops found in DB: {stats['stops_found']}")
        logger.info(f"Stops not found: {stats['stops_not_found']}")
        logger.info(f"Discrepancies recorded: {stats['discrepancies_found']}")
        logger.info(f"Line transfers created: {stats['line_transfers_created']}")

        if stats["discrepancies_found"] > 0:
            logger.warning(
                f"\n{stats['discrepancies_found']} discrepancies found. "
                "Review them in the correspondence_discrepancies table."
            )

    except Exception as e:
        logger.error(f"Error during import: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    import_from_csv(dry_run=dry_run)
