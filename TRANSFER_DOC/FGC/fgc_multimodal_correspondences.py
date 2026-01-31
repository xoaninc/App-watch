#!/usr/bin/env python3
"""
FGC - Correspondencias Multimodales.

Este script crea correspondencias entre FGC y otros operadores:
- FGC ↔ RENFE Rodalies
- FGC ↔ TMB Metro (ya creadas desde TMB, verifica bidireccionalidad)

Basado en datos OSM verificados manualmente.

Uso:
    source .venv/bin/activate
    python TRANSFER_DOC/FGC/fgc_multimodal_correspondences.py --dry-run
    python TRANSFER_DOC/FGC/fgc_multimodal_correspondences.py
"""

import os
import argparse
import logging
from math import radians, sin, cos, sqrt, atan2
from typing import List, Tuple, Dict

import psycopg2

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

# Correspondencias FGC ↔ RENFE verificadas con OSM
# Formato: (fgc_station_id, renfe_stop_id, walk_time_s, distance_m, notes)
FGC_RENFE_CORRESPONDENCES = [
    # Barcelona centro
    ("FGC_PC", "RENFE_78805", 300, 268, "Plaça Catalunya - mismo intercambiador"),

    # Vallès
    ("FGC_NO", "RENFE_78709", 120, 90, "Sabadell Nord - mismo edificio"),
    ("FGC_EN", "RENFE_78700", 120, 103, "Terrassa Estació Nord - mismo edificio"),

    # Llobregat-Anoia
    ("FGC_MC", "RENFE_72209", 60, 3, "Martorell Central - misma estación"),
    ("FGC_SV", "RENFE_78604", 300, 272, "Sant Vicenç Castellet - cercano"),
    ("FGC_GO", "RENFE_71708", 180, 180, "Gornal ↔ Bellvitge - mismo intercambiador R2"),
]

# Nota: FGC ↔ TMB Metro ya está creado desde tmb_multimodal_correspondences.py


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distancia en metros entre dos coordenadas."""
    R = 6371000
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def get_fgc_platforms(conn, station_id: str) -> List[Dict]:
    """Obtiene andenes de una estación FGC."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, lat, lon FROM gtfs_stops
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

    # Si no hay andenes, usar la estación misma
    if not platforms:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, lat, lon FROM gtfs_stops WHERE id = %s
        """, (station_id,))
        row = cur.fetchone()
        if row:
            platforms.append({
                'id': row[0],
                'name': row[1],
                'lat': float(row[2]) if row[2] else None,
                'lon': float(row[3]) if row[3] else None
            })
        cur.close()

    return platforms


def get_stop(conn, stop_id: str) -> Dict:
    """Obtiene una parada por ID."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, lat, lon, location_type FROM gtfs_stops WHERE id = %s
    """, (stop_id,))
    row = cur.fetchone()
    cur.close()

    if row:
        return {
            'id': row[0],
            'name': row[1],
            'lat': float(row[2]) if row[2] else None,
            'lon': float(row[3]) if row[3] else None,
            'location_type': row[4]
        }
    return None


def create_correspondences(conn, dry_run: bool) -> Tuple[int, int, int]:
    """
    Crea correspondencias multimodales FGC.

    Returns:
        (creadas, existentes, errores)
    """
    logger.info("=== CREANDO CORRESPONDENCIAS FGC MULTIMODALES ===")

    correspondences = []
    errors = []

    # Procesar FGC ↔ RENFE
    logger.info("")
    logger.info("=== FGC ↔ RENFE ===")

    for fgc_id, renfe_id, walk_time, distance, notes in FGC_RENFE_CORRESPONDENCES:
        fgc_platforms = get_fgc_platforms(conn, fgc_id)
        renfe_stop = get_stop(conn, renfe_id)

        if not fgc_platforms:
            errors.append(f"FGC station '{fgc_id}' not found")
            logger.warning(f"  ⚠ FGC '{fgc_id}' no encontrada")
            continue

        if not renfe_stop:
            errors.append(f"RENFE stop '{renfe_id}' not found")
            logger.warning(f"  ⚠ RENFE '{renfe_id}' no encontrada")
            continue

        for fgc_plat in fgc_platforms:
            if fgc_plat.get('lat') and renfe_stop.get('lat'):
                real_dist = int(haversine(
                    fgc_plat['lat'], fgc_plat['lon'],
                    renfe_stop['lat'], renfe_stop['lon']
                ))
                final_dist = max(distance, real_dist)
                final_time = walk_time if real_dist <= distance else int(real_dist / 1.2)
            else:
                final_dist = distance
                final_time = walk_time

            correspondences.append({
                'from_id': fgc_plat['id'],
                'to_id': renfe_stop['id'],
                'distance': final_dist,
                'walk_time': final_time,
                'source': 'manual_multimodal',
                'notes': notes
            })

        logger.info(f"  ✓ {fgc_id} ↔ {renfe_id}: {notes}")

    # Eliminar duplicados
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
    parser = argparse.ArgumentParser(description="Crear correspondencias multimodales FGC")
    parser.add_argument('--dry-run', action='store_true', help="Simular sin insertar")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("FGC - Correspondencias Multimodales")
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
