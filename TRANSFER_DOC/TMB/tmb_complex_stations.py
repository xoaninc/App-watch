#!/usr/bin/env python3
"""
TMB Metro Barcelona - Actualización de estaciones complejas.

Este script maneja estaciones donde el número de andenes OSM != BD.
Agrupa andenes OSM por línea y calcula promedios para actualizar BD.

Uso:
    source .venv/bin/activate
    python TRANSFER_DOC/TMB/tmb_complex_stations.py --dry-run
    python TRANSFER_DOC/TMB/tmb_complex_stations.py
"""

import os
import json
import argparse
import logging
from typing import Dict, List, Tuple

import psycopg2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "renfeserver_dev")
    DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{db}"

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "tmb_data_v2.json")

# Mapeo manual de estaciones complejas
# Formato: BD station name -> {BD platform suffix -> [OSM line filter]}
# Esto mapea cada andén BD a las líneas OSM que corresponden
COMPLEX_STATION_MAPPING = {
    "La Pau": {
        # BD tiene 2 andenes, OSM tiene 4 (2 por L2, 2 por L4)
        "221": ["L2"],  # 1.221 -> L2
        "413": ["L4"],  # 1.413 -> L4
    },
    "La Sagrera": {
        # BD tiene 3 andenes (L1, L5, L9/L10), OSM tiene 2 (solo L9/L10)
        "133": [],  # L1 - sin datos OSM
        "526": [],  # L5 - sin datos OSM
        "930": ["L9N-L10N", "L9", "L10"],  # L9/L10 -> usar OSM
    },
    "Passeig de Gràcia": {
        # BD tiene 3 andenes (L2, L3, L4), OSM tiene 4 (2 por L2, 2 por L3)
        "213": ["L2"],  # 1.213 -> L2
        "327": ["L3"],  # 1.327 -> L3
        "425": ["L4"],  # 1.425 -> L4 (sin datos OSM específicos)
    },
    "Sagrada Família": {
        # BD tiene 2 andenes (L2, L5), OSM tiene 4 (2 por línea)
        "216": ["L2"],  # 1.216 -> L2
        "523": ["L5"],  # 1.523 -> L5
    },
    "Paral·lel": {
        # BD tiene 3 andenes (L2, L3, funicular), OSM tiene 4 (L2, L3)
        "210": ["L2"],  # Paral·lel L2
        "323": ["L3"],  # Paral·lel L3
        "9901": [],  # Funicular Montjuïc - sin datos OSM
    },
    "Verdaguer": {
        # BD tiene 2 andenes (L4, L5), OSM tiene 2 (solo L5)
        "427": [],  # L4 - sin datos OSM específicos
        "522": ["L5"],  # usar OSM L5
    },
    "Universitat": {
        # BD tiene 2 andenes (L1, L2), OSM tiene 4
        "125": ["L1"],  # 1.125 -> L1
        "212": ["L2"],  # 1.212 -> L2
    },
    "Urquinaona": {
        # BD tiene 2 andenes (L1, L4), OSM tiene muchos (incluye accesos)
        "127": ["L1"],  # 1.127 -> L1
        "424": ["L4"],  # 1.424 -> L4
    },
    "Espanya": {
        # BD tiene 2 andenes (L1, L3), OSM tiene 4 (Espanya L1 y L3)
        "122": ["L1"],  # 1.122 -> L1
        "321": ["L3"],  # 1.321 -> L3
    },
}


def load_osm_data() -> Dict:
    """Carga datos de OSM."""
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_bd_platforms(conn, station_name: str) -> List[Dict]:
    """Obtiene andenes BD para una estación."""
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.name, s.lat, s.lon
        FROM gtfs_stops s
        JOIN gtfs_stops p ON s.parent_station_id = p.id
        WHERE p.name = %s AND s.location_type = 0 AND s.id LIKE 'TMB_METRO_1.%%'
        ORDER BY s.id
    """, (station_name,))
    platforms = []
    for row in cur.fetchall():
        platforms.append({
            'id': row[0],
            'name': row[1],
            'lat': float(row[2]),
            'lon': float(row[3]),
            'suffix': row[0].split('.')[-1]  # Extract numeric suffix
        })
    cur.close()
    return platforms


def get_osm_platforms_for_station(osm_data: Dict, station_name: str) -> List[Dict]:
    """Obtiene andenes OSM para una estación."""
    platforms = []
    for anden in osm_data.get('andenes', []):
        osm_station = anden.get('station_name', '').lower()
        if station_name.lower() in osm_station or osm_station in station_name.lower():
            platforms.append(anden)
    return platforms


def filter_osm_by_line(osm_platforms: List[Dict], line_filters: List[str]) -> List[Dict]:
    """Filtra andenes OSM por línea (busca en line y station_name)."""
    if not line_filters:
        return []

    filtered = []
    for p in osm_platforms:
        line = p.get('line', '').lower()
        station = p.get('station_name', '').lower()
        searchable = f"{line} {station}"

        for f in line_filters:
            if f.lower() in searchable:
                filtered.append(p)
                break
    return filtered


def calculate_centroid(platforms: List[Dict]) -> Tuple[float, float]:
    """Calcula centroide de una lista de andenes."""
    if not platforms:
        return None, None

    lat_sum = sum(p['lat'] for p in platforms)
    lon_sum = sum(p['lon'] for p in platforms)
    n = len(platforms)

    return lat_sum / n, lon_sum / n


def update_complex_stations(conn, osm_data: Dict, dry_run: bool) -> Tuple[int, int]:
    """
    Actualiza coordenadas de estaciones complejas.

    Returns:
        (actualizados, sin_cambios)
    """
    logger.info("=== ACTUALIZANDO ESTACIONES COMPLEJAS ===")

    updates = []
    no_change = []

    for station_name, mapping in COMPLEX_STATION_MAPPING.items():
        logger.info(f"")
        logger.info(f"### {station_name} ###")

        bd_platforms = get_bd_platforms(conn, station_name)
        osm_platforms = get_osm_platforms_for_station(osm_data, station_name)

        logger.info(f"  BD andenes: {len(bd_platforms)}")
        logger.info(f"  OSM andenes: {len(osm_platforms)}")

        for bd_plat in bd_platforms:
            suffix = bd_plat['suffix']

            if suffix not in mapping:
                logger.info(f"  {bd_plat['id']}: No hay mapeo definido")
                no_change.append(bd_plat)
                continue

            line_filters = mapping[suffix]

            if not line_filters:
                logger.info(f"  {bd_plat['id']}: Sin datos OSM disponibles")
                no_change.append(bd_plat)
                continue

            # Filter OSM platforms by line
            filtered_osm = filter_osm_by_line(osm_platforms, line_filters)

            if not filtered_osm:
                logger.info(f"  {bd_plat['id']}: No se encontraron andenes OSM para {line_filters}")
                no_change.append(bd_plat)
                continue

            # Calculate centroid
            new_lat, new_lon = calculate_centroid(filtered_osm)

            if new_lat is None:
                no_change.append(bd_plat)
                continue

            # Check if coords are different
            if abs(bd_plat['lat'] - new_lat) > 0.00001 or abs(bd_plat['lon'] - new_lon) > 0.00001:
                updates.append({
                    'id': bd_plat['id'],
                    'old_lat': bd_plat['lat'],
                    'old_lon': bd_plat['lon'],
                    'new_lat': new_lat,
                    'new_lon': new_lon,
                    'osm_count': len(filtered_osm)
                })
                logger.info(f"  {bd_plat['id']}: ({bd_plat['lat']:.6f}, {bd_plat['lon']:.6f}) -> ({new_lat:.6f}, {new_lon:.6f}) [from {len(filtered_osm)} OSM]")
            else:
                logger.info(f"  {bd_plat['id']}: Coords ya correctas")
                no_change.append(bd_plat)

    logger.info("")
    logger.info(f"=== RESUMEN ===")
    logger.info(f"  A actualizar: {len(updates)}")
    logger.info(f"  Sin cambios: {len(no_change)}")

    if dry_run:
        logger.info("")
        logger.info("[DRY-RUN] No se aplicaron cambios")
        return len(updates), len(no_change)

    # Apply updates
    if updates:
        cur = conn.cursor()
        for upd in updates:
            cur.execute("""
                UPDATE gtfs_stops SET lat = %s, lon = %s WHERE id = %s
            """, (upd['new_lat'], upd['new_lon'], upd['id']))
        conn.commit()
        cur.close()
        logger.info(f"  Actualizados: {len(updates)}")

    return len(updates), len(no_change)


def main():
    parser = argparse.ArgumentParser(description="Actualizar estaciones complejas TMB")
    parser.add_argument('--dry-run', action='store_true', help="Simular sin cambios")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("TMB Metro - Estaciones Complejas")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("*** MODO DRY-RUN ***")

    osm_data = load_osm_data()
    conn = psycopg2.connect(DATABASE_URL)

    try:
        updated, no_change = update_complex_stations(conn, osm_data, args.dry_run)

        logger.info("")
        logger.info("=" * 60)
        logger.info("COMPLETADO")
        logger.info("=" * 60)
        logger.info(f"  Andenes actualizados: {updated}")
        logger.info(f"  Sin cambios: {no_change}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
