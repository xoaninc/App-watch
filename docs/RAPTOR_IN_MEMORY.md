# RAPTOR In-Memory Optimization

**Estado:** En implementación
**Fecha:** 2026-01-28
**Revisado por:** Experto externo ✓

---

## Resumen

Optimización del algoritmo RAPTOR para usar datos en memoria (RAM) en lugar de queries SQL por petición.

| Métrica | Antes | Después |
|---------|-------|---------|
| Tiempo respuesta | ~7s | <500ms |
| Memoria servidor | ~200MB | ~500MB |
| Tiempo startup | ~1s | ~45s |
| Queries SQL/request | ~10 | 0 |

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                     SERVER STARTUP (~30-60s)                │
│  ┌─────────────┐     ┌─────────────┐     ┌──────────────┐  │
│  │ PostgreSQL  │────▶│ GTFSStore   │────▶│ RAM (~400MB) │  │
│  │ (una vez)   │     │ singleton   │     │ (persistente)│  │
│  └─────────────┘     └─────────────┘     └──────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     CADA REQUEST (<500ms)                   │
│  ┌─────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │ Cliente │────▶│ /route-planner│────▶│ RAPTOR       │     │
│  └─────────┘     └──────────────┘     │ (usa RAM)    │     │
│                                       └──────┬───────┘     │
│                                              │             │
│                                              ▼             │
│                                       ┌─────────────┐      │
│                                       │ GTFSStore   │      │
│                                       │ O(1) access │      │
│                                       └─────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Decisiones de Diseño

### 1. Patterns vs Routes

**Problema:** En GTFS, una `route_id` es una agrupación comercial (ej: "Línea 1"). Puede tener trips con diferentes secuencias de paradas (express, locales, cortos).

**Solución:** Crear **patterns** que agrupan trips con la misma secuencia exacta de paradas.

```
GTFS Route "L1" → Pattern 0 (todas las paradas)
                → Pattern 1 (express, salta paradas)
                → Pattern 2 (servicio corto)
```

**Razón:** RAPTOR asume que si te subes en parada i y te bajas en j, el viaje es válido. Si mezclas trips con diferentes paradas, esta asunción se rompe.

### 2. No filtrar por Network/Ciudad

**Problema:** ¿Filtrar datos geográficamente (solo Sevilla) para reducir scope?

**Solución:** NO filtrar. Cargar todo.

**Razón:**
- RAPTOR ignora automáticamente las "islas" desconectadas (Madrid nunca se explora si empiezas en Sevilla)
- Filtrar causa "efecto frontera" (rutas metropolitanas cortadas)
- El grafo hace el filtrado naturalmente por accesibilidad

### 3. Lazy Check para Servicios Activos

**Problema:** ¿Pre-filtrar 260k trips por servicio activo, o verificar durante búsqueda?

**Solución:** Verificar durante búsqueda (lazy check).

```python
# En get_earliest_trip()
if service_id in active_services_set:  # O(1) set lookup
    return trip_id
```

**Razón:**
- Set lookup es O(1) (nanosegundos)
- RAPTOR solo explora ~5% de las rutas
- Pre-filtrar procesa 100% innecesariamente

### 4. No asumir FIFO

**Problema:** ¿Asumir que trips salen en el mismo orden en todas las paradas?

**Solución:** NO asumir. Verificar hora real en cada parada.

**Razón:** Trenes express pueden adelantar a locales. RENFE tiene paradas de regulación de 15+ minutos.

### 5. Matrices Paralelas (arrivals/departures)

**Problema:** ¿Guardar tiempos como tuplas `(arr, dep)` o solo departure?

**Solución:** Dos matrices separadas.

```python
pattern = {
    'departures': [[28800, 29100], [28900, 29200]],  # Para verificar boarding
    'arrivals':   [[28750, 29000], [28850, 29150]],  # Para calcular llegada
}
```

**Razón:**
- Tuplas tienen overhead de objeto (~100MB extra)
- Solo departure falla con RENFE (paradas largas)
- Matrices de enteros son cache-friendly

**Optimización:** Para Metro (arrival ≈ departure), apuntar ambas a la misma lista:
```python
if arrivals_equal_departures:
    pattern['arrivals'] = pattern['departures']  # Sin duplicar
```

### 6. Pattern ID como Entero

**Problema:** ¿Usar string "METRO_1_dir0" o entero como ID?

**Solución:** Enteros auto-incrementales (0, 1, 2...).

**Razón:**
- Hash de entero es instantáneo (el hash de 150 es 150)
- Hash de string recorre caracteres
- Permite usar Lista en vez de Dict: `patterns[150]` vs `patterns.get("METRO_1_dir0")`

---

## Estructuras de Datos

### Pattern (elemento de la lista `patterns`)

```python
{
    'id': 0,                          # Entero auto-incremental
    'route_id': 'METRO_1',            # String original para UI
    'stops': ('STOP_A', 'STOP_B'),    # Tupla de stop_ids ordenada
    'departures': [                   # [trip_idx][stop_idx] = departure_sec
        [28800, 29100, 29500],        # Trip 0
        [28900, 29200, 29600],        # Trip 1
    ],
    'arrivals': [                     # [trip_idx][stop_idx] = arrival_sec
        [28750, 29000, 29400],        # Trip 0 (puede apuntar a departures)
        [28850, 29100, 29500],        # Trip 1
    ],
    'trips_meta': [                   # [(trip_id, service_id), ...]
        ('trip_001', 'SERVICE_L'),
        ('trip_002', 'SERVICE_L'),
    ]
}
```

### GTFSStore (singleton)

```python
class GTFSStore:
    # Datos principales para RAPTOR
    patterns: List[dict]                    # Indexado por pattern_id
    patterns_by_stop: Dict[str, List[int]]  # stop_id → [pattern_ids]
    transfers: Dict[str, List[Tuple]]       # stop_id → [(to_stop, secs)]

    # Calendarios
    services_by_weekday: Dict[str, Set[str]]  # 'monday' → {service_ids}
    calendar_exceptions: Dict[str, Dict]       # date → {added, removed}

    # Metadata para UI
    stops_info: Dict[str, Tuple]    # stop_id → (name, lat, lon)
    routes_info: Dict[str, Tuple]   # route_id → (short_name, color, type)
```

### Acceso en RAPTOR

```python
# 1. Obtener patterns que pasan por una parada
pattern_ids = store.patterns_by_stop[stop_id]  # O(1)

# 2. Acceder a un pattern
pattern = store.patterns[pattern_id]  # O(1) array access

# 3. Buscar trip más temprano en una parada
stop_idx = pattern['stops'].index(stop_id)
for trip_idx, (trip_id, service_id) in enumerate(pattern['trips_meta']):
    dep_time = pattern['departures'][trip_idx][stop_idx]
    if dep_time >= min_time and service_id in active_services:
        return trip_id

# 4. Obtener tiempo de llegada
arrival = pattern['arrivals'][trip_idx][target_stop_idx]
```

---

## Archivos

| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `src/gtfs_bc/routing/gtfs_store.py` | ✅ Creado | Singleton (pendiente actualizar estructura) |
| `src/gtfs_bc/routing/raptor.py` | ⏳ Pendiente | Modificar para usar GTFSStore |
| `src/gtfs_bc/routing/__init__.py` | ✅ Actualizado | Exports |
| `app.py` | ✅ Actualizado | Health check + admin endpoint |
| `gtfs_rt_scheduler.py` | ✅ Actualizado | Carga GTFSStore en startup |

---

## Optimizaciones Aplicadas

| Técnica | Impacto | Ubicación |
|---------|---------|-----------|
| `sys.intern()` | -20-30% RAM en strings | `gtfs_store.py` |
| `gc.freeze()` | Reduce overhead GC | `gtfs_store.py` |
| Lista vs Dict para patterns | Acceso O(1) real | `gtfs_store.py` |
| Matrices paralelas | Cache-friendly | Pattern structure |
| Lazy service check | Evita pre-filtrado | `get_earliest_trip()` |
| Arrivals = Departures ref | -50% RAM para Metro | Pattern load |

---

## Próximos Pasos

1. [ ] Actualizar `gtfs_store.py` con estructura de patterns
2. [ ] Implementar carga de patterns durante startup
3. [ ] Modificar `raptor.py` para usar GTFSStore
4. [ ] Tests de rendimiento
5. [ ] Deploy a producción

---

## Referencias

- Paper original RAPTOR: "Round-Based Public Transit Routing" (Delling et al., 2012)
- Decisiones revisadas por experto externo (2026-01-28)
