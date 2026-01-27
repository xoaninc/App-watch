# Instrucciones de Migración para App iOS

**Última actualización:** 2026-01-27
**Estado:** API COMPLETADA - App pendiente de migrar

---

## Resumen Ejecutivo

| Funcionalidad | Estado API | Estado App | Líneas a eliminar |
|---------------|------------|------------|-------------------|
| Normalización Shapes | ✅ Desplegado | ⏳ Pendiente | ~50 |
| Route Planner RAPTOR | ✅ Desplegado | ⏳ Pendiente | ~530 |
| Alternativas Pareto | ✅ Desplegado | ⏳ Pendiente | Nueva UI |
| Alertas de servicio | ✅ Desplegado | ⏳ Pendiente | Nueva UI |
| Widget/Siri compact | ⏳ Pendiente API | ⏳ Pendiente | Nueva feature |
| **Total código a eliminar** | | | **~580 líneas** |

---

## Fases de Migración

### FASE APP-1: Normalización de Shapes (~50 líneas)

**Riesgo:** Bajo
**Dependencias:** Ninguna

#### Estado API: ✅ COMPLETADO

**Endpoint:** `GET /api/v1/gtfs/routes/{route_id}/shape?max_gap=50`

El servidor interpola puntos usando SLERP para que no haya gaps mayores al valor indicado.

```bash
# Sin normalizar
GET /routes/METRO_SEV_L1_CE_OQ/shape
→ 590 puntos

# Normalizado con gaps máximos de 50m
GET /routes/METRO_SEV_L1_CE_OQ/shape?max_gap=50
→ 747 puntos
```

#### Tareas en la App:

- [ ] Añadir parámetro `maxGap` a `fetchRouteShape()`
- [ ] Eliminar `AnimationController.normalizeRoute()`
- [ ] Eliminar `AnimationController.sphericalInterpolate()`
- [ ] Probar animaciones 3D con shapes del servidor

#### Código a eliminar:

```swift
// ELIMINAR de AnimationController.swift
func normalizeRoute(_ coords: [Coordinate], maxSegmentMeters: Double) -> [Coordinate]
func sphericalInterpolate(from: Coordinate, to: Coordinate, fraction: Double) -> Coordinate
```

#### Antes vs Después:

```swift
// ANTES
let rawShape = await dataService.fetchRouteShape(routeId: routeId)
let normalizedCoords = AnimationController.normalizeRoute(rawShape, maxSegmentMeters: 50.0)
mapView.addPolyline(normalizedCoords)

// DESPUÉS
let shape = await dataService.fetchRouteShape(routeId: routeId, maxGap: 50)
mapView.addPolyline(shape)  // Ya viene normalizado
```

---

### FASE APP-2: Route Planner RAPTOR (~530 líneas)

**Riesgo:** Alto (cambio grande)
**Dependencias:** Ninguna

#### Estado API: ✅ COMPLETADO

**Endpoint:** `GET /api/v1/gtfs/route-planner`

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `from` | string | requerido | ID parada origen |
| `to` | string | requerido | ID parada destino |
| `departure_time` | string | hora actual | Formato HH:MM |
| `max_transfers` | int | 3 | Máximo transbordos (0-5) |
| `max_alternatives` | int | 3 | Máximo alternativas (1-5) |

#### Response actual (RAPTOR):

```json
{
  "success": true,
  "message": null,
  "journeys": [
    {
      "departure": "2026-01-28T08:32:00",
      "arrival": "2026-01-28T09:07:00",
      "duration_minutes": 35,
      "transfers": 2,
      "walking_minutes": 5,
      "segments": [
        {
          "type": "transit",
          "mode": "metro",
          "line_id": "METRO_SEV_L1_CE_OQ",
          "line_name": "L1",
          "line_color": "#0D6928",
          "headsign": "Ciudad Expo",
          "origin": {
            "id": "METRO_SEV_L1_E10",
            "name": "Nervión",
            "lat": 37.3891,
            "lon": -5.9723
          },
          "destination": {
            "id": "METRO_SEV_L1_E05",
            "name": "San Bernardo",
            "lat": 37.3801,
            "lon": -5.9784
          },
          "departure": "2026-01-28T08:32:00",
          "arrival": "2026-01-28T08:47:00",
          "duration_minutes": 15,
          "intermediate_stops": [
            {"id": "...", "name": "Gran Plaza", "lat": 37.385, "lon": -5.975}
          ],
          "distance_meters": null,
          "coordinates": [
            {"lat": 37.3891, "lon": -5.9723},
            {"lat": 37.3885, "lon": -5.9730}
          ],
          "suggested_heading": 225.0
        },
        {
          "type": "walking",
          "mode": "walking",
          "line_id": null,
          "line_name": null,
          "line_color": null,
          "headsign": null,
          "origin": {"id": "...", "name": "San Bernardo", "lat": 37.3801, "lon": -5.9784},
          "destination": {"id": "...", "name": "San Bernardo Cercanías", "lat": 37.3795, "lon": -5.9780},
          "departure": null,
          "arrival": null,
          "duration_minutes": 3,
          "intermediate_stops": [],
          "distance_meters": 200,
          "coordinates": [...],
          "suggested_heading": 180.0
        }
      ]
    },
    {
      "departure": "2026-01-28T08:40:00",
      "arrival": "2026-01-28T09:15:00",
      "duration_minutes": 35,
      "transfers": 1,
      "walking_minutes": 2,
      "segments": [...]
    }
  ],
  "alerts": [
    {
      "id": "alert_001",
      "line_id": "METRO_SEV_L1_CE_OQ",
      "line_name": "L1",
      "message": "Frecuencia reducida por obras",
      "severity": "warning"
    }
  ]
}
```

#### Tareas en la App:

- [ ] Crear nuevos modelos Swift (ver abajo)
- [ ] Crear función `planRoute()` en DataService
- [ ] Reemplazar todas las llamadas a RoutingService
- [ ] Eliminar `RoutingService.swift` completo

#### Código a eliminar:

```swift
// ELIMINAR archivos/funciones completos:
- RoutingService.swift
- TransitNode, TransitEdge, EdgeType en Journey.swift
- buildGraph()
- dijkstra()
- buildSegments()
- extractShapeSegment()
- Llamadas a fetchCorrespondences() para construir grafo
```

#### Modelos Swift actualizados:

```swift
// MARK: - Response principal
struct RoutePlannerResponse: Codable {
    let success: Bool
    let message: String?
    let journeys: [Journey]
    let alerts: [JourneyAlert]?
}

// MARK: - Journey (una alternativa de viaje)
struct Journey: Codable {
    let departure: String      // ISO8601 "2026-01-28T08:32:00"
    let arrival: String        // ISO8601
    let durationMinutes: Int
    let transfers: Int
    let walkingMinutes: Int
    let segments: [JourneySegment]

    enum CodingKeys: String, CodingKey {
        case departure, arrival, transfers, segments
        case durationMinutes = "duration_minutes"
        case walkingMinutes = "walking_minutes"
    }
}

// MARK: - Segment (tramo de viaje)
struct JourneySegment: Codable {
    let type: String           // "transit" | "walking"
    let mode: String           // "metro" | "cercanias" | "walking" | "tram"
    let lineId: String?
    let lineName: String?
    let lineColor: String?
    let headsign: String?
    let origin: JourneyStop
    let destination: JourneyStop
    let departure: String?     // ISO8601 (null para walking)
    let arrival: String?       // ISO8601 (null para walking)
    let durationMinutes: Int
    let intermediateStops: [JourneyStop]
    let distanceMeters: Int?   // Solo para walking
    let coordinates: [Coordinate]
    let suggestedHeading: Double?

    enum CodingKeys: String, CodingKey {
        case type, mode, headsign, origin, destination
        case departure, arrival, coordinates
        case lineId = "line_id"
        case lineName = "line_name"
        case lineColor = "line_color"
        case durationMinutes = "duration_minutes"
        case intermediateStops = "intermediate_stops"
        case distanceMeters = "distance_meters"
        case suggestedHeading = "suggested_heading"
    }
}

// MARK: - Stop
struct JourneyStop: Codable {
    let id: String
    let name: String
    let lat: Double
    let lon: Double
}

// MARK: - Coordinate
struct Coordinate: Codable {
    let lat: Double
    let lon: Double
}

// MARK: - Alert
struct JourneyAlert: Codable {
    let id: String
    let lineId: String?
    let lineName: String?
    let message: String
    let severity: String       // "info" | "warning" | "severe"

    enum CodingKeys: String, CodingKey {
        case id, message, severity
        case lineId = "line_id"
        case lineName = "line_name"
    }
}
```

#### Antes vs Después:

```swift
// ANTES (RoutingService.swift - Dijkstra local)
let graph = buildGraph()
let path = dijkstra(from: originNode, to: destinationNodes)
let segments = buildSegments(from: path)
for segment in segments {
    segment.coordinates = extractShapeSegment(...)
    segment.coordinates = normalizeRoute(segment.coordinates)
}

// DESPUÉS (una llamada a la API)
let response = await api.planRoute(
    from: originId,
    to: destinationId,
    departureTime: "08:30",
    maxAlternatives: 3
)
if response.success {
    let journeys = response.journeys  // Array de alternativas Pareto-óptimas
    // Usar journeys[0].segments directamente
    // Las coordenadas ya vienen normalizadas
}
```

---

### FASE APP-3: Nuevas Features UI

**Riesgo:** Medio
**Dependencias:** Fase App-2 completada

#### 3.1 Selector de Alternativas

RAPTOR devuelve 2-3 rutas Pareto-óptimas (la más rápida, la de menos transbordos, etc.)

- [ ] UI para mostrar lista de alternativas
- [ ] Mostrar duración, transbordos, hora llegada de cada una
- [ ] Permitir seleccionar una alternativa

#### 3.2 Heading en Animación 3D

El campo `suggested_heading` indica la dirección del segmento (0-360°).

- [ ] Usar `suggestedHeading` para orientar la cámara en la animación 3D
- [ ] Suavizar transiciones entre headings

#### 3.3 Mostrar Alertas de Servicio

El campo `alerts[]` contiene avisos que afectan al journey.

- [ ] UI para mostrar alertas al usuario
- [ ] Diferenciar por severidad: info, warning, severe
- [ ] Mostrar qué líneas están afectadas

---

### FASE APP-4: Widget y Siri

**Riesgo:** Bajo
**Dependencias:** API debe implementar `?compact=true` primero

#### Estado API: ⏳ PENDIENTE

**Endpoint futuro:** `GET /api/v1/gtfs/stops/{stop_id}/departures?compact=true&limit=3`

**Requisitos:**
- Response < 5KB (ideal ~500 bytes)
- Latencia < 500ms (para Siri timeout)

#### Tareas en la App (cuando API esté lista):

- [ ] Implementar Widget iOS con próximas salidas
- [ ] Implementar Siri shortcut para consultar

---

## Testing

### Endpoints funcionando ahora:

```bash
# Shape normalizado
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_SEV_L1_CE_OQ/shape?max_gap=50"

# Route planner RAPTOR
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004"

# Con hora de salida
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004&departure_time=08:30"

# Con múltiples alternativas
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004&max_alternatives=3"
```

---

## Orden de Migración Recomendado

| Orden | Fase | Riesgo | Dependencias |
|-------|------|--------|--------------|
| 1 | App-1: Shapes | Bajo | Ninguna |
| 2 | App-2: Route Planner | Alto | Ninguna |
| 3 | App-3: UI Features | Medio | App-2 |
| 4 | App-4: Widget/Siri | Bajo | API compact |

---

## Referencia

- Documento principal: `docs/RAPTOR_IMPLEMENTATION_PLAN.md`
- Algoritmo RAPTOR: `docs/archive/ROUTING_ALGORITHMS.md`
- Estado operadores: `docs/GTFS_OPERATORS_STATUS.md`
