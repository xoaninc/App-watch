# GTFS Realtime Implementation

## Overview

GTFS-RT (Realtime) provides live updates for transit data including vehicle positions, trip delays, and service alerts. This implementation fetches data from multiple operators and stores it in the database.

**Note:** Feeds may be empty during night hours when no trains are running.

## Scheduler Automático

El sistema incluye un **scheduler automático** que hace fetch cada **30 segundos** de todos los operadores configurados.

### Implementación

- **Sistema**: AsyncIO nativo integrado con FastAPI lifespan
- **Intervalo**: 30 segundos (`FETCH_INTERVAL = 30`)
- **Delay inicial**: 5 segundos (para que la app arranque completamente)
- **Archivo**: `src/gtfs_bc/realtime/infrastructure/services/gtfs_rt_scheduler.py`

### Activación

El scheduler se activa automáticamente al iniciar la aplicación FastAPI:

```python
# app.py
lifespan=lifespan_with_scheduler
```

### Endpoint de Estado

```
GET /api/v1/gtfs/realtime/scheduler/status
```

Respuesta:
```json
{
  "running": true,
  "last_fetch": "2026-01-18T10:15:30",
  "fetch_count": 12345,
  "error_count": 3,
  "interval_seconds": 30
}
```

### Sistema Alternativo (Celery)

También existe configuración para Celery Beat como alternativa:
- **Archivo**: `core/celery.py`
- **Cola**: `gtfs_realtime`
- **Intervalo**: 30 segundos

---

## Operadores Soportados

El sistema soporta **múltiples operadores** con **diferentes formatos de datos**:

| Operador | Formato | Tipo de Feed |
|----------|---------|--------------|
| **Renfe** | JSON | Vehicle Positions, Trip Updates, Alerts |
| **Metro Bilbao** | Protobuf | Vehicle Positions, Trip Updates, Alerts |
| **Euskotren** | Protobuf | Vehicle Positions, Trip Updates, Alerts |
| **FGC** | Protobuf/JSON | Vehicle Positions, Trip Updates, Alerts |
| **TMB Metro Barcelona** | API personalizada (iMetro) | Predicciones por estación |

---

## Data Sources

### Renfe (JSON)

| Feed | URL | Description |
|------|-----|-------------|
| Vehicle Positions | `https://gtfsrt.renfe.com/vehicle_positions.json` | Live train locations |
| Trip Updates | `https://gtfsrt.renfe.com/trip_updates.json` | Delays and schedule changes |
| Alerts | `https://gtfsrt.renfe.com/alerts.json` | Service disruptions and notices |

### Metro Bilbao (Protobuf)

| Feed | URL |
|------|-----|
| Vehicle Positions | `https://opendata.euskadi.eus/.../gtfsrt_metro_bilbao_vehicle_positions.pb` |
| Trip Updates | `https://opendata.euskadi.eus/.../gtfsrt_metro_bilbao_trip_updates.pb` |
| Alerts | `https://opendata.euskadi.eus/.../gtfsrt_metro_bilbao_alerts.pb` |

### Euskotren (Protobuf)

| Feed | URL |
|------|-----|
| Vehicle Positions | `https://opendata.euskadi.eus/.../gtfsrt_euskotren_vehicle_positions.pb` |
| Trip Updates | `https://opendata.euskadi.eus/.../gtfsrt_euskotren_trip_updates.pb` |
| Alerts | `https://opendata.euskadi.eus/.../gtfsrt_euskotren_alerts.pb` |

### FGC (JSON/Protobuf)

| Feed | URL |
|------|-----|
| Vehicle Positions | `https://dadesobertes.fgc.cat/.../vehicle-positions-gtfs_realtime/...` |
| Trip Updates | `https://dadesobertes.fgc.cat/.../trip-updates-gtfs_realtime/...` |
| Alerts | `https://dadesobertes.fgc.cat/.../alerts-gtfs_realtime/...` |

### TMB Metro Barcelona (API iMetro)

| Feed | URL |
|------|-----|
| Predicciones | `https://api.tmb.cat/v1/imetro/estacions` |

Requiere credenciales: `app_id` y `app_key`

## Database Tables

### GTFS-RT Tables (created in migration 002 and 014)

```sql
-- Vehicle positions (real-time train locations)
gtfs_rt_vehicle_positions
  - vehicle_id (PK)
  - trip_id
  - latitude, longitude
  - current_status (INCOMING_AT, STOPPED_AT, IN_TRANSIT_TO)
  - stop_id
  - timestamp

-- Trip updates (delays)
gtfs_rt_trip_updates
  - trip_id (PK)
  - delay (seconds)
  - vehicle_id
  - timestamp

-- Stop time updates (per-stop delays)
gtfs_rt_stop_time_updates
  - trip_id (FK)
  - stop_id
  - arrival_delay, departure_delay (seconds)
  - arrival_time, departure_time

-- Alerts (service disruptions)
gtfs_rt_alerts
  - alert_id (PK)
  - cause (MAINTENANCE, STRIKE, WEATHER, etc.)
  - effect (NO_SERVICE, REDUCED_SERVICE, SIGNIFICANT_DELAYS, etc.)
  - header_text, description_text
  - active_period_start, active_period_end

-- Alert entities (what's affected)
gtfs_rt_alert_entities
  - alert_id (FK)
  - route_id, stop_id, trip_id
```

## API Endpoints

### Fetch/Update Data

```
POST /api/v1/gtfs/realtime/fetch
```
Fetches all three GTFS-RT feeds and stores in database. Returns counts:
```json
{
  "vehicle_positions": 45,
  "trip_updates": 120,
  "alerts": 52,
  "message": "GTFS-RT data fetched and stored successfully"
}
```

### Vehicle Positions

```
GET /api/v1/gtfs/realtime/vehicles
GET /api/v1/gtfs/realtime/vehicles/{vehicle_id}
```
Query params: `stop_id`, `trip_id`

### Trip Delays

```
GET /api/v1/gtfs/realtime/delays
GET /api/v1/gtfs/realtime/stops/{stop_id}/delays
```
Query params: `min_delay`, `trip_id`

### Service Alerts

```
GET /api/v1/gtfs/realtime/alerts
GET /api/v1/gtfs/realtime/routes/{route_id}/alerts
GET /api/v1/gtfs/realtime/stops/{stop_id}/alerts
```
Query params: `route_id`, `stop_id`, `active_only`

### Departures (with integrated delays)

```
GET /api/v1/gtfs/stops/{stop_id}/departures
```
Returns scheduled departures with realtime delay information:
```json
{
  "trip_id": "6012V26500C3",
  "route_id": "RENFE_C3_28",
  "route_short_name": "C3",
  "departure_time": "05:00:00",
  "minutes_until": 48,
  "delay_seconds": 180,
  "realtime_departure_time": "05:03:00",
  "realtime_minutes_until": 51,
  "is_delayed": true
}
```

## Files Modified/Created

### New Files
- `src/gtfs_bc/realtime/domain/entities/alert.py` - Alert domain entity
- `src/gtfs_bc/realtime/infrastructure/models/alert.py` - Alert SQLAlchemy models
- `alembic/versions/014_create_gtfs_rt_alerts_tables.py` - Database migration

### Modified Files
- `src/gtfs_bc/realtime/infrastructure/services/gtfs_rt_fetcher.py` - Added alerts support
- `adapters/http/api/gtfs/routers/realtime_router.py` - Added alerts endpoints
- `adapters/http/api/gtfs/routers/query_router.py` - Integrated delays into /departures

## Usage

### Automático (Recomendado)

El scheduler integrado hace fetch automáticamente cada 30 segundos. No requiere configuración adicional.

### Manual Fetch
```bash
curl -X POST https://redcercanias.com/api/v1/gtfs/realtime/fetch
```

### Verificar Estado del Scheduler
```bash
curl https://redcercanias.com/api/v1/gtfs/realtime/scheduler/status
```

---

## Arquitectura de Fetchers

### Archivos Principales

| Archivo | Propósito |
|---------|-----------|
| `src/gtfs_bc/realtime/infrastructure/services/gtfs_rt_fetcher.py` | Fetcher principal de Renfe (JSON) |
| `src/gtfs_bc/realtime/infrastructure/services/multi_operator_fetcher.py` | Fetcher multi-operador (Protobuf, JSON, API) |
| `src/gtfs_bc/realtime/infrastructure/services/gtfs_rt_scheduler.py` | Scheduler AsyncIO + lifespan |

### Flujo de Ejecución

```
FastAPI Startup
    ↓
app.py lifespan_with_scheduler
    ↓
GTFSRTScheduler.start() [async]
    ↓
_fetch_loop() cada 30 segundos
    ↓
├─ GTFSRealtimeFetcher.fetch_all_sync() [Renfe]
│  ├─ fetch_and_store_vehicle_positions_sync()
│  ├─ fetch_and_store_trip_updates_sync()
│  └─ fetch_and_store_alerts_sync()
│
└─ MultiOperatorFetcher.fetch_all_operators_sync()
   ├─ Metro Bilbao (Protobuf)
   ├─ Euskotren (Protobuf)
   ├─ FGC (JSON/Protobuf)
   └─ TMB Metro (API iMetro)
```

### Parsers por Formato

- **JSON (Renfe)**: Métodos `from_gtfsrt_json()` en entidades de dominio
- **Protobuf**: Métodos `_parse_protobuf_*()` en `multi_operator_fetcher.py`
- **API TMB**: Método `_parse_tmb_predictions()` en `multi_operator_fetcher.py`

### Prefijos de IDs por Operador

| Operador | Prefijo |
|----------|---------|
| Renfe | `RENFE_` |
| Metro Bilbao | `METRO_BILBAO_` |
| Euskotren | `EUSKOTREN_` |
| FGC | `FGC_` |
| TMB Metro | `TMB_METRO_` |

---

## Notes

- Vehicle positions and trip updates are typically empty during night hours (no trains running)
- Alerts persist until their `active_period_end` or until updated by Renfe
- The `/departures` endpoint automatically includes delay info when available
- Route IDs in alerts use GTFS format (e.g., `10T0025C9`) not our format (`RENFE_C9_34`)
- El scheduler se integra con FastAPI lifespan y arranca automáticamente
- Detección automática de variantes C4a/C4b y C8a/C8b en Madrid basada en headsign
