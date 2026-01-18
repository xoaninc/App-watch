#!/usr/bin/env python3
"""Fix Metro Sevilla Line 1 stop order.

The stops should be ordered from Ciudad Expo to Olivar de Quintos, not alphabetically.
This script updates the stop_route_sequence table with the correct order.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import SessionLocal
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel
from src.gtfs_bc.stop_route_sequence.infrastructure.models import StopRouteSequenceModel

# Correct station order for Metro Sevilla Line 1
# From Ciudad Expo (west) to Olivar de Quintos (southeast)
METRO_SEV_L1_STATION_ORDER = [
    "Ciudad Expo",
    "Cavaleri",
    "San Juan Alto",
    "San Juan Bajo",
    "Blas Infante",
    "Parque de los Príncipes",
    "Plaza de Cuba",
    "Puerta Jerez",
    "Prado de San Sebastián",
    "San Bernardo",
    "Nervión",
    "Gran Plaza",
    "1º de Mayo",
    "Amate",
    "La Plata",
    "Cocheras",
    "Pablo de Olavide",
    "Condequinto",
    "Montequinto",
    "Europa",
    "Olivar de Quintos",
]


def fix_metro_sevilla_sequences():
    """Fix stop sequences for Metro Sevilla routes."""
    db = SessionLocal()
    try:
        # Get all Metro Sevilla routes
        routes = db.query(RouteModel).filter(
            RouteModel.id.like("METRO_SEV_%")
        ).all()

        if not routes:
            print("No Metro Sevilla routes found!")
            return

        print(f"Found {len(routes)} Metro Sevilla routes")

        # Get all Metro Sevilla stops
        stops = db.query(StopModel).filter(
            StopModel.id.like("METRO_SEV_%")
        ).all()

        print(f"Found {len(stops)} Metro Sevilla stops")

        # Create name -> stop_id mapping
        name_to_stop = {}
        for stop in stops:
            name_to_stop[stop.name] = stop.id
            print(f"  - {stop.name}: {stop.id}")

        # Process each route
        for route in routes:
            print(f"\nFixing sequences for route {route.id} ({route.short_name})")

            # Delete existing sequences for this route
            deleted = db.query(StopRouteSequenceModel).filter(
                StopRouteSequenceModel.route_id == route.id
            ).delete()
            print(f"  Deleted {deleted} existing sequences")

            # Create new sequences in correct order
            created = 0
            for seq, station_name in enumerate(METRO_SEV_L1_STATION_ORDER, start=1):
                stop_id = name_to_stop.get(station_name)
                if not stop_id:
                    print(f"  WARNING: Stop '{station_name}' not found in database!")
                    continue

                sequence = StopRouteSequenceModel(
                    route_id=route.id,
                    stop_id=stop_id,
                    sequence=seq,
                )
                db.add(sequence)
                created += 1
                print(f"  {seq}. {station_name} -> {stop_id}")

            print(f"  Created {created} sequences")

        db.commit()
        print("\nMetro Sevilla stop sequences fixed successfully!")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    fix_metro_sevilla_sequences()
