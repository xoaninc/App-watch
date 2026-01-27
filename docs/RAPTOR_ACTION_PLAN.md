# Plan de Accion: RAPTOR In-Memory Optimization

**Estado:** Pendiente de aprobacion
**Fecha:** 2026-01-28
**Objetivo:** Reducir tiempo de respuesta de ~7s a <500ms

---

## Resumen de Fases

| Fase | Descripcion | Test | Archivos |
|------|-------------|------|----------|
| 1 | Actualizar GTFSStore con estructura patterns | Unit tests | `gtfs_store.py` |
| 2 | Implementar carga de patterns en startup | Health check | `gtfs_store.py` |
| 3 | Modificar RAPTOR para usar GTFSStore | Integration test | `raptor.py` |
| 4 | Eliminar filtrado por network | Route planner API | `raptor.py` |
| 5 | Tests de rendimiento | Benchmark | - |
| 6 | Deploy a produccion | Servidor | - |

---

## Fase 1: Actualizar GTFSStore con estructura patterns

### Objetivo
Cambiar la estructura de datos de `trips_by_route` a `patterns` con matrices paralelas.

### Cambios en `gtfs_store.py`

**Estructura ACTUAL (incorrecta):**
```python
trips_by_route: Dict[str, List[Tuple[int, str]]]  # {route_id: [(dep_sec, trip_id)]}
stop_times_by_trip: Dict[str, List[Tuple[str, int, int]]]  # {trip_id: [(stop_id, arr, dep)]}
routes_by_stop: Dict[str, Set[str]]  # {stop_id: {route_ids}}
```

**Estructura NUEVA (correcta):**
```python
# Estructura principal para RAPTOR
patterns: List[dict]  # Indexado por pattern_id (entero)
# Cada pattern:
# {
#     'id': int,
#     'route_id': str,
#     'stops': tuple,  # (stop_id, stop_id, ...)
#     'departures': List[List[int]],  # [trip_idx][stop_idx] = dep_seconds
#     'arrivals': List[List[int]],    # [trip_idx][stop_idx] = arr_seconds
#     'trips_meta': List[Tuple[str, str]]  # [(trip_id, service_id), ...]
# }

patterns_by_stop: Dict[str, List[int]]  # {stop_id: [pattern_ids]}
transfers: Dict[str, List[Tuple[str, int]]]  # {from_stop: [(to_stop, secs)]}
```

### Test
```bash
# Unit test: verificar que patterns se construyen correctamente
python -c "
from src.gtfs_bc.routing.gtfs_store import GTFSStore
store = GTFSStore.get_instance()
# Verificar estructura
assert hasattr(store, 'patterns')
assert hasattr(store, 'patterns_by_stop')
print('Estructura OK')
"
```

### Criterio de exito
- [ ] `patterns` es List[dict]
- [ ] `patterns_by_stop` mapea stop_id a lista de pattern_ids (enteros)
- [ ] Cada pattern tiene 'stops', 'departures', 'arrivals', 'trips_meta'

---

## Fase 2: Implementar carga de patterns en startup

### Objetivo
Cargar patterns desde PostgreSQL al iniciar el servidor (una vez).

### Algoritmo de carga

```python
def _load_patterns(self, db_session):
    """
    1. Cargar todos los trips con sus stop_times
    2. Agrupar trips por secuencia exacta de paradas -> pattern
    3. Para cada pattern:
       - Crear matriz departures[trip_idx][stop_idx]
       - Crear matriz arrivals[trip_idx][stop_idx]
       - Si arrivals == departures (Metro), apuntar a misma lista
    4. Construir patterns_by_stop inverso
    """
```

### Query SQL optimizada
```sql
SELECT t.id, t.route_id, t.service_id,
       st.stop_id, st.arrival_seconds, st.departure_seconds, st.stop_sequence
FROM gtfs_trips t
JOIN gtfs_stop_times st ON t.id = st.trip_id
ORDER BY t.id, st.stop_sequence
```

### Test
```bash
# Verificar carga via health endpoint
curl http://localhost:8080/health
# Debe retornar: {"status": "healthy", "gtfs_store": {"loaded": true, ...}}
```

### Criterio de exito
- [ ] Health check retorna `loaded: true`
- [ ] `stats` muestra numero de patterns
- [ ] Tiempo de carga ~30-60 segundos

---

## Fase 3: Modificar RAPTOR para usar GTFSStore

### Objetivo
Eliminar queries SQL de `raptor.py`, usar GTFSStore en su lugar.

### Cambios principales

**ANTES (SQL por request):**
```python
class RaptorAlgorithm:
    def __init__(self, db: Session):
        self.db = db

    def _load_data(self, travel_date, origin, dest):
        # Queries SQL...
        stops = self.db.query(StopModel).all()
        trips = self.db.query(TripModel).filter(...).all()
```

**DESPUES (GTFSStore):**
```python
class RaptorAlgorithm:
    def __init__(self, db: Session = None):  # db opcional para compatibilidad
        self.store = GTFSStore.get_instance()

    def plan(self, origin, dest, departure_time, travel_date):
        active_services = self.store.get_active_services(travel_date)
        # Usar self.store.patterns, self.store.patterns_by_stop, etc.
```

### Cambios en _scan_route()

**ANTES:**
```python
for trip in trips:
    for st in trip.stop_times:
        if st.stop_id == stop_id:
            if st.departure_seconds >= min_departure:
                return trip
```

**DESPUES:**
```python
pattern = self.store.patterns[pattern_id]
stop_idx = pattern['stops'].index(stop_id)
for trip_idx, (trip_id, service_id) in enumerate(pattern['trips_meta']):
    if service_id not in active_services:
        continue
    if pattern['departures'][trip_idx][stop_idx] >= min_departure:
        return trip_idx
```

### Test
```bash
# Integration test: comparar resultados antes/despues
curl "http://localhost:8080/api/v1/route-planner?origin=METRO_SEV_T1_1&dest=METRO_SEV_T1_22&time=08:00"
# Debe retornar journeys validos
```

### Criterio de exito
- [ ] API retorna mismos resultados que antes
- [ ] Tiempo de respuesta < 1 segundo
- [ ] Sin queries SQL en logs (excepto startup)

---

## Fase 4: Eliminar filtrado por network

### Objetivo
Remover `_get_relevant_networks()` y filtrado geografico.

### Razon
RAPTOR ignora automaticamente las "islas" desconectadas. Si empiezas en Sevilla, nunca exploraras paradas de Madrid porque no hay conexion.

### Cambios
```python
# ELIMINAR:
def _get_relevant_networks(self, origin_stop_id, destination_stop_id):
    ...

# ELIMINAR parametros:
def _load_data(self, travel_date, origin_stop_id=None, destination_stop_id=None):
    relevant_networks = self._get_relevant_networks(...)  # ELIMINAR
```

### Test
```bash
# Probar rutas multimodales (RENFE + Metro)
curl "http://localhost:8080/api/v1/route-planner?origin=RENFE_71801&dest=METRO_SEV_T1_22&time=08:00"
```

### Criterio de exito
- [ ] Rutas multimodales funcionan
- [ ] Sin efecto frontera en rutas metropolitanas

---

## Fase 5: Tests de rendimiento

### Benchmark
```bash
# Medir tiempo de respuesta (10 requests)
for i in {1..10}; do
    time curl -s "http://localhost:8080/api/v1/route-planner?origin=METRO_SEV_T1_1&dest=METRO_SEV_T1_22&time=08:00" > /dev/null
done
```

### Metricas objetivo
| Metrica | Antes | Objetivo |
|---------|-------|----------|
| Tiempo respuesta | ~7s | <500ms |
| Memoria servidor | ~200MB | <600MB |
| CPU durante request | Alto | Bajo |

### Criterio de exito
- [ ] Tiempo promedio < 500ms
- [ ] Sin timeout en 10 requests consecutivos

---

## Fase 6: Deploy a produccion

### Comandos de deploy

```bash
# 1. Sincronizar archivos
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.venv' --exclude='venv' --exclude='node_modules' \
  --exclude='.env' --exclude='*.db' --exclude='*.sqlite' \
  --exclude='alembic.bak' --exclude='.idea' --exclude='.vscode' \
  /Users/juanmaciasgomez/Projects/renfeserver/ root@juanmacias.com:/var/www/renfeserver/

# 2. Reiniciar servicio
ssh root@juanmacias.com "systemctl restart renfeserver"

# 3. Verificar logs
ssh root@juanmacias.com "journalctl -u renfeserver -f"
```

### Verificacion post-deploy
```bash
# Health check en produccion
curl https://api.juanmacias.com/health

# Test route planner
curl "https://api.juanmacias.com/api/v1/route-planner?origin=METRO_SEV_T1_1&dest=METRO_SEV_T1_22&time=08:00"
```

### Criterio de exito
- [ ] Health retorna `loaded: true`
- [ ] Route planner responde < 500ms
- [ ] Sin errores en logs

---

## Dependencias entre fases

```
Fase 1 (estructura)
    |
    v
Fase 2 (carga)
    |
    v
Fase 3 (RAPTOR)
    |
    v
Fase 4 (network)  <-- Puede hacerse en paralelo con Fase 5
    |
    v
Fase 5 (benchmark)
    |
    v
Fase 6 (deploy)
```

---

## Rollback Plan

Si algo falla en produccion:

```bash
# Revertir al commit anterior
git revert HEAD

# Re-deploy
rsync ...
ssh root@juanmacias.com "systemctl restart renfeserver"
```

---

## Notas importantes

1. **No asumir FIFO**: Verificar hora real de departure en cada parada
2. **Lazy service check**: Verificar service_id durante busqueda, no pre-filtrar
3. **Pattern IDs enteros**: Usar List en lugar de Dict para acceso O(1)
4. **Matrices paralelas**: arrivals y departures separados (pueden compartir referencia para Metro)

---

## Checklist final

- [ ] Fase 1 completada y commiteada
- [ ] Fase 2 completada y commiteada
- [ ] Fase 3 completada y commiteada
- [ ] Fase 4 completada y commiteada
- [ ] Fase 5 benchmark OK
- [ ] Fase 6 deploy exitoso
- [ ] Documentacion actualizada
