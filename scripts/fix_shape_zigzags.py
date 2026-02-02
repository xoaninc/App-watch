#!/usr/bin/env python3
"""Fix zigzag patterns in shapes (where the line goes back and forth).

This script detects and removes duplicate back-and-forth patterns in shapes
that cause visual "double line" effects.

Usage:
    python scripts/fix_shape_zigzags.py --detect --shape 20_C1
    python scripts/fix_shape_zigzags.py --fix --shape 20_C1
"""

import argparse
import logging
from core.database import SessionLocal
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_shape_points(db, shape_id: str) -> list:
    """Get all points for a shape."""
    result = db.execute(text("""
        SELECT sequence, lat, lon
        FROM gtfs_shape_points
        WHERE shape_id = :shape_id
        ORDER BY sequence
    """), {'shape_id': shape_id})
    return [{'seq': r[0], 'lat': r[1], 'lon': r[2]} for r in result]


def detect_zigzags(points: list, threshold: float = 0.0003) -> list:
    """Detect zigzag patterns where direction reverses.

    A zigzag is when:
    1. Points move in one direction (e.g., west)
    2. Then reverse direction (e.g., east)
    3. Then reverse again back to original direction

    Returns list of (start_seq, end_seq) tuples marking zigzag segments to remove.
    """
    zigzags = []
    i = 0

    while i < len(points) - 4:
        p0, p1, p2, p3, p4 = points[i:i+5]

        # Calculate lon deltas
        d1 = p1['lon'] - p0['lon']
        d2 = p2['lon'] - p1['lon']
        d3 = p3['lon'] - p2['lon']
        d4 = p4['lon'] - p3['lon']

        # Check for reversal pattern: going one way, then back, then original direction
        # Pattern: +++ then --- then +++ (or vice versa)
        if abs(d1) > threshold and abs(d2) > threshold:
            # Check if d2 reverses d1
            if d1 * d2 < 0:  # Sign changed = reversal
                # Look for return to original direction
                if d2 * d3 < 0 or d2 * d4 < 0:  # Another reversal
                    # Found a zigzag pattern
                    # Find extent of the zigzag
                    start = i + 1
                    end = i + 3

                    # Extend to include all reversal points
                    while end < len(points) - 1:
                        next_d = points[end + 1]['lon'] - points[end]['lon']
                        curr_d = points[end]['lon'] - points[end - 1]['lon']
                        if curr_d * next_d < 0 and abs(curr_d) > threshold:
                            end += 1
                        else:
                            break

                    zigzags.append({
                        'start_seq': points[start]['seq'],
                        'end_seq': points[end]['seq'],
                        'start_idx': start,
                        'end_idx': end,
                        'points': points[start:end+1]
                    })
                    i = end + 1
                    continue
        i += 1

    return zigzags


def fix_zigzags(db, shape_id: str, zigzags: list, dry_run: bool = False):
    """Remove zigzag points from shape."""
    if not zigzags:
        logger.info("No zigzags to fix")
        return

    # Get all points
    points = get_shape_points(db, shape_id)

    # Create set of sequences to remove
    seqs_to_remove = set()
    for z in zigzags:
        for p in z['points']:
            seqs_to_remove.add(p['seq'])

    logger.info(f"Removing {len(seqs_to_remove)} zigzag points")

    if dry_run:
        logger.info("[DRY RUN] Would remove sequences: " + str(sorted(seqs_to_remove)))
        return

    # Filter out zigzag points
    filtered = [p for p in points if p['seq'] not in seqs_to_remove]

    logger.info(f"Points before: {len(points)}, after: {len(filtered)}")

    # Delete and reinsert
    db.execute(text("DELETE FROM gtfs_shape_points WHERE shape_id = :shape_id"),
               {'shape_id': shape_id})

    for i, p in enumerate(filtered):
        db.execute(text("""
            INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon)
            VALUES (:shape_id, :seq, :lat, :lon)
        """), {
            'shape_id': shape_id,
            'seq': i + 1,
            'lat': p['lat'],
            'lon': p['lon']
        })

    db.commit()
    logger.info(f"Fixed {shape_id}: removed {len(seqs_to_remove)} points")


def main():
    parser = argparse.ArgumentParser(description='Fix zigzag patterns in shapes')
    parser.add_argument('--detect', action='store_true', help='Detect zigzags')
    parser.add_argument('--fix', action='store_true', help='Fix zigzags')
    parser.add_argument('--shape', type=str, required=True, help='Shape ID')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        points = get_shape_points(db, args.shape)
        logger.info(f"Shape {args.shape}: {len(points)} points")

        zigzags = detect_zigzags(points)

        if args.detect or not args.fix:
            print(f"\nDetected {len(zigzags)} zigzag patterns:")
            for z in zigzags:
                print(f"  seq {z['start_seq']} - {z['end_seq']}: {len(z['points'])} points")
                for p in z['points']:
                    print(f"    seq {p['seq']}: ({p['lat']:.6f}, {p['lon']:.6f})")

        if args.fix:
            fix_zigzags(db, args.shape, zigzags, dry_run=args.dry_run)

    finally:
        db.close()


if __name__ == "__main__":
    main()
