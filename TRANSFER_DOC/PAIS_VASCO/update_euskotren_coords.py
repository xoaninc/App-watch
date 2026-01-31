#!/usr/bin/env python3
"""
Actualiza coordenadas de andenes de Euskotren desde OSM.

Los andenes del GTFS tienen coordenadas "falsas" (igual a la estación padre).
Este script:
1. Usa coordenadas reales de estaciones OSM
2. Aplica un offset de ~10m para separar Q1 y Q2
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# COORDENADAS REALES DE OSM (Estaciones Euskotren)
# Extraído de Overpass API 2026-01-31
# =============================================================================

# Estaciones Euskotren desde OSM
# El offset se aplica para separar Q1/Q2 (~10m = 0.0001 grados)
OFFSET = 0.00015  # ~15m de separación entre andenes

EUSKOTREN_STATIONS_OSM = {
    # Línea Bilbao-Donostia
    "1471": ("Abando", 43.260600, -2.926500),  # Estimado (no en OSM directo)
    "1472": ("Basurto", 43.263100, -2.954100),  # Estimado
    "1487": ("Basauri", 43.236227, -2.893483),  # OSM: similar nombre
    "1488": ("Ariz", 43.239802, -2.878973),
    "1489": ("Galdakao", 43.228780, -2.854188),  # OSM: Zuhatzu
    "1490": ("Usansolo", 43.217742, -2.821761),
    "1491": ("Lemoa", 43.207144, -2.775409),
    "1492": ("Bedia", 43.206119, -2.797612),
    "1493": ("Lemoa-Industria", 43.207144, -2.775409),  # Misma que Lemoa
    "1494": ("Apatamonasterio", 43.216760, -2.736456),  # OSM: Amorebieta
    "1495": ("Iurreta", 43.183600, -2.638100),  # Estimado
    "1496": ("Durango", 43.169395, -2.634551),
    "1497": ("Garay", 43.165275, -2.612563),  # OSM: Traña
    "1498": ("Abadiano", 43.168456, -2.574433),  # OSM: Berriz
    "1499": ("Atxondo", 43.171626, -2.548024),  # OSM: Zaldibar
    "1500": ("Apata", 43.171626, -2.548024),  # Mismo que Atxondo
    "1501": ("Eibar", 43.187107, -2.465668),
    "1502": ("Azitain", 43.190395, -2.455022),
    "1503": ("Elgoibar", 43.213601, -2.415827),
    "1504": ("Mendaro", 43.252196, -2.387899),
    "1505": ("Deba", 43.295900, -2.348900),  # Estimado
    "1506": ("Zumaia", 43.291546, -2.251795),
    "1507": ("Zarautz", 43.284214, -2.171059),
    "1508": ("Orio", 43.274215, -2.126464),  # OSM: Aia-Orio
    "1509": ("Usurbil", 43.268705, -2.052941),
    "1510": ("Lasarte-Oria", 43.270947, -2.020255),
    "1511": ("Hernani", 43.267700, -1.975400),  # Estimado
    "1512": ("Loiola", 43.310488, -1.967962),
    "1513": ("Donostia", 43.319800, -1.981800),  # Estimado

    # Línea Amara-Hendaia
    "2570": ("Amara", 43.312676, -1.981529),  # OSM verificado
    "2571": ("Herrera", 43.319849, -1.938126),
    "2572": ("Añorga", 43.294900, -1.994300),  # Estimado
    "2573": ("Intxaurrondo", 43.314232, -1.954873),
    "2574": ("Pasaia", 43.318219, -1.918003),
    "2575": ("Lezo-Renteria", 43.311009, -1.898693),  # OSM: Errenteria
    "2600": ("Alegi", 43.270947, -2.020255),  # OSM: Lasarte-Oria
    "2601": ("Oiartzun", 43.308624, -1.879163),
    "2602": ("Galtzaraborda", 43.312391, -1.906440),
    "2603": ("Ventas", 43.330360, -1.817057),  # OSM: Bentak
    "2604": ("Hendaia", 43.352100, -1.788800),  # Estimado
    "2605": ("Irun", 43.340947, -1.796059),  # OSM: Irun Colon
}


def get_engine():
    """Create database engine."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        user = os.getenv("POSTGRES_USER", "renfeserver")
        password = os.getenv("POSTGRES_PASSWORD", "")
        host = os.getenv("POSTGRES_HOST", "localhost")
        db = os.getenv("POSTGRES_DB", "renfeserver_prod")
        database_url = f"postgresql://{user}:{password}@{host}/{db}"
    return create_engine(database_url)


def update_euskotren_coords():
    """Update Euskotren platform coordinates."""
    engine = get_engine()
    updated = 0
    errors = 0
    not_found = 0

    with engine.connect() as conn:
        for code, (name, base_lat, base_lon) in EUSKOTREN_STATIONS_OSM.items():
            # Buscar andenes de esta estación (Q1, Q2, Q3)
            for q_num in [1, 2, 3]:
                stop_id = f"EUSKOTREN_ES:Euskotren:Quay:{code}_Plataforma_Q{q_num}:"

                try:
                    # Verificar que existe
                    result = conn.execute(text("""
                        SELECT lat, lon FROM gtfs_stops WHERE id = :id
                    """), {"id": stop_id})
                    row = result.fetchone()

                    if not row:
                        continue  # Este andén no existe

                    old_lat, old_lon = row

                    # Calcular offset según número de andén
                    # Q1: +offset, Q2: -offset, Q3: 0
                    if q_num == 1:
                        new_lat = base_lat + OFFSET
                        new_lon = base_lon
                    elif q_num == 2:
                        new_lat = base_lat - OFFSET
                        new_lon = base_lon
                    else:
                        new_lat = base_lat
                        new_lon = base_lon + OFFSET

                    # Actualizar
                    conn.execute(text("""
                        UPDATE gtfs_stops
                        SET lat = :lat, lon = :lon
                        WHERE id = :id
                    """), {"lat": new_lat, "lon": new_lon, "id": stop_id})

                    print(f"  ✅ {name} Q{q_num}: ({old_lat:.4f}, {old_lon:.4f}) → ({new_lat:.4f}, {new_lon:.4f})")
                    updated += 1

                except Exception as e:
                    print(f"  ❌ Error {stop_id}: {e}")
                    errors += 1

        conn.commit()

    return updated, errors


def main():
    print("=" * 60)
    print("ACTUALIZACIÓN COORDENADAS ANDENES EUSKOTREN - OSM")
    print("=" * 60)
    print(f"\nEstaciones en mapa: {len(EUSKOTREN_STATIONS_OSM)}")
    print(f"Offset entre andenes: {OFFSET} grados (~{OFFSET * 111000:.0f}m)")
    print()

    updated, errors = update_euskotren_coords()

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"✅ Actualizados: {updated}")
    print(f"❌ Errores: {errors}")


if __name__ == "__main__":
    main()
