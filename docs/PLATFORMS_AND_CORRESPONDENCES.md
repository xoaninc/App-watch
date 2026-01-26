# Plataformas y Correspondencias - Documentación Completa

**Última actualización:** 2026-01-26

---

## 1. Resumen Ejecutivo

Este documento describe el sistema de plataformas y correspondencias implementado para gestionar:
1. **Coordenadas de andenes** por línea en cada estación
2. **Conexiones a pie** entre estaciones diferentes

---

## 2. Modelo de Datos

### 2.1 Tabla `stop_platform`

Almacena las coordenadas específicas de cada andén/línea en una estación.

```sql
CREATE TABLE stop_platform (
    id SERIAL PRIMARY KEY,
    stop_id VARCHAR(100) NOT NULL,      -- Referencia a gtfs_stops
    lines VARCHAR(255) NOT NULL,         -- "L6" o "C2, C3, C4a, C4b"
    lat FLOAT NOT NULL,
    lon FLOAT NOT NULL,
    source VARCHAR(50),                  -- 'gtfs', 'osm', 'manual'
    UNIQUE(stop_id, lines)
);
```

**Ejemplo:**
| stop_id | lines | lat | lon | source |
|---------|-------|-----|-----|--------|
| METRO_120 | L6 | 40.446620 | -3.692410 | osm |
| METRO_120 | L8 | 40.446550 | -3.692410 | osm |
| METRO_120 | L10 | 40.446590 | -3.692410 | osm |
| RENFE_17001 | C2, C3, C4a, C4b, C7, C8a, C8b, C10 | 40.446627 | -3.692347 | gtfs |

### 2.2 Tabla `stop_correspondence`

Almacena conexiones a pie entre estaciones DIFERENTES.

```sql
CREATE TABLE stop_correspondence (
    id SERIAL PRIMARY KEY,
    from_stop_id VARCHAR(100) NOT NULL,
    to_stop_id VARCHAR(100) NOT NULL,
    distance_m INTEGER,                  -- Distancia en metros
    walk_time_s INTEGER,                 -- Tiempo caminando en segundos
    source VARCHAR(50),                  -- 'manual', 'osm', 'proximity'
    UNIQUE(from_stop_id, to_stop_id)
);
```

**Ejemplo:**
| from_stop_id | to_stop_id | distance_m | walk_time_s | source |
|--------------|------------|------------|-------------|--------|
| METRO_92 | METRO_46 | 200 | 180 | manual |
| METRO_46 | METRO_92 | 200 | 180 | manual |

**Nota:** Las correspondencias son bidireccionales (se insertan ambas direcciones).

### 2.3 Diferencia Conceptual

| Concepto | Tabla | Ejemplo |
|----------|-------|---------|
| Misma estación, múltiples líneas | `stop_platform` | Cuatro Caminos: L1, L2, L6 |
| Estaciones diferentes conectadas | `stop_correspondence` | Acacias (L5) ↔ Embajadores (L3) |

---

## 3. APIs Disponibles

### 3.1 GET /stops/{stop_id}/platforms

Devuelve las coordenadas de cada andén/línea en una estación.

**Request:**
```
GET /api/v1/gtfs/stops/METRO_120/platforms
```

**Response:**
```json
{
  "stop_id": "METRO_120",
  "stop_name": "Nuevos Ministerios",
  "platforms": [
    {
      "id": 174,
      "stop_id": "METRO_120",
      "lines": "L10",
      "lat": 40.4452235,
      "lon": -3.6913658,
      "source": "osm"
    },
    {
      "id": 175,
      "stop_id": "METRO_120",
      "lines": "L8",
      "lat": 40.4454795,
      "lon": -3.6915608,
      "source": "osm"
    }
  ]
}
```

**Casos de uso:**
- Mostrar posiciones exactas de andenes en el mapa
- Calcular rutas dentro de una estación
- Indicar al usuario a qué andén dirigirse

### 3.2 GET /stops/{stop_id}/correspondences

Devuelve las conexiones a pie a otras estaciones cercanas.

**Request:**
```
GET /api/v1/gtfs/stops/METRO_92/correspondences
```

**Response:**
```json
{
  "stop_id": "METRO_92",
  "stop_name": "Acacias",
  "correspondences": [
    {
      "id": 1,
      "to_stop_id": "METRO_46",
      "to_stop_name": "Embajadores",
      "to_lines": "L3, L5, C5",
      "distance_m": 200,
      "walk_time_s": 180,
      "source": "manual"
    }
  ]
}
```

**Casos de uso:**
- Mostrar al usuario opciones de transbordo caminando
- Calcular rutas multimodales
- Indicar tiempo de caminata entre estaciones

### 3.3 GET /routes/{route_id}/shape

Devuelve los puntos del trayecto de una ruta para dibujar en el mapa.

**Request:**
```
GET /api/v1/gtfs/routes/RENFE_C3/shape
```

**Response:**
```json
{
  "route_id": "RENFE_C3",
  "route_short_name": "C3",
  "shape": [
    {"lat": 40.4527, "lon": -3.6876, "sequence": 1},
    {"lat": 40.4530, "lon": -3.6880, "sequence": 2},
    ...
  ]
}
```

**Notas:**
- Los shapes provienen de la tabla `gtfs_shape_points`
- Solo las rutas con shapes en GTFS devuelven datos (principalmente Cercanías)
- Metros de frecuencia (TMB, FGC) no tienen shapes GTFS
- Se podría añadir fallback a OSM para rutas sin shapes

---

## 4. Fuentes de Datos

### 4.1 GTFS (stops.txt)

- **Qué proporciona:** Una coordenada por estación
- **Limitación:** No distingue entre andenes de diferentes líneas
- **Uso:** Fallback cuando no hay datos OSM

### 4.2 OpenStreetMap (OSM)

- **Tag `public_transport=stop_area_group`:** Agrupa estaciones que forman un intercambiador
- **Tag `public_transport=stop_area`:** Define una estación con sus andenes
- **Tag `railway=platform`:** Andén físico con coordenadas exactas

**Consulta Overpass para obtener grupos:**
```
[out:json][timeout:120];
(
  relation["public_transport"="stop_area_group"];
);
out body geom;
```

### 4.3 Proximidad (<300m)

Estaciones de diferentes redes que están cerca se conectan automáticamente:
- Metro ↔ Cercanías
- Metro ↔ Metro Ligero
- Etc.

### 4.4 Manual

Correspondencias verificadas manualmente que no están en OSM.

---

## 5. Estado Actual de Datos

### 5.1 Plataformas por Red

| Red | Plataformas | Paradas | Fuente | Estado |
|-----|-------------|---------|--------|--------|
| Renfe Cercanías | 797 | 791 | GTFS | ✅ Completo |
| Euskotren | 746 | 740 | GTFS | ✅ Completo (incluye Vitoria) |
| Metro Madrid | 281 | 233 | OSM | ✅ Coords por línea |
| TMB Metro BCN | 173 | 145 | OSM | ✅ Coords por línea |
| TRAM Barcelona | 172 | 172 | GTFS | ✅ Completo |
| Metro Valencia | 219 | 144 | OSM+GTFS | ✅ Coords por línea |
| Metro Ligero Madrid | 56 | 56 | GTFS | ✅ Completo |
| Metro Bilbao | 55 | 42 | OSM | ✅ Coords por línea |
| FGC | 54 | 34 | OSM | ✅ Coords por línea |
| Tranvía Zaragoza | 29 | 32 | OSM | ✅ Coords por estación |
| Metro Granada | 38 | 26 | OSM | ✅ Coords por línea |
| Metro Málaga | 44 | 25 | OSM | ✅ Coords por línea |
| Metro Sevilla | 34 | 21 | OSM | ✅ Coords por línea |
| Tranvía Sevilla | 7 | 7 | GTFS | ✅ Completo |
| **TOTAL** | **~2700** | **~2500** | | |

### 5.2 Correspondencias por Ciudad

| Ciudad | Pares | Fuente | Ejemplos |
|--------|-------|--------|----------|
| Barcelona | 25 | OSM | Catalunya, Passeig de Gràcia, Sants |
| Madrid Metro | 17 | proximity+manual | Atocha, Nuevos Ministerios, Sol |
| Cercanías | 20 | proximity+OSM | Metro↔Cercanías en intercambiadores |
| Sevilla | 6 | manual | San Bernardo, Nervión↔Eduardo Dato, Prado, Puerta Jerez |
| Bilbao | 5 | manual | Abando, San Mamés, Casco Viejo |
| Zaragoza | 9 | OSM | Delicias, Plaza Aragón |
| Valencia | 1 | OSM | Sant Isidre |
| Málaga | 5 | manual | El Perchel↔María Zambrano, El Perchel L1↔L2, Guadalmedina L1↔L2 |
| Metro Ligero | 3 | proximity | Colonia Jardín, Pinar de Chamartín |
| **TOTAL** | **91** | | |

### 5.3 stop_area_group Conocidos en OSM

#### Madrid (13 grupos)
| ID | Nombre | Tipo |
|----|--------|------|
| 7849782 | Plaza de España - Noviciado | Correspondencia |
| 7849788 | Moncloa | Misma estación |
| 7849793 | Cuatro Caminos | Misma estación |
| 7849798 | Bilbao | Misma estación |
| 7718408 | Avenida de América | Misma estación |
| 7718417 | Sol | Correspondencia |
| 7718418 | Atocha | Correspondencia |
| 7894618 | Plaza de Castilla | Misma estación |
| 7894621 | Plaza Elíptica | Correspondencia |
| 10077012 | Aeropuerto T4 | Misma estación |
| 10077017 | Paco de Lucía | Correspondencia |
| 10077046 | Vicálvaro - Puerta de Arganda | Correspondencia |
| 10077099 | Sierra Guadalupe - Vallecas | Correspondencia |

#### Barcelona (24 grupos)
| ID | Nombre | Tipo |
|----|--------|------|
| 4125372 | Catalunya | Correspondencia |
| 5720834 | Espanya | Correspondencia (TMB↔FGC) |
| 6648219 | El Clot | Correspondencia |
| 7646482 | Sagrada Família | Misma estación |
| 7646492 | Passeig de Gràcia | Correspondencia |
| 7646696 | Sants Estació | Correspondencia |
| 7781537 | Plaça d'Espanya | Misma estación |
| 7782168 | Aeroport T2 | Correspondencia |
| 7782174 | Provença/Diagonal | Correspondencia |
| 7782177 | Universitat | Misma estación |
| 7857590 | Urquinaona | Misma estación |
| 7873703 | Trinitat Nova | Misma estación |
| ... | (14 más) | |

#### Otras Ciudades
| Ciudad | ID | Nombre |
|--------|-----|--------|
| Bilbao | 12227411 | Abando (Metro↔Euskotren↔Cercanías) |
| Valencia | 11789701 | Sant Isidre |
| Zaragoza | 6204978 | Delicias |
| Zaragoza | 18082571 | Plaza Aragón |
| Granada | 20127125 | Estación de Ferrocarril |

---

## 6. Scripts de Importación

### 6.1 import_stop_platforms.py

Importa coordenadas de plataformas desde archivos CSV extraídos de OSM.

```bash
.venv/bin/python scripts/import_stop_platforms.py
```

**Archivos fuente:**
- `docs/osm_coords/metro_madrid_by_line.csv`
- `docs/osm_coords/metro_bcn_by_line.csv`
- `docs/osm_coords/metro_bilbao_by_line.csv`

### 6.2 import_osm_correspondences.py

Importa correspondencias desde OSM `stop_area_group`.

```bash
# Una ciudad
.venv/bin/python scripts/import_osm_correspondences.py --city madrid

# Todas las ciudades
.venv/bin/python scripts/import_osm_correspondences.py --all

# Ver qué haría sin ejecutar
.venv/bin/python scripts/import_osm_correspondences.py --city madrid --dry-run

# Un grupo específico por ID
.venv/bin/python scripts/import_osm_correspondences.py --group-id 7849782
```

**Flujo del script:**
1. Consulta Overpass API por `stop_area_group`
2. Para cada grupo, obtiene sus miembros (`stop_area`)
3. Clasifica: misma estación vs estaciones diferentes
4. Busca las estaciones en nuestra BD
5. Inserta en `stop_platform` y/o `stop_correspondence`

---

## 7. Migraciones

| Migración | Descripción |
|-----------|-------------|
| 029 | Crea tabla `stop_platform`, elimina `line_transfer` |
| 030 | Renombra `line` a `lines` en `stop_platform` |
| 031 | Crea tabla `stop_correspondence` |

---

## 8. Mapeo de Redes OSM → Base de Datos

| OSM network | Prefijo BD | Tipo |
|-------------|------------|------|
| Metro de Madrid | METRO_ | metro |
| Metro de Barcelona | TMB_METRO_ | metro |
| FGC | FGC_ | fgc |
| Cercanías Madrid | RENFE_ | cercanias |
| Rodalies Barcelona | RENFE_ | cercanias |
| Metro Bilbao | METRO_BILBAO_ | metro |
| Euskotren | EUSKOTREN_ | euskotren |
| TRAM Barcelona | TRAM_BARCELONA_ | tranvia |
| Metrovalencia | METRO_VALENCIA_ | metro |
| Metro de Sevilla | METRO_SEV_ | metro |
| Metro de Málaga | METRO_MALAGA_ | metro |
| Metro de Granada | METRO_GRANADA_ | metro |
| Tranvía Sevilla | TRAM_SEV_ | tranvia |

---

## 9. Correspondencias Manuales Añadidas

Estas no están en OSM y se añadieron manualmente:

### Madrid
| Desde | Hasta | Distancia |
|-------|-------|-----------|
| METRO_92 (Acacias L5) | METRO_46 (Embajadores L3) | 200m |
| METRO_38 (Noviciado L2) | METRO_50 (Plaza España L3/L10) | 250m |
| METRO_46 (Embajadores) | RENFE_35609 (Embajadores C5) | 100m |

### Sevilla (Metro ↔ Tranvía ↔ Cercanías)
| Desde | Hasta | Distancia |
|-------|-------|-----------|
| METRO_SEV_L1_E10 (San Bernardo Metro) | RENFE_51100 (San Bernardo Cercanías) | 87m |
| METRO_SEV_L1_E10 (San Bernardo Metro) | TRAM_SEV_SAN_BERNARDO (San Bernardo Tranvía) | 51m |
| RENFE_51100 (San Bernardo Cercanías) | TRAM_SEV_SAN_BERNARDO (San Bernardo Tranvía) | 96m |
| METRO_SEV_L1_E11 (Nervión) | TRAM_SEV_EDUARDO_DATO (Eduardo Dato) | 117m |
| METRO_SEV_L1_E9 (Prado de San Sebastián) | TRAM_SEV_PRADO_SAN_SEBASTIÁN | 33m |
| METRO_SEV_L1_E8 (Puerta Jerez) | TRAM_SEV_PUERTA_JEREZ | 137m |

### Bilbao (Metro ↔ Euskotren ↔ Cercanías)
| Desde | Hasta | Distancia |
|-------|-------|-----------|
| METRO_BILBAO_7 (Abando) | EUSKOTREN Abando | 86m |
| METRO_BILBAO_7 (Abando) | RENFE_13200 (Abando Cercanías) | 160m |
| EUSKOTREN Abando | RENFE_13200 (Abando Cercanías) | 184m |
| METRO_BILBAO_7 (Abando) | RENFE_5451 (Bilbao La Concordia) | 167m |
| METRO_BILBAO_10 (San Mamés) | EUSKOTREN San Mames | 144m |
| METRO_BILBAO_6 (Casco Viejo) | EUSKOTREN Casco Viejo | 125m |

### Málaga
| Desde | Hasta | Distancia |
|-------|-------|-----------|
| METRO_MALAGA_PCH (El Perchel) | RENFE_54500 (María Zambrano) | 178m |
| METRO_MALAGA_PC1 (El Perchel L1) | METRO_MALAGA_PC2 (El Perchel L2) | 50m |
| METRO_MALAGA_GD1 (Guadalmedina L1) | METRO_MALAGA_GD2 (Guadalmedina L2) | 50m |

---

## 10. Tareas Pendientes

### 10.1 Correspondencias Completadas ✅

| Ciudad | Estaciones | Estado |
|--------|------------|--------|
| Sevilla | Nervión↔Eduardo Dato, Puerta Jerez, Prado San Sebastián | ✅ Completado |
| Bilbao | Abando (Metro↔Euskotren↔Cercanías), San Mamés, Casco Viejo | ✅ Completado |
| Valencia | Sant Isidre | ✅ Completado |
| Zaragoza | Delicias, Plaza Aragón | ✅ Completado |
| Málaga | El Perchel↔María Zambrano, L1↔L2 correspondences | ✅ Completado |
| Granada | Sin Cercanías - solo AVE | N/A |

### 10.2 Plataformas OSM Completadas ✅

| Red | Paradas | Estado |
|-----|---------|--------|
| Metro Valencia | 75 plataformas | ✅ OSM import |
| Metro Sevilla | 13 plataformas | ✅ OSM import |
| Metro Málaga | 19 plataformas | ✅ OSM import |
| Metro Granada | 12 plataformas | ✅ OSM import |
| Tranvía Zaragoza | 29 plataformas | ✅ OSM import |

### 10.3 Correspondencias Pendientes (Valencia)

Valencia tiene más correspondencias Metro↔Cercanías que no están en OSM:
- Xàtiva (Metro L3, L5 ↔ Cercanías)
- Colón (Metro L5 ↔ Cercanías)

### 10.4 Matching Manual de Intercambiadores

Estaciones grandes que requieren revisión manual:
- Nuevos Ministerios (Metro L6/L8/L10 + Cercanías)
- Atocha (Metro + Cercanías + AVE)
- Chamartín
- Sol
- Sants, Passeig de Gràcia, Catalunya (Barcelona)

### 10.5 Notas sobre Tranvías

| Red | GTFS | Plataformas | Notas |
|-----|------|-------------|-------|
| Tranvía Zaragoza | ✅ NAP | ✅ OSM | 29 plataformas importadas |
| Tranvía Vitoria | ✅ Euskotren GTFS | En Euskotren | Incluido en GTFS de Euskotren (Zone:70) |
| Tranvía Murcia | ✅ NAP | Pendiente | Necesita extracción OSM |

---

## 11. Referencias

- [OSM Wiki: stop_area_group](https://wiki.openstreetmap.org/wiki/Tag:public_transport%3Dstop_area_group)
- [OpenRailwayMap](https://openrailwaymap.app/)
- [Overpass Turbo](https://overpass-turbo.eu/)
- Documentación interna: `docs/IMPORT_OSM_CORRESPONDENCES.md`
