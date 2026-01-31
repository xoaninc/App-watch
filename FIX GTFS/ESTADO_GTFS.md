# Estado GTFS - Documento Principal

**Última actualización:** 2026-01-31

---

## Resumen de Operadores en Producción

| Operador | Trips | Stop Times | GTFS-RT | Estado |
|----------|-------|------------|---------|--------|
| Renfe Cercanías | 130,616 | 1,642,874 | ✅ JSON | ✅ |
| Metro Madrid | 26,470 | 494,810 | ❌ | ✅ |
| TMB Metro | 15,630 | 298,001 | ✅ API | ✅ |
| FGC | 15,495 | 165,548 | ✅ Protobuf | ✅ |
| Euskotren | 10,315 | 154,325 | ✅ Protobuf | ✅ |
| Metro Sevilla | 9,862 | 204,414 | ❌ | ✅ |
| Metro Granada | 5,693 | 143,098 | ❌ | ✅ |
| TRAM Barcelona | 3,195 | 56,789 | ❌ | ✅ |
| Metro Bilbao | 3,345 | 71,488 | ✅ Protobuf | ✅ |
| Metro Ligero Madrid | 3,001 | 38,983 | ❌ | ✅ |
| TRAM Alicante | ~2,214 | ~38,024 | ❌ | ✅ |
| Metro Málaga | 2,104 | 22,092 | ❌ | ✅ |
| Metro Tenerife | 1,168 | 17,238 | ❌ | ✅ |
| SFM Mallorca | 808 | 14,799 | ❌ | ✅ |
| Tranvía Zaragoza | ~720 | ~18,000 | ❌ | ✅ |
| Tranvía Murcia | ~200 | ~2,800 | ❌ | ✅ |
| Tranvía Sevilla | 958 | 6,649 | ❌ | ✅ |
| Metrovalencia | 10,348 | 181,995 | ❌ | ✅ |

---

## ✅ COMPLETADO: Metrovalencia (2026-01-31)

### Fuente de datos
- **NAP ID:** 967 (conjuntoDatoId) → **ficheroId: 1168**
- **Descargado:** 2026-01-31
- **Tamaño:** 1,065,751 bytes

### Comparativa GTFS NAP vs BD

| Elemento | GTFS NAP | BD Actual | Acción |
|----------|----------|-----------|--------|
| **Stops** | 144 | 144 | ✅ Iguales - No tocar |
| **Routes** | 189 | 114 | **+75 nuevas** - Importar |
| **Trips** | 10,348 | 0 | **Importar todo** |
| **Stop Times** | 181,995 | 0 | **Importar todo** |
| **Shapes** | 20 | 20 | **Importar** (reemplazar) |
| **Calendar** | 7 | 11 | Importar |

### Contenido del GTFS

| Archivo | Registros |
|---------|-----------|
| stops.txt | 144 |
| routes.txt | 189 |
| trips.txt | 10,348 |
| stop_times.txt | 181,995 |
| calendar.txt | 7 |
| calendar_dates.txt | 33 |
| shapes.txt | 900 puntos (20 shapes) |

### Trips por línea

| Línea | Trips |
|-------|-------|
| L1 | 915 |
| L2 | 903 |
| L3 | 858 |
| L4 | 1,973 |
| L5 | 898 |
| L6 | 1,012 |
| L7 | 832 |
| L8 | 619 |
| L9 | 766 |
| L10 | 1,572 |

### Rutas nuevas a importar (75)

Todas son variantes de L4, L6 y L8:
- **L4:** 50 variantes (V4-100-93, V4-102-115, V4-103-98, etc.)
- **L6:** 15 variantes (V6-123-130, V6-124-129, V6-131-125, etc.)
- **L8:** 10 variantes (V8-123-124, V8-124-125, V8-126-124, etc.)

### Calendario

**Problema:** El GTFS solo cubre 27 ene - 28 feb 2026 usando calendar_dates.txt día a día.

**Solución:** Convertir a calendario normal y extender a todo el año.

#### Servicios del GTFS → Conversión

| service_id | GTFS (días=0) | Convertir a | Usar en |
|------------|---------------|-------------|---------|
| 3091 | - | L=1,M=1,X=1,J=1 | Laborable L-J |
| 3093 | - | V=1 | Viernes |
| 3076 | - | S=1 | Sábado |
| 3078 | - | D=1 | Domingo/Festivo |

**Rango:** start_date=20260101, end_date=20261231

#### Festivos Valencia 2026 (usar servicio 3078 = Domingo)

**Nacionales:**
| Fecha | Festivo |
|-------|---------|
| 2026-01-01 | Año Nuevo |
| 2026-01-06 | Reyes |
| 2026-04-03 | Viernes Santo |
| 2026-05-01 | Día del Trabajo |
| 2026-08-15 | Asunción |
| 2026-10-12 | Fiesta Nacional |
| 2026-12-08 | Inmaculada |
| 2026-12-25 | Navidad |

**Autonómicos (Comunitat Valenciana):**
| Fecha | Festivo |
|-------|---------|
| 2026-04-06 | Lunes de Pascua |
| 2026-10-09 | Día de la Comunitat |

**Locales (Valencia ciudad):**
| Fecha | Festivo |
|-------|---------|
| 2026-01-22 | San Vicente Mártir |
| 2026-03-19 | San José (Fallas) |
| 2026-04-13 | San Vicente Ferrer |
| 2026-06-24 | San Juan |

**Total: 14 festivos** → Añadir a calendar_dates con service_id=3078, exception_type=1

### Mapeo de IDs

```
GTFS stop_id    → BD: METRO_VALENCIA_{stop_id}
GTFS route_id   → BD: METRO_VALENCIA_{route_id}
GTFS trip_id    → BD: METRO_VALENCIA_{trip_id}
GTFS service_id → BD: METRO_VALENCIA_{service_id}
GTFS shape_id   → BD: METRO_VALENCIA_{shape_id}
```

### Plan de importación

1. **Routes:** Insertar 75 nuevas (las 114 existentes ya están)
2. **Shapes:** Limpiar existentes e importar los 20 del GTFS
3. **Calendar:** Limpiar existentes y crear 4 servicios convertidos:
   - METRO_VALENCIA_3091 (L-J) → monday-thursday=1, resto=0
   - METRO_VALENCIA_3093 (V) → friday=1, resto=0
   - METRO_VALENCIA_3076 (S) → saturday=1, resto=0
   - METRO_VALENCIA_3078 (D/Festivo) → sunday=1, resto=0
   - Todos con start_date=20260101, end_date=20261231
4. **Calendar Dates:** Añadir 14 festivos Valencia 2026:
   - 01/01, 06/01, 22/01, 19/03, 03/04, 06/04, 13/04
   - 01/05, 24/06, 15/08, 09/10, 12/10, 08/12, 25/12
   - Todos con service_id=METRO_VALENCIA_3078, exception_type=1
5. **Trips:** Importar 10,348 trips (solo los que usan servicios 3091, 3093, 3076, 3078)
6. **Stop Times:** Importar 181,995 stop_times

### Progreso

- [x] Descargar GTFS (NAP) - ficheroId 1168
- [x] Analizar contenido
- [x] Comparar con BD
- [x] Crear script de importación (`import_metrovalencia_gtfs.py`)
- [x] Ejecutar en producción (2026-01-31)
- [x] Verificar API ✅
- [x] Verificar RAPTOR ✅

### Verificación RAPTOR (2026-01-31)

**IMPORTANTE:** Después de importar, reiniciar el servicio para que RAPTOR cargue los nuevos datos:
```bash
ssh root@juanmacias.com "systemctl restart renfeserver"
```

#### Pruebas realizadas

| Test | Ruta | Resultado |
|------|------|-----------|
| Directo | Alameda → Aeroport (L3) | ✅ 24 min |
| Directo | Aeroport → Marítim (L5) | ✅ 30 min |
| Transbordo | València Sud → Rafelbunyol (L2+L3) | ✅ 61 min, 1 transbordo |
| Intermodal | Alameda → RENFE Valencia Norte | ✅ 9 min (L9 + walking) |
| Complejo | Aeroport → RENFE Valencia Norte | ✅ 31 min (L3 + walking) |

#### Correspondencias activas

| Metro | Renfe | Tiempo | Distancia |
|-------|-------|--------|-----------|
| METRO_VALENCIA_71 (Xàtiva) | RENFE_65000 (València Nord) | 25s | 31m |
| METRO_VALENCIA_25 (Àngel Guimerà) | RENFE_65000 (València Nord) | 360s | 300m |

#### Comandos de prueba

```bash
# Ruta directa
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_VALENCIA_69&to=METRO_VALENCIA_182&departure_time=06:00"

# Ruta con transbordo
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_VALENCIA_20&to=METRO_VALENCIA_64&departure_time=09:00"

# Ruta intermodal (Metro → Renfe)
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_VALENCIA_182&to=RENFE_65000&departure_time=08:00"
```

---

## URLs de GTFS

### Descarga Directa (automático)

| Operador | URL |
|----------|-----|
| Renfe Cercanías | `https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip` |
| Metro Bilbao | `https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfs_metro_bilbao.zip` |
| Euskotren | `https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfs_euskotren.zip` |
| FGC | `https://www.fgc.cat/google/google_transit.zip` |
| TMB Metro | `https://api.tmb.cat/v1/static/datasets/gtfs.zip?app_id=XXX&app_key=XXX` |
| TRAM Barcelona | `https://www.tram.cat/documents/20124/260748/google_transit_tram.zip` |
| Metro Madrid | `https://crtm.maps.arcgis.com/sharing/rest/content/items/5c7f2951962540d69ffe8f640d94c246/data` |
| Metro Ligero | `https://crtm.maps.arcgis.com/sharing/rest/content/items/aaed26cc0ff64b0c947ac0bc3e033196/data` |
| Metro Tenerife | `https://metrotenerife.com/transit/google_transit.zip` |
| Metrovalencia | `https://www.metrovalencia.es/google_transit_feed/google_transit.zip` |

### NAP (API)

Portal: https://nap.transportes.gob.es
Documentación API: https://nap.transportes.gob.es/Account/InstruccionesAPI
API Key: Ver `.env.local` en el proyecto

#### Instrucciones de uso de la API

**Header de autenticación:** `ApiKey` (con A y K mayúsculas)

**Endpoints:**
- Info dataset: `GET /api/Fichero/{conjuntoDatoId}`
- Descargar: `GET /api/Fichero/download/{ficheroId}`
- Link descarga: `GET /api/Fichero/downloadLink/{ficheroId}`

**IMPORTANTE:** `conjuntoDatoId` != `ficheroId`
- `conjuntoDatoId` es el ID del dataset (tabla abajo)
- `ficheroId` es el ID del archivo GTFS dentro del dataset
- Primero llamar a `/api/Fichero/{conjuntoDatoId}` para obtener el `ficheroId`

**Ejemplo:**
```bash
# 1. Obtener info del dataset (devuelve ficheroId)
curl -s "https://nap.transportes.gob.es/api/Fichero/967" \
    -H "ApiKey: $NAP_API_KEY"

# 2. Descargar usando ficheroId obtenido
curl -s "https://nap.transportes.gob.es/api/Fichero/download/{ficheroId}" \
    -H "ApiKey: $NAP_API_KEY" \
    -o gtfs.zip
```

| Operador | conjuntoDatoId |
|----------|----------------|
| TRAM Alicante | 966 |
| Metrovalencia | 967 |
| SFM Mallorca | 1272 |
| Metro Málaga | 1296 |
| Metro Granada | 1370 |
| Tranvía Murcia | 1371 |
| Metro Sevilla | 1385 |
| Tranvía Zaragoza | 1394 |
| Metro Tenerife | 1395 |
| TUSSAM | 1567 |

---

## Scripts de Importación

| Operador | Script |
|----------|--------|
| Metro Madrid | `generate_metro_madrid_from_gtfs.py` |
| Metro Tenerife | `import_metro_tenerife_gtfs.py` |
| Metro Sevilla | `import_metro_sevilla_gtfs.py` |
| Metro Granada | `import_metro_granada_gtfs.py` |
| Metro Málaga | `import_metro_malaga_gtfs.py` |
| Tranvía Zaragoza | `import_tranvia_zaragoza_frequencies.py` |
| Tranvía Murcia | `import_tranvia_murcia_gtfs.py` |
| TRAM Alicante | `import_tram_alicante_gtfs.py` |
| SFM Mallorca | `import_sfm_mallorca_gtfs.py` |
| Metrovalencia | `import_metrovalencia_gtfs.py` |

---

## GTFS-RT (Tiempo Real)

| Operador | Formato | Vehicle Positions | Trip Updates | Alerts |
|----------|---------|-------------------|--------------|--------|
| Renfe | JSON | `gtfsrt.renfe.com/vehicle_positions.json` | `trip_updates.json` | `alerts.json` |
| Metro Bilbao | Protobuf | `opendata.euskadi.eus/.../gtfsrt_metro_bilbao_vehicle_positions.pb` | `_trip_updates.pb` | `_alerts.pb` |
| Euskotren | Protobuf | `opendata.euskadi.eus/.../gtfsrt_euskotren_vehicle_positions.pb` | `_trip_updates.pb` | `_alerts.pb` |
| FGC | Protobuf | `dadesobertes.fgc.cat/api/...` | `...` | `...` |
| TMB Metro | API JSON | `api.tmb.cat/v1/imetro/estacions` | - | - |

---

# MODELO BASE: Cómo Importar un Nuevo Operador

## Notas Técnicas Importantes

### Estructura de la BD (gtfs_routes)

```sql
-- Columnas de gtfs_routes (verificar antes de crear script)
id, agency_id, short_name, long_name, route_type, color, text_color,
description, url, sort_order, renfe_idlinea, geometry, network_id, is_circular
```

**IMPORTANTE:** La columna es `route_type`, NO `type`.

### Verificar IDs existentes antes de importar

Antes de crear el script, verificar qué `agency_id` y `network_id` usa el operador:

```sql
-- Ver agency_id existente
SELECT DISTINCT agency_id FROM gtfs_routes WHERE id LIKE '{PREFIJO}%';

-- Ver network_id existente
SELECT DISTINCT network_id FROM gtfs_routes WHERE id LIKE '{PREFIJO}%';

-- Ver agencies disponibles
SELECT id FROM gtfs_agencies WHERE id LIKE '%{OPERADOR}%';
```

**Ejemplo Metrovalencia:**
- `agency_id`: `METRO_VALENCIA_1` (no `METRO_VALENCIA`)
- `network_id`: `40T` (no `METROVALENCIA`)

### Deploy a producción

```bash
# 1. Subir script
rsync -avz scripts/import_{operador}_gtfs.py root@juanmacias.com:/var/www/renfeserver/scripts/

# 2. Subir GTFS
rsync -avz /tmp/gtfs_{operador}/ root@juanmacias.com:/tmp/gtfs_{operador}/

# 3. Ejecutar
ssh root@juanmacias.com "cd /var/www/renfeserver && source .venv/bin/activate && python scripts/import_{operador}_gtfs.py"

# 4. Verificar API
curl "https://juanmacias.com/api/v1/gtfs/stops/{STOP_ID}/departures?limit=5"
```

---

## Fase 1: Investigación

### 1.1 Buscar fuentes de datos

```bash
# Buscar en:
# 1. Web oficial del operador → sección "Datos abiertos" o "Desarrolladores"
# 2. NAP: https://nap.transportes.gob.es → buscar por nombre
# 3. Google: "{operador} GTFS"
# 4. Transitland: https://www.transit.land/feeds
# 5. Mobility Database: https://database.mobilitydata.org
```

### 1.2 Descargar y analizar GTFS

```bash
# OPCIÓN A: URL directa
curl -sL "{URL_GTFS}" -o /tmp/gtfs_operador.zip

# OPCIÓN B: Desde NAP (requiere API Key)
# 1. Primero obtener ficheroId del dataset
curl -s "https://nap.transportes.gob.es/api/Fichero/{conjuntoDatoId}" \
    -H "ApiKey: $NAP_API_KEY" | jq '.ficheroId'

# 2. Descargar usando ficheroId
curl -s "https://nap.transportes.gob.es/api/Fichero/download/{ficheroId}" \
    -H "ApiKey: $NAP_API_KEY" \
    -o /tmp/gtfs_operador.zip

# Descomprimir
unzip -o /tmp/gtfs_operador.zip -d /tmp/gtfs_operador

# Analizar contenido
cd /tmp/gtfs_operador
wc -l *.txt                    # Contar líneas
head -5 stops.txt              # Ver estructura paradas
head -5 routes.txt             # Ver rutas
head -5 trips.txt              # Ver trips
head -5 stop_times.txt         # Ver horarios
cat calendar.txt               # Ver servicios
cat frequencies.txt 2>/dev/null # Ver si usa frequencies
```

### 1.3 Verificar qué existe en BD

```sql
-- Paradas
SELECT COUNT(*) FROM gtfs_stops WHERE id LIKE '{PREFIJO}%';

-- Rutas
SELECT COUNT(*) FROM gtfs_routes WHERE id LIKE '{PREFIJO}%';

-- Trips
SELECT COUNT(*) FROM gtfs_trips WHERE route_id LIKE '{PREFIJO}%';

-- Stop times
SELECT COUNT(*) FROM gtfs_stop_times st
JOIN gtfs_trips t ON st.trip_id = t.id
WHERE t.route_id LIKE '{PREFIJO}%';

-- Shapes
SELECT COUNT(DISTINCT shape_id) FROM gtfs_shape_points
WHERE shape_id LIKE '{PREFIJO}%';
```

---

## Fase 2: Documentar

### 2.1 Información básica

| Campo | Valor |
|-------|-------|
| Operador | {nombre} |
| Prefijo BD | {PREFIJO_} |
| URL GTFS | {url} |
| NAP ID | {id o N/A} |
| Líneas | {lista} |
| Paradas | {número} |

### 2.2 Contenido del GTFS

| Archivo | Registros | Notas |
|---------|-----------|-------|
| stops.txt | X | |
| routes.txt | X | |
| trips.txt | X | ¿Base o expandidos? |
| stop_times.txt | X | |
| calendar.txt | X | |
| calendar_dates.txt | X | |
| frequencies.txt | X | ¿Necesita expansión? |
| shapes.txt | X | |
| transfers.txt | X | |

### 2.3 Tipos de servicio

| service_id | Días | Horario |
|------------|------|---------|
| LABORABLE | L-J | 06:00-23:00 |
| VIERNES | V | 06:00-02:00 |
| SABADO | S | 07:00-02:00 |
| DOMINGO | D | 07:00-23:00 |
| FESTIVO | Festivos | 07:00-23:00 |

### 2.4 Festivos a configurar

**Nacionales:**
- 01/01: Año Nuevo
- 06/01: Reyes
- Jueves Santo (variable)
- Viernes Santo (variable)
- 01/05: Día del Trabajo
- 15/08: Asunción
- 12/10: Fiesta Nacional
- 01/11: Todos los Santos
- 06/12: Constitución
- 08/12: Inmaculada
- 25/12: Navidad

**Autonómicos:** (según comunidad)

**Locales:** (según ciudad)

### 2.5 Vísperas de festivo

Si el operador tiene servicio nocturno en vísperas:
- Identificar qué días aplica
- Configurar exception_type en calendar_dates

---

## Fase 3: Mapeo de IDs

### 3.1 Paradas

```
GTFS stop_id → BD stop_id
{id_gtfs} → {PREFIJO}_{id_gtfs}
```

### 3.2 Rutas

```
GTFS route_id → BD route_id
{id_gtfs} → {PREFIJO}_{id_gtfs}
```

### 3.3 Servicios

```
GTFS service_id → BD service_id
{id_gtfs} → {PREFIJO}_{id_gtfs}
```

### 3.4 Shapes

```
GTFS shape_id → BD shape_id
{id_gtfs} → {PREFIJO}_{linea}_{direccion}
```

---

## Fase 4: Script de Importación

### 4.1 Estructura del script

```python
#!/usr/bin/env python3
"""Import {OPERADOR} GTFS data."""

import os
import sys
import csv
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# IMPORTANTE: Verificar estos valores con la BD antes de ejecutar
PREFIX = '{PREFIJO}_'           # Ej: 'METRO_VALENCIA_'
AGENCY_ID = '{AGENCY_ID}'       # Verificar con: SELECT DISTINCT agency_id FROM gtfs_routes WHERE id LIKE '{PREFIJO}%'
NETWORK_ID = '{NETWORK_ID}'     # Verificar con: SELECT DISTINCT network_id FROM gtfs_routes WHERE id LIKE '{PREFIJO}%'
GTFS_DIR = '/tmp/gtfs_{operador}'

def import_routes(db, dry_run: bool):
    """Importar rutas nuevas."""
    # NOTA: Columna es route_type, NO type
    db.execute(text('''
        INSERT INTO gtfs_routes (id, agency_id, short_name, long_name, route_type, color, text_color, network_id)
        VALUES (:id, :agency_id, :short_name, :long_name, :route_type, :color, :text_color, :network_id)
        ON CONFLICT (id) DO NOTHING
    '''), {...})

def main():
    db = SessionLocal()
    try:
        # 1. Importar rutas nuevas (si hay)
        import_routes(db, dry_run)

        # 2. Crear calendarios
        create_calendars(db, dry_run)

        # 3. Añadir festivos
        create_calendar_dates(db, dry_run)

        # 4. Importar shapes
        import_shapes(db, dry_run)

        # 5. Importar trips
        import_trips(db, dry_run)

        # 6. Importar stop_times
        import_stop_times(db, dry_run)

        if not dry_run:
            db.commit()
            verify_import(db)
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
```

### 4.2 Decisiones clave

| Pregunta | Opciones |
|----------|----------|
| ¿El GTFS usa frequencies.txt? | Sí → Expandir a trips individuales |
| ¿Los shapes del GTFS son buenos? | No → Usar OSM o mantener BD |
| ¿Hay stop_times completos? | Sí → Importar directo / No → Generar desde frequencies |
| ¿Hay calendario completo? | Sí → Importar / No → Crear manualmente |
| ¿Hay festivos en calendar_dates? | Sí → Importar / No → Añadir manualmente |
| ¿El calendario usa días=0 + calendar_dates? | Sí → Convertir a calendario normal con días=1 |
| ¿Hay que añadir rutas nuevas? | Verificar agency_id y network_id existentes |

---

## Fase 5: Verificación

### 5.1 SQL

```sql
-- Calendarios
SELECT * FROM gtfs_calendar WHERE service_id LIKE '{PREFIJO}%';

-- Trips por servicio
SELECT service_id, COUNT(*) FROM gtfs_trips
WHERE route_id LIKE '{PREFIJO}%'
GROUP BY service_id;

-- Stop times
SELECT COUNT(*) FROM gtfs_stop_times
WHERE trip_id LIKE '{PREFIJO}%';

-- Shapes
SELECT shape_id, COUNT(*) FROM gtfs_shape_points
WHERE shape_id LIKE '{PREFIJO}%'
GROUP BY shape_id;
```

### 5.2 API

```bash
# Próximas salidas
curl "https://juanmacias.com/api/v1/gtfs/stops/{STOP_ID}/departures?limit=5"

# Routing
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from={STOP_A}&to={STOP_B}&departure_time=08:00"
```

### 5.3 Comparar con web oficial

- Verificar frecuencias coinciden
- Verificar primer/último tren
- Verificar paradas

### 5.4 Verificar RAPTOR

**IMPORTANTE:** Reiniciar servicio después de importar para que RAPTOR cargue los datos:
```bash
ssh root@juanmacias.com "systemctl restart renfeserver"
```

**Pruebas a realizar:**

```bash
# 1. Ruta directa (misma línea)
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from={STOP_A}&to={STOP_B}&departure_time=09:00"

# 2. Ruta con transbordo (diferentes líneas del mismo operador)
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from={STOP_LINEA1}&to={STOP_LINEA2}&departure_time=09:00"

# 3. Ruta intermodal (si hay correspondencias con Renfe u otro operador)
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from={STOP_METRO}&to=RENFE_{STOP}&departure_time=09:00"
```

**Verificar que devuelve:**
- `success: true`
- `journeys` con segmentos válidos
- Tiempos coherentes
- Transbordos correctos

**Si no encuentra ruta:**
1. Verificar que el servicio está activo para el día/hora de la consulta
2. Verificar que hay trips para ese servicio
3. Verificar calendarios (start_date, end_date, días de la semana)
4. Reiniciar el servicio si se importaron datos nuevos

---

## Fase 6: Checklist

- [ ] Descargar GTFS (URL directa o NAP)
- [ ] Analizar contenido (wc -l, head)
- [ ] Verificar estado BD (stops, routes, trips existentes)
- [ ] **Verificar agency_id y network_id existentes**
- [ ] Documentar mapeo IDs
- [ ] Identificar festivos locales (buscar en web)
- [ ] Crear script importación
- [ ] Test --dry-run
- [ ] **rsync script y GTFS al servidor**
- [ ] Ejecutar importación en producción
- [ ] **Reiniciar servicio** (`systemctl restart renfeserver`)
- [ ] Verificar SQL
- [ ] Verificar API (curl departures)
- [ ] **Verificar RAPTOR** (route-planner con rutas directas, transbordos e intermodales)
- [ ] Comparar con web oficial
- [ ] Actualizar documentación

---

# Archivos de Referencia

Los planes detallados de importaciones anteriores están en `archive/`:

| Archivo | Operador | Contenido |
|---------|----------|-----------|
| `PLAN_METRO_MALAGA_IMPORT.md` | Málaga | 5 servicios, vísperas, festivos Andalucía |
| `PLAN_METRO_SEVILLA_IMPORT.md` | Sevilla | Temporadas, Semana Santa, Feria |
| `PLAN_METRO_TENERIFE_IMPORT.md` | Tenerife | Frequencies expansion, festivos Canarias |
| `CRTM_METRO_MADRID_DATA.md` | Madrid | API CRTM, shapes, andenes |
| `TRAM_SEVILLA_SHAPES.md` | Tram Sevilla | Shapes desde OSM |
| `TODO_PENDIENTE.md` | General | Histórico de tareas |
| `GTFS_OPERATORS_STATUS.md` | General | Estado anterior |

---

# Verificación Rápida en Producción

```bash
ssh root@juanmacias.com "cd /var/www/renfeserver && source .venv/bin/activate && python3 -c \"
from sqlalchemy import create_engine, text
engine = create_engine('postgresql://renfeserver:renfeserver@localhost:5432/renfeserver_prod')
with engine.connect() as conn:
    r = conn.execute(text('''
        SELECT
            CASE
                WHEN route_id LIKE 'RENFE_%' THEN 'Renfe'
                WHEN route_id LIKE 'METRO_BILBAO%' THEN 'Metro Bilbao'
                WHEN route_id LIKE 'METRO_VAL%' THEN 'Metrovalencia'
                WHEN route_id LIKE 'METRO_MALAGA%' THEN 'Metro Málaga'
                WHEN route_id LIKE 'METRO_TENERIFE%' THEN 'Metro Tenerife'
                WHEN route_id LIKE 'METRO_GRANADA%' THEN 'Metro Granada'
                WHEN route_id LIKE 'METRO_SEV%' THEN 'Metro Sevilla'
                WHEN route_id LIKE 'METRO_%' THEN 'Metro Madrid'
                WHEN route_id LIKE 'ML_%' THEN 'Metro Ligero'
                WHEN route_id LIKE 'EUSKOTREN%' THEN 'Euskotren'
                WHEN route_id LIKE 'FGC%' THEN 'FGC'
                WHEN route_id LIKE 'TMB_METRO%' THEN 'TMB Metro'
                WHEN route_id LIKE 'TRAM_BARCELONA%' THEN 'TRAM Barcelona'
                WHEN route_id LIKE 'TRAM_ALICANTE%' THEN 'TRAM Alicante'
                WHEN route_id LIKE 'TRANVIA_MURCIA%' THEN 'Tranvía Murcia'
                WHEN route_id LIKE 'TRANVIA_ZARAGOZA%' THEN 'Tranvía Zaragoza'
                WHEN route_id LIKE 'SFM_MALLORCA%' THEN 'SFM Mallorca'
                ELSE 'Otro'
            END as operador,
            COUNT(*) as trips
        FROM gtfs_trips
        GROUP BY operador
        ORDER BY trips DESC
    '''))
    for row in r:
        print(f'{row[0]}: {row[1]:,} trips')
\""
```
