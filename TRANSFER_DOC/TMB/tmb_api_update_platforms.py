#!/usr/bin/env python3
"""
TMB Metro Barcelona - Actualización de coordenadas de andenes desde API TMB.

Este script usa los datos extraídos de la API TMB (tmb_api_data.json) para
actualizar las coordenadas de andenes en la BD.

Lógica:
1. BD platform ID 1.1XX -> L1, 1.2XX -> L2, etc.
2. Buscar estación padre en datos API por nombre
3. Usar coordenadas de la línea correspondiente

Uso:
    source .venv/bin/activate
    python TRANSFER_DOC/TMB/tmb_api_update_platforms.py --dry-run
    python TRANSFER_DOC/TMB/tmb_api_update_platforms.py
"""

import os
import json
import argparse
import logging
from typing import Dict, List, Tuple

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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
API_DATA_FILE = os.path.join(SCRIPT_DIR, "tmb_api_data.json")

# Mapeo de prefijo de ID BD a línea TMB API
PREFIX_TO_LINE = {
    "1": "L1",
    "2": "L2",
    "3": "L3",
    "4": "L4",
    "5": "L5",
    "9": None,  # Necesita mapeo especial para L9N/L9S/L10N/L10S/L11/FM
}

# Mapeo de IDs específicos de L9/L10/L11/FM
# Basado en stops.txt de GTFS TMB (verificado con BD)
L9_MAPPING = {
    # L9S (91) - Aeroport a Zona Universitària
    "901": "L9S",  # Aeroport T1
    "903": "L9S",  # Aeroport T2
    "904": "L9S",  # Mas Blau
    "905": "L9S",  # Parc Nou
    "906": "L9S",  # Cèntric
    "907": "L9S",  # El Prat Estació
    "909": "L9S",  # Les Moreres
    "910": "L9S",  # Mercabarna
    "911": "L9S",  # Parc Logístic
    "912": "L9S",  # Fira
    "913": "L9S",  # Europa | Fira
    "914": "L9S",  # Can Tries | Gornal
    "915": "L9S",  # Torrassa
    "916": "L9S",  # Collblanc
    "918": "L9S",  # Zona Universitària

    # L9N/L10N compartidos - La Sagrera a Gorg
    "930": "L9N",  # La Sagrera
    "932": "L9N",  # Onze de Setembre
    "933": "L9N",  # Bon Pastor
    "934": "L9N",  # Llefià
    "935": "L9N",  # La Salut
    "936": "L10N",  # Gorg (solo L10N)

    # L9N exclusivo
    "940": "L9N",  # Can Peixauet
    "941": "L9N",  # Santa Rosa
    "942": "L9N",  # Fondo
    "943": "L9N",  # Església Major
    "944": "L9N",  # Singuerlín
    "945": "L9N",  # Can Zam

    # L10S (101) - ZAL a Provençana
    "951": "L10S",  # ZAL | Riu Vell
    "952": "L10S",  # Ecoparc
    "953": "L10S",  # Port Comercial | La Factoria
    "954": "L10S",  # Zona Franca
    "956": "L10S",  # Foc
    "957": "L10S",  # Foneria
    "958": "L10S",  # Ciutat de la Justícia
    "959": "L10S",  # Provençana

    # L11 (11) - Trinitat Nova a Can Cuiàs
    "1136": "L11",  # Trinitat Nova
    "1137": "L11",  # Casa de l'Aigua
    "1138": "L11",  # Torre Baró | Vallbona
    "1139": "L11",  # Ciutat Meridiana
    "1140": "L11",  # Can Cuiàs

    # FM - Funicular de Montjuïc (99)
    "9901": "FM",  # Paral·lel
    "9902": "FM",  # Parc de Montjuïc
}


def load_api_data() -> Dict:
    """Carga datos de API TMB."""
    with open(API_DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_line_from_platform_id(platform_id: str) -> str:
    """Determina la línea de metro a partir del ID del andén."""
    # TMB_METRO_1.XXX -> XXX
    num = platform_id.split(".")[-1]

    # Primero buscar en mapeo específico de L9/L10/L11/FM
    if num in L9_MAPPING:
        return L9_MAPPING[num]

    # Detectar por rango numérico
    try:
        n = int(num)

        # L11 (IDs 1136-1140)
        if 1136 <= n <= 1140:
            return "L11"

        # L9S (IDs 901-918)
        if 901 <= n <= 918:
            return "L9S"

        # L9N/L10N compartido (IDs 930-936)
        if 930 <= n <= 936:
            return "L9N"

        # L9N exclusivo (IDs 940-945)
        if 940 <= n <= 945:
            return "L9N"

        # L10S (IDs 951-959)
        if 951 <= n <= 959:
            return "L10S"

        # FM (IDs 9901-9902)
        if 9901 <= n <= 9902:
            return "FM"

        # L1-L5 por prefijo (IDs de 3 dígitos)
        if 100 <= n <= 199:
            return "L1"
        elif 200 <= n <= 299:
            return "L2"
        elif 300 <= n <= 399:
            return "L3"
        elif 400 <= n <= 499:
            return "L4"
        elif 500 <= n <= 599:
            return "L5"

    except ValueError:
        pass

    return None


def normalize_station_name(name: str) -> str:
    """Normaliza nombre para comparación."""
    # Remover prefijos/sufijos comunes
    normalized = name.strip()

    # Mapeo específico de nombres BD -> API
    name_map = {
        "Plaça de Catalunya": "Catalunya",
        "Sant Pau | Dos de Maig": "Sant Pau | Dos de Maig",
    }

    return name_map.get(normalized, normalized)


def find_station_in_api(api_data: Dict, station_name: str) -> Dict:
    """Busca estación en datos API por nombre."""
    stations = api_data.get("stations", {})

    # Buscar exacto
    if station_name in stations:
        return stations[station_name]

    # Buscar normalizado
    normalized = normalize_station_name(station_name)
    if normalized in stations:
        return stations[normalized]

    # Buscar parcial
    for api_name, data in stations.items():
        if station_name.lower() in api_name.lower() or api_name.lower() in station_name.lower():
            return data

    return None


def get_bd_platforms(conn) -> List[Dict]:
    """Obtiene andenes de BD con coords = parent."""
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.name, s.lat, s.lon, p.name as parent_name, p.lat as parent_lat, p.lon as parent_lon
        FROM gtfs_stops s
        JOIN gtfs_stops p ON s.parent_station_id = p.id
        WHERE s.id LIKE 'TMB_METRO_1.%' AND s.location_type = 0
        ORDER BY s.id
    """)

    platforms = []
    for row in cur.fetchall():
        lat, lon = float(row[2]), float(row[3])
        parent_lat, parent_lon = float(row[5]), float(row[6])

        platforms.append({
            "id": row[0],
            "name": row[1],
            "lat": lat,
            "lon": lon,
            "parent_name": row[4],
            "parent_lat": parent_lat,
            "parent_lon": parent_lon,
            "needs_update": abs(lat - parent_lat) < 0.00001 and abs(lon - parent_lon) < 0.00001
        })

    cur.close()
    return platforms


def update_platforms(conn, api_data: Dict, dry_run: bool) -> Tuple[int, int, int]:
    """
    Actualiza coordenadas de andenes.

    Returns:
        (actualizados, sin_cambio, errores)
    """
    logger.info("=== ACTUALIZANDO COORDENADAS DE ANDENES ===")

    platforms = get_bd_platforms(conn)
    needs_update = [p for p in platforms if p["needs_update"]]

    logger.info(f"Total andenes BD: {len(platforms)}")
    logger.info(f"Andenes que necesitan actualización: {len(needs_update)}")

    updates = []
    no_match = []
    no_line_coords = []

    for plat in needs_update:
        line = get_line_from_platform_id(plat["id"])
        if not line:
            no_match.append((plat["id"], plat["parent_name"], "No se pudo determinar línea"))
            continue

        # Buscar estación en API
        api_station = find_station_in_api(api_data, plat["parent_name"])
        if not api_station:
            no_match.append((plat["id"], plat["parent_name"], "Estación no encontrada en API"))
            continue

        # Buscar coords para esta línea
        line_data = api_station.get("lines", {}).get(line)
        if not line_data:
            # Intentar con línea alternativa (L9N/L9S, L10N/L10S)
            alt_lines = {
                "L9N": ["L9S"], "L9S": ["L9N"],
                "L10N": ["L10S"], "L10S": ["L10N"]
            }
            found = False
            for alt in alt_lines.get(line, []):
                line_data = api_station.get("lines", {}).get(alt)
                if line_data:
                    found = True
                    break

            if not found:
                # Usar cualquier línea disponible
                available_lines = list(api_station.get("lines", {}).keys())
                if available_lines:
                    line_data = api_station["lines"][available_lines[0]]
                else:
                    no_line_coords.append((plat["id"], plat["parent_name"], line))
                    continue

        new_lat = line_data["lat"]
        new_lon = line_data["lon"]

        if new_lat and new_lon:
            updates.append({
                "id": plat["id"],
                "name": plat["name"],
                "parent": plat["parent_name"],
                "line": line,
                "old_lat": plat["lat"],
                "old_lon": plat["lon"],
                "new_lat": new_lat,
                "new_lon": new_lon
            })

    logger.info(f"\nResultados:")
    logger.info(f"  A actualizar: {len(updates)}")
    logger.info(f"  Sin match: {len(no_match)}")
    logger.info(f"  Sin coords de línea: {len(no_line_coords)}")

    if no_match:
        logger.info(f"\nSin match ({len(no_match)}):")
        for plat_id, parent, reason in no_match[:10]:
            logger.info(f"  {plat_id} ({parent}): {reason}")
        if len(no_match) > 10:
            logger.info(f"  ... y {len(no_match) - 10} más")

    if updates:
        logger.info(f"\nEjemplos de actualizaciones:")
        for upd in updates[:10]:
            logger.info(f"  {upd['id']} ({upd['parent']} {upd['line']}): ({upd['old_lat']:.6f}, {upd['old_lon']:.6f}) -> ({upd['new_lat']:.6f}, {upd['new_lon']:.6f})")

    if dry_run:
        logger.info(f"\n[DRY-RUN] No se aplicaron cambios")
        return len(updates), len(needs_update) - len(updates) - len(no_match) - len(no_line_coords), len(no_match) + len(no_line_coords)

    # Aplicar actualizaciones
    if updates:
        cur = conn.cursor()
        for upd in updates:
            cur.execute("""
                UPDATE gtfs_stops SET lat = %s, lon = %s WHERE id = %s
            """, (upd["new_lat"], upd["new_lon"], upd["id"]))
        conn.commit()
        cur.close()
        logger.info(f"\nActualizados: {len(updates)} andenes")

    return len(updates), len(needs_update) - len(updates) - len(no_match) - len(no_line_coords), len(no_match) + len(no_line_coords)


def main():
    parser = argparse.ArgumentParser(description="Actualizar coords de andenes TMB desde API")
    parser.add_argument('--dry-run', action='store_true', help="Simular sin cambios")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("TMB Metro - Actualización desde API TMB")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("*** MODO DRY-RUN ***")

    api_data = load_api_data()
    logger.info(f"Estaciones en API: {len(api_data.get('stations', {}))}")

    conn = psycopg2.connect(DATABASE_URL)

    try:
        updated, unchanged, errors = update_platforms(conn, api_data, args.dry_run)

        logger.info("")
        logger.info("=" * 60)
        logger.info("RESUMEN FINAL")
        logger.info("=" * 60)
        logger.info(f"  Actualizados: {updated}")
        logger.info(f"  Sin cambio: {unchanged}")
        logger.info(f"  Errores: {errors}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
