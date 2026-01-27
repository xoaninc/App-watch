# Plan de Accion: RAPTOR In-Memory Optimization

**Estado:** APROBADO - Revision de experto
**Fecha:** 2026-01-28
**Objetivo:** Reducir tiempo de respuesta de ~7s a <500ms
**Tiempo estimado:** 6 horas

---

## RIESGO CRITICO IDENTIFICADO

El `gtfs_store.py` actual agrupa trips por `route_id`. **RAPTOR no funciona con rutas, funciona con PATTERNS** (secuencias unicas de paradas).

**Ejemplo del problema:**
- La linea METRO_1 tiene Direccion A y Direccion B
- Si las metes todas en `trips_by_route`, el algoritmo intentara subirse a un tren que va en direccion contraria

**Solucion:** Agrupar trips por su secuencia exacta de paradas (pattern).

---

## Resumen de Horas

| Hora | Descripcion | Archivos | Test |
|------|-------------|----------|------|
| 1 | Corregir GTFSStore con patterns | `gtfs_store.py` | Estructura OK |
| 2 | Limpiar raptor.py (quitar SQL) | `raptor.py` | Import OK |
| 3 | Ajustar _scan_pattern y get_earliest_trip | `raptor.py` | Logica OK |
| 4 | Integracion y reconstruccion | `raptor.py`, `app.py` | Health OK |
| 5 | Testing rapido | - | curl tests |
| 6 | Deploy a produccion | - | Server OK |

---

## Hora 1: Corregir GTFSStore (Implementar Patterns)

### Objetivo
Modificar `gtfs_store.py` para agrupar trips por pattern (secuencia exacta de paradas).

### Cambios en `__init__`

**ANTES (incorrecto):**
```python
self.trips_by_route: Dict[str, List[Tuple[int, str]]] = {}
self.routes_by_stop: Dict[str, Set[str]] = defaultdict(set)
```

**DESPUES (correcto):**
```python
# Clave: pattern_id (str), Valor: Lista de tuplas (departure_time, trip_id)
self.trips_by_pattern: Dict[str, List[Tuple[int, str]]] = {}

# Clave: pattern_id, Valor: Lista ordenada de stop_ids
self.stops_by_pattern: Dict[str, List[str]] = {}

# Clave: stop_id, Valor: Set de pattern_ids (NO route_ids)
self.patterns_by_stop: Dict[str, Set[str]] = defaultdict(set)
```

### Logica de construccion de patterns (en `_do_load`)

```python
print("  Construyendo Patterns (Rutas unicas)...")

# 1. Agrupar trips por su secuencia exacta de paradas
# { (route_id, tuple_stops): [trip_ids...] }
temp_patterns = defaultdict(list)

for trip_id, stops_data in self.stop_times_by_trip.items():
    if not stops_data:
        continue

    # Extraer solo IDs para la firma
    stop_sequence = tuple(s[0] for s in stops_data)
    route_id = self.trips_info[trip_id][0]  # route_id esta en index 0

    temp_patterns[(route_id, stop_sequence)].append(trip_id)

# 2. Crear estructuras finales
for i, ((route_id, stop_seq), trips) in enumerate(temp_patterns.items()):
    # Crear un ID unico para el pattern
    pattern_id = sys.intern(f"{route_id}_{i}")

    self.stops_by_pattern[pattern_id] = list(stop_seq)

    # Indexar que patterns pasan por cada parada
    for stop_id in stop_seq:
        self.patterns_by_stop[stop_id].add(pattern_id)

    # Guardar trips de este pattern ordenados por hora
    trip_list = []
    for t_id in trips:
        # Obtener hora de salida de la PRIMERA parada del pattern
        first_departure = self.stop_times_by_trip[t_id][0][2]  # index 2 = departure
        trip_list.append((first_departure, t_id))

    trip_list.sort(key=lambda x: x[0])
    self.trips_by_pattern[pattern_id] = trip_list

print(f"    {len(self.trips_by_pattern):,} patterns creados")
```

### Test
```bash
python -c "
from src.gtfs_bc.routing.gtfs_store import GTFSStore
store = GTFSStore.get_instance()
assert hasattr(store, 'trips_by_pattern')
assert hasattr(store, 'stops_by_pattern')
assert hasattr(store, 'patterns_by_stop')
print('Estructura OK')
"
```

### Criterio de exito
- [x] `trips_by_pattern` existe y es Dict[str, List] ✓ commit 596d267
- [x] `stops_by_pattern` existe y es Dict[str, List] ✓ commit 596d267
- [x] `patterns_by_stop` mapea stop_id a set de pattern_ids ✓ commit 596d267

---

## Hora 2: Limpiar raptor.py (Quitar SQL)

### Objetivo
Eliminar todas las queries SQL de `raptor.py`. Usar `gtfs_store` singleton.

### Cambios principales

**1. Imports - AÑADIR:**
```python
from src.gtfs_bc.routing.gtfs_store import gtfs_store
```

**2. `__init__` - SIMPLIFICAR:**
```python
def __init__(self, db: Session = None):
    self.db = db  # Mantener para compatibilidad
    self.store = gtfs_store
    # ELIMINAR: self._stops, self._routes, self._route_patterns, etc.
```

**3. `_load_data` - ELIMINAR O VACIAR:**
```python
def _load_data(self, travel_date, origin_stop_id=None, destination_stop_id=None):
    pass  # Ya no necesita cargar nada
```

**4. `_get_relevant_networks` - ELIMINAR:**
El grafo hace el filtrado naturalmente por accesibilidad.

### Test
```bash
python -c "
from src.gtfs_bc.routing.raptor import RaptorAlgorithm
r = RaptorAlgorithm()
print('Import OK')
"
```

### Criterio de exito
- [x] RaptorAlgorithm se puede instanciar sin db ✓ commit f6f2cf3
- [x] No hay queries SQL en el archivo (excepto comentarios) ✓ commit f6f2cf3

---

## Hora 3: Ajustar _scan_pattern y get_earliest_trip

### Objetivo
Modificar `_scan_route` a `_scan_pattern`. Trabajar con tuplas del store.

### Cambios en `_run_raptor`

```python
def _run_raptor(self, origin, dest, dep_time, rounds):
    # Obtener servicios activos HOY desde el Store
    active_services = self.store.get_active_services(self.travel_date)

    for k in range(1, rounds + 1):
        # PASO 1: Escanear Patterns (antes Routes)
        patterns_to_scan = set()
        for stop_id in marked_stops:
            # USAR STORE:
            patterns_to_scan.update(self.store.patterns_by_stop.get(stop_id, set()))

        for pattern_id in patterns_to_scan:
            # Obtener stops del pattern del Store
            stops = self.store.stops_by_pattern[pattern_id]

            # Chequear si tocamos una marked stop
            if not any(s in marked_stops for s in stops):
                continue

            # Obtener trips del Store
            trips = self.store.trips_by_pattern[pattern_id]

            # Llamar a scan_pattern
            self._scan_pattern(pattern_id, stops, trips, active_services, ...)

        # PASO 2: Transbordos
        for stop_id in marked_stops:
            transfers = self.store.get_transfers(stop_id)
            for to_stop, walk_sec in transfers:
                # ... logica normal ...
```

### Cambios en `_find_earliest_trip`

**ANTES (objetos Trip):**
```python
for trip in trips:
    for st in trip.stop_times:
        if st.stop_id == stop_id:
            if st.departure_seconds >= min_departure:
                return trip
```

**DESPUES (tuplas del store):**
```python
def _find_earliest_trip(self, trips_list, min_time, active_services):
    # trips_list viene de store.trips_by_pattern[pid]
    # Es [(dep_time, trip_id), ...]

    for dep_time, trip_id in trips_list:
        if dep_time >= min_time:
            # Validar servicio activo
            trip_info = self.store.get_trip_info(trip_id)
            if trip_info and trip_info[2] in active_services:  # index 2 es service_id
                return trip_id
    return None
```

### Nota sobre FIFO
Para ahorrar tiempo, inicialmente asumimos FIFO. Si hay tiempo en Hora 5, implementar verificacion de hora exacta en cada parada.

### Criterio de exito
- [x] `_scan_pattern` usa `store.stops_by_pattern` ✓ commit 670a501
- [x] `_find_earliest_trip` trabaja con tuplas ✓ commit 670a501
- [x] Verifica `active_services` con lazy check ✓ commit 670a501

**PENDIENTE REVISIÓN DEL USUARIO**

---

## Hora 4: Integracion y Reconstruccion

### Objetivo
Verificar startup y ajustar reconstruccion de journeys.

### Verificar startup en `app.py`
Ya esta configurado en `gtfs_rt_scheduler.py`:
```python
@asynccontextmanager
async def lifespan_with_scheduler(app):
    # Startup: Load GTFS data into memory first
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_gtfs_store)
    ...
```

### Ajustar reconstruccion (`_extract_journeys`)

Usar store para obtener info de trips y rutas:
```python
# Para obtener headsign:
trip_info = self.store.get_trip_info(trip_id)
headsign = trip_info[1] if trip_info else None

# Para obtener short_name y color:
route_info = self.store.get_route_info(route_id)
short_name = route_info[0] if route_info else ""
color = route_info[1] if route_info else None
```

### Test
```bash
curl http://localhost:8080/health
# Debe retornar: {"status": "healthy", "gtfs_store": {"loaded": true, ...}}
```

### Criterio de exito
- [ ] Health check retorna `loaded: true`
- [ ] Journey legs tienen headsign y route info

---

## Hora 5: Testing Rapido

### Tests con curl

```bash
# 1. Health check
curl http://localhost:8080/health

# 2. Ruta simple (Metro Sevilla)
curl "http://localhost:8080/api/v1/route-planner?origin=METRO_SEV_T1_1&dest=METRO_SEV_T1_22&time=08:00"

# 3. Ruta multimodal (RENFE + Metro)
curl "http://localhost:8080/api/v1/route-planner?origin=RENFE_71801&dest=METRO_SEV_T1_22&time=08:00"
```

### Errores tipicos

| Error | Causa | Solucion |
|-------|-------|----------|
| `KeyError` | ID no cargado | Verificar carga de patterns |
| `AttributeError: .stop_times` | Usando objeto en vez de ID | Cambiar a tuplas |
| `TypeError: unhashable` | Lista en vez de tupla | Usar `tuple()` |

### Benchmark
```bash
for i in {1..10}; do
    time curl -s "http://localhost:8080/api/v1/route-planner?origin=METRO_SEV_T1_1&dest=METRO_SEV_T1_22&time=08:00" > /dev/null
done
```

### Criterio de exito
- [ ] Health retorna OK
- [ ] Rutas simples funcionan
- [ ] Rutas multimodales funcionan
- [ ] Tiempo < 500ms

---

## Hora 6: Deploy a Produccion

### Pasos

```bash
# 1. Limpiar prints de debug (opcional)

# 2. Commit
git add -A
git commit -m "feat: RAPTOR in-memory optimization with patterns"
git push

# 3. Sincronizar archivos
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.venv' --exclude='venv' --exclude='node_modules' \
  --exclude='.env' --exclude='*.db' --exclude='*.sqlite' \
  --exclude='alembic.bak' --exclude='.idea' --exclude='.vscode' \
  /Users/juanmaciasgomez/Projects/renfeserver/ root@juanmacias.com:/var/www/renfeserver/

# 4. Reiniciar servicio
ssh root@juanmacias.com "systemctl restart renfeserver"

# 5. Verificar logs (esperar ~30-60s para carga)
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

## Rollback Plan

Si algo falla en produccion:

```bash
# Revertir al commit anterior
git revert HEAD
git push

# Re-deploy
rsync ...
ssh root@juanmacias.com "systemctl restart renfeserver"
```

---

## Checklist Final

- [x] Hora 1: GTFSStore con patterns - commit 596d267
- [x] Hora 2: raptor.py sin SQL - commit f6f2cf3
- [ ] Hora 3: _scan_pattern ajustado - commit 670a501 (pendiente revisión)
- [ ] Hora 4: Integracion OK - commit
- [ ] Hora 5: Tests OK
- [ ] Hora 6: Deploy exitoso
- [ ] Documentacion actualizada
