#!/usr/bin/env python3
"""Fix Metro Madrid routes network_id.

Metro Madrid routes are incorrectly assigned to network_id '10T' (Cercanías Madrid)
instead of '11T' (Metro de Madrid). This script fixes that.

Run on the server:
    source .venv/bin/activate
    python scripts/fix_metro_madrid_network.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv('.env.local')


def main():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL not set")
        sys.exit(1)

    engine = create_engine(db_url)

    with engine.begin() as conn:
        # Check current state
        result = conn.execute(text("""
            SELECT id, short_name, network_id
            FROM gtfs_routes
            WHERE id LIKE 'METRO\\_%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_VALENCIA%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_BILBAO%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_GRANADA%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_MALAGA%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_SEV%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_TENERIFE%' ESCAPE '\\'
            ORDER BY id
        """))

        print("Current Metro Madrid routes:")
        routes = result.fetchall()
        for row in routes:
            status = "❌" if row[2] != '11T' else "✅"
            print(f"  {status} {row[0]}: {row[1]} -> network={row[2]}")

        # Fix network_id
        result = conn.execute(text("""
            UPDATE gtfs_routes
            SET network_id = '11T'
            WHERE id LIKE 'METRO\\_%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_VALENCIA%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_BILBAO%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_GRANADA%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_MALAGA%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_SEV%' ESCAPE '\\'
            AND id NOT LIKE 'METRO\\_TENERIFE%' ESCAPE '\\'
            AND network_id != '11T'
        """))

        updated = result.rowcount
        print(f"\nUpdated {updated} routes to network_id='11T'")

        # Also fix Metro Ligero (ML_) routes
        result = conn.execute(text("""
            UPDATE gtfs_routes
            SET network_id = '12T'
            WHERE id LIKE 'ML\\_%' ESCAPE '\\'
            AND network_id != '12T'
        """))

        ml_updated = result.rowcount
        print(f"Updated {ml_updated} Metro Ligero routes to network_id='12T'")

        # Verify
        print("\nVerification:")
        result = conn.execute(text("""
            SELECT network_id, COUNT(*) as count
            FROM gtfs_routes
            WHERE id LIKE 'METRO\\_%' ESCAPE '\\'
            OR id LIKE 'ML\\_%' ESCAPE '\\'
            GROUP BY network_id
            ORDER BY network_id
        """))

        for row in result.fetchall():
            print(f"  network_id={row[0]}: {row[1]} routes")


if __name__ == '__main__':
    main()
