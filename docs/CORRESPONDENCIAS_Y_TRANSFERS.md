# Correspondencias y Transfers - Documentación Técnica

**Fecha:** 2026-01-26
**Autor:** Claude Code

---

## 1. Conceptos Clave

### 1.1 Plataformas (stop_platform) - MODELO ACTUAL

Tabla que almacena las coordenadas específicas de cada andén/plataforma en una estación.

**Estructura:**
```sql
stop_platform:
  id: INTEGER PRIMARY KEY
  stop_id: VARCHAR(100)     -- Referencia a gtfs_stops
  lines: VARCHAR(255)       -- Una o varias líneas: "L6" o "C2, C3, C4a, C4b"
  lat: FLOAT
  lon: FLOAT
  source: VARCHAR(50)       -- 'gtfs', 'osm', 'manual'
  UNIQUE(stop_id, lines)
```

**Lógica de agrupación:**
- Si varias líneas comparten el mismo andén (mismas coordenadas) → se agrupan en `lines`
- Si cada línea tiene coordenadas diferentes → una entrada por línea

**Ejemplo - METRO_120 (Nuevos Ministerios Metro):**
```
| lines | lat       | lon       | source |
|-------|-----------|-----------|--------|
| L6    | 40.446620 | -3.692410 | osm    |
| L8    | 40.446550 | -3.692380 | osm    |
| L10   | 40.446590 | -3.692400 | osm    |
```

**Ejemplo - RENFE_18002 (Nuevos Ministerios Cercanías):**
```
| lines              | lat       | lon       | source |
|--------------------|-----------|-----------|--------|
| C3, C4a, C4b       | 40.445306 | -3.692042 | osm    |
| C7, C8a, C8b, C10  | 40.445187 | -3.692495 | osm    |
| C2                 | 40.445194 | -3.693120 | osm    |
```

**Endpoint:** `GET /api/v1/gtfs/stops/{stop_id}/platforms`

**Respuesta:**
```json
{
  "stop_id": "RENFE_18002",
  "stop_name": "Nuevos Ministerios",
  "platforms": [
    {"id": 1, "lines": "C3, C4a, C4b", "lat": 40.445306, "lon": -3.692042, "source": "osm"},
    {"id": 2, "lines": "C7, C8a, C8b, C10", "lat": 40.445187, "lon": -3.692495, "source": "osm"},
    {"id": 3, "lines": "C2", "lat": 40.445194, "lon": -3.693120, "source": "osm"}
  ]
}
```

### 1.2 Modelo Anterior (DEPRECADO) - line_transfer

> **NOTA:** El modelo `line_transfer` fue eliminado en migración 029. Se documenta aquí para referencia histórica.

El modelo anterior almacenaba transfers entre paradas (from_stop → to_stop) con tiempos de caminata.
Fue reemplazado por `stop_platform` que es más simple y directo: almacena las coordenadas
de cada andén sin necesidad de calcular transfers.

Scripts deprecados movidos a `scripts/deprecated/`:
- `import_transfers.py`
- `import_proximity_transfers.py`
- `import_platform_coords.py`

### 1.3 Correspondencias (cor_*)

Campos en la tabla `gtfs_stops` que indican qué líneas de cada tipo de transporte hay en/cerca de esa parada.

| Campo | Descripción |
|-------|-------------|
| `cor_metro` | Líneas de metro |
| `cor_cercanias` | Líneas de cercanías/rodalies/FGC/Euskotren |
| `cor_tranvia` | Líneas de tranvía |
| `cor_ml` | Líneas de metro ligero |

**Todos los campos están presentes en todas las paradas**, pero su uso varía:

| Situación | Uso |
|-----------|-----|
| **Mismo tipo de transporte** | ACTIVO - la app lo usa funcionalmente |
| **Otro tipo de transporte** | INFORMATIVO - se muestra pero solo como referencia |

**Ejemplo - Nuevos Ministerios (parada de METRO):**
```
id: METRO_12345
name: Nuevos Ministerios
cor_metro: L6, L8, L10           ← ACTIVO (líneas de metro que pasan aquí)
cor_cercanias: C3, C4a, C4b...   ← INFORMATIVO (cercanías cerca)
cor_tranvia: null
cor_ml: null
```

**Ejemplo - Nuevos Ministerios (parada de CERCANÍAS):**
```
id: RENFE_17000
name: Nuevos Ministerios
cor_metro: L6, L8, L10           ← INFORMATIVO (metro cerca)
cor_cercanias: C3, C4a, C4b...   ← ACTIVO (líneas de cercanías que pasan aquí)
cor_tranvia: null
cor_ml: null
```

**Ejemplo - Glòries (parada de TRANVÍA Barcelona):**
```
id: TRAM_BARCELONA_1234
name: Glòries
cor_metro: L1                    ← INFORMATIVO (metro cerca)
cor_cercanias: null
cor_tranvia: T4, T5, T6          ← ACTIVO (líneas de tranvía que pasan aquí)
cor_ml: null
```

### 1.2 Line Transfers - DETALLADO

Tabla `line_transfer` que almacena información de **transfers entre líneas/andenes dentro de una misma estación física**.

**Propósito:** Calcular tiempo de caminata entre andenes y mostrar la ruta.

**Estructura:**
```sql
line_transfer:
  id: INTEGER PRIMARY KEY

  -- Paradas origen/destino
  from_stop_id: VARCHAR(100)  -- ej: METRO_12345
  to_stop_id: VARCHAR(100)    -- ej: RENFE_67890

  -- Líneas específicas
  from_line: VARCHAR(50)      -- ej: L6
  to_line: VARCHAR(50)        -- ej: C4

  -- Coordenadas de cada andén (para mostrar ruta de caminata)
  from_lat: FLOAT             -- latitud andén origen
  from_lon: FLOAT             -- longitud andén origen
  to_lat: FLOAT               -- latitud andén destino
  to_lon: FLOAT               -- longitud andén destino

  -- Tiempo de transfer
  min_transfer_time: INTEGER  -- segundos de caminata
  transfer_type: INTEGER      -- tipo GTFS (0-5)

  -- Metadata
  network_id: VARCHAR(20)
  source: VARCHAR(50)         -- 'gtfs', 'proximity', 'osm', 'manual'
```

**Ejemplo real:**
```
from_stop_id: METRO_12345 (Nuevos Ministerios)
to_stop_id: RENFE_67890 (Nuevos Ministerios Cercanías)
from_line: L6
to_line: C4
from_lat: 40.446620
from_lon: -3.692410
to_lat: 40.447100
to_lon: -3.691800
min_transfer_time: 180 (3 minutos)
```

---

## 2. Estructura de Base de Datos

### 2.1 Tabla gtfs_stops (campos cor_*)

```sql
ALTER TABLE gtfs_stops ADD COLUMN cor_metro TEXT;
ALTER TABLE gtfs_stops ADD COLUMN cor_cercanias TEXT;
ALTER TABLE gtfs_stops ADD COLUMN cor_tranvia TEXT;
ALTER TABLE gtfs_stops ADD COLUMN cor_ml TEXT;
```

**Migraciones:**
- `027_add_correspondence_columns_to_stops.py` - Añade cor_ml y cor_cercanias

### 2.2 Tabla line_transfer

```sql
CREATE TABLE line_transfer (
    id SERIAL PRIMARY KEY,
    from_stop_id VARCHAR(100) NOT NULL,
    to_stop_id VARCHAR(100) NOT NULL,
    from_route_id VARCHAR(100),
    to_route_id VARCHAR(100),
    from_lat FLOAT,
    from_lon FLOAT,
    to_lat FLOAT,
    to_lon FLOAT,
    transfer_type INTEGER NOT NULL DEFAULT 0,
    min_transfer_time INTEGER,
    from_stop_name VARCHAR(255),
    to_stop_name VARCHAR(255),
    from_line VARCHAR(50),
    to_line VARCHAR(50),
    network_id VARCHAR(20),
    instructions TEXT,
    exit_name VARCHAR(255),
    source VARCHAR(50)
);

CREATE INDEX ix_line_transfer_from_stop_id ON line_transfer(from_stop_id);
CREATE INDEX ix_line_transfer_to_stop_id ON line_transfer(to_stop_id);
CREATE INDEX ix_line_transfer_network_id ON line_transfer(network_id);
```

**Migraciones:**
- `026_create_line_transfer_table.py` - Crea la tabla
- `028_add_coords_to_line_transfer.py` - Añade columnas de coordenadas + tabla discrepancies

### 2.3 Tabla correspondence_discrepancies

Para revisión manual cuando hay diferencias entre fuentes de datos:

```sql
CREATE TABLE correspondence_discrepancies (
    id SERIAL PRIMARY KEY,
    stop_id VARCHAR(100) NOT NULL,
    stop_name VARCHAR(255),
    field VARCHAR(50) NOT NULL,        -- cor_metro, cor_cercanias, etc.
    value_in_db TEXT,
    value_in_csv TEXT,
    discrepancy_type VARCHAR(50),      -- 'missing_in_db', 'missing_in_csv', 'different'
    reviewed BOOLEAN DEFAULT FALSE,
    resolution VARCHAR(50),            -- 'keep_db', 'use_csv', 'manual'
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 3. Fuentes de Datos

### 3.1 Para cor_* (correspondencias)

| Fuente | Método | Ejemplo |
|--------|--------|---------|
| **OpenStreetMap** | Overpass API | TRAM_BARCELONA cor_tranvia |
| **GTFS transfers.txt** | Importación directa | TMB, Euskotren, Renfe |
| **Manual** | SQL directo | Correcciones puntuales |

**Script de ejemplo (OSM):**
```bash
# Extraer líneas de tranvía de Barcelona desde OSM
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:90];
area["name"="Catalunya"]->.cat;
relation["type"="route"]["route"="tram"]["ref"~"^T[1-6]$"](area.cat);
out body;
>;
out skel qt;
'
```

### 3.2 Para line_transfer (transfers entre andenes)

| Fuente | Registros | Descripción |
|--------|-----------|-------------|
| GTFS transfers.txt | 98 | Datos oficiales de operadores |
| Proximidad (<250m) | 592 | Calculados automáticamente |
| OSM | Pendiente | Coordenadas de andenes |
| Manual | Variable | Correcciones y adiciones |

### 3.3 Para coordenadas de andenes

Las coordenadas específicas de cada andén (`from_lat/lon`, `to_lat/lon`) deben extraerse de:

1. **OpenStreetMap** - Nodos con tags `railway=platform` o `public_transport=platform`
2. **Google Maps** - Verificación manual cuando OSM no tiene datos
3. **GTFS stops.txt** - Algunos operadores incluyen coordenadas de plataformas

---

## 4. Estado Actual (2026-01-26)

### 4.1 Correspondencias (cor_*)

| Métrica | Valor |
|---------|-------|
| Total stops | 6466 |
| con cor_metro | 2122 (33%) |
| con cor_cercanias | 2085 (32%) |
| con cor_tranvia | 358 (6%) |
| con cor_ml | 62 (1%) |

### 4.2 Line Transfers

| Fuente | Registros |
|--------|-----------|
| proximity | 592 |
| gtfs | 94 |
| nap | 4 |
| **TOTAL** | **690** |

### 4.3 Coordenadas de Andenes - ESTADO DETALLADO

**Resumen:** 690/690 transfers tienen coordenadas, pero la mayoría usa fallback de gtfs_stops (coordenadas generales), no coordenadas específicas por andén/línea.

#### Redes con datos OSM extraídos (coordenadas por línea)

| Red | Estaciones | Pares estación-línea | Intercambiadores | Archivo CSV |
|-----|------------|---------------------|------------------|-------------|
| Metro Madrid | 235 | 281 | 36 | `docs/osm_coords/metro_madrid_by_line.csv` |
| Metro Barcelona | 187 | 259 | 46 | `docs/osm_coords/metro_bcn_by_line.csv` |
| Metro Bilbao | 48 | 62 | 12 | `docs/osm_coords/metro_bilbao_by_line.csv` |
| **TOTAL OSM** | **470** | **602** | **94** | |

#### Redes SIN datos OSM (usan fallback gtfs_stops)

| Red | Transfers afectados | Tipo de transporte | Estado OSM |
|-----|--------------------|--------------------|------------|
| Renfe Cercanías (10T, 40T, etc.) | ~200 | Tren cercanías | ❌ No extraído |
| FGC | ~30 | Ferrocarril | ❌ No extraído |
| Euskotren | 13 | Ferrocarril | ❌ No extraído |
| TRAM Barcelona | ~20 | Tranvía | ❌ No extraído |
| Metro Ligero Madrid (ML) | ~6 | Metro ligero | ❌ No extraído |
| Metro Valencia | ~4 | Metro | ❌ No extraído |
| Metro Sevilla | ~2 | Metro | ❌ No extraído |
| Metro Málaga | 4 | Metro | ❌ No extraído |
| Metro Granada | - | Metro | ❌ No extraído |
| Metro Tenerife | 2 | Metro | ❌ No extraído |
| Tranvía Zaragoza | 2 | Tranvía | ❌ No extraído |
| Tranvía Murcia | - | Tranvía | ❌ No extraído |

#### Problema actual de coordenadas

Cuando un transfer conecta:
- **Metro → Cercanías** (ej: L6 Nuevos Ministerios → C4 Nuevos Ministerios)
  - `from_lat/lon` = coordenadas OSM del andén L6 ✅
  - `to_lat/lon` = coordenadas generales de gtfs_stops ⚠️ (no son del andén específico)

Esto significa que para mostrar la ruta de caminata entre andenes, el destino usa la coordenada general de la estación, no la del andén C4 específico.

#### Queries Overpass pendientes de ejecutar

```bash
# Renfe Cercanías - España completa
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:180];
area["ISO3166-1"="ES"]->.spain;
relation["type"="route"]["route"="train"]["operator"~"Renfe|RENFE"](area.spain);
out body;
>;
out skel qt;
'

# FGC - Cataluña
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:120];
area["name"="Catalunya"]->.cat;
relation["type"="route"]["route"="train"]["operator"~"FGC|Ferrocarrils"](area.cat);
out body;
>;
out skel qt;
'

# Tranvía Barcelona (T1-T6)
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:90];
area["name"="Catalunya"]->.cat;
relation["type"="route"]["route"="tram"]["ref"~"^T[1-6]$"](area.cat);
out body;
>;
out skel qt;
'

# Metro Ligero Madrid (ML1-ML3)
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:90];
area["name"="Comunidad de Madrid"]->.madrid;
relation["type"="route"]["route"="light_rail"](area.madrid);
out body;
>;
out skel qt;
'

# Euskotren
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:90];
area["name"="Euskadi"]->.euskadi;
relation["type"="route"]["route"="train"]["operator"~"Euskotren"](area.euskadi);
out body;
>;
out skel qt;
'
```

---

## 5. API Endpoints

### 5.1 GET /api/v1/gtfs/stops/{stop_id}/transfers

Devuelve transfers desde/hacia una parada.

**Parámetros:**
- `stop_id`: ID de la parada
- `direction` (opcional): `from` o `to`

**Respuesta:**
```json
{
  "id": 100,
  "from_stop_id": "METRO_12345",
  "to_stop_id": "RENFE_67890",
  "from_line": "L6",
  "to_line": "C4",
  "from_lat": 40.446620,
  "from_lon": -3.692410,
  "to_lat": 40.447100,
  "to_lon": -3.691800,
  "min_transfer_time": 180,
  "transfer_type": 2,
  "network_id": "METRO",
  "source": "proximity"
}
```

### 5.2 Campos en respuestas de stops

```json
{
  "id": "METRO_12345",
  "name": "Nuevos Ministerios",
  "cor_metro": "L6, L8, L10",
  "cor_cercanias": "C3, C4a, C4b, C7, C8a, C8b, C10",
  "is_hub": true
}
```

**is_hub:** `true` si la parada tiene 2+ tipos de transporte diferentes (metro + cercanías, etc.)

---

## 6. Tareas Pendientes

### Alta Prioridad - Coordenadas de Andenes

| Tarea | Red | Tipo OSM | Estado |
|-------|-----|----------|--------|
| Extraer coords Renfe Cercanías | 10T, 40T, 51T, etc. | `route=train` + `operator=Renfe` | ❌ Pendiente |
| Extraer coords FGC | S1, S2, L8, etc. | `route=train` + `operator=FGC` | ❌ Pendiente |
| Extraer coords Euskotren | E1, E2, E3 | `route=train` + `operator=Euskotren` | ❌ Pendiente |
| Extraer coords TRAM BCN | T1-T6 | `route=tram` | ❌ Pendiente |
| Extraer coords ML Madrid | ML1, ML2, ML3 | `route=light_rail` | ❌ Pendiente |

### Alta Prioridad - Otros
- [ ] Completar Passeig de Gràcia (L2, L4 en cor_metro)

### Media Prioridad
- [ ] Extraer coords Metro Valencia (si existe en OSM)
- [ ] Extraer coords Metro Sevilla (si existe en OSM)
- [ ] Revisar SFM_MALLORCA (32% cor_metro)
- [ ] Añadir transfers 250m-500m que tengan sentido

### Baja Prioridad
- [ ] Investigar API Valencia (devuelve vacío)
- [ ] Metro/Tranvía Sevilla (requiere NAP)
- [ ] Metro Granada, Málaga, Tenerife (coords OSM si disponible)

---

## 7. Archivos Relevantes

```
# Modelos
src/gtfs_bc/transfer/infrastructure/models/line_transfer_model.py
src/gtfs_bc/transfer/infrastructure/models/discrepancy_model.py
src/gtfs_bc/stop/infrastructure/models/stop_model.py

# Migraciones
alembic/versions/026_create_line_transfer_table.py
alembic/versions/027_add_correspondence_columns_to_stops.py
alembic/versions/028_add_coords_to_line_transfer.py

# Scripts de importación
scripts/import_transfers.py              # Importa desde GTFS transfers.txt
scripts/import_proximity_transfers.py    # Calcula transfers por proximidad
scripts/update_tram_barcelona_cor_tranvia.sql  # Actualiza cor_tranvia BCN

# Routers API
adapters/http/api/gtfs/routers/query_router.py   # Endpoint transfers
adapters/http/api/gtfs/routers/network_router.py # transport_type

# Documentación
docs/CORRESPONDENCIAS_Y_TRANSFERS.md     # Este archivo
docs/ANALISIS_CORRESPONDENCIAS_SERVIDOR.md
docs/GTFS_OPERATORS_STATUS.md
```

---

## 8. Instrucciones de Desarrollo

### 8.1 Añadir correspondencias desde OSM

```bash
# 1. Extraer datos de OSM con Overpass API
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json];
area["name"="Madrid"]->.madrid;
relation["type"="route"]["route"="subway"](area.madrid);
out body;
>;
out skel qt;
' > /tmp/metro_madrid.json

# 2. Procesar JSON y generar SQL
python3 scripts/process_osm_metro.py > /tmp/update_cor_metro.sql

# 3. Ejecutar en BD local
psql -d renfeserver_dev < /tmp/update_cor_metro.sql

# 4. Verificar resultados
psql -d renfeserver_dev -c "SELECT name, cor_metro FROM gtfs_stops WHERE cor_metro IS NOT NULL LIMIT 10;"

# 5. Si OK, ejecutar en producción
ssh root@juanmacias.com "sudo -u postgres psql renfeserver_prod < /tmp/update_cor_metro.sql"
```

### 8.2 Añadir coordenadas de andenes

```bash
# 1. Extraer plataformas de OSM
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json];
area["name"="Madrid"]->.madrid;
(
  node["railway"="platform"](area.madrid);
  way["railway"="platform"](area.madrid);
);
out body;
>;
out skel qt;
' > /tmp/platforms_madrid.json

# 2. Procesar y actualizar line_transfer
python3 scripts/update_transfer_coords.py

# 3. Verificar
psql -d renfeserver_dev -c "SELECT from_stop_name, from_line, from_lat, from_lon FROM line_transfer WHERE from_lat IS NOT NULL LIMIT 10;"
```

### 8.3 Conexión al servidor

```bash
# SSH al servidor
ssh -i ~/.ssh/id_ed25519 root@juanmacias.com

# Base de datos en servidor
sudo -u postgres psql renfeserver_prod

# Subir archivos
scp -i ~/.ssh/id_ed25519 archivo.py root@juanmacias.com:/var/www/renfeserver/scripts/

# Reiniciar servicio
ssh -i ~/.ssh/id_ed25519 root@juanmacias.com "systemctl restart renfeserver"
```

---

## 9. Historial de Cambios

### 2026-01-26 (sesión actual)

**Transfers por proximidad importados:**
- 592 transfers nuevos (296 bidireccionales)
- Conectan Metro/Tranvía/FGC/ML con Cercanías a <250m
- Total: 690 transfers (592 proximity + 94 gtfs + 4 nap)

**Coordenadas de andenes añadidas:**
- Extraídas de OSM (Overpass API) para:
  - Metro Madrid: 235 estaciones, 36 intercambiadores
  - Metro Barcelona: 187 estaciones, 46 intercambiadores
  - Metro Bilbao: 48 estaciones, 12 intercambiadores
- 690/690 transfers con from_lat/lon y to_lat/lon

**Fuentes de coordenadas:**
1. OSM (rutas de metro con stop_positions) - coordenadas por línea
2. Fallback: tabla gtfs_stops - coordenadas generales

**TRAM_BARCELONA cor_tranvia:**
- 172 paradas con cor_tranvia poblado desde OSM
- Líneas T1-T6 asignadas

**Infraestructura:**
- Migración 028 ejecutada
- BD local sincronizada con producción

### 2026-01-25
- Migraciones 026, 027 ejecutadas
- 98 transfers importados (GTFS original)
- Campos transport_type e is_hub añadidos a API

---

## 10. Scripts de Importación

### import_proximity_transfers.py

```bash
# Ejecutar
.venv/bin/python scripts/import_proximity_transfers.py

# En servidor
ssh root@juanmacias.com "cd /var/www/renfeserver && .venv/bin/python scripts/import_proximity_transfers.py"
```

**Qué hace:**
1. Busca paradas Metro/Tranvía/FGC/ML
2. Busca paradas Renfe Cercanías
3. Calcula distancia haversine entre todas
4. Crea transfers bidireccionales para distancia < 250m
5. Tiempo de caminata: distancia / 1.2 m/s

**Redes procesadas:**
- TMB_METRO (Barcelona): 215 conexiones
- METRO (Madrid): 26 conexiones
- METRO_BILBAO: 16 conexiones
- FGC: 17 conexiones
- TRAM: 10 conexiones
- ML (Metro Ligero): 3 conexiones
- METRO_VALENCIA: 2 conexiones
- TRANVIA (Zaragoza): 2 conexiones
- METRO_MALAGA: 4 conexiones
- METRO_SEV: 1 conexión

### Extracción de coordenadas de andenes (OSM)

```bash
# 1. Descargar rutas de metro de OSM
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:120];
area["name"="Comunidad de Madrid"]->.madrid;
relation["type"="route"]["route"="subway"](area.madrid);
out body;
>;
out skel qt;
' > /tmp/metro_madrid_routes.json

# 2. Descargar estaciones
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:60];
area["name"="Comunidad de Madrid"]->.madrid;
node["railway"="station"]["station"="subway"](area.madrid);
out body;
' > /tmp/metro_madrid_stations.json

# 3. Procesar y generar CSV con coordenadas por línea
# (script Python que matchea stops de rutas con estaciones por proximidad)
```

**Resultado:** CSV con formato:
```csv
station_name,line,lat,lon
Nuevos Ministerios,L10,40.4452235,-3.6913658
Nuevos Ministerios,L8,40.4454795,-3.6915608
```

**Intercambiadores encontrados (coords diferentes por línea):**
```
Avenida de América (Madrid):
    L4: (40.438002, -3.678090)
    L6: (40.437782, -3.678183)
    L7: (40.437419, -3.679145)
    L9: (40.438138, -3.679117)

Zazpikaleak (Bilbao):
    L1: (43.25964, -2.92077)
    L2: (43.25966, -2.92075)
    L3: (43.26024, -2.92186)
```

---

## 11. Limitaciones Actuales

### 11.1 Coordenadas de Andenes - Solo 3 Redes

**Estado actual (2026-01-26):**
- ✅ Metro Madrid - 281 pares estación-línea con coords específicas
- ✅ Metro Barcelona - 259 pares estación-línea con coords específicas
- ✅ Metro Bilbao - 62 pares estación-línea con coords específicas
- ❌ **TODO EL RESTO** - usa coordenadas generales de gtfs_stops

**Consecuencia:**
Para un transfer como "L6 Nuevos Ministerios → C4 Nuevos Ministerios":
- `from_lat/lon` = coords del andén L6 (específicas de OSM) ✅
- `to_lat/lon` = coords de la estación general (no del andén C4) ⚠️

### 11.2 Redes pendientes de extracción OSM

| Red | Disponibilidad OSM | Notas |
|-----|-------------------|-------|
| Renfe Cercanías | ⚠️ Parcial | Algunas líneas mapeadas, revisar cobertura |
| FGC | ⚠️ Parcial | Líneas principales probablemente disponibles |
| Euskotren | ⚠️ Parcial | Revisar mapeo en País Vasco |
| TRAM Barcelona | ✅ Disponible | T1-T6 mapeados en OSM |
| Metro Ligero Madrid | ✅ Disponible | ML1-ML3 mapeados |
| Metro Valencia | ⚠️ Desconocido | Verificar disponibilidad |
| Metro Sevilla | ⚠️ Desconocido | Verificar disponibilidad |
| Otros metros | ⚠️ Desconocido | Málaga, Granada, Tenerife |

### 11.3 Matching de nombres

**Problema:** Diferentes redes usan nombres distintos para la misma estación:
- GTFS: "Nuevos Ministerios"
- OSM: "Nuevos Ministerios" o "Estación de Nuevos Ministerios"

**Solución actual:** Normalización de nombres (minúsculas, sin acentos, sin prefijos comunes)

### 11.4 Líneas sin asignar

Muchos transfers (especialmente de `proximity`) no tienen `from_line` ni `to_line` asignados porque se crean a partir de paradas, no de rutas. Esto dificulta asignar coordenadas específicas de andén.

**Campos afectados en line_transfer:**
```sql
SELECT COUNT(*) FROM line_transfer WHERE from_line IS NULL;  -- ~400 registros
SELECT COUNT(*) FROM line_transfer WHERE to_line IS NULL;    -- ~500 registros
```

---

## 12. Proceso de Extracción OSM - Guía Completa

Esta sección documenta paso a paso cómo extraer coordenadas de andenes desde OpenStreetMap.

### 12.1 Estructura de datos OSM

En OSM, las líneas de transporte público se modelan como **relations** de tipo `route`:

```
relation (type=route, route=subway/train/tram/light_rail)
├── tags: ref (L1, C4, T2), name, operator, colour
└── members:
    ├── way (la vía)
    └── node (paradas) con role="stop" o "platform"
```

### 12.2 Queries Overpass por tipo de transporte

#### Metro (subway)
```bash
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:120];
area["name"="AREA_NAME"]->.area;
relation["type"="route"]["route"="subway"](area.area);
out body;
>;
out skel qt;
' > /tmp/metro_AREA.json
```

#### Tren (cercanías, FGC, Euskotren)
```bash
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:180];
area["ISO3166-1"="ES"]->.spain;
relation["type"="route"]["route"="train"]["operator"~"Renfe|RENFE|FGC|Euskotren"](area.spain);
out body;
>;
out skel qt;
' > /tmp/trains_spain.json
```

#### Tranvía
```bash
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:90];
area["name"="Catalunya"]->.cat;
relation["type"="route"]["route"="tram"](area.cat);
out body;
>;
out skel qt;
' > /tmp/tram_cat.json
```

#### Metro Ligero
```bash
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=
[out:json][timeout:90];
area["name"="Comunidad de Madrid"]->.madrid;
relation["type"="route"]["route"="light_rail"](area.madrid);
out body;
>;
out skel qt;
' > /tmp/metro_ligero_madrid.json
```

### 12.3 Script Python para procesar respuesta OSM

```python
import json
from collections import defaultdict

def process_osm_routes(json_file):
    """
    Procesa la respuesta de Overpass y genera CSV con coordenadas por línea.
    """
    with open(json_file) as f:
        data = json.load(f)

    # Indexar nodos por ID
    nodes = {e['id']: e for e in data['elements'] if e['type'] == 'node'}

    # Procesar relaciones (rutas)
    routes = [e for e in data['elements'] if e['type'] == 'relation']

    # Dict: station_name -> {line -> (lat, lon)}
    coords_by_station = defaultdict(dict)

    for route in routes:
        line = route.get('tags', {}).get('ref', 'Unknown')

        # Obtener nodos con role=stop o platform
        for member in route.get('members', []):
            if member['type'] == 'node' and member.get('role') in ['stop', 'platform', '']:
                node_id = member['ref']
                if node_id in nodes:
                    node = nodes[node_id]
                    name = node.get('tags', {}).get('name', '')
                    if name:
                        lat = node['lat']
                        lon = node['lon']
                        coords_by_station[name][line] = (lat, lon)

    # Generar CSV
    print("station_name,line,lat,lon")
    for station in sorted(coords_by_station.keys()):
        for line in sorted(coords_by_station[station].keys()):
            lat, lon = coords_by_station[station][line]
            print(f"{station},{line},{lat},{lon}")

if __name__ == "__main__":
    import sys
    process_osm_routes(sys.argv[1])
```

**Uso:**
```bash
python3 process_osm.py /tmp/metro_madrid_routes.json > /tmp/metro_madrid_by_line.csv
```

### 12.4 Actualizar coordenadas en line_transfer

Una vez generado el CSV, actualizar la BD:

```python
import csv
from collections import defaultdict
from sqlalchemy import create_engine, text
import unicodedata
import re

def normalize(s):
    """Normaliza nombre para matching."""
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.lower().strip()
    s = re.sub(r'^(estacion de |estacio |station )', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s

# Cargar CSV en dict
coords = defaultdict(dict)
with open('/tmp/metro_madrid_by_line.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = normalize(row['station_name'])
        line = row['line']
        coords[name][line] = (float(row['lat']), float(row['lon']))

# Actualizar BD
engine = create_engine('postgresql://...')
with engine.connect() as conn:
    transfers = conn.execute(text("SELECT * FROM line_transfer")).fetchall()

    for t in transfers:
        from_name = normalize(t.from_stop_name or '')
        to_name = normalize(t.to_stop_name or '')

        updates = {}

        # from coords
        if from_name in coords:
            if t.from_line and t.from_line in coords[from_name]:
                lat, lon = coords[from_name][t.from_line]
            else:
                lat, lon = list(coords[from_name].values())[0]
            updates['from_lat'] = lat
            updates['from_lon'] = lon

        # to coords
        if to_name in coords:
            if t.to_line and t.to_line in coords[to_name]:
                lat, lon = coords[to_name][t.to_line]
            else:
                lat, lon = list(coords[to_name].values())[0]
            updates['to_lat'] = lat
            updates['to_lon'] = lon

        if updates:
            conn.execute(
                text(f"UPDATE line_transfer SET ... WHERE id = :id"),
                {**updates, 'id': t.id}
            )
    conn.commit()
```

### 12.5 Verificación

```sql
-- Transfers con coordenadas diferentes (intercambiadores correctos)
SELECT from_stop_name, from_line, to_line,
       from_lat, from_lon, to_lat, to_lon
FROM line_transfer
WHERE from_lat != to_lat OR from_lon != to_lon
LIMIT 20;

-- Resumen por red
SELECT network_id,
       COUNT(*) as total,
       COUNT(CASE WHEN from_lat != to_lat THEN 1 END) as coords_diferentes
FROM line_transfer
GROUP BY network_id
ORDER BY total DESC;
```

---

## 13. Plan de Importación de Plataformas - TODAS LAS REDES

### 13.1 Cambio de Modelo Pendiente

**Migración 030:** Cambiar `line` → `lines` en `stop_platform`
```sql
ALTER TABLE stop_platform RENAME COLUMN line TO lines;
ALTER TABLE stop_platform ALTER COLUMN lines TYPE VARCHAR(255);
```

### 13.2 Estrategia por Tipo de Transporte

#### METRO (coords diferentes por línea)

| Red | Prefijo stop_id | Fuente OSM | Estado |
|-----|-----------------|------------|--------|
| Metro Madrid | METRO_ | `route=subway` | ✅ 278 plataformas |
| TMB Metro Barcelona | TMB_METRO_ | `route=subway` | ✅ 157 plataformas |
| Metro Bilbao | METRO_BILBAO_ | `route=subway` | ✅ 55 plataformas |
| Metro Valencia | METRO_VALENCIA_ | `route=subway` | ❌ Pendiente |
| Metro Sevilla | METRO_SEV_ | `route=subway` | ❌ Pendiente |
| Metro Málaga | METRO_MALAGA_ | `route=subway` | ❌ Pendiente |
| Metro Granada | METRO_GRANADA_ | `route=subway` | ❌ Pendiente |
| Metro Tenerife | METRO_TENERIFE_ | `route=subway` | ❌ Pendiente |

**Lógica:** Una entrada por línea (L1, L2, etc.) con coords específicas de OSM.

#### CERCANÍAS/RODALIES (coords agrupadas por andén)

| Red | Prefijo stop_id | Fuente | Intercambiadores clave |
|-----|-----------------|--------|------------------------|
| Cercanías Madrid (10T) | RENFE_ | OSM plataformas + GTFS fallback | Nuevos Ministerios, Atocha, Chamartín, Sol, Príncipe Pío |
| Rodalies Barcelona (50T) | RENFE_ | OSM plataformas + GTFS fallback | Passeig de Gràcia, Sants, Plaça Catalunya |
| Cercanías Valencia (40T) | RENFE_ | GTFS | Xàtiva, Nord |
| Cercanías Sevilla (51T) | RENFE_ | GTFS | Santa Justa, San Bernardo |
| Cercanías Bilbao (60T) | RENFE_ | GTFS | Abando |
| Otros núcleos | RENFE_ | GTFS | - |

**Lógica:**
1. **Intercambiadores grandes:** Buscar plataformas en OSM, asignar líneas manualmente
2. **Resto de estaciones:** Usar coord de GTFS, agrupar todas las líneas en `lines`

**Ejemplo intercambiador (OSM disponible):**
```
RENFE_18002 (Nuevos Ministerios):
  lines: "C3, C4a, C4b" → (40.4453, -3.6920)  -- Andén 1
  lines: "C7, C8a, C8b, C10" → (40.4452, -3.6925)  -- Andén 2
  lines: "C2" → (40.4452, -3.6931)  -- Andén 3
```

**Ejemplo estación normal (solo GTFS):**
```
RENFE_18100 (Getafe Centro):
  lines: "C3, C4a, C4b" → (40.3051, -3.7329)  -- Una sola coord
```

#### FGC (coords por línea donde haya datos)

| Red | Prefijo stop_id | Fuente |
|-----|-----------------|--------|
| FGC Barcelona | FGC_ | OSM `route=train, operator=FGC` |

**Estado actual:** 54 plataformas importadas (parcial)
**Pendiente:** Completar con rutas S1, S2, L6, L7, L8, L12

#### EUSKOTREN (coords agrupadas)

| Red | Prefijo stop_id | Fuente |
|-----|-----------------|--------|
| Euskotren | EUSKOTREN_ | OSM `route=train, operator=Euskotren` + GTFS fallback |

**Lógica:** Similar a cercanías. Líneas E1, E2, E3 suelen compartir andén.

#### TRANVÍA (coords por línea)

| Red | Prefijo stop_id | Fuente OSM |
|-----|-----------------|------------|
| TRAM Barcelona | TRAM_BARCELONA_ | `route=tram, ref=T1-T6` |
| Tranvía Zaragoza | TRANVIA_ZARAGOZA_ | `route=tram` |
| Tranvía Alicante | TRAM_ALICANTE_ | `route=tram` |
| Tranvía Murcia | TRANVIA_MURCIA_ | `route=tram` |

**Lógica:** Una entrada por línea (T1, T2, etc.)

#### METRO LIGERO (coords por línea)

| Red | Prefijo stop_id | Fuente OSM |
|-----|-----------------|------------|
| Metro Ligero Madrid | ML_ | `route=light_rail` |

**Lógica:** Una entrada por línea (ML1, ML2, ML3)

### 13.3 Proceso de Importación

```
Para cada red:
1. Intentar extraer de OSM (plataformas con coords por línea)
2. Si OSM tiene datos específicos → usar coords de OSM
3. Si OSM no tiene datos o son incompletos → usar GTFS (coord general)
4. Si varias líneas tienen mismas coords → agrupar en `lines`
5. Para intercambiadores clave → matching manual de líneas a plataformas
```

### 13.4 Intercambiadores que Requieren Matching Manual

Estaciones donde hay múltiples plataformas en OSM pero sin indicar qué líneas pasan:

| Ciudad | Estación | Plataformas OSM | Líneas a asignar |
|--------|----------|-----------------|------------------|
| Madrid | Nuevos Ministerios | 4 | C2, C3, C4a, C4b, C7, C8a, C8b, C10 |
| Madrid | Atocha Cercanías | ~10 | C1, C2, C3, C4, C5, C7, C10 |
| Madrid | Chamartín | ~6 | C1, C2, C3, C4, C7, C8, C10 |
| Madrid | Sol | 2 | C3, C4a, C4b |
| Madrid | Príncipe Pío | 2 | C7, C10 |
| Barcelona | Passeig de Gràcia | 4 | R1, R2, R3, R4 |
| Barcelona | Sants | ~8 | R1, R2, R3, R4, R11-R16 |
| Barcelona | Plaça Catalunya | 2 | R1, R2, R3, R4 |

**Fuentes para matching:**
1. Google Maps (vista satélite)
2. Planos oficiales de ADIF/Renfe
3. Wikipedia (esquemas de estaciones)

### 13.5 Orden de Ejecución

1. **Migración 030:** Cambiar `line` → `lines`
2. **Re-importar Metro** (ya hecho, solo actualizar campo)
3. **Importar Cercanías Madrid:** OSM plataformas + GTFS + matching manual
4. **Importar Rodalies Barcelona:** OSM + GTFS + matching manual
5. **Importar FGC:** Completar con OSM
6. **Importar Euskotren:** OSM + GTFS
7. **Importar Tranvías:** OSM
8. **Importar Metro Ligero:** OSM
9. **Importar Metros secundarios:** Valencia, Sevilla, Málaga, etc.
10. **Importar resto de Cercanías:** GTFS (Sevilla, Valencia, Bilbao, etc.)
