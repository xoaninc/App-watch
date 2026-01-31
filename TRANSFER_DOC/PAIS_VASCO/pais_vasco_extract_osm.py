#!/usr/bin/env python3
"""
Extracción de datos OSM para País Vasco.

Extrae:
- Estaciones y andenes de Metro Bilbao
- Estaciones y andenes de Euskotren
- Funicular Artxanda
- stop_area y stop_area_group (intercambiadores)

Uso:
    python pais_vasco_extract_osm.py
"""

import requests
import json
import time
from typing import Dict, List, Any

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# BBOX País Vasco (sur, oeste, norte, este)
BBOX_BILBAO = "43.20,-3.10,43.45,-2.85"  # Área metropolitana Bilbao
BBOX_PAIS_VASCO = "42.80,-3.20,43.50,-1.70"  # Todo el País Vasco

def query_overpass(query: str, retries: int = 3) -> Dict:
    """Ejecuta query Overpass con reintentos."""
    for attempt in range(retries):
        try:
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=120
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code in [429, 504]:
                print(f"  ⚠️ Rate limit/timeout, reintentando en {30 * (attempt + 1)}s...")
                time.sleep(30 * (attempt + 1))
            else:
                print(f"  ❌ Error {response.status_code}")
                return {"elements": []}
        except Exception as e:
            print(f"  ❌ Error: {e}")
            time.sleep(10)
    return {"elements": []}


def extract_metro_bilbao() -> Dict:
    """Extrae datos de Metro Bilbao."""
    print("\n=== METRO BILBAO ===")

    # Estaciones
    query_stations = f"""
    [out:json][timeout:60];
    (
      node["station"="subway"]["network"~"Metro Bilbao|Bilboko Metroa",i]({BBOX_BILBAO});
      node["railway"="station"]["network"~"Metro Bilbao|Bilboko Metroa",i]({BBOX_BILBAO});
      way["station"="subway"]["network"~"Metro Bilbao|Bilboko Metroa",i]({BBOX_BILBAO});
    );
    out body center;
    """
    print("  Buscando estaciones...")
    stations_data = query_overpass(query_stations)
    stations = stations_data.get("elements", [])
    print(f"  Encontradas: {len(stations)} estaciones")

    # Andenes
    query_platforms = f"""
    [out:json][timeout:60];
    (
      node["railway"="platform"]["network"~"Metro Bilbao|Bilboko Metroa",i]({BBOX_BILBAO});
      way["railway"="platform"]["network"~"Metro Bilbao|Bilboko Metroa",i]({BBOX_BILBAO});
      node["public_transport"="platform"]["network"~"Metro Bilbao|Bilboko Metroa",i]({BBOX_BILBAO});
      way["public_transport"="platform"]["network"~"Metro Bilbao|Bilboko Metroa",i]({BBOX_BILBAO});
    );
    out body center;
    """
    print("  Buscando andenes...")
    platforms_data = query_overpass(query_platforms)
    platforms = platforms_data.get("elements", [])
    print(f"  Encontrados: {len(platforms)} andenes")

    # Accesos
    query_accesses = f"""
    [out:json][timeout:60];
    (
      node["railway"="subway_entrance"]["network"~"Metro Bilbao|Bilboko Metroa",i]({BBOX_BILBAO});
      node["entrance"]["network"~"Metro Bilbao|Bilboko Metroa",i]({BBOX_BILBAO});
    );
    out body;
    """
    print("  Buscando accesos...")
    accesses_data = query_overpass(query_accesses)
    accesses = accesses_data.get("elements", [])
    print(f"  Encontrados: {len(accesses)} accesos")

    return {
        "stations": stations,
        "platforms": platforms,
        "accesses": accesses
    }


def extract_euskotren() -> Dict:
    """Extrae datos de Euskotren."""
    print("\n=== EUSKOTREN ===")

    # Estaciones
    query_stations = f"""
    [out:json][timeout:90];
    (
      node["railway"="station"]["operator"~"Euskotren|Eusko Trenbideak",i]({BBOX_PAIS_VASCO});
      node["railway"="halt"]["operator"~"Euskotren|Eusko Trenbideak",i]({BBOX_PAIS_VASCO});
      way["railway"="station"]["operator"~"Euskotren|Eusko Trenbideak",i]({BBOX_PAIS_VASCO});
    );
    out body center;
    """
    print("  Buscando estaciones...")
    stations_data = query_overpass(query_stations)
    stations = stations_data.get("elements", [])
    print(f"  Encontradas: {len(stations)} estaciones")

    # Andenes
    query_platforms = f"""
    [out:json][timeout:90];
    (
      node["railway"="platform"]["operator"~"Euskotren|Eusko Trenbideak",i]({BBOX_PAIS_VASCO});
      way["railway"="platform"]["operator"~"Euskotren|Eusko Trenbideak",i]({BBOX_PAIS_VASCO});
    );
    out body center;
    """
    print("  Buscando andenes...")
    platforms_data = query_overpass(query_platforms)
    platforms = platforms_data.get("elements", [])
    print(f"  Encontrados: {len(platforms)} andenes")

    return {
        "stations": stations,
        "platforms": platforms
    }


def extract_funicular() -> Dict:
    """Extrae datos del Funicular de Artxanda."""
    print("\n=== FUNICULAR ARTXANDA ===")

    query = f"""
    [out:json][timeout:60];
    (
      node["railway"~"station|halt"]["name"~"Artxanda|Funicular",i]({BBOX_BILBAO});
      way["railway"="funicular"]({BBOX_BILBAO});
      node["aerialway"="station"]["name"~"Artxanda|Funicular",i]({BBOX_BILBAO});
    );
    out body center;
    """
    print("  Buscando estaciones funicular...")
    data = query_overpass(query)
    elements = data.get("elements", [])
    print(f"  Encontrados: {len(elements)} elementos")

    return {"elements": elements}


def extract_stop_areas() -> Dict:
    """Extrae stop_area y stop_area_group para intercambiadores."""
    print("\n=== STOP_AREA (Intercambiadores) ===")

    # stop_area en Bilbao
    query_stop_area = f"""
    [out:json][timeout:90];
    (
      relation["public_transport"="stop_area"]["name"~"Abando|Casco Viejo|San Mames|Matiko|Zazpikaleak",i]({BBOX_BILBAO});
      relation["public_transport"="stop_area"]["operator"~"Metro Bilbao|Euskotren",i]({BBOX_BILBAO});
    );
    out body;
    """
    print("  Buscando stop_area...")
    stop_area_data = query_overpass(query_stop_area)
    stop_areas = stop_area_data.get("elements", [])
    print(f"  Encontrados: {len(stop_areas)} stop_area")

    # stop_area_group (intercambiadores multimodales)
    query_stop_area_group = f"""
    [out:json][timeout:60];
    relation["public_transport"="stop_area_group"]({BBOX_BILBAO});
    out body;
    """
    print("  Buscando stop_area_group...")
    stop_area_group_data = query_overpass(query_stop_area_group)
    stop_area_groups = stop_area_group_data.get("elements", [])
    print(f"  Encontrados: {len(stop_area_groups)} stop_area_group")

    return {
        "stop_areas": stop_areas,
        "stop_area_groups": stop_area_groups
    }


def extract_interchanges_by_name() -> Dict:
    """Busca intercambiadores específicos por nombre."""
    print("\n=== INTERCAMBIADORES POR NOMBRE ===")

    interchanges = {}

    names = [
        ("Abando", "43.255,-2.935,43.268,-2.920"),
        ("Casco Viejo", "43.255,-2.928,43.265,-2.915"),
        ("San Mamés", "43.258,-2.955,43.268,-2.940"),
        ("Matiko", "43.265,-2.932,43.275,-2.918"),
    ]

    for name, bbox in names:
        print(f"  Buscando {name}...")
        query = f"""
        [out:json][timeout:60];
        (
          node["railway"]["name"~"{name}",i]({bbox});
          way["railway"]["name"~"{name}",i]({bbox});
          node["public_transport"]["name"~"{name}",i]({bbox});
          relation["public_transport"]["name"~"{name}",i]({bbox});
        );
        out body center;
        """
        data = query_overpass(query)
        elements = data.get("elements", [])

        # Clasificar por operador
        metro = [e for e in elements if "Metro" in str(e.get("tags", {}))]
        euskotren = [e for e in elements if "Euskotren" in str(e.get("tags", {})) or "Eusko" in str(e.get("tags", {}))]
        renfe = [e for e in elements if "Renfe" in str(e.get("tags", {})) or "RENFE" in str(e.get("tags", {}))]
        otros = [e for e in elements if e not in metro and e not in euskotren and e not in renfe]

        interchanges[name] = {
            "total": len(elements),
            "metro": len(metro),
            "euskotren": len(euskotren),
            "renfe": len(renfe),
            "otros": len(otros),
            "elements": elements
        }
        print(f"    Total: {len(elements)} (Metro: {len(metro)}, Euskotren: {len(euskotren)}, RENFE: {len(renfe)})")

        time.sleep(2)  # Rate limiting

    return interchanges


def main():
    print("=" * 60)
    print("EXTRACCIÓN OSM - PAÍS VASCO")
    print("=" * 60)

    results = {
        "fecha": time.strftime("%Y-%m-%d %H:%M"),
        "metro_bilbao": extract_metro_bilbao(),
        "euskotren": extract_euskotren(),
        "funicular": extract_funicular(),
        "stop_areas": extract_stop_areas(),
        "interchanges": extract_interchanges_by_name(),
    }

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Metro Bilbao:")
    print(f"  - Estaciones: {len(results['metro_bilbao']['stations'])}")
    print(f"  - Andenes: {len(results['metro_bilbao']['platforms'])}")
    print(f"  - Accesos: {len(results['metro_bilbao']['accesses'])}")
    print(f"Euskotren:")
    print(f"  - Estaciones: {len(results['euskotren']['stations'])}")
    print(f"  - Andenes: {len(results['euskotren']['platforms'])}")
    print(f"Funicular: {len(results['funicular']['elements'])} elementos")
    print(f"Stop areas: {len(results['stop_areas']['stop_areas'])}")
    print(f"Stop area groups: {len(results['stop_areas']['stop_area_groups'])}")

    # Guardar resultados
    output_file = "pais_vasco_osm_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Datos guardados en {output_file}")

    return results


if __name__ == "__main__":
    main()
