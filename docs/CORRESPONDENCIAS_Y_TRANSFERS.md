# Correspondencias y Transfers - Documentación Técnica

**Fecha:** 2026-01-26
**Autor:** Claude Code

---

## 1. Conceptos Clave

### 1.1 Correspondencias (cor_*)

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

### 4.3 Coordenadas de Andenes

| Campo | Estado |
|-------|--------|
| from_lat/lon | 0% poblado |
| to_lat/lon | 0% poblado |

**Pendiente:** Extraer coordenadas de andenes desde OSM para los 690 transfers existentes.

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

### Alta Prioridad
- [ ] Extraer coordenadas de andenes desde OSM para transfers existentes
- [ ] Completar Passeig de Gràcia (L2, L4 en cor_metro)

### Media Prioridad
- [ ] Revisar SFM_MALLORCA (32% cor_metro)
- [ ] Añadir transfers 250m-500m que tengan sentido

### Baja Prioridad
- [ ] Investigar API Valencia (devuelve vacío)
- [ ] Metro/Tranvía Sevilla (requiere NAP)

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

1. **Coordenadas duplicadas para mismo nombre:**
   - Si Metro y Cercanías tienen mismo nombre (ej: "Nuevos Ministerios"), ambos obtienen coords de OSM (metro)
   - Solución pendiente: usar stop_id para distinguir tipo de parada

2. **Líneas sin from_line/to_line:**
   - Muchos transfers no tienen la línea específica asignada
   - Usan la primera coordenada disponible de esa estación

3. **Redes sin datos OSM:**
   - Metro Valencia, Metro Sevilla, etc. no tienen rutas en OSM
   - Usan coordenadas generales de gtfs_stops
