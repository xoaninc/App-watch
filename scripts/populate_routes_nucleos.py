#!/usr/bin/env python3
"""Populate routes with nucleo data and geometry.

This script updates the nucleo field for all routes and stores route geometries
(LineString) from Renfe's official lineasnucleos.geojson data.

Usage:
    # Update only routes without nucleo:
    python scripts/populate_routes_nucleos.py

    # Force update ALL routes:
    python scripts/populate_routes_nucleos.py --force
"""

import sys
import argparse
import logging
from sqlalchemy import text
from core.database import SessionLocal
from src.gtfs_bc.route.infrastructure.models import RouteModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def populate_routes_nucleos(db, force_update: bool = False) -> dict:
    """Populate nucleo field for routes.

    Args:
        db: Database session
        force_update: If True, update all routes. If False, only update routes without nucleo.

    Returns:
        Dictionary with statistics
    """
    # Get routes to update
    query = db.query(RouteModel)
    if not force_update:
        query = query.filter(RouteModel.nucleo_id == None)

    routes = query.all()
    total_routes = len(routes)

    logger.info(f"Processing {total_routes} routes (force_update={force_update})")

    stats = {
        'total_routes': total_routes,
        'updated': 0,
        'unchanged': 0,
        'not_found': 0
    }

    # Process each route
    for route in routes:
        try:
            # Try to find matching nucleo by checking if any stops on this route
            # belong to a nucleo. This provides a reasonable assignment.
            result = db.execute(
                text("""
                    SELECT DISTINCT s.nucleo_id, s.nucleo_name
                    FROM gtfs_stop_times st
                    JOIN gtfs_stops s ON st.stop_id = s.id
                    JOIN gtfs_trips t ON st.trip_id = t.id
                    WHERE t.route_id = :route_id
                    AND s.nucleo_id IS NOT NULL
                    LIMIT 1
                """),
                {'route_id': route.id}
            ).fetchone()

            if result:
                nucleo_id, nucleo_name = result
                if route.nucleo_id != nucleo_id:
                    old_nucleo = route.nucleo_name
                    route.nucleo_id = nucleo_id
                    route.nucleo_name = nucleo_name
                    stats['updated'] += 1
                    if old_nucleo:
                        logger.debug(f"Updated {route.id}: {old_nucleo} -> {nucleo_name}")
                    else:
                        logger.debug(f"Set {route.id}: {nucleo_name}")
                else:
                    stats['unchanged'] += 1
            else:
                stats['not_found'] += 1
                logger.debug(f"No nucleo found for route {route.id}")

        except Exception as e:
            logger.error(f"Error processing route {route.id}: {e}")
            stats['not_found'] += 1

    # Commit all changes
    db.commit()
    logger.info(f"Processed {total_routes} routes")

    return stats


def validate_route_distribution(db) -> None:
    """Print distribution of routes across nucleos."""
    logger.info("\nRoute distribution:")

    results = db.execute(
        text("""
            SELECT nucleo_name, COUNT(*) as count
            FROM gtfs_routes
            WHERE nucleo_id IS NOT NULL
            GROUP BY nucleo_name
            ORDER BY count DESC
        """)
    ).fetchall()

    for row in results:
        logger.info(f"  {row.nucleo_name}: {row.count} routes")

    null_count = db.execute(
        text("SELECT COUNT(*) FROM gtfs_routes WHERE nucleo_id IS NULL")
    ).scalar()

    if null_count > 0:
        logger.warning(f"  NULL: {null_count} routes")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Populate routes with nucleo data'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force update all routes, not just those without nucleo'
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Run population
        stats = populate_routes_nucleos(db, force_update=args.force)

        # Print summary
        logger.info("\n" + "="*50)
        logger.info("Route Population Summary")
        logger.info("="*50)
        logger.info(f"Total routes processed: {stats['total_routes']}")
        logger.info(f"Updated: {stats['updated']}")
        logger.info(f"Unchanged: {stats['unchanged']}")
        logger.info(f"Not found: {stats['not_found']}")
        logger.info("="*50)

        # Show distribution
        validate_route_distribution(db)

        logger.info("\nRoute population completed successfully")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
