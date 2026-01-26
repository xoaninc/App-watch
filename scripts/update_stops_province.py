#!/usr/bin/env python3
"""
Update the province field for all stops based on their coordinates.

Uses PostGIS ST_Contains to find which province each stop is in.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import SessionLocal


def update_stops_province():
    """Update province field for all stops using PostGIS spatial query."""
    db = SessionLocal()

    try:
        # Update stops with province based on their coordinates
        # Uses ST_Contains to check if the stop point is within a province polygon
        sql = text("""
            UPDATE gtfs_stops s
            SET province = sp.name
            FROM spanish_provinces sp
            WHERE ST_Contains(
                sp.geometry,
                ST_SetSRID(ST_MakePoint(s.lon, s.lat), 4326)
            )
            AND s.province IS NULL
        """)

        result = db.execute(sql)
        updated_count = result.rowcount
        db.commit()

        print(f"Updated {updated_count} stops with province information")

        # Show some stats
        stats_sql = text("""
            SELECT province, COUNT(*) as count
            FROM gtfs_stops
            WHERE province IS NOT NULL
            GROUP BY province
            ORDER BY count DESC
            LIMIT 15
        """)

        stats = db.execute(stats_sql).fetchall()
        print("\nStops by province:")
        for row in stats:
            print(f"  {row[0]}: {row[1]}")

        # Check how many still have NULL province
        null_count = db.execute(
            text("SELECT COUNT(*) FROM gtfs_stops WHERE province IS NULL")
        ).scalar()
        print(f"\nStops still without province: {null_count}")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    update_stops_province()
