#!/usr/bin/env python3
"""Re-populate province field in gtfs_stops using accurate PostGIS boundaries.

This script updates the province field for all stops (or only those without
a province) using accurate PostGIS polygon boundaries instead of bounding boxes.

Usage:
    # Update only stops without province:
    python scripts/populate_provinces.py

    # Force update ALL stops:
    python scripts/populate_provinces.py --force
"""

import sys
import argparse
import logging
from sqlalchemy import text
from core.database import SessionLocal
from src.gtfs_bc.stop.infrastructure.models import StopModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def populate_provinces_postgis(db, force_update: bool = False) -> dict:
    """Populate province field using PostGIS spatial queries.

    Args:
        db: Database session
        force_update: If True, update all stops. If False, only update stops without province.

    Returns:
        Dictionary with statistics: {
            'total_stops': int,
            'updated': int,
            'unchanged': int,
            'not_found': int
        }
    """
    # Get stops to update
    query = db.query(StopModel)
    if not force_update:
        query = query.filter(StopModel.province == None)

    stops = query.all()
    total_stops = len(stops)

    logger.info(f"Processing {total_stops} stops (force_update={force_update})")

    stats = {
        'total_stops': total_stops,
        'updated': 0,
        'unchanged': 0,
        'not_found': 0
    }

    # Process in batches for efficiency
    batch_size = 100
    for i in range(0, total_stops, batch_size):
        batch = stops[i:i+batch_size]

        for stop in batch:
            try:
                # Query province using PostGIS
                result = db.execute(
                    text("""
                        SELECT name
                        FROM spanish_provinces
                        WHERE ST_Contains(
                            geometry,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                        )
                        LIMIT 1
                    """),
                    {'lat': stop.lat, 'lon': stop.lon}
                ).fetchone()

                if result:
                    new_province = result[0]
                    if stop.province != new_province:
                        old_province = stop.province
                        stop.province = new_province
                        stats['updated'] += 1
                        if old_province:
                            logger.debug(f"Updated {stop.id}: {old_province} -> {new_province}")
                        else:
                            logger.debug(f"Set {stop.id}: {new_province}")
                    else:
                        stats['unchanged'] += 1
                else:
                    stats['not_found'] += 1
                    logger.warning(f"No province found for stop {stop.id} at ({stop.lat}, {stop.lon})")

            except Exception as e:
                logger.error(f"Error processing stop {stop.id}: {e}")
                stats['not_found'] += 1

        # Commit batch
        db.commit()
        logger.info(f"Processed {min(i+batch_size, total_stops)}/{total_stops} stops")

    return stats


def validate_province_distribution(db) -> None:
    """Print distribution of stops across provinces."""
    logger.info("\nProvince distribution:")

    results = db.execute(
        text("""
            SELECT province, COUNT(*) as count
            FROM gtfs_stops
            WHERE province IS NOT NULL
            GROUP BY province
            ORDER BY count DESC
        """)
    ).fetchall()

    for row in results:
        logger.info(f"  {row.province}: {row.count} stops")

    null_count = db.execute(
        text("SELECT COUNT(*) FROM gtfs_stops WHERE province IS NULL")
    ).scalar()

    if null_count > 0:
        logger.warning(f"  NULL: {null_count} stops")


def main():
    parser = argparse.ArgumentParser(
        description='Populate province field using PostGIS boundaries'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force update all stops, not just those without province'
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Run population
        stats = populate_provinces_postgis(db, force_update=args.force)

        # Print summary
        logger.info("\n" + "="*50)
        logger.info("Province Population Summary")
        logger.info("="*50)
        logger.info(f"Total stops processed: {stats['total_stops']}")
        logger.info(f"Updated: {stats['updated']}")
        logger.info(f"Unchanged: {stats['unchanged']}")
        logger.info(f"Not found: {stats['not_found']}")
        logger.info("="*50)

        # Show distribution
        validate_province_distribution(db)

        logger.info("\nProvince population completed successfully")

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
