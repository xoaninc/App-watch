#!/usr/bin/env python3
"""Import FGC Geotren real-time train positions with occupancy.

Fetches real-time train positions from FGC's Geotren service, which includes
occupancy data per car that is not available in standard GTFS-RT.

Source: https://dadesobertes.fgc.cat/explore/dataset/posicionament-dels-trens/

Fields:
- Position: geo_point_2d (lat/lon)
- Route: lin (line), dir (direction), origen, desti
- Status: en_hora (on time), estacionat_a (stationed at)
- Vehicle: ut (unit ID), tipus_unitat (model)
- Occupancy per car: mi (middle), ri (rear), m1/m2 (motor cars)

Usage:
    python scripts/import_fgc_geotren.py [--dry-run] [--once]

Note: Run periodically (e.g., every 30 seconds) to capture real-time data.
Occupancy fields may be null when no trains are running (late night).
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FGC Open Data API endpoint
GEOTREN_URL = "https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/posicionament-dels-trens/records"


def fetch_geotren_positions() -> List[Dict]:
    """Fetch current train positions from Geotren API.

    Returns:
        List of position records with all available fields.
    """
    logger.info("Fetching Geotren positions...")

    params = {
        'limit': 100,  # Should be enough for all active trains
    }

    try:
        response = requests.get(GEOTREN_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        records = data.get('results', [])
        total = data.get('total_count', 0)

        logger.info(f"  Fetched {len(records)}/{total} positions")
        return records

    except Exception as e:
        logger.error(f"Error fetching Geotren data: {e}")
        raise


def parse_position(record: Dict) -> Dict:
    """Parse a Geotren record into our database format.

    Args:
        record: Raw record from API

    Returns:
        Parsed record dict ready for database insertion
    """
    # Extract coordinates from geo_point_2d
    geo_point = record.get('geo_point_2d', {})
    lat = geo_point.get('lat') if geo_point else None
    lon = geo_point.get('lon') if geo_point else None

    # Parse on_time boolean
    en_hora = record.get('en_hora')
    if isinstance(en_hora, str):
        on_time = en_hora.lower() in ('true', '1', 'yes')
    elif isinstance(en_hora, bool):
        on_time = en_hora
    else:
        on_time = None

    # Parse occupancy percentages (may be null or string)
    def parse_percent(value) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    return {
        'id': record.get('id', ''),
        'vehicle_id': record.get('ut', ''),
        'line': record.get('lin', ''),
        'direction': record.get('dir', ''),
        'origin': record.get('origen', ''),
        'destination': record.get('desti', ''),
        'next_stops': record.get('properes_parades', ''),
        'stationed_at': record.get('estacionat_a'),
        'on_time': on_time,
        'unit_type': record.get('tipus_unitat', ''),
        'latitude': lat,
        'longitude': lon,
        # Occupancy fields
        'occupancy_mi_percent': parse_percent(record.get('ocupacio_mi_percent')),
        'occupancy_mi_level': record.get('ocupacio_mi_tram'),
        'occupancy_ri_percent': parse_percent(record.get('ocupacio_ri_percent')),
        'occupancy_ri_level': record.get('ocupacio_ri_tram'),
        'occupancy_m1_percent': parse_percent(record.get('ocupacio_m1_percent')),
        'occupancy_m1_level': record.get('ocupacio_m1_tram'),
        'occupancy_m2_percent': parse_percent(record.get('ocupacio_m2_percent')),
        'occupancy_m2_level': record.get('ocupacio_m2_tram'),
    }


def save_positions(db, positions: List[Dict], dry_run: bool = False) -> Dict[str, int]:
    """Save positions to database.

    Uses UPSERT to update existing records or insert new ones.

    Args:
        db: Database session
        positions: List of parsed position dicts
        dry_run: If True, don't make changes

    Returns:
        Stats dict with counts
    """
    stats = {
        'total': len(positions),
        'with_occupancy': 0,
        'inserted': 0,
        'updated': 0,
    }

    for pos in positions:
        # Count positions with any occupancy data
        if any([
            pos.get('occupancy_mi_percent'),
            pos.get('occupancy_ri_percent'),
            pos.get('occupancy_m1_percent'),
            pos.get('occupancy_m2_percent'),
        ]):
            stats['with_occupancy'] += 1

        if dry_run:
            logger.info(f"  [DRY] Train {pos['vehicle_id']}: Line {pos['line']}, "
                       f"Dir {pos['direction']}, At {pos['stationed_at']}")
            continue

        # UPSERT: Insert or update on conflict
        result = db.execute(text("""
            INSERT INTO fgc_geotren_positions (
                id, vehicle_id, line, direction, origin, destination,
                next_stops, stationed_at, on_time, unit_type,
                latitude, longitude,
                occupancy_mi_percent, occupancy_mi_level,
                occupancy_ri_percent, occupancy_ri_level,
                occupancy_m1_percent, occupancy_m1_level,
                occupancy_m2_percent, occupancy_m2_level,
                timestamp, updated_at
            ) VALUES (
                :id, :vehicle_id, :line, :direction, :origin, :destination,
                :next_stops, :stationed_at, :on_time, :unit_type,
                :latitude, :longitude,
                :occupancy_mi_percent, :occupancy_mi_level,
                :occupancy_ri_percent, :occupancy_ri_level,
                :occupancy_m1_percent, :occupancy_m1_level,
                :occupancy_m2_percent, :occupancy_m2_level,
                NOW(), NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                vehicle_id = EXCLUDED.vehicle_id,
                line = EXCLUDED.line,
                direction = EXCLUDED.direction,
                origin = EXCLUDED.origin,
                destination = EXCLUDED.destination,
                next_stops = EXCLUDED.next_stops,
                stationed_at = EXCLUDED.stationed_at,
                on_time = EXCLUDED.on_time,
                unit_type = EXCLUDED.unit_type,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                occupancy_mi_percent = EXCLUDED.occupancy_mi_percent,
                occupancy_mi_level = EXCLUDED.occupancy_mi_level,
                occupancy_ri_percent = EXCLUDED.occupancy_ri_percent,
                occupancy_ri_level = EXCLUDED.occupancy_ri_level,
                occupancy_m1_percent = EXCLUDED.occupancy_m1_percent,
                occupancy_m1_level = EXCLUDED.occupancy_m1_level,
                occupancy_m2_percent = EXCLUDED.occupancy_m2_percent,
                occupancy_m2_level = EXCLUDED.occupancy_m2_level,
                updated_at = NOW()
        """), pos)

        stats['inserted'] += 1

    if not dry_run:
        db.commit()

    return stats


def verify_data(db) -> None:
    """Print current data summary."""
    logger.info("\nData verification:")

    # Count total positions
    total = db.execute(text(
        "SELECT COUNT(*) FROM fgc_geotren_positions"
    )).scalar()

    # Count positions with occupancy
    with_occ = db.execute(text("""
        SELECT COUNT(*) FROM fgc_geotren_positions
        WHERE occupancy_mi_percent IS NOT NULL
           OR occupancy_ri_percent IS NOT NULL
           OR occupancy_m1_percent IS NOT NULL
           OR occupancy_m2_percent IS NOT NULL
    """)).scalar()

    # Get line distribution
    by_line = db.execute(text("""
        SELECT line, COUNT(*) as cnt
        FROM fgc_geotren_positions
        GROUP BY line
        ORDER BY line
    """)).fetchall()

    logger.info(f"  Total positions stored: {total}")
    logger.info(f"  With occupancy data: {with_occ}")
    logger.info(f"  By line: {dict(by_line) if by_line else 'none'}")


def main():
    parser = argparse.ArgumentParser(
        description='Import FGC Geotren real-time positions with occupancy'
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without saving')
    parser.add_argument('--once', action='store_true',
                       help='Run once and exit (default behavior)')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made\n")

        # Fetch positions
        records = fetch_geotren_positions()

        if not records:
            logger.warning("No train positions available (trains may not be running)")
            return

        # Parse records
        positions = [parse_position(r) for r in records]

        # Save to database
        stats = save_positions(db, positions, dry_run=args.dry_run)

        logger.info("\n" + "=" * 60)
        logger.info("GEOTREN IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Positions fetched: {stats['total']}")
        logger.info(f"With occupancy data: {stats['with_occupancy']}")
        if not args.dry_run:
            logger.info(f"Records saved: {stats['inserted']}")
            verify_data(db)
        else:
            logger.info("[DRY RUN - no changes saved]")
        logger.info("=" * 60)

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
