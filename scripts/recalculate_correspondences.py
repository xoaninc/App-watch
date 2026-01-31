#!/usr/bin/env python3
"""
Recalculate all stop_correspondence distances and walk times based on actual stop coordinates.

This script:
1. Reads all correspondences from stop_correspondence table
2. Gets coordinates for each stop from gtfs_stops
3. Calculates real distance using haversine formula
4. Updates distance_m and walk_time_s with correct values

Usage:
    source .venv/bin/activate && python scripts/recalculate_correspondences.py
    source .venv/bin/activate && python scripts/recalculate_correspondences.py --dry-run
    source .venv/bin/activate && python scripts/recalculate_correspondences.py --source manual
"""
import argparse
import math
import os
import sys
from pathlib import Path

import psycopg2

# Constants
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost/renfeserver_dev"
)
WALKING_SPEED = 1.25  # m/s (4.5 km/h)


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def main():
    parser = argparse.ArgumentParser(description='Recalculate correspondence distances')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    parser.add_argument('--source', type=str, help='Only recalculate specific source (manual, osm, proximity)')
    parser.add_argument('--threshold', type=float, default=0.3, help='Error threshold to report (default: 0.3 = 30%%)')
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Build query
    query = """
        SELECT c.id, c.from_stop_id, c.to_stop_id, c.distance_m, c.walk_time_s, c.source,
               s1.lat as lat1, s1.lon as lon1, s1.name as name1,
               s2.lat as lat2, s2.lon as lon2, s2.name as name2
        FROM stop_correspondence c
        LEFT JOIN gtfs_stops s1 ON c.from_stop_id = s1.id
        LEFT JOIN gtfs_stops s2 ON c.to_stop_id = s2.id
    """
    if args.source:
        query += f" WHERE c.source = '{args.source}'"
    query += " ORDER BY c.source, c.from_stop_id"

    cur.execute(query)
    rows = cur.fetchall()

    print("=" * 70)
    print("Recalculating Stop Correspondence Distances")
    print("=" * 70)
    print(f"Total correspondences: {len(rows)}")
    if args.source:
        print(f"Filtering by source: {args.source}")
    print()

    # Statistics
    stats = {
        'total': len(rows),
        'updated': 0,
        'no_coords': 0,
        'unchanged': 0,
        'by_source': {}
    }

    problems = []
    updates = []

    for row in rows:
        corr_id, from_id, to_id, dist_db, time_db, source = row[:6]
        lat1, lon1, name1, lat2, lon2, name2 = row[6:]

        if source not in stats['by_source']:
            stats['by_source'][source] = {'total': 0, 'updated': 0, 'no_coords': 0}
        stats['by_source'][source]['total'] += 1

        # Check if we have coordinates
        if not all([lat1, lon1, lat2, lon2]):
            stats['no_coords'] += 1
            stats['by_source'][source]['no_coords'] += 1
            continue

        # Calculate real distance
        real_dist = haversine(lat1, lon1, lat2, lon2)
        real_time = int(real_dist / WALKING_SPEED)

        # Round distance
        real_dist = int(real_dist)

        # Check if update needed
        dist_diff = abs(real_dist - (dist_db or 0))
        time_diff = abs(real_time - (time_db or 0))

        needs_update = dist_db is None or time_db is None or dist_diff > 5 or time_diff > 5

        if needs_update:
            # Check if significant error
            if dist_db and dist_db > 0:
                error_pct = dist_diff / dist_db
                if error_pct > args.threshold:
                    problems.append({
                        'from': from_id,
                        'to': to_id,
                        'name_from': name1,
                        'name_to': name2,
                        'dist_db': dist_db,
                        'dist_real': real_dist,
                        'time_db': time_db,
                        'time_real': real_time,
                        'source': source,
                        'error_pct': error_pct
                    })

            updates.append({
                'id': corr_id,
                'dist': real_dist,
                'time': real_time,
                'source': source
            })
            stats['updated'] += 1
            stats['by_source'][source]['updated'] += 1
        else:
            stats['unchanged'] += 1

    # Print statistics
    print("Statistics by source:")
    print("-" * 70)
    for source, data in sorted(stats['by_source'].items(), key=lambda x: x[0] or ''):
        print(f"  {source or 'NULL':12} | Total: {data['total']:4} | To update: {data['updated']:4} | No coords: {data['no_coords']:4}")

    print()
    print(f"Total to update: {stats['updated']}")
    print(f"No coordinates: {stats['no_coords']}")
    print(f"Unchanged: {stats['unchanged']}")

    # Print problems (significant errors)
    if problems:
        print()
        print(f"Significant errors (>{args.threshold*100:.0f}% difference): {len(problems)}")
        print("-" * 70)
        for p in problems[:20]:
            print(f"  {p['name_from'][:25]:25} -> {p['name_to'][:25]:25}")
            print(f"    DB: {p['dist_db']}m/{p['time_db']}s | Real: {p['dist_real']}m/{p['time_real']}s | Error: {p['error_pct']*100:.0f}% ({p['source']})")

    # Apply updates
    if not args.dry_run and updates:
        print()
        print("Applying updates...")
        for upd in updates:
            cur.execute("""
                UPDATE stop_correspondence
                SET distance_m = %s, walk_time_s = %s
                WHERE id = %s
            """, (upd['dist'], upd['time'], upd['id']))

        conn.commit()
        print(f"Updated {len(updates)} correspondences")
    elif args.dry_run:
        print()
        print("[DRY-RUN] No changes applied")
    else:
        print()
        print("No updates needed")

    conn.close()


if __name__ == '__main__':
    main()
