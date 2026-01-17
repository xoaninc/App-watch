#!/usr/bin/env python3
"""Script to import Metro Madrid frequencies from GTFS."""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database import SessionLocal

# Import all models to ensure relationships are configured
from src.gtfs_bc.nucleo.infrastructure.models import NucleoModel
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel, RouteFrequencyModel
from src.gtfs_bc.stop_route_sequence.infrastructure.models import StopRouteSequenceModel

from src.gtfs_bc.metro.infrastructure.services import MetroFrequencyImporter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def print_usage():
    """Print usage instructions."""
    print("Usage: python import_metro_frequencies.py <metro_gtfs_path> [ml_gtfs_path]")
    print("")
    print("Arguments:")
    print("  metro_gtfs_path  Path to Metro Madrid GTFS zip file (required)")
    print("  ml_gtfs_path     Path to Metro Ligero GTFS zip file (optional)")
    print("")
    print("Example:")
    print("  python import_metro_frequencies.py ./data/google_transit_M4.zip ./data/google_transit_M10.zip")


def main():
    """Run the Metro frequency import."""
    # Require at least the Metro GTFS path
    if len(sys.argv) < 2:
        logger.error("Missing required argument: metro_gtfs_path")
        print_usage()
        sys.exit(1)

    metro_gtfs_path = sys.argv[1]
    ml_gtfs_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not Path(metro_gtfs_path).exists():
        logger.error(f"Metro GTFS file not found: {metro_gtfs_path}")
        sys.exit(1)

    if ml_gtfs_path and not Path(ml_gtfs_path).exists():
        logger.warning(f"Metro Ligero GTFS file not found: {ml_gtfs_path}")
        logger.info("Importing only Metro Madrid frequencies...")
        ml_gtfs_path = None

    logger.info(f"Importing Metro frequencies...")

    db = SessionLocal()
    try:
        importer = MetroFrequencyImporter(db)

        if ml_gtfs_path:
            # Import both
            stats = importer.import_all_metro_frequencies(metro_gtfs_path, ml_gtfs_path)
            logger.info("=" * 50)
            logger.info("IMPORT COMPLETE")
            logger.info("=" * 50)
            logger.info(f"Metro Madrid:")
            logger.info(f"  - Trips loaded: {stats['metro_trips_loaded']}")
            logger.info(f"  - Frequencies imported: {stats['metro_frequencies_imported']}")
            logger.info(f"Metro Ligero:")
            logger.info(f"  - Trips loaded: {stats['ml_trips_loaded']}")
            logger.info(f"  - Frequencies imported: {stats['ml_frequencies_imported']}")
            logger.info(f"Total frequencies: {stats['total_frequencies']}")
        else:
            # Import only Metro Madrid
            stats = importer.import_from_gtfs_zip(metro_gtfs_path)
            logger.info("=" * 50)
            logger.info("IMPORT COMPLETE")
            logger.info("=" * 50)
            logger.info(f"Trips loaded: {stats['trips_loaded']}")
            logger.info(f"Frequencies imported: {stats['frequencies_imported']}")

        # Show sample frequencies
        logger.info("")
        logger.info("Sample frequencies:")

        # Metro lines
        for line_num in ['1', '6', '10']:
            route_id = f'METRO_{line_num}'
            freqs = db.query(RouteFrequencyModel).filter(
                RouteFrequencyModel.route_id == route_id,
                RouteFrequencyModel.day_type == 'weekday'
            ).order_by(RouteFrequencyModel.start_time).all()

            if freqs:
                logger.info(f"  Metro Línea {line_num} (laborables):")
                for f in freqs[:3]:  # Show first 3
                    logger.info(f"    {f.start_time.strftime('%H:%M')}-{f.end_time.strftime('%H:%M')}: cada {f.headway_minutes} min")

        # Metro Ligero
        for line_num in ['ML1', 'ML2']:
            route_id = f'ML_{line_num}'
            freqs = db.query(RouteFrequencyModel).filter(
                RouteFrequencyModel.route_id == route_id,
                RouteFrequencyModel.day_type == 'weekday'
            ).order_by(RouteFrequencyModel.start_time).all()

            if freqs:
                logger.info(f"  Metro Ligero {line_num} (laborables):")
                for f in freqs[:3]:  # Show first 3
                    logger.info(f"    {f.start_time.strftime('%H:%M')}-{f.end_time.strftime('%H:%M')}: cada {f.headway_minutes} min")

    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
