#!/usr/bin/env python3
"""
Import correspondences from OSM stop_area_group relations.

This script:
1. Queries OSM Overpass API for stop_area_group relations
2. Analyzes each group to determine if it's:
   - Same station with multiple lines -> stop_platform only
   - Different stations connected -> stop_correspondence
3. Matches OSM stations to our database
4. Imports data into stop_platform and/or stop_correspondence

Usage:
    .venv/bin/python scripts/import_osm_correspondences.py --city madrid
    .venv/bin/python scripts/import_osm_correspondences.py --all
    .venv/bin/python scripts/import_osm_correspondences.py --city madrid --dry-run

See docs/IMPORT_OSM_CORRESPONDENCES.md for full documentation.
"""
import argparse
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional
import requests

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import SessionLocal

# OSM network to our prefix mapping
NETWORK_MAPPING = {
    'metro de madrid': 'METRO_',
    'metro de barcelona': 'TMB_METRO_',
    'fgc': 'FGC_',
    'ferrocarrils de la generalitat de catalunya': 'FGC_',
    'metro del baix llobregat': 'FGC_',  # FGC line
    'cercanías madrid': 'RENFE_',
    'rodalies barcelona': 'RENFE_',
    'rodalies de catalunya': 'RENFE_',
    'metro bilbao': 'METRO_BILBAO_',
    'euskotren': 'EUSKOTREN_',
    'tram barcelona': 'TRAM_BARCELONA_',
    'metrovalencia': 'METRO_VALENCIA_',
    'metro de sevilla': 'METRO_SEV_',
    'metro de málaga': 'METRO_MALAGA_',
    'metro de granada': 'METRO_GRANADA_',
}

# City bounding boxes for filtering
CITY_BBOX = {
    'madrid': (40.3, -3.9, 40.6, -3.5),
    'barcelona': (41.3, 2.0, 41.5, 2.3),
    'bilbao': (43.2, -3.0, 43.4, -2.8),
    'valencia': (39.4, -0.5, 39.6, -0.3),
    'sevilla': (37.3, -6.1, 37.5, -5.9),
}

# Known stop_area_group IDs by city (some don't have bounds in API response)
KNOWN_GROUPS = {
    'madrid': [
        7849782,   # Plaza de España - Noviciado
        7849788,   # Moncloa
        7849793,   # Cuatro Caminos
        7849798,   # Bilbao
        7718408,   # Avenida de América
        7718417,   # Sol
        7718418,   # Atocha
        7894618,   # Plaza de Castilla
        7894621,   # Plaza Elíptica
        10077012,  # Aeropuerto T4 (transbordo)
        10077017,  # Estación Paco de Lucía
        10077046,  # Trasbordo Vicálvaro - Puerta de Arganda
        10077099,  # Sierra de Guadalupe - Vallecas
    ],
    'barcelona': [
        4125372,   # Catalunya
        5720834,   # Espanya (TMB + FGC)
        6648219,   # El Clot
        7646482,   # Sagrada Família
        7646492,   # Passeig de Gràcia
        7646696,   # Sants Estació
        7781537,   # Plaça d'Espanya
        7782168,   # Aeroport T2
        7782174,   # Provença/Diagonal
        7782177,   # Universitat
        7857590,   # Urquinaona
        7873703,   # Trinitat Nova
        7884318,   # El Prat de Llobregat
        7890707,   # Plaça de Sants
        7890712,   # Avinguda Carrilet
        7926003,   # Monistrol de Montserrat (FGC)
        10379730,  # Sant Gervasi / Plaça Molina
        18468321,  # Hospital de Bellvitge
        18468578,  # Sant Ildefons
        18468638,  # Rambla de Sant Just
        18480399,  # Sant Boi - Pl. Europa
        20029907,  # Sant Andreu
        20029921,  # Sant Adrià
        20029922,  # Sant Roc
    ],
    'bilbao': [
        12227411,  # Abando (Geltokia/Estación)
    ],
    'valencia': [
        11789701,  # València - Sant Isidre
    ],
    'zaragoza': [
        6204978,   # Estación Intermodal Zaragoza-Delicias
        18082571,  # Plaza Aragón
    ],
    'granada': [
        20127125,  # Estación de Ferrocarril de Granada
    ],
}


def normalize_name(name: str) -> str:
    """Normalize station name for matching."""
    # Remove accents
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    # Lowercase and strip
    name = name.lower().strip()
    # Remove common prefixes
    name = re.sub(r'^(estacion de |estacio de |estacio |station |parada )', '', name)
    # Remove line suffixes like "L1", "L3 (metro)"
    name = re.sub(r'\s+l\d+.*$', '', name)
    name = re.sub(r'\s+\(.*\)$', '', name)
    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name)
    return name


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def query_overpass(query: str) -> dict:
    """Execute Overpass API query."""
    url = "https://overpass-api.de/api/interpreter"
    response = requests.post(url, data={'data': query}, timeout=120)
    response.raise_for_status()
    return response.json()


def get_all_stop_area_groups() -> list:
    """Get all stop_area_group relations from OSM."""
    query = """
    [out:json][timeout:120];
    (
      relation["public_transport"="stop_area_group"];
    );
    out body geom;
    """
    data = query_overpass(query)
    return data.get('elements', [])


def get_relation_members(relation_ids: list) -> dict:
    """Get details of multiple relations."""
    # Build query with relation IDs
    ids_list = ",".join(str(rid) for rid in relation_ids)
    query = f"""
    [out:json][timeout:60];
    (
      relation(id:{ids_list});
    );
    out body;
    """
    data = query_overpass(query)
    return {el['id']: el for el in data.get('elements', []) if el['type'] == 'relation'}


def get_stop_area_coords(relation_id: int) -> Optional[tuple]:
    """Get coordinates for a stop_area (centroid of platforms or station node)."""
    query = f"""
    [out:json][timeout:30];
    relation({relation_id});
    (
      node(r)["railway"="station"];
      node(r)["public_transport"="station"];
      way(r)["railway"="platform"];
      node(r)["railway"="platform"];
    );
    out center;
    """
    try:
        data = query_overpass(query)
        lats, lons = [], []
        for el in data.get('elements', []):
            if el['type'] == 'node':
                lats.append(el.get('lat', 0))
                lons.append(el.get('lon', 0))
            elif el['type'] == 'way' and 'center' in el:
                lats.append(el['center'].get('lat', 0))
                lons.append(el['center'].get('lon', 0))

        if lats and lons:
            return (sum(lats) / len(lats), sum(lons) / len(lons))
    except Exception as e:
        print(f"  [WARN] Could not get coords for relation {relation_id}: {e}")
    return None


def find_stop_in_db(session, name: str, network_prefix: str = None, lat: float = None, lon: float = None) -> Optional[dict]:
    """Find a stop in our database by name and optionally coordinates."""
    normalized = normalize_name(name)

    # Build query
    if network_prefix:
        result = session.execute(text("""
            SELECT id, name, cor_metro, cor_cercanias, cor_ml, cor_tranvia, lat, lon
            FROM gtfs_stops
            WHERE id LIKE :prefix AND lat IS NOT NULL
        """), {'prefix': f'{network_prefix}%'}).fetchall()
    else:
        result = session.execute(text("""
            SELECT id, name, cor_metro, cor_cercanias, cor_ml, cor_tranvia, lat, lon
            FROM gtfs_stops
            WHERE lat IS NOT NULL
        """)).fetchall()

    # Find best match by name
    candidates = []
    for row in result:
        if normalize_name(row[1]) == normalized:
            candidates.append({
                'id': row[0],
                'name': row[1],
                'cor_metro': row[2],
                'cor_cercanias': row[3],
                'cor_ml': row[4],
                'cor_tranvia': row[5],
                'lat': row[6],
                'lon': row[7],
            })

    if not candidates:
        # Try partial match
        for row in result:
            if normalized in normalize_name(row[1]) or normalize_name(row[1]) in normalized:
                candidates.append({
                    'id': row[0],
                    'name': row[1],
                    'cor_metro': row[2],
                    'cor_cercanias': row[3],
                    'cor_ml': row[4],
                    'cor_tranvia': row[5],
                    'lat': row[6],
                    'lon': row[7],
                })

    if not candidates:
        return None

    # If we have coordinates, pick the closest one
    if lat and lon and len(candidates) > 1:
        candidates.sort(key=lambda c: haversine(lat, lon, c['lat'], c['lon']))

    return candidates[0]


def analyze_group(group: dict, members: dict) -> dict:
    """Analyze a stop_area_group to determine its type and contents."""
    group_name = group.get('tags', {}).get('name', 'Unknown')
    member_relations = [m['ref'] for m in group.get('members', []) if m['type'] == 'relation']

    stations = []
    for rel_id in member_relations:
        rel = members.get(rel_id)
        if rel:
            tags = rel.get('tags', {})
            name = tags.get('name', '')
            network = tags.get('network', '').lower()

            # Extract line from name if present
            line_match = re.search(r'[Ll](\d+)', name)
            line = f"L{line_match.group(1)}" if line_match else None

            stations.append({
                'osm_id': rel_id,
                'name': name,
                'normalized_name': normalize_name(name),
                'network': network,
                'line': line,
            })

    # Determine if this is same-station or different-stations
    unique_names = set(s['normalized_name'] for s in stations)
    unique_networks = set(s['network'] for s in stations if s['network'])

    # It's a correspondence if:
    # - Different station names (Noviciado vs Plaza de España)
    # - OR different networks (TMB vs FGC)
    is_correspondence = len(unique_names) > 1 or len(unique_networks) > 1

    return {
        'osm_id': group['id'],
        'name': group_name,
        'is_correspondence': is_correspondence,
        'stations': stations,
        'unique_names': unique_names,
        'unique_networks': unique_networks,
    }


def import_group(session, analysis: dict, dry_run: bool = False) -> dict:
    """Import a group into the database."""
    result = {
        'group_name': analysis['name'],
        'is_correspondence': analysis['is_correspondence'],
        'platforms_added': 0,
        'correspondences_added': 0,
        'not_found': [],
    }

    # Get coordinates for each station
    for station in analysis['stations']:
        coords = get_stop_area_coords(station['osm_id'])
        station['coords'] = coords

    # Find matching stops in our DB
    for station in analysis['stations']:
        # Determine prefix from network
        prefix = None
        for osm_net, db_prefix in NETWORK_MAPPING.items():
            if osm_net in station['network']:
                prefix = db_prefix
                break

        lat, lon = station['coords'] if station['coords'] else (None, None)
        db_stop = find_stop_in_db(session, station['name'], prefix, lat, lon)
        station['db_stop'] = db_stop

        if not db_stop:
            result['not_found'].append(station['name'])

    # Process based on type
    if analysis['is_correspondence']:
        # Insert stop_correspondence for each pair of different stations
        found_stations = [s for s in analysis['stations'] if s['db_stop']]

        for i, s1 in enumerate(found_stations):
            for s2 in found_stations[i+1:]:
                # Only add correspondence if they're actually different stops
                if s1['db_stop']['id'] != s2['db_stop']['id']:
                    # Calculate distance
                    if s1['coords'] and s2['coords']:
                        dist = int(haversine(s1['coords'][0], s1['coords'][1],
                                           s2['coords'][0], s2['coords'][1]))
                    else:
                        dist = 200  # Default estimate

                    walk_time = int(dist / 1.2)  # ~1.2 m/s walking

                    if not dry_run:
                        # Insert bidirectional
                        for from_id, to_id in [(s1['db_stop']['id'], s2['db_stop']['id']),
                                               (s2['db_stop']['id'], s1['db_stop']['id'])]:
                            session.execute(text("""
                                INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
                                VALUES (:from_id, :to_id, :dist, :time, 'osm')
                                ON CONFLICT (from_stop_id, to_stop_id) DO UPDATE SET
                                    distance_m = :dist, walk_time_s = :time
                            """), {'from_id': from_id, 'to_id': to_id, 'dist': dist, 'time': walk_time})
                            result['correspondences_added'] += 1
                    else:
                        print(f"  [DRY-RUN] Would add correspondence: {s1['db_stop']['name']} <-> {s2['db_stop']['name']} ({dist}m)")
                        result['correspondences_added'] += 2

    # Add platform coordinates if we have them
    for station in analysis['stations']:
        if station['db_stop'] and station['coords'] and station['line']:
            if not dry_run:
                session.execute(text("""
                    INSERT INTO stop_platform (stop_id, lines, lat, lon, source)
                    VALUES (:stop_id, :lines, :lat, :lon, 'osm')
                    ON CONFLICT (stop_id, lines) DO UPDATE SET
                        lat = :lat, lon = :lon
                """), {
                    'stop_id': station['db_stop']['id'],
                    'lines': station['line'],
                    'lat': station['coords'][0],
                    'lon': station['coords'][1],
                })
                result['platforms_added'] += 1
            else:
                print(f"  [DRY-RUN] Would add platform: {station['db_stop']['name']} {station['line']}")
                result['platforms_added'] += 1

    if not dry_run:
        session.commit()

    return result


def main():
    parser = argparse.ArgumentParser(description='Import OSM stop_area_group correspondences')
    parser.add_argument('--city', type=str, choices=list(CITY_BBOX.keys()), help='City to import')
    parser.add_argument('--all', action='store_true', help='Import all cities')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without making changes')
    parser.add_argument('--group-id', type=int, help='Import specific OSM relation ID')
    args = parser.parse_args()

    if not args.city and not args.all and not args.group_id:
        parser.print_help()
        return

    print("=" * 60)
    print("Import OSM stop_area_group Correspondences")
    print("=" * 60)

    session = SessionLocal()

    # Get all stop_area_groups
    print("\nFetching stop_area_group relations from OSM...")
    all_groups = get_all_stop_area_groups()
    print(f"Found {len(all_groups)} stop_area_group relations globally")

    # Filter by city/bbox or specific ID
    if args.group_id:
        groups = [g for g in all_groups if g['id'] == args.group_id]
    elif args.city:
        # Use known groups + bbox filter
        known_ids = KNOWN_GROUPS.get(args.city, [])
        bbox = CITY_BBOX[args.city]
        groups = []
        for g in all_groups:
            # Include if in known list
            if g['id'] in known_ids:
                groups.append(g)
                continue
            # Or if within bbox
            bounds = g.get('bounds', {})
            if bounds:
                lat = (bounds.get('minlat', 0) + bounds.get('maxlat', 0)) / 2
                lon = (bounds.get('minlon', 0) + bounds.get('maxlon', 0)) / 2
                if bbox[0] < lat < bbox[2] and bbox[1] < lon < bbox[3]:
                    groups.append(g)
    else:  # --all
        # Use all known groups + Spain bbox filter
        all_known_ids = set()
        for city_ids in KNOWN_GROUPS.values():
            all_known_ids.update(city_ids)

        groups = []
        for g in all_groups:
            if g['id'] in all_known_ids:
                groups.append(g)
                continue
            bounds = g.get('bounds', {})
            if bounds:
                lat = (bounds.get('minlat', 0) + bounds.get('maxlat', 0)) / 2
                lon = (bounds.get('minlon', 0) + bounds.get('maxlon', 0)) / 2
                if 36 < lat < 44 and -10 < lon < 5:
                    groups.append(g)

    print(f"Processing {len(groups)} groups")

    # Get member relations
    all_member_ids = []
    for g in groups:
        for m in g.get('members', []):
            if m['type'] == 'relation':
                all_member_ids.append(m['ref'])

    print(f"Fetching {len(all_member_ids)} member relations...")
    members = get_relation_members(all_member_ids) if all_member_ids else {}

    # Process each group
    total_platforms = 0
    total_correspondences = 0
    not_found_all = []

    for group in groups:
        name = group.get('tags', {}).get('name', 'Unknown')
        print(f"\n[{name}]")

        analysis = analyze_group(group, members)
        print(f"  Type: {'Correspondence' if analysis['is_correspondence'] else 'Same station'}")
        print(f"  Stations: {', '.join(analysis['unique_names'])}")

        result = import_group(session, analysis, args.dry_run)

        if result['not_found']:
            print(f"  [WARN] Not found in DB: {', '.join(result['not_found'])}")
            not_found_all.extend(result['not_found'])

        total_platforms += result['platforms_added']
        total_correspondences += result['correspondences_added']

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Platforms added/updated: {total_platforms}")
    print(f"Correspondences added/updated: {total_correspondences}")
    if not_found_all:
        print(f"\nStations not found in DB ({len(not_found_all)}):")
        for name in set(not_found_all):
            print(f"  - {name}")

    session.close()


if __name__ == "__main__":
    main()
