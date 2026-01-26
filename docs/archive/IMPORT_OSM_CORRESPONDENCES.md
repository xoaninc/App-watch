# Importación de Correspondencias desde OSM

## 1. Conceptos Clave

### 1.1 Tablas Involucradas

| Tabla | Propósito | Ejemplo |
|-------|-----------|---------|
| `stop_platform` | Coordenadas de cada andén/línea en UNA estación | Nuevos Ministerios: L6 (40.446, -3.692), L8 (40.445, -3.691) |
| `stop_correspondence` | Conexiones a pie entre estaciones DIFERENTES | Acacias (L5) ↔ Embajadores (L3): 200m, 3min |

### 1.2 Diferencia Clave

- **Misma estación, múltiples líneas** → Solo `stop_platform`
  - Cuatro Caminos: L1, L2, L6 (mismo nombre, mismo lugar)
  - Bilbao: L1, L4

- **Estaciones diferentes conectadas** → `stop_correspondence`
  - Acacias (L5) ↔ Embajadores (L3): pasillo subterráneo
  - Noviciado (L2) ↔ Plaza de España (L3, L10): pasillo subterráneo
  - Sierra de Guadalupe (Metro L1) ↔ Vallecas (Cercanías): intercambiador

### 1.3 Tags OSM Relevantes

| Tag | Tipo | Descripción |
|-----|------|-------------|
| `public_transport=stop_area_group` | Relation | Agrupa múltiples stop_areas que forman un intercambiador |
| `public_transport=stop_area` | Relation | Una estación/parada con sus elementos (andenes, accesos) |
| `railway=platform` | Way/Node | Andén físico con coordenadas |
| `railway=station` | Node | Estación de tren/metro |

---

## 2. Fuente de Datos: OSM stop_area_group

### 2.1 Consulta Overpass para Obtener Grupos

```
[out:json][timeout:120];
(
  relation["public_transport"="stop_area_group"];
);
out body geom;
```

### 2.2 Grupos Identificados en España (2026-01-26)

| ID | Nombre | Ciudad | Tipo | Acción |
|----|--------|--------|------|--------|
| 7849782 | Plaza de España - Noviciado | Madrid | Estaciones diferentes | `stop_correspondence` |
| 7849793 | Cuatro Caminos | Madrid | Misma estación | Solo `stop_platform` |
| 7849798 | Bilbao | Madrid | Misma estación | Solo `stop_platform` |
| 10077099 | Sierra Guadalupe - Vallecas | Madrid | Metro ↔ Cercanías | `stop_correspondence` |
| 5720834 | Espanya | Barcelona | TMB ↔ FGC | `stop_correspondence` |
| 7781537 | Plaça d'Espanya | Barcelona | TRAM/FGC | `stop_correspondence` |

---

## 3. Proceso de Importación

### 3.1 Paso 1: Obtener stop_area_group de OSM

```bash
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=[out:json][timeout:120];
(
  relation["public_transport"="stop_area_group"];
);
out body geom;' > osm_stop_area_groups.json
```

### 3.2 Paso 2: Para cada grupo, obtener sus miembros (stop_areas)

```bash
# Ejemplo para Plaza de España - Noviciado (7849782)
curl -s "https://overpass-api.de/api/interpreter" --data-urlencode 'data=[out:json];
relation(7849782);
out body;
>;
out skel qt;'
```

### 3.3 Paso 3: Analizar cada stop_area

Para cada `stop_area` miembro, extraer:
- **name**: Nombre de la estación
- **network**: Red (Metro de Barcelona, Metro de Madrid, Renfe Cercanías...)
- **ref**: Línea si está disponible
- **Coordenadas**: Del nodo `railway=station` o centroide de los `railway=platform`

### 3.4 Paso 4: Clasificar el grupo

**Criterios para `stop_correspondence`:**
1. Nombres de estación DIFERENTES (Plaza de España ≠ Noviciado)
2. Redes DIFERENTES (TMB Metro ≠ FGC)
3. Tipos de transporte DIFERENTES (Metro ≠ Cercanías)

**Criterios para solo `stop_platform`:**
1. Mismo nombre de estación
2. Misma red
3. Solo diferentes líneas (L1, L2, L6)

### 3.5 Paso 5: Buscar en nuestra BD

```sql
-- Buscar por nombre normalizado
SELECT id, name, cor_metro, cor_cercanias, cor_ml, cor_tranvia, lat, lon
FROM gtfs_stops
WHERE LOWER(REPLACE(name, ' ', '')) LIKE '%plazadeespaña%'
   OR LOWER(REPLACE(name, ' ', '')) LIKE '%noviciado%';
```

### 3.6 Paso 6: Insertar datos

**Si es correspondencia entre estaciones diferentes:**
```sql
INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
VALUES ('METRO_38', 'METRO_50', 250, 210, 'osm')
ON CONFLICT (from_stop_id, to_stop_id) DO UPDATE SET
    distance_m = EXCLUDED.distance_m,
    walk_time_s = EXCLUDED.walk_time_s;

-- Bidireccional
INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
VALUES ('METRO_50', 'METRO_38', 250, 210, 'osm')
ON CONFLICT DO NOTHING;
```

**Si son plataformas de la misma estación:**
```sql
INSERT INTO stop_platform (stop_id, lines, lat, lon, source)
VALUES ('METRO_XX', 'L1', 40.XXXX, -3.XXXX, 'osm')
ON CONFLICT (stop_id, lines) DO UPDATE SET
    lat = EXCLUDED.lat,
    lon = EXCLUDED.lon;
```

---

## 4. Mapeo de Redes OSM → Nuestra BD

| OSM network | Nuestro prefijo | Tipo |
|-------------|-----------------|------|
| Metro de Madrid | METRO_ | metro |
| Metro de Barcelona | TMB_METRO_ | metro |
| FGC | FGC_ | fgc |
| Cercanías Madrid | RENFE_ (network 10T) | cercanias |
| Rodalies Barcelona | RENFE_ (network 50T) | cercanias |
| Metro Bilbao | METRO_BILBAO_ | metro |
| Euskotren | EUSKOTREN_ | euskotren |
| TRAM Barcelona | TRAM_BARCELONA_ | tranvia |
| Metrovalencia | METRO_VALENCIA_ | metro |
| Metro Sevilla | METRO_SEV_ | metro |
| Metro Málaga | METRO_MALAGA_ | metro |

---

## 5. Correspondencias Conocidas en Madrid

### 5.1 Ya Importadas (manual + proximidad)

| Desde | Hasta | Distancia | Fuente |
|-------|-------|-----------|--------|
| METRO_92 (Acacias L5) | METRO_46 (Embajadores L3) | 200m | manual |
| METRO_38 (Noviciado L2) | METRO_50 (Plaza España L3,L10) | 250m | manual |
| METRO_46 (Embajadores) | RENFE_35609 (Embajadores C5) | 100m | manual |
| METRO_16 (Atocha) | RENFE_18000 (Atocha RENFE) | 6m | proximity |
| METRO_120 (Nuevos Ministerios) | RENFE_17001 (Nuevos Ministerios) | 5m | proximity |
| ... | ... | ... | proximity |

### 5.2 Pendientes de Verificar

- Bilbao (L1, L4) - ¿misma estación o diferentes?
- Cuatro Caminos (L1, L2, L6) - probablemente misma estación
- Otras que aparezcan en OSM

---

## 6. Script de Importación

Ver: `scripts/import_osm_correspondences.py`

### 6.1 Uso

```bash
# Importar correspondencias de Madrid
.venv/bin/python scripts/import_osm_correspondences.py --city madrid

# Importar de todas las ciudades
.venv/bin/python scripts/import_osm_correspondences.py --all

# Solo mostrar lo que haría (dry-run)
.venv/bin/python scripts/import_osm_correspondences.py --city madrid --dry-run
```

### 6.2 Flujo del Script

1. Consulta Overpass API para obtener `stop_area_group`
2. Para cada grupo:
   - Obtiene miembros (stop_areas)
   - Extrae nombre, red, línea, coordenadas
   - Clasifica: correspondencia vs plataformas
3. Busca estaciones en nuestra BD por nombre/coordenadas
4. Inserta en `stop_correspondence` o `stop_platform`
5. Genera reporte de lo importado y lo no encontrado

---

## 7. Verificación Manual Necesaria

Algunos casos requieren revisión manual:

1. **Nombres diferentes en OSM vs nuestra BD**
   - OSM: "Nuevos Ministerios" vs BD: "Nuevos Ministerios RENFE"

2. **Múltiples matches posibles**
   - "Sol" aparece en Metro y Cercanías

3. **Coordenadas muy diferentes**
   - Si la distancia calculada > 500m, revisar manualmente

4. **Redes no mapeadas**
   - Operadores nuevos no en nuestra BD

---

## 8. Endpoints Relacionados

| Endpoint | Descripción |
|----------|-------------|
| `GET /stops/{stop_id}/platforms` | Coordenadas de cada andén/línea |
| `GET /stops/{stop_id}/correspondences` | Conexiones a pie a otras estaciones |

### 8.1 Ejemplo de Respuesta /correspondences

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

---

## 9. Mantenimiento

### 9.1 Añadir Nueva Correspondencia Manual

```sql
-- Insertar bidireccional
INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
VALUES
    ('METRO_XX', 'METRO_YY', 150, 120, 'manual'),
    ('METRO_YY', 'METRO_XX', 150, 120, 'manual')
ON CONFLICT DO NOTHING;
```

### 9.2 Actualizar desde OSM

```bash
# Re-ejecutar importación (actualiza existentes)
.venv/bin/python scripts/import_osm_correspondences.py --city madrid --update
```

---

## 10. Referencias

- [OSM Wiki: stop_area_group](https://wiki.openstreetmap.org/wiki/Tag:public_transport%3Dstop_area_group)
- [OpenRailwayMap](https://openrailwaymap.app/)
- [Overpass Turbo](https://overpass-turbo.eu/)
