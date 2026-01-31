#!/usr/bin/env python3
"""
Corrige andenes de Euskotren con coordenadas duplicadas.
Aplica un offset de ~15m para separar Q1, Q2, Q3, etc.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

OFFSET = 0.00015  # ~15m


def get_engine():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        user = os.getenv("POSTGRES_USER", "renfeserver")
        password = os.getenv("POSTGRES_PASSWORD", "")
        host = os.getenv("POSTGRES_HOST", "localhost")
        db = os.getenv("POSTGRES_DB", "renfeserver_prod")
        database_url = f"postgresql://{user}:{password}@{host}/{db}"
    return create_engine(database_url)


def fix_duplicates():
    engine = get_engine()
    updated = 0

    with engine.connect() as conn:
        # Obtener todos los andenes
        result = conn.execute(text("""
            SELECT id, name, lat, lon
            FROM gtfs_stops
            WHERE id LIKE 'EUSKOTREN%Quay%'
            AND location_type = 0
            ORDER BY id
        """))

        # Agrupar por estación
        stations = defaultdict(list)
        for row in result:
            parts = row[0].split(':')
            if len(parts) >= 4:
                code = parts[3].split('_')[0]
                stations[code].append({
                    'id': row[0],
                    'name': row[1],
                    'lat': row[2],
                    'lon': row[3]
                })

        # Procesar estaciones con duplicados
        for code, platforms in stations.items():
            if len(platforms) <= 1:
                continue

            # Verificar si tienen mismas coords
            coords = set((round(p['lat'], 4), round(p['lon'], 4)) for p in platforms)
            if len(coords) > 1:
                continue  # Ya están separadas

            base_lat = platforms[0]['lat']
            base_lon = platforms[0]['lon']

            # Aplicar offset según número de andén
            for i, p in enumerate(platforms):
                # Extraer número de Q
                q_part = p['id'].split('_Q')[-1].rstrip(':')
                try:
                    q_num = int(q_part)
                except:
                    q_num = i + 1

                # Calcular nuevo offset
                if q_num == 1:
                    new_lat = base_lat + OFFSET
                    new_lon = base_lon
                elif q_num == 2:
                    new_lat = base_lat - OFFSET
                    new_lon = base_lon
                else:
                    # Para Q3+, usar offset en longitud
                    new_lat = base_lat
                    new_lon = base_lon + OFFSET * (q_num - 2)

                # Actualizar
                conn.execute(text("""
                    UPDATE gtfs_stops
                    SET lat = :lat, lon = :lon
                    WHERE id = :id
                """), {"lat": new_lat, "lon": new_lon, "id": p['id']})

                updated += 1

            print(f"  ✅ {platforms[0]['name']} ({code}): {len(platforms)} andenes separados")

        conn.commit()

    return updated


def main():
    print("=" * 60)
    print("CORRECCIÓN DUPLICADOS EUSKOTREN")
    print("=" * 60)
    print(f"Offset: {OFFSET} grados (~{OFFSET * 111000:.0f}m)")
    print()

    updated = fix_duplicates()

    print("\n" + "=" * 60)
    print(f"✅ Andenes actualizados: {updated}")


if __name__ == "__main__":
    main()
