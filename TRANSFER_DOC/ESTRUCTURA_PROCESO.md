# Estructura de Proceso para Importación de Datos

Este documento define el proceso estándar para importar datos de accesos, andenes y correspondencias para cada red de transporte.

## Estructura de Carpetas

```
TRANSFER_DOC/
├── ESTRUCTURA_PROCESO.md          (este archivo)
├── FIX_TRANSFERS_MANUAL.md        (resumen general por red)
├── [RED]/
│   ├── [RED]_PROBLEM.md           (documentación del problema)
│   ├── [RED]_FIX.md               (plan de solución y cronología)
│   ├── [RED]_REVIEW.md            (checklist de revisión manual)
│   ├── [red]_extract_osm.py       (script 1: extracción)
│   ├── [red]_data.json            (datos extraídos para revisión)
│   └── [red]_populate_tables.py   (script 2: población)
```

## Proceso por Red

### Paso 0: Limpiar datos erróneos (si aplica)
**Archivo:** `[RED]_PROBLEM.md`

**ANTES de cualquier otra acción**, si la red tiene datos añadidos manualmente o de OSM que no estaban en el GTFS oficial:

1. Identificar datos a eliminar:
   ```sql
   -- Accesos manuales en stop_access
   SELECT * FROM stop_access WHERE stop_id LIKE '[PREFIX]_%';

   -- Accesos en gtfs_stops (location_type=2)
   SELECT * FROM gtfs_stops WHERE id LIKE '[PREFIX]_%' AND location_type = 2;

   -- Correspondencias
   SELECT * FROM stop_correspondence
   WHERE from_stop_id LIKE '[PREFIX]_%' OR to_stop_id LIKE '[PREFIX]_%';
   ```

2. Eliminar datos erróneos (conservar solo lo del GTFS oficial)

3. Documentar qué se eliminó en `[RED]_PROBLEM.md`

**PAUSA:** Confirmar eliminación antes de continuar.

---

### Paso 1: Documentar problema
**Archivo:** `[RED]_PROBLEM.md`

Antes de empezar, documentar el estado actual:
- Analizar GTFS oficial (¿tiene transfers.txt? ¿pathways.txt?)
- Listar correspondencias existentes en BD local
- Listar correspondencias en BD producción (si difieren)
- Identificar errores y datos de origen desconocido
- Verificar estructura padre/hijo en GTFS (location_type)

**PAUSA:** Revisar documentación antes de continuar.

---

### Paso 2: Extracción de datos OSM
**Archivos:** `[red]_extract_osm.py` → `[red]_data.json`

Crear script que consulte OSM (Overpass API) para extraer:

| Elemento | Tags OSM | location_type GTFS |
|----------|----------|-------------------|
| Accesos | `railway=subway_entrance`, `entrance=yes` | 2 |
| Andenes | `railway=platform`, `public_transport=platform` | 0 |
| stop_area | `public_transport=stop_area` | - |
| stop_area_group | `public_transport=stop_area_group` | - |

El script debe:
1. Extraer datos crudos de OSM
2. Mapear andenes a estaciones (vía stop_area relations)
3. Guardar todo en `[red]_data.json`
4. Listar discrepancias encontradas

**PAUSA:** Ejecutar script y revisar output antes de continuar.

---

### Paso 3: Revisión manual
**Archivos:** `[red]_data.json` → `[RED]_REVIEW.md`

Crear archivo de revisión con checklist:

#### 3.1 Revisar andenes
- Verificar que todos los andenes tienen estación asociada
- Identificar duplicados
- Corregir andenes huérfanos (sin stop_area en OSM)

**PAUSA:** El usuario debe revisar y aprobar andenes.

#### 3.2 Revisar accesos
- Verificar nombres de accesos
- Corregir accesos sin nombre (marcados como "?")
- Validar coordenadas

**PAUSA:** El usuario debe revisar y aprobar accesos.

#### 3.3 Revisar mapeo estaciones
- Confirmar mapeo OSM_ID → GTFS_ID para estaciones clave
- Documentar códigos GTFS (ej: PC = Plaça Catalunya)

**PAUSA:** El usuario debe confirmar mapeo.

#### 3.4 Actualizar JSON
- Aplicar todas las correcciones al `[red]_data.json`
- Añadir secciones: `accesos_verificados`, `mapeo_estaciones`
- Actualizar contadores en `resumen`

---

### Paso 4: Comparación con BD
**Objetivo:** Verificar qué datos de OSM ya existen en la BD y cuáles faltan.

#### 4.1 Comparar andenes
- Consultar `gtfs_stops` filtrando por operador y `location_type=0`
- Comparar con andenes extraídos de OSM
- Identificar:
  - Andenes en BD que no están en OSM
  - Andenes en OSM que no están en BD
  - Andenes con coordenadas diferentes

#### 4.2 Comparar accesos
- Consultar `gtfs_stops` filtrando por operador y `location_type=2`
- Comparar con accesos extraídos de OSM
- Identificar discrepancias

#### 4.3 Comparar estaciones padre
- Consultar `gtfs_stops` filtrando por operador y `location_type=1`
- Verificar mapeo OSM_ID → GTFS_ID
- Confirmar estructura padre/hijo

#### 4.4 Documentar diferencias
- Crear sección en `[RED]_REVIEW.md` con resultados de comparación
- Decidir acciones: insertar, actualizar, ignorar

**PAUSA:** Revisar diferencias antes de población.

---

### Paso 5: Población de tablas
**Archivo:** `[red]_populate_tables.py`

Crear script que lea `[red]_data.json` (ya validado) y:
1. Actualice `gtfs_stops` con coordenadas de andenes y accesos
2. Cree correspondencias en `stop_correspondence`
3. Calcule distancias reales (haversine o OSRM/BRouter)

**PAUSA:** Revisar script antes de ejecutar.

---

### Paso 6: Pruebas en local
- Ejecutar script en BD local
- Verificar datos insertados con queries
- Probar routing con las nuevas correspondencias

**PAUSA:** Validar resultados antes de producción.

---

### Paso 7: Despliegue a producción
- Eliminar datos erróneos en producción
- Ejecutar script de población
- Verificar datos insertados
- Documentar resultado final

---

## Fuentes de Datos

| Fuente | Uso |
|--------|-----|
| GTFS oficial | Estructura padre/hijo, IDs de paradas |
| OSM (Overpass API) | Accesos, andenes, stop_area |
| OSRM / BRouter | Distancias reales a pie (opcional) |
| Haversine | Distancias aproximadas (fallback) |

## Técnicas de Extracción OSM

### 1. Buscar andenes por operador
```
[out:json][timeout:60];
(
  way["railway"="platform"]["operator"~"OPERADOR",i](BBOX);
  node["railway"="platform"]["operator"~"OPERADOR",i](BBOX);
  way["public_transport"="platform"]["operator"~"OPERADOR",i](BBOX);
);
out center;
```

### 2. Buscar stop_area por operador/nombre
```
[out:json][timeout:60];
(
  relation["public_transport"="stop_area"]["operator"~"OPERADOR",i](BBOX);
  relation["public_transport"="stop_area"]["name"~"NOMBRE",i](BBOX);
);
out body;
```

### 3. Mapeo andén → estación (técnica clave)

**Problema:** Los andenes en OSM frecuentemente NO tienen el tag `station` con el nombre de la estación.

**Solución:** Usar relaciones stop_area para mapear:
1. Buscar todas las stop_area del operador
2. Para cada stop_area, expandir sus miembros con query recursivo:
   ```
   relation(OSM_ID);
   (._;>;);
   out body center;
   ```
3. Filtrar elementos con `railway=platform`
4. Crear mapeo: `platform_osm_id → station_name`

### 4. Buscar accesos
```
[out:json][timeout:60];
(
  node["railway"="subway_entrance"]["operator"~"OPERADOR",i](BBOX);
  node["entrance"="yes"]["operator"~"OPERADOR",i](BBOX);
  node["railway"="subway_entrance"]["network"="RED"](BBOX);
);
out body;
```

### 5. Buscar intercambiadores (stop_area_group)
```
[out:json][timeout:60];
area["name"="CIUDAD"]->.city;
(
  relation["public_transport"="stop_area_group"](area.city);
);
out body;
```
**Nota:** No todas las ciudades tienen stop_area_group en OSM.

## Problemas Comunes y Soluciones

| Problema | Solución |
|----------|----------|
| Andenes sin nombre de estación | Mapear vía stop_area relations (técnica 3) |
| Accesos no encontrados | Buscar con múltiples tags (subway_entrance, entrance=yes) |
| Coordenadas iguales padre/hijo en GTFS | Usar coordenadas reales de OSM |
| stop_area_group no existe | Crear correspondencias por proximidad |
| Andenes huérfanos (sin stop_area) | Identificar manualmente por coordenadas |
| Duplicados en OSM | Identificar y marcar para ignorar |
| Accesos sin nombre | Revisar manualmente, buscar nombre en contexto |

## Actualizaciones de coordenadas de andenes

**Actualizar coordenadas SOLO donde coincide el número de andenes OSM=BD.**

### Criterio de modelado
- **BD cuenta vías** (cada sentido = 1 andén)
- **OSM cuenta andenes físicos** (andén central = 1, aunque sirva 2 vías)

### Proceso de actualización
1. Agrupar andenes OSM y BD por estación padre
2. Si `count(OSM) == count(BD)`: actualizar coordenadas automáticamente
3. Si `count(OSM) != count(BD)`: ignorar (diferencia de criterio, no error)

### Casos comunes ignorados (sin acción)
| Patrón | Ejemplo | Motivo |
|--------|---------|--------|
| OSM=1, BD=2 | Terrassa Rambla | Andén central, 2 vías |
| OSM<BD complejas | Gràcia, Sarrià | Múltiples líneas/apartados |

### Validación de mapeos
Usar algoritmo de proximidad como verificación:
- Si distancia > 100m entre andén OSM y BD → revisar mapeo manualmente
- Errores detectados así: FGC_QUE→FGC_RV, FGC_SJ→FGC_SJM

## Problemas de Mapeo OSM ↔ GTFS

### 1. Estaciones sin datos en OSM
No todas las estaciones GTFS tienen datos en OSM. Causas comunes:
- Estaciones pequeñas o rurales sin mapear en OSM
- Estaciones nuevas no actualizadas en OSM
- Diferentes operadores mapeados de forma incompleta

**Ejemplo FGC:** 45 de 104 estaciones sin andenes en OSM (43%)

### 2. Nombres distintos entre OSM y GTFS
Los nombres pueden diferir significativamente entre fuentes:

| Tipo | Ejemplo |
|------|---------|
| Prefijos/sufijos | BD: "Barcelona - Plaça Catalunya" vs OSM: "Catalunya (FGC)" |
| Abreviaciones | BD: "Pl. Molina" vs OSM: "Plaça Molina" |
| Orden invertido | BD: "Guardia de Tremp" vs OSM: "Guàrdia de Tremp" |

### 3. Estaciones con nombres similares (CRÍTICO)
Algunas estaciones tienen nombres muy similares pero son **estaciones diferentes**:

| BD | OSM | ¿Son la misma? |
|----|-----|----------------|
| FGC_GR "Gràcia" | "Gràcia" | ✅ Sí |
| FGC_CF "Can Feu - Gràcia" | "Can Feu \| Gràcia" | ✅ Sí (diferente a FGC_GR) |

**Peligro:** Un mapeo automático por nombre parcial puede confundir estaciones diferentes.

### 4. Estaciones con accesos pero sin andenes
Algunas estaciones tienen datos de accesos en OSM pero no de andenes.

**Solución:** Buscar en `estaciones_clave` datos sueltos con:
- Coordenadas cercanas a la estación
- Tag `train:yes` (diferencia FGC/tren de metro)
- Sin operador definido (`operator: ?`)

**Ejemplo FGC Espanya:**
- Problema: 3 accesos, 0 andenes en extracción inicial
- Solución: 4 nodos con `train:yes` encontrados en `estaciones_clave`
- Resultado: Atribuidos a FGC_PE (4 vías de la estación terminal)

### 5. Inconsistencias de nivel (level) en OSM
Los tags `level` pueden ser inconsistentes entre mapeadores:

**Ejemplo:** Andenes de una misma estación etiquetados en niveles diferentes (-2 y -3) cuando físicamente están al mismo nivel.

**Solución:** Verificar que los puntos están geográficamente juntos e ignorar discrepancia de nivel.

### Recomendaciones

1. **Mapeo manual obligatorio** para estaciones con nombres similares
2. **Verificar coordenadas** antes de asociar estaciones
3. **Documentar estaciones sin datos** para completar posteriormente
4. **No forzar mapeos** cuando no hay datos fiables

## Estructura del JSON de datos

```json
{
  "fecha_extraccion": "ISO datetime",
  "resumen": {
    "accesos": 0,
    "andenes": 0,
    "stop_areas": 0,
    "stop_area_groups": 0,
    "discrepancias": 0,
    "andenes_con_estacion": 0,
    "andenes_sin_estacion": 0,
    "andenes_duplicados": 0,
    "accesos_corregidos": 0,
    "mapeo_estaciones": 0
  },
  "accesos": [],
  "andenes": [],
  "stop_areas": [],
  "stop_area_groups": [],
  "estaciones_clave": [],
  "discrepancias": [],
  "accesos_verificados": [],
  "mapeo_estaciones": []
}
```

## Estado por Red

| Red | Limpieza | Problema | Extracción | Revisión | Comparación | Población | Producción | RAPTOR |
|-----|----------|----------|------------|----------|-------------|-----------|------------|--------|
| FGC | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⏳ bloqueado |
| TMB | ✅ | ✅ | ✅ GTFS+OSM | ✅ | - | ⏳ | - | ⏳ pendiente |
| METRO_BILBAO | - | - | - | - | - | - | - | - |
| RENFE_CERCANIAS | - | - | - | - | - | - | - | - |
| TRAM_BARCELONA | - | - | - | - | - | - | - | - |
| ... | - | - | - | - | - | - | - | - |

### Notas
- **FGC RAPTOR bloqueado:** Depende de arreglar estructura intercambiadores BCN_* (TMB)
- **TMB en progreso:** Limpieza ✅, GTFS ✅, OSM ✅, Revisión ✅ → Pendiente población
- Ver `TRANSFER_DOC/FGC/FGC_CORRESPONDENCIAS.md` para detalles del problema BCN_*
