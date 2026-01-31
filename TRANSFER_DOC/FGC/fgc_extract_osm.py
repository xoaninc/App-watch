#!/usr/bin/env python3
"""
FGC - Extracción de datos desde OSM

Este script extrae datos de OpenStreetMap para FGC:
- Accesos (subway_entrance)
- Andenes (railway=platform)
- stop_area relations
- Correspondencias con otros operadores

Salida: fgc_data.json para revisión manual

Uso:
    python fgc_extract_osm.py
    python fgc_extract_osm.py --output fgc_data.json
"""

import argparse
import json
import requests
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TIMEOUT = 60

# Área de búsqueda: Cataluña
BBOX = "41.0,0.5,42.5,3.0"


@dataclass
class Acceso:
    osm_id: int
    osm_type: str
    name: str
    lat: float
    lon: float
    station_name: str
    tags: Dict[str, str]


@dataclass
class Anden:
    osm_id: int
    osm_type: str
    name: str
    lat: float
    lon: float
    station_name: str
    tags: Dict[str, str]


@dataclass
class StopArea:
    osm_id: int
    name: str
    members_count: int
    members: List[Dict[str, Any]]
    operator: str


@dataclass
class Discrepancia:
    tipo: str
    descripcion: str
    osm_id: int = None
    gtfs_id: str = None


def query_overpass(query: str) -> Dict:
    """Ejecuta query en Overpass API."""
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error en Overpass: {e}")
        return {"elements": []}


def get_center(element: Dict) -> tuple:
    """Obtiene coordenadas centrales de un elemento OSM."""
    if "lat" in element and "lon" in element:
        return element["lat"], element["lon"]
    elif "center" in element:
        return element["center"]["lat"], element["center"]["lon"]
    return None, None


def extract_accesos() -> List[Acceso]:
    """Extrae accesos de estaciones FGC."""
    print("Extrayendo accesos FGC...")

    query = f"""
    [out:json][timeout:{TIMEOUT}];
    (
      node["railway"="subway_entrance"]["operator"~"FGC|Ferrocarrils",i]({BBOX});
      node["entrance"="yes"]["operator"~"FGC|Ferrocarrils",i]({BBOX});
      node["railway"="subway_entrance"]["network"="FGC"]({BBOX});
    );
    out body;
    """

    data = query_overpass(query)
    accesos = []

    for elem in data.get("elements", []):
        tags = elem.get("tags", {})
        lat, lon = get_center(elem)

        accesos.append(Acceso(
            osm_id=elem["id"],
            osm_type=elem["type"],
            name=tags.get("name", "Sin nombre"),
            lat=lat,
            lon=lon,
            station_name=tags.get("station", tags.get("ref", "?")),
            tags=tags
        ))

    print(f"  Encontrados: {len(accesos)} accesos")
    return accesos


def extract_andenes() -> List[Anden]:
    """Extrae andenes/plataformas FGC."""
    print("Extrayendo andenes FGC...")

    query = f"""
    [out:json][timeout:{TIMEOUT}];
    (
      way["railway"="platform"]["operator"~"FGC|Ferrocarrils",i]({BBOX});
      node["railway"="platform"]["operator"~"FGC|Ferrocarrils",i]({BBOX});
      way["public_transport"="platform"]["operator"~"FGC|Ferrocarrils",i]({BBOX});
    );
    out center;
    """

    data = query_overpass(query)
    andenes = []

    for elem in data.get("elements", []):
        tags = elem.get("tags", {})
        lat, lon = get_center(elem)

        andenes.append(Anden(
            osm_id=elem["id"],
            osm_type=elem["type"],
            name=tags.get("name", tags.get("ref", "Sin nombre")),
            lat=lat,
            lon=lon,
            station_name=tags.get("station", tags.get("description", "?")),
            tags=tags
        ))

    print(f"  Encontrados: {len(andenes)} andenes")
    return andenes


def extract_stop_areas() -> List[StopArea]:
    """Extrae stop_area relations de FGC."""
    print("Extrayendo stop_area FGC...")

    query = f"""
    [out:json][timeout:{TIMEOUT}];
    (
      relation["public_transport"="stop_area"]["name"~"FGC|Ferrocarrils",i]({BBOX});
      relation["public_transport"="stop_area"]["operator"~"FGC|Ferrocarrils",i]({BBOX});
    );
    out body;
    """

    data = query_overpass(query)
    stop_areas = []

    for elem in data.get("elements", []):
        tags = elem.get("tags", {})
        members = elem.get("members", [])

        stop_areas.append(StopArea(
            osm_id=elem["id"],
            name=tags.get("name", "Sin nombre"),
            members_count=len(members),
            members=members,
            operator=tags.get("operator", tags.get("network", "?"))
        ))

    print(f"  Encontrados: {len(stop_areas)} stop_area")
    return stop_areas


def extract_stop_area_groups() -> List[Dict]:
    """Extrae stop_area_group (intercambiadores multi-operador)."""
    print("Extrayendo stop_area_group (intercambiadores)...")

    # Buscar stop_area_group en Barcelona que contengan FGC
    query = f"""
    [out:json][timeout:{TIMEOUT}];
    area["name"="Barcelona"]->.bcn;
    (
      relation["public_transport"="stop_area_group"](area.bcn);
    );
    out body;
    """

    data = query_overpass(query)
    groups = []

    for elem in data.get("elements", []):
        tags = elem.get("tags", {})
        members = elem.get("members", [])

        groups.append({
            "osm_id": elem["id"],
            "name": tags.get("name", "Sin nombre"),
            "members_count": len(members),
            "members": members,
            "tags": tags
        })

    print(f"  Encontrados: {len(groups)} stop_area_group")
    return groups


def extract_key_stations() -> List[Dict]:
    """Extrae estaciones clave de intercambio."""
    print("Extrayendo estaciones clave (Catalunya, Espanya, Gràcia, Provença)...")

    query = f"""
    [out:json][timeout:{TIMEOUT}];
    (
      node["railway"~"station|stop"]["name"~"Catalunya|Espanya|Gràcia|Provença",i](41.3,2.0,41.5,2.3);
    );
    out body;
    """

    data = query_overpass(query)
    stations = []

    for elem in data.get("elements", []):
        tags = elem.get("tags", {})
        lat, lon = get_center(elem)

        stations.append({
            "osm_id": elem["id"],
            "name": tags.get("name", "?"),
            "operator": tags.get("operator", tags.get("network", "?")),
            "lat": lat,
            "lon": lon,
            "tags": tags
        })

    print(f"  Encontradas: {len(stations)} estaciones")
    return stations


def find_discrepancias(accesos: List, andenes: List, stop_areas: List) -> List[Discrepancia]:
    """Identifica discrepancias y datos que no cuadran."""
    discrepancias = []

    # Verificar andenes sin nombre de estación
    for anden in andenes:
        if anden.station_name == "?":
            discrepancias.append(Discrepancia(
                tipo="anden_sin_estacion",
                descripcion=f"Andén {anden.osm_id} sin estación asociada",
                osm_id=anden.osm_id
            ))

    # Verificar accesos sin nombre
    for acceso in accesos:
        if acceso.name == "Sin nombre" and acceso.station_name == "?":
            discrepancias.append(Discrepancia(
                tipo="acceso_sin_info",
                descripcion=f"Acceso {acceso.osm_id} sin nombre ni estación",
                osm_id=acceso.osm_id
            ))

    # Verificar stop_areas sin operador claro
    for sa in stop_areas:
        if sa.operator == "?":
            discrepancias.append(Discrepancia(
                tipo="stop_area_sin_operador",
                descripcion=f"stop_area '{sa.name}' sin operador definido",
                osm_id=sa.osm_id
            ))

    return discrepancias


def main():
    parser = argparse.ArgumentParser(description="Extrae datos FGC de OSM")
    parser.add_argument("--output", "-o", default="fgc_data.json", help="Archivo de salida")
    args = parser.parse_args()

    print("=" * 60)
    print("FGC - Extracción de datos OSM")
    print("=" * 60)
    print()

    # Extraer datos
    accesos = extract_accesos()
    andenes = extract_andenes()
    stop_areas = extract_stop_areas()
    stop_area_groups = extract_stop_area_groups()
    key_stations = extract_key_stations()

    # Encontrar discrepancias
    discrepancias = find_discrepancias(accesos, andenes, stop_areas)

    # Preparar resultado
    result = {
        "fecha_extraccion": datetime.now().isoformat(),
        "resumen": {
            "accesos": len(accesos),
            "andenes": len(andenes),
            "stop_areas": len(stop_areas),
            "stop_area_groups": len(stop_area_groups),
            "estaciones_clave": len(key_stations),
            "discrepancias": len(discrepancias)
        },
        "accesos": [asdict(a) for a in accesos],
        "andenes": [asdict(a) for a in andenes],
        "stop_areas": [asdict(sa) for sa in stop_areas],
        "stop_area_groups": stop_area_groups,
        "estaciones_clave": key_stations,
        "discrepancias": [asdict(d) for d in discrepancias]
    }

    # Guardar JSON
    output_path = args.output
    if not output_path.startswith("/"):
        import os
        output_path = os.path.join(os.path.dirname(__file__), output_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"  Accesos:           {len(accesos)}")
    print(f"  Andenes:           {len(andenes)}")
    print(f"  stop_area:         {len(stop_areas)}")
    print(f"  stop_area_group:   {len(stop_area_groups)}")
    print(f"  Estaciones clave:  {len(key_stations)}")
    print(f"  Discrepancias:     {len(discrepancias)}")
    print()
    print(f"Guardado en: {output_path}")

    # Mostrar discrepancias
    if discrepancias:
        print()
        print("DISCREPANCIAS ENCONTRADAS:")
        print("-" * 40)
        for d in discrepancias[:10]:
            print(f"  [{d.tipo}] {d.descripcion}")
        if len(discrepancias) > 10:
            print(f"  ... y {len(discrepancias) - 10} más")

    # Mostrar estaciones clave por operador
    print()
    print("ESTACIONES CLAVE POR OPERADOR:")
    print("-" * 40)
    by_operator = {}
    for s in key_stations:
        op = s["operator"]
        if op not in by_operator:
            by_operator[op] = []
        by_operator[op].append(s["name"])

    for op, names in sorted(by_operator.items()):
        print(f"  {op}: {len(names)} estaciones")
        for name in names[:5]:
            print(f"    - {name}")
        if len(names) > 5:
            print(f"    ... y {len(names) - 5} más")


if __name__ == "__main__":
    main()
