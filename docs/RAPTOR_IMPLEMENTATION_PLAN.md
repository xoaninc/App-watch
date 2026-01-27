# Plan de Implementación - Migración Completa del Proyecto

**Fecha inicio:** 2026-01-16
**Última actualización:** 2026-01-27
**Estado general:** MEGA-FASES 1-2 COMPLETADAS, MEGA-FASE 3 AL 85%, MEGA-FASES 4-5 PENDIENTES

---

## Índice

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [MEGA-FASE 1: Infraestructura Base](#mega-fase-1-infraestructura-base)
3. [MEGA-FASE 2: Plataformas y Correspondencias](#mega-fase-2-plataformas-y-correspondencias)
4. [MEGA-FASE 3: RAPTOR Route Planner](#mega-fase-3-raptor-route-planner)
5. [MEGA-FASE 4: Migración App iOS](#mega-fase-4-migración-app-ios)
6. [MEGA-FASE 5: Datos Pendientes](#mega-fase-5-datos-pendientes)
7. [Referencia Técnica RAPTOR](#referencia-técnica-raptor)
8. [Endpoints API](#endpoints-api)
9. [Archivos Clave](#archivos-clave)
10. [Historial de Bugs y Fixes](#historial-de-bugs-y-fixes)

---

## Resumen Ejecutivo

### Estado por Mega-Fase

| Mega-Fase | Descripción | Estado | Progreso |
|-----------|-------------|--------|----------|
| **1** | Infraestructura Base (BD, GTFS, PostGIS) | ✅ COMPLETADA | 100% |
| **2** | Plataformas y Correspondencias | ✅ COMPLETADA | 100% |
| **3** | RAPTOR Route Planner | ✅ COMPLETADA | 100% |
| **4** | Migración App iOS | ⏳ PENDIENTE | 0% |
| **5** | Datos Pendientes | ⏳ PENDIENTE | 20% |

### Métricas del Proyecto

| Métrica | Valor |
|---------|-------|
| Migraciones de BD | 32 |
| Operadores GTFS | 18 |
| Operadores GTFS-RT | 5 |
| Paradas totales | 6,709 |
| Stop times | 1,988,956 |
| Shapes | 949 (650,332 puntos) |
| Plataformas | 2,550 |
| Correspondencias | 166 (83 pares) |

### Decisiones Arquitectónicas

| Aspecto | Decisión |
|---------|----------|
| Algoritmo routing | RAPTOR (reemplaza Dijkstra) |
| Ubicación routing | Servidor (no cliente) |
| Alternativas | Múltiples rutas Pareto-óptimas |
| Time-dependent | Sí, con `departure_time` |
| Referencia implementación | `planarnetwork/raptor` (TypeScript → Python) |

---

## MEGA-FASE 1: Infraestructura Base

**Estado:** ✅ COMPLETADA
**Migraciones:** 001-025
**Período:** 2026-01-16 a 2026-01-18

### Migraciones Detalladas

| # | Migración | Descripción | Estado |
|---|-----------|-------------|--------|
| 001 | `create_gtfs_tables` | Tablas base: routes, stops, trips, stop_times, calendar, shapes | ✅ |
| 002 | `create_gtfs_rt_tables` | GTFS-RT: trip_updates, vehicle_positions, stop_time_updates | ✅ |
| 003 | `create_eta_tables` | Tablas ETA para predicciones | ✅ |
| 004 | `create_network_table` | Tabla gtfs_networks (31 redes) | ✅ |
| 005 | `add_province_to_stops` | Campo province en stops | ✅ |
| 006 | `enable_postgis` | Extensión PostGIS para geolocalización | ✅ |
| 007 | `create_provinces_table` | Tabla spanish_provinces con polígonos | ✅ |
| 008 | `create_nucleos_table` | Tabla gtfs_nucleos (obsoleta, ver 024) | ✅ |
| 009 | `add_nucleo_to_stops` | Campo nucleo_id en stops (obsoleto, ver 024) | ✅ |
| 010 | `add_nucleo_to_routes` | Campo nucleo_id en routes (obsoleto, ver 024) | ✅ |
| 011 | `add_nucleo_to_provinces` | Relación nucleos-provinces (obsoleta) | ✅ |
| 012 | `add_lineas_to_stops` | Campos cor_metro, cor_cercanias, etc. | ✅ |
| 013 | `create_stop_route_sequence` | Orden de paradas por ruta | ✅ |
| 014 | `create_gtfs_rt_alerts_tables` | Alertas de servicio GTFS-RT | ✅ |
| 015 | `add_platform_to_stop_time_updates` | Platform en predicciones | ✅ |
| 016 | `create_platform_history` | Historial de plataformas | ✅ |
| 017 | `add_observation_date` | Fecha observación en historial | ✅ |
| 018 | `add_route_frequencies` | Frecuencias de rutas + alert source | ✅ |
| 019 | `add_route_short_name_to_alerts` | Nombre corto en alertas | ✅ |
| 020 | `add_cor_tranvia_to_stops` | Campo cor_tranvia | ✅ |
| 021 | `add_nucleo_id_to_networks` | Nucleo en networks (temporal) | ✅ |
| 022 | `expand_color_columns` | Colores con prefijo # | ✅ |
| 023 | `restructure_nucleos_provinces` | Preparación para migración 024 | ✅ |
| **024** | **`replace_nucleos_with_network_provinces`** | **IMPORTANTE: Elimina nucleos, crea network_provinces** | ✅ |
| 025 | `add_occupancy` | Ocupación en stop_time_updates | ✅ |

### Cambio Importante: Migración 024

La migración 024 eliminó el sistema de "nucleos" y lo reemplazó por `network_provinces`:

**Antes:**
- `gtfs_nucleos` tabla separada
- `nucleo_id` en routes y stops

**Después:**
- Tabla `network_provinces` (relación N:M entre networks y provincias)
- `network_id` en routes (referencia a `gtfs_networks.code`)
- Sin `nucleo_id` en ninguna tabla

**Mapeo GTFS nucleo → network_id:**

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

---

## MEGA-FASE 2: Plataformas y Correspondencias

**Estado:** ✅ COMPLETADA
**Migraciones:** 026-032
**Período:** 2026-01-25 a 2026-01-26

### Migraciones Detalladas

| # | Migración | Descripción | Estado |
|---|-----------|-------------|--------|
| 026 | `create_line_transfer_table` | Tabla line_transfer (temporal) | ✅ |
| 027 | `add_correspondence_columns` | Campos cor_ml, cor_cercanias en stops | ✅ |
| 028 | `add_coords_to_line_transfer` | Coordenadas en transfers | ✅ |
| **029** | **`replace_line_transfer_with_stop_platform`** | **Elimina line_transfer, crea stop_platform** | ✅ |
| 030 | `rename_line_to_lines` | Campo `line` → `lines` (array) | ✅ |
| **031** | **`create_stop_correspondence_table`** | **Nueva tabla para conexiones a pie** | ✅ |
| 032 | `add_color_description_to_platform` | Color y descripción en plataformas | ✅ |

### Datos Importados

#### Plataformas (stop_platform): 2,550 total

| Red | Plataformas | Paradas | Fuente |
|-----|-------------|---------|--------|
| Renfe Cercanías | 797 | 791 | GTFS |
| Euskotren | 746 | 740 | GTFS |
| Metro Madrid | 281 | 233 | OSM |
| TRAM Barcelona | 172 | 172 | GTFS |
| TMB Metro BCN | 157 | 131 | OSM |
| Metro Valencia | 144 | 144 | GTFS |
| Metro Ligero | 56 | 56 | GTFS |
| Metro Bilbao | 55 | 42 | OSM |
| FGC | 54 | 34 | OSM |
| Metro Granada | 26 | 26 | GTFS |
| Metro Málaga | 25 | 25 | GTFS |
| Metro Sevilla | 21 | 21 | GTFS |

#### Correspondencias (stop_correspondence): 166 total (83 pares)

| Fuente | Cantidad | Ejemplos |
|--------|----------|----------|
| Manual | 32 | Acacias↔Embajadores, Nervión↔Eduardo Dato, Abando |
| OSM | 72 | Barcelona stop_area_groups (Catalunya, Sants) |
| Proximidad (<300m) | 62 | Atocha Metro↔Cercanías, Nuevos Ministerios |

**Por ciudad:**
- Madrid Metro: 17 pares
- Barcelona (TMB+FGC): 25 pares
- Bilbao (Metro+Euskotren): 5 pares
- Sevilla (Metro+Tranvía): 6 pares
- Valencia: 1 par (Sant Isidre)
- Zaragoza: 9 pares (Delicias, Plaza Aragón)

### Nuevos Endpoints

```
GET /api/v1/gtfs/stops/{stop_id}/platforms
GET /api/v1/gtfs/stops/{stop_id}/correspondences
```

### Nuevos Campos en API

| Campo | Endpoint | Descripción |
|-------|----------|-------------|
| `transport_type` | `/networks` | Tipo: cercanias, metro, tranvia, etc. |
| `is_hub` | `/stops/*` | true si 2+ tipos de transporte |
| `cor_ml` | stops | Correspondencia metro ligero |
| `cor_cercanias` | stops | Correspondencia cercanías |

---

## MEGA-FASE 3: RAPTOR Route Planner

**Estado:** 🔄 EN PROGRESO (85%)
**Período:** 2026-01-27

### Fase 3.1: Desarrollo Core ✅ COMPLETADA

| Tarea | Archivo | Estado |
|-------|---------|--------|
| Estructuras de datos RAPTOR | `src/gtfs_bc/routing/raptor.py` | ✅ |
| Algoritmo de rondas | `raptor.py` | ✅ |
| Filtro Pareto (alternativas óptimas) | `raptor.py` | ✅ |
| RaptorService | `src/gtfs_bc/routing/raptor_service.py` | ✅ |
| Schemas de routing | `adapters/http/api/gtfs/schemas/routing_schemas.py` | ✅ |

### Fase 3.2: Integración API ✅ COMPLETADA

| Tarea | Estado |
|-------|--------|
| Endpoint `/route-planner` en query_router.py | ✅ |
| Parámetro `departure_time` (hora de salida) | ✅ |
| Parámetro `max_alternatives` (1-5 rutas) | ✅ |
| Parámetro `max_transfers` (0-5 transbordos) | ✅ |
| Response con array `journeys[]` | ✅ |
| Campo `suggested_heading` por segmento | ✅ |
| Array `alerts[]` con avisos de servicio | ✅ |

### Fase 3.3: Fixes y Datos ✅ COMPLETADA

| Bug/Tarea | Causa | Solución | Estado |
|-----------|-------|----------|--------|
| Direcciones bidireccionales | stop_route_sequence usa orden geométrico | Construir patrones desde stop_times | ✅ |
| Paradas faltantes | Script saltaba stop_times sin stop_id | Función `import_missing_stops()` | ✅ |
| calendar_dates | No soportaba excepciones | Añadir consulta a calendar_dates | ✅ |
| nucleo_id → network_id | Columna eliminada en migración 024 | Actualizar scripts importación | ✅ |
| Metro Sevilla stop_times | Sin horarios reales | Script `import_metro_sevilla_gtfs.py` | ✅ |
| Metro Granada stop_times | Sin horarios reales | Script `import_metro_granada_gtfs.py` | ✅ |

### Fase 3.4: Deploy ✅ COMPLETADA

| Tarea | Estado |
|-------|--------|
| Deploy inicial a producción | ✅ |
| Re-importar GTFS con fixes (243 paradas, 1.84M stop_times) | ✅ |
| Endpoint funcionando en `https://juanmacias.com/api/v1/gtfs/route-planner` | ✅ |

### Fase 3.5: Limpieza ✅ COMPLETADA

| Tarea | Descripción | Estado |
|-------|-------------|--------|
| Eliminar `routing_service.py` | Código Dijkstra legacy (~16KB) | ✅ Eliminado |
| Limpiar Makefile | Referencias frontend | ✅ Limpio |

### Fase 3.6: Optimización ✅ COMPLETADA

| Tarea | Descripción | Estado |
|-------|-------------|--------|
| Crear estructura `tests/` | Directorio tests/ | ✅ Creado |
| Tests unitarios RAPTOR | 19 tests pasando | ✅ |
| Tests integración endpoint | 14 tests (skip sin BD) | ✅ |
| `?compact=true` | Response compacto para widget/Siri | ✅ Implementado |
| Índices BD | Para búsqueda en stop_times | ⏳ Opcional |
| Cache trips activos | Por fecha | ⏳ Opcional |

---

## MEGA-FASE 4: Migración App iOS

**Estado:** ⏳ PENDIENTE (0%)
**Responsable:** Compañero de equipo (app iOS)

### Fase 4.1: Normalización de Shapes

**API:** ✅ COMPLETADA (`?max_gap` implementado)
**App:** ⏳ PENDIENTE

| Tarea en App | Líneas a eliminar |
|--------------|-------------------|
| Añadir parámetro `maxGap` a `fetchRouteShape()` | - |
| Eliminar `AnimationController.normalizeRoute()` | ~30 |
| Eliminar `AnimationController.sphericalInterpolate()` | ~20 |
| **Total** | **~50** |

**Código a eliminar:**
```swift
// ELIMINAR de AnimationController.swift
func normalizeRoute(_ coords: [Coordinate], maxSegmentMeters: Double) -> [Coordinate]
func sphericalInterpolate(from: Coordinate, to: Coordinate, fraction: Double) -> Coordinate
```

### Fase 4.2: Route Planner RAPTOR

**API:** ✅ COMPLETADA (endpoint funcionando)
**App:** ⏳ PENDIENTE

| Tarea en App | Líneas a eliminar |
|--------------|-------------------|
| Crear nuevos modelos Swift | - |
| Crear función `planRoute()` en DataService | - |
| Eliminar `RoutingService.swift` completo | ~400 |
| Eliminar `buildGraph()`, `dijkstra()`, `buildSegments()` | ~100 |
| Eliminar `extractShapeSegment()` | ~30 |
| **Total** | **~530** |

**Código a eliminar:**
```swift
// ELIMINAR archivos/funciones completos:
- RoutingService.swift (completo)
- TransitNode, TransitEdge, EdgeType en Journey.swift
- buildGraph()
- dijkstra()
- buildSegments()
- extractShapeSegment()
- Llamadas a fetchCorrespondences() para construir grafo
```

**Modelos Swift nuevos necesarios:**
```swift
struct RoutePlannerResponse: Codable {
    let success: Bool
    let message: String?
    let journeys: [Journey]
    let alerts: [JourneyAlert]?
}

struct Journey: Codable {
    let departure: String      // ISO8601
    let arrival: String        // ISO8601
    let durationMinutes: Int
    let transfers: Int
    let walkingMinutes: Int
    let segments: [JourneySegment]
}

struct JourneySegment: Codable {
    let type: String           // "transit" | "walking"
    let mode: String           // "metro" | "cercanias" | "walking"
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

### Fase 4.3: Nuevas Features UI

**API:** ✅ COMPLETADA
**App:** ⏳ PENDIENTE

| Feature | Descripción | Dependencia |
|---------|-------------|-------------|
| Selector alternativas | UI para elegir entre 2-3 rutas Pareto | Fase 4.2 |
| Heading animación 3D | Usar `suggestedHeading` para orientar cámara | Fase 4.2 |
| Mostrar alertas | UI para avisos de servicio en journey | Fase 4.2 |

### Fase 4.4: Widget y Siri

**API:** ⏳ PENDIENTE (`?compact=true`)
**App:** ⏳ PENDIENTE

| Feature | Requisito API | Requisito App |
|---------|---------------|---------------|
| Widget iOS | Response <5KB | Widget extension |
| Siri shortcut | Latencia <500ms | Siri intent |

### Resumen Migración App

| Fase | API | App | Líneas |
|------|-----|-----|--------|
| 4.1 Shapes | ✅ | ⏳ | ~50 eliminar |
| 4.2 Route Planner | ✅ | ⏳ | ~530 eliminar |
| 4.3 UI Features | ✅ | ⏳ | Nueva UI |
| 4.4 Widget/Siri | ⏳ | ⏳ | Nueva feature |
| **Total eliminar** | | | **~580 líneas** |

---

## MEGA-FASE 5: Datos Pendientes

**Estado:** ⏳ PENDIENTE (20%)

### Intercambiadores Grandes

Estaciones con múltiples líneas que necesitan mapeo manual de plataformas:

| Estación | Ciudad | Líneas | Estado |
|----------|--------|--------|--------|
| Nuevos Ministerios | Madrid | L6, L8, L10, Cercanías | ⏳ |
| Atocha Cercanías | Madrid | ~10 plataformas | ⏳ |
| Chamartín | Madrid | ~6 plataformas | ⏳ |
| Sol | Madrid | L1, L2, L3, Cercanías | ⏳ |
| Príncipe Pío | Madrid | L6, L10, R, Cercanías | ⏳ |
| Passeig de Gràcia | Barcelona | L2, L3, L4, Rodalies | ⏳ |
| Sants | Barcelona | Metro, Rodalies, AVE | ⏳ |
| Plaça Catalunya | Barcelona | L1, L3, FGC, Rodalies | ⏳ |

### Otras Tareas de Datos

| Tarea | Prioridad | Estado |
|-------|-----------|--------|
| Completar Passeig de Gràcia (L2, L4 en cor_metro) | Media | ⏳ |
| Investigar API Valencia (devuelve vacío) | Baja | ⏳ |
| Investigar CIVIS Madrid | Baja | ⏳ |
| Coordenadas OSM metros secundarios (Valencia, Sevilla, Málaga, Granada) | Baja | ⏳ |
| Metro Tenerife (datos de líneas en cor_metro) | Baja | ⏳ |

---

## Referencia Técnica RAPTOR

### ¿Qué es RAPTOR?

**RAPTOR** = Round-bAsed Public Transit Optimized Router

Algoritmo diseñado específicamente para transporte público. Usado por Google Maps, Moovit, Citymapper, Transit App.

### Cómo funciona

1. **Rondas:** Cada ronda = 1 transbordo adicional
   - Ronda 0: Rutas directas (sin transbordos)
   - Ronda 1: Con 1 transbordo
   - Ronda 2: Con 2 transbordos
   - Máximo configurable (default: 5)

2. **Por cada ronda:**
   ```
   1. Relajar transferencias a pie
   2. Identificar rutas que pasan por paradas actualizadas
   3. Escanear cada ruta para encontrar mejores conexiones
   4. Actualizar tiempos de llegada (EarliestArrivalLabel)
   ```

3. **Filtro Pareto:** Retener rutas donde ninguna otra es mejor en TODOS los criterios:
   - Tiempo total
   - Número de transbordos
   - Tiempo caminando

### Ventajas sobre Dijkstra

| Aspecto | Dijkstra (antes) | RAPTOR (ahora) |
|---------|------------------|----------------|
| Tiempos | Estimados (velocidad comercial) | Reales (stop_times) |
| Hora salida | No considera | Sí (time-dependent) |
| Resultados | 1 ruta | Múltiples alternativas |
| Optimización | Solo tiempo | Multi-criterio Pareto |
| Complejidad | O(E log V) | O(K × R × T) |

### Estructuras de Datos

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

### Referencias

- Paper original: "Round-Based Public Transit Routing" (Delling et al., 2012)
- Implementación referencia: https://github.com/planarnetwork/raptor (TypeScript)
- Nuestra implementación: `src/gtfs_bc/routing/raptor.py`

---

## Endpoints API

### Route Planner (RAPTOR)

```
GET /api/v1/gtfs/route-planner
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `from` | string | requerido | ID parada origen |
| `to` | string | requerido | ID parada destino |
| `departure_time` | string | hora actual | Formato HH:MM |
| `max_transfers` | int | 3 | Máximo transbordos (0-5) |
| `max_alternatives` | int | 3 | Máximo alternativas (1-5) |

**Response:**
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
      "segments": [...]
    }
  ],
  "alerts": [...]
}
```

### Shapes Normalizados

```
GET /api/v1/gtfs/routes/{route_id}/shape?max_gap=50
```

### Plataformas

```
GET /api/v1/gtfs/stops/{stop_id}/platforms
```

### Correspondencias

```
GET /api/v1/gtfs/stops/{stop_id}/correspondences
```

### Testing

```bash
# Route planner básico
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004"

# Con hora de salida
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004&departure_time=08:30"

# Con alternativas
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004&max_alternatives=3"

# Shape normalizado
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_SEV_L1_CE_OQ/shape?max_gap=50"
```

---

## Archivos Clave

### Routing (RAPTOR)

| Archivo | Descripción |
|---------|-------------|
| `src/gtfs_bc/routing/raptor.py` | Algoritmo RAPTOR core (~30KB) |
| `src/gtfs_bc/routing/raptor_service.py` | Servicio HTTP para RAPTOR (~14KB) |
| `src/gtfs_bc/routing/routing_service.py` | **LEGACY** Dijkstra (~16KB) - ELIMINAR |
| `adapters/http/api/gtfs/schemas/routing_schemas.py` | Schemas Pydantic |
| `adapters/http/api/gtfs/routers/query_router.py` | Endpoint `/route-planner` |

### Scripts de Importación

| Script | Descripción |
|--------|-------------|
| `scripts/import_gtfs_static.py` | Importador multi-network Renfe |
| `scripts/import_metro_sevilla_gtfs.py` | Metro Sevilla stop_times |
| `scripts/import_metro_granada_gtfs.py` | Metro Granada stop_times |
| `scripts/import_stop_platforms.py` | Plataformas desde OSM |
| `scripts/import_osm_correspondences.py` | Correspondencias desde OSM |

### Documentación

| Archivo | Descripción |
|---------|-------------|
| `docs/RAPTOR_IMPLEMENTATION_PLAN.md` | Este archivo |
| `docs/archive/APP_MIGRATION_INSTRUCTIONS.md` | Instrucciones para app iOS |
| `docs/PLATFORMS_AND_CORRESPONDENCES.md` | Sistema de plataformas |
| `docs/GTFS_OPERATORS_STATUS.md` | Estado de operadores |
| `docs/archive/ROUTING_ALGORITHMS.md` | Investigación de algoritmos |

---

## Historial de Bugs y Fixes

### Bug: Direcciones de viaje (RESUELTO)

**Problema:** El algoritmo encontraba viajes en dirección contraria (llegada antes que salida).

**Causa:** La tabla `stop_route_sequence` almacena paradas en orden geométrico (posición en el shape), no en orden de viaje.

**Solución:**
1. Construir patrones de ruta desde `stop_times` (orden real de viaje)
2. Crear patrones separados por dirección: `RENFE_C10_42_dir_0`, `RENFE_C10_42_dir_1`
3. Verificar que destino viene DESPUÉS del origen en `stop_sequence`

### Bug: Paradas faltantes (RESUELTO)

**Problema:** Algunos trips de RENFE no tenían stop_times importados.

**Causa:** El script `import_gtfs_static.py` saltaba stop_times cuando el `stop_id` no existía en la BD.

**Solución:** Función `import_missing_stops()` que:
1. Lee `stop_times.txt` para encontrar paradas referenciadas
2. Compara con paradas existentes en BD
3. Importa las faltantes desde `stops.txt`

**Resultado:** 243 paradas importadas, 1.84M stop_times recuperados.

### Bug: calendar_dates (RESUELTO)

**Problema:** El algoritmo no soportaba excepciones de calendario (días festivos, servicios especiales).

**Solución:**
1. Función `import_calendar_dates()` en script de importación
2. RAPTOR consulta `calendar_dates` para añadir/quitar servicios según `exception_type`

### Bug: nucleo_id obsoleto (RESUELTO)

**Problema:** Scripts de importación usaban `nucleo_id` que fue eliminado en migración 024.

**Solución:**
1. Diccionario `GTFS_NUCLEO_TO_NETWORK` con mapeo
2. Función `network_id_to_gtfs_nucleo()` para conversión
3. Actualizar `build_route_mapping()` para usar `network_id`

---

## Estado Actual Route Planner (2026-01-27)

### Redes Funcionando ✅

| Red | Trips | Stop Times | Estado |
|-----|-------|------------|--------|
| **Cercanías (RENFE)** | 133,985 | ~1.5M | ✅ Funciona |
| **Metro Granada** | 5,693 | ~148k | ✅ Funciona |
| **Euskotren** | 11,088 | ~200k | ✅ Funciona (GTFS-RT) |

### Redes con Problemas de Calendario ⚠️

| Red | Trips | Problema | Solución |
|-----|-------|----------|----------|
| **FGC** | 15,495 | service_ids no coinciden con calendar | Reimportar GTFS o arreglar calendar |
| **TMB Metro** | 15,630 | service_ids no coinciden con calendar | Reimportar GTFS o arreglar calendar |
| **Metro Bilbao** | 10,620 | Verificar calendar | Reimportar si necesario |
| **Metrovalencia** | 11,230 | Verificar calendar | Reimportar si necesario |
| **TRAM** | 5,408 | Verificar calendar | Reimportar si necesario |

**Nota:** FGC y TMB son redes GTFS-RT - tienen datos de tiempo real pero los calendarios del GTFS estático no coinciden con los service_ids de los trips.

### Redes Sin Stop Times ❌

| Red | Problema | Solución |
|-----|----------|----------|
| **Metro Madrid** | GTFS solo tiene frequencies.txt, no stop_times individuales | Generar stop_times desde frecuencias |
| **Metro Sevilla** | GTFS tiene pocos trips (6:30-7:30), resto son frecuencias | Generar stop_times desde frecuencias |
| **Metro Ligero Madrid** | GTFS solo tiene frequencies.txt | Generar stop_times desde frecuencias |

---

## Tareas Pendientes Route Planner

### PASO 1: Arreglar Calendarios GTFS-RT (FGC, TMB, Metro Bilbao)

**Problema:** Los trips tienen service_ids como `FGC_6c4bdae202747640fd55c10d40` pero el calendar tiene `FGC_LABORABLE`.

**Solución paso a paso:**

1. Descargar GTFS fresco de cada operador:
   - FGC: `https://www.fgc.cat/google/google_transit.zip`
   - TMB: `https://api.tmb.cat/v1/static/datasets/gtfs.zip` (requiere API key)
   - Metro Bilbao: `https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfs_metro_bilbao.zip`

2. Verificar que calendar.txt tiene los service_ids correctos

3. Reimportar con script:
   ```bash
   python scripts/import_gtfs_static.py --network=FGC /path/to/gtfs.zip
   ```

4. O crear entradas de calendario manualmente:
   ```sql
   -- Ejemplo: crear calendar para service_ids existentes
   INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
   SELECT DISTINCT service_id, true, true, true, true, true, false, false, '2025-01-01', '2026-12-31'
   FROM gtfs_trips WHERE route_id LIKE 'FGC%'
   ON CONFLICT (service_id) DO NOTHING;
   ```

### PASO 2: Generar Stop Times para Redes con Frecuencias

**Redes afectadas:** Metro Madrid, Metro Sevilla, Metro Ligero Madrid

**Problema:** El GTFS de estas redes usa `frequencies.txt` en lugar de `stop_times.txt` completos. RAPTOR necesita stop_times individuales.

**Solución paso a paso:**

1. Para cada red, obtener datos de frecuencias:
   ```sql
   SELECT route_id, day_type, start_time, end_time, headway_secs
   FROM gtfs_route_frequencies
   WHERE route_id LIKE 'METRO_%'
   ORDER BY route_id, day_type, start_time;
   ```

2. Usar trip template existente para obtener secuencia de paradas y tiempos de viaje

3. Generar trips para cada franja horaria según el headway:
   - **IMPORTANTE:** Generar solo para el service_id correcto de cada día
   - **IMPORTANTE:** Usar headways específicos de cada día (weekday ≠ friday ≠ saturday ≠ sunday)
   - **IMPORTANTE:** Generar número razonable de trips (~200-400 por línea, no miles)

4. Script existente (necesita ajustes):
   ```bash
   python scripts/generate_metro_madrid_full_trips.py --day-type=weekday
   ```

**Mapeo de service_ids por red:**

| Red | Laborable | Viernes | Sábado | Domingo |
|-----|-----------|---------|--------|---------|
| Metro Madrid | METRO_MAD_LABORABLE | METRO_MAD_VIERNES | METRO_MAD_SABADO | METRO_MAD_DOMINGO |
| Metro Sevilla | METRO_SEV_2026_Laborable_ENE_JUN | METRO_SEV_2026_Viernes_ENE_JUN | METRO_SEV_2026_Sabado_ENE_JUN | METRO_SEV_2026_Domingo_ENE_JUN |
| Metro Ligero | ML_LABORABLE | ML_VIERNES | ML_SABADO | ML_DOMINGO |

### PASO 3: Optimizar RAPTOR (Opcional)

Si el rendimiento es problema con muchos trips:

1. **Filtrar por zona:** Modificar `_load_trips()` en `raptor.py` para cargar solo trips de redes relevantes (origen/destino)

2. **Añadir índices BD:**
   ```sql
   CREATE INDEX IF NOT EXISTS ix_trips_service_id ON gtfs_trips (service_id);
   CREATE INDEX IF NOT EXISTS ix_stop_times_trip_sequence ON gtfs_stop_times (trip_id, stop_sequence);
   ```

3. **Cache de servicios activos:** Cachear lista de service_ids activos por fecha

---

## Próximos Pasos

### Inmediatos (Fase 3.5-3.6)

1. [x] Eliminar `routing_service.py`
2. [x] Limpiar Makefile
3. [x] Crear estructura `tests/`
4. [x] Tests unitarios RAPTOR
5. [x] Implementar `?compact=true`
6. [ ] **Arreglar calendarios FGC/TMB/Metro Bilbao** (PASO 1)
7. [ ] **Generar stop_times Metro Madrid/Sevilla/ML** (PASO 2)

### Corto plazo (Fase 4)

1. [ ] App: Migrar shapes
2. [ ] App: Migrar route planner
3. [ ] App: UI alternativas

### Medio plazo (Fase 5)

1. [ ] Mapear intercambiadores grandes
2. [ ] Investigar APIs pendientes

---

**Última actualización:** 2026-01-27 por Claude
