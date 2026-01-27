# Route Planner API

## Resumen

Endpoint de planificación de rutas que encuentra el camino óptimo entre dos paradas usando el algoritmo de Dijkstra sobre un grafo de transporte público.

**Endpoint:** `GET /api/v1/gtfs/route-planner`

**Fecha de implementación:** 2026-01-27

---

## Parámetros

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `from` | string | Sí | - | ID de la parada origen |
| `to` | string | Sí | - | ID de la parada destino |
| `max_transfers` | int | No | 3 | Máximo de transbordos (0-5) |
| `max_gap` | float | No | 50 | Gap máximo en metros para normalización de shapes (10-500). `null` para desactivar |

---

## Ejemplo de Request

```bash
curl "https://redcercanias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004"
```

---

## Ejemplo de Response

```json
{
  "success": true,
  "message": null,
  "journey": {
    "origin": {
      "id": "METRO_SEV_L1_E21",
      "name": "Olivar de Quintos",
      "lat": 37.329216,
      "lon": -5.933652
    },
    "destination": {
      "id": "RENFE_43004",
      "name": "Cartuja",
      "lat": 37.409123,
      "lon": -5.998456
    },
    "total_duration_minutes": 45,
    "total_walking_minutes": 3,
    "total_transit_minutes": 42,
    "transfer_count": 2,
    "segments": [
      {
        "type": "transit",
        "transport_mode": "metro",
        "line_id": "METRO_SEV_L1_CE_OQ",
        "line_name": "L1",
        "line_color": "ED1C24",
        "headsign": "Ciudad Expo",
        "origin": {
          "id": "METRO_SEV_L1_E21",
          "name": "Olivar de Quintos",
          "lat": 37.329216,
          "lon": -5.933652
        },
        "destination": {
          "id": "METRO_SEV_L1_E10",
          "name": "San Bernardo",
          "lat": 37.380123,
          "lon": -5.978456
        },
        "intermediate_stops": [
          {"id": "METRO_SEV_L1_E20", "name": "Montequinto", "lat": 37.332, "lon": -5.936},
          {"id": "METRO_SEV_L1_E19", "name": "La Raza", "lat": 37.338, "lon": -5.940}
        ],
        "duration_minutes": 25,
        "distance_meters": null,
        "coordinates": [
          {"lat": 37.329216, "lon": -5.933652},
          {"lat": 37.329300, "lon": -5.933700},
          ...
        ]
      },
      {
        "type": "walking",
        "transport_mode": "walking",
        "line_id": null,
        "line_name": null,
        "line_color": null,
        "headsign": null,
        "origin": {
          "id": "METRO_SEV_L1_E10",
          "name": "San Bernardo",
          "lat": 37.380123,
          "lon": -5.978456
        },
        "destination": {
          "id": "RENFE_43002",
          "name": "San Bernardo",
          "lat": 37.380456,
          "lon": -5.978789
        },
        "intermediate_stops": [],
        "duration_minutes": 3,
        "distance_meters": 200,
        "coordinates": [
          {"lat": 37.380123, "lon": -5.978456},
          {"lat": 37.380150, "lon": -5.978500},
          ...
        ]
      },
      {
        "type": "transit",
        "transport_mode": "cercanias",
        "line_id": "RENFE_C5",
        "line_name": "C5",
        "line_color": "78B4E1",
        "headsign": "Cartuja",
        "origin": {...},
        "destination": {...},
        "intermediate_stops": [...],
        "duration_minutes": 17,
        "distance_meters": null,
        "coordinates": [...]
      }
    ]
  },
  "alternatives": []
}
```

---

## Arquitectura

### Algoritmo: Dijkstra

El servicio construye un grafo donde:
- **Nodos** = `(stop_id, route_id)` - Estar en una parada, opcionalmente en una línea
- **Aristas** = Conexiones con coste en tiempo

### Tipos de Aristas

| Tipo | Descripción | Coste |
|------|-------------|-------|
| `transit` | Viajar en una línea | Tiempo estimado según velocidad comercial |
| `transfer_same_station` | Cambiar de línea en misma estación | 3 minutos (penalización) |
| `transfer_walking` | Caminar a otra estación | Tiempo de caminata + 3 min penalización |
| `board` | Subir a una línea | 2 minutos (espera promedio) |

### Velocidades Comerciales

| Tipo de Transporte | Velocidad | route_type GTFS |
|--------------------|-----------|-----------------|
| Metro | 30 km/h | 1 |
| Cercanías | 45 km/h | 2 |
| Tranvía | 18 km/h | 0 |
| Andando | 4.5 km/h | - |

---

## Archivos del Sistema

```
src/gtfs_bc/routing/
├── __init__.py                 # Exports RoutingService
└── routing_service.py          # Algoritmo Dijkstra (~400 líneas)

adapters/http/api/gtfs/
├── schemas/
│   └── routing_schemas.py      # Pydantic models para request/response
└── routers/
    └── query_router.py         # Endpoint /route-planner (líneas 1772-2033)
```

---

## Tablas de Base de Datos Utilizadas

| Tabla | Uso |
|-------|-----|
| `gtfs_stops` | Información de paradas (coordenadas, nombre) |
| `gtfs_routes` | Información de líneas (color, nombre, tipo) |
| `gtfs_stop_route_sequence` | Qué paradas tiene cada ruta y en qué orden |
| `stop_correspondence` | Transbordos a pie entre estaciones |
| `gtfs_shape_points` | Geometría de las rutas para dibujar en mapa |
| `gtfs_trips` | Para obtener el shape_id de una ruta |

---

## Normalización de Shapes

Las coordenadas de cada segmento se normalizan usando interpolación esférica (SLERP) para garantizar:
- Gaps máximos de 50 metros entre puntos (configurable)
- Animaciones 3D suaves en la app
- Sin saltos visuales en curvas

El parámetro `max_gap` controla este comportamiento:
- `max_gap=50` → Puntos cada 50m máximo (default)
- `max_gap=null` → Sin normalización, puntos originales

---

## Casos de Error

| Caso | Response |
|------|----------|
| Parada origen no existe | `{"success": false, "message": "Origin stop not found: XXX"}` |
| Parada destino no existe | `{"success": false, "message": "Destination stop not found: XXX"}` |
| No hay ruta posible | `{"success": false, "message": "No route found from A to B..."}` |

---

## Limitaciones Actuales

1. **Sin horarios reales**: Los tiempos son estimaciones basadas en velocidad comercial, no en horarios GTFS
2. **Sin tiempo real**: No considera retrasos de GTFS-RT
3. **Sin alternativas**: Solo devuelve la mejor ruta, no alternativas
4. **Direccionalidad**: Asume que todas las líneas son bidireccionales

---

## Mejoras Futuras

- [ ] Usar `stop_times` para tiempos reales de viaje
- [ ] Considerar horarios (no buscar rutas de noche si no hay servicio)
- [ ] Devolver rutas alternativas en `alternatives[]`
- [ ] Integrar retrasos de GTFS-RT
- [ ] Añadir `departure_time` para buscar próxima salida
