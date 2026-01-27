# Plan de Implementación RAPTOR

**Fecha:** 2026-01-27
**Estado:** EN DESARROLLO

### Progreso:
- [x] Implementar estructuras de datos RAPTOR (`raptor.py`)
- [x] Implementar algoritmo de rondas con filtro Pareto
- [x] Crear RaptorService para integración API (`raptor_service.py`)
- [x] Actualizar schemas (`routing_schemas.py`)
- [x] Integrar con endpoint route-planner (`query_router.py`)
- [ ] **Tests** ← PENDIENTE
- [ ] **Deploy** ← PENDIENTE

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
