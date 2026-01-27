# Instrucciones de Migración para App iOS

## Resumen de Cambios en la API

Se han implementado dos nuevas funcionalidades en el servidor que permiten eliminar código de la app:

1. **Normalización de Shapes** (ya desplegado)
2. **Route Planner** (pendiente de desplegar)

---

## 1. Normalización de Shapes

### Cambio en la API

**Endpoint:** `GET /api/v1/gtfs/routes/{route_id}/shape`

**Nuevo parámetro:** `max_gap` (float, 10-500 metros)

Cuando se especifica, el servidor interpola puntos usando SLERP para que no haya gaps mayores al valor indicado.

### Ejemplo

```
# Sin normalizar
GET /routes/METRO_SEV_L1_CE_OQ/shape
→ 590 puntos

# Normalizado con gaps máximos de 50m
GET /routes/METRO_SEV_L1_CE_OQ/shape?max_gap=50
→ 747 puntos
```

### Cambios en la App

**Antes:**
```swift
let rawShape = await dataService.fetchRouteShape(routeId: routeId)
let normalizedCoords = AnimationController.normalizeRoute(rawShape, maxSegmentMeters: 50.0)
mapView.addPolyline(normalizedCoords)
```

**Después:**
```swift
let shape = await dataService.fetchRouteShape(routeId: routeId, maxGap: 50)
mapView.addPolyline(shape)  // Ya viene normalizado
```

### Código a Eliminar

- `AnimationController.normalizeRoute()`
- `AnimationController.sphericalInterpolate()`
- Cualquier función de interpolación SLERP local

---

## 2. Route Planner (NUEVO)

### Endpoint

```
GET /api/v1/gtfs/route-planner?from=STOP_ID&to=STOP_ID
```

### Parámetros

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `from` | string | requerido | ID parada origen |
| `to` | string | requerido | ID parada destino |
| `max_transfers` | int | 3 | Máximo transbordos (0-5) |
| `max_gap` | float | 50 | Gap máximo para shapes |

### Response

```json
{
  "success": true,
  "journey": {
    "origin": {"id": "...", "name": "Olivar de Quintos", "lat": 37.329, "lon": -5.933},
    "destination": {"id": "...", "name": "Cartuja", "lat": 37.409, "lon": -5.998},
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
        "origin": {"id": "...", "name": "...", "lat": ..., "lon": ...},
        "destination": {"id": "...", "name": "...", "lat": ..., "lon": ...},
        "intermediate_stops": [...],
        "duration_minutes": 25,
        "coordinates": [{"lat": 37.329, "lon": -5.933}, ...]
      },
      {
        "type": "walking",
        "transport_mode": "walking",
        "origin": {...},
        "destination": {...},
        "duration_minutes": 3,
        "distance_meters": 200,
        "coordinates": [...]
      },
      ...
    ]
  }
}
```

### Cambios en la App

**Antes (RoutingService.swift):**
```swift
// Construir grafo
let graph = buildGraph()

// Dijkstra
let path = dijkstra(from: originNode, to: destinationNodes)

// Construir segmentos
let segments = buildSegments(from: path)

// Extraer shapes
for segment in segments {
    segment.coordinates = extractShapeSegment(...)
    segment.coordinates = normalizeRoute(segment.coordinates)
}
```

**Después:**
```swift
// Una sola llamada
let response = await api.planRoute(from: originId, to: destinationId)

if response.success {
    let journey = response.journey
    // Usar journey.segments directamente
    // Las coordenadas ya vienen normalizadas
}
```

### Código a Eliminar (~600 líneas)

- `RoutingService.swift` completo
- `TransitNode`, `TransitEdge`, `EdgeType` en Journey.swift
- `buildGraph()`
- `dijkstra()`
- `buildSegments()`
- `extractShapeSegment()`
- Todas las llamadas a `fetchCorrespondences()` para construir el grafo

### Modelo Swift Sugerido

```swift
struct RoutePlannerResponse: Codable {
    let success: Bool
    let message: String?
    let journey: Journey?
}

struct Journey: Codable {
    let origin: JourneyStop
    let destination: JourneyStop
    let totalDurationMinutes: Int
    let totalWalkingMinutes: Int
    let totalTransitMinutes: Int
    let transferCount: Int
    let segments: [JourneySegment]
}

struct JourneyStop: Codable {
    let id: String
    let name: String
    let lat: Double
    let lon: Double
}

struct JourneySegment: Codable {
    let type: String  // "transit" or "walking"
    let transportMode: String
    let lineId: String?
    let lineName: String?
    let lineColor: String?
    let headsign: String?
    let origin: JourneyStop
    let destination: JourneyStop
    let intermediateStops: [JourneyStop]
    let durationMinutes: Int
    let distanceMeters: Int?
    let coordinates: [Coordinate]
}

struct Coordinate: Codable {
    let lat: Double
    let lon: Double
}
```

---

## 3. Resumen de Cambios

| Funcionalidad | Antes (App) | Después (API) | Líneas eliminadas |
|---------------|-------------|---------------|-------------------|
| Normalización SLERP | `normalizeRoute()` | `?max_gap=50` | ~50 |
| Route Planning | `RoutingService.swift` | `/route-planner` | ~530 |
| **Total** | | | **~580 líneas** |

---

## 4. Orden de Migración Sugerido

1. **Primero**: Migrar normalización de shapes (cambio pequeño, bajo riesgo)
   - Añadir `maxGap` a `fetchRouteShape()`
   - Eliminar código de normalización local
   - Probar animaciones 3D

2. **Segundo**: Migrar route planner (cambio grande)
   - Crear nuevos modelos Swift
   - Crear función `planRoute()` en DataService
   - Reemplazar uso de RoutingService
   - Eliminar RoutingService.swift

---

## 5. Testing

### Endpoints para probar:

```bash
# Shape normalizado
curl "https://redcercanias.com/api/v1/gtfs/routes/METRO_SEV_L1_CE_OQ/shape?max_gap=50"

# Route planner (después del deploy)
curl "https://redcercanias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004"
```

---

## 6. Contacto

Si hay dudas sobre la estructura de la response o necesitas campos adicionales, coordinar antes del desarrollo para añadirlos a la API.
