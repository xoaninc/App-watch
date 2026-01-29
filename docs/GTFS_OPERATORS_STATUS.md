# Estado de Operadores GTFS

**Última actualización:** 2026-01-29

---

## Comparación GTFS vs OSM

### Archivos de Revisión

| Archivo | Descripción |
|---------|-------------|
| `revision_final.csv` | **Archivo principal** - 2,054 estaciones para revisar |
| `revision_simple.csv` | Backup del archivo original con tus notas |
| `revision_tecnica.csv` | Datos técnicos con coordenadas OSM (uso interno) |

#### Columnas de revision_final.csv

| Columna | Qué hacer |
|---------|-----------|
| `ESTA_BIEN` | Marcar **SI** si las líneas de Cor_Metro/Cercanias/Tranvia son correctas |
| `FALTA_ALGO` | Escribir qué línea falta o si hay error en el nombre |

**Nota:** Se han eliminado 38 entradas internas (vestíbulos, áreas, salidas) que no son estaciones reales.

#### Estadísticas por red (2,054 estaciones)

| Red | Estaciones |
|-----|------------|
| RENFE | 774 |
| METRO (Madrid) | 242 |
| METRO_BILBAO | 149 |
| METRO_VALENCIA | 143 |
| TMB_METRO | 139 |
| EUSKOTREN | 134 |
| FGC | 100 |
| TRAM_ALICANTE | 70 |
| TRAM_BARCELONA | 58 |
| ML (Metro Ligero) | 56 |
| TRANVIA_ZARAGOZA | 32 |
| SFM_MALLORCA | 31 |
| TRANVIA_MURCIA | 28 |
| METRO_GRANADA | 26 |
| METRO_TENERIFE | 25 |
| METRO_SEV | 21 |
| METRO_MALAGA | 19 |
| TRAM_SEV | 7 |

---

## Resumen

| Operador | GTFS Estático | GTFS-RT | transfers.txt | Shapes |
|----------|---------------|---------|---------------|--------|
| Metro Bilbao | ✅ | ✅ | ❌ | ✅ 13k pts |
| Euskotren | ✅ | ✅ | ✅ (13) | ✅ 61k pts |
| FGC | ✅ | ✅ | ❌ | ✅ 12k pts |
| TMB Metro | ✅ (API key) | ✅ API | ✅ (60) | ✅ 103k pts |
| TRAM Barcelona | ✅ | ❌ | ❌ | ✅ 5k pts (OSM 2026-01-26) |
| TRAM Alicante | ✅ NAP | ❌ | ❌ | ✅ 7k pts (OSM 2026-01-26) |
| Metro Tenerife | ✅ | ❌ | ✅ (2) | ✅ 132 pts |
| Metro Málaga | ✅ Frecuencias | ❌ | ✅ (4) | ✅ 260 pts |
| Metrovalencia | ✅ NAP | ❌ (API*) | ❌ | ✅ 11k pts (OSM 2026-01-26) |
| Metro Granada | ✅ Frecuencias | ❌ | ❌ | ✅ 52 pts (bidireccional) |
| Metro Sevilla | ✅ Frecuencias | ❌ | ❌ | ✅ 424 pts (OSM) |
| Tranvía Zaragoza | ✅ NAP | ❌ | ❌ | ✅ 252 pts |
| Tranvía Murcia | ✅ NAP | ❌ | ❌ | ✅ 989 pts (L1 circular + L1B bidir) |
| SFM Mallorca | ✅ NAP | ❌ | ❌ | ✅ 258k pts |
| Tranvía Sevilla | ✅ manual | ❌ | ❌ | ✅ 552 pts (OSM 2026-01-27) |
| **Renfe Cercanías** | ✅ | ✅ JSON | ✅ (19)* | ✅ 74k pts |
| Metro Madrid (CRTM) | ✅ | ❌ | ❌ | ✅ 57k pts (2026-01-27) |
| Metro Ligero Madrid | ✅ | ❌ | ❌ | ✅ 62k pts |

**Leyenda:**
- ✅ = Funciona (shapes: incluye cantidad de puntos en producción)
- ✅ Frecuencias = Trips generados desde frecuencias oficiales (ver sección "Importación basada en Frecuencias")
- 🔧 NAP = Requiere descarga manual desde NAP (con login)
- ⚠️ URL directa = Shapes disponibles en URL pública, pendiente de importar
- ❌ (API*) = No hay GTFS-RT; existe API propietaria pero devuelve vacío (ver sección Metrovalencia)
- ❌ No en GTFS = El GTFS del operador no incluye shapes.txt
- ✅ (19)* = Transfers distribuidos por red (40T, 10T, etc.) según route_id

---

## URLs Funcionando ✅

### Metro Bilbao
- **GTFS Estático:** `https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfs_metro_bilbao.zip`
- **GTFS-RT Vehicle Positions:** `https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfsrt_metro_bilbao_vehicle_positions.pb`
- **GTFS-RT Trip Updates:** `https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfsrt_metro_bilbao_trip_updates.pb`
- **GTFS-RT Alerts:** `https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfsrt_metro_bilbao_alerts.pb`
- **transfers.txt:** NO

### Euskotren
- **GTFS Estático:** `https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfs_euskotren.zip`
- **GTFS-RT Vehicle Positions:** `https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfsrt_euskotren_vehicle_positions.pb`
- **GTFS-RT Trip Updates:** `https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfsrt_euskotren_trip_updates.pb`
- **GTFS-RT Alerts:** `https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfsrt_euskotren_alerts.pb`
- **transfers.txt:** ✅ SÍ (13 registros)

### FGC (Ferrocarrils de la Generalitat de Catalunya)
- **GTFS Estático:** `https://www.fgc.cat/google/google_transit.zip`
- **GTFS-RT Vehicle Positions:** `https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/vehicle-positions-gtfs_realtime/files/d286964db2d107ecdb1344bf02f7b27b`
- **GTFS-RT Trip Updates:** `https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/trip-updates-gtfs_realtime/files/735985017f62fd33b2fe46e31ce53829`
- **GTFS-RT Alerts:** `https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/alerts-gtfs_realtime/files/02f92ddc6d2712788903e54468542936`
- **transfers.txt:** NO

### TMB Metro Barcelona
- **GTFS Estático:** `https://api.tmb.cat/v1/static/datasets/gtfs.zip?app_id=XXX&app_key=XXX`
- **GTFS-RT:** API custom `https://api.tmb.cat/v1/imetro/estacions`
- **Portal:** https://developer.tmb.cat/api-docs/v1/
- **Notas:** Requiere app_id y app_key
- **transfers.txt:** ✅ SÍ (60 registros)

### TRAM Barcelona
- **GTFS Estático Trambaix:** `https://www.tram.cat/documents/20124/260748/google_transit_tram.zip`
- **GTFS Estático Trambesòs:** `https://www.tram.cat/documents/20124/260749/google_transit_tram_besos.zip`
- **GTFS-RT:** No disponible
- **transfers.txt:** NO

### Metro Tenerife
- **GTFS Estático:** `https://metrotenerife.com/transit/google_transit.zip`
- **GTFS-RT:** No disponible
- **Fuente:** Portal datos abiertos Canarias
- **transfers.txt:** ✅ SÍ (2 registros)

### Renfe Cercanías (todas las regiones)
- **GTFS Estático:** `https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip`
- **GTFS-RT Vehicle Positions:** `https://gtfsrt.renfe.com/vehicle_positions.json`
- **GTFS-RT Trip Updates:** `https://gtfsrt.renfe.com/trip_updates.json`
- **GTFS-RT Alerts:** `https://gtfsrt.renfe.com/alerts.json`
- **Formato RT:** JSON
- **Fuente:** data.renfe.com
- **transfers.txt:** ✅ SÍ (19 registros)
- **Notas:** Feed unificado para todas las regiones de Cercanías
- **network_id:** Se extrae del route_id (ej: `40T0002C1` → `40T` Valencia, `10T...` → `10T` Madrid)

### Metro Madrid (CRTM)
- **GTFS Estático:** `https://crtm.maps.arcgis.com/sharing/rest/content/items/5c7f2951962540d69ffe8f640d94c246/data`
- **GTFS-RT:** No disponible
- **Fuente:** CRTM Open Data
- **transfers.txt:** NO

### Metro Ligero Madrid
- **GTFS Estático:** `https://crtm.maps.arcgis.com/sharing/rest/content/items/aaed26cc0ff64b0c947ac0bc3e033196/data`
- **GTFS-RT:** No disponible
- **Fuente:** CRTM Open Data
- **transfers.txt:** NO

---

## Metrovalencia (FGV)

### Resumen de APIs

| Tipo | API | Estado |
|------|-----|--------|
| **Datos Estáticos** | `valencia.opendatasoft.com` | ✅ Funciona |
| **Tiempo Real** | `geoportal.valencia.es` | ❌ Devuelve vacío |
| **GTFS Estático** | NAP (ID 967) | 🔧 Descarga manual |
| **GTFS-RT** | No existe | ❌ |

### Datos Estáticos ✅ (OpenDataSoft)

| Concepto | Valor |
|----------|-------|
| Portal | https://valencia.opendatasoft.com |
| API Base | `https://valencia.opendatasoft.com/api/explore/v2.1/` |
| Auth | No requerida (5000 req/día) |

| Dataset | Registros | Descripción |
|---------|-----------|-------------|
| `fgv-estacions-estaciones` | 142 | Estaciones (coords, línea, código, URLs) |
| `fgv-bocas` | 187 | Bocas de acceso |
| `emt` | 1126 | Paradas de bus EMT |

```bash
# Exportar estaciones JSON
GET https://valencia.opendatasoft.com/api/explore/v2.1/catalog/datasets/fgv-estacions-estaciones/exports/json

# Exportar en GeoJSON
GET https://valencia.opendatasoft.com/api/explore/v2.1/catalog/datasets/fgv-estacions-estaciones/exports/geojson
```

### Tiempo Real ❌ (Geoportal)

```
GET https://geoportal.valencia.es/geoportal-services/api/v1/salidas-metro.json?estacion={codigo}

Respuesta: {"salidasMetro":[]}
```

**Nota:** El campo `proximas_llegadas` en `fgv-estacions-estaciones` apunta a esta API, pero actualmente no devuelve datos de próximas llegadas.

---

## Requieren Descarga Manual (NAP)

Estos operadores requieren descarga desde el NAP con login web:
- Portal: https://nap.transportes.gob.es

| Operador | NAP ID | URL |
|----------|--------|-----|
| TRAM Alicante | 966 | https://nap.transportes.gob.es/Files/Detail/966 |
| Metrovalencia | 967 | https://nap.transportes.gob.es/Files/Detail/967 |
| Metro Málaga | 1296 | https://nap.transportes.gob.es/Files/Detail/1296 |
| Metro Granada | 1370 | https://nap.transportes.gob.es/Files/Detail/1370 |
| Tranvía Zaragoza | 1394 | https://nap.transportes.gob.es/Files/Detail/1394 |
| Tranvía Murcia | 1371 | https://nap.transportes.gob.es/Files/Detail/1371 |
| SFM Mallorca | 1071 | https://nap.transportes.gob.es/Files/Detail/1071 |
| Metro Sevilla | 1385 | https://nap.transportes.gob.es/Files/Detail/1385 |

**Nota:** La API key del NAP no permite descargas directas. Se requiere login web.

---

## Transfers.txt - Resumen

| Operador | Registros | Fuente |
|----------|-----------|--------|
| TMB Metro Barcelona | 60 | GTFS URL |
| Renfe Cercanías | 19 | GTFS URL (distribuidos por network: 40T, 10T, etc.) |
| Euskotren | 13 | GTFS URL |
| Metro Málaga | 4 | NAP (manual) |
| Metro Tenerife | 2 | GTFS URL |
| **Total** | **98** | |

### Operadores verificados SIN transfers.txt
- Metro Bilbao ❌
- FGC ❌
- TRAM Barcelona ❌
- TRAM Alicante ❌
- Metrovalencia ❌
- Metro Granada ❌
- Tranvía Zaragoza ❌
- Tranvía Murcia ❌
- SFM Mallorca ❌
- Metro Madrid (CRTM) ❌
- Metro Ligero Madrid ❌

---

## Archivos de Configuración

| Archivo | Descripción |
|---------|-------------|
| `scripts/operators_config.py` | Configuración de operadores |
| `scripts/import_transfers.py` | Importador de transfers |
| `scripts/import_metro_sevilla_frequencies.py` | Importador frecuencias Metro Sevilla |
| `scripts/import_metro_granada_frequencies.py` | Importador frecuencias Metro Granada |
| `scripts/import_metro_malaga_frequencies.py` | Importador frecuencias Metro Málaga |
| `src/gtfs_bc/realtime/infrastructure/services/multi_operator_fetcher.py` | Fetcher multi-operador |

---

## API Endpoint (Desplegado ✅)

```
GET /api/v1/gtfs/stops/{stop_id}/transfers?direction={from|to}
```

**Parámetros:**
- `stop_id`: ID de la parada (ej: `TMB_METRO_1.117`, `EUSKOTREN_ES:Euskotren:StopPlace:1480:`)
- `direction` (opcional): `from` (transfers desde esta parada), `to` (transfers hacia esta parada)

**Ejemplo respuesta:**
```json
{
  "id": 100,
  "from_stop_id": "TMB_METRO_1.117",
  "to_stop_id": "TMB_METRO_1.915",
  "transfer_type": 2,
  "min_transfer_time": 45,
  "from_stop_name": "Torrassa",
  "to_stop_name": "Torrassa",
  "network_id": "TMB_METRO",
  "source": "gtfs"
}
```

**Transfer types (GTFS estándar):**
- 0 = Punto de transbordo recomendado
- 1 = Transbordo temporizado (vehículo espera)
- 2 = Tiempo mínimo requerido
- 3 = Transbordo no posible

---

## Importación basada en Frecuencias

Algunos operadores tienen datos GTFS en el NAP con validez limitada o frecuencias incorrectas. Para estos casos, se han creado scripts que generan trips individuales a partir de las frecuencias oficiales publicadas en sus webs.

### Metro Sevilla
- **Script:** `scripts/import_metro_sevilla_frequencies.py`
- **Fuente:** https://metrodesevilla.info/horarios
- **Línea:** L1 (21 paradas)
- **Validez:** Todo 2026
- **Trips generados:** ~1,000
- **Frecuencias:**
  - L-J: 4-6 min (punta), 7.5 min (valle)
  - Viernes: 4-6 min (punta), 7.5 min (valle), 10 min (noche)
  - Sábado: 7.5 min (día), 10-15 min (noche)
  - Domingo/Festivo: 10 min

### Metro Granada
- **Script:** `scripts/import_metro_granada_frequencies.py`
- **Fuente:** https://metropolitanogranada.es/horarios
- **Línea:** L1 (26 paradas: Albolote ↔ Armilla)
- **Validez:** Todo 2026
- **Trips generados:** 966
- **Stop times generados:** 25,116
- **Frecuencias:**
  - L-J: 8'30" todo el día
  - Viernes: 8'30" (día), 15' (noche 22:00-00:00)
  - Sábado: 10' (día), 15' (noche)
  - Domingo/Festivo: 15' todo el día
- **Tiempo total de recorrido:** 50-51 minutos
- **Festivos 2026:** Incluye festivos nacionales, autonómicos (Andalucía) y locales (Granada)

### Metro Málaga
- **Script:** `scripts/import_metro_malaga_frequencies.py`
- **Fuente:** https://metromalaga.es/horarios/
- **Líneas:**
  - L1: El Perchel ↔ Andalucía Tech (13 paradas, ~20 min)
  - L2: Palacio Deportes ↔ El Perchel (8 paradas, ~12 min)
- **Validez:** Todo 2026
- **Trips generados:** 2,104
- **Stop times generados:** 22,092
- **Frecuencias:**
  - L-V: 9'30" todo el día
  - Sábado: 12' todo el día
  - Domingo/Festivo: 15' todo el día
- **Festivos 2026:** Incluye festivos nacionales, autonómicos (Andalucía) y locales (Málaga, incluyendo Feria de Málaga y Virgen de la Victoria)

### Cómo ejecutar los scripts

```bash
# Granada
python scripts/import_metro_granada_frequencies.py

# Málaga
python scripts/import_metro_malaga_frequencies.py

# Sevilla
python scripts/import_metro_sevilla_frequencies.py
```

**Nota:** Los scripts borran los datos existentes del operador antes de insertar los nuevos. Ejecutar en producción con precaución.
