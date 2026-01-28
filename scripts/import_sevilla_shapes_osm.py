#!/usr/bin/env python3
"""Import Cercanías Sevilla and Tranvía T1 shapes from OpenStreetMap.

Extracts detailed route geometry from OSM relations and imports them
into the gtfs_shape_points table, replacing the basic shapes from GTFS.

Usage:
    python scripts/import_sevilla_shapes_osm.py
    python scripts/import_sevilla_shapes_osm.py --dry-run

OSM Relations for Cercanías Sevilla:
    C-1: 11378448 (Utrera -> Lora), 11378449 (Lora -> Utrera)
    C-2: 11378341 (Santa Justa -> Cartuja), 11378342 (Cartuja -> Santa Justa)
    C-3: 11382022 (Santa Justa -> Cazalla), 11382023 (Cazalla -> Santa Justa)
    C-4: 11382118 (Santa Justa -> Virgen del Rocío)
    C-5: 11384991 (Hércules -> Benacazón), 11384992 (Benacazón -> Hércules)
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import httpx
from sqlalchemy import text

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# OSM relation IDs for Cercanías Sevilla
SEVILLA_RELATIONS = {
    'C1': {
        'ida': 11378448,    # Utrera -> Lora del Río
        'vuelta': 11378449, # Lora del Río -> Utrera
    },
    'C2': {
        'ida': 11378341,    # Santa Justa -> Cartuja
        'vuelta': 11378342, # Cartuja -> Santa Justa
    },
    'C3': {
        'ida': 11382022,    # Santa Justa -> Cazalla
        'vuelta': 11382023, # Cazalla -> Santa Justa
    },
    'C4': {
        'ida': 11382118,    # Santa Justa -> Virgen del Rocío (only one direction in OSM)
        'vuelta': None,     # Will create reverse from ida
    },
    'C5': {
        'ida': 11384991,    # Jardines de Hércules -> Benacazón
        'vuelta': 11384992, # Benacazón -> Jardines de Hércules
    },
}

# T1 Tranvía Sevilla (Metrocentro)
TRANVIA_RELATIONS = {
    'T1': {
        'ida': 36937,      # Plaza Nueva -> San Bernardo
        'vuelta': None,    # Will create reverse from ida
        'route_id': 'TRAM_SEV_T1',  # Direct route ID
    },
}

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def query_overpass(relation_id: int, max_retries: int = 3) -> Dict:
    """Query Overpass API for a relation's full geometry."""
    import time

    query = f"""[out:json][timeout:120];
relation({relation_id});
(._;>;);
out body;"""

    for attempt in range(max_retries):
        try:
            logger.info(f"Querying Overpass for relation {relation_id}... (attempt {attempt + 1})")
            response = httpx.post(OVERPASS_URL, data={'data': query}, timeout=180.0)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            if attempt < max_retries - 1:
                wait_time = 10 * (attempt + 1)  # 10s, 20s, 30s
                logger.warning(f"Overpass request failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise


def extract_coordinates(data: Dict) -> List[Tuple[float, float]]:
    """Extract ordered coordinates from Overpass response.

    Returns list of (lat, lon) tuples in order along the route.
    Uses node IDs to properly connect ways in sequence.
    """
    nodes = {}
    ways = []
    relation_members = []

    for el in data.get('elements', []):
        if el['type'] == 'node':
            nodes[el['id']] = (el['lat'], el['lon'])
        elif el['type'] == 'way':
            ways.append(el)
        elif el['type'] == 'relation':
            relation_members = el.get('members', [])

    # Build way order from relation members (only ways with role="" or "forward"/"backward")
    way_order = []
    for member in relation_members:
        if member['type'] == 'way':
            way_order.append({
                'id': member['ref'],
                'role': member.get('role', '')
            })

    # Create way lookup
    way_lookup = {w['id']: w for w in ways}

    # Extract coordinates in order using node IDs for proper connection
    coords = []
    prev_end_node = None

    for way_info in way_order:
        way_id = way_info['id']
        role = way_info['role']

        way = way_lookup.get(way_id)
        if not way:
            continue

        way_node_ids = way.get('nodes', [])
        if not way_node_ids:
            continue

        # Determine if way needs to be reversed based on:
        # 1. Role in relation (backward = reverse)
        # 2. Connection to previous way via node ID
        should_reverse = False

        if role == 'backward':
            should_reverse = True
        elif prev_end_node is not None:
            # Check if previous end node matches start or end of this way
            first_node = way_node_ids[0]
            last_node = way_node_ids[-1]

            if prev_end_node == last_node:
                # Previous end matches our last node -> reverse
                should_reverse = True
            elif prev_end_node == first_node:
                # Previous end matches our first node -> don't reverse
                should_reverse = False
            else:
                # No direct node connection - use distance heuristic
                if prev_end_node in nodes:
                    prev_coord = nodes[prev_end_node]
                    first_coord = nodes.get(first_node)
                    last_coord = nodes.get(last_node)

                    if first_coord and last_coord:
                        dist_to_first = haversine(prev_coord, first_coord)
                        dist_to_last = haversine(prev_coord, last_coord)
                        should_reverse = dist_to_last < dist_to_first

        # Get node IDs in correct order
        if should_reverse:
            way_node_ids = list(reversed(way_node_ids))

        # Convert to coordinates
        way_coords = [(nodes[nid][0], nodes[nid][1]) for nid in way_node_ids if nid in nodes]

        if not way_coords:
            continue

        # Add coordinates, avoiding duplicates at connection points
        for coord in way_coords:
            if not coords or coords[-1] != coord:
                coords.append(coord)

        # Track the last node ID for next way connection
        if way_node_ids:
            prev_end_node = way_node_ids[-1]

    return coords


def haversine(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Calculate distance between two coordinates in meters."""
    from math import radians, sin, cos, sqrt, atan2

    lat1, lon1 = coord1
    lat2, lon2 = coord2

    R = 6371000  # Earth radius in meters

    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi/2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def simplify_coords(coords: List[Tuple[float, float]], tolerance: float = 10.0) -> List[Tuple[float, float]]:
    """Simplify coordinates by removing points closer than tolerance meters.

    Keeps first and last points, removes intermediate points that are
    too close to previous point.
    """
    if len(coords) <= 2:
        return coords

    simplified = [coords[0]]

    for coord in coords[1:-1]:
        if haversine(simplified[-1], coord) >= tolerance:
            simplified.append(coord)

    simplified.append(coords[-1])
    return simplified


def insert_shape_points(db, shape_id: str, coords: List[Tuple[float, float]], dry_run: bool = False):
    """Insert shape points into database."""
    if dry_run:
        logger.info(f"[DRY-RUN] Would insert {len(coords)} points for shape {shape_id}")
        return

    # Delete existing points for this shape
    db.execute(text("DELETE FROM gtfs_shape_points WHERE shape_id = :sid"), {'sid': shape_id})

    # Ensure shape exists
    db.execute(text("INSERT INTO gtfs_shapes (id) VALUES (:sid) ON CONFLICT DO NOTHING"), {'sid': shape_id})

    # Insert points
    dist_traveled = 0.0
    prev_coord = None

    for seq, (lat, lon) in enumerate(coords):
        if prev_coord:
            dist_traveled += haversine(prev_coord, (lat, lon))

        db.execute(text("""
            INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon, dist_traveled)
            VALUES (:shape_id, :seq, :lat, :lon, :dist)
        """), {
            'shape_id': shape_id,
            'seq': seq,
            'lat': lat,
            'lon': lon,
            'dist': dist_traveled,
        })
        prev_coord = (lat, lon)

    db.commit()
    logger.info(f"Inserted {len(coords)} points for shape {shape_id}")


def update_trips_shape(db, line: str, shape_id_ida: str, shape_id_vuelta: str, dry_run: bool = False):
    """Update trips to use the new shapes based on direction."""
    if dry_run:
        logger.info(f"[DRY-RUN] Would update trips for line {line}")
        return

    # Find route IDs for this line in Sevilla (network 30T)
    result = db.execute(text("""
        SELECT id FROM gtfs_routes
        WHERE short_name = :line
        AND network_id = '30T'
    """), {'line': line}).fetchall()

    route_ids = [r[0] for r in result]

    if not route_ids:
        logger.warning(f"No routes found for line {line} in network 30T")
        return

    logger.info(f"Found routes for {line}: {route_ids}")

    for route_id in route_ids:
        # Update trips based on direction_id
        # direction_id 0 = ida, direction_id 1 = vuelta
        # Also handle NULL direction_id by assigning ida shape
        updated_ida = db.execute(text("""
            UPDATE gtfs_trips SET shape_id = :shape_id
            WHERE route_id = :route_id AND (direction_id = 0 OR direction_id IS NULL)
        """), {'shape_id': shape_id_ida, 'route_id': route_id})

        updated_vuelta = db.execute(text("""
            UPDATE gtfs_trips SET shape_id = :shape_id
            WHERE route_id = :route_id AND direction_id = 1
        """), {'shape_id': shape_id_vuelta, 'route_id': route_id})

        db.commit()
        logger.info(f"Updated trips for {route_id}: ida/null={updated_ida.rowcount}, vuelta={updated_vuelta.rowcount}")


def update_tranvia_trips_shape(db, line: str, route_id: str, shape_id_ida: str, shape_id_vuelta: str, dry_run: bool = False):
    """Update tranvía trips to use the new shapes."""
    if dry_run:
        logger.info(f"[DRY-RUN] Would update trips for tranvía {line}")
        return

    # Update all trips for this route
    updated = db.execute(text("""
        UPDATE gtfs_trips SET shape_id = :shape_id
        WHERE route_id = :route_id
    """), {'shape_id': shape_id_ida, 'route_id': route_id})

    db.commit()
    logger.info(f"Updated {updated.rowcount} trips for {route_id}")


def main():
    parser = argparse.ArgumentParser(description='Import Sevilla Cercanías and Tranvía shapes from OSM')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--line', type=str, help='Import only specific line (C1-C5, T1)')
    parser.add_argument('--tranvia-only', action='store_true', help='Only import T1 tranvía')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        # Process Cercanías lines
        if not args.tranvia_only:
            lines_to_import = [args.line.upper()] if args.line and args.line.upper().startswith('C') else list(SEVILLA_RELATIONS.keys())

            for line in lines_to_import:
                if line not in SEVILLA_RELATIONS:
                    logger.error(f"Unknown line: {line}")
                    continue

                relations = SEVILLA_RELATIONS[line]
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing {line}")
                logger.info(f"{'='*60}")

                # Extract IDA shape
                ida_relation = relations['ida']
                shape_id_ida = f"30_{line}_OSM"

                logger.info(f"Extracting {line} IDA from relation {ida_relation}...")
                data_ida = query_overpass(ida_relation)
                coords_ida = extract_coordinates(data_ida)
                coords_ida = simplify_coords(coords_ida, tolerance=5.0)  # Keep more detail
                logger.info(f"  {line} IDA: {len(coords_ida)} points")

                insert_shape_points(db, shape_id_ida, coords_ida, args.dry_run)

                # Extract VUELTA shape
                vuelta_relation = relations['vuelta']
                shape_id_vuelta = f"30_{line}_OSM_REV"

                if vuelta_relation:
                    logger.info(f"Extracting {line} VUELTA from relation {vuelta_relation}...")
                    data_vuelta = query_overpass(vuelta_relation)
                    coords_vuelta = extract_coordinates(data_vuelta)
                    coords_vuelta = simplify_coords(coords_vuelta, tolerance=5.0)
                else:
                    # Create reverse from ida
                    logger.info(f"Creating {line} VUELTA by reversing IDA...")
                    coords_vuelta = list(reversed(coords_ida))

                logger.info(f"  {line} VUELTA: {len(coords_vuelta)} points")
                insert_shape_points(db, shape_id_vuelta, coords_vuelta, args.dry_run)

                # Update trips to use new shapes
                update_trips_shape(db, line, shape_id_ida, shape_id_vuelta, args.dry_run)

                # Small delay to avoid rate limiting Overpass API
                import time
                time.sleep(3)

        # Process T1 Tranvía if requested
        if args.tranvia_only or (args.line and args.line.upper() == 'T1') or not args.line:
            for line, relations in TRANVIA_RELATIONS.items():
                if args.line and args.line.upper() != line:
                    continue

                logger.info(f"\n{'='*60}")
                logger.info(f"Processing Tranvía {line}")
                logger.info(f"{'='*60}")

                # Extract IDA shape
                ida_relation = relations['ida']
                shape_id_ida = f"TRAM_SEV_{line}_OSM"

                logger.info(f"Extracting {line} from relation {ida_relation}...")
                data_ida = query_overpass(ida_relation)
                coords_ida = extract_coordinates(data_ida)
                coords_ida = simplify_coords(coords_ida, tolerance=3.0)  # Higher detail for short route
                logger.info(f"  {line}: {len(coords_ida)} points")

                insert_shape_points(db, shape_id_ida, coords_ida, args.dry_run)

                # Create reverse
                shape_id_vuelta = f"TRAM_SEV_{line}_OSM_REV"
                if relations['vuelta']:
                    logger.info(f"Extracting {line} reverse from relation {relations['vuelta']}...")
                    data_vuelta = query_overpass(relations['vuelta'])
                    coords_vuelta = extract_coordinates(data_vuelta)
                    coords_vuelta = simplify_coords(coords_vuelta, tolerance=3.0)
                else:
                    logger.info(f"Creating {line} reverse by reversing...")
                    coords_vuelta = list(reversed(coords_ida))

                logger.info(f"  {line} reverse: {len(coords_vuelta)} points")
                insert_shape_points(db, shape_id_vuelta, coords_vuelta, args.dry_run)

                # Update trips
                update_tranvia_trips_shape(db, line, relations['route_id'], shape_id_ida, shape_id_vuelta, args.dry_run)

        # Print summary
        if not args.dry_run:
            result = db.execute(text("""
                SELECT shape_id, COUNT(*) as points
                FROM gtfs_shape_points
                WHERE shape_id LIKE '30_%_OSM%' OR shape_id LIKE 'TRAM_SEV_%_OSM%'
                GROUP BY shape_id
                ORDER BY shape_id
            """)).fetchall()

            logger.info(f"\n{'='*60}")
            logger.info("SUMMARY - New OSM shapes for Sevilla")
            logger.info(f"{'='*60}")
            total_points = 0
            for shape_id, points in result:
                logger.info(f"  {shape_id}: {points} points")
                total_points += points
            logger.info(f"  TOTAL: {total_points} points")
            logger.info(f"{'='*60}")

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
