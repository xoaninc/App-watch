#!/usr/bin/env python3
"""
Sevilla - Correspondencias Multimodales

Crea correspondencias entre:
- Metro Sevilla L1 ↔ Tranvía Sevilla T1
- Metro Sevilla L1 ↔ RENFE Cercanías
- Tranvía Sevilla T1 ↔ RENFE Cercanías

Uso:
    python sevilla_multimodal_correspondences.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CORRESPONDENCIAS SEVILLA
# =============================================================================

# Formato: (from_id, to_id, distance_m, walk_time_s, description)
CORRESPONDENCES = [
    # ----- METRO SEVILLA ↔ TRANVÍA SEVILLA -----
    # San Bernardo (51m) - Hub principal trimodal
    ("METRO_SEV_L1_E10", "TRAM_SEV_SAN_BERNARDO", 51, 42, "San Bernardo - Metro ↔ Tram"),

    # Prado de San Sebastián (33m) - Estación bus también
    ("METRO_SEV_L1_E9", "TRAM_SEV_PRADO_SAN_SEBASTIÁN", 33, 27, "Prado - Metro ↔ Tram"),

    # Puerta Jerez (137m)
    ("METRO_SEV_L1_E8", "TRAM_SEV_PUERTA_JEREZ", 137, 114, "Puerta Jerez - Metro ↔ Tram"),

    # Nervión / Eduardo Dato (117m)
    ("METRO_SEV_L1_E11", "TRAM_SEV_EDUARDO_DATO", 117, 97, "Nervión - Metro ↔ Tram"),

    # ----- METRO SEVILLA ↔ RENFE -----
    # San Bernardo (87m) - Cercanías C1/C2/C3/C4/C5
    ("METRO_SEV_L1_E10", "RENFE_51100", 87, 72, "San Bernardo - Metro ↔ RENFE"),

    # ----- TRANVÍA SEVILLA ↔ RENFE -----
    # San Bernardo (96m)
    ("TRAM_SEV_SAN_BERNARDO", "RENFE_51100", 96, 80, "San Bernardo - Tram ↔ RENFE"),
]


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
    print("SEVILLA - Correspondencias Multimodales")
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
