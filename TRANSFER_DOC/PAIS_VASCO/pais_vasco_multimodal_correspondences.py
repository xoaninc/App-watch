#!/usr/bin/env python3
"""
País Vasco - Correspondencias Multimodales

Crea correspondencias entre:
- Metro Bilbao ↔ Euskotren
- Metro Bilbao ↔ RENFE
- Euskotren ↔ RENFE
- Funicular Artxanda ↔ Euskotren

Uso:
    python pais_vasco_multimodal_correspondences.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CORRESPONDENCIAS PAÍS VASCO (BILBAO)
# =============================================================================

# Formato: (from_id, to_id, distance_m, walk_time_s, description)
CORRESPONDENCES = [
    # ----- METRO BILBAO ↔ EUSKOTREN -----
    # Lutxana (40m) - OSM confirma stop_area conjunto
    ("METRO_BILBAO_14", "EUSKOTREN_ES:Euskotren:StopPlace:2576:", 40, 60, "Lutxana - Metro ↔ Euskotren"),

    # Abando (86m) - Intercambiador principal Bilbao
    ("METRO_BILBAO_7", "EUSKOTREN_ES:Euskotren:StopPlace:1471:", 86, 90, "Abando - Metro ↔ Euskotren"),

    # Casco Viejo / Zazpikaleak (125m)
    ("METRO_BILBAO_6", "EUSKOTREN_ES:Euskotren:StopPlace:2577:", 125, 120, "Casco Viejo - Metro ↔ Euskotren"),

    # San Mamés (144m) - Usar San Mamés, no Sabino Arana
    ("METRO_BILBAO_10", "EUSKOTREN_ES:Euskotren:StopPlace:1470:", 144, 150, "San Mamés - Metro ↔ Euskotren"),

    # ----- METRO BILBAO ↔ RENFE -----
    # Abando (167m)
    ("METRO_BILBAO_7", "RENFE_05451", 167, 180, "Abando - Metro ↔ RENFE Concordia"),

    # ----- EUSKOTREN ↔ RENFE -----
    # Abando (98m)
    ("EUSKOTREN_ES:Euskotren:StopPlace:1471:", "RENFE_05451", 98, 120, "Abando - Euskotren ↔ RENFE Concordia"),

    # Basurto Hospital (209m) - Estaciones separadas pero correspondencia válida
    ("EUSKOTREN_ES:Euskotren:StopPlace:1472:", "RENFE_05455", 209, 180, "Hospital - Euskotren ↔ RENFE Basurto"),

    # ----- EUSKOTREN ↔ RENFE (GIPUZKOA C1) -----
    # Donostia/Amara (675m) - Hub principal San Sebastián, conecta LD/Cercanías con Topo
    ("EUSKOTREN_ES:Euskotren:StopPlace:2581:", "RENFE_11511", 675, 600, "Donostia - Amara ↔ RENFE San Sebastián"),

    # Irun (900m) - Hub frontera Francia, conecta interior Gipuzkoa
    ("EUSKOTREN_ES:Euskotren:StopPlace:2605:", "RENFE_11600", 900, 720, "Irun - Euskotren Colón ↔ RENFE Irun"),

    # ----- FUNICULAR ↔ EUSKOTREN -----
    # Matiko (90m)
    ("FUNICULAR_ARTXANDA_12", "EUSKOTREN_ES:Euskotren:StopPlace:2597:", 90, 90, "Matiko - Funicular ↔ Euskotren"),
]


def get_engine():
    """Create database engine."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Production fallback
        user = os.getenv("POSTGRES_USER", "renfeserver")
        password = os.getenv("POSTGRES_PASSWORD", "")
        host = os.getenv("POSTGRES_HOST", "localhost")
        db = os.getenv("POSTGRES_DB", "renfeserver_prod")
        database_url = f"postgresql://{user}:{password}@{host}/{db}"
    return create_engine(database_url)


def create_correspondences():
    """Insert correspondences into database."""
    engine = get_engine()

    created = 0
    skipped = 0
    errors = 0

    with engine.connect() as conn:
        for from_id, to_id, distance, walk_time, description in CORRESPONDENCES:
            # Insert bidirectional (A→B and B→A)
            for a, b in [(from_id, to_id), (to_id, from_id)]:
                try:
                    # Check if exists
                    result = conn.execute(text("""
                        SELECT 1 FROM stop_correspondence
                        WHERE from_stop_id = :from_id AND to_stop_id = :to_id
                    """), {"from_id": a, "to_id": b})

                    if result.fetchone():
                        print(f"  ⏭️  Ya existe: {a} → {b}")
                        skipped += 1
                        continue

                    # Insert
                    conn.execute(text("""
                        INSERT INTO stop_correspondence
                        (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
                        VALUES (:from_id, :to_id, :distance, :walk_time, 'manual_multimodal')
                    """), {
                        "from_id": a,
                        "to_id": b,
                        "distance": distance,
                        "walk_time": walk_time
                    })
                    print(f"  ✅ Creada: {a} → {b} ({distance}m)")
                    created += 1

                except Exception as e:
                    print(f"  ❌ Error: {a} → {b}: {e}")
                    errors += 1

        conn.commit()

    return created, skipped, errors


def main():
    print("=" * 60)
    print("PAÍS VASCO - Correspondencias Multimodales")
    print("=" * 60)
    print(f"\nCorrespondencias a crear: {len(CORRESPONDENCES)} pares")
    print(f"Total registros: {len(CORRESPONDENCES) * 2} (bidireccional)\n")

    created, skipped, errors = create_correspondences()

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"✅ Creadas: {created}")
    print(f"⏭️  Existentes: {skipped}")
    print(f"❌ Errores: {errors}")

    if errors == 0:
        print("\n✅ Proceso completado correctamente")
    else:
        print(f"\n⚠️  Proceso completado con {errors} errores")


if __name__ == "__main__":
    main()
