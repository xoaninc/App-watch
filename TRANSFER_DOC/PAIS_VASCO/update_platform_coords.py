#!/usr/bin/env python3
"""
Actualiza coordenadas de andenes de Metro Bilbao desde OSM.

Los andenes del GTFS tienen coordenadas "falsas" (igual a la estación padre).
Este script actualiza las coordenadas con datos reales de OSM.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# COORDENADAS REALES DE OSM
# Formato: stop_id -> (lat, lon)
# Extraído de Overpass API 2026-01-31
# =============================================================================

# Metro Bilbao - Coordenadas reales de OSM
# Extraído de Overpass API 2026-01-31 (station=subway nodes)
METRO_COORDS_OSM = {
    # === YA ACTUALIZADOS (14) ===
    "METRO_BILBAO_4.0": (43.251151, -2.910744),   # Basarrate
    "METRO_BILBAO_5.0": (43.260170, -2.921824),   # Zazpikaleak
    "METRO_BILBAO_6.0": (43.259641, -2.920709),   # Zazpikaleak
    "METRO_BILBAO_7.0": (43.261363, -2.927437),   # Abando
    "METRO_BILBAO_8.0": (43.261294, -2.941861),   # Indautxu
    "METRO_BILBAO_9.0": (43.271545, -2.949600),   # Deustu
    "METRO_BILBAO_10.0": (43.262552, -2.947596),  # San Mamés
    "METRO_BILBAO_14.0": (43.290995, -2.969921),  # Lutxana
    "METRO_BILBAO_16.0": (43.305731, -2.992614),  # Urbinaga
    "METRO_BILBAO_19.0": (43.290995, -2.969921),  # Lutxana
    "METRO_BILBAO_29.0": (43.333025, -3.007381),  # Gobela
    "METRO_BILBAO_37.0": (43.380220, -2.978972),  # Sopela
    "METRO_BILBAO_39.0": (43.317667, -3.020735),  # Portugalete
    "METRO_BILBAO_41.0": (43.322357, -3.037821),  # Kabiezes

    # === PENDIENTES (28) - Nuevas coords OSM ===
    "METRO_BILBAO_1.0": (43.254297, -2.913287),   # Santutxu
    "METRO_BILBAO_2.0": (43.251064, -2.889680),   # Larreineta/Kukullaga
    "METRO_BILBAO_3.0": (43.280785, -2.962474),   # San Inazio
    "METRO_BILBAO_11.0": (43.328850, -3.034286),  # Santurtzi
    "METRO_BILBAO_12.0": (43.340231, -3.005547),  # Neguri
    "METRO_BILBAO_13.0": (43.317900, -2.991707),  # Leioa
    "METRO_BILBAO_15.0": (43.298809, -2.992626),  # Bagatza
    "METRO_BILBAO_17.0": (43.283038, -2.982483),  # Gurutzeta
    "METRO_BILBAO_18.0": (43.303881, -2.974465),  # Erandio
    "METRO_BILBAO_20.0": (43.243873, -2.897741),  # Etxebarri
    "METRO_BILBAO_21.0": (43.271545, -2.949600),  # Deustu (mismo que 9)
    "METRO_BILBAO_22.0": (43.246951, -2.905644),  # Bolueta
    "METRO_BILBAO_23.0": (43.350331, -3.009294),  # Algorta
    "METRO_BILBAO_24.0": (43.356445, -3.011273),  # Bidezabal
    "METRO_BILBAO_25.0": (43.366967, -2.999522),  # Berango
    "METRO_BILBAO_26.0": (43.363276, -3.006978),  # Ibarbengoa
    "METRO_BILBAO_27.0": (43.375674, -2.991499),  # Larrabasterra
    "METRO_BILBAO_28.0": (43.401223, -2.946352),  # Plentzia
    "METRO_BILBAO_30.0": (43.379004, -2.958142),  # Urduliz
    "METRO_BILBAO_31.0": (43.309170, -3.005685),  # Sestao
    "METRO_BILBAO_32.0": (43.380220, -2.978972),  # Sopela
    "METRO_BILBAO_33.0": (43.379004, -2.958142),  # Urduliz (duplicado)
    "METRO_BILBAO_34.0": (43.314623, -2.986798),  # Astrabudua
    "METRO_BILBAO_35.0": (43.289696, -2.986892),  # Ansio
    "METRO_BILBAO_36.0": (43.243873, -2.897741),  # Etxebarri (duplicado)
    "METRO_BILBAO_38.0": (43.344060, -3.002687),  # Aiboa
    "METRO_BILBAO_40.0": (43.321972, -3.025367),  # Peñota
    "METRO_BILBAO_42.0": (43.325997, -3.009635),  # Areeta
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


def update_coords():
    """Update platform coordinates from OSM data."""
    engine = get_engine()
    updated = 0
    errors = 0

    with engine.connect() as conn:
        for stop_id, (lat, lon) in METRO_COORDS_OSM.items():
            try:
                # Verificar que existe
                result = conn.execute(text("""
                    SELECT lat, lon FROM gtfs_stops WHERE id = :id
                """), {"id": stop_id})
                row = result.fetchone()

                if not row:
                    print(f"  ⚠️  No existe: {stop_id}")
                    continue

                old_lat, old_lon = row

                # Actualizar
                conn.execute(text("""
                    UPDATE gtfs_stops
                    SET lat = :lat, lon = :lon
                    WHERE id = :id
                """), {"lat": lat, "lon": lon, "id": stop_id})

                print(f"  ✅ {stop_id}: ({old_lat:.4f}, {old_lon:.4f}) → ({lat:.4f}, {lon:.4f})")
                updated += 1

            except Exception as e:
                print(f"  ❌ Error {stop_id}: {e}")
                errors += 1

        conn.commit()

    return updated, errors


def main():
    print("=" * 60)
    print("ACTUALIZACIÓN COORDENADAS ANDENES - OSM")
    print("=" * 60)
    print(f"\nAndenes a actualizar: {len(METRO_COORDS_OSM)}")
    print()

    updated, errors = update_coords()

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"✅ Actualizados: {updated}")
    print(f"❌ Errores: {errors}")

    remaining = 42 - updated
    print(f"\n⚠️  Quedan {remaining} andenes Metro Bilbao sin datos OSM")


if __name__ == "__main__":
    main()
