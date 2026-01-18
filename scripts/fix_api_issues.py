#!/usr/bin/env python3
"""Fix API issues: logo_url, text_color, route/stop ID prefix mismatch."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import SessionLocal


def main():
    db = SessionLocal()

    try:
        # 1. Update ML network logo_url
        db.execute(text("""
            UPDATE gtfs_networks
            SET logo_url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/86/MetroLigeroMadrid.svg/200px-MetroLigeroMadrid.svg.png'
            WHERE code = 'ML'
        """))
        print("✓ ML logo_url updated")

        # 2. Update TRAM_SEV logo_url
        db.execute(text("""
            UPDATE gtfs_networks
            SET logo_url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/MetroCentro_Sevilla_logo.svg/200px-MetroCentro_Sevilla_logo.svg.png'
            WHERE code = 'TRAM_SEV'
        """))
        print("✓ TRAM_SEV logo_url updated")

        # 3. Rename TRANVIA_SEV -> TRAM_SEV to match network code
        # First, save existing data from child tables

        # Save stop_route_sequence data
        srs_data = db.execute(text("""
            SELECT route_id, stop_id, sequence FROM gtfs_stop_route_sequence
            WHERE route_id LIKE 'TRANVIA_SEV%' OR stop_id LIKE 'TRANVIA_SEV%'
        """)).fetchall()
        print(f"  Saved {len(srs_data)} stop_route_sequence entries")

        # Save route_frequencies data
        freq_data = db.execute(text("""
            SELECT route_id, start_time, end_time, headway_secs, day_type
            FROM gtfs_route_frequencies
            WHERE route_id LIKE 'TRANVIA_SEV%'
        """)).fetchall()
        print(f"  Saved {len(freq_data)} route_frequencies entries")

        # Delete old entries
        db.execute(text("""
            DELETE FROM gtfs_stop_route_sequence
            WHERE route_id LIKE 'TRANVIA_SEV%' OR stop_id LIKE 'TRANVIA_SEV%'
        """))
        db.execute(text("""
            DELETE FROM gtfs_route_frequencies
            WHERE route_id LIKE 'TRANVIA_SEV%'
        """))
        print("✓ Deleted old child table entries")

        # Update routes table id
        db.execute(text("""
            UPDATE gtfs_routes
            SET id = REPLACE(id, 'TRANVIA_SEV', 'TRAM_SEV')
            WHERE id LIKE 'TRANVIA_SEV%'
        """))
        print("✓ Routes ids updated")

        # Update stops table id
        db.execute(text("""
            UPDATE gtfs_stops
            SET id = REPLACE(id, 'TRANVIA_SEV', 'TRAM_SEV')
            WHERE id LIKE 'TRANVIA_SEV%'
        """))
        print("✓ Stops ids updated")

        # Reinsert stop_route_sequence with new IDs
        for route_id, stop_id, sequence in srs_data:
            new_route_id = route_id.replace('TRANVIA_SEV', 'TRAM_SEV')
            new_stop_id = stop_id.replace('TRANVIA_SEV', 'TRAM_SEV')
            db.execute(text("""
                INSERT INTO gtfs_stop_route_sequence (route_id, stop_id, sequence)
                VALUES (:rid, :sid, :seq)
            """), {"rid": new_route_id, "sid": new_stop_id, "seq": sequence})
        print(f"✓ Reinserted {len(srs_data)} stop_route_sequence entries")

        # Reinsert route_frequencies with new IDs
        for route_id, start_time, end_time, headway_secs, day_type in freq_data:
            new_route_id = route_id.replace('TRANVIA_SEV', 'TRAM_SEV')
            db.execute(text("""
                INSERT INTO gtfs_route_frequencies (route_id, start_time, end_time, headway_secs, day_type)
                VALUES (:rid, :st, :et, :hw, :dt)
            """), {"rid": new_route_id, "st": start_time, "et": end_time, "hw": headway_secs, "dt": day_type})
        print(f"✓ Reinserted {len(freq_data)} route_frequencies entries")

        # 4. Update Cercanías routes with text_color
        result = db.execute(text("""
            UPDATE gtfs_routes
            SET text_color = 'FFFFFF'
            WHERE agency_id = '1071VC' AND text_color IS NULL
        """))
        print(f"✓ Updated {result.rowcount} Cercanías routes with text_color")

        db.commit()
        print("\n=== VERIFICATION ===")

        # Verify networks
        result = db.execute(text("SELECT code, logo_url FROM gtfs_networks WHERE code IN ('ML', 'TRAM_SEV')"))
        for row in result:
            logo = row[1][:60] + "..." if row[1] and len(row[1]) > 60 else row[1]
            print(f"Network {row[0]}: logo_url={logo}")

        # Verify route with new ID
        result = db.execute(text("SELECT id, agency_id FROM gtfs_routes WHERE id LIKE 'TRAM_SEV%'"))
        for row in result:
            print(f"Route: {row[0]}, agency_id={row[1]}")

        # Verify stops with new ID
        result = db.execute(text("SELECT COUNT(*) FROM gtfs_stops WHERE id LIKE 'TRAM_SEV%'"))
        print(f"TRAM_SEV stops count: {result.scalar()}")

        # Verify route_count calculation (routes matching network code prefix)
        result = db.execute(text("SELECT COUNT(*) FROM gtfs_routes WHERE id LIKE 'TRAM_SEV%'"))
        print(f"TRAM_SEV route_count: {result.scalar()}")

        # Verify Cercanías text_color
        result = db.execute(text("SELECT COUNT(*) FROM gtfs_routes WHERE agency_id = '1071VC' AND text_color IS NULL"))
        print(f"Cercanías routes without text_color: {result.scalar()}")

        print("\n✅ All fixes applied successfully!")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
