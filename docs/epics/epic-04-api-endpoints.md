# Epic 04: API REST Pública

## Objetivo
Exponer una API REST para que los clientes (web, móvil) puedan consultar información de líneas, estaciones, horarios y tiempos estimados.

## User Stories

### US-04.1: Listar líneas/rutas
**Como** usuario
**Quiero** ver las líneas disponibles
**Para** saber qué opciones de transporte tengo

**Endpoint:** `GET /api/v1/routes`

**Response:**
```json
{
  "routes": [
    {
      "id": "C1",
      "short_name": "C1",
      "long_name": "Lora del Río - Sevilla - Lebrija",
      "color": "#FF6600",
      "text_color": "#FFFFFF",
      "type": "rail"
    }
  ]
}
```

### US-04.2: Detalle de línea
**Como** usuario
**Quiero** ver el detalle de una línea
**Para** conocer sus paradas y recorrido

**Endpoint:** `GET /api/v1/routes/{route_id}`

**Response:**
```json
{
  "id": "C1",
  "short_name": "C1",
  "long_name": "...",
  "stops": [
    {"id": "...", "name": "Lora del Río", "sequence": 1},
    {"id": "...", "name": "Sevilla Santa Justa", "sequence": 5}
  ],
  "shape": [[lat, lon], ...]
}
```

### US-04.3: Listar estaciones
**Como** usuario
**Quiero** ver las estaciones disponibles
**Para** encontrar mi estación

**Endpoint:** `GET /api/v1/stops`

**Query params:**
- `lat`, `lon`, `radius`: Buscar cercanas
- `q`: Buscar por nombre
- `route_id`: Filtrar por línea

### US-04.4: Detalle de estación
**Como** usuario
**Quiero** ver el detalle de una estación
**Para** conocer sus líneas y próximas salidas

**Endpoint:** `GET /api/v1/stops/{stop_id}`

**Response:**
```json
{
  "id": "...",
  "name": "Sevilla Santa Justa",
  "lat": 37.391,
  "lon": -5.975,
  "routes": ["C1", "C2", "C3", "C4", "C5"],
  "next_departures": [...]
}
```

### US-04.5: Próximas salidas de una estación
**Como** usuario
**Quiero** ver las próximas salidas desde una estación
**Para** saber cuándo sale el próximo tren

**Endpoint:** `GET /api/v1/stops/{stop_id}/departures`

**Query params:**
- `route_id`: Filtrar por línea
- `limit`: Número de resultados (default: 10)

**Response:**
```json
{
  "departures": [
    {
      "trip_id": "...",
      "route_id": "C1",
      "headsign": "Lebrija",
      "scheduled_departure": "14:35:00",
      "estimated_departure": "14:37:00",
      "delay_minutes": 2,
      "status": "ON_TIME",
      "platform": "3"
    }
  ]
}
```

### US-04.6: Consultar ETA para un viaje
**Como** usuario
**Quiero** saber cuándo llegará el tren a mi estación
**Para** planificar mi viaje

**Endpoint:** `GET /api/v1/trips/{trip_id}/eta`

**Query params:**
- `stop_id`: Estación de destino

**Response:**
```json
{
  "trip_id": "...",
  "stop_id": "...",
  "stop_name": "Sevilla Santa Justa",
  "scheduled_arrival": "14:45:00",
  "estimated_arrival": "14:47:30",
  "delay_seconds": 150,
  "confidence": "HIGH",
  "vehicle_position": {
    "lat": 37.38,
    "lon": -5.95,
    "last_stop": "Virgen del Rocío",
    "next_stop": "Santa Justa"
  }
}
```

### US-04.7: Posición de trenes en tiempo real
**Como** usuario
**Quiero** ver dónde están los trenes ahora
**Para** seguir mi tren en el mapa

**Endpoint:** `GET /api/v1/vehicles`

**Query params:**
- `route_id`: Filtrar por línea
- `bounds`: Filtrar por área geográfica

**Response:**
```json
{
  "vehicles": [
    {
      "vehicle_id": "...",
      "trip_id": "...",
      "route_id": "C1",
      "lat": 37.39,
      "lon": -5.97,
      "bearing": 180,
      "speed_kmh": 45,
      "status": "IN_TRANSIT_TO",
      "next_stop": "Santa Justa",
      "updated_at": "2024-01-14T14:30:00Z"
    }
  ]
}
```

### US-04.8: Alertas de servicio
**Como** usuario
**Quiero** ver las alertas activas
**Para** estar informado de incidencias

**Endpoint:** `GET /api/v1/alerts`

**Query params:**
- `route_id`: Filtrar por línea
- `stop_id`: Filtrar por estación

**Response:**
```json
{
  "alerts": [
    {
      "id": "...",
      "cause": "MAINTENANCE",
      "effect": "REDUCED_SERVICE",
      "header": "Obras en vía",
      "description": "Frecuencia reducida...",
      "affected_routes": ["C1"],
      "active_until": "2024-01-20T23:59:59Z"
    }
  ]
}
```

## Tareas Técnicas
1. Crear routers para cada recurso
2. Implementar controladores
3. Crear DTOs/schemas de request/response
4. Implementar queries y handlers
5. Añadir validación de parámetros
6. Implementar paginación
7. Añadir cache (Redis) para respuestas frecuentes
8. Documentar con OpenAPI/Swagger
9. Añadir rate limiting
10. Crear tests de integración
