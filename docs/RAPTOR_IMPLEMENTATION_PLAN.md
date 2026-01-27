# Plan de Implementación RAPTOR

**Fecha:** 2026-01-27
**Última actualización:** 2026-01-27
**Estado:** FASE 2 COMPLETADA - FASE 3/4 EN PROGRESO

---

## Estado de Fases

| Fase | Estado | Descripción |
|------|--------|-------------|
| **Fase 1: Desarrollo** | ✅ COMPLETADA | Implementación core RAPTOR |
| **Fase 2: Deploy** | ✅ COMPLETADA | Deploy a producción |
| **Fase 3: Limpieza** | 🔄 EN PROGRESO | Eliminar código legacy |
| **Fase 4: Optimización** | 🔄 EN PROGRESO | Tests, cache, rendimiento |

---

### Progreso Detallado:

#### Fase 1-2: Implementación y Deploy ✅
- [x] Implementar estructuras de datos RAPTOR (`raptor.py`)
- [x] Implementar algoritmo de rondas con filtro Pareto
- [x] Crear RaptorService para integración API (`raptor_service.py`)
- [x] Actualizar schemas (`routing_schemas.py`)
- [x] Integrar con endpoint route-planner (`query_router.py`)
- [x] Añadir parámetro `departure_time`
- [x] Añadir `alerts` al response
- [x] Añadir `suggested_heading` a segments
- [x] Fix: manejo de direcciones (trips bidireccionales)
- [x] Deploy inicial a producción
- [x] Fix: importar paradas faltantes (`import_missing_stops`)
- [x] Fix: soporte para calendar_dates (excepciones de servicio)
- [x] Fix: migración de nucleo_id a network_id (schema actualizado)
- [x] Re-importar GTFS con fixes (243 paradas faltantes, 1.84M stop_times)

#### Fase 3: Limpieza 🔄
- [ ] Eliminar `routing_service.py` (Dijkstra legacy)
- [ ] Limpiar Makefile (referencias a frontend inexistente)

#### Fase 4: Optimización 🔄
- [x] ~~Ejecutar import Metro Sevilla stop_times~~ ✅ COMPLETADO
- [x] ~~Ejecutar import Metro Granada stop_times~~ ✅ COMPLETADO
- [ ] Crear estructura de tests (`tests/`)
- [ ] Tests unitarios para RAPTOR
- [ ] Tests de integración endpoint route-planner
- [ ] Optimizar queries con índices BD
- [ ] Cache de trips activos por fecha
- [ ] Implementar `?compact=true` en departures (widget/Siri)

---

## Migración App iOS

La migración de la app iOS consiste en mover lógica del cliente al servidor, eliminando ~580 líneas de código Swift.

### Estado de Migración

| Componente | API (Backend) | App (Frontend) |
|------------|---------------|----------------|
| Normalización Shapes | ✅ `?max_gap` implementado | ⏳ Pendiente migrar |
| Route Planner RAPTOR | ✅ `/route-planner` funcionando | ⏳ Pendiente migrar |
| Alternativas Pareto | ✅ `journeys[]` array | ⏳ Pendiente UI |
| Alertas de servicio | ✅ `alerts[]` en response | ⏳ Pendiente UI |
| Compact departures | ⏳ Pendiente `?compact=true` | ⏳ Pendiente widget/Siri |

### Fase App-1: Normalización de Shapes (cambio pequeño, ~50 líneas)

**API ya soporta:** `GET /routes/{id}/shape?max_gap=50`

**Tareas en la App:**
- [ ] Añadir parámetro `maxGap` a `fetchRouteShape()`
- [ ] Eliminar `AnimationController.normalizeRoute()`
- [ ] Eliminar `AnimationController.sphericalInterpolate()`
- [ ] Probar animaciones 3D con shapes normalizados del servidor

**Código a eliminar:**
```swift
// ELIMINAR de AnimationController.swift
func normalizeRoute(_ coords: [Coordinate], maxSegmentMeters: Double) -> [Coordinate]
func sphericalInterpolate(from: Coordinate, to: Coordinate, fraction: Double) -> Coordinate
```

### Fase App-2: Route Planner RAPTOR (cambio grande, ~530 líneas)

**API ya soporta:** `GET /route-planner?from=STOP&to=STOP&departure_time=HH:MM`

**Tareas en la App:**
- [ ] Crear nuevos modelos Swift:
  - `RoutePlannerResponse`
  - `Journey`
  - `JourneySegment`
  - `JourneyStop`
- [ ] Crear función `planRoute()` en DataService
- [ ] Reemplazar todas las llamadas a RoutingService
- [ ] Eliminar `RoutingService.swift` completo

**Código a eliminar:**
```swift
// ELIMINAR archivos/funciones:
- RoutingService.swift (completo)
- TransitNode, TransitEdge, EdgeType en Journey.swift
- buildGraph()
- dijkstra()
- buildSegments()
- extractShapeSegment()
- Llamadas a fetchCorrespondences() para construir grafo
```

**Modelos Swift sugeridos:**
```swift
struct RoutePlannerResponse: Codable {
    let success: Bool
    let message: String?
    let journeys: [Journey]
    let alerts: [JourneyAlert]?
}

struct Journey: Codable {
    let departure: String  // ISO8601
    let arrival: String    // ISO8601
    let durationMinutes: Int
    let transfers: Int
    let walkingMinutes: Int
    let segments: [JourneySegment]
}

struct JourneySegment: Codable {
    let type: String       // "transit" | "walking"
    let mode: String       // "metro" | "cercanias" | "walking"
    let lineId: String?
    let lineName: String?
    let lineColor: String?
    let headsign: String?
    let origin: JourneyStop
    let destination: JourneyStop
    let departure: String?
    let arrival: String?
    let durationMinutes: Int
    let intermediateStops: [JourneyStop]
    let distanceMeters: Int?
    let coordinates: [Coordinate]
    let suggestedHeading: Double?
}

struct JourneyStop: Codable {
    let id: String
    let name: String
    let lat: Double
    let lon: Double
}

struct JourneyAlert: Codable {
    let id: String
    let lineId: String?
    let lineName: String?
    let message: String
    let severity: String
}
```

### Fase App-3: Nuevas Features UI

**Requiere completar Fase App-2 primero.**

- [ ] **Selector de alternativas:** UI para elegir entre 2-3 rutas Pareto-óptimas
- [ ] **Heading en animación 3D:** Usar `suggestedHeading` para orientar cámara
- [ ] **Mostrar alertas:** UI para avisos de suspensiones/retrasos en el journey

### Fase App-4: Widget y Siri

**Requiere que API implemente `?compact=true` primero.**

- [ ] Widget iOS con próximas salidas (response < 5KB)
- [ ] Siri shortcut para consultar salidas (latencia < 500ms)

### Orden de Migración Recomendado

1. **Fase App-1** (Shapes) - Cambio pequeño, bajo riesgo
2. **Fase App-2** (Route Planner) - Cambio grande, requiere testing
3. **Fase App-3** (UI) - Nuevas features, puede hacerse gradualmente
4. **Fase App-4** (Widget/Siri) - Depende de API `?compact=true`

### Testing de Endpoints

```bash
# Shape normalizado (YA FUNCIONA)
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_SEV_L1_CE_OQ/shape?max_gap=50"

# Route planner RAPTOR (YA FUNCIONA)
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004&departure_time=08:30"

# Con alternativas
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004&max_alternatives=3"
```

---

## 0. Decisión de Implementación

### Contexto del proyecto

| Métrica | Valor |
|---------|-------|
| Estaciones totales | ~2,054 |
| Operadores | 18 |
| Redes principales | RENFE, Metro Madrid, Metro Bilbao, Valencia, Barcelona |

### Opciones evaluadas

| Opción | Descripción | Veredicto |
|--------|-------------|-----------|
| A) Desde cero siguiendo paper | Control total, más trabajo | - |
| B) Portar `planarnetwork/raptor` (TS→Py) | Código limpio, referencia clara | ✅ **ELEGIDA** |
| C) Adaptar `transnetlab/transit-routing` | Ya en Python, pero académico | ❌ Código difícil de mantener |

### Razones de la elección

1. **Código limpio:** `planarnetwork/raptor` tiene arquitectura clara
2. **Sin dependencias externas:** Implementamos nosotros, integrado con PostgreSQL
3. **Mantenibilidad:** El equipo podrá entender y modificar el código
4. **Extensibilidad:** Arquitectura preparada para añadir CSA, isócronas, etc.
5. **Rendimiento:** Para ~2,000 paradas, <500ms es alcanzable fácilmente

### Tiempo estimado

| Fase | Duración |
|------|----------|
| Estudiar referencia | 1 día |
| Diseñar estructuras | 1 día |
| Implementar RAPTOR core | 3-4 días |
| Integrar endpoint + tests | 1-2 días |
| **Total** | **1-2 semanas** |

---

## 1. Resumen Ejecutivo

Migración del algoritmo de routing de Dijkstra a RAPTOR para el endpoint `/route-planner`.

### Decisiones tomadas:

| Aspecto | Decisión |
|---------|----------|
| Algoritmo | RAPTOR (Round-bAsed Public Transit Optimized Router) |
| Ubicación del routing | Server (con cache en app) |
| Alternativas | 3 rutas Pareto-óptimas |
| Time-dependent | Sí, con parámetro `departure_time` |
| Breaking change | Aprobado |

---

## 2. Arquitectura

### Actual (Dijkstra):
```
App → GET /route-planner?from=A&to=B → 1 ruta con tiempos estimados
```

### Nueva (RAPTOR):
```
App → GET /route-planner?from=A&to=B&departure_time=08:30 → 3 rutas con tiempos reales
```

### Diagrama:
```
┌─────────────────────────────────────────┐
│              App iOS                     │
│  ┌─────────────────────────────────┐    │
│  │ Cache local:                     │    │
│  │ - Paradas (nombres, coords)      │    │
│  │ - Líneas (colores, nombres)      │    │
│  │ - Favoritos                      │    │
│  │ - Últimas búsquedas              │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│              Server (FastAPI)            │
│  ┌─────────────────────────────────┐    │
│  │ RAPTOR Engine:                   │    │
│  │ - Consulta stop_times            │    │
│  │ - Calcula rutas Pareto-óptimas   │    │
│  │ - Devuelve 3 alternativas        │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

---

## 3. Nuevo Schema del API

### Request

```
GET /api/v1/gtfs/route-planner?from=STOP_ID&to=STOP_ID&departure_time=HH:MM
```

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `from` | string | Sí | - | ID parada origen |
| `to` | string | Sí | - | ID parada destino |
| `departure_time` | string | No | Hora actual | Formato HH:MM o ISO8601 |
| `max_transfers` | int | No | 3 | Máximo transbordos (0-5) |
| `max_alternatives` | int | No | 3 | Máximo alternativas (1-5) |

### Response

```json
{
  "success": true,
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
          "line_id": "METRO_SEV_L1",
          "line_name": "L1",
          "line_color": "ED1C24",
          "headsign": "Ciudad Expo",
          "departure": "2026-01-28T08:32:00",
          "arrival": "2026-01-28T08:47:00",
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
          "intermediate_stops": [
            {"id": "...", "name": "Gran Plaza", "lat": ..., "lon": ...},
            {"id": "...", "name": "El Greco", "lat": ..., "lon": ...}
          ],
          "stop_count": 5,
          "coordinates": [
            {"lat": 37.3891, "lon": -5.9723},
            {"lat": 37.3885, "lon": -5.9730},
            ...
          ],
          "suggested_heading": 225.0
        },
        {
          "type": "walking",
          "mode": "walking",
          "duration_minutes": 3,
          "distance_meters": 200,
          "origin": {...},
          "destination": {...},
          "coordinates": [...],
          "suggested_heading": 180.0
        },
        {
          "type": "transit",
          "mode": "cercanias",
          ...
        }
      ]
    },
    {
      "departure": "2026-01-28T08:35:00",
      "arrival": "2026-01-28T09:15:00",
      "duration_minutes": 40,
      "transfers": 1,
      "walking_minutes": 2,
      "segments": [...]
    },
    {
      "departure": "2026-01-28T08:40:00",
      "arrival": "2026-01-28T09:20:00",
      "duration_minutes": 40,
      "transfers": 0,
      "walking_minutes": 8,
      "segments": [...]
    }
  ],
  "alerts": [
    {
      "id": "alert_001",
      "line_id": "METRO_SEV_L1",
      "line_name": "L1",
      "message": "Frecuencia reducida por obras en Conde de Bustillo",
      "severity": "warning",
      "active_from": "2026-01-27T06:00:00",
      "active_until": "2026-01-30T23:59:59"
    }
  ]
}
```

### Cambios vs schema actual

| Campo | Antes | Después |
|-------|-------|---------|
| Root | `journey` (objeto) | `journeys` (array) |
| Timestamps | No | `departure`, `arrival` en ISO8601 |
| Alertas | No | `alerts[]` con líneas afectadas |
| Heading | No | `suggested_heading` por segment |

---

## 4. Endpoint Widget/Siri

### Request

```
GET /api/v1/gtfs/stops/{stop_id}/departures?compact=true&limit=3
```

### Response (compact)

```json
{
  "stop_id": "METRO_SOL",
  "stop_name": "Sol",
  "departures": [
    {"line": "L1", "minutes": 3, "headsign": "Valdecarros"},
    {"line": "L2", "minutes": 5, "headsign": "Las Rosas"},
    {"line": "L3", "minutes": 2, "headsign": "Moncloa"}
  ],
  "updated_at": "2026-01-27T15:30:00Z"
}
```

### Requisitos

- Response < 5KB (ideal ~500 bytes)
- Latencia < 500ms (para Siri timeout)
- Parámetro `limit` para controlar cantidad

---

## 5. Algoritmo RAPTOR

### Referencia de implementación

**Repositorio:** https://github.com/planarnetwork/raptor (TypeScript)

### Concepto básico

1. **Rondas:** Cada ronda = 1 transbordo adicional
   - Ronda 0: Rutas directas (sin transbordos)
   - Ronda 1: Con 1 transbordo
   - Ronda 2: Con 2 transbordos
   - Máximo: 5 rondas (configurable)

2. **Por cada ronda:**
   ```
   1. Relajar transferencias a pie
   2. Identificar rutas que pasan por paradas actualizadas
   3. Escanear cada ruta para encontrar mejores conexiones
   4. Actualizar tiempos de llegada (EarliestArrivalLabel)
   ```

3. **Filtro Pareto:**
   - Retener rutas donde ninguna otra es mejor en TODOS los criterios
   - Criterios: tiempo total, número de transbordos, tiempo caminando

### Estructuras de datos

```python
@dataclass
class EarliestArrivalLabel:
    """Tiempo de llegada más temprano a una parada por ronda."""
    arrival_time: int  # segundos desde medianoche
    trip_id: str
    boarding_stop: str

@dataclass
class Transfer:
    """Transferencia a pie entre paradas."""
    from_stop: str
    to_stop: str
    walk_time_seconds: int

@dataclass
class StopTime:
    """Evento de llegada/salida en una parada."""
    trip_id: str
    stop_id: str
    arrival_seconds: int
    departure_seconds: int
    stop_sequence: int
```

### Queries de BD necesarias

```sql
-- Trips activos en una fecha
SELECT t.id, t.route_id, t.service_id, t.headsign
FROM gtfs_trips t
JOIN gtfs_calendar c ON t.service_id = c.service_id
WHERE c.start_date <= :date AND c.end_date >= :date
  AND (CASE EXTRACT(DOW FROM :date)
       WHEN 0 THEN c.sunday
       WHEN 1 THEN c.monday
       -- etc
       END) = true;

-- Stop times para trips activos
SELECT trip_id, stop_id, arrival_seconds, departure_seconds, stop_sequence
FROM gtfs_stop_times
WHERE trip_id IN (:active_trips)
ORDER BY trip_id, stop_sequence;

-- Transferencias a pie
SELECT from_stop_id, to_stop_id, walk_seconds
FROM stop_correspondence
WHERE walk_seconds IS NOT NULL;
```

---

## 6. Campo `suggested_heading`

### Cálculo

```python
import math

def calculate_heading(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula el bearing (heading) entre dos puntos.
    Retorna grados 0-360 donde 0=Norte, 90=Este, 180=Sur, 270=Oeste.
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    bearing = math.atan2(x, y)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360

    return round(bearing, 1)
```

### Uso en segmento

Se calcula desde el primer punto hasta el último punto del segmento para dar la dirección general.

---

## 7. Cache en App (Recomendaciones)

| Dato | Cachear | TTL | Storage |
|------|---------|-----|---------|
| Lista de paradas | ✅ | 1 semana | CoreData/SQLite |
| Info de líneas | ✅ | 1 semana | CoreData/SQLite |
| Últimas búsquedas | ✅ | Indefinido | UserDefaults |
| Favoritos | ✅ | Indefinido | UserDefaults |
| Departures | ❌ | - | Siempre fetch |
| Route planner | ❌ | - | Siempre fetch |

---

## 8. Tareas de Implementación

### Backend (API)

| # | Tarea | Prioridad | Esfuerzo | Dependencias |
|---|-------|-----------|----------|--------------|
| 1 | Crear estructuras de datos RAPTOR | Alta | Medio | - |
| 2 | Implementar carga de datos (trips, stop_times, transfers) | Alta | Medio | 1 |
| 3 | Implementar algoritmo de rondas | Alta | Alto | 2 |
| 4 | Implementar filtro Pareto | Alta | Medio | 3 |
| 5 | Integrar con endpoint route-planner | Alta | Medio | 4 |
| 6 | Añadir parámetro `departure_time` | Alta | Bajo | 5 |
| 7 | Añadir `alerts` al response | Media | Bajo | 5 |
| 8 | Añadir `suggested_heading` a segments | Baja | Bajo | 5 |
| 9 | Implementar `?compact=true` en departures | Media | Bajo | - |
| 10 | Optimizar queries con índices | Media | Medio | 5 |
| 11 | Tests unitarios RAPTOR | Alta | Medio | 4 |
| 12 | Tests integración endpoint | Alta | Medio | 5 |

### Frontend (App iOS)

| # | Tarea | Prioridad | Dependencias |
|---|-------|-----------|--------------|
| 1 | Actualizar modelos Swift para nuevo schema | Alta | Backend #5 |
| 2 | Adaptar UI para mostrar alternativas | Alta | 1 |
| 3 | Implementar selector de alternativas | Alta | 2 |
| 4 | Usar `suggested_heading` en animación 3D | Baja | 1 |
| 5 | Implementar widget con `?compact=true` | Media | Backend #9 |
| 6 | Implementar Siri shortcut | Media | Backend #9 |
| 7 | Implementar cache de paradas/líneas | Media | - |
| 8 | Mostrar alertas en journey | Media | Backend #7 |

---

## 9. Plan de Despliegue

### Fase 1: Desarrollo
1. Backend implementa RAPTOR
2. App prepara nuevos modelos Swift
3. Testing en local/staging

### Fase 2: Deploy coordinado
1. Deploy backend a producción (mantiene compatibilidad temporal)
2. App envía update a App Store
3. Período de transición (ambos schemas funcionan)

### Fase 3: Limpieza
1. Remover schema antiguo del backend
2. Remover código legacy de la app

---

## 10. Métricas de Éxito

| Métrica | Actual | Objetivo |
|---------|--------|----------|
| Tiempo de respuesta route-planner | ~800ms | <500ms |
| Alternativas devueltas | 1 | 3 |
| Precisión de tiempos | Estimados | Reales (±1min) |
| Soporte hora de salida | No | Sí |

---

## 11. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| RAPTOR más lento que Dijkstra | Baja | Alto | Pre-calcular datos, índices BD |
| Breaking change rompe apps antiguas | Media | Alto | Período de transición |
| Complejidad de implementación | Media | Medio | Seguir referencia planarnetwork |
| Datos stop_times incompletos | Baja | Alto | Fallback a tiempos estimados |

---

## 12. Referencias

- Documentación RAPTOR: `docs/ROUTING_ALGORITHMS.md` (secciones 2, 17)
- Implementación referencia: https://github.com/planarnetwork/raptor
- Paper original: "Round-Based Public Transit Routing" (Delling et al., 2012)
- Schema actual: `docs/ROUTE_PLANNER.md`
- Instrucciones migración app: `docs/APP_MIGRATION_INSTRUCTIONS.md`

---

## 13. Notas de Implementación

### Bug: Direcciones de viaje

**Problema:** El algoritmo encontraba viajes en dirección contraria (llegada antes que salida).

**Causa:** La tabla `stop_route_sequence` almacena paradas en orden geométrico (posición en el shape), no en orden de viaje. Los trenes pueden ir en ambas direcciones en la misma línea.

**Solución:**
1. Construir patrones de ruta desde `stop_times` (orden real de viaje) en lugar de `stop_route_sequence`
2. Crear patrones separados para cada dirección: `RENFE_C10_42_dir_0`, `RENFE_C10_42_dir_1`
3. Verificar que el destino viene DESPUÉS del origen en el `stop_sequence` del trip

**Código:**
```python
def _get_arrival_time_with_boarding(self, trip, stop_id, boarding_stop_id):
    # Only return if destination comes AFTER boarding in the trip
    if boarding_seq is not None and stop_seq is not None and stop_seq > boarding_seq:
        return arrival_time
```

### Fix: Paradas faltantes en stop_times

**Problema:** Algunos trips de RENFE no tenían stop_times importados.

**Causa:** El script `import_gtfs_static.py` saltaba stop_times cuando el `stop_id` no existía en nuestra base de datos. Si el archivo GTFS referenciaba paradas nuevas que no habíamos importado, esos stop_times se perdían.

**Solución:** Se añadió la función `import_missing_stops()` que:
1. Lee `stop_times.txt` para encontrar todas las paradas referenciadas por los trips a importar
2. Compara con las paradas existentes en la BD
3. Importa las paradas faltantes desde `stops.txt` antes de importar stop_times

### Fix: Soporte para calendar_dates

**Problema:** El algoritmo no soportaba excepciones de calendario (días festivos, servicios especiales).

**Solución:**
1. Se añadió la función `import_calendar_dates()` al script de importación
2. RAPTOR ahora consulta `calendar_dates` para añadir/quitar servicios según `exception_type` (1=añadido, 2=eliminado)

### Fix: Migración de nucleo_id a network_id (Migración 024)

**Contexto:** La tabla `gtfs_nucleos` fue eliminada y reemplazada por el sistema de `network_provinces` en la migración 024.

**Cambios en el schema:**
- Eliminada columna `nucleo_id` de `gtfs_routes` y `gtfs_stops`
- Añadida columna `network_id` a `gtfs_routes` (referencia a `gtfs_networks.code`)
- Creada tabla `network_provinces` para relación N:M entre networks y provincias

**Mapeo GTFS nucleo → network_id:**
El archivo GTFS de Renfe usa IDs de núcleo que difieren de nuestros network_ids en algunos casos:

| GTFS Nucleo | Nombre | Network ID |
|-------------|--------|------------|
| 10 | Madrid | 10T |
| 20 | Asturias | 20T |
| 30 | Sevilla | 30T |
| 31 | Cádiz | **33T** |
| 32 | Málaga | **34T** |
| 40 | Valencia | 40T |
| 41 | Murcia/Alicante | 41T |
| 51 | Barcelona (Rodalies) | 51T |
| 60 | Bilbao | 60T |
| 61 | San Sebastián | 61T |
| 62 | Santander | 62T |
| 70 | Zaragoza | 70T |
| 90 | C-9 Cotos | 10T |

**Actualización del script de importación:**
- Añadida función `network_id_to_gtfs_nucleo()` para convertir network_id → GTFS nucleo
- Añadido diccionario `GTFS_NUCLEO_TO_NETWORK` con el mapeo inverso
- Actualizada `build_route_mapping()` para usar `network_id` en lugar de `nucleo_id`
- Actualizada `clear_nucleo_data()` para usar el mapeo correcto

**Documentación:** Ver `docs/ARCHITECTURE_NETWORK_PROVINCES.md` para detalles completos del sistema de networks y provincias.

### Limitaciones conocidas

1. **Metro Sevilla sin stop_times:** ⏳ Script `scripts/import_metro_sevilla_gtfs.py` listo. Mapea plataformas GTFS (`L1-1`) a nuestras estaciones (`METRO_SEV_L1_E1`). Pendiente ejecutar en servidor.

2. **Metro Granada sin stop_times:** ⏳ Script `scripts/import_metro_granada_gtfs.py` listo. Mapea stop_ids (`1`) a nuestras estaciones (`METRO_GRANADA_1`). Pendiente ejecutar en servidor.

3. **Transfers solo por stop_correspondence:** El algoritmo solo considera transfers definidos en la tabla `stop_correspondence`. No calcula transfers automáticos por proximidad.

**Nota:** Metro Sevilla y Granada también publican frequencies.txt. Los scripts de importación permiten cargar stop_times para que RAPTOR calcule rutas con horarios exactos.
