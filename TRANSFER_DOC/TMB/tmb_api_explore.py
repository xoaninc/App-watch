#!/usr/bin/env python3
"""
TMB API Explorer - Extrae coordenadas de estaciones y accesos.

Este script explora la API de TMB para obtener:
1. Coordenadas de estaciones por línea (pueden diferir = coords de andén)
2. Coordenadas de accesos por estación

Uso:
    source .venv/bin/activate
    python TRANSFER_DOC/TMB/tmb_api_explore.py
"""

import os
import json
import requests
from typing import Dict, List
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('.env.local')

APP_ID = os.getenv('TMB_APP_ID')
APP_KEY = os.getenv('TMB_APP_KEY')

BASE_URL = "https://api.tmb.cat/v1"

METRO_LINES = ["L1", "L2", "L3", "L4", "L5", "L9N", "L9S", "L10N", "L10S", "L11"]


def get_stations_by_line(line: str) -> List[Dict]:
    """Obtiene estaciones de una línea de metro."""
    url = f"{BASE_URL}/transit/linies/metro/{line}/estacions"
    params = {"app_id": APP_ID, "app_key": APP_KEY}

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("features", [])
        else:
            print(f"  Error {resp.status_code} para {line}")
            return []
    except Exception as e:
        print(f"  Exception para {line}: {e}")
        return []


def get_accesos_by_station(line: str, station_id: str) -> List[Dict]:
    """Obtiene accesos de una estación."""
    url = f"{BASE_URL}/transit/linies/metro/{line}/estacions/{station_id}/accessos"
    params = {"app_id": APP_ID, "app_key": APP_KEY}

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("features", [])
        else:
            return []
    except Exception:
        return []


def main():
    print("=" * 60)
    print("TMB API Explorer - Extracción de coordenadas")
    print("=" * 60)

    all_stations = {}  # station_name -> {line -> coords}
    all_accesos = {}   # station_name -> [accesos]

    for line in METRO_LINES:
        print(f"\n=== Línea {line} ===")
        stations = get_stations_by_line(line)
        print(f"  Estaciones: {len(stations)}")

        for station in stations:
            props = station.get("properties", {})
            geom = station.get("geometry", {})

            station_name = props.get("NOM_ESTACIO", "?")
            station_id = props.get("CODI_ESTACIO", "?")
            coords = geom.get("coordinates", [None, None])

            if station_name not in all_stations:
                all_stations[station_name] = {"id": station_id, "lines": {}}

            all_stations[station_name]["lines"][line] = {
                "lon": coords[0],
                "lat": coords[1]
            }

            # Obtener accesos
            if station_name not in all_accesos:
                accesos = get_accesos_by_station(line, station_id)
                if accesos:
                    all_accesos[station_name] = []
                    for acc in accesos:
                        acc_props = acc.get("properties", {})
                        acc_geom = acc.get("geometry", {})
                        acc_coords = acc_geom.get("coordinates", [None, None])
                        all_accesos[station_name].append({
                            "name": acc_props.get("NOM_ACCES", "?"),
                            "wheelchair": acc_props.get("ACCESSIBLE", "?"),
                            "lon": acc_coords[0],
                            "lat": acc_coords[1]
                        })

    # Análisis: ¿Estaciones con coords diferentes por línea?
    print("\n" + "=" * 60)
    print("ANÁLISIS: Estaciones con coords diferentes por línea")
    print("=" * 60)

    stations_with_diff_coords = []

    for name, data in all_stations.items():
        lines = data["lines"]
        if len(lines) > 1:
            coords_set = set()
            for line, c in lines.items():
                if c["lat"] and c["lon"]:
                    coords_set.add((round(c["lat"], 5), round(c["lon"], 5)))

            if len(coords_set) > 1:
                stations_with_diff_coords.append(name)
                print(f"\n{name}:")
                for line, c in lines.items():
                    print(f"  {line}: ({c['lat']}, {c['lon']})")

    print(f"\n\nEstaciones con coords diferentes: {len(stations_with_diff_coords)}")
    print(f"Estaciones totales: {len(all_stations)}")
    print(f"Estaciones con accesos: {len(all_accesos)}")

    # Guardar datos
    output = {
        "stations": all_stations,
        "accesos": all_accesos,
        "stations_with_diff_coords": stations_with_diff_coords
    }

    output_file = os.path.join(os.path.dirname(__file__), "tmb_api_data.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDatos guardados en: {output_file}")

    # Resumen de accesos
    print("\n" + "=" * 60)
    print("ACCESOS POR ESTACIÓN")
    print("=" * 60)
    total_accesos = sum(len(a) for a in all_accesos.values())
    print(f"Total accesos: {total_accesos}")
    print(f"Estaciones con accesos: {len(all_accesos)}")

    # Mostrar algunas estaciones con accesos
    for name, accesos in list(all_accesos.items())[:5]:
        print(f"\n{name} ({len(accesos)} accesos):")
        for acc in accesos[:3]:
            print(f"  - {acc['name']}: ({acc['lat']}, {acc['lon']}) wheelchair={acc['wheelchair']}")


if __name__ == "__main__":
    main()
