#!/usr/bin/env python3
"""
Fix C1 Asturias shape - Replace detour via C3 with correct Ferrocarril León-Gijón track

Problem: The C1 shape follows C3 track (San Juan de Nieva - Villabona)
from Villabona-Tabladiello area before joining back to C1 at Villabona de Asturias.

Solution: Replace the detour segment with geometry from OpenStreetMap's
"Ferrocarril León - Gijón" railway.

Usage:
    # Dry run (show what would be changed)
    python scripts/fix_c1_asturias_shape.py --dry-run

    # Apply fix
    python scripts/fix_c1_asturias_shape.py
"""

import argparse
import sys
import json
import math
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings


def get_db_session():
    """Create database session."""
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()


def find_shape_id(session):
    """Find the shape_id used by C1 Asturias route."""
    result = session.execute(text("""
        SELECT DISTINCT t.shape_id, COUNT(*) as trip_count
        FROM gtfs_trips t
        JOIN gtfs_routes r ON r.id = t.route_id
        WHERE r.id = 'RENFE_C1_47'
        AND t.shape_id IS NOT NULL
        GROUP BY t.shape_id
        ORDER BY trip_count DESC
        LIMIT 1
    """))
    row = result.fetchone()
    if row:
        return row[0]
    return "20_C1"


def get_current_shape(session, shape_id):
    """Get all points for a shape."""
    result = session.execute(text("""
        SELECT sequence, lat, lon
        FROM gtfs_shape_points
        WHERE shape_id = :shape_id
        ORDER BY sequence
    """), {"shape_id": shape_id})
    return [{"sequence": row[0], "lat": row[1], "lon": row[2]} for row in result]


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two points."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def find_detour_boundaries(points):
    """Find where the C3 detour starts and ends.

    The detour is characterized by points going significantly west (lon < -5.835)
    in the Villabona area (lat between 43.43 and 43.48).
    The C1 track goes west to about -5.831 at most, C3 goes to -5.85+.
    """
    detour_start = None
    detour_end = None

    for i, p in enumerate(points):
        # C3 detour goes much further west than -5.835
        if 43.43 < p['lat'] < 43.48 and p['lon'] < -5.835:
            if detour_start is None:
                detour_start = i
            detour_end = i

    return detour_start, detour_end


def fetch_osm_leon_gijon_segment():
    """Fetch the Ferrocarril León-Gijón geometry from OpenStreetMap."""
    query = """
    [out:json][timeout:60];
    (
      way["railway"="rail"]["name"="Ferrocarril León - Gijón"](43.42,-5.87,43.52,-5.78);
    );
    out body;
    >;
    out skel qt;
    """

    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        timeout=60
    )

    if response.status_code != 200:
        raise Exception(f"OSM query failed: {response.status_code}")

    data = response.json()

    # Parse nodes and ways
    nodes = {}
    ways = []

    for element in data['elements']:
        if element['type'] == 'node':
            nodes[element['id']] = (element['lat'], element['lon'])
        elif element['type'] == 'way':
            ways.append(element)

    # Build continuous path by connecting ways
    if not ways:
        raise Exception("No ways found for Ferrocarril León - Gijón")

    # Start with first way and build path
    all_points = []
    used_ways = set()

    # Get all node sequences from ways
    way_segments = []
    for way in ways:
        segment = [nodes[nid] for nid in way['nodes'] if nid in nodes]
        if segment:
            way_segments.append(segment)

    # Simple approach: sort all points by latitude (north to south)
    all_coords = []
    for segment in way_segments:
        all_coords.extend(segment)

    # Remove duplicates and sort
    unique_coords = list(set(all_coords))
    unique_coords.sort(key=lambda x: -x[0])  # Sort by lat descending (N to S)

    return unique_coords


def find_closest_point_index(points, target_lat, target_lon):
    """Find index of closest point to target coordinates."""
    min_dist = float('inf')
    min_idx = 0

    for i, p in enumerate(points):
        lat = p['lat'] if isinstance(p, dict) else p[0]
        lon = p['lon'] if isinstance(p, dict) else p[1]
        dist = haversine_distance(lat, lon, target_lat, target_lon)
        if dist < min_dist:
            min_dist = dist
            min_idx = i

    return min_idx, min_dist


def get_osm_replacement_segment(osm_points, start_lat, start_lon, end_lat, end_lon):
    """Get the OSM segment between two points."""
    start_idx, start_dist = find_closest_point_index(osm_points, start_lat, start_lon)
    end_idx, end_dist = find_closest_point_index(osm_points, end_lat, end_lon)

    print(f"  OSM start match: index {start_idx}, distance {start_dist:.1f}m")
    print(f"  OSM end match: index {end_idx}, distance {end_dist:.1f}m")

    if start_idx > end_idx:
        start_idx, end_idx = end_idx, start_idx

    # Extract segment
    segment = []
    for i in range(start_idx, end_idx + 1):
        p = osm_points[i]
        lat = p[0] if isinstance(p, tuple) else p['lat']
        lon = p[1] if isinstance(p, tuple) else p['lon']
        segment.append({'lat': lat, 'lon': lon})

    return segment


def apply_fix(session, shape_id, dry_run=False):
    """Apply the shape fix using OSM geometry."""
    print(f"Shape ID: {shape_id}")

    # Get current shape
    points = get_current_shape(session, shape_id)
    print(f"Current shape has {len(points)} points")

    # Find detour boundaries
    detour_start, detour_end = find_detour_boundaries(points)

    if detour_start is None:
        print("No C3 detour found (no points with lon < -5.835)")
        print("Shape may already be fixed or uses different detour")
        return False

    print(f"\nDetour found from index {detour_start} to {detour_end}")
    print(f"  First detour point: {points[detour_start]['lat']:.6f}, {points[detour_start]['lon']:.6f}")
    print(f"  Last detour point: {points[detour_end]['lat']:.6f}, {points[detour_end]['lon']:.6f}")
    print(f"  Detour has {detour_end - detour_start + 1} points")

    # Get boundary points
    before_detour = points[detour_start - 1]
    after_detour = points[detour_end + 1] if detour_end + 1 < len(points) else points[detour_end]

    print(f"\nBoundary points:")
    print(f"  Before detour: {before_detour['lat']:.6f}, {before_detour['lon']:.6f}")
    print(f"  After detour: {after_detour['lat']:.6f}, {after_detour['lon']:.6f}")

    # Fetch OSM geometry
    print("\nFetching Ferrocarril León-Gijón geometry from OpenStreetMap...")
    osm_points = fetch_osm_leon_gijon_segment()
    print(f"  Retrieved {len(osm_points)} points from OSM")

    # Get replacement segment from OSM
    print("\nFinding replacement segment in OSM data...")
    osm_segment = get_osm_replacement_segment(
        osm_points,
        before_detour['lat'], before_detour['lon'],
        after_detour['lat'], after_detour['lon']
    )
    print(f"  OSM replacement segment has {len(osm_segment)} points")

    if len(osm_segment) < 5:
        print("WARNING: OSM segment too short, may indicate matching issue")

    # Build new shape
    new_points = []

    # Part 1: Points before detour (keep original)
    for i in range(detour_start):
        new_points.append(points[i])

    # Part 2: OSM replacement segment
    for p in osm_segment:
        new_points.append(p)

    # Part 3: Points after detour (keep original)
    for i in range(detour_end + 1, len(points)):
        new_points.append(points[i])

    print(f"\nNew shape will have {len(new_points)} points")
    print(f"  Points removed: {detour_end - detour_start + 1}")
    print(f"  Points added: {len(osm_segment)}")

    if dry_run:
        print("\n[DRY RUN] Would apply the following changes:")
        print(f"  - Delete all {len(points)} existing points")
        print(f"  - Insert {len(new_points)} new points")
        print(f"  - Replace C3 detour with Ferrocarril León-Gijón track")
        return True

    # Apply changes
    print("\nApplying changes to database...")

    # Delete all existing points for this shape
    session.execute(text("""
        DELETE FROM gtfs_shape_points WHERE shape_id = :shape_id
    """), {"shape_id": shape_id})

    # Insert new points
    for i, p in enumerate(new_points):
        session.execute(text("""
            INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon)
            VALUES (:shape_id, :sequence, :lat, :lon)
        """), {
            "shape_id": shape_id,
            "sequence": i + 1,
            "lat": p['lat'],
            "lon": p['lon']
        })

    session.commit()
    print(f"✓ Shape updated with {len(new_points)} points")

    # Verify
    new_count = session.execute(text("""
        SELECT COUNT(*) FROM gtfs_shape_points WHERE shape_id = :shape_id
    """), {"shape_id": shape_id}).scalar()
    print(f"Verification: {new_count} points in database")

    return True


def main():
    parser = argparse.ArgumentParser(description="Fix C1 Asturias shape using OSM data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without applying")
    args = parser.parse_args()

    session = get_db_session()

    try:
        # Find shape ID
        shape_id = find_shape_id(session)
        if not shape_id:
            print("ERROR: Could not find shape_id for RENFE_C1_47")
            return 1

        # Apply fix
        success = apply_fix(session, shape_id, dry_run=args.dry_run)

        if success:
            print("\n✓ Fix completed successfully")
            return 0
        else:
            print("\nNo changes needed")
            return 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
