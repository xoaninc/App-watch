#!/usr/bin/env python3
"""
FGC - Población de tablas con datos validados de OSM.

Este script lee fgc_data.json (validado) y:
1. INSERTA accesos nuevos en gtfs_stops (location_type=2)
2. ACTUALIZA coordenadas de andenes SOLO donde coincide el número OSM=BD

Las estaciones con diferente número de andenes se ignoran (diferencia de
criterio de modelado: BD cuenta vías, OSM cuenta andenes físicos).

Uso:
    source .venv/bin/activate
    python TRANSFER_DOC/FGC/fgc_populate_tables.py --dry-run
    python TRANSFER_DOC/FGC/fgc_populate_tables.py
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
DATA_FILE = os.path.join(SCRIPT_DIR, "fgc_data.json")


def load_data() -> Dict:
    """Carga datos validados de fgc_data.json."""
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_existing_stops(conn) -> Dict[str, Dict]:
    """Obtiene paradas FGC existentes en BD."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, lat, lon, location_type, parent_station_id
        FROM gtfs_stops
        WHERE id LIKE 'FGC_%'
        ORDER BY id
    """)
    stops = {}
    for row in cur.fetchall():
        stops[row[0]] = {
            'id': row[0],
            'name': row[1],
            'lat': row[2],
            'lon': row[3],
            'location_type': row[4],
            'parent_station_id': row[5]
        }
    cur.close()
    return stops


def insert_accesos(conn, accesos: List[Dict], existing_stops: Dict, dry_run: bool) -> int:
    """Inserta accesos nuevos en gtfs_stops."""
    logger.info("=== INSERTANDO ACCESOS ===")

    # Mapeo estación -> GTFS parent ID
    station_to_gtfs = {
        "Catalunya (FGC)": "FGC_PC",
        "Espanya (FGC)": "FGC_PE",
        "Gràcia": "FGC_GR",
        "Provença (FGC)": "FGC_PR"
    }

    # Set para trackear IDs usados
    used_ids = set(existing_stops.keys())

    # Set de coordenadas existentes para detectar duplicados
    existing_coords = set()
    for stop in existing_stops.values():
        if stop['location_type'] == 2:  # Solo accesos
            existing_coords.add((round(stop['lat'], 5), round(stop['lon'], 5)))

    inserts = []
    skipped = 0
    for acc in accesos:
        parent_id = station_to_gtfs.get(acc['estacion'])
        if not parent_id:
            logger.warning(f"  Sin parent para acceso: {acc['estacion']}")
            continue

        # Verificar si ya existe un acceso en estas coordenadas
        coords = (round(acc['lat'], 5), round(acc['lon'], 5))
        if coords in existing_coords:
            skipped += 1
            continue

        # Generar ID único para acceso
        base_id = f"{parent_id}_ACC"
        n = 1
        while f"{base_id}_{n}" in used_ids:
            n += 1
        access_id = f"{base_id}_{n}"
        used_ids.add(access_id)

        inserts.append({
            'id': access_id,
            'name': acc['nombre'],
            'lat': acc['lat'],
            'lon': acc['lon'],
            'location_type': 2,
            'parent_station_id': parent_id
        })
        logger.info(f"  + {access_id} | {acc['nombre']} | {acc['lat']}, {acc['lon']}")

    if skipped:
        logger.info(f"  Omitidos {skipped} accesos (ya existen)")

    if dry_run:
        logger.info(f"  [DRY-RUN] Se insertarían {len(inserts)} accesos")
        return len(inserts)

    if inserts:
        cur = conn.cursor()
        for acc in inserts:
            cur.execute("""
                INSERT INTO gtfs_stops (id, name, lat, lon, location_type, parent_station_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (acc['id'], acc['name'], acc['lat'], acc['lon'],
                  acc['location_type'], acc['parent_station_id']))
        conn.commit()
        cur.close()
        logger.info(f"  Insertados: {len(inserts)} accesos")

    return len(inserts)


def update_platform_coords(conn, andenes: List[Dict], existing_stops: Dict, dry_run: bool) -> Tuple[int, int, int]:
    """
    Actualiza coordenadas de andenes.

    Casos manejados:
    1. OSM=BD: Emparejar 1:1 por orden
    2. OSM=1, BD=2 (andén central): Asignar misma coordenada OSM a ambas vías BD
    3. Otros casos: Ignorar (estaciones complejas, requieren revisión manual)

    Returns:
        (actualizados, ignorados_complejos, ignorados_sin_bd)
    """
    logger.info("=== ACTUALIZANDO COORDENADAS ANDENES ===")

    # Agrupar andenes OSM por estación (gtfs_parent_id)
    osm_by_station = {}
    for anden in andenes:
        gtfs_id = anden.get('gtfs_parent_id')
        if not gtfs_id:
            continue
        if gtfs_id not in osm_by_station:
            osm_by_station[gtfs_id] = []
        osm_by_station[gtfs_id].append(anden)

    # Agrupar andenes BD por estación
    bd_by_station = {}
    for stop_id, stop in existing_stops.items():
        if stop['location_type'] == 0:  # Solo andenes
            parent = stop['parent_station_id']
            if parent and parent.startswith('FGC_'):
                if parent not in bd_by_station:
                    bd_by_station[parent] = []
                bd_by_station[parent].append(stop)

    updates = []
    ignorados_complejos = []
    ignorados_sin_bd = []
    andenes_centrales = []

    for station_id, osm_platforms in osm_by_station.items():
        bd_platforms = bd_by_station.get(station_id, [])

        if not bd_platforms:
            ignorados_sin_bd.append(station_id)
            continue

        osm_count = len(osm_platforms)
        bd_count = len(bd_platforms)

        # Caso 1: Coincide el número - emparejar 1:1
        if osm_count == bd_count:
            osm_sorted = sorted(osm_platforms, key=lambda x: (x['lat'], x['lon']))
            bd_sorted = sorted(bd_platforms, key=lambda x: (x['id']))

            for osm_p, bd_p in zip(osm_sorted, bd_sorted):
                if bd_p['lat'] != osm_p['lat'] or bd_p['lon'] != osm_p['lon']:
                    updates.append({
                        'id': bd_p['id'],
                        'lat': osm_p['lat'],
                        'lon': osm_p['lon']
                    })

        # Caso 2: Andén central - OSM=1, BD=2 (asignar misma coord a ambas vías)
        elif osm_count == 1 and bd_count == 2:
            osm_p = osm_platforms[0]
            for bd_p in bd_platforms:
                if bd_p['lat'] != osm_p['lat'] or bd_p['lon'] != osm_p['lon']:
                    updates.append({
                        'id': bd_p['id'],
                        'lat': osm_p['lat'],
                        'lon': osm_p['lon']
                    })
            andenes_centrales.append(station_id)

        # Caso 3: Estación compleja - ignorar
        else:
            ignorados_complejos.append((station_id, osm_count, bd_count))

    # Log resultados
    if andenes_centrales:
        logger.info(f"  Andenes centrales (OSM=1 → BD=2): {len(andenes_centrales)} estaciones")
        for st in andenes_centrales[:5]:
            logger.info(f"    {st}")
        if len(andenes_centrales) > 5:
            logger.info(f"    ... y {len(andenes_centrales) - 5} más")

    if ignorados_complejos:
        logger.info(f"  Ignoradas {len(ignorados_complejos)} estaciones complejas:")
        for st, osm, bd in ignorados_complejos[:5]:
            logger.info(f"    {st}: OSM={osm}, BD={bd}")
        if len(ignorados_complejos) > 5:
            logger.info(f"    ... y {len(ignorados_complejos) - 5} más")

    if ignorados_sin_bd:
        logger.info(f"  Ignoradas {len(ignorados_sin_bd)} estaciones (no existen en BD)")

    logger.info(f"  Andenes a actualizar: {len(updates)}")

    if dry_run:
        logger.info(f"  [DRY-RUN] Se actualizarían {len(updates)} andenes")
        return len(updates), len(ignorados_complejos), len(ignorados_sin_bd)

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

    return len(updates), len(ignorados_complejos), len(ignorados_sin_bd)


def fix_phantom_platforms(conn, andenes: List[Dict], dry_run: bool) -> Tuple[int, int]:
    """
    Corrige estaciones con "vías fantasma" (BD tiene más andenes que OSM).

    Estas estaciones tienen vías de mercancías/maniobras en BD que no son de pasajeros.
    Se eliminan los andenes extra y se actualizan los restantes con coords OSM.

    Estaciones afectadas:
    - FGC_GR (Gràcia): 4→2
    - FGC_MA (Manresa Alta): 4→2
    - FGC_SV (Sant Vicenç Castellgalí): 4→2
    - FGC_MO (Monistrol de Montserrat): 4→2

    Returns:
        (eliminados, actualizados)
    """
    logger.info("=== CORRIGIENDO VÍAS FANTASMA ===")

    # Estaciones a corregir: mantener andenes 1 y 2, eliminar el resto
    stations_to_fix = {
        'FGC_GR': ['FGC_GR3', 'FGC_GR4'],
        'FGC_MA': ['FGC_MA3', 'FGC_MA7'],
        'FGC_SV': ['FGC_SV3', 'FGC_SV4'],
        'FGC_MO': ['FGC_MO3', 'FGC_MO4'],
    }

    # Agrupar andenes OSM por estación
    osm_by_station = {}
    for anden in andenes:
        gtfs_id = anden.get('gtfs_parent_id')
        if gtfs_id in stations_to_fix:
            if gtfs_id not in osm_by_station:
                osm_by_station[gtfs_id] = []
            osm_by_station[gtfs_id].append(anden)

    eliminados = 0
    actualizados = 0

    for station_id, to_delete in stations_to_fix.items():
        osm_platforms = osm_by_station.get(station_id, [])

        if len(osm_platforms) != 2:
            logger.warning(f"  {station_id}: Esperados 2 andenes OSM, hay {len(osm_platforms)}")
            continue

        # Ordenar OSM por coordenadas
        osm_sorted = sorted(osm_platforms, key=lambda x: (x['lat'], x['lon']))

        # Andenes a mantener (1 y 2)
        keep_ids = [f"{station_id}1", f"{station_id}2"]

        logger.info(f"  {station_id}: Eliminar {to_delete}, actualizar {keep_ids}")

        if dry_run:
            eliminados += len(to_delete)
            actualizados += 2
            continue

        cur = conn.cursor()

        # Eliminar andenes fantasma (primero referencias en todas las tablas FK)
        for del_id in to_delete:
            cur.execute("DELETE FROM gtfs_stop_route_sequence WHERE stop_id = %s", (del_id,))
            cur.execute("DELETE FROM gtfs_stop_times WHERE stop_id = %s", (del_id,))
            cur.execute("DELETE FROM gtfs_stops WHERE id = %s", (del_id,))
            logger.info(f"    Eliminado: {del_id}")

        # Actualizar coords de andenes restantes
        for i, keep_id in enumerate(keep_ids):
            if i < len(osm_sorted):
                cur.execute("""
                    UPDATE gtfs_stops SET lat = %s, lon = %s WHERE id = %s
                """, (osm_sorted[i]['lat'], osm_sorted[i]['lon'], keep_id))

        conn.commit()
        cur.close()

        eliminados += len(to_delete)
        actualizados += 2

    if dry_run:
        logger.info(f"  [DRY-RUN] Se eliminarían {eliminados} andenes, se actualizarían {actualizados}")
    else:
        logger.info(f"  Eliminados: {eliminados}, Actualizados: {actualizados}")

    return eliminados, actualizados


def show_summary(data: Dict, existing_stops: Dict):
    """Muestra resumen de datos a procesar."""
    logger.info("=== RESUMEN DATOS ===")
    logger.info(f"  Andenes OSM: {len(data['andenes'])}")
    logger.info(f"  Accesos verificados: {len(data.get('accesos_verificados', []))}")

    # Contar por tipo en BD
    bd_stations = sum(1 for s in existing_stops.values() if s['location_type'] == 1)
    bd_platforms = sum(1 for s in existing_stops.values() if s['location_type'] == 0)
    bd_accesses = sum(1 for s in existing_stops.values() if s['location_type'] == 2)

    logger.info(f"  BD - Estaciones: {bd_stations}")
    logger.info(f"  BD - Andenes: {bd_platforms}")
    logger.info(f"  BD - Accesos: {bd_accesses}")


def main():
    parser = argparse.ArgumentParser(description="Poblar tablas FGC con datos OSM")
    parser.add_argument('--dry-run', action='store_true', help="Simular sin hacer cambios")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("FGC - Población de tablas")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("*** MODO DRY-RUN - No se harán cambios ***")

    # Cargar datos
    logger.info(f"Cargando datos de: {DATA_FILE}")
    data = load_data()

    # Conectar BD
    logger.info(f"Conectando a BD...")
    conn = psycopg2.connect(DATABASE_URL)

    try:
        # Obtener stops existentes
        existing_stops = get_existing_stops(conn)

        # Mostrar resumen
        show_summary(data, existing_stops)

        # 1. Insertar accesos
        accesos = data.get('accesos_verificados', [])
        accesos_insertados = insert_accesos(conn, accesos, existing_stops, args.dry_run)

        # 2. Actualizar coordenadas de andenes (solo donde coincide el número)
        andenes = data.get('andenes', [])
        andenes_actualizados, ignorados_diff, ignorados_sin_bd = update_platform_coords(
            conn, andenes, existing_stops, args.dry_run
        )

        # 3. Corregir vías fantasma (BD > OSM)
        fantasma_eliminados, fantasma_actualizados = fix_phantom_platforms(
            conn, andenes, args.dry_run
        )

        # Resumen final
        logger.info("")
        logger.info("=" * 60)
        logger.info("RESUMEN FINAL")
        logger.info("=" * 60)
        logger.info(f"  Accesos insertados: {accesos_insertados}")
        logger.info(f"  Andenes actualizados: {andenes_actualizados}")
        logger.info(f"  Vías fantasma eliminadas: {fantasma_eliminados}")
        logger.info(f"  Vías fantasma actualizadas: {fantasma_actualizados}")
        logger.info(f"  Estaciones complejas (ignoradas): {ignorados_diff}")
        logger.info(f"  Estaciones sin BD (ignoradas): {ignorados_sin_bd}")

        if args.dry_run:
            logger.info("")
            logger.info("*** Ejecutar sin --dry-run para aplicar cambios ***")

    finally:
        conn.close()

    logger.info("")
    logger.info("Completado.")


if __name__ == "__main__":
    main()
