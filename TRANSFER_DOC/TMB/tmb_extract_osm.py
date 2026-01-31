#!/usr/bin/env python3
"""
TMB Metro Barcelona - Extracción de datos de OSM.

Este script consulta la API de Overpass para extraer:
- Accesos de metro (subway_entrance)
- Andenes (platform)
- stop_area relations
- stop_area_group (intercambiadores)
- Estaciones de metro

Basado en: fgc_extract_osm.py

Uso:
    python TRANSFER_DOC/TMB/tmb_extract_osm.py
    python TRANSFER_DOC/TMB/tmb_extract_osm.py --output tmb_data.json
"""

import argparse
import json
import os
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Any

# Overpass API
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TIMEOUT = 90

# BBOX Barcelona metropolitana
BBOX = "41.3,1.9,41.5,2.3"


@dataclass
class Acceso:
    osm_id: int
    osm_type: str
    name: str
    lat: float
    lon: float
    station_name: str
    line: str
    level: str
    wheelchair: str
    tags: Dict[str, str]


@dataclass
class Anden:
    osm_id: int
    osm_type: str
    name: str
    lat: float
    lon: float
    station_name: str
    line: str
    ref: str
    tags: Dict[str, str]


@dataclass
class StopArea:
    osm_id: int
    name: str
    operator: str
    network: str
    members_count: int
    members: List[Dict[str, Any]]


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
        print(f"  Error en Overpass: {e}")
        return {"elements": []}


def get_center(element: Dict) -> tuple:
    """Obtiene coordenadas centrales de un elemento OSM."""
    if "lat" in element and "lon" in element:
        return element["lat"], element["lon"]
    elif "center" in element:
        return element["center"]["lat"], element["center"]["lon"]
    return None, None


def extract_accesos_via_stop_areas(stop_areas: List[StopArea]) -> List[Acceso]:
    """Extrae accesos de metro TMB expandiendo stop_areas.

    Similar a andenes, los accesos están asociados vía stop_area relations.
    """
    print("Extrayendo accesos vía stop_areas...")

    accesos = []
    seen_ids = set()

    for sa in stop_areas:
        # Filtrar solo TMB
        if "TMB" not in sa.operator and "Transports Metropolitans" not in sa.operator:
            continue

        # Expandir miembros de la stop_area
        query = f"""
        [out:json][timeout:{TIMEOUT}];
        relation({sa.osm_id});
        (._;>;);
        out body center;
        """

        result = query_overpass(query)

        # Filtrar accesos (entrances)
        for element in result.get("elements", []):
            if element["id"] in seen_ids:
                continue

            tags = element.get("tags", {})

            # Solo accesos/entradas
            is_entrance = (
                tags.get("railway") == "subway_entrance" or
                tags.get("entrance") in ["yes", "main", "subway"] or
                tags.get("subway") == "entrance"
            )
            if not is_entrance:
                continue

            seen_ids.add(element["id"])
            lat, lon = get_center(element)

            if lat and lon:
                # Extraer línea del nombre de stop_area
                line = "?"
                if "(" in sa.name and ")" in sa.name:
                    line = sa.name.split("(")[-1].replace(")", "").strip()

                # Nombre de estación sin la línea
                station_name = sa.name.split("(")[0].strip() if "(" in sa.name else sa.name

                accesos.append(Acceso(
                    osm_id=element["id"],
                    osm_type=element["type"],
                    name=tags.get("name", tags.get("ref", "Sin nombre")),
                    lat=lat,
                    lon=lon,
                    station_name=station_name,
                    line=line,
                    level=tags.get("level", "?"),
                    wheelchair=tags.get("wheelchair", "?"),
                    tags=tags
                ))

    print(f"  Encontrados: {len(accesos)} accesos de TMB")
    return accesos


def extract_andenes_via_stop_areas(stop_areas: List[StopArea]) -> List[Anden]:
    """Extrae andenes de metro TMB expandiendo stop_areas.

    Los andenes en OSM no tienen tag 'station' directo, están asociados
    a estaciones vía relaciones stop_area. Esta función:
    1. Toma las stop_areas ya extraídas
    2. Para cada una, expande sus miembros
    3. Filtra los elementos que son plataformas/andenes
    4. Asigna el nombre de la estación desde la stop_area
    """
    print("Extrayendo andenes vía stop_areas (técnica de mapeo)...")

    andenes = []
    seen_ids = set()

    for sa in stop_areas:
        # Filtrar solo TMB
        if "TMB" not in sa.operator and "Transports Metropolitans" not in sa.operator:
            continue

        # Expandir miembros de la stop_area
        query = f"""
        [out:json][timeout:{TIMEOUT}];
        relation({sa.osm_id});
        (._;>;);
        out body center;
        """

        result = query_overpass(query)

        # Filtrar plataformas
        for element in result.get("elements", []):
            if element["id"] in seen_ids:
                continue

            tags = element.get("tags", {})

            # Solo plataformas
            is_platform = (
                tags.get("railway") == "platform" or
                tags.get("public_transport") == "platform"
            )
            if not is_platform:
                continue

            seen_ids.add(element["id"])
            lat, lon = get_center(element)

            if lat and lon:
                # Extraer línea del nombre de stop_area (ej: "La Sagrera (L1)" -> "L1")
                line = "?"
                if "(" in sa.name and ")" in sa.name:
                    line = sa.name.split("(")[-1].replace(")", "").strip()

                # Nombre de estación sin la línea
                station_name = sa.name.split("(")[0].strip() if "(" in sa.name else sa.name

                andenes.append(Anden(
                    osm_id=element["id"],
                    osm_type=element["type"],
                    name=tags.get("name", tags.get("ref", "Sin nombre")),
                    lat=lat,
                    lon=lon,
                    station_name=station_name,
                    line=line,
                    ref=tags.get("ref", "?"),
                    tags=tags
                ))

    print(f"  Encontrados: {len(andenes)} andenes de TMB")
    return andenes


def extract_stop_areas() -> List[StopArea]:
    """Extrae relaciones stop_area de TMB."""
    print("Extrayendo stop_areas TMB Metro...")

    query = f"""
    [out:json][timeout:{TIMEOUT}];
    (
      relation["public_transport"="stop_area"]["operator"~"TMB|Transports Metropolitans",i]({BBOX});
      relation["public_transport"="stop_area"]["network"~"Metro de Barcelona|TMB",i]({BBOX});
    );
    out body;
    """

    result = query_overpass(query)
    stop_areas = []

    for element in result.get("elements", []):
        tags = element.get("tags", {})
        members = element.get("members", [])

        stop_areas.append(StopArea(
            osm_id=element["id"],
            name=tags.get("name", "Sin nombre"),
            operator=tags.get("operator", "?"),
            network=tags.get("network", "?"),
            members_count=len(members),
            members=[
                {"type": m["type"], "ref": m["ref"], "role": m.get("role", "")}
                for m in members
            ]
        ))

    print(f"  Encontradas: {len(stop_areas)}")
    return stop_areas


def extract_stop_area_groups() -> List[Dict]:
    """Extrae intercambiadores (stop_area_group)."""
    print("Extrayendo stop_area_groups (intercambiadores)...")

    query = f"""
    [out:json][timeout:{TIMEOUT}];
    area["name"="Barcelona"]->.city;
    (
      relation["public_transport"="stop_area_group"](area.city);
    );
    out body;
    """

    result = query_overpass(query)
    groups = []

    for element in result.get("elements", []):
        tags = element.get("tags", {})
        members = element.get("members", [])

        groups.append({
            "osm_id": element["id"],
            "name": tags.get("name", "Sin nombre"),
            "members_count": len(members),
            "members": [
                {"type": m["type"], "ref": m["ref"], "role": m.get("role", "")}
                for m in members
            ],
            "tags": tags
        })

    print(f"  Encontrados: {len(groups)}")
    return groups


def extract_metro_stations() -> List[Dict]:
    """Extrae estaciones de metro (nodos station=subway)."""
    print("Extrayendo estaciones de metro...")

    query = f"""
    [out:json][timeout:{TIMEOUT}];
    (
      node["station"="subway"]({BBOX});
      node["railway"="station"]["subway"="yes"]({BBOX});
    );
    out body;
    """

    result = query_overpass(query)
    stations = []
    seen_ids = set()

    for element in result.get("elements", []):
        if element["id"] in seen_ids:
            continue
        seen_ids.add(element["id"])

        tags = element.get("tags", {})
        lat, lon = get_center(element)

        stations.append({
            "osm_id": element["id"],
            "name": tags.get("name", "?"),
            "operator": tags.get("operator", tags.get("network", "?")),
            "line": tags.get("line", tags.get("ref", "?")),
            "lat": lat,
            "lon": lon,
            "wikidata": tags.get("wikidata"),
            "tags": tags
        })

    print(f"  Encontradas: {len(stations)}")
    return stations


def extract_key_interchanges() -> List[Dict]:
    """Extrae estaciones clave de intercambio multimodal."""
    print("Extrayendo intercambiadores clave...")

    # Estaciones con correspondencias importantes entre líneas TMB
    key_names = [
        "Passeig de Gràcia",
        "Diagonal",
        "Catalunya",
        "Espanya",
        "Sants Estació",
        "Sagrada Família",
        "Universitat",
        "Arc de Triomf",
        "Clot",
        "Torrassa",
        "Trinitat Nova",
        "La Pau",
        "Paral·lel"
    ]

    query = f"""
    [out:json][timeout:{TIMEOUT}];
    (
      node["station"="subway"]["name"~"{'|'.join(key_names)}",i]({BBOX});
      relation["public_transport"="stop_area"]["name"~"{'|'.join(key_names)}",i]({BBOX});
    );
    out body center;
    """

    result = query_overpass(query)
    interchanges = []

    for element in result.get("elements", []):
        tags = element.get("tags", {})
        lat, lon = get_center(element)

        interchanges.append({
            "osm_id": element["id"],
            "osm_type": element["type"],
            "name": tags.get("name", "?"),
            "operator": tags.get("operator", tags.get("network", "?")),
            "lines": tags.get("line", "?"),
            "lat": lat,
            "lon": lon,
            "tags": tags
        })

    print(f"  Encontrados: {len(interchanges)}")
    return interchanges


def find_discrepancias(accesos: List, andenes: List, stop_areas: List) -> List[Discrepancia]:
    """Identifica discrepancias y datos incompletos."""
    discrepancias = []

    # Andenes sin estación asociada
    for anden in andenes:
        if anden.station_name == "?":
            discrepancias.append(Discrepancia(
                tipo="anden_sin_estacion",
                descripcion=f"Andén {anden.osm_id} ({anden.name}) sin estación asociada",
                osm_id=anden.osm_id
            ))

    # Accesos sin información
    for acceso in accesos:
        if acceso.name == "Sin nombre" and acceso.station_name == "?":
            discrepancias.append(Discrepancia(
                tipo="acceso_sin_info",
                descripcion=f"Acceso {acceso.osm_id} sin nombre ni estación",
                osm_id=acceso.osm_id
            ))

    # stop_areas sin operador
    for sa in stop_areas:
        if sa.operator == "?":
            discrepancias.append(Discrepancia(
                tipo="stop_area_sin_operador",
                descripcion=f"stop_area '{sa.name}' sin operador definido",
                osm_id=sa.osm_id
            ))

    return discrepancias


def group_by_station(andenes: List[Anden]) -> Dict[str, List]:
    """Agrupa andenes por nombre de estación."""
    by_station = {}
    for anden in andenes:
        station = anden.station_name
        if station not in by_station:
            by_station[station] = []
        by_station[station].append(asdict(anden))
    return by_station


def main():
    parser = argparse.ArgumentParser(description="Extrae datos TMB Metro de OSM")
    parser.add_argument("--output", "-o", default="tmb_data.json", help="Archivo de salida")
    args = parser.parse_args()

    print("=" * 60)
    print("TMB Metro Barcelona - Extracción de datos OSM")
    print("=" * 60)
    print(f"Fecha: {datetime.now().isoformat()}")
    print(f"BBOX: {BBOX}")
    print()

    # Extraer datos base
    stop_areas = extract_stop_areas()
    stop_area_groups = extract_stop_area_groups()
    metro_stations = extract_metro_stations()
    key_interchanges = extract_key_interchanges()

    # Extraer accesos y andenes vía stop_areas (técnica de mapeo OSM)
    accesos = extract_accesos_via_stop_areas(stop_areas)
    andenes = extract_andenes_via_stop_areas(stop_areas)

    # Encontrar discrepancias
    discrepancias = find_discrepancias(accesos, andenes, stop_areas)

    # Agrupar andenes por estación
    andenes_by_station = group_by_station(andenes)

    # Preparar resultado
    data = {
        "fecha_extraccion": datetime.now().isoformat(),
        "bbox": BBOX,
        "resumen": {
            "accesos": len(accesos),
            "andenes": len(andenes),
            "estaciones_con_andenes": len(andenes_by_station),
            "stop_areas": len(stop_areas),
            "stop_area_groups": len(stop_area_groups),
            "metro_stations": len(metro_stations),
            "intercambiadores_clave": len(key_interchanges),
            "discrepancias": len(discrepancias)
        },
        "accesos": [asdict(a) for a in accesos],
        "andenes": [asdict(a) for a in andenes],
        "andenes_por_estacion": andenes_by_station,
        "stop_areas": [asdict(sa) for sa in stop_areas],
        "stop_area_groups": stop_area_groups,
        "metro_stations": metro_stations,
        "intercambiadores_clave": key_interchanges,
        "discrepancias": [asdict(d) for d in discrepancias]
    }

    # Guardar JSON
    output_path = args.output
    if not output_path.startswith("/"):
        output_path = os.path.join(os.path.dirname(__file__), output_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Resumen
    print()
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"  Accesos:                {len(accesos)}")
    print(f"  Andenes:                {len(andenes)}")
    print(f"  Estaciones con andenes: {len(andenes_by_station)}")
    print(f"  stop_area:              {len(stop_areas)}")
    print(f"  stop_area_group:        {len(stop_area_groups)}")
    print(f"  Metro stations:         {len(metro_stations)}")
    print(f"  Intercambiadores clave: {len(key_interchanges)}")
    print(f"  Discrepancias:          {len(discrepancias)}")
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

    # Andenes por estación (muestra)
    print()
    print("ANDENES POR ESTACIÓN (muestra):")
    print("-" * 40)
    for station, station_andenes in list(andenes_by_station.items())[:10]:
        print(f"  {station}: {len(station_andenes)} andenes")
    if len(andenes_by_station) > 10:
        print(f"  ... y {len(andenes_by_station) - 10} estaciones más")

    # Intercambiadores clave
    if key_interchanges:
        print()
        print("INTERCAMBIADORES CLAVE:")
        print("-" * 40)
        for ic in key_interchanges[:10]:
            lines = ic.get("lines", "?")
            print(f"  {ic['name']}: {lines}")


if __name__ == "__main__":
    main()
