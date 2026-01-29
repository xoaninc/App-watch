# Estado de Datos: Accesos y Vestíbulos por Operador

**Última actualización:** 2026-01-29

## Resumen

| Operador | Stops | Accesos | Vestíbulos | Andenes | Fuente Datos | Estado |
|----------|-------|---------|------------|---------|--------------|--------|
| Metro Madrid | 242 | 799 | 344 | 1,169 | CRTM ArcGIS | ✅ Completo |
| Metro Ligero | 56 | 27 | 16 | 162 | CRTM ArcGIS | ✅ Completo |
| Renfe Cercanías | 1,034 | 0 | 0 | 797 | - | ⏳ Pendiente |
| TMB Metro Barcelona | 3,461 | 0 | 0 | 199 | - | ⏳ Pendiente |
| Euskotren | 798 | 0 | 0 | 746 | - | ⏳ Pendiente |
| FGC | 302 | 0 | 0 | 413 | - | ⏳ Pendiente |
| Metro Bilbao | 191 | 0 | 0 | 55 | - | ⏳ Pendiente |
| Metro Valencia | 144 | 0 | 0 | 149 | - | ⏳ Pendiente |

---

## Operadores Completados

### 1. Metro de Madrid ✅

**Fuente:** CRTM ArcGIS Feature Service
- URL: `https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M4_Red/FeatureServer`
- Layers:
  - Layer 1: M4_Accesos (799 registros)
  - Layer 2: M4_Vestibulos (344 registros)
  - Layer 3: M4_Andenes (plataformas)

**Script:** `scripts/import_metro_madrid_crtm.py` (si existe) o datos importados manualmente

**Datos importados:**
- 799 accesos con coordenadas, horarios, accesibilidad
- 344 vestíbulos con tipo, torniquetes, horarios
- 1,169 andenes con líneas y coordenadas

**Fecha importación:** 2026-01-28

---

### 2. Metro Ligero Madrid ✅

**Fuente:** CRTM ArcGIS Feature Service
- URL: `https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/Red_MetroLigero/FeatureServer`
- Layers:
  - Layer 1: Accesos (27 registros)
  - Layer 2: Vestíbulos (16 registros)
  - Layer 3: Andenes (107 registros)
  - Layer 4: Tramos/Shapes (100 registros)

**Script:** `scripts/import_metro_ligero_crtm.py`

**Datos importados:**
- 27 accesos
- 16 vestíbulos
- 162 andenes (107 CRTM + existentes)
- 8 shapes con 4,342 puntos

**Notas:**
- Mapeo especial: CRTM código 10 → ML_24 (Colonia Jardín)
- ML4 (Parla) es línea circular

**Fecha importación:** 2026-01-29

---

## Operadores Pendientes (GTFS-RT)

### 3. TMB Metro Barcelona ✅

**Investigación realizada:** 2026-01-29

**Credenciales API TMB:**
- `TMB_APP_ID=ec080da7`
- `TMB_APP_KEY=3ab0315198cfcd290b487438d888b361`
- Aplicación: "WatchTrans"

**Fuente de datos: GTFS**
Los datos de accesos están en el GTFS, no en la API REST.

**URL GTFS:** `https://api.tmb.cat/v1/static/datasets/gtfs.zip?app_id=...&app_key=...`

**Datos disponibles en GTFS:**

| Archivo | Contenido |
|---------|-----------|
| `stops.txt` | 505 entradas (location_type=2) + 151 ascensores |
| `pathways.txt` | Conexiones entrada↔andén con tiempos (60s) |

**Formato stops.txt:**
```
stop_id,stop_code,stop_name,stop_lat,stop_lon,stop_url,location_type,parent_station,wheelchair_boarding
E.1011101,11101,"Ascensor - Residència sanitària",41.344324,2.106855,,2,P.6660111,1
E.11101,11101,"Residència sanitària",41.344357,2.106669,,2,P.6660111,2
```

**Convenciones:**
- `location_type=0`: Plataforma/andén
- `location_type=1`: Estación (parent)
- `location_type=2`: Entrada/Salida
- `E.10xxxxx`: Ascensor
- `E.xxxxx`: Entrada normal
- `wheelchair_boarding`: 1=accesible, 2=no accesible

**API REST disponible:**
- `/v1/transit/estacions` - 139 estaciones ✅
- `/v1/transit/parades` - 2731 paradas (bus+metro) ✅
- `/v1/imetro/estacions` - Tiempo real ✅
- `/v1/planner/plan` - Planificador rutas ✅

**Estado:** ✅ Datos disponibles en GTFS - Pendiente importar

---

### 4. FGC (Ferrocarrils de la Generalitat) ⏳

**Investigación:**
- [ ] Buscar Open Data Generalitat
- [ ] Verificar datos FGC

**Fuentes potenciales:**
- Dades Obertes Generalitat: https://analisi.transparenciacatalunya.cat/

**Estado:** Pendiente investigación

---

### 5. Euskotren ⏳

**Investigación:**
- [ ] Buscar Open Data Euskadi
- [ ] Verificar datos Euskotren

**Fuentes potenciales:**
- Open Data Euskadi: https://opendata.euskadi.eus/

**Estado:** Pendiente investigación

---

### 6. Metro Bilbao ⏳

**Investigación:**
- [ ] Buscar Open Data Euskadi/Bilbao
- [ ] Verificar datos Metro Bilbao

**Fuentes potenciales:**
- Open Data Euskadi: https://opendata.euskadi.eus/
- Metro Bilbao web

**Estado:** Pendiente investigación

---

### 7. Renfe Cercanías ⏳

**Investigación:**
- [ ] Buscar datos ADIF (infraestructura)
- [ ] Verificar NAP España

**Fuentes potenciales:**
- NAP España: https://nap.mitma.es/
- ADIF datos abiertos

**Estado:** Pendiente investigación

---

## Otros Operadores (Sin GTFS-RT)

### Metro Valencia (FGV)
- [ ] Investigar datos FGV/GVA

### Tranvía Zaragoza
- [ ] Investigar datos ayuntamiento

### Metro Granada/Málaga/Tenerife
- [ ] Investigar datos respectivos

---

## Notas Técnicas

### Estructura de tablas

```sql
-- stop_access (accesos/bocas de metro)
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

-- stop_vestibule (vestíbulos)
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

### Integración RAPTOR

Los accesos se cargan como puntos virtuales en el algoritmo RAPTOR:
- Se crean IDs virtuales: `ACCESS_{id}`
- Se generan transfers bidireccionales acceso ↔ plataforma
- Tiempo de caminata calculado por distancia (1.25 m/s = 4.5 km/h)

**Código:** `src/gtfs_bc/routing/gtfs_store.py` (paso 9)
