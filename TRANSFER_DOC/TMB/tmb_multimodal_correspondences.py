#!/usr/bin/env python3
"""
TMB Metro Barcelona - Correspondencias Multimodales.

Este script crea correspondencias entre TMB Metro y otros operadores:
- TMB ↔ FGC (Ferrocarrils de la Generalitat)
- TMB ↔ RENFE Rodalies

Las correspondencias se basan en intercambiadores conocidos y distancias calculadas.

Uso:
    source .venv/bin/activate
    python TRANSFER_DOC/TMB/tmb_multimodal_correspondences.py --dry-run
    python TRANSFER_DOC/TMB/tmb_multimodal_correspondences.py
"""

import os
import argparse
import logging
from math import radians, sin, cos, sqrt, atan2
from typing import List, Tuple, Dict

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

# Correspondencias multimodales conocidas
# Formato: (tmb_station_name_pattern, other_stop_id, walk_time_s, distance_m, notes)

TMB_FGC_CORRESPONDENCES = [
    # Intercambiadores directos (mismo edificio o conexión interior)
    # NOTA: Passeig de Gràcia ↔ FGC Provença ELIMINADA - >800m no es transfer real
    ("Espanya", "FGC_PE", 120, 80, "Mismo intercambiador"),  # L1/L3 ↔ Espanya FGC
    ("Catalunya", "FGC_PC", 180, 100, "Mismo intercambiador"),  # L1/L3 ↔ Pl. Catalunya FGC
    ("Diagonal", "FGC_PR", 300, 200, "~200m caminando"),  # L3/L5 ↔ Provença FGC
    # Correspondencias cercanas
    ("Fontana", "FGC_GR", 300, 325, "Fontana L3 ↔ Gràcia FGC ~325m"),  # L3 ↔ Gràcia FGC
    # Segunda corona - Baix Llobregat
    ("Av. Carrilet", "FGC_LH", 120, 50, "L1 ↔ FGC Llobregat-Anoia - conexión subterránea"),
    ("Europa | Fira", "FGC_EU", 120, 50, "L9S ↔ FGC - mismo intercambiador Fira"),
]

TMB_RENFE_CORRESPONDENCES = [
    # Intercambiadores principales
    ("Sants Estació", "RENFE_71801", 240, 150, "Barcelona-Sants - conexión interior"),
    ("Passeig de Gràcia", "RENFE_71802", 180, 100, "Barcelona-Passeig de Gràcia"),
    ("Catalunya", "RENFE_78805", 240, 150, "Barcelona-Plaça de Catalunya"),
    # Correspondencias cercanas
    ("Clot", "RENFE_79009", 180, 100, "Barcelona-El Clot"),
    ("Arc de Triomf", "RENFE_78804", 300, 200, "Barcelona-Arc de Triomf"),
    ("La Sagrera", "RENFE_78806", 240, 150, "Barcelona-La Sagrera-Meridiana"),
    # Segunda corona
    ("Fabra i Puig", "RENFE_78802", 180, 100, "L1 ↔ Sant Andreu Arenal R3/R4/R7"),
    ("Cornellà Centre", "RENFE_72303", 240, 200, "L5 ↔ Cornellà R1/R4"),
    ("Torre Baró | Vallbona", "RENFE_78801", 180, 100, "L11 ↔ Torre Baró Rodalies"),
    # Nuevas - detectadas por nombre
    ("Sant Andreu", "RENFE_79004", 180, 175, "L1 ↔ Barcelona-Sant Andreu R1/R3/R4"),
    ("Aeroport T2", "RENFE_72400", 60, 46, "L9S ↔ Aeroport RENFE - mismo edificio"),
]

TMB_TRAM_CORRESPONDENCES = [
    # Trambesòs (T4/T5/T6)
    ("Glòries", "TRAM_BARCELONA_BESOS_2003", 120, 50, "L1 ↔ Trambesòs T4/T5/T6"),
    ("Ciutadella | Vila Olímpica", "TRAM_BARCELONA_BESOS_2020", 180, 100, "L4 ↔ Trambesòs"),
    ("Besòs", "TRAM_BARCELONA_BESOS_2026", 120, 56, "L4 ↔ Trambesòs T5/T6"),
    ("El Maresme | Fòrum", "TRAM_BARCELONA_BESOS_2008", 180, 170, "L4 ↔ Trambesòs T4"),
    ("Marina", "TRAM_BARCELONA_BESOS_2022", 180, 119, "L1 ↔ Trambesòs T4"),
    ("Selva de Mar", "TRAM_BARCELONA_BESOS_2007", 180, 165, "L4 ↔ Trambesòs T4"),
    # Trambesòs Badalona (T5)
    ("Gorg", "TRAM_BARCELONA_BESOS_2019", 60, 55, "L2/L10N ↔ Trambesòs T5 - intercambiador"),
    ("Sant Roc", "TRAM_BARCELONA_BESOS_2017", 120, 105, "L2 ↔ Trambesòs T5"),
    # Trambaix (T1/T2/T3)
    ("Ernest Lluch", "TRAM_BARCELONA_1011", 120, 50, "L5/L9S ↔ Trambaix T1/T2/T3"),
    ("Maria Cristina", "TRAM_BARCELONA_1004", 180, 100, "L3 ↔ Trambaix"),
    ("Palau Reial", "TRAM_BARCELONA_1008", 180, 100, "L3 ↔ Trambaix"),
    ("Cornellà Centre", "TRAM_BARCELONA_1019", 120, 44, "L5 ↔ Trambaix T1/T2/T3"),
    ("Zona Universitària", "TRAM_BARCELONA_1009", 240, 239, "L3/L9S ↔ Trambaix T1/T2/T3"),
]


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distancia en metros entre dos coordenadas."""
    R = 6371000  # Radio de la Tierra en metros

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def get_tmb_stations(conn) -> Dict[str, Dict]:
    """Obtiene estaciones TMB Metro (location_type=1)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, lat, lon
        FROM gtfs_stops
        WHERE id LIKE 'TMB_METRO_P.%' AND location_type = 1
        ORDER BY name
    """)
    stations = {}
    for row in cur.fetchall():
        # Usar nombre como clave para búsqueda flexible
        name = row[1]
        if name not in stations:
            stations[name] = []
        stations[name].append({
            'id': row[0],
            'name': row[1],
            'lat': float(row[2]),
            'lon': float(row[3])
        })
    cur.close()
    return stations


def get_tmb_platforms(conn) -> Dict[str, List[Dict]]:
    """Obtiene andenes TMB Metro (location_type=0) agrupados por estación."""
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.name, s.lat, s.lon, p.name as parent_name
        FROM gtfs_stops s
        JOIN gtfs_stops p ON s.parent_station_id = p.id
        WHERE s.id LIKE 'TMB_METRO_1.%' AND s.location_type = 0
        ORDER BY p.name, s.id
    """)
    platforms = {}
    for row in cur.fetchall():
        parent_name = row[4]
        if parent_name not in platforms:
            platforms[parent_name] = []
        platforms[parent_name].append({
            'id': row[0],
            'name': row[1],
            'lat': float(row[2]),
            'lon': float(row[3])
        })
    cur.close()
    return platforms


def get_other_operator_stops(conn, stop_ids: List[str]) -> Dict[str, Dict]:
    """Obtiene paradas de otros operadores por ID."""
    if not stop_ids:
        return {}

    cur = conn.cursor()
    placeholders = ','.join(['%s'] * len(stop_ids))
    cur.execute(f"""
        SELECT id, name, lat, lon, location_type
        FROM gtfs_stops
        WHERE id IN ({placeholders})
    """, stop_ids)

    stops = {}
    for row in cur.fetchall():
        stops[row[0]] = {
            'id': row[0],
            'name': row[1],
            'lat': float(row[2]) if row[2] else None,
            'lon': float(row[3]) if row[3] else None,
            'location_type': row[4]
        }
    cur.close()
    return stops


def get_other_operator_platforms(conn, station_id: str) -> List[Dict]:
    """Obtiene andenes de una estación de otro operador."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, lat, lon
        FROM gtfs_stops
        WHERE parent_station_id = %s AND location_type = 0
    """, (station_id,))

    platforms = []
    for row in cur.fetchall():
        platforms.append({
            'id': row[0],
            'name': row[1],
            'lat': float(row[2]) if row[2] else None,
            'lon': float(row[3]) if row[3] else None
        })
    cur.close()
    return platforms


def find_tmb_station(tmb_stations: Dict, pattern: str) -> List[Dict]:
    """Busca estaciones TMB que coincidan con el patrón."""
    matches = []
    for name, stations in tmb_stations.items():
        if pattern.lower() in name.lower():
            matches.extend(stations)
    return matches


def create_correspondences(conn, dry_run: bool) -> Tuple[int, int, int]:
    """
    Crea correspondencias multimodales entre TMB y otros operadores.

    Returns:
        (creadas, existentes, errores)
    """
    logger.info("=== CREANDO CORRESPONDENCIAS MULTIMODALES ===")

    # Obtener datos
    tmb_stations = get_tmb_stations(conn)
    tmb_platforms = get_tmb_platforms(conn)

    # IDs de otros operadores
    fgc_ids = [c[1] for c in TMB_FGC_CORRESPONDENCES]
    renfe_ids = [c[1] for c in TMB_RENFE_CORRESPONDENCES]
    tram_ids = [c[1] for c in TMB_TRAM_CORRESPONDENCES]
    other_stops = get_other_operator_stops(conn, fgc_ids + renfe_ids + tram_ids)

    logger.info(f"  Estaciones TMB: {len(tmb_stations)}")
    logger.info(f"  Paradas FGC/RENFE/TRAM encontradas: {len(other_stops)}")

    correspondences = []
    errors = []

    # Procesar correspondencias FGC
    logger.info("")
    logger.info("=== TMB ↔ FGC ===")
    for tmb_pattern, fgc_id, walk_time, distance, notes in TMB_FGC_CORRESPONDENCES:
        tmb_matches = find_tmb_station(tmb_stations, tmb_pattern)
        fgc_stop = other_stops.get(fgc_id)

        if not tmb_matches:
            errors.append(f"TMB station '{tmb_pattern}' not found")
            logger.warning(f"  ⚠ TMB '{tmb_pattern}' no encontrada")
            continue

        if not fgc_stop:
            errors.append(f"FGC stop '{fgc_id}' not found")
            logger.warning(f"  ⚠ FGC '{fgc_id}' no encontrada")
            continue

        # Obtener andenes FGC (location_type=0 si fgc_stop es estación)
        if fgc_stop['location_type'] == 1:
            fgc_platforms = get_other_operator_platforms(conn, fgc_id)
        else:
            fgc_platforms = [fgc_stop]

        if not fgc_platforms:
            fgc_platforms = [fgc_stop]  # Usar estación si no hay andenes

        for tmb_station in tmb_matches:
            tmb_plats = tmb_platforms.get(tmb_station['name'], [])
            if not tmb_plats:
                # Sin andenes, usar estación
                tmb_plats = [tmb_station]

            for tmb_plat in tmb_plats:
                for fgc_plat in fgc_platforms:
                    # Calcular distancia real si hay coords
                    if tmb_plat.get('lat') and fgc_plat.get('lat'):
                        real_dist = int(haversine(
                            tmb_plat['lat'], tmb_plat['lon'],
                            fgc_plat['lat'], fgc_plat['lon']
                        ))
                        # Usar distancia real si es mayor que la estimada
                        final_dist = max(distance, real_dist)
                        # Ajustar tiempo si la distancia es mayor
                        final_time = walk_time if real_dist <= distance else int(real_dist / 1.2)  # ~1.2 m/s
                    else:
                        final_dist = distance
                        final_time = walk_time

                    correspondences.append({
                        'from_id': tmb_plat['id'],
                        'to_id': fgc_plat['id'],
                        'distance': final_dist,
                        'walk_time': final_time,
                        'source': 'manual_multimodal',
                        'notes': notes
                    })

        logger.info(f"  ✓ {tmb_pattern} ↔ {fgc_id}: {notes}")

    # Procesar correspondencias RENFE
    logger.info("")
    logger.info("=== TMB ↔ RENFE ===")
    for tmb_pattern, renfe_id, walk_time, distance, notes in TMB_RENFE_CORRESPONDENCES:
        tmb_matches = find_tmb_station(tmb_stations, tmb_pattern)
        renfe_stop = other_stops.get(renfe_id)

        if not tmb_matches:
            errors.append(f"TMB station '{tmb_pattern}' not found")
            logger.warning(f"  ⚠ TMB '{tmb_pattern}' no encontrada")
            continue

        if not renfe_stop:
            errors.append(f"RENFE stop '{renfe_id}' not found")
            logger.warning(f"  ⚠ RENFE '{renfe_id}' no encontrada")
            continue

        # RENFE stops son location_type=0, usar directamente
        for tmb_station in tmb_matches:
            tmb_plats = tmb_platforms.get(tmb_station['name'], [])
            if not tmb_plats:
                tmb_plats = [tmb_station]

            for tmb_plat in tmb_plats:
                if tmb_plat.get('lat') and renfe_stop.get('lat'):
                    real_dist = int(haversine(
                        tmb_plat['lat'], tmb_plat['lon'],
                        renfe_stop['lat'], renfe_stop['lon']
                    ))
                    final_dist = max(distance, real_dist)
                    final_time = walk_time if real_dist <= distance else int(real_dist / 1.2)
                else:
                    final_dist = distance
                    final_time = walk_time

                correspondences.append({
                    'from_id': tmb_plat['id'],
                    'to_id': renfe_stop['id'],
                    'distance': final_dist,
                    'walk_time': final_time,
                    'source': 'manual_multimodal',
                    'notes': notes
                })

        logger.info(f"  ✓ {tmb_pattern} ↔ {renfe_id}: {notes}")

    # Procesar correspondencias TRAM
    logger.info("")
    logger.info("=== TMB ↔ TRAM ===")
    for tmb_pattern, tram_id, walk_time, distance, notes in TMB_TRAM_CORRESPONDENCES:
        tmb_matches = find_tmb_station(tmb_stations, tmb_pattern)
        tram_stop = other_stops.get(tram_id)

        if not tmb_matches:
            errors.append(f"TMB station '{tmb_pattern}' not found")
            logger.warning(f"  ⚠ TMB '{tmb_pattern}' no encontrada")
            continue

        if not tram_stop:
            errors.append(f"TRAM stop '{tram_id}' not found")
            logger.warning(f"  ⚠ TRAM '{tram_id}' no encontrada")
            continue

        # TRAM stops son location_type=0, usar directamente
        for tmb_station in tmb_matches:
            tmb_plats = tmb_platforms.get(tmb_station['name'], [])
            if not tmb_plats:
                tmb_plats = [tmb_station]

            for tmb_plat in tmb_plats:
                if tmb_plat.get('lat') and tram_stop.get('lat'):
                    real_dist = int(haversine(
                        tmb_plat['lat'], tmb_plat['lon'],
                        tram_stop['lat'], tram_stop['lon']
                    ))
                    final_dist = max(distance, real_dist)
                    final_time = walk_time if real_dist <= distance else int(real_dist / 1.2)
                else:
                    final_dist = distance
                    final_time = walk_time

                correspondences.append({
                    'from_id': tmb_plat['id'],
                    'to_id': tram_stop['id'],
                    'distance': final_dist,
                    'walk_time': final_time,
                    'source': 'manual_multimodal',
                    'notes': notes
                })

        logger.info(f"  ✓ {tmb_pattern} ↔ {tram_id}: {notes}")

    # Eliminar duplicados (misma pareja de stops)
    seen = set()
    unique_correspondences = []
    for c in correspondences:
        key = (c['from_id'], c['to_id'])
        reverse_key = (c['to_id'], c['from_id'])
        if key not in seen and reverse_key not in seen:
            seen.add(key)
            unique_correspondences.append(c)

    logger.info("")
    logger.info(f"  Total correspondencias únicas: {len(unique_correspondences)}")

    if errors:
        logger.info(f"  Errores: {len(errors)}")
        for e in errors[:5]:
            logger.info(f"    - {e}")

    if dry_run:
        logger.info("")
        logger.info("[DRY-RUN] No se insertaron correspondencias")
        return len(unique_correspondences), 0, len(errors)

    # Insertar correspondencias
    cur = conn.cursor()
    created = 0
    existing = 0

    for c in unique_correspondences:
        try:
            # Insertar en ambas direcciones
            cur.execute("""
                INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (from_stop_id, to_stop_id) DO NOTHING
            """, (c['from_id'], c['to_id'], c['distance'], c['walk_time'], c['source']))

            if cur.rowcount > 0:
                created += 1
            else:
                existing += 1

            # Dirección inversa
            cur.execute("""
                INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (from_stop_id, to_stop_id) DO NOTHING
            """, (c['to_id'], c['from_id'], c['distance'], c['walk_time'], c['source']))

            if cur.rowcount > 0:
                created += 1
            else:
                existing += 1

        except Exception as e:
            logger.error(f"Error insertando {c['from_id']} -> {c['to_id']}: {e}")

    conn.commit()
    cur.close()

    logger.info("")
    logger.info(f"  Creadas: {created}")
    logger.info(f"  Ya existían: {existing}")

    return created, existing, len(errors)


def main():
    parser = argparse.ArgumentParser(description="Crear correspondencias multimodales TMB")
    parser.add_argument('--dry-run', action='store_true', help="Simular sin insertar")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("TMB Metro - Correspondencias Multimodales")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("*** MODO DRY-RUN ***")

    conn = psycopg2.connect(DATABASE_URL)

    try:
        created, existing, errors = create_correspondences(conn, args.dry_run)

        logger.info("")
        logger.info("=" * 60)
        logger.info("RESUMEN FINAL")
        logger.info("=" * 60)
        logger.info(f"  Correspondencias creadas: {created}")
        logger.info(f"  Ya existían: {existing}")
        logger.info(f"  Errores: {errors}")

        if args.dry_run:
            logger.info("")
            logger.info("*** Ejecutar sin --dry-run para aplicar cambios ***")

    finally:
        conn.close()

    logger.info("")
    logger.info("Completado.")


if __name__ == "__main__":
    main()
