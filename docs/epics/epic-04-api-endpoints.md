# Epic 04: API REST Pública

## Estado: ✅ Completada

## Objetivo
Exponer una API REST para que los clientes (web, móvil) puedan consultar información de redes, líneas, estaciones, horarios y datos en tiempo real.

## Endpoints Implementados

### Redes de Transporte

#### Listar todas las redes
```
GET /api/v1/gtfs/networks
```
Devuelve las 31 redes de transporte con logo, color y número de rutas.

#### Detalle de red con líneas
```
GET /api/v1/gtfs/networks/{code}
```
Devuelve la red con todas sus líneas ordenadas por `sort_order`.

### Rutas/Líneas

#### Listar rutas
```
GET /api/v1/gtfs/routes
GET /api/v1/gtfs/routes?network_id=TMB_METRO
GET /api/v1/gtfs/routes?search=C1
```

#### Rutas por coordenadas
```
GET /api/v1/gtfs/coordinates/routes?lat=41.38&lon=2.17
```
Detecta la provincia por coordenadas y devuelve todas las rutas de las redes en esa provincia.

#### Paradas de una ruta
```
GET /api/v1/gtfs/routes/{route_id}/stops
```
Devuelve las paradas ordenadas por secuencia.

#### Frecuencias de una ruta
```
GET /api/v1/gtfs/routes/{route_id}/frequencies
```
Para rutas de Metro/ML con datos de frecuencia.

#### Horarios operativos
```
GET /api/v1/gtfs/routes/{route_id}/operating-hours
```

### Paradas/Estaciones

#### Buscar paradas
```
GET /api/v1/gtfs/stops?search=sol
GET /api/v1/gtfs/stops/by-network?network_id=TMB_METRO
```

#### Paradas cercanas
```
GET /api/v1/gtfs/stops/by-coordinates?lat=41.38&lon=2.17&radius_km=5
```
Por defecto solo devuelve paradas con GTFS-RT. Usar `transport_type=all` para todas.

#### Próximas salidas
```
GET /api/v1/gtfs/stops/{stop_id}/departures?limit=10
```

**Response:**
```json
{
  "trip_id": "...",
  "route_id": "RENFE_C1_01",
  "route_short_name": "C1",
  "route_color": "#FF6600",
  "headsign": "Lebrija",
  "departure_time": "14:35:00",
  "minutes_until": 5,
  "delay_seconds": 120,
  "realtime_departure_time": "14:37:00",
  "realtime_minutes_until": 7,
  "is_delayed": true,
  "platform": "3",
  "platform_estimated": false,
  "train_position": {
    "latitude": 37.39,
    "longitude": -5.97,
    "current_stop_name": "Virgen del Rocío",
    "status": "IN_TRANSIT_TO",
    "progress_percent": 65.0,
    "estimated": false
  },
  "frequency_based": false
}
```

### Tiempo Real (GTFS-RT)

#### Posiciones de vehículos
```
GET /api/v1/gtfs/realtime/vehicles
GET /api/v1/gtfs/realtime/vehicles?route_id=RENFE_C1_01
```

#### Retrasos
```
GET /api/v1/gtfs/realtime/delays
GET /api/v1/gtfs/realtime/stops/{stop_id}/delays
```

#### Alertas de servicio
```
GET /api/v1/gtfs/realtime/alerts
GET /api/v1/gtfs/realtime/routes/{route_id}/alerts
GET /api/v1/gtfs/realtime/stops/{stop_id}/alerts
```

#### Estado del scheduler
```
GET /api/v1/gtfs/realtime/scheduler/status
```

#### Fetch manual (admin)
```
POST /api/v1/gtfs/realtime/fetch
```

### Viajes

#### Detalle de viaje
```
GET /api/v1/gtfs/trips/{trip_id}
```
Devuelve todas las paradas del viaje con horarios.

## Características Implementadas

### Filtro de Horarios Operativos
Las redes con GTFS estático (Metro Madrid, ML, Tranvías) no muestran salidas fuera de su horario de servicio. Las redes con GTFS-RT (Renfe, TMB, FGC, Euskotren) no se filtran ya que los datos en tiempo real reflejan el servicio real.

### Estimación de Andén
Si no hay dato de andén en tiempo real, se estima usando el histórico (`gtfs_rt_platform_history`).

### Posición del Tren
- **GTFS-RT**: Posición real del vehículo
- **Estimada**: Calculada interpolando entre paradas según el horario

### Salidas Basadas en Frecuencia
Para Metro Madrid y ML que no tienen `stop_times`, se generan salidas estimadas basadas en los datos de `gtfs_route_frequencies`.

## Documentación OpenAPI

Disponible en: `https://redcercanias.com/docs`
