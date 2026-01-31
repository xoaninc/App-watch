# FGC - Problema de Correspondencias

## Estado del GTFS oficial

**URL:** https://www.fgc.cat/google/google_transit.zip

**Archivos disponibles (8):**
- agency.txt
- calendar_dates.txt
- feed_info.txt
- routes.txt
- shapes.txt
- stop_times.txt
- stops.txt
- trips.txt

**NO tiene:**
- transfers.txt
- pathways.txt

## Problema

El GTFS de FGC **no contiene transfers.txt**, por lo tanto no hay datos oficiales de correspondencias/transbordos.

Sin embargo, en la base de datos existían 30 correspondencias relacionadas con FGC cuyo origen es desconocido:
- 26 con source='manual'
- 4 con source='osm'

No se sabe de dónde salieron estos datos manuales ni con qué criterio se crearon.

## Estructura de estaciones

El GTFS de FGC tiene estructura padre/hijo correcta en stops.txt:
- Estaciones padre (location_type=1): PC, PR, GR, PE, etc.
- Plataformas hijo (location_type=0): PC1, PC2, GR1, GR2, PE1, PE2, etc.

Ejemplo:
```
PC (Plaça Catalunya) - padre
├── PC1 - plataforma 1
├── PC2 - plataforma 2
├── PC3 - plataforma 3
├── PC4 - plataforma 4
└── PC5 - plataforma 5
```

## Correspondencias que existían (origen desconocido)

### Resumen por Intercambiador

| Intercambiador | Correspondencias | Source | Estado |
|----------------|------------------|--------|--------|
| **Catalunya (FGC_PC ↔ TMB/RENFE)** | 6 | manual | ❌ Errores 107-434% |
| **Espanya (FGC_PE* ↔ TMB)** | 20 | manual | ⚠️ Mixto (23-160%) |
| **Provença (FGC_PR1 ↔ TMB)** | 4 | osm | ✅ Correctas |

### Lista Completa (30 total)

| ID | FROM | TO | DIST_BD | DIST_REAL | SOURCE | ESTADO |
|----|------|-----|---------|-----------|--------|--------|
| 316 | FGC_PC | RENFE_78805 | 50m | 267m | manual | ❌ 434% |
| 309 | FGC_PC | TMB_METRO_1.126 | 100m | 207m | manual | ❌ 107% |
| 311 | FGC_PC | TMB_METRO_1.326 | 50m | 137m | manual | ❌ 174% |
| 333 | FGC_PE | TMB_METRO_1.122 | 100m | 116m | manual | ✅ OK |
| 335 | FGC_PE | TMB_METRO_1.321 | 200m | 260m | manual | ⚠️ 30% |
| 355 | FGC_PE1 | TMB_METRO_1.122 | 150m | 116m | manual | ⚠️ 23% |
| 357 | FGC_PE1 | TMB_METRO_1.321 | 100m | 260m | manual | ❌ 160% |
| 359 | FGC_PE2 | TMB_METRO_1.122 | 150m | 116m | manual | ⚠️ 23% |
| 361 | FGC_PE2 | TMB_METRO_1.321 | 100m | 260m | manual | ❌ 160% |
| 363 | FGC_PE3 | TMB_METRO_1.122 | 150m | 116m | manual | ⚠️ 23% |
| 365 | FGC_PE3 | TMB_METRO_1.321 | 100m | 260m | manual | ❌ 160% |
| 367 | FGC_PE4 | TMB_METRO_1.122 | 150m | 116m | manual | ⚠️ 23% |
| 369 | FGC_PE4 | TMB_METRO_1.321 | 100m | 260m | manual | ❌ 160% |
| 114 | FGC_PR1 | TMB_METRO_1.328 | 378m | 380m | osm | ✅ OK |
| 116 | FGC_PR1 | TMB_METRO_1.521 | 189m | 192m | osm | ✅ OK |
| 317 | RENFE_78805 | FGC_PC | 50m | 267m | manual | ❌ 434% |
| 332 | TMB_METRO_1.122 | FGC_PE | 100m | 116m | manual | ✅ OK |
| 354 | TMB_METRO_1.122 | FGC_PE1 | 150m | 116m | manual | ⚠️ 23% |
| 358 | TMB_METRO_1.122 | FGC_PE2 | 150m | 116m | manual | ⚠️ 23% |
| 362 | TMB_METRO_1.122 | FGC_PE3 | 150m | 116m | manual | ⚠️ 23% |
| 366 | TMB_METRO_1.122 | FGC_PE4 | 150m | 116m | manual | ⚠️ 23% |
| 308 | TMB_METRO_1.126 | FGC_PC | 100m | 207m | manual | ❌ 107% |
| 334 | TMB_METRO_1.321 | FGC_PE | 200m | 260m | manual | ⚠️ 30% |
| 356 | TMB_METRO_1.321 | FGC_PE1 | 100m | 260m | manual | ❌ 160% |
| 360 | TMB_METRO_1.321 | FGC_PE2 | 100m | 260m | manual | ❌ 160% |
| 364 | TMB_METRO_1.321 | FGC_PE3 | 100m | 260m | manual | ❌ 160% |
| 368 | TMB_METRO_1.321 | FGC_PE4 | 100m | 260m | manual | ❌ 160% |
| 310 | TMB_METRO_1.326 | FGC_PC | 50m | 137m | manual | ❌ 174% |
| 113 | TMB_METRO_1.328 | FGC_PR1 | 378m | 380m | osm | ✅ OK |
| 115 | TMB_METRO_1.521 | FGC_PR1 | 189m | 192m | osm | ✅ OK |

### Problema con Espanya

Hay correspondencias redundantes: FGC_PE, FGC_PE1, FGC_PE2, FGC_PE3, FGC_PE4 todos tienen correspondencias con TMB.
Solo debería haber correspondencia FGC_PE ↔ TMB (el padre), no los hijos.

## Estado actual

| BD | Correspondencias FGC | Estado |
|----|---------------------|--------|
| **Local (dev)** | 0 | ✅ Eliminadas (2026-01-30) |
| **Producción** | 52 | ❌ Pendiente eliminar |

### Diferencia dev vs producción

Producción tiene 22 correspondencias adicionales que son **intra-estación** (erróneas):
- FGC_PE ↔ FGC_PE1/PE2/PE3/PE4 (padre ↔ hijos)
- FGC_PE1 ↔ FGC_PE2 ↔ FGC_PE3 ↔ FGC_PE4 (entre hermanos)
- FGC_PR ↔ TRAM_BARCELONA_1001 (400m)

Estas correspondencias intra-estación NO deberían existir - los transbordos dentro de la misma estación se gestionan con la estructura parent_station del GTFS.

## Correspondencias Barcelona (sin FGC)

| Operadores | Total | Con walking_shape (OSRM) |
|------------|-------|--------------------------|
| TMB_METRO, TRAM_BARCELONA, RENFE | 96 | 0 |

Ninguna correspondencia de Barcelona tiene rutas OSRM (walking_shape = NULL).

## Estructura FGC en BD

| Tipo | Count | Fuente |
|------|-------|--------|
| Estaciones padre (location_type=1) | 104 | GTFS oficial |
| Plataformas hijo (location_type=0) | 198 | GTFS oficial |

La estructura padre/hijo viene directamente del GTFS de FGC y gestiona los transbordos **intra-estación** automáticamente.

## Solución propuesta

TODO: Definir de dónde deben provenir las correspondencias FGC:
1. Calcular por proximidad (<250m)
2. Importar desde OSM stop_area_group
3. Definir manualmente con datos verificados

Ver `FGC_FIX.md` cuando se implemente la solución.
