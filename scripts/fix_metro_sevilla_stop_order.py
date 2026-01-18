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
    """Fix stop sequences for Metro Sevilla routes using raw SQL."""
    db = SessionLocal()
    try:
        # Get all Metro Sevilla routes using raw SQL
        result = db.execute(text("SELECT id, short_name FROM gtfs_routes WHERE id LIKE 'METRO_SEV_%'"))
        routes = result.fetchall()

        if not routes:
            print("No Metro Sevilla routes found!")
            return

        print(f"Found {len(routes)} Metro Sevilla routes")

        # Get all Metro Sevilla stops
        result = db.execute(text("SELECT id, name FROM gtfs_stops WHERE id LIKE 'METRO_SEV_%'"))
        stops = result.fetchall()

        print(f"Found {len(stops)} Metro Sevilla stops")

        # Create name -> stop_id mapping
        name_to_stop = {}
        for stop_id, name in stops:
            name_to_stop[name] = stop_id
            print(f"  - {name}: {stop_id}")

        # Process each route
        for route_id, short_name in routes:
            print(f"\nFixing sequences for route {route_id} ({short_name})")

            # Delete existing sequences for this route
            result = db.execute(
                text("DELETE FROM gtfs_stop_route_sequence WHERE route_id = :route_id"),
                {"route_id": route_id}
            )
            print(f"  Deleted {result.rowcount} existing sequences")

            # Create new sequences in correct order
            created = 0
            for seq, station_name in enumerate(METRO_SEV_L1_STATION_ORDER, start=1):
                stop_id = name_to_stop.get(station_name)
                if not stop_id:
                    print(f"  WARNING: Stop '{station_name}' not found in database!")
                    continue

                db.execute(
                    text("INSERT INTO gtfs_stop_route_sequence (route_id, stop_id, sequence) VALUES (:route_id, :stop_id, :seq)"),
                    {"route_id": route_id, "stop_id": stop_id, "seq": seq}
                )
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
