#!/usr/bin/env python3
"""Interpolate missing shape points using OpenStreetMap railway data.

This script detects gaps (jumps > threshold) in GTFS shapes and fills them
using railway nodes from OpenStreetMap's Overpass API.

Usage:
    python scripts/interpolate_shapes_osm.py --detect
    python scripts/interpolate_shapes_osm.py --fix
    python scripts/interpolate_shapes_osm.py --fix --shape 20_C1
"""

import argparse
import json
import logging
import math
import time
from pathlib import Path
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Minimum gap distance (meters) to consider for interpolation
MIN_GAP_METERS = 300

# Path to GTFS shapes file
GTFS_SHAPES_PATH = Path(__file__).parent.parent / "data" / "gtfs" / "shapes.txt"

# Output path for corrected shapes
OUTPUT_SHAPES_PATH = Path(__file__).parent.parent / "data" / "shapes_interpolated.json"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def load_shapes_from_gtfs(gtfs_path: Path) -> dict:
    """Load shapes from GTFS file."""
    shapes = {}

    with open(gtfs_path, 'r') as f:
        # Skip header
        header = f.readline().strip().split(',')
        header = [h.strip() for h in header]

        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 4:
                continue

            shape_id = parts[0].strip()
            lat = float(parts[1].strip())
            lon = float(parts[2].strip())
            seq = int(parts[3].strip())

            if shape_id not in shapes:
                shapes[shape_id] = []

            shapes[shape_id].append({
                'seq': seq,
                'lat': lat,
                'lon': lon
            })

    # Sort by sequence
    for shape_id in shapes:
        shapes[shape_id].sort(key=lambda x: x['seq'])

    return shapes


def detect_gaps(shapes: dict, min_gap: float = MIN_GAP_METERS) -> list:
    """Detect gaps larger than threshold in shapes."""
    gaps = []

    for shape_id, points in shapes.items():
        for i in range(1, len(points)):
            prev = points[i-1]
            curr = points[i]

            dist = haversine_distance(prev['lat'], prev['lon'], curr['lat'], curr['lon'])

            if dist > min_gap:
                gaps.append({
                    'shape_id': shape_id,
                    'from_seq': prev['seq'],
                    'to_seq': curr['seq'],
                    'from_lat': prev['lat'],
                    'from_lon': prev['lon'],
                    'to_lat': curr['lat'],
                    'to_lon': curr['lon'],
                    'distance': dist
                })

    return gaps


def query_osm_railway(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> list:
    """Query OSM Overpass API for railway nodes in bounding box."""
    # Add small buffer to bounding box
    buffer = 0.002  # ~200m
    min_lat -= buffer
    min_lon -= buffer
    max_lat += buffer
    max_lon += buffer

    query = f"""
    [out:json][timeout:30];
    (
      way["railway"="rail"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    (._;>;);
    out body;
    """

    logger.info(f"Querying OSM for bbox: ({min_lat:.4f},{min_lon:.4f}) - ({max_lat:.4f},{max_lon:.4f})")

    try:
        response = requests.post(OVERPASS_URL, data={'data': query}, timeout=60)
        response.raise_for_status()
        data = response.json()

        # Extract nodes
        nodes = {}
        for element in data.get('elements', []):
            if element['type'] == 'node':
                nodes[element['id']] = {
                    'lat': element['lat'],
                    'lon': element['lon']
                }

        # Extract ways and their node order
        ways = []
        for element in data.get('elements', []):
            if element['type'] == 'way':
                way_nodes = []
                for node_id in element.get('nodes', []):
                    if node_id in nodes:
                        way_nodes.append(nodes[node_id])
                if way_nodes:
                    ways.append(way_nodes)

        logger.info(f"Found {len(nodes)} nodes in {len(ways)} railway ways")
        return ways

    except Exception as e:
        logger.error(f"OSM query failed: {e}")
        return []


def interpolate_gap(gap: dict, osm_ways: list) -> list:
    """Find OSM nodes that fill the gap between two points."""
    from_lat, from_lon = gap['from_lat'], gap['from_lon']
    to_lat, to_lon = gap['to_lat'], gap['to_lon']

    # Find the best matching way
    best_way = None
    best_score = float('inf')

    for way in osm_ways:
        if len(way) < 2:
            continue

        # Find start and end points closest to our gap endpoints
        start_dist = min(haversine_distance(from_lat, from_lon, n['lat'], n['lon']) for n in way)
        end_dist = min(haversine_distance(to_lat, to_lon, n['lat'], n['lon']) for n in way)

        score = start_dist + end_dist
        if score < best_score:
            best_score = score
            best_way = way

    if not best_way or best_score > 500:  # Max 500m deviation
        logger.warning(f"No suitable OSM way found for gap (score={best_score:.0f}m)")
        return []

    # Find the segment of the way that connects our points
    # Find indices closest to start and end
    start_idx = min(range(len(best_way)),
                    key=lambda i: haversine_distance(from_lat, from_lon, best_way[i]['lat'], best_way[i]['lon']))
    end_idx = min(range(len(best_way)),
                  key=lambda i: haversine_distance(to_lat, to_lon, best_way[i]['lat'], best_way[i]['lon']))

    # Extract nodes between start and end
    if start_idx < end_idx:
        segment = best_way[start_idx:end_idx+1]
    else:
        segment = best_way[end_idx:start_idx+1][::-1]

    # Filter to only include intermediate points (not the endpoints)
    intermediate = []
    for node in segment[1:-1]:  # Exclude first and last
        dist_from_start = haversine_distance(from_lat, from_lon, node['lat'], node['lon'])
        dist_from_end = haversine_distance(to_lat, to_lon, node['lat'], node['lon'])

        # Only include if it's actually between the two points
        if dist_from_start > 50 and dist_from_end > 50:
            intermediate.append(node)

    logger.info(f"Found {len(intermediate)} intermediate points from OSM")
    return intermediate


def fix_shape_gaps(shapes: dict, gaps: list) -> dict:
    """Fix gaps in shapes using OSM data."""
    # Group gaps by shape
    gaps_by_shape = {}
    for gap in gaps:
        shape_id = gap['shape_id']
        if shape_id not in gaps_by_shape:
            gaps_by_shape[shape_id] = []
        gaps_by_shape[shape_id].append(gap)

    interpolations = {}

    for shape_id, shape_gaps in gaps_by_shape.items():
        logger.info(f"\nProcessing shape {shape_id} with {len(shape_gaps)} gaps")
        interpolations[shape_id] = []

        for gap in shape_gaps:
            logger.info(f"  Gap: seq {gap['from_seq']} -> {gap['to_seq']} ({gap['distance']:.0f}m)")

            # Query OSM for this gap's area
            min_lat = min(gap['from_lat'], gap['to_lat'])
            max_lat = max(gap['from_lat'], gap['to_lat'])
            min_lon = min(gap['from_lon'], gap['to_lon'])
            max_lon = max(gap['from_lon'], gap['to_lon'])

            osm_ways = query_osm_railway(min_lat, min_lon, max_lat, max_lon)

            if osm_ways:
                intermediate = interpolate_gap(gap, osm_ways)

                if intermediate:
                    # Generate intermediate sequence numbers
                    from_seq = gap['from_seq']
                    to_seq = gap['to_seq']

                    interpolated_points = []
                    for i, node in enumerate(intermediate):
                        # Use decimal sequences to insert between existing points
                        frac = (i + 1) / (len(intermediate) + 1)
                        new_seq = from_seq + frac * (to_seq - from_seq)

                        interpolated_points.append({
                            'seq': new_seq,
                            'lat': node['lat'],
                            'lon': node['lon'],
                            'interpolated': True
                        })

                    interpolations[shape_id].extend(interpolated_points)
                    logger.info(f"    Added {len(interpolated_points)} interpolated points")

            # Rate limiting for Overpass API
            time.sleep(1)

    return interpolations


def merge_interpolations(shapes: dict, interpolations: dict) -> dict:
    """Merge original shapes with interpolated points."""
    merged = {}

    for shape_id, points in shapes.items():
        merged_points = list(points)  # Copy original

        # Add interpolated points if any
        if shape_id in interpolations:
            for interp in interpolations[shape_id]:
                merged_points.append(interp)

        # Sort by sequence
        merged_points.sort(key=lambda x: x['seq'])
        merged[shape_id] = merged_points

    return merged


def save_interpolations(interpolations: dict, output_path: Path):
    """Save interpolations to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(interpolations, f, indent=2)

    logger.info(f"Saved interpolations to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Interpolate shape gaps using OSM')
    parser.add_argument('--detect', action='store_true', help='Detect gaps without fixing')
    parser.add_argument('--fix', action='store_true', help='Fix gaps using OSM data')
    parser.add_argument('--shape', type=str, help='Only process specific shape ID')
    parser.add_argument('--gtfs', type=str, help='Path to GTFS shapes.txt')
    parser.add_argument('--threshold', type=float, default=MIN_GAP_METERS,
                        help=f'Minimum gap distance in meters (default: {MIN_GAP_METERS})')
    args = parser.parse_args()

    # Determine GTFS path
    gtfs_path = Path(args.gtfs) if args.gtfs else GTFS_SHAPES_PATH

    # Try alternative paths if default doesn't exist
    if not gtfs_path.exists():
        alt_paths = [
            Path.home() / "Downloads" / "20260131_050017_RENFE_CERCA" / "shapes.txt",
            Path(__file__).parent.parent / "static" / "gtfs" / "shapes.txt",
        ]
        for alt in alt_paths:
            if alt.exists():
                gtfs_path = alt
                break

    if not gtfs_path.exists():
        logger.error(f"GTFS shapes file not found: {gtfs_path}")
        logger.info("Use --gtfs to specify the path")
        return

    logger.info(f"Loading shapes from {gtfs_path}")
    shapes = load_shapes_from_gtfs(gtfs_path)
    logger.info(f"Loaded {len(shapes)} shapes")

    # Filter to specific shape if requested
    if args.shape:
        if args.shape in shapes:
            shapes = {args.shape: shapes[args.shape]}
        else:
            logger.error(f"Shape {args.shape} not found")
            return

    # Detect gaps
    gaps = detect_gaps(shapes, args.threshold)

    if args.detect or not args.fix:
        print("\n" + "=" * 70)
        print(f"Detected {len(gaps)} gaps > {args.threshold}m")
        print("=" * 70)

        for gap in sorted(gaps, key=lambda x: -x['distance']):
            print(f"  {gap['shape_id']:>10} | seq {gap['from_seq']:>4} -> {gap['to_seq']:<4} | {gap['distance']:>6.0f}m")

        if not args.fix:
            print("\nRun with --fix to interpolate missing points using OSM")
            return

    if args.fix:
        logger.info("\nFixing gaps using OSM data...")
        interpolations = fix_shape_gaps(shapes, gaps)

        # Count total interpolated points
        total = sum(len(pts) for pts in interpolations.values())
        logger.info(f"\nTotal interpolated points: {total}")

        if total > 0:
            save_interpolations(interpolations, OUTPUT_SHAPES_PATH)

            # Also create a merged shapes file
            merged = merge_interpolations(shapes, interpolations)
            merged_path = OUTPUT_SHAPES_PATH.with_name("shapes_merged.json")

            with open(merged_path, 'w') as f:
                json.dump(merged, f, indent=2)

            logger.info(f"Saved merged shapes to {merged_path}")

            print("\n" + "=" * 70)
            print("Interpolation complete!")
            print("=" * 70)
            print(f"  Gaps fixed: {len([g for s in interpolations.values() for g in s if g])}")
            print(f"  Points added: {total}")
            print(f"  Output: {OUTPUT_SHAPES_PATH}")


if __name__ == "__main__":
    main()
