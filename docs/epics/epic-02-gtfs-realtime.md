# Epic 02: Integración GTFS Realtime

## Estado: ✅ Completada

## Objetivo
Integrar los datos en tiempo real de GTFS-RT para obtener la posición actual de los trenes y las actualizaciones de horarios.

## Fuentes de Datos

### Renfe (JSON)
- https://gtfsrt.renfe.com/vehicle_positions.json
- https://gtfsrt.renfe.com/trip_updates.json
- https://gtfsrt.renfe.com/alerts.json
- **Formato: JSON** (no Protobuf)

### Otros Operadores
| Operador | Formato | URLs |
|----------|---------|------|
| Metro Bilbao | Protobuf | opendata.euskadi.eus |
| Euskotren | Protobuf | opendata.euskadi.eus |
| FGC | JSON/Protobuf | dadesobertes.fgc.cat |
| TMB Metro | API iMetro | api.tmb.cat |

## User Stories

### US-02.1: Conexión al feed GTFS-RT ✅
**Como** sistema
**Quiero** conectarme al feed GTFS-RT de Renfe
**Para** obtener datos en tiempo real

**Criterios de aceptación:**
- ✅ Conexión al endpoint de Renfe
- ✅ Parseo de JSON (Renfe usa JSON, no Protobuf)
- ✅ Parseo de Protobuf (para Metro Bilbao, Euskotren, FGC)
- ✅ Manejo de errores de conexión
- ✅ Reconexión automática (scheduler cada 30s)

### US-02.2: Procesamiento de Vehicle Positions
**Como** sistema
**Quiero** procesar las posiciones de vehículos
**Para** saber dónde está cada tren

**Datos a procesar:**
- vehicle_id
- trip_id
- route_id
- latitude, longitude
- current_stop_sequence
- current_status (INCOMING_AT, STOPPED_AT, IN_TRANSIT_TO)
- timestamp

### US-02.3: Procesamiento de Trip Updates
**Como** sistema
**Quiero** procesar las actualizaciones de viajes
**Para** conocer retrasos y cancelaciones

**Datos a procesar:**
- trip_id
- route_id
- stop_time_updates (arrival/departure delays)
- schedule_relationship (SCHEDULED, CANCELED, ADDED)

### US-02.4: Procesamiento de Service Alerts
**Como** sistema
**Quiero** procesar las alertas de servicio
**Para** informar de incidencias

**Datos a procesar:**
- alert_id
- affected_entities (routes, stops, trips)
- cause
- effect
- header_text
- description_text
- active_period

### US-02.5: Almacenamiento de posiciones históricas
**Como** sistema
**Quiero** almacenar el historial de posiciones
**Para** calcular tiempos estimados de llegada

**Criterios de aceptación:**
- Guardar cada posición con timestamp
- Retención configurable (ej: 7 días)
- Índices para consultas eficientes

### US-02.6: Polling periódico
**Como** sistema
**Quiero** consultar el feed cada X segundos
**Para** mantener datos actualizados

**Criterios de aceptación:**
- Intervalo configurable (default: 30 segundos)
- Worker en background (Celery)
- Métricas de latencia

## Modelo de Datos

```
VehiclePosition (
    id,
    vehicle_id,
    trip_id,
    route_id,
    latitude,
    longitude,
    bearing,
    speed,
    current_stop_id,
    current_status,
    timestamp,
    created_at
)

TripUpdate (
    id,
    trip_id,
    route_id,
    schedule_relationship,
    timestamp,
    stop_time_updates[]
)

StopTimeUpdate (
    trip_update_id,
    stop_id,
    stop_sequence,
    arrival_delay,
    departure_delay,
    schedule_relationship
)

ServiceAlert (
    id,
    cause,
    effect,
    header_text,
    description_text,
    url,
    active_period_start,
    active_period_end,
    affected_routes[],
    affected_stops[],
    created_at
)
```

## Tareas Técnicas
1. ✅ Instalar dependencia gtfs-realtime-bindings
2. ✅ Crear cliente HTTP para feed GTFS-RT
3. ✅ Implementar parser de JSON (Renfe) y Protobuf (otros)
4. ✅ Crear modelos para datos en tiempo real
5. ✅ Implementar scheduler AsyncIO (alternativa a Celery)
6. ✅ Crear repositorio de posiciones históricas
7. ⏳ Implementar limpieza de datos antiguos
8. ✅ Añadir métricas y logging

---

## Implementación Actual

### Scheduler Automático
- **Sistema**: AsyncIO nativo integrado con FastAPI lifespan
- **Intervalo**: 30 segundos
- **Archivo**: `src/gtfs_bc/realtime/infrastructure/services/gtfs_rt_scheduler.py`

### Archivos Principales
| Archivo | Propósito |
|---------|-----------|
| `gtfs_rt_fetcher.py` | Fetcher principal de Renfe (JSON) |
| `multi_operator_fetcher.py` | Fetcher multi-operador (Protobuf, JSON, API) |
| `gtfs_rt_scheduler.py` | Scheduler AsyncIO + lifespan |

### Endpoints API
- `POST /api/v1/gtfs/realtime/fetch` - Fetch manual
- `GET /api/v1/gtfs/realtime/vehicles` - Posiciones
- `GET /api/v1/gtfs/realtime/delays` - Retrasos
- `GET /api/v1/gtfs/realtime/alerts` - Alertas
- `GET /api/v1/gtfs/realtime/scheduler/status` - Estado del scheduler

### Documentación Completa
Ver `GTFS_REALTIME.md` en la raíz del proyecto.
