#!/usr/bin/env python3
"""
Extrae datos de OSM para Metro Sevilla y Tranvía Sevilla.
- Plataformas (andenes)
- Accesos (entradas)
- Coordenadas reales
"""

import requests
import json
import time

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Área de Sevilla metropolitana
SEVILLA_BBOX = "37.25,-6.25,37.45,-5.85"

def query_overpass(query: str) -> dict:
    """Execute Overpass query."""
    response = requests.post(OVERPASS_URL, data={"data": query}, timeout=60)
    response.raise_for_status()
    return response.json()


def extract_metro_sevilla():
    """Extract Metro Sevilla data from OSM."""
    print("=" * 60)
    print("METRO SEVILLA - OSM")
    print("=" * 60)

    # Query for Metro Sevilla stations and platforms
    query = f"""
    [out:json][timeout:60];
    (
      // Metro stations
      node["station"="subway"](37.25,-6.25,37.45,-5.85);
      node["railway"="station"]["subway"="yes"](37.25,-6.25,37.45,-5.85);

      // Metro platforms
      node["railway"="platform"]["subway"="yes"](37.25,-6.25,37.45,-5.85);
      way["railway"="platform"]["subway"="yes"](37.25,-6.25,37.45,-5.85);

      // Metro entrances
      node["railway"="subway_entrance"](37.25,-6.25,37.45,-5.85);
      node["entrance"]["subway"="yes"](37.25,-6.25,37.45,-5.85);

      // Light rail / Metro line
      relation["route"="subway"](37.25,-6.25,37.45,-5.85);
    );
    out body;
    >;
    out skel qt;
    """

    print("\nConsultando OSM...")
    data = query_overpass(query)

    stations = []
    platforms = []
    entrances = []

    for element in data.get("elements", []):
        tags = element.get("tags", {})

        if element["type"] == "node":
            lat = element.get("lat")
            lon = element.get("lon")
            name = tags.get("name", "")

            if tags.get("station") == "subway" or tags.get("subway") == "yes":
                stations.append({
                    "osm_id": element["id"],
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "tags": tags
                })
            elif tags.get("railway") == "platform":
                platforms.append({
                    "osm_id": element["id"],
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "tags": tags
                })
            elif tags.get("railway") == "subway_entrance" or tags.get("entrance"):
                entrances.append({
                    "osm_id": element["id"],
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "tags": tags
                })

    print(f"\n  Estaciones: {len(stations)}")
    for s in stations:
        print(f"    - {s['name']} ({s['lat']:.6f}, {s['lon']:.6f})")

    print(f"\n  Plataformas: {len(platforms)}")
    for p in platforms:
        print(f"    - {p['name']} ({p['lat']:.6f}, {p['lon']:.6f})")

    print(f"\n  Accesos: {len(entrances)}")
    for e in entrances:
        print(f"    - {e['name']} ({e['lat']:.6f}, {e['lon']:.6f})")

    return {
        "stations": stations,
        "platforms": platforms,
        "entrances": entrances
    }


def extract_tranvia_sevilla():
    """Extract Tranvía Sevilla (MetroCentro) data from OSM."""
    print("\n" + "=" * 60)
    print("TRANVÍA SEVILLA (METROCENTRO) - OSM")
    print("=" * 60)

    # Query for tram stops and platforms
    query = f"""
    [out:json][timeout:60];
    (
      // Tram stops with name containing Sevilla or in area
      node["railway"="tram_stop"](37.37,-6.01,37.40,-5.96);
      node["public_transport"="stop_position"]["tram"="yes"](37.37,-6.01,37.40,-5.96);

      // Tram platforms
      node["railway"="platform"]["tram"="yes"](37.37,-6.01,37.40,-5.96);
      way["railway"="platform"]["tram"="yes"](37.37,-6.01,37.40,-5.96);

      // MetroCentro relation
      relation["route"="tram"]["name"~"MetroCentro|T1"](37.25,-6.25,37.45,-5.85);
    );
    out body;
    >;
    out skel qt;
    """

    print("\nConsultando OSM...")
    data = query_overpass(query)

    stops = []
    platforms = []

    for element in data.get("elements", []):
        tags = element.get("tags", {})

        if element["type"] == "node":
            lat = element.get("lat")
            lon = element.get("lon")
            name = tags.get("name", "")

            if tags.get("railway") == "tram_stop" or tags.get("public_transport") == "stop_position":
                stops.append({
                    "osm_id": element["id"],
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "tags": tags
                })
            elif tags.get("railway") == "platform":
                platforms.append({
                    "osm_id": element["id"],
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "tags": tags
                })

    print(f"\n  Paradas: {len(stops)}")
    for s in stops:
        print(f"    - {s['name']} ({s['lat']:.6f}, {s['lon']:.6f})")

    print(f"\n  Plataformas: {len(platforms)}")
    for p in platforms:
        print(f"    - {p['name']} ({p['lat']:.6f}, {p['lon']:.6f})")

    return {
        "stops": stops,
        "platforms": platforms
    }


def extract_renfe_sevilla():
    """Extract RENFE Cercanías Sevilla stations from OSM."""
    print("\n" + "=" * 60)
    print("RENFE CERCANÍAS SEVILLA - OSM")
    print("=" * 60)

    # Query for train stations in Sevilla area
    query = f"""
    [out:json][timeout:60];
    (
      // Train stations
      node["railway"="station"](37.25,-6.25,37.45,-5.85);
      node["railway"="halt"](37.25,-6.25,37.45,-5.85);

      // Entrances
      node["railway"="station_entrance"](37.25,-6.25,37.45,-5.85);
    );
    out body;
    """

    print("\nConsultando OSM...")
    data = query_overpass(query)

    stations = []
    entrances = []

    for element in data.get("elements", []):
        tags = element.get("tags", {})

        if element["type"] == "node":
            lat = element.get("lat")
            lon = element.get("lon")
            name = tags.get("name", "")

            if tags.get("railway") in ["station", "halt"]:
                stations.append({
                    "osm_id": element["id"],
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "operator": tags.get("operator", ""),
                    "tags": tags
                })
            elif tags.get("railway") == "station_entrance":
                entrances.append({
                    "osm_id": element["id"],
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "tags": tags
                })

    print(f"\n  Estaciones: {len(stations)}")
    for s in sorted(stations, key=lambda x: x['name']):
        print(f"    - {s['name']} ({s['lat']:.6f}, {s['lon']:.6f}) [{s['operator']}]")

    return {
        "stations": stations,
        "entrances": entrances
    }


def main():
    print("=" * 60)
    print("EXTRACCIÓN OSM - SEVILLA")
    print("=" * 60)
    print(f"Fecha: {time.strftime('%Y-%m-%d %H:%M')}")

    metro_data = extract_metro_sevilla()
    time.sleep(2)  # Rate limiting

    tram_data = extract_tranvia_sevilla()
    time.sleep(2)

    renfe_data = extract_renfe_sevilla()

    # Save to JSON
    all_data = {
        "metro_sevilla": metro_data,
        "tranvia_sevilla": tram_data,
        "renfe_sevilla": renfe_data,
        "extracted_at": time.strftime('%Y-%m-%d %H:%M:%S')
    }

    output_file = "sevilla_osm_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print(f"\n\n{'=' * 60}")
    print(f"Datos guardados en: {output_file}")
    print("=" * 60)

    # Summary
    print("\nRESUMEN:")
    print(f"  Metro Sevilla:")
    print(f"    - Estaciones: {len(metro_data['stations'])}")
    print(f"    - Plataformas: {len(metro_data['platforms'])}")
    print(f"    - Accesos: {len(metro_data['entrances'])}")
    print(f"  Tranvía Sevilla:")
    print(f"    - Paradas: {len(tram_data['stops'])}")
    print(f"    - Plataformas: {len(tram_data['platforms'])}")
    print(f"  RENFE Sevilla:")
    print(f"    - Estaciones: {len(renfe_data['stations'])}")


if __name__ == "__main__":
    main()
