# Estado del Proyecto - GTFS y APIs de Transporte

**Última actualización:** 2026-01-26 12:30 CET

---

## Resumen de Estado

| Operador | GTFS Estático | GTFS-RT | transfers.txt |
|----------|---------------|---------|---------------|
| Metro Bilbao | ✅ | ✅ Protobuf | ❌ |
| Euskotren | ✅ | ✅ Protobuf | ✅ (13) |
| FGC | ✅ | ✅ Protobuf | ❌ |
| TMB Metro | ✅ (API key) | ✅ iMetro API | ✅ (60) |
| TRAM Barcelona | ✅ | ❌ | ❌ |
| TRAM Alicante | 🔧 NAP | ❌ | ❌ |
| Metro Tenerife | ✅ | ❌ | ✅ (2) |
| Metro Málaga | 🔧 NAP | ❌ | ✅ (4) |
| Metrovalencia | 🔧 NAP | ❌ (API*) | ❌ |
| Metro Granada | 🔧 NAP | ❌ | ❌ |
| Tranvía Zaragoza | 🔧 NAP | ❌ | ❌ |
| Tranvía Murcia | 🔧 NAP | ❌ | ❌ |
| SFM Mallorca | 🔧 NAP | ❌ | ❌ |
| **Renfe Cercanías** | ✅ | ✅ JSON | ✅ (19)* |
| Metro Madrid (CRTM) | ✅ | ❌ | ❌ |
| Metro Ligero Madrid | ✅ | ❌ | ❌ |

**Leyenda:**
- ✅ = Funciona y desplegado
- 🔧 NAP = Requiere descarga manual desde NAP (con login)
- ❌ (API*) = No hay GTFS-RT; existe API propietaria pero devuelve vacío (ver sección Valencia)
- ✅ (19)* = Transfers distribuidos por red (40T, 10T, etc.) según route_id

---

## 1. Cambios Desplegados (2026-01-25)

### 1.1 URLs Corregidas ✅

| Operador | URL Nueva (Funciona) |
|----------|----------------------|
| FGC | `https://www.fgc.cat/google/google_transit.zip` |
| TMB | `https://api.tmb.cat/v1/static/datasets/gtfs.zip?app_id=XXX&app_key=XXX` |
| Metro Tenerife | `https://metrotenerife.com/transit/google_transit.zip` |

### 1.2 Transfers Importados ✅

#### Transfers GTFS (fuente oficial)
| Operador | Registros | Fuente |
|----------|-----------|--------|
| TMB Metro Barcelona | 60 | GTFS URL |
| Renfe Cercanías | 19 | GTFS URL (por network: 40T, 10T, etc.) |
| Euskotren | 13 | GTFS URL |
| Metro Málaga | 4 | NAP (manual) |
| Metro Tenerife | 2 | GTFS URL |
| **Subtotal GTFS** | **98** | |

#### Transfers por Proximidad (< 250m) ✅ NUEVO
| Red | Conexiones | Ejemplo |
|-----|------------|---------|
| TMB_METRO (Barcelona) | 215 | Arc de Triomf ↔ Cercanías (4m) |
| METRO (Madrid) | 26 | Nuevos Ministerios (5m), Atocha (6m), Sol (33m) |
| METRO_BILBAO | 16 | San Mamés (19m), Abando (115m) |
| FGC | 17 | Martorell Central (3m), Lleida (4m) |
| TRAM | 10 | Cornellà (31m), St.Adrià (52m) |
| METRO_MALAGA | 4 | El Perchel ↔ María Zambrano (178m) |
| ML (Metro Ligero Madrid) | 3 | Fuente de la Mora (19m), Aravaca (33m) |
| METRO_VALENCIA | 2 | Xàtiva (31m), Sant Isidre (136m) |
| TRANVIA (Zaragoza) | 2 | Fernando El Católico ↔ Goya (77m) |
| METRO_SEV (Sevilla) | 1 | San Bernardo (87m) |
| **Subtotal Proximidad** | **296 x 2** | **592 bidireccionales** |

#### Total
| Fuente | Registros |
|--------|-----------|
| proximity | 592 |
| gtfs | 94 |
| nap | 4 |
| **TOTAL** | **690** |

**Nota Renfe:** Los transfers de Renfe Cercanías se distribuyen por network_id real (40T Valencia, 10T Madrid, etc.) extraído del route_id del GTFS (`40T0002C1` → `40T`).

### 1.3 Endpoint Transfers ✅
- `GET /api/v1/gtfs/stops/{stop_id}/transfers`
- Parámetro opcional: `direction=from|to`

### 1.4 Migración 026 ✅
- Tabla `line_transfer` creada
- Índices en `from_stop_id`, `to_stop_id`, `network_id`

### 1.5 Otros Cambios ✅
- Detección de suspensión de servicio en `/routes/{id}/operating-hours`
- Filtro de rutas C4/C8 genéricas cuando existen variantes (C4a/C4b, C8a/C8b)
- Metrovalencia fetcher preparado (pendiente que API devuelva datos)

### 1.6 Nuevos Campos API (2026-01-25 23:30) ✅

#### transport_type en /networks
Campo nuevo en todas las respuestas de networks (`GET /api/v1/gtfs/networks`):
```json
{
  "code": "10T",
  "name": "Cercanías Madrid",
  "transport_type": "cercanias",
  ...
}
```

**Valores posibles:**
- `cercanias` - Renfe Cercanías/Rodalies (10T, 40T, 51T, etc.)
- `metro` - Metro (METRO_BILBAO, TMB_METRO, 11T)
- `metro_ligero` - Metro Ligero (12T, ML_*)
- `tranvia` - Tranvía (TRANVIA_*, TRAM_*)
- `fgc` - FGC
- `euskotren` - Euskotren
- `other` - Otros

#### is_hub en stops
Campo nuevo en todas las respuestas de stops (`GET /api/v1/gtfs/stops/*`):
```json
{
  "id": "RENFE_17000",
  "name": "Madrid-Atocha Cercanías",
  "is_hub": true,
  ...
}
```

**Definición de hub:** Estación con 2+ tipos de transporte diferentes:
- Metro (cor_metro)
- Cercanías/Rodalies (cor_cercanias con líneas C*/R* - excluye Euskotren E1, E2, TR)
- Metro Ligero (cor_ml)
- Tranvía (cor_tranvia)

**Nota:** Múltiples líneas del mismo tipo NO hacen hub.

### 1.7 Migración 027 ✅
- Añadidas columnas `cor_ml` y `cor_cercanias` a `gtfs_stops`
- Necesario para el cálculo de `is_hub`

---

## 2. NAP - IDs Completos

| Operador | NAP ID | URL |
|----------|--------|-----|
| TRAM Alicante | 966 | https://nap.transportes.gob.es/Files/Detail/966 |
| Metrovalencia | 967 | https://nap.transportes.gob.es/Files/Detail/967 |
| Metro Málaga | 1296 | https://nap.transportes.gob.es/Files/Detail/1296 |
| Metro Granada | 1370 | https://nap.transportes.gob.es/Files/Detail/1370 |
| Tranvía Zaragoza | 1394 | https://nap.transportes.gob.es/Files/Detail/1394 |
| Tranvía Murcia | 1371 | https://nap.transportes.gob.es/Files/Detail/1371 |
| SFM Mallorca | 1071 | https://nap.transportes.gob.es/Files/Detail/1071 |

**Nota:** Requiere login web para descargar. La API key no permite descargas directas.

---

## 3. Valencia (FGV - Metrovalencia)

### 3.1 Datos Estáticos ✅
**API:** `valencia.opendatasoft.com` (funciona sin auth, 5000 req/día)

| Dataset ID | Registros | Datos |
|------------|-----------|-------|
| `fgv-estacions-estaciones` | 142 | Estaciones metro/tranvía (coords, línea, código) |
| `fgv-bocas` | 187 | Bocas de acceso |
| `emt` | 1126 | Paradas de bus EMT |

```bash
# Exportar estaciones
GET https://valencia.opendatasoft.com/api/explore/v2.1/catalog/datasets/fgv-estacions-estaciones/exports/json
```

### 3.2 Tiempo Real ❌
**API:** `geoportal.valencia.es` (NO funciona)

```
GET https://geoportal.valencia.es/geoportal-services/api/v1/salidas-metro.json?estacion={codigo}

Estado: ⚠️ Responde HTTP 200 pero devuelve {"salidasMetro":[]}
```

**Nota:** El campo `proximas_llegadas` en los datos de estaciones apunta a esta API, pero actualmente no devuelve datos.

---

## 4. TMB Barcelona

### Credenciales
```
app_id: e76ae269
app_key: 291c7f8027c5e684e010e6a54e76428c
```

### APIs Implementadas
- iMetro: `/v1/imetro/estacions` (tiempo real)
- GTFS Static: `/v1/static/datasets/gtfs.zip`

---

## 5. Coordenadas de Andenes y Correspondencias (EN PROGRESO)

### 5.1 Contexto
Las estaciones con múltiples líneas tienen andenes en diferentes ubicaciones físicas. Por ejemplo:
- **Nuevos Ministerios (Madrid)**: L6, L8, L10 tienen coordenadas ligeramente diferentes
- **Embajadores**: L3 + C5 + intercambiador con Acacias (L5)

### 5.2 Estructura de Datos

**CSV fuente:** `docs/estaciones_espana_completo.csv` (1168 estaciones)
- Renfe Cercanías: 856 estaciones
- Euskotren: 128 estaciones
- FGC: 100 estaciones
- Metro Madrid: 42 estaciones
- Metro Bilbao: 42 estaciones

**Formato de coordenadas por línea:**
```
platform_coords_by_line: "L6:[40.446620,-3.692410]; L8:[40.446550,-3.692410]; L10:[40.446590,-3.692410]"
```

### 5.3 Migración 028 (PENDIENTE DE EJECUTAR)
- Añade columnas `from_lat`, `from_lon`, `to_lat`, `to_lon` a `line_transfer`
- Crea tabla `correspondence_discrepancies` para revisión manual de diferencias

### 5.4 Sistema de Discrepancias
Cuando los datos del CSV difieren de la BD, **NO se sobreescribe**. Se guarda en `correspondence_discrepancies`:
- `value_in_db`: Lo que hay actualmente
- `value_in_csv`: Lo que viene del CSV
- `discrepancy_type`: 'missing_in_db', 'missing_in_csv', 'different'
- `reviewed`: false hasta que se revise manualmente

### 5.5 Script de Importación
`scripts/import_platform_coords.py`
- Lee CSV
- Compara con BD
- Guarda discrepancias si hay diferencias
- Actualiza `line_transfer` con coordenadas

---

## 6. Tareas Pendientes

### Completadas
- [x] ~~Importar Renfe Cercanías transfers~~ ✅ Desplegado 2026-01-25 21:11
- [x] ~~Añadir transport_type a /networks~~ ✅ Implementado 2026-01-25 23:30
- [x] ~~Añadir is_hub a stops~~ ✅ Implementado 2026-01-25 23:30
- [x] ~~Poblar cor_tranvia en TRAM_BARCELONA~~ ✅ Ejecutado 2026-01-26 03:20 (172 paradas, OSM data)
- [x] ~~Reemplazar line_transfer con stop_platform~~ ✅ Ejecutado 2026-01-26 05:00
  - Migración 029: Elimina line_transfer, crea stop_platform
  - Nuevo endpoint: `GET /stops/{stop_id}/platforms`
- [x] ~~Migración 030: Cambiar `line` → `lines`~~ ✅ Ejecutado 2026-01-26 06:30
- [x] ~~Importar plataformas de TODAS las redes~~ ✅ Ejecutado 2026-01-26 07:00
- [x] ~~Crear tabla stop_correspondence~~ ✅ Ejecutado 2026-01-26 08:00
  - Migración 031: Nueva tabla para conexiones a pie entre estaciones diferentes
  - Nuevo endpoint: `GET /stops/{stop_id}/correspondences`
- [x] ~~Importar correspondencias por proximidad~~ ✅ Ejecutado 2026-01-26 08:30
  - 68 correspondencias: Metro↔Cercanías, Metro↔Metro Ligero (<300m)
- [x] ~~Script import_osm_correspondences.py~~ ✅ Ejecutado 2026-01-26 09:00
  - Importa `stop_area_group` de OSM
  - Clasifica: misma estación vs estaciones diferentes
  - Documentación: `docs/IMPORT_OSM_CORRESPONDENCES.md`

### Estado Actual de Plataformas (stop_platform)

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
| **TOTAL** | **2550** | **2429** | |

### Estado Actual de Correspondencias (stop_correspondence)

| Fuente | Cantidad | Ejemplo |
|--------|----------|---------|
| Manual | 32 | Acacias↔Embajadores, Nervión↔Eduardo Dato (Sevilla), Abando (Bilbao) |
| OSM | 72 | Barcelona stop_area_groups (Catalunya, Sants, etc.) |
| Proximidad (<300m) | 62 | Atocha Metro↔Cercanías, Nuevos Ministerios |
| **TOTAL** | **166** (83 pares) | |

**Por ciudad:**
- Madrid Metro: 17 pares
- Barcelona (TMB+FGC): 25 pares
- Bilbao (Metro+Euskotren): 5 pares
- Sevilla (Metro+Tranvía): 6 pares
- Valencia: 1 par (Sant Isidre)
- Zaragoza: 9 pares (Delicias, Plaza Aragón)

### Tareas Completadas (2026-01-26)

- [x] ~~Importar stop_area_group de Barcelona~~ ✅ 27 plataformas, 96 correspondencias
- [x] ~~Añadir correspondencias Sevilla (Metro↔Tranvía)~~ ✅ Nervión↔Eduardo Dato, Prado, Puerta Jerez
- [x] ~~Añadir correspondencias Bilbao (Metro↔Euskotren↔Cercanías)~~ ✅ Abando, San Mamés, Casco Viejo
- [x] ~~Importar stop_area_group Valencia, Zaragoza~~ ✅ Sant Isidre, Delicias, Plaza Aragón
- [x] ~~Documentación completa~~ ✅ `docs/PLATFORMS_AND_CORRESPONDENCES.md`

### Tareas Pendientes

#### Matching Manual Intercambiadores (cuando el usuario esté listo)
- [ ] Nuevos Ministerios (separar plataformas por líneas)
- [ ] Atocha Cercanías (~10 plataformas)
- [ ] Chamartín (~6 plataformas)
- [ ] Sol, Príncipe Pío
- [ ] Passeig de Gràcia, Sants, Plaça Catalunya (Barcelona)

### Otras Tareas
- [ ] Completar Passeig de Gràcia con L2, L4 en cor_metro
- [ ] Investigar API Valencia (devuelve vacío)
- [ ] Metro Tenerife (no tiene datos de líneas en cor_metro)
- [ ] Extraer coordenadas OSM para metros secundarios (Valencia, Sevilla, Málaga, Granada)

---

## 7. Archivos Clave

```
# Configuración y scripts de importación
scripts/operators_config.py              # Config de todos los operadores + NAP IDs
scripts/import_stop_platforms.py         # Importador de plataformas desde OSM CSV
scripts/import_osm_correspondences.py    # Importador de correspondencias desde OSM stop_area_group

# Datos fuente
docs/estaciones_espana_completo.csv      # 1168 estaciones con coordenadas por andén (OSM/GMaps)
docs/estaciones_bilbao_detallado.csv     # Detalle de Bilbao
docs/osm_coords/                         # CSVs con coordenadas OSM por línea
  - metro_madrid_by_line.csv             # 281 pares estación-línea
  - metro_bcn_by_line.csv                # 259 pares estación-línea
  - metro_bilbao_by_line.csv             # 62 pares estación-línea

# API Routers
adapters/http/api/gtfs/routers/query_router.py    # Endpoint transfers + is_hub
adapters/http/api/gtfs/routers/network_router.py  # Endpoint networks + transport_type

# Modelos
src/gtfs_bc/transfer/infrastructure/models/line_transfer_model.py  # LineTransfer con coords
src/gtfs_bc/transfer/infrastructure/models/discrepancy_model.py    # Discrepancias (NUEVO)
src/gtfs_bc/stop/infrastructure/models/stop_model.py               # StopModel con is_hub
src/gtfs_bc/network/infrastructure/models/__init__.py              # NetworkModel con transport_type

# Migraciones
alembic/versions/026_create_line_transfer_table.py                 # Tabla line_transfer
alembic/versions/027_add_correspondence_columns_to_stops.py        # cor_ml, cor_cercanias
alembic/versions/028_add_coords_to_line_transfer.py                # Coords + discrepancies (NUEVO)

# Documentación
docs/GTFS_OPERATORS_STATUS.md            # Estado de operadores
```
