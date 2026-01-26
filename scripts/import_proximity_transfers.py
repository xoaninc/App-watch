#!/usr/bin/env python3
"""Import proximity-based transfers between Metro/Tranvía and Cercanías.

Creates transfers for stations within 250m walking distance.
Walking time calculated at 1.2 m/s.

Usage:
    python scripts/import_proximity_transfers.py
"""

import math
import sys
import logging
from pathlib import Path
from typing import List, Tuple

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import SessionLocal
from src.gtfs_bc.transfer.infrastructure.models import LineTransferModel
from src.gtfs_bc.stop.infrastructure.models import StopModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MAX_DISTANCE_METERS = 250
WALKING_SPEED_MS = 1.2  # meters per second


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def get_network_from_stop_id(stop_id: str) -> str:
    """Extract network identifier from stop ID."""
    if stop_id.startswith('METRO_BILBAO_'):
        return 'METRO_BILBAO'
    elif stop_id.startswith('METRO_SEV_'):
        return 'METRO_SEV'
    elif stop_id.startswith('METRO_MALAGA_'):
        return 'METRO_MALAGA'
    elif stop_id.startswith('METRO_VALENCIA_'):
        return 'METRO_VALENCIA'
    elif stop_id.startswith('TMB_METRO_'):
        return 'TMB_METRO'
    elif stop_id.startswith('FGC_'):
        return 'FGC'
    elif stop_id.startswith('ML_'):
        return 'ML'
    elif stop_id.startswith('TRAM_'):
        return 'TRAM'
    elif stop_id.startswith('TRANVIA_'):
        return 'TRANVIA'
    elif stop_id.startswith('RENFE_'):
        return 'RENFE'
    else:
        parts = stop_id.split('_')
        return parts[0] if parts else 'UNKNOWN'


def find_proximity_transfers(db) -> List[Tuple]:
    """Find all Metro/Tranvía ↔ Cercanías connections within MAX_DISTANCE_METERS."""

    # Get all metro/tranvía stops
    metro_stops = db.query(StopModel).filter(
        StopModel.id.like('METRO_%') |
        StopModel.id.like('TMB_METRO_%') |
        StopModel.id.like('TRAM_%') |
        StopModel.id.like('TRANVIA_%') |
        StopModel.id.like('FGC_%') |
        StopModel.id.like('ML_%')
    ).all()

    # Get all Cercanías stops
    cercanias_stops = db.query(StopModel).filter(StopModel.id.like('RENFE_%')).all()

    logger.info(f"Found {len(metro_stops)} Metro/Tranvía stops")
    logger.info(f"Found {len(cercanias_stops)} Cercanías stops")

    transfers = []

    for metro in metro_stops:
        if not metro.lat or not metro.lon:
            continue
        for cerc in cercanias_stops:
            if not cerc.lat or not cerc.lon:
                continue

            dist = haversine(metro.lat, metro.lon, cerc.lat, cerc.lon)

            if dist < MAX_DISTANCE_METERS:
                walk_time = int(dist / WALKING_SPEED_MS)
                transfers.append((
                    metro.id, metro.name,
                    cerc.id, cerc.name,
                    dist, walk_time
                ))

    # Sort by distance
    transfers.sort(key=lambda x: x[4])
    return transfers


def import_proximity_transfers(db):
    """Import proximity-based transfers."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Importing proximity transfers (< {MAX_DISTANCE_METERS}m)")
    logger.info(f"{'='*60}")

    # Find all connections
    connections = find_proximity_transfers(db)
    logger.info(f"Found {len(connections)} connections within {MAX_DISTANCE_METERS}m")

    # Delete existing proximity transfers
    deleted = db.query(LineTransferModel).filter(
        LineTransferModel.source == 'proximity'
    ).delete()
    logger.info(f"Deleted {deleted} existing proximity transfers")

    # Group by network for logging
    by_network = {}

    count = 0
    for metro_id, metro_name, cerc_id, cerc_name, dist, walk_time in connections:
        network = get_network_from_stop_id(metro_id)

        # Create bidirectional transfers
        # Metro -> Cercanías
        transfer1 = LineTransferModel(
            from_stop_id=metro_id,
            to_stop_id=cerc_id,
            from_stop_name=metro_name,
            to_stop_name=cerc_name,
            transfer_type=2,  # Minimum transfer time required
            min_transfer_time=walk_time,
            network_id=network,
            source='proximity',
        )
        db.add(transfer1)

        # Cercanías -> Metro
        transfer2 = LineTransferModel(
            from_stop_id=cerc_id,
            to_stop_id=metro_id,
            from_stop_name=cerc_name,
            to_stop_name=metro_name,
            transfer_type=2,
            min_transfer_time=walk_time,
            network_id=network,
            source='proximity',
        )
        db.add(transfer2)

        count += 2

        # Track by network
        if network not in by_network:
            by_network[network] = []
        by_network[network].append((metro_name, cerc_name, int(dist), walk_time))

    db.commit()

    # Log summary by network
    logger.info(f"\nImported {count} proximity transfers ({count//2} bidirectional pairs)")
    logger.info("\nBy network:")
    for network in sorted(by_network.keys()):
        items = by_network[network]
        logger.info(f"\n  {network}: {len(items)} connections")
        for metro_name, cerc_name, dist, walk_time in items[:5]:
            logger.info(f"    {metro_name} <-> {cerc_name}: {dist}m ({walk_time}s)")
        if len(items) > 5:
            logger.info(f"    ... and {len(items) - 5} more")

    return count


def main():
    """Main entry point."""
    db = SessionLocal()

    try:
        count = import_proximity_transfers(db)

        logger.info(f"\n{'='*60}")
        logger.info(f"TOTAL: Imported {count} proximity transfers")
        logger.info(f"{'='*60}")

        # Show final summary
        result = db.execute(text("""
            SELECT source, COUNT(*) as count
            FROM line_transfer
            GROUP BY source
            ORDER BY count DESC
        """))

        logger.info("\nAll transfers by source:")
        for row in result:
            logger.info(f"  {row[0]}: {row[1]} transfers")

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
