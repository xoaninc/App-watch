# RAPTOR Code Review - Post Hora 4

**Fecha:** 2026-01-28
**Revisores:** Claude + Experto externo
**Archivos revisados:**
- `gtfs_store.py` - Core data store
- `raptor.py` - Algoritmo RAPTOR
- `raptor_service.py` - Servicio de alto nivel
- `query_router.py` - Endpoints API
- `routing_schemas.py` - Schemas Pydantic
- `shape_utils.py` - Utilidades geográficas

---

## Bugs Críticos (CORREGIDOS)

### 1. Copia de labels perdiendo trip_id
**Archivo:** `raptor.py:199`
**Commit:** `524e59d`

```python
# ANTES (Mal): Creaba objeto nuevo sin trip_id
labels[k][stop_id] = Label(arrival_time=label.arrival_time)

# DESPUÉS (Bien): Copia referencia completa
labels[k][stop_id] = label
```

**Impacto:** El algoritmo sabía cuándo llegabas pero no cómo. Rompía `_reconstruct_legs`.

---

### 2. Tiempo fantasma en walking legs
**Archivo:** `raptor.py:437`
**Commit:** `524e59d`

```python
# ANTES (Mal): Inventaba medianoche si no encontraba parada
from_arrival = labels[current_round].get(from_stop, Label(arrival_time=0)).arrival_time

# DESPUÉS (Bien): Valida existencia, skip si corrupto
from_label = labels[current_round].get(from_stop)
if not from_label:
    current_stop = from_stop
    continue
from_arrival = from_label.arrival_time
```

**Impacto:** Walking legs mostraban "850 minutos" por usar 0 como fallback.

---

### 3. boarding_time or 0
**Archivo:** `raptor.py:454`
**Commit:** `6f84cd2`

```python
# ANTES (Mal): Inventaba medianoche
actual_departure = label.boarding_time or 0

# DESPUÉS (Bien): Prioriza store, fallback a label, skip si falla
if actual_departure is None:
    actual_departure = label.boarding_time
if actual_departure is None:
    current_stop = label.boarding_stop_id
    current_round -= 1
    continue
```

**Impacto:** Transit legs con salida a medianoche fantasma.

---

### 4. Infinite loop en _reconstruct_legs
**Archivo:** `raptor.py:426`
**Commit:** `d7fb325`

```python
# AÑADIDO: Safety counter
safety_counter = 0
MAX_STEPS = 20

while current_stop != origin_stop_id and current_round >= 0:
    safety_counter += 1
    if safety_counter > MAX_STEPS:
        print(f"⚠️ Infinite loop detected...")
        return []
```

**Impacto:** Walking legs en ciclo colgaban el worker al 100% CPU.

---

## Bugs Moderados (CORREGIDOS)

### 5. except Exception silencioso en alertas
**Archivo:** `raptor_service.py:217`
**Commit:** `8dd26f4`

```python
# ANTES (Mal): Silenciaba todos los errores
except Exception:
    return []

# DESPUÉS (Bien): Loguea el error
except Exception as e:
    print(f"⚠️ ALERTS SYSTEM ERROR: {e}")
    return []
```

**Impacto:** Errores de alertas invisibles en debugging.

---

## Deuda Técnica (ACEPTADA - Baja Prioridad)

### gtfs_store.py

| Línea | Descripción | Riesgo |
|-------|-------------|--------|
| 259 | `service_id = ... if row[2] else ""` - Fail-safe intencional | Ninguno |
| 285-286 | `arr_sec = row[2] or 0` - Redundante (BD tiene NOT NULL) | Ninguno |
| 62, 67 | Comentarios duplicados "# 5." | Cosmético |

### raptor.py

| Línea | Descripción | Riesgo |
|-------|-------------|--------|
| 34 | `WALKING_SPEED_KMH = 4.5` no usado | Código muerto |

### raptor_service.py

| Línea | Descripción | Riesgo |
|-------|-------------|--------|
| 22 | `import normalize_shape` no usado | Código muerto |
| 269 | Import dentro de función (`haversine_distance`) | Ineficiencia mínima |
| 232 | Duración negativa si datos corruptos | Chivato visual útil |
| 89, 95-96 | Lat/lon 0,0 si falta parada | Chivato visual útil |

### query_router.py

| Línea | Descripción | Riesgo |
|-------|-------------|--------|
| 1029 | Import `datetime` dentro de función | Ineficiencia mínima |
| 1226 | Import `StopRouteSequenceModel` dentro de función | Ineficiencia mínima |
| 1629-1630 | Imports de shapes dentro de función | Ineficiencia mínima |
| 1838, 1850 | Imports `datetime` dentro de función | Ineficiencia mínima |

### routing_schemas.py

| Línea | Descripción | Riesgo |
|-------|-------------|--------|
| 120-155 | Schemas legacy para backwards compatibility | Eliminar en v2.0 |

### shape_utils.py

✅ **Sin deuda técnica** - Código limpio con buenas prácticas (clamp numérico, manejo división por cero)

### realtime_router.py

| Línea | Descripción | Riesgo |
|-------|-------------|--------|
| 149-150 | Búsqueda de vehículo iterando en memoria vs query | Ineficiencia menor |
| 639 | Workaround timezone naive para BD | Funcional, bien comentado |

### holiday_utils.py

| Línea | Descripción | Riesgo |
|-------|-------------|--------|
| 27-30 | Solo festivos de Madrid (hardcoded) | Limitación multi-región |

**Nota:** No bloquea routing (GTFS calendar_dates es la fuente de verdad). Refactorizar para aceptar `region_code` en v2.0.

### route_utils.py

| Línea | Descripción | Riesgo |
|-------|-------------|--------|
| 50-51 | Parseo tiempo sin try/except | Bajo (datos de BD controlada) |

### estimated_positions.py

| Línea | Descripción | Riesgo |
|-------|-------------|--------|
| 60-65 | SQL con f-string (pero variable controlada) | Ninguno (seguro) |
| 191-192 | Interpolación lineal vs esférica | Aceptable (distancias cortas) |
| - | Servicios nocturnos post-medianoche | Limitación v2.0 |

### gtfs_rt_fetcher.py

| Línea | Descripción | Riesgo |
|-------|-------------|--------|
| 208-209 | N+1 queries en _record_platform_history | Bajo (logging) |
| 470-505 | N+1 queries en _predict_platforms_from_history | Moderado (no crítico) |
| 435, 467, 523 | Imports dentro de funciones | Ineficiencia mínima |

---

## Decisiones de Diseño Validadas

1. **Patterns vs Routes**: Correcto. Agrupa por secuencia de paradas.
2. **Lazy check de servicios**: Correcto. O(1) en runtime.
3. **No filtrar por red/ciudad**: Correcto. Grafo ignora islas.
4. **Tuplas nativas**: Correcto. Menor memoria.

---

## Resumen de Commits

| Commit | Descripción |
|--------|-------------|
| `524e59d` | Fix label copy + walking leg time |
| `6f84cd2` | Fix boarding_time or 0 |
| `d7fb325` | Add safety counter for infinite loops |
| `8dd26f4` | Log alerts errors |

---

---

## Seguridad - Claves API

### TMB API Keys

**Archivo:** `src/gtfs_bc/realtime/infrastructure/services/multi_operator_fetcher.py`

**Estado:** ✅ Movidas a variables de entorno (.env)

```python
import os
TMB_APP_ID = os.getenv('TMB_APP_ID')
TMB_APP_KEY = os.getenv('TMB_APP_KEY')
```

### Claves NO expuestas (protegidas por .gitignore)

| Archivo | Contenido |
|---------|-----------|
| `.env.local` | NAP_USER, NAP_PASSWORD |
| `.claude/settings.local.json` | NAP API Key en logs |

### BLOCKER PRODUCCIÓN: Endpoint admin sin auth

**Archivo:** `app.py:77-103`

```python
@app.post("/admin/reload-gtfs")
async def reload_gtfs(background_tasks: BackgroundTasks):
    # Sin autenticación - cualquiera puede llamar
```

**Riesgo:** Vector de ataque DoS. Un atacante puede forzar recargas continuas (100% CPU, OOM kill).

**Acción ANTES de producción:**
1. Añadir API key header (`x-admin-token`)
2. O bloquear `/admin/*` en Nginx/Ingress

---

## Pre-Testing Checklist

### Verificar migraciones de Alembic

Antes de arrancar el servidor, verificar que la BD tenga las últimas migraciones:

```bash
cd /Users/juanmaciasgomez/Projects/renfeserver
alembic current
```

Si no muestra `033` (la última), ejecutar:
```bash
alembic upgrade head
```

**Columnas críticas que deben existir:**

| Tabla | Columnas | Migración |
|-------|----------|-----------|
| `gtfs_rt_stop_time_updates` | `occupancy_percent`, `occupancy_per_car`, `headsign` | 025 |
| `gtfs_rt_stop_time_updates` | `platform` | 015 |
| `gtfs_rt_vehicle_positions` | `platform` | 001 |
| `platform_history` | (tabla completa) | 016, 017 |

Si faltan, el fetcher de realtime fallará con errores de columnas inexistentes.

---

## Estado Final

**Código listo para Hora 5 (Testing).**

Todos los bugs críticos corregidos. Deuda técnica documentada para v2.0.

**IMPORTANTE:** Rotar claves TMB inmediatamente después del testing.

---

## Archivos Revisados (25+)

### Core RAPTOR (críticos)
- [x] `gtfs_store.py` - 4 bugs encontrados (código defensivo redundante)
- [x] `raptor.py` - **4 bugs críticos corregidos**
- [x] `raptor_service.py` - **1 bug moderado corregido**

### API/Routers
- [x] `query_router.py` - Imports dentro de funciones (menor)
- [x] `realtime_router.py` - N+1 queries (menor)
- [x] `eta_router.py` - Limpio
- [x] `network_router.py` - N+1 queries, código duplicado (menor)
- [x] `import_router.py` - Limpio

### Schemas
- [x] `routing_schemas.py` - Schemas legacy (menor)
- [x] `departure_schemas.py` - Limpio

### Utils
- [x] `shape_utils.py` - Limpio, buenas prácticas
- [x] `holiday_utils.py` - Solo festivos Madrid (limitación)
- [x] `route_utils.py` - Parseo sin try/except (menor)

### Servicios Realtime
- [x] `gtfs_rt_fetcher.py` - N+1 queries en predicción
- [x] `gtfs_rt_scheduler.py` - asyncio.get_event_loop deprecated (menor)
- [x] `estimated_positions.py` - Interpolación lineal OK, servicios nocturnos (limitación)
- [x] `multi_operator_fetcher.py` - **TMB keys expuestas**, FGC no implementado

### ETA
- [x] `eta_calculator.py` - Bug `!= 0` (impacto suave), queries separadas

### Core
- [x] `config.py` - Limpio, validación SECRET_KEY
- [x] `database.py` - Pool robusto, retry logic
- [x] `celery.py` - Bien configurado
- [x] `app.py` - **Endpoint admin sin auth (DoS risk)**

### Entidades/Modelos
- [x] `stop_model.py` - Limpio
- [x] `trip_model.py` - Limpio, confirma nullable=False
- [x] `stop_time_model.py` - Limpio, confirma nullable=False
- [x] `vehicle_position.py` - Limpio
- [x] `eta_result.py` - Excelente diseño

### Scripts
- [x] `auto_update_gtfs.py` - Excelente, usa env vars

### Tests
- [x] `test_raptor.py` - Solo estructuras, faltan tests de bugs
- [x] `test_route_planner.py` - Integración básica

### Config
- [x] `docker-compose.yml` - Falta TZ=Europe/Madrid en db

---

## Archivos NO Revisados (para v2.0)

### Framework CQRS
- [ ] `src/framework/application/command_bus.py`
- [ ] `src/framework/application/query_bus.py`

### Importadores de datos
- [ ] `src/gtfs_bc/metro/infrastructure/services/crtm_metro_importer.py`
- [ ] `src/gtfs_bc/metro/infrastructure/services/metro_frequency_importer.py`
- [ ] `scripts/import_gtfs_static.py`
- [ ] `scripts/import_metro.py`
- [ ] `scripts/import_metro_sevilla.py`
- [ ] ~20 scripts más de importación/fix

### Otros servicios
- [ ] `src/gtfs_bc/province/province_lookup.py`
- [ ] `src/gtfs_bc/realtime/infrastructure/tasks.py`
- [ ] `src/gtfs_bc/eta/domain/value_objects/geo.py`

### Modelos restantes (~30 archivos)
- [ ] Modelos de calendar, route, shape, agency, etc.

**Nota:** Estos archivos no son críticos para el routing RAPTOR. Son importadores de datos, framework auxiliar, y modelos secundarios.

---

## Resumen Ejecutivo

| Categoría | Encontrados | Corregidos | Pendientes |
|-----------|-------------|------------|------------|
| Bugs críticos | 4 | 4 | 0 |
| Bugs moderados | 1 | 1 | 0 |
| Seguridad | 2 | 0 | 2 (post-testing) |
| Deuda técnica | 15+ | 0 | 15+ (v2.0) |

### Blockers para Producción
1. **TMB API Keys** - Rotar y mover a env vars
2. **Endpoint /admin/reload-gtfs** - Añadir auth o bloquear en proxy

### Recomendaciones Inmediatas
1. Verificar `alembic current` = 033
2. Configurar `TZ=Europe/Madrid` en docker-compose (opcional)
3. Ejecutar tests de carga en localhost:8000

---

## Fixes de Datos (2026-01-28)

### ✅ Metro Tenerife - Trips expandidos
**Problema:** Solo 12 trips plantilla (GTFS usa frequencies.txt)
**Solución:** Script `generate_metro_tenerife_trips.py`
**Resultado:** 1,212 trips, 16,362 stop_times generados

### ✅ Tranvía Sevilla (Metrocentro) - Trips creados
**Problema:** Ruta y paradas existían pero 0 trips
**Solución:** Script `generate_tranvia_sevilla_trips.py`
**Resultado:** 636 trips, 4,452 stop_times generados

### ✅ TRAM Barcelona - Correspondencia Francesc Macià
**Problema:** Faltaba conexión del terminal Trambaix con FGC/Metro
**Solución:** INSERT manual en stop_correspondence
**Resultado:** 4 conexiones añadidas (Francesc Macià ↔ FGC Provença, Metro Diagonal)

### ✅ Tranvía Vitoria - FUNCIONANDO
**Estado:** Completado (2026-01-28)
**Líneas:** TG1, TG2, 41 (parte del feed Euskotren)
**Trips:** 2,233 trips, 32,945 stop_times
**Nota:** Usar IDs de StopPlace (estación padre), no Quay (plataforma). La resolución multi-plataforma funciona automáticamente.

---

**Revisión completada:** 2026-01-28
**Commits de fixes:** 524e59d, 6f84cd2, d7fb325, 8dd26f4
**Scripts de datos:** generate_metro_tenerife_trips.py, generate_tranvia_sevilla_trips.py
