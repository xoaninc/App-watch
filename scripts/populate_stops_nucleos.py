#!/usr/bin/env python3
"""Populate stops with nucleo data using PostGIS spatial queries.

This script updates the nucleo field for all stops using accurate PostGIS
spatial queries to determine which nucleo contains each stop.

Usage:
    # Update only stops without nucleo:
    python scripts/populate_stops_nucleos.py

    # Force update ALL stops:
    python scripts/populate_stops_nucleos.py --force
"""

import sys
import argparse
import logging
from sqlalchemy import text
from core.database import SessionLocal
from src.gtfs_bc.stop.infrastructure.models import StopModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def populate_stops_nucleos(db, force_update: bool = False) -> dict:
    """Populate nucleo field using PostGIS spatial queries.

    Args:
        db: Database session
        force_update: If True, update all stops. If False, only update stops without nucleo.

    Returns:
        Dictionary with statistics
    """
    # Get stops to update
    query = db.query(StopModel)
    if not force_update:
        query = query.filter(StopModel.nucleo_id == None)

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
                # Query nucleo using PostGIS
                result = db.execute(
                    text("""
                        SELECT id, name
                        FROM gtfs_nucleos
                        WHERE ST_Contains(
                            ST_MakeEnvelope(
                                bounding_box_min_lon,
                                bounding_box_min_lat,
                                bounding_box_max_lon,
                                bounding_box_max_lat,
                                4326
                            ),
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                        )
                        LIMIT 1
                    """),
                    {'lat': stop.lat, 'lon': stop.lon}
                ).fetchone()

                if result:
                    nucleo_id, nucleo_name = result
                    if stop.nucleo_id != nucleo_id:
                        old_nucleo = stop.nucleo_name
                        stop.nucleo_id = nucleo_id
                        stop.nucleo_name = nucleo_name
                        stats['updated'] += 1
                        if old_nucleo:
                            logger.debug(f"Updated {stop.id}: {old_nucleo} -> {nucleo_name}")
                        else:
                            logger.debug(f"Set {stop.id}: {nucleo_name}")
                    else:
                        stats['unchanged'] += 1
                else:
                    stats['not_found'] += 1
                    logger.warning(f"No nucleo found for stop {stop.id} at ({stop.lat}, {stop.lon})")

            except Exception as e:
                logger.error(f"Error processing stop {stop.id}: {e}")
                stats['not_found'] += 1

        # Commit batch
        db.commit()
        logger.info(f"Processed {min(i+batch_size, total_stops)}/{total_stops} stops")

    return stats


def validate_nucleo_distribution(db) -> None:
    """Print distribution of stops across nucleos."""
    logger.info("\nNucleo distribution:")

    results = db.execute(
        text("""
            SELECT nucleo_name, COUNT(*) as count
            FROM gtfs_stops
            WHERE nucleo_id IS NOT NULL
            GROUP BY nucleo_name
            ORDER BY count DESC
        """)
    ).fetchall()

    for row in results:
        logger.info(f"  {row.nucleo_name}: {row.count} stops")

    null_count = db.execute(
        text("SELECT COUNT(*) FROM gtfs_stops WHERE nucleo_id IS NULL")
    ).scalar()

    if null_count > 0:
        logger.warning(f"  NULL: {null_count} stops")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Populate stops with nucleo data using PostGIS'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force update all stops, not just those without nucleo'
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Run population
        stats = populate_stops_nucleos(db, force_update=args.force)

        # Print summary
        logger.info("\n" + "="*50)
        logger.info("Stop Population Summary")
        logger.info("="*50)
        logger.info(f"Total stops processed: {stats['total_stops']}")
        logger.info(f"Updated: {stats['updated']}")
        logger.info(f"Unchanged: {stats['unchanged']}")
        logger.info(f"Not found: {stats['not_found']}")
        logger.info("="*50)

        # Show distribution
        validate_nucleo_distribution(db)

        logger.info("\nStop population completed successfully")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
