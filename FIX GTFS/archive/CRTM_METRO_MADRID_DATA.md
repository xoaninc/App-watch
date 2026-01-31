# Datos CRTM Metro Madrid

**Fecha:** 2026-01-28
**Estado:** Implementado

## Resumen

Implementación de 5 nuevas fuentes de datos del CRTM (Consorcio Regional de Transportes de Madrid) para Metro Madrid, reemplazando datos generados o de OSM por datos oficiales.

## Fuente de Datos

**API Base:** `https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M4_Red/FeatureServer`

| Layer | Nombre | Geometría | Registros | Uso |
|-------|--------|-----------|-----------|-----|
| 0 | M4_Estaciones | Punto | ~242 | Ya importado |
| 1 | M4_Accesos | Punto | ~156 | **NUEVO**: Bocas de metro |
| 2 | M4_Vestibulos | Punto | ~130 | **NUEVO**: Vestíbulos |
| 3 | M4_Andenes | Punto | ~147 | **NUEVO**: Andenes |
| 4 | M4_Tramos | Polilínea | ~540 | **NUEVO**: Shapes reales |
| 5 | M4_ParadasPorItinerario | Tabla | ~540 | **NUEVO**: Tiempos de viaje |

**Sistema de coordenadas:** UTM EPSG:25830 → WGS84 EPSG:4326 (usando pyproj)

---

## Componentes Implementados

### 1. Shapes Reales (Prioridad Alta)

**Problema:** Los shapes generados con BRouter no seguían las vías reales del metro.

**Solución:** Importar geometrías directamente de CRTM Layer 4.

**Script:** `scripts/import_metro_madrid_shapes.py`

```bash
# Importar todas las líneas
python scripts/import_metro_madrid_shapes.py

# Importar línea específica
python scripts/import_metro_madrid_shapes.py --route METRO_10

# Ver qué haría sin ejecutar
python scripts/import_metro_madrid_shapes.py --dry-run
```

**Formato shape_id:** `METRO_MAD_{linea}_CRTM`
Ejemplos: `METRO_MAD_1_CRTM`, `METRO_MAD_7B_CRTM`

---

### 2. Andenes/Platforms (Prioridad Alta)

**Problema:** Los datos de andenes provenían de OSM y podían ser inexactos.

**Solución:** Importar ubicaciones oficiales de CRTM Layer 3.

**Script:** `scripts/import_metro_madrid_platforms.py`

```bash
python scripts/import_metro_madrid_platforms.py
python scripts/import_metro_madrid_platforms.py --dry-run
```

**Tabla:** `stop_platform` (existente, se repuebla con source='crtm')

---

### 3. Stop Times Mejorados (Prioridad Media)

**Problema:** Tiempos entre estaciones fijos (2 min) no reflejaban la realidad.

**Solución:** Calcular tiempos usando distancia y velocidad de CRTM Layer 5.

**Script:** `scripts/generate_metro_madrid_trips.py` (modificado)

```bash
# Con tiempos estimados (comportamiento anterior)
python scripts/generate_metro_madrid_trips.py

# Con tiempos reales de CRTM
python scripts/generate_metro_madrid_trips.py --use-crtm-times
```

**Fórmula:**
```
tiempo_segundos = distancia_metros / (velocidad_kmh / 3.6)
tiempo_total = tiempo_viaje + 30s (dwell time)
```

---

### 4. Accesos/Bocas (Prioridad Baja)

**Nueva funcionalidad:** Almacenar las bocas de acceso al metro.

**Tabla:** `stop_access` (nueva)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | Integer | PK autoincrement |
| stop_id | String(100) | FK a gtfs_stops |
| name | String(255) | Nombre del acceso |
| lat, lon | Float | Coordenadas WGS84 |
| street | String(255) | Calle |
| street_number | String(20) | Número |
| opening_time | Time | Hora apertura |
| closing_time | Time | Hora cierre |
| wheelchair | Boolean | Accesibilidad |
| level | Integer | Nivel de entrada |
| source | String(50) | 'crtm' |

**Script:** `scripts/import_metro_madrid_accesses.py`

```bash
python scripts/import_metro_madrid_accesses.py
```

---

### 5. Vestíbulos (Prioridad Baja)

**Nueva funcionalidad:** Almacenar los vestíbulos interiores.

**Tabla:** `stop_vestibule` (nueva)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | Integer | PK autoincrement |
| stop_id | String(100) | FK a gtfs_stops |
| name | String(255) | Nombre del vestíbulo |
| lat, lon | Float | Coordenadas WGS84 |
| level | Integer | Profundidad (-1, -2...) |
| vestibule_type | String(50) | Tipo de vestíbulo |
| turnstile_type | String(50) | Tipo de torniquete |
| opening_time | Time | Hora apertura |
| closing_time | Time | Hora cierre |
| wheelchair | Boolean | Accesibilidad |
| source | String(50) | 'crtm' |

**Script:** `scripts/import_metro_madrid_vestibules.py`

```bash
python scripts/import_metro_madrid_vestibules.py
```

---

## Migraciones

| Migración | Tabla | Estado |
|-----------|-------|--------|
| 037_create_stop_access_table.py | stop_access | Nueva |
| 038_create_stop_vestibule_table.py | stop_vestibule | Nueva |

```bash
alembic upgrade head
```

---

## Modelos SQLAlchemy

```
src/gtfs_bc/stop/infrastructure/models/
├── stop_access_model.py      # NUEVO
├── stop_vestibule_model.py   # NUEVO
├── stop_platform_model.py    # Existente
└── __init__.py               # Actualizado
```

---

## Dependencias

```toml
# pyproject.toml
"pyproj>=3.6.0"  # Conversión UTM → WGS84
```

---

## Orden de Ejecución

```bash
# 1. Aplicar migraciones
alembic upgrade head

# 2. Importar shapes (reemplaza BRouter)
python scripts/import_metro_madrid_shapes.py

# 3. Importar andenes (reemplaza OSM)
python scripts/import_metro_madrid_platforms.py

# 4. Importar accesos (nuevos)
python scripts/import_metro_madrid_accesses.py

# 5. Importar vestíbulos (nuevos)
python scripts/import_metro_madrid_vestibules.py

# 6. Regenerar trips con tiempos reales (opcional)
python scripts/generate_metro_madrid_trips.py --use-crtm-times
```

---

## Verificación

```sql
-- Shapes
SELECT COUNT(*) FROM gtfs_shape_points WHERE shape_id LIKE 'METRO_MAD_%_CRTM';

-- Andenes
SELECT COUNT(*) FROM stop_platform WHERE stop_id LIKE 'METRO_%' AND source = 'crtm';

-- Accesos
SELECT COUNT(*) FROM stop_access WHERE stop_id LIKE 'METRO_%';

-- Vestíbulos
SELECT COUNT(*) FROM stop_vestibule WHERE stop_id LIKE 'METRO_%';
```

---

## Archivos Creados/Modificados

| Archivo | Acción |
|---------|--------|
| `scripts/import_metro_madrid_shapes.py` | Creado |
| `scripts/import_metro_madrid_platforms.py` | Creado |
| `scripts/import_metro_madrid_accesses.py` | Creado |
| `scripts/import_metro_madrid_vestibules.py` | Creado |
| `scripts/generate_metro_madrid_trips.py` | Modificado |
| `alembic/versions/037_create_stop_access_table.py` | Creado |
| `alembic/versions/038_create_stop_vestibule_table.py` | Creado |
| `src/gtfs_bc/stop/infrastructure/models/stop_access_model.py` | Creado |
| `src/gtfs_bc/stop/infrastructure/models/stop_vestibule_model.py` | Creado |
| `src/gtfs_bc/stop/infrastructure/models/__init__.py` | Modificado |
| `pyproject.toml` | Modificado (añadido pyproj) |
