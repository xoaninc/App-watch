# Estado de Datos: Accesos y Vestíbulos por Operador

**Última actualización:** 2026-01-29

---

## Resumen Ejecutivo

| Operador | Stops | Accesos | Vestíbulos | Andenes | Fuente | Estado |
|----------|-------|---------|------------|---------|--------|--------|
| Metro Madrid | 242 | 799 | 344 | 1,169 | CRTM ArcGIS | ✅ Completo |
| Metro Ligero | 56 | 27 | 16 | 162 | CRTM ArcGIS | ✅ Completo |
| TMB Metro Barcelona | 2,809 | 504 | - | 199 | GTFS | ✅ Completo |
| Renfe Cercanías | 1,034 | 0 | 0 | 797 | - | ⏳ Pendiente |
| Euskotren | 798 | 149 | - | - | GTFS opendata.euskadi.eus | ✅ Completo |
| FGC | 302 | 0 | 0 | 413 | GTFS + Geotren | ❌ Accesos / ✅ Shapes + Geotren |
| Metro Bilbao | 191 | 107 | - | - | data.ctb.eus GTFS | ✅ Completo |
| Metro Valencia | 144 | 0 | 0 | 149 | - | ⏳ Pendiente |

---

## Credenciales API

**Archivo:** `.env.local` (gitignored, no se sube al repo)

### TMB Barcelona
- Variables: `TMB_APP_ID`, `TMB_APP_KEY`
- Aplicación: "WatchTrans"
- Portal: https://developer.tmb.cat

### NAP (Punto de Acceso Nacional)
- Variables: `NAP_USER`, `NAP_PASSWORD`
- Portal: https://nap.transportes.gob.es

---

## Operadores Completados

### 1. Metro de Madrid ✅

**Fuente:** CRTM ArcGIS Feature Service
```
https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M4_Red/FeatureServer
```

**Layers:**
| Layer | Nombre | Registros |
|-------|--------|-----------|
| 1 | M4_Accesos | 799 |
| 2 | M4_Vestibulos | 344 |
| 3 | M4_Andenes | ~300 |
| 4 | M4_Tramos | ~540 |
| 5 | M4_ParadasPorItinerario | ~540 |

**Datos importados:**
- 799 accesos con coordenadas, horarios, accesibilidad
- 344 vestíbulos con tipo, torniquetes, horarios
- 1,169 andenes con líneas y coordenadas
- Shapes con geometría real de vías
- Stop times con tiempos reales (distancia/velocidad)

**Script:** N/A (importación manual previa)

**Integración RAPTOR:** ✅ 799 accesos como puntos virtuales

**Fecha:** 2026-01-28

---

### 2. Metro Ligero Madrid ✅

**Fuente:** CRTM ArcGIS Feature Service
```
https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/Red_MetroLigero/FeatureServer
```

**Layers:**
| Layer | Nombre | Registros |
|-------|--------|-----------|
| 1 | Accesos | 27 |
| 2 | Vestíbulos | 16 |
| 3 | Andenes | 107 |
| 4 | Tramos | 100 |

**Datos importados:**
- 27 accesos
- 16 vestíbulos
- 162 andenes (107 CRTM + existentes)
- 8 shapes con 4,342 puntos

**Script:** `scripts/import_metro_ligero_crtm.py`

**Notas:**
- Mapeo especial: CRTM código 10 → ML_24 (Colonia Jardín)
- ML4 (Parla) es línea circular

**Integración RAPTOR:** ✅ 27 accesos añadidos (total 826)

**Fecha:** 2026-01-29

---

## Operadores con Script Listo

### 3. TMB Metro Barcelona ✅

**Fecha completado:** 2026-01-29

**Fuente de datos:** GTFS (no API REST)

**URL GTFS:**
```
https://api.tmb.cat/v1/static/datasets/gtfs.zip?app_id={APP_ID}&app_key={APP_KEY}
```

**Datos importados:**

| Tipo | Cantidad |
|------|----------|
| Accesos totales | 504 |
| Ascensores | 151 |
| Estaciones con accesos | 127 |

**Script:** `scripts/import_tmb_accesses.py`

**Integración RAPTOR:** ✅ 504 accesos como puntos virtuales

**Estado:** ✅ Completo

---

## Operadores Pendientes Investigación

### 4. FGC (Ferrocarrils de la Generalitat) ❌ Accesos / ✅ Shapes / ✅ Geotren

**Investigación completada:** 2026-01-29

**GTFS:** `https://www.fgc.cat/google/google_transit.zip`
- ❌ Sin location_type=2 (entradas)
- ❌ Sin pathways.txt
- Solo tiene: 198 plataformas, 104 estaciones

**Open Data:** https://dadesobertes.fgc.cat/ (56 datasets)
- ❌ `informacio-tecnica-accessos`: Es de estaciones de esquí, no tren
- ❌ `accesibilidad-itinerarios`: Rutas accesibles (texto), sin coordenadas
- ✅ `gtfs_shapes`: 11,591 shape points - **IMPORTADO**
- ✅ `posicionament-dels-trens` (Geotren): Posiciones + ocupación - **IMPORTADO**
- ✅ GTFS-RT: Ya consumimos (236 posiciones en BD)

---

#### Shapes FGC

**Importados:** 2026-01-29

| Dato | Cantidad |
|------|----------|
| Shapes | 42 |
| Puntos | 11,591 |
| Rutas con shapes | 20/21 |

**Script:** `scripts/import_fgc_shapes.py`

**Comando:**
```bash
source .venv/bin/activate && python scripts/import_fgc_shapes.py
```

---

#### Geotren (Posicionamiento + Ocupación)

**Fuente:** https://dadesobertes.fgc.cat/explore/dataset/posicionament-dels-trens/

**Campos disponibles:**

| Campo | Descripción |
|-------|-------------|
| `ut` | ID del tren |
| `lin` | Línea (S1, S2, L6, R5, etc.) |
| `dir` | Dirección (D=down, A=up) |
| `origen` / `desti` | Estación origen/destino |
| `estacionat_a` | Estación actual |
| `en_hora` | Puntualidad |
| `geo_point_2d` | Coordenadas lat/lon |
| `ocupacio_mi_percent` | Ocupación vagón medio (%) |
| `ocupacio_ri_percent` | Ocupación vagón trasero (%) |
| `ocupacio_m1_percent` | Ocupación motor 1 (%) |
| `ocupacio_m2_percent` | Ocupación motor 2 (%) |

**Tabla BD:** `fgc_geotren_positions`

**Migración:** `039_create_fgc_geotren_table.py`

**Script:** `scripts/import_fgc_geotren.py`

**Comando:**
```bash
source .venv/bin/activate && python scripts/import_fgc_geotren.py
```

**Nota:** Los campos de ocupación pueden estar NULL fuera de horario de servicio.

**Integración `/departures`:** ✅ Completada (2026-01-29)

La ocupación de FGC se muestra en el endpoint `/departures` cuando está disponible:
- Los GTFS-RT trip_ids no coinciden con los GTFS estáticos
- Fallback implementado: consulta `fgc_geotren_positions` por línea
- Campos mostrados: `occupancy_percentage`, `occupancy_per_car` [mi, ri, m1, m2]

**Ejemplo respuesta `/api/v1/gtfs/stops/FGC_BN/departures`:**
```json
{
  "route_short_name": "S2",
  "occupancy_status": 0,
  "occupancy_percentage": 5,
  "occupancy_per_car": [5, 5, 5, 5]
}
```

---

**Conclusión FGC:**
- ❌ NO tienen datos de accesos físicos disponibles
- ✅ Shapes importados correctamente (42 shapes, 11,591 puntos)
- ✅ Geotren configurado para posiciones con ocupación
- ✅ Ocupación integrada en `/departures` endpoint

---

### 5. Euskotren ✅

**Fecha completado:** 2026-01-29

**Fuente GTFS:** `https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfs_euskotren.zip`

**Datos importados:**

| Tipo | Cantidad |
|------|----------|
| Stops | 798 |
| Accesos (location_type=2) | 149 |
| Shapes | 115 |
| Shape points | 60,886 |
| Trips | 11,088 |
| Stop times | 159,736 |

**GTFS-RT:** ✅ Posiciones, retrasos, alertas

**Integración RAPTOR:** ✅ 149 accesos añadidos

**Notas:**
- GTFS tiene location_type=2 (entradas) con coordenadas
- Shapes ya estaban importados (no requerían prefijo EUSKOTREN_)
- Accesos importados a `stop_access` desde gtfs_stops

**Estado:** ✅ Completo

---

### 6. Metro Bilbao ✅

**Fecha completado:** 2026-01-29

**Portal GTFS-RT:** https://data.ctb.eus/eu/dataset/horario-metro-bilbao

**Portal GTFS Oficial:** https://www.metrobilbao.eus/es/open-data/dataset/horarios (GTFS más actualizado)

**URLs actualizadas:**
| Tipo | URL |
|------|-----|
| GTFS (oficial) | `https://www.metrobilbao.eus/es/open-data/dataset/horarios` (descargar manualmente) |
| GTFS (CTB) | `https://ctb-gtfs.s3.eu-south-2.amazonaws.com/metrobilbao.zip` (puede estar desactualizado) |
| GTFS-RT Positions | `https://ctb-gtfs-rt.s3.eu-south-2.amazonaws.com/metro-bilbao-vehicle-positions.pb` |
| GTFS-RT Updates | `https://ctb-gtfs-rt.s3.eu-south-2.amazonaws.com/metro-bilbao-trip-updates.pb` |
| GTFS-RT Alerts | `https://ctb-gtfs-rt.s3.eu-south-2.amazonaws.com/metro-bilbao-service-alerts.pb` |

**Datos importados:**

| Tipo | Cantidad |
|------|----------|
| Accesos (location_type=2) | 107 |
| Shapes | 33 |
| Shape points | 13,271 |
| Trips | 10,675 |
| Stop times | 274,586 |

**Script:** `scripts/import_metro_bilbao_data.py`

**Comando:**
```bash
source .venv/bin/activate && python scripts/import_metro_bilbao_data.py
```

**Notas:**
- URLs antiguas de opendata.euskadi.eus ya no funcionan (redirigen a S3 con Access Denied)
- GTFS-RT en data.ctb.eus (Consorcio de Transportes de Bizkaia)
- **GTFS estático: usar siempre la web oficial de Metro Bilbao** (más actualizado que CTB)
- GTFS tiene location_type=2 (entradas) con coordenadas
- 42 estaciones con 107 accesos totales

**Integración RAPTOR:** ✅ 107 accesos añadidos (total 1,437)

---

### 7. Renfe Cercanías ⏳

**Fuentes potenciales:**
- NAP España: https://nap.transportes.gob.es/
- ADIF datos abiertos

**Investigar:**
- [ ] Datos ADIF de estaciones
- [ ] Información de accesibilidad Renfe

**Estado:** Pendiente investigación

---

### 8. Metro Valencia (FGV) ⏳

**Fuentes potenciales:**
- NAP: Descargar GTFS
- GVA Datos Abiertos

**Estado:** Pendiente investigación

---

## Scripts Disponibles

| Script | Operador | Función |
|--------|----------|---------|
| `import_metro_ligero_crtm.py` | Metro Ligero | Importa accesos, vestíbulos, andenes, shapes |
| `import_tmb_accesses.py` | TMB Barcelona | Importa entradas desde GTFS |
| `import_fgc_shapes.py` | FGC | Importa shapes desde GTFS (42 shapes, 11,591 puntos) |
| `import_fgc_geotren.py` | FGC | Importa posiciones Geotren con ocupación |
| `import_metro_madrid_shapes.py` | Metro Madrid | Importa shapes desde CRTM ArcGIS |
| `import_metro_bilbao_data.py` | Metro Bilbao | Importa accesos, shapes, trips desde data.ctb.eus |

---

## Estructura de Tablas

### stop_access
```sql
CREATE TABLE stop_access (
    id SERIAL PRIMARY KEY,
    stop_id VARCHAR(100) NOT NULL,  -- FK a gtfs_stops
    name VARCHAR(255),
    lat FLOAT,
    lon FLOAT,
    street VARCHAR(255),
    street_number VARCHAR(20),
    opening_time TIME,
    closing_time TIME,
    wheelchair BOOLEAN,
    level INTEGER,
    source VARCHAR(50)
);
```

### stop_vestibule
```sql
CREATE TABLE stop_vestibule (
    id SERIAL PRIMARY KEY,
    stop_id VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    lat FLOAT,
    lon FLOAT,
    level INTEGER,
    vestibule_type VARCHAR(50),
    turnstile_type VARCHAR(50),
    opening_time TIME,
    closing_time TIME,
    wheelchair BOOLEAN,
    source VARCHAR(50)
);
```

### fgc_geotren_positions
```sql
CREATE TABLE fgc_geotren_positions (
    id VARCHAR(100) PRIMARY KEY,
    vehicle_id VARCHAR(100),       -- ut (ID del tren)
    line VARCHAR(20),              -- lin (S1, S2, L6...)
    direction VARCHAR(10),         -- dir (D/A)
    origin VARCHAR(50),            -- origen
    destination VARCHAR(50),       -- desti
    next_stops TEXT,               -- properes_parades
    stationed_at VARCHAR(50),      -- estacionat_a
    on_time BOOLEAN,               -- en_hora
    unit_type VARCHAR(50),         -- tipus_unitat
    latitude FLOAT,
    longitude FLOAT,
    -- Ocupación por vagón
    occupancy_mi_percent FLOAT,    -- Vagón medio %
    occupancy_mi_level VARCHAR(20),
    occupancy_ri_percent FLOAT,    -- Vagón trasero %
    occupancy_ri_level VARCHAR(20),
    occupancy_m1_percent FLOAT,    -- Motor 1 %
    occupancy_m1_level VARCHAR(20),
    occupancy_m2_percent FLOAT,    -- Motor 2 %
    occupancy_m2_level VARCHAR(20),
    timestamp TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## Integración RAPTOR

Los accesos se cargan como puntos virtuales en el algoritmo RAPTOR:

**Código:** `src/gtfs_bc/routing/gtfs_store.py` (paso 9)

**Funcionamiento:**
1. Se crean IDs virtuales: `ACCESS_{id}`
2. Se añaden a `stops_info` con coordenadas
3. Se generan transfers bidireccionales acceso ↔ plataforma
4. Tiempo de caminata: distancia / 1.25 m/s (4.5 km/h)
5. Mínimo 30 segundos por acceso

**Operadores integrados:**

| Operador | Accesos | Transfers | Estado |
|----------|---------|-----------|--------|
| Metro Madrid | 799 | ~1,598 | ✅ |
| TMB Barcelona | 504 | ~1,008 | ✅ |
| Metro Ligero | 27 | ~54 | ✅ |
| **TOTAL** | **1,330** | **~2,538** | |

---

## API Endpoint

### GET /api/v1/gtfs/accesses/by-coordinates

Busca accesos de metro cercanos a unas coordenadas. Devuelve el `raptor_id` para usar en rutas.

**Parámetros:**
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| lat | float | requerido | Latitud |
| lon | float | requerido | Longitud |
| radius | int | 500 | Radio de búsqueda en metros (50-2000) |
| limit | int | 20 | Máximo de resultados (1-100) |

**Ejemplo Madrid (Sol):**
```bash
curl "http://localhost:8000/api/v1/gtfs/accesses/by-coordinates?lat=40.4168&lon=-3.7038&radius=500"
```

**Ejemplo Barcelona (Bellvitge):**
```bash
curl "http://localhost:8000/api/v1/gtfs/accesses/by-coordinates?lat=41.3508&lon=2.1108&radius=500"
```

**Respuesta:**
```json
[
  {
    "id": 702,
    "raptor_id": "ACCESS_702",
    "stop_id": "METRO_12",
    "stop_name": "Sol",
    "name": "Ascensor",
    "lat": 40.4185,
    "lon": -3.7031,
    "distance_m": 202,
    "wheelchair": null,
    "is_elevator": true
  }
]
```

**Uso en route-planner:**
```bash
curl "http://localhost:8000/api/v1/gtfs/route-planner?from=ACCESS_702&to=METRO_1"
```

---

## Plan de Acción

### Fase 1: TMB Barcelona ✅ COMPLETADO
1. [x] Ejecutar `import_tmb_accesses.py --dry-run`
2. [x] Verificar mapeo de IDs TMB → nuestros stops (504/504 OK)
3. [x] Script funciona correctamente
4. [x] Importación real ejecutada (504 accesos)
5. [x] Integración RAPTOR completada

**Comando para re-importar:**
```bash
source .venv/bin/activate && export $(grep -v '^#' .env.local | xargs) && python scripts/import_tmb_accesses.py
```

### Fase 2: Otros operadores GTFS-RT
1. [x] FGC - Shapes importados, Geotren + ocupación integrada ✅
2. [ ] Euskotren - Verificar GTFS
3. [ ] Metro Bilbao - Verificar GTFS

### Fase 3: Operadores sin GTFS-RT
1. [ ] Metro Valencia
2. [ ] Metro Granada/Málaga/Tenerife
3. [ ] Tranvías

### Fase 4: Renfe Cercanías
1. [ ] Investigar datos ADIF
2. [ ] Evaluar si hay información de accesos

---

## Historial de Cambios

| Fecha | Cambio |
|-------|--------|
| 2026-01-29 | Creación documento |
| 2026-01-29 | Metro Ligero completado |
| 2026-01-29 | TMB investigado, script creado |
| 2026-01-29 | Actualización credenciales TMB |
| 2026-01-29 | TMB script verificado: 504 accesos, 151 ascensores |
| 2026-01-29 | TMB importado e integrado en RAPTOR (1,330 accesos totales) |
| 2026-01-29 | **Nuevo endpoint** `/accesses/by-coordinates` unificado |
| 2026-01-29 | FGC investigado: NO tiene accesos (shapes sí disponibles) |
| 2026-01-29 | FGC shapes importados: 42 shapes, 11,591 puntos |
| 2026-01-29 | FGC Geotren: tabla creada, script importación listo |
| 2026-01-29 | **FGC ocupación integrada en `/departures`** (fallback por línea) |
| 2026-01-29 | FGC Geotren: tabla y script para posiciones con ocupación |
| 2026-01-29 | **Metro Bilbao**: URLs actualizadas a data.ctb.eus |
| 2026-01-29 | **Metro Bilbao**: 107 accesos importados desde GTFS |
| 2026-01-29 | **Metro Bilbao**: 33 shapes, 13,271 puntos importados |
| 2026-01-29 | **Metro Bilbao**: Trips y stop_times importados (2,572 trips) |
| 2026-01-29 | **Metro Bilbao**: Fix departures endpoint (incluir parent station en query) |
| 2026-01-29 | **Metro Bilbao**: Fix RAPTOR resolve_stop_to_platforms (incluir parent + children) |
| 2026-01-29 | **Metro Bilbao**: Fix GTFS store access transfers (conectar a parent + children) |
| 2026-01-29 | **Metro Bilbao**: Desplegado a producción - departures + GTFS-RT + RAPTOR funcionando |
| 2026-01-29 | **Euskotren**: 149 accesos importados desde GTFS (location_type=2) |
| 2026-01-29 | **Euskotren**: Fix GTFS store para cargar accesos EUSKOTREN_% |
| 2026-01-29 | **Euskotren**: Shapes ya existían (115 shapes, 60,886 puntos) |
| 2026-01-29 | **Euskotren**: Desplegado - departures + GTFS-RT + RAPTOR + accesos funcionando |
