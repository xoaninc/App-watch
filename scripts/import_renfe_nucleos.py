#!/usr/bin/env python3
"""Import Renfe núcleo data from official GeoJSON sources.

This script downloads estaciones.geojson and lineasnucleos.geojson from Renfe's
official API and imports them into the database, creating the gtfs_nucleos table
with all 12 regional networks and updating stops/routes with nucleo information.

Usage:
    python scripts/import_renfe_nucleos.py
"""

import sys
import logging
from sqlalchemy import text
from core.database import SessionLocal
from src.gtfs_bc.nucleo.infrastructure.services import RenfeGeoJSONImporter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Run the Renfe GeoJSON import."""
    db = SessionLocal()
    try:
        logger.info("Starting Renfe GeoJSON import...")
        importer = RenfeGeoJSONImporter(db)
        stats = importer.import_nucleos()

        # Print summary
        logger.info("\n" + "="*60)
        logger.info("Import Summary")
        logger.info("="*60)
        logger.info(f"Nucleos created: {stats['nucleos_created']}")
        logger.info(f"Nucleos updated: {stats['nucleos_updated']}")
        logger.info(f"Stops updated: {stats['stops_updated']}")
        logger.info(f"Stops created: {stats['stops_created']}")
        logger.info(f"Routes updated: {stats['routes_updated']}")
        logger.info(f"Routes created: {stats['routes_created']}")
        logger.info("="*60)

        # Verify import
        logger.info("\nVerifying import...")
        nucleos_count = db.execute(text(
            "SELECT COUNT(*) as count FROM gtfs_nucleos"
        )).scalar()
        logger.info(f"Total nucleos in database: {nucleos_count}")

        logger.info("\nRenfe GeoJSON import completed successfully!")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
