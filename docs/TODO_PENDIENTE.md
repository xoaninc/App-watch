# TODO - Tareas Pendientes

**Última actualización:** 2026-01-27 06:00

---

## Estado Actual

### Funcionando en Producción ✅

| Feature | Estado | Endpoint |
|---------|--------|----------|
| Platforms | ✅ | `GET /stops/{stop_id}/platforms` |
| Correspondences | ✅ | `GET /stops/{stop_id}/correspondences` |
| Shapes | ✅ COMPLETO | `GET /routes/{route_id}/shape` |

### Shapes - Estado por Red

| Red | Shapes | Puntos | Estado |
|-----|--------|--------|--------|
| TMB Metro Barcelona | 290 | 103,248 | ✅ Funciona |
| SFM Mallorca | 243 | 257,515 | ✅ Importado 2026-01-26 |
| Renfe Cercanías | 118 | 74,420 | ✅ Funciona (variantes de ruta) |
| Euskotren | 115 | 60,886 | ✅ Funciona |
| Metro Ligero Madrid | 38 | 61,816 | ✅ Funciona |
| **Metro Madrid** | 30 | 57,474 | ✅ **Importado 2026-01-27** (15 líneas x 2 dir) |
| Metro Bilbao | 33 | 13,271 | ✅ Funciona |
| FGC | 42 | 11,591 | ✅ Funciona |
| Tranvía Murcia | 3 | 989 | ✅ L1 circular + L1B bidireccional |
| Metro Málaga | 4 | 260 | ✅ Importado 2026-01-26 |
| Tranvía Zaragoza | 2 | 252 | ✅ Importado 2026-01-26 |
| Metro Tenerife | 4 | 132 | ✅ Importado 2026-01-26 |
| Metro Sevilla | 2 | 212 | ✅ OSM sin depot 2026-01-26 |
| TRAM Barcelona | 12 | 5,136 | ✅ Extraído de OSM 2026-01-26 |
| Metro Granada | 2 | 52 | ✅ Bidireccional 2026-01-27 |
| Metrovalencia | 20 | 11,390 | ✅ Extraído de OSM 2026-01-26 (10 líneas x 2 dir) |
| TRAM Alicante | 12 | 6,858 | ✅ Extraído de OSM 2026-01-26 (6 líneas x 2 dir) |
| Tranvía Sevilla (Metrocentro) | 2 | 552 | ✅ Extraído de OSM 2026-01-27 |

**Total en producción:** 949 shapes, 650,332 puntos
**Trips con shape:** 239,225
**Trips sin shape:** 1,218 (trips huérfanos)

---

## Tareas Completadas (2026-01-27)

### ✅ Fix Bug Departures - Metro Sevilla/Granada (05:30)

**Bug:** El endpoint `/stops/{stop_id}/departures` devolvía `[]` para Metro Sevilla y Granada.

**Causa raíz:** El filtro `is_route_operating()` comprobaba si `current_seconds` estaba dentro del horario de servicio. Si consultabas a las 5:20 AM y el servicio empezaba a las 6:30 AM, se filtraban TODAS las salidas aunque fueran válidas para más tarde.

**Fix:** Cambiar de `is_route_operating(db, route.id, current_seconds, day_type)` a `is_route_operating(db, route.id, stop_time.departure_seconds, day_type)` - ahora comprueba si la hora de SALIDA está dentro del horario, no la hora actual.

**Archivo:** `adapters/http/api/gtfs/routers/query_router.py` línea 1076

**Commit:** `5b6713d`

**Resultado:**
```bash
# Antes del fix
curl ".../stops/METRO_SEV_L1_E1/departures"  # → []

# Después del fix
curl ".../stops/METRO_SEV_L1_E1/departures"  # → 6:30 Olivar de Quintos, 6:50 Pablo de Olavide...
curl ".../stops/METRO_GRANADA_1/departures"  # → 6:31:30 Armilla, 6:38:30 Armilla...
```

### ✅ Tests Unitarios RAPTOR (04:50)

Creada estructura de tests con pytest:

```
tests/
├── __init__.py
├── conftest.py
├── unit/
│   └── routing/
│       └── test_raptor.py  # 19 tests para data structures
└── integration/
    └── gtfs/
        └── test_route_planner.py  # 14 tests (skip sin DB)
```

**Tests unitarios:** 19 pasando (StopTime, Trip, Transfer, RoutePattern, Label, Journey, JourneyLeg, Constants)

**Tests integración:** 14 tests (se saltan automáticamente sin BD, activar con `SKIP_INTEGRATION_TESTS=0`)

### ✅ Cleanup Código Legacy (04:30)

- Eliminado `src/gtfs_bc/routing/routing_service.py` (Dijkstra legacy ~16KB)
- Limpiado `Makefile` (quitadas referencias frontend)
- Actualizado `__init__.py` y `query_router.py` para quitar imports de RoutingService

### ✅ Metro Madrid - Importación Completa

Importados shapes desde GTFS oficial de CRTM (Consorcio Regional de Transportes de Madrid):

| Dato | Valor |
|------|-------|
| Shapes | 30 (15 líneas × 2 direcciones) |
| Puntos | 57,474 |
| Trips | 18 |
| Fuente | `https://crtm.maps.arcgis.com/sharing/rest/content/items/5c7f2951962540d69ffe8f640d94c246/data` |

**Shape IDs:** `METRO_MAD_4__1____1__IT_1` (L1 ida), `METRO_MAD_4__1____2__IT_1` (L1 vuelta), etc.

**Nota:** La documentación anterior decía incorrectamente que el GTFS de Metro Madrid no tenía shapes. El GTFS SÍ incluye shapes.txt con 57k puntos.

### ✅ Shapes Bidireccionales Arreglados

| Red | Antes | Después | Acción |
|-----|-------|---------|--------|
| Metro Granada | 1 shape | 2 shapes | Creado reverse |
| TRAM Barcelona (real) | 1 shape/ruta | 2 shapes/ruta | Asignados shapes OSM a trips reales |
| Tranvía Murcia L1B | 1 shape | 2 shapes | Creado reverse |

### ✅ Tranvía Sevilla (Metrocentro) - Añadido

Extraído desde OSM (tracks `railway=tram`):
- 2 shapes (ida/vuelta)
- 552 puntos
- Shape IDs: `TRAM_SEV_T1_OSM`, `TRAM_SEV_T1_OSM_REV`

### ✅ Metro Granada - Importación Completa de Horarios

Importados trips y stop_times desde GTFS del NAP:

| Dato | Valor |
|------|-------|
| Trips | 5,693 |
| Stop times | 143,098 |
| Calendar entries | 4 + 17 (excepciones) |
| Calendar dates | 34 |
| Fuente | NAP ID 1370 |

**Script:** `scripts/import_metro_granada_gtfs.py`

**Fix aplicado:** El script ahora crea entradas dummy en `gtfs_calendar` para service_ids que solo existen en `calendar_dates.txt` (servicios de días festivos específicos).

**Endpoints funcionando:**
```bash
# Salidas
curl "https://juanmacias.com/api/v1/gtfs/stops/METRO_GRANADA_1/departures"
# → 06:31:30 -> Armilla, 06:38:30 -> Armilla, ...

# Route planner
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_GRANADA_1&to=METRO_GRANADA_26"
# → Success: true, 1 journey
```

---

## Tareas Completadas (2026-01-26)

### ✅ Shapes de Metros Secundarios

Importados automáticamente desde NAP usando credenciales de `.env.local`:

| Red | NAP ID | Shapes | Puntos |
|-----|--------|--------|--------|
| Metro Málaga | 1296 | 4 | 260 |
| Metro Granada | 1370 | 2 | 784 |
| Metrovalencia | 967 | 20 | 900 |
| Tranvía Zaragoza | 1394 | 2 | 252 |
| Tranvía Murcia | 1371 | 2 | 634 |
| TRAM Alicante | 966 | 12 | 2,719 |
| SFM Mallorca | 1071 | 243 | 257,515 |
| Metro Tenerife | URL directa | 4 | 132 |

**Nota:** Metro Sevilla (NAP ID 1385, no 1583) tiene el archivo shapes.txt pero está VACÍO (solo header). Se extrajeron de OSM.

### ✅ Shapes de OSM (Metro Sevilla, TRAM Barcelona, Tranvía Sevilla)

Extraídos desde OpenStreetMap usando Overpass API:

| Red | Shapes | Puntos | Fuente OSM |
|-----|--------|--------|------------|
| TRAM Barcelona | 12 | 5,136 | Relations T1-T6 (ida/vuelta) |
| Metro Sevilla | 2 | 1,227 | Relations L1 (ida/vuelta) |
| Tranvía Sevilla (Metrocentro) | 2 | 552 | Tracks railway=tram (2026-01-27) |

**IDs de shapes OSM:**
- `TRAM_BCN_T1_4666995`, `TRAM_BCN_T1_4666996` (T1 ida/vuelta)
- `TRAM_BCN_T2_4666997`, `TRAM_BCN_T2_4666998` (T2 ida/vuelta)
- `TRAM_BCN_T3_4666999`, `TRAM_BCN_T3_4667000` (T3 ida/vuelta)
- `TRAM_BCN_T4_4665781`, `TRAM_BCN_T4_4665782` (T4 ida/vuelta)
- `TRAM_BCN_T5_4665783`, `TRAM_BCN_T5_4665784` (T5 ida/vuelta)
- `TRAM_BCN_T6_4665785`, `TRAM_BCN_T6_4665786` (T6 ida/vuelta)
- `METRO_SEV_L1_255088`, `METRO_SEV_L1_7781388` (L1 ida/vuelta)
- `TRAM_SEV_T1_OSM`, `TRAM_SEV_T1_OSM_REV` (Metrocentro T1 ida/vuelta)

### ✅ Correspondencias Estaciones Principales (TODAS LAS CIUDADES)

#### Barcelona

| Estación | Conexiones |
|----------|------------|
| Catalunya | TMB L1 ↔ FGC ↔ RENFE, TMB L3 ↔ FGC ↔ RENFE |
| Passeig de Gràcia | TMB L2/L4 ↔ RENFE, TMB L3 ↔ RENFE |
| Sants Estació | TMB L3 ↔ RENFE, TMB L5 ↔ RENFE |
| Arc de Triomf | TMB L1 ↔ RENFE |
| Espanya | TMB L1 ↔ FGC, TMB L3 ↔ FGC |
| Sagrera | TMB L1 ↔ L5 ↔ L9N/L10N ↔ RENFE |
| Clot | TMB L1 ↔ L2 ↔ RENFE |

#### Madrid

| Estación | Conexiones |
|----------|------------|
| Sol | Metro L1 ↔ L2 ↔ L3 ↔ RENFE C3/C4 |
| Nuevos Ministerios | Metro L6 ↔ L8 ↔ L10 ↔ RENFE |
| Atocha | Metro L1 ↔ RENFE |
| Chamartín | Metro L1 ↔ L10 ↔ RENFE |
| Príncipe Pío | Metro L6 ↔ L10 ↔ RENFE |
| Méndez Álvaro | Metro L6 ↔ RENFE |

#### Bilbao

| Estación | Conexiones |
|----------|------------|
| Abando | Metro Bilbao L1/L2 ↔ RENFE ↔ Euskotren |
| Casco Viejo | Metro Bilbao L1/L2 ↔ Euskotren |

#### Valencia

| Estación | Conexiones |
|----------|------------|
| Àngel Guimerà | Metrovalencia L1/L2/L5 ↔ RENFE |

#### Sevilla

| Estación | Conexiones |
|----------|------------|
| San Bernardo | Metro Sevilla L1 ↔ RENFE |

### ✅ Limpieza de Datos Erróneos

- Eliminadas 22 correspondencias inválidas entre ciudades (ej: Zaragoza Delicias ↔ Madrid Metro, distancia >350km)
- Eliminadas 6 paradas mal asignadas a rutas:
  - RENFE_4040 (Zaragoza) en C10 Madrid
  - RENFE_54501 (Victoria Kent Málaga) en R3 Barcelona
  - METRO_285 (T4 Madrid) en C1 Málaga
  - ML_59 (Metro Ligero) en C3 Madrid
  - RENFE_5436 (Asturias) en C2 Santander
  - RENFE_71602 (Calafell costa) en RL4 interior

### ✅ Platforms Verificados para Estaciones Principales

Añadidos platforms para Sagrera (L1, L5, L9N/L10N). Verificados todos los intercambiadores principales tienen platforms con coordenadas.

### ✅ Fix headsign CIVIS (2026-01-26)

735 trips tenían headsign "CIVIS" en lugar del destino real. CIVIS es un servicio semi-directo de Renfe, no un destino.

**Fix:** Actualizado headsign con la última parada del viaje (destino real).

| Ruta | Destinos reales |
|------|-----------------|
| C1 Valencia | València Estació del Nord |
| C1 Asturias | Llamaquique, Gijón Sanz Crespo |
| C1 Alicante | Alacant Terminal |
| C2 Madrid | Chamartín RENFE, Guadalajara |
| C3 Madrid | Chamartín RENFE, Aranjuez |
| C3 Asturias | Avilés, Llamaquique |
| C4 Bilbao | Ametzola |
| C6 Valencia | València, Castelló de la Plana, Vila-real |
| C10 Madrid | Villalba de Guadarrama, Chamartín RENFE |

### ✅ Fix headsigns vacíos y correspondencias huérfanas (2026-01-26)

- **155,834 trips** sin headsign → rellenados con nombre de última parada
- **6 correspondencias huérfanas** Euskotren → eliminadas (IDs malformados con `::` doble)
- **3,369 trips** sin stop_times → no afectan API (orphan data del GTFS original)

### ✅ Plataformas completadas para todas las paradas (2026-01-26)

Añadidas 403 plataformas faltantes usando coordenadas GTFS:

| Red | Añadidas | Total |
|-----|----------|-------|
| FGC | +359 | 412 |
| TMB Barcelona | +24 | 199 |
| Metro Madrid | +13 | 570 |
| Tram Sevilla | +7 | 179 |

**Nota:** FGC_PC (Plaça Catalunya) añadido como estación padre con todas las líneas (L6, L7, S1, S2).

**Total plataformas en producción:** 2,989

### ✅ Limpieza de Shapes Corruptos (2026-01-26)

Los shapes importados del NAP usaban IDs numéricos simples (1, 2, 3...) que colisionaron entre redes:

**Problema detectado:**
- Shape ID "1" tenía puntos de Granada (lat 37.14), Valencia (lat 39.62) y Alicante - saltos de 400+ km
- Shape IDs 1-10 afectados en Metro Granada, Metrovalencia y TRAM Alicante

**Acciones tomadas:**
1. Nullificados shape_id en 22,331 trips afectados
2. Eliminados 4,140 puntos de shapes corruptos
3. Creado shape de Metro Granada desde coordenadas de estaciones (26 puntos)
4. Enlazados trips de TRAM Barcelona a shapes OSM existentes (3,195 trips)
5. Metro Sevilla: filtrado para excluir área de cocheras (depot) - de 272 a 212 puntos

### ✅ Shapes de Metrovalencia y TRAM Alicante desde OSM (2026-01-26)

Extraídos desde OpenStreetMap usando Overpass API con shapes bidireccionales:

**Metrovalencia (10 líneas, 20 shapes):**
| Línea | Shape IDA | Shape VUELTA | Puntos |
|-------|-----------|--------------|--------|
| L1 | METRO_VAL_L1_5622354 | METRO_VAL_L1_5622924 | 3,357 |
| L2 | METRO_VAL_L2_5622180 | METRO_VAL_L2_5625922 | 1,472 |
| L3 | METRO_VAL_L3_5622355 | METRO_VAL_L3_5625981 | 1,269 |
| L4 | METRO_VAL_L4_5620862 | METRO_VAL_L4_5620871 | 1,598 |
| L5 | METRO_VAL_L5_5622154 | METRO_VAL_L5_5626066 | 606 |
| L6 | METRO_VAL_L6_5621993 | METRO_VAL_L6_5622028 | 802 |
| L7 | METRO_VAL_L7_5616613 | METRO_VAL_L7_5626067 | 664 |
| L8 | METRO_VAL_L8_5622077 | METRO_VAL_L8_5622078 | 194 |
| L9 | METRO_VAL_L9_5626068 | METRO_VAL_L9_5626069 | 1,058 |
| L10 | METRO_VAL_L10_14166106 | METRO_VAL_L10_14166107 | 342 |

**TRAM Alicante (6 líneas, 12 shapes):**
| Línea | Shape IDA | Shape VUELTA | Puntos |
|-------|-----------|--------------|--------|
| L1 | TRAM_ALI_L1_190196 | TRAM_ALI_L1_6269076 | 2,018 |
| L2 | TRAM_ALI_L2_190199 | TRAM_ALI_L2_6563046 | 597 |
| L3 | TRAM_ALI_L3_190203 | TRAM_ALI_L3_6266776 | 655 |
| L4 | TRAM_ALI_L4_190184 | TRAM_ALI_L4_6266683 | 548 |
| L5 | TRAM_ALI_L5_13154071 | TRAM_ALI_L5_14193223 | 506 |
| L9 | TRAM_ALI_L9_404372 | TRAM_ALI_L9_15320667 | 2,565 |

**Asignación de shapes:** Cada trip se asigna al shape de IDA o VUELTA basándose en la comparación de los números de estación de origen y destino.

### Resumen Base de Datos (2026-01-27 20:00)

| Datos | Total |
|-------|-------|
| Trips RAPTOR-ready | 260,038 (100%) |
| Platforms | 2,989 |
| Correspondencias | 218 |
| Trips con shape | 239,225 |
| Shape points | 650,332 |
| Shapes | 949 |

---

## Tareas Pendientes

### Backend API

| Tarea | Prioridad | Estado |
|-------|-----------|--------|
| Route planner Cercanías | Alta | ✅ Funciona |
| Route planner Metro Granada | Alta | ✅ Funciona |
| Route planner Euskotren | Alta | ✅ Funciona |
| `?compact=true` en departures | Media | ✅ Completado |
| **Fix calendarios FGC/TMB** | Alta | ✅ **COMPLETADO** |
| **Generar stop_times Metro Madrid** | Alta | ✅ Ejecutado en producción |
| **Generar stop_times Metro Sevilla** | Alta | ✅ Ejecutado en producción |
| **Vincular shapes Metro Madrid** | Media | ✅ 19,658 trips (2026-01-27) |
| Optimizar queries con índices BD | Baja | ✅ **Migración 035** |
| **Generar stop_times Metro Ligero MAD** | Baja | ⏳ Pendiente (ver sección abajo) |

---

## ✅ Optimización de Índices BD (2026-01-28)

### Migración 035: Query Optimization Indexes

**Estado:** ✅ Migración creada, pendiente de ejecutar en producción

**Índices creados (10 nuevos):**

| Índice | Tabla | Columnas | Uso |
|--------|-------|----------|-----|
| `ix_stop_times_stop_departure_trip` | gtfs_stop_times | (stop_id, departure_seconds, trip_id) | Departures query |
| `ix_routes_network_short_name` | gtfs_routes | (network_id, short_name) | Routes filtering |
| `ix_route_frequency_route_day_time` | gtfs_route_frequency | (route_id, day_type, start_time) | Frequency lookups |
| `ix_platform_history_stop_route_date` | gtfs_rt_platform_history | (stop_id, route_short_name, observation_date) | Platform prediction |
| `ix_stop_time_updates_stop_trip` | gtfs_rt_stop_time_updates | (stop_id, trip_id) | RT delay lookups |
| `ix_trips_route_service` | gtfs_trips | (route_id, service_id) | Estimated positions |
| `ix_stop_route_sequence_stop` | gtfs_stop_route_sequence | (stop_id, route_id, sequence) | Reverse route lookup |
| `ix_calendar_date_range` | gtfs_calendar | (start_date, end_date) | Calendar filtering |
| `ix_calendar_dates_date_exception` | gtfs_calendar_dates | (date, exception_type) | Service exceptions |
| `ix_stops_location_parent` | gtfs_stops | (location_type, parent_station_id) | Station filtering |

**Índices existentes (migración 033):**
- `ix_trips_service_id` - gtfs_trips (service_id)
- `ix_stop_times_trip_sequence` - gtfs_stop_times (trip_id, stop_sequence)
- `ix_stop_correspondence_from_stop` - stop_correspondence (from_stop_id)
- `ix_calendar_dates_service` - gtfs_calendar_dates (service_id)
- `ix_stop_times_stop_departure` - gtfs_stop_times (stop_id, departure_seconds)

**Impacto estimado:**
- Departures endpoint: ~800ms → ~100ms (10x mejora)
- Routes endpoint: ~200ms → ~30ms (7x mejora)
- Calendar filtering: ~100ms → ~10ms (10x mejora)

**Ejecución:**
```bash
# En producción
cd /var/www/renfeserver
source venv/bin/activate
alembic upgrade head
sudo systemctl restart renfeserver
```

---

## ⏳ Tareas Pendientes de Baja Prioridad

### Metro Ligero Madrid - Script de Generación de Stop Times

**Estado:** ⏳ Pendiente (baja prioridad, el sistema funciona sin esto)

**Problema:** Metro Ligero Madrid usa `frequencies.txt` en su GTFS en lugar de `stop_times.txt` completos. Actualmente tiene ~3,001 trips pero RAPTOR necesita stop_times individuales para cada trip para funcionar de forma óptima.

**Solución necesaria:** Crear un script similar a:
- `scripts/generate_metro_madrid_from_gtfs.py`
- `scripts/generate_metro_sevilla_trips.py`

**Líneas de Metro Ligero:**
- ML1: Pinar de Chamartín ↔ Las Tablas
- ML2: Colonia Jardín ↔ Estación de Aravaca
- ML3: Colonia Jardín ↔ Puerta de Boadilla

**Fuente GTFS:** CRTM (Consorcio Regional de Transportes de Madrid)
- URL: `https://crtm.maps.arcgis.com/sharing/rest/content/items/5c7f2951962540d69ffe8f640d94c246/data`

**Notas:**
- El GTFS de CRTM incluye Metro Ligero junto con Metro Madrid
- Hay que filtrar por `route_type` o `route_id` para separar Metro Ligero de Metro
- Script debería generar ~3,000-5,000 trips con sus stop_times

---

### Scripts de Shapes de Sevilla (Experimentales)

**Estado:** ⚠️ Scripts creados pero NO ejecutados en producción. Propósito: mejora futura de shapes.

#### `scripts/import_sevilla_shapes_osm.py`

**Propósito:** Importar shapes de alta resolución para Cercanías Sevilla (C1-C5) y Tranvía Sevilla (T1) desde OpenStreetMap.

**Relaciones OSM mapeadas:**
| Línea | Relación IDA | Relación VUELTA |
|-------|--------------|-----------------|
| C-1 | 11378448 (Utrera → Lora) | 11378449 (Lora → Utrera) |
| C-2 | 11378341 (Sta Justa → Cartuja) | 11378342 (Cartuja → Sta Justa) |
| C-3 | 11382022 (Sta Justa → Cazalla) | 11382023 (Cazalla → Sta Justa) |
| C-4 | 11382118 (Sta Justa → Virgen Rocío) | (reverse automático) |
| C-5 | 11384991 (Hércules → Benacazón) | 11384992 (Benacazón → Hércules) |
| T1 | 36937 (Plaza Nueva → San Bernardo) | (reverse automático) |

**Uso:**
```bash
# Ver qué haría (sin cambios)
python scripts/import_sevilla_shapes_osm.py --dry-run

# Importar solo una línea
python scripts/import_sevilla_shapes_osm.py --line C1

# Importar todo
python scripts/import_sevilla_shapes_osm.py
```

**⚠️ Notas:**
- NO se ha ejecutado en producción
- Los shapes actuales de Cercanías Sevilla vienen del GTFS de RENFE (funcionan bien)
- Este script es para MEJORA FUTURA si se quieren shapes más detallados de OSM
- Requiere conexión a Overpass API (puede tener rate limiting)

#### `scripts/restore_sevilla_shapes.py`

**Propósito:** Restaurar shapes de Sevilla desde un backup JSON (útil si se corrompen datos).

**Uso:**
```bash
# Ver qué restauraría
python scripts/restore_sevilla_shapes.py backups/sevilla_shapes_backup.json --dry-run

# Restaurar
python scripts/restore_sevilla_shapes.py backups/sevilla_shapes_backup.json
```

**⚠️ Notas:**
- Script de utilidad para backup/restore
- Requiere archivo JSON de backup previo
- NO hay backups creados actualmente

---

## ✅ Route Planner - Estado Actual (2026-01-27 20:00)

### ✅ TODAS LAS REDES FUNCIONANDO

**Total: 260,038 trips RAPTOR-ready (100%)**

**Limpieza realizada (2026-01-27):**
- Eliminados 1,512 trips METRO_R sin stop_times (paradas no mapeadas correctamente)
- Eliminados 3,369 trips RENFE huérfanos sin stop_times (datos basura del GTFS original)

| Red | Trips | Estado | Test |
|-----|-------|--------|------|
| **Cercanías (RENFE)** | 130,616 | ✅ | Sants → Bellvitge |
| **Metro Madrid** | 19,658 | ✅ | Pinar Chamartín → Sol |
| **Metro Sevilla** | 3,340 | ✅ | Ciudad Expo → Olivar Quintos |
| **Metro Granada** | 5,693 | ✅ | Albolote → Armilla |
| **Metro Bilbao** | 10,620 | ✅ | Ariz → San Mamés |
| **Metrovalencia** | 11,230 | ✅ | Castelló → Font Almaguer |
| **Metro Málaga** | 4,681 | ✅ | Atarazanas → Clínico |
| **Metro Tenerife** | 12 | ✅ | Intercambiador → La Laguna |
| **FGC** | 15,495 | ✅ | La Bonanova → Can Feu |
| **TMB Metro** | 15,630 | ✅ | Hospital Bellvitge → Catalunya |
| **TRAM Barcelona** | 3,195 | ✅ | Francesc Macià → Pius XII |
| **Euskotren** | 11,088 | ✅ | Amara → Anoeta |
| **Metro Ligero MAD** | 3,001 | ✅ | Pinar Chamartín → Somosaguas |
| **Tranvía Zaragoza** | ~5,400 | ✅ | - |
| **TRAM Alicante** | ~2,200 | ✅ | - |

### Calendarios Arreglados (2026-01-27)

Se crearon **942 calendar entries** para arreglar redes que tenían trips sin calendario:

| Red | Entries | Patrón Días |
|-----|---------|-------------|
| FGC | 49 | L-D (todos) |
| TMB Metro | 43 | L-D (todos) |
| Metro Bilbao | 20 | Por patrón (invl=L-J, invv=V, etc.) |
| Metrovalencia | 7 | L-D (todos) |
| TRAM Barcelona | 8 | L-D (todos) |
| Metro Málaga | 9 | L-D (todos) |
| Metro Ligero MAD | 4 | Por patrón (I14=L-J, I15=V, etc.) |
| Metro Tenerife | 3 | S1=L-V, S2=S, S3=D |
| Cercanías RENFE | 120 | Por última letra (L,M,X,J,V,S,D) |
| Euskotren | 4 | L-D (todos) |
| Tranvía Zaragoza | ~20 | L-D (todos) |
| TRAM Alicante | ~15 | L-D (todos) |

**Script:** `scripts/fix_calendar_entries.py`

```bash
# Analizar (sin cambios)
python scripts/fix_calendar_entries.py --analyze

# Ejecutar fix
python scripts/fix_calendar_entries.py
```

**SQL Manual (alternativa):**
```sql
-- FGC: Crear calendarios activos L-D
INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
SELECT DISTINCT t.service_id, true, true, true, true, true, true, true, '2025-01-01', '2026-12-31'
FROM gtfs_trips t
WHERE t.route_id LIKE 'FGC%'
AND NOT EXISTS (SELECT 1 FROM gtfs_calendar c WHERE c.service_id = t.service_id)
ON CONFLICT (service_id) DO NOTHING;

-- TMB Metro: Crear calendarios activos L-D
INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
SELECT DISTINCT t.service_id, true, true, true, true, true, true, true, '2025-01-01', '2026-12-31'
FROM gtfs_trips t
WHERE t.route_id LIKE 'TMB_METRO%'
AND NOT EXISTS (SELECT 1 FROM gtfs_calendar c WHERE c.service_id = t.service_id)
ON CONFLICT (service_id) DO NOTHING;

-- Metro Bilbao: Mapear por patrón de nombre
-- Laborables (L-J): invl, verl
INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
SELECT DISTINCT t.service_id, true, true, true, true, false, false, false, '2025-01-01', '2026-12-31'
FROM gtfs_trips t
WHERE t.route_id LIKE 'METRO_BIL%'
AND (t.service_id ILIKE '%invl%' OR t.service_id ILIKE '%verl%')
AND NOT EXISTS (SELECT 1 FROM gtfs_calendar c WHERE c.service_id = t.service_id)
ON CONFLICT (service_id) DO NOTHING;

-- Viernes: invv, verv
INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
SELECT DISTINCT t.service_id, false, false, false, false, true, false, false, '2025-01-01', '2026-12-31'
FROM gtfs_trips t
WHERE t.route_id LIKE 'METRO_BIL%'
AND (t.service_id ILIKE '%invv%' OR t.service_id ILIKE '%verv%')
AND NOT EXISTS (SELECT 1 FROM gtfs_calendar c WHERE c.service_id = t.service_id)
ON CONFLICT (service_id) DO NOTHING;

-- Sábados: invs, vers
INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
SELECT DISTINCT t.service_id, false, false, false, false, false, true, false, '2025-01-01', '2026-12-31'
FROM gtfs_trips t
WHERE t.route_id LIKE 'METRO_BIL%'
AND (t.service_id ILIKE '%invs%' OR t.service_id ILIKE '%vers%')
AND NOT EXISTS (SELECT 1 FROM gtfs_calendar c WHERE c.service_id = t.service_id)
ON CONFLICT (service_id) DO NOTHING;

-- Domingos: invd, verd
INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
SELECT DISTINCT t.service_id, false, false, false, false, false, false, true, '2025-01-01', '2026-12-31'
FROM gtfs_trips t
WHERE t.route_id LIKE 'METRO_BIL%'
AND (t.service_id ILIKE '%invd%' OR t.service_id ILIKE '%verd%')
AND NOT EXISTS (SELECT 1 FROM gtfs_calendar c WHERE c.service_id = t.service_id)
ON CONFLICT (service_id) DO NOTHING;

-- Metrovalencia: Crear calendarios activos L-D
INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
SELECT DISTINCT t.service_id, true, true, true, true, true, true, true, '2025-01-01', '2026-12-31'
FROM gtfs_trips t
WHERE t.route_id LIKE 'METRO_VAL%'
AND NOT EXISTS (SELECT 1 FROM gtfs_calendar c WHERE c.service_id = t.service_id)
ON CONFLICT (service_id) DO NOTHING;

-- TRAM Barcelona: Crear calendarios activos L-D
INSERT INTO gtfs_calendar (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
SELECT DISTINCT t.service_id, true, true, true, true, true, true, true, '2025-01-01', '2026-12-31'
FROM gtfs_trips t
WHERE t.route_id LIKE 'TRAM_BARCELONA%'
AND NOT EXISTS (SELECT 1 FROM gtfs_calendar c WHERE c.service_id = t.service_id)
ON CONFLICT (service_id) DO NOTHING;
```

**NOTA:** La solución L-D para FGC/TMB/Metrovalencia/TRAM no es 100% precisa (algunos servicios pueden ser solo laborables o fines de semana), pero permite que RAPTOR funcione. Para mayor precisión, habría que reimportar los GTFS completos con sus calendarios originales.

### ✅ Redes con Scripts de Generación de Stop Times

**Problema resuelto:** Estas redes usan `frequencies.txt` en su GTFS, no `stop_times.txt` completos. RAPTOR necesita stop_times individuales para cada trip.

**Solución:** Se han creado scripts que descargan el GTFS oficial, leen los trip templates y frequencies, y generan trips individuales para todo el día.

| Red | Script | Trips Estimados | Estado |
|-----|--------|-----------------|--------|
| **Metro Sevilla** | `scripts/generate_metro_sevilla_trips.py` | ~3,340 | ✅ Script listo |
| **Metro Madrid** | `scripts/generate_metro_madrid_from_gtfs.py` | ~21,574 | ✅ Script listo |
| **Metro Ligero MAD** | Pendiente | - | ⏳ Por crear |

#### Metro Sevilla - Uso del Script

```bash
# Analizar el GTFS (sin cambios en BD)
python scripts/generate_metro_sevilla_trips.py --analyze

# Dry run (muestra qué se generaría)
python scripts/generate_metro_sevilla_trips.py --dry-run

# Generar trips (EJECUTAR EN SERVIDOR)
python scripts/generate_metro_sevilla_trips.py
```

**Datos a generar:**
- 2 direcciones (Ciudad Expo ↔ Olivar de Quintos)
- 21 paradas, 38 min de viaje
- ~952 trips weekday + ~1008 friday + ~748 saturday + ~632 sunday
- Total: ~3,340 trips, ~70,140 stop_times

#### Metro Madrid - Uso del Script

```bash
# Analizar el GTFS (sin cambios en BD)
python scripts/generate_metro_madrid_from_gtfs.py --analyze

# Dry run
python scripts/generate_metro_madrid_from_gtfs.py --dry-run

# Generar trips (EJECUTAR EN SERVIDOR)
python scripts/generate_metro_madrid_from_gtfs.py
```

**Datos a generar:**
- 12 líneas (1,2,4,5,6,7,8,9,10,11,12,R) - L3 no está en GTFS oficial
- ~5,906 trips weekday + ~5,984 friday + ~4,924 saturday + ~4,760 sunday
- Total: ~21,574 trips, ~539,350 stop_times

**IMPORTANTE:** Los scripts requieren que las paradas existan en la BD con los IDs correctos:
- Metro Sevilla: `METRO_SEV_L1_E1`, `METRO_SEV_L1_E2`, ..., `METRO_SEV_L1_E21`
- Metro Madrid: `METRO_1`, `METRO_2`, ..., `METRO_295`

### App iOS (para el compañero)

| Tarea | Descripción | API Ready |
|-------|-------------|-----------|
| Migrar route planner a API RAPTOR | Usar `/gtfs/route-planner` en vez de cálculo local | ✅ |
| Implementar selector de alternativas | Mostrar múltiples journeys de RAPTOR | ✅ |
| Widget/Siri con compact departures | Usar `?compact=true` en departures | ✅ |
| Mostrar alertas en journey | Usar `alerts` del response de route-planner | ✅ |
| Migrar normalización de shapes | Usar `?max_gap=50` del endpoint shapes | ✅ |

**Compact departures example:**
```bash
curl "https://redcercanias.com/api/v1/gtfs/stops/RENFE_17000/departures?compact=true&limit=5"
# Returns: [{"line":"C10","color":"#BCCF00","dest":"Pinar de las Rozas","mins":2,"plat":"8","delay":false}]
```

### Mejoras opcionales (baja prioridad)

- [ ] Investigar API Valencia tiempo real (devuelve vacío)
- [ ] Investigar servicio CIVIS Madrid
- [ ] Matching manual intercambiadores grandes
- [x] ~~Mapear shapes OSM a route_ids existentes~~ ✅ Completado 2026-01-26

### ✅ Shapes OSM mapeados a rutas (2026-01-26)

Creadas rutas y trips para acceder a los shapes via endpoint estándar:

| Ruta | Endpoint | Puntos |
|------|----------|--------|
| `TRAM_BCN_T1` | `/routes/TRAM_BCN_T1/shape` | 405 |
| `TRAM_BCN_T2` | `/routes/TRAM_BCN_T2/shape` | 532 |
| `TRAM_BCN_T3` | `/routes/TRAM_BCN_T3/shape` | 478 |
| `TRAM_BCN_T4` | `/routes/TRAM_BCN_T4/shape` | 311 |
| `TRAM_BCN_T5` | `/routes/TRAM_BCN_T5/shape` | 436 |
| `TRAM_BCN_T6` | `/routes/TRAM_BCN_T6/shape` | 400 |
| `METRO_SEV_L1_CE_OQ` | `/routes/METRO_SEV_L1_CE_OQ/shape` | 1,227 |

---

## Resumen de Producción

### Correspondencias
| Fuente | Cantidad |
|--------|----------|
| manual | 82 |
| osm | 74 |
| proximity | 62 |
| **TOTAL** | **218** |

### Shapes
- 949 shapes (todas las redes completas)
- 650,332 puntos
- 239,225 trips con shape (99.5%)

---

## Ejemplos de Uso de la API

### IDs Correctos (IMPORTANTE)

El compañero de la app debe usar los IDs **completos con prefijo**:

```bash
# ❌ INCORRECTO
curl ".../stops/79600/platforms"
curl ".../stops/TMB_232/correspondences"
curl ".../routes/METRO_1/shape"

# ✅ CORRECTO
curl ".../stops/RENFE_79600/platforms"
curl ".../stops/TMB_METRO_1.126/correspondences"
curl ".../routes/TMB_METRO_1.1.1/shape"
```

### Correspondencias Barcelona (NUEVAS)

```bash
# Catalunya - ahora incluye FGC y RENFE
curl "https://juanmacias.com/api/v1/gtfs/stops/TMB_METRO_1.126/correspondences"
# → FGC_PC, RENFE_78805, TMB_METRO_1.326

# Passeig de Gràcia - ahora incluye RENFE
curl "https://juanmacias.com/api/v1/gtfs/stops/TMB_METRO_1.327/correspondences"
# → RENFE_71802, TMB_METRO_1.213, TMB_METRO_1.425

# Sants - ahora incluye RENFE
curl "https://juanmacias.com/api/v1/gtfs/stops/TMB_METRO_1.518/correspondences"
# → RENFE_71801, TMB_METRO_1.319
```

### Shapes Nuevos (desde NAP)

```bash
# Metrovalencia
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_VAL_L1/shape"

# Metro Málaga
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_MAL_L1/shape"

# Metro Granada
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_GRA_L1/shape"

# Metro Tenerife (tranvía)
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_TEN_L1/shape"
```

### Shapes OSM (TRAM Barcelona y Metro Sevilla)

```bash
# TRAM Barcelona T1-T6
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T1/shape"
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T2/shape"
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T3/shape"
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T4/shape"
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T5/shape"
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T6/shape"

# Metro Sevilla L1
curl "https://redcercanias.com/api/v1/gtfs/routes/METRO_SEV_L1_CE_OQ/shape"

# Tranvía Sevilla (Metrocentro) T1
curl "https://juanmacias.com/api/v1/gtfs/routes/TRAM_SEV_T1/shape"
```

### Metro Madrid (NUEVO 2026-01-27)

```bash
# Metro Madrid - todas las líneas disponibles
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_1/shape"   # L1 Pinar de Chamartín - Valdecarros
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_2/shape"   # L2 Las Rosas - Cuatro Caminos
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_3/shape"   # L3 Villaverde Alto - Moncloa
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_4/shape"   # L4 Argüelles - Pinar de Chamartín
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_5/shape"   # L5 Alameda de Osuna - Casa de Campo
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_6/shape"   # L6 Circular
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_7/shape"   # L7 Pitis - Estadio Metropolitano
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_7B/shape"  # L7B Estadio Metropolitano - Hospital del Henares
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_8/shape"   # L8 Nuevos Ministerios - Aeropuerto T4
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_9/shape"   # L9 Paco de Lucía - Puerta de Arganda
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_9B/shape"  # L9B Puerta de Arganda - Arganda del Rey
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_10/shape"  # L10 Tres Olivos - Puerta del Sur
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_10B/shape" # L10B Hospital Infanta Sofía - Tres Olivos
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_11/shape"  # L11 Plaza Elíptica - La Fortuna
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_12/shape"  # L12 MetroSur (Circular)
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_R/shape"   # R Ópera - Príncipe Pío (solo shape, trips eliminados por datos incompletos)
```
