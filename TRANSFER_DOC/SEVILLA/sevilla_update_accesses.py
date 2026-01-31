#!/usr/bin/env python3
"""
Actualiza accesos de Metro Sevilla desde OSM.

Los accesos permiten al routing saber por qué entrada acceder a cada estación.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# ACCESOS METRO SEVILLA (desde OSM 2026-01-31)
# =============================================================================

# Formato: (stop_id, access_name, lat, lon, wheelchair)
METRO_ACCESSES = [
    # Prado San Sebastián - 1 ascensor
    ("METRO_SEV_L1_E9", "Ascensor Prado", 37.380677, -5.987358, True),

    # San Bernardo - 2 accesos (entrada + ascensor)
    ("METRO_SEV_L1_E10", "San Bernardo", 37.378198, -5.979034, None),
    ("METRO_SEV_L1_E10", "Ascensor Calle Enramadilla", 37.378347, -5.979138, True),

    # La Plata - 2 accesos
    ("METRO_SEV_L1_E15", "La Plata Norte", 37.371613, -5.951870, None),
    ("METRO_SEV_L1_E15", "La Plata Sur", 37.371539, -5.951610, None),

    # Parque de los Príncipes - 1 acceso
    ("METRO_SEV_L1_E6", "Parque de los Príncipes", 37.376395, -6.004669, None),

    # Puerta de Jerez - 1 acceso
    ("METRO_SEV_L1_E8", "Puerta de Jerez", 37.381859, -5.994462, None),

    # Cocheras - 1 acceso
    ("METRO_SEV_L1_E16", "Cocheras", 37.367935, -5.950275, None),

    # Pablo de Olavide - 1 acceso
    ("METRO_SEV_L1_E17", "Pablo de Olavide", 37.354112, -5.943295, None),
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


def update_accesses():
    """Insert or update accesses in database."""
    engine = get_engine()

    created = 0
    updated = 0
    errors = 0

    with engine.connect() as conn:
        for stop_id, name, lat, lon, wheelchair in METRO_ACCESSES:
            try:
                # Check if exists
                result = conn.execute(text("""
                    SELECT id FROM stop_access
                    WHERE stop_id = :stop_id AND name = :name
                """), {"stop_id": stop_id, "name": name})

                if result.fetchone():
                    # Update
                    conn.execute(text("""
                        UPDATE stop_access
                        SET lat = :lat, lon = :lon
                        WHERE stop_id = :stop_id AND name = :name
                    """), {"stop_id": stop_id, "name": name, "lat": lat, "lon": lon})
                    print(f"  ⏫ Actualizado: {stop_id} - {name}")
                    updated += 1
                else:
                    # Insert
                    conn.execute(text("""
                        INSERT INTO stop_access (stop_id, name, lat, lon, wheelchair, source)
                        VALUES (:stop_id, :name, :lat, :lon, :wheelchair, 'osm')
                    """), {"stop_id": stop_id, "name": name, "lat": lat, "lon": lon, "wheelchair": wheelchair})
                    print(f"  ✅ Creado: {stop_id} - {name}" + (" (♿)" if wheelchair else ""))
                    created += 1

            except Exception as e:
                print(f"  ❌ Error: {stop_id} - {name}: {e}")
                errors += 1

        conn.commit()

    return created, updated, errors


def main():
    print("=" * 60)
    print("SEVILLA - Accesos Metro desde OSM")
    print("=" * 60)
    print(f"\nAccesos a procesar: {len(METRO_ACCESSES)}\n")

    created, updated, errors = update_accesses()

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"✅ Creados: {created}")
    print(f"⏫ Actualizados: {updated}")
    print(f"❌ Errores: {errors}")


if __name__ == "__main__":
    main()
