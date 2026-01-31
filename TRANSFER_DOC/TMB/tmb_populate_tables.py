#!/usr/bin/env python3
"""
TMB Metro Barcelona - Población de tablas con datos validados de OSM.

Este script lee tmb_data.json (validado) y:
1. ACTUALIZA coordenadas de andenes donde corresponda
2. Usa el mapeo verificado de nombres OSM -> BD

Las estaciones con diferente número de andenes se ignoran (diferencia de
criterio de modelado: BD cuenta 1 andén por estación, OSM cuenta 2 por sentido).

Uso:
    source .venv/bin/activate
    python TRANSFER_DOC/TMB/tmb_populate_tables.py --dry-run
    python TRANSFER_DOC/TMB/tmb_populate_tables.py
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

# Database - soporta DATABASE_URL o variables individuales
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

# Mapeo verificado de nombres OSM -> nombres BD (GTFS)
# Resultado de la revisión manual 2026-01-31
OSM_TO_BD_NAME = {
    # Match directo
    "Arc de Triomf": "Arc de Triomf",
    "La Sagrera": "La Sagrera",
    "Paral·lel": "Paral·lel",
    "Passeig de Gràcia": "Passeig de Gràcia",
    "Sagrada Família": "Sagrada Família",
    "Trinitat Nova": "Trinitat Nova",
    "Universitat": "Universitat",
    "Urquinaona": "Urquinaona",
    "Verdaguer": "Verdaguer",
    "Virrei Amat": "Virrei Amat",
    # Nombre diferente
    "Catalunya": "Plaça de Catalunya",
    # Prefijo a eliminar
    "Metro Urquinaona": "Urquinaona",
    # Líneas separadas -> estación padre
    "Espanya L1": "Espanya",
    "Espanya L3": "Espanya",
}


def load_data() -> Dict:
    """Carga datos validados de tmb_data.json."""
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_bd_stations(conn) -> Dict[str, Dict]:
    """Obtiene estaciones TMB (location_type=1) de BD."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, lat, lon
        FROM gtfs_stops
        WHERE id LIKE 'TMB_METRO_P.%' AND location_type = 1
        ORDER BY name
    """)
    stations = {}
    for row in cur.fetchall():
        stations[row[1]] = {  # Indexado por nombre
            'id': row[0],
            'name': row[1],
            'lat': float(row[2]),
            'lon': float(row[3])
        }
    cur.close()
    return stations


def get_bd_platforms(conn) -> Dict[str, List[Dict]]:
    """Obtiene andenes TMB (location_type=0) agrupados por estación padre."""
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.name, s.lat, s.lon, s.parent_station_id, p.name as parent_name
        FROM gtfs_stops s
        JOIN gtfs_stops p ON s.parent_station_id = p.id
        WHERE s.id LIKE 'TMB_METRO_1.%' AND s.location_type = 0
        ORDER BY p.name, s.id
    """)
    platforms = {}
    for row in cur.fetchall():
        parent_name = row[5]
        if parent_name not in platforms:
            platforms[parent_name] = []
        platforms[parent_name].append({
            'id': row[0],
            'name': row[1],
            'lat': float(row[2]),
            'lon': float(row[3]),
            'parent_id': row[4],
            'parent_name': parent_name
        })
    cur.close()
    return platforms


def normalize_station_name(osm_name: str) -> str:
    """Normaliza nombre de estación OSM para match con BD."""
    # Primero buscar en mapeo explícito
    if osm_name in OSM_TO_BD_NAME:
        return OSM_TO_BD_NAME[osm_name]

    # Eliminar sufijos de línea (ej: "Espanya L1" -> "Espanya")
    for suffix in [" L1", " L2", " L3", " L4", " L5", " L9", " L10", " L11"]:
        if osm_name.endswith(suffix):
            return osm_name[:-len(suffix)]

    # Eliminar prefijo "Metro "
    if osm_name.startswith("Metro "):
        return osm_name[6:]

    return osm_name


def update_platform_coords(conn, osm_data: Dict, bd_platforms: Dict, bd_stations: Dict, dry_run: bool) -> Tuple[int, int, int]:
    """
    Actualiza coordenadas de andenes BD con datos de OSM.

    Casos manejados:
    1. OSM tiene andenes para estación -> usar coords OSM
    2. BD tiene 1 andén, OSM tiene 2 -> usar promedio de coords OSM
    3. Sin match -> ignorar

    Returns:
        (actualizados, ignorados_sin_osm, ignorados_complejo)
    """
    logger.info("=== ACTUALIZANDO COORDENADAS ANDENES ===")

    # Agrupar andenes OSM por nombre de estación normalizado
    osm_by_station = {}
    for anden in osm_data.get('andenes', []):
        osm_name = anden.get('station_name', '?')
        bd_name = normalize_station_name(osm_name)

        if bd_name not in osm_by_station:
            osm_by_station[bd_name] = []
        osm_by_station[bd_name].append(anden)

    updates = []
    ignorados_sin_osm = []
    ignorados_complejo = []
    usaron_promedio = []

    for bd_station_name, bd_plats in bd_platforms.items():
        osm_plats = osm_by_station.get(bd_station_name, [])

        if not osm_plats:
            ignorados_sin_osm.append(bd_station_name)
            continue

        bd_count = len(bd_plats)
        osm_count = len(osm_plats)

        # Caso 1: BD=1, OSM=2 -> usar promedio
        if bd_count == 1 and osm_count == 2:
            avg_lat = sum(p['lat'] for p in osm_plats) / 2
            avg_lon = sum(p['lon'] for p in osm_plats) / 2
            bd_plat = bd_plats[0]

            # Solo actualizar si coords son diferentes (están en la estación padre)
            if abs(bd_plat['lat'] - avg_lat) > 0.00001 or abs(bd_plat['lon'] - avg_lon) > 0.00001:
                updates.append({
                    'id': bd_plat['id'],
                    'name': bd_plat['name'],
                    'lat': avg_lat,
                    'lon': avg_lon,
                    'old_lat': bd_plat['lat'],
                    'old_lon': bd_plat['lon']
                })
                usaron_promedio.append(bd_station_name)

        # Caso 2: BD=OSM -> emparejar 1:1
        elif bd_count == osm_count:
            osm_sorted = sorted(osm_plats, key=lambda x: (x['lat'], x['lon']))
            bd_sorted = sorted(bd_plats, key=lambda x: x['id'])

            for osm_p, bd_p in zip(osm_sorted, bd_sorted):
                if abs(bd_p['lat'] - osm_p['lat']) > 0.00001 or abs(bd_p['lon'] - osm_p['lon']) > 0.00001:
                    updates.append({
                        'id': bd_p['id'],
                        'name': bd_p['name'],
                        'lat': osm_p['lat'],
                        'lon': osm_p['lon'],
                        'old_lat': bd_p['lat'],
                        'old_lon': bd_p['lon']
                    })

        # Caso 3: Diferente número -> ignorar
        else:
            ignorados_complejo.append((bd_station_name, osm_count, bd_count))

    # Log resultados
    logger.info(f"  Estaciones con datos OSM: {len(osm_by_station)}")
    logger.info(f"  Estaciones BD: {len(bd_platforms)}")
    logger.info(f"  Andenes a actualizar: {len(updates)}")

    if usaron_promedio:
        logger.info(f"  Usaron promedio (BD=1, OSM=2): {len(usaron_promedio)}")
        for st in usaron_promedio[:5]:
            logger.info(f"    {st}")
        if len(usaron_promedio) > 5:
            logger.info(f"    ... y {len(usaron_promedio) - 5} más")

    if ignorados_complejo:
        logger.info(f"  Ignoradas (diferente count): {len(ignorados_complejo)}")
        for st, osm, bd in ignorados_complejo[:5]:
            logger.info(f"    {st}: OSM={osm}, BD={bd}")

    if ignorados_sin_osm:
        logger.info(f"  Sin datos OSM: {len(ignorados_sin_osm)}")

    # Mostrar algunos updates
    if updates:
        logger.info(f"  Ejemplos de updates:")
        for upd in updates[:5]:
            logger.info(f"    {upd['name']}: ({upd['old_lat']:.6f}, {upd['old_lon']:.6f}) -> ({upd['lat']:.6f}, {upd['lon']:.6f})")

    if dry_run:
        logger.info(f"  [DRY-RUN] Se actualizarían {len(updates)} andenes")
        return len(updates), len(ignorados_sin_osm), len(ignorados_complejo)

    if updates:
        cur = conn.cursor()
        for upd in updates:
            cur.execute("""
                UPDATE gtfs_stops
                SET lat = %s, lon = %s
                WHERE id = %s
            """, (upd['lat'], upd['lon'], upd['id']))
        conn.commit()
        cur.close()
        logger.info(f"  Actualizados: {len(updates)} andenes")

    return len(updates), len(ignorados_sin_osm), len(ignorados_complejo)


def show_summary(osm_data: Dict, bd_platforms: Dict, bd_stations: Dict):
    """Muestra resumen de datos a procesar."""
    logger.info("=== RESUMEN DATOS ===")
    logger.info(f"  OSM - Andenes: {len(osm_data.get('andenes', []))}")
    logger.info(f"  OSM - Accesos: {len(osm_data.get('accesos', []))}")
    logger.info(f"  OSM - Estaciones con andenes: {len(osm_data.get('andenes_por_estacion', {}))}")
    logger.info(f"  BD - Estaciones: {len(bd_stations)}")
    logger.info(f"  BD - Estaciones con andenes: {len(bd_platforms)}")
    logger.info(f"  BD - Total andenes: {sum(len(p) for p in bd_platforms.values())}")


def main():
    parser = argparse.ArgumentParser(description="Poblar tablas TMB con datos OSM")
    parser.add_argument('--dry-run', action='store_true', help="Simular sin hacer cambios")
    parser.add_argument('--analyze-only', action='store_true', help="Solo analizar, no modificar")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("TMB Metro Barcelona - Población de tablas")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("*** MODO DRY-RUN - No se harán cambios ***")

    # Cargar datos OSM
    logger.info(f"Cargando datos de: {DATA_FILE}")
    osm_data = load_data()

    # Conectar BD
    logger.info(f"Conectando a BD...")
    conn = psycopg2.connect(DATABASE_URL)

    try:
        # Obtener datos BD
        bd_stations = get_bd_stations(conn)
        bd_platforms = get_bd_platforms(conn)

        # Mostrar resumen
        show_summary(osm_data, bd_platforms, bd_stations)

        if args.analyze_only:
            logger.info("Modo análisis - no se realizan cambios")
            return

        # Actualizar coordenadas de andenes
        actualizados, sin_osm, complejos = update_platform_coords(
            conn, osm_data, bd_platforms, bd_stations, args.dry_run
        )

        # Resumen final
        logger.info("")
        logger.info("=" * 60)
        logger.info("RESUMEN FINAL")
        logger.info("=" * 60)
        logger.info(f"  Andenes actualizados: {actualizados}")
        logger.info(f"  Estaciones sin datos OSM: {sin_osm}")
        logger.info(f"  Estaciones complejas (ignoradas): {complejos}")

        if args.dry_run:
            logger.info("")
            logger.info("*** Ejecutar sin --dry-run para aplicar cambios ***")

    finally:
        conn.close()

    logger.info("")
    logger.info("Completado.")


if __name__ == "__main__":
    main()
