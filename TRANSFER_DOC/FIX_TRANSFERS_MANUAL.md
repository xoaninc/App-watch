# Análisis de Correspondencias Manuales - FIX NEEDED

**Fecha:** 2026-01-30
**Total correspondencias manuales:** 134

Este documento analiza todas las correspondencias con `source='manual'` que necesitan revisión.
Las correspondencias deberían provenir de:
1. **OSM stop_area_group** - Intercambiadores mapeados en OpenStreetMap
2. **GTFS transfers.txt** - Datos oficiales de los operadores (pocos lo tienen)
3. **Proximidad automática** - Calculadas por distancia <250m entre paradas

---

## Resumen por Red

| Red | Manual | Problema Principal | Estado |
|-----|--------|-------------------|--------|
| EUSKOTREN | 2 | Conexiones con Metro Bilbao, valores hardcodeados | Pendiente |
| FGC | 0 (dev) / 52 (prod) | Correspondencias intra-estación + inter-operador | ⚠️ Ver [FGC/](FGC/) |
| METRO_BILBAO | 4 | Sin OSM, valores hardcodeados incorrectos | Pendiente |
| METRO_MADRID | 5 | Correspondencias que deberían ser OSM o proximidad | Pendiente |
| METRO_MALAGA | 5 | Transbordos L1↔L2 + conexión con RENFE | Pendiente |
| METRO_SEVILLA | 5 | Conexiones con Tram Sevilla, sin OSM | Pendiente |
| METRO_VALENCIA | 2 | Conexiones con RENFE, valores estimados | Pendiente |
| RENFE | 21 | Conexiones con Metro/Tram de varias ciudades | Pendiente |
| TMB_METRO | 40 | Duplicados con OSM, valores estimados incorrectos | Pendiente |
| TRAM_ALICANTE | 1 | Conexión con RENFE | Pendiente |
| TRAM_BARCELONA | 10 | Conexiones con TMB Metro | Pendiente |
| TRAM_SEVILLA | 5 | Conexiones con Metro Sevilla, sin OSM | Pendiente |
| TRANVIA_ZARAGOZA | 1 | Conexión con RENFE | Pendiente |

---

## EUSKOTREN

**Total manual:** 2

| Desde | Hasta | Dist BD | Dist Real | Error |
|-------|-------|---------|-----------|-------|
| Zazpikaleak/Casco Viejo-Bilbao | Zazpikaleak/Casco Viejo | 50m | 125m | 150% |
| Zazpikaleak/Casco Viejo-Bilbao | Abando | 200m | 465m | 132% |

### Problema
Las distancias están muy subestimadas. La correspondencia Zazpikaleak Metro ↔ Euskotren es de ~125m reales, no 50m.

### Recomendación
- Recalcular con haversine
- Verificar si existe stop_area_group en OSM para Zazpikaleak

---

## FGC ⚠️ EN PROGRESO

**Estado:** Ver documentación detallada en [FGC/FGC_PROBLEM.md](FGC/FGC_PROBLEM.md)

**Resumen:**
- GTFS de FGC NO tiene transfers.txt
- Local (dev): 0 correspondencias ✅
- Producción: 52 correspondencias ❌ (pendiente eliminar)

---

## METRO_BILBAO

**Total manual:** 4

| Desde | Hasta | Dist BD | Dist Real | Error |
|-------|-------|---------|-----------|-------|
| Zazpikaleak/Casco Viejo | Zazpikaleak/Casco Viejo-Bilbao (Euskotren) | 50m | 125m | 150% |
| Abando | Zazpikaleak/Casco Viejo-Bilbao (Euskotren) | 200m | 465m | 132% |
| Abando | Abando (RENFE) | 160m | 160m | 0% |
| Abando | Bilbao La Concordia (RENFE) | 167m | 167m | 0% |

### Problema
- Las correspondencias de Abando están correctas
- Las de Zazpikaleak/Casco Viejo están muy subestimadas

### Recomendación
- Verificar si existe stop_area_group en OSM para Casco Viejo/Zazpikaleak
- Recalcular distancias con haversine
- La correspondencia Zazpikaleak Metro ↔ Euskotren debería ser ~125m, no 50m

---

## METRO_MADRID

**Total manual:** 5

| Desde | Hasta | Dist BD | Dist Real | Error |
|-------|-------|---------|-----------|-------|
| Noviciado | Plaza De España | 330m | 356m | 8% |
| Plaza De España | Noviciado | 330m | 356m | 8% |
| Embajadores (L3) | Acacias (L5) | 200m | 363m | 82% |
| Acacias (L5) | Embajadores (L3) | 200m | 363m | 82% |
| Embajadores (Metro) | Embajadores (Cercanías) | 100m | 53m | 47% |

### Problema
- Noviciado ↔ Plaza de España: valores aceptables (8% error)
- Acacias ↔ Embajadores: muy subestimado (82% error)
- Embajadores Metro ↔ Cercanías: sobreestimado (47% error)

### Recomendación
- OSM tiene stop_area_group para Plaza de España - Noviciado (7849782)
- Importar desde OSM en lugar de mantener manual
- Recalcular Acacias ↔ Embajadores

---

## METRO_MALAGA

**Total manual:** 5

| Desde | Hasta | Dist BD | Dist Real | Error |
|-------|-------|---------|-----------|-------|
| Guadalmedina L1 | Guadalmedina L2 | 50m | 0m | ⚠️ |
| Guadalmedina L2 | Guadalmedina L1 | 50m | 0m | ⚠️ |
| El Perchel L1 | El Perchel L2 | 50m | 0m | ⚠️ |
| El Perchel L2 | El Perchel L1 | 50m | 0m | ⚠️ |
| El Perchel | María Zambrano (RENFE) | 177m | 178m | 1% |

### Problema
- Los transbordos L1↔L2 muestran 0m porque el GTFS no tiene coordenadas distintas para cada andén
- El transbordo real entre andenes L1↔L2 requiere tiempo aunque estén en el mismo punto del mapa
- La conexión con RENFE está correcta

### Recomendación
- Mantener 50m/60s para transbordos L1↔L2 (tiempo mínimo de transbordo)
- O bien obtener coordenadas reales de andenes desde OSM

---

## METRO_SEVILLA

**Total manual:** 5

| Desde | Hasta | Dist BD | Dist Real | Error |
|-------|-------|---------|-----------|-------|
| San Bernardo (Metro) | San Bernardo (RENFE) | 87m | 87m | 0% |
| San Bernardo (Metro) | San Bernardo (Tram) | 51m | 51m | 0% |
| Nervión (Metro) | Eduardo Dato (Tram) | 117m | 117m | 0% |
| Puerta Jerez (Metro) | Puerta Jerez (Tram) | 137m | 137m | 0% |
| Prado San Sebastián (Metro) | Prado San Sebastián (Tram) | 33m | 33m | 0% |

### Estado
✅ Todas las distancias están correctas (calculadas con haversine)

### Recomendación
- No hay stop_area_group en OSM para Sevilla
- Considerar cambiar source a 'proximity' ya que todas están <250m
- Mantener como están

---

## METRO_VALENCIA

**Total manual:** 2

| Desde | Hasta | Dist BD | Dist Real | Error |
|-------|-------|---------|-----------|-------|
| Àngel Guimerà | València Estació del Nord | 300m | 768m | 156% |
| Xàtiva | València Estació del Nord | 31m | 31m | 0% |

### Problema
- Xàtiva ↔ Nord está correcta
- Àngel Guimerà ↔ Nord está muy subestimada (768m reales vs 300m en BD)

### Recomendación
- Recalcular Àngel Guimerà con haversine
- Verificar si la correspondencia tiene sentido (768m es mucho para caminar)

---

## RENFE

**Total manual:** 21

Conexiones de RENFE Cercanías/Rodalies con otros operadores:

| Ciudad | Conexión | Dist BD | Dist Real | Estado |
|--------|----------|---------|-----------|--------|
| Bilbao | Abando ↔ Metro Bilbao | 160m | 160m | ✅ OK |
| Bilbao | La Concordia ↔ Metro Bilbao | 167m | 167m | ✅ OK |
| Málaga | María Zambrano ↔ Metro | 177m | 178m | ✅ OK |
| Alicante | Terminal ↔ Tram Luceros | 447m | 447m | ✅ OK |
| Valencia | Nord ↔ Xàtiva | 31m | 31m | ✅ OK |
| Valencia | Nord ↔ Àngel Guimerà | 300m | 768m | ❌ Error 156% |
| Zaragoza | Goya ↔ Tranvía | 83m | 83m | ✅ OK |
| Barcelona | Sants ↔ TMB | 100-200m | 52-192m | ⚠️ Revisar |
| Barcelona | Passeig de Gràcia ↔ TMB | 100-150m | 53-383m | ❌ Errores |
| Barcelona | Catalunya ↔ TMB/FGC | 50-150m | 76-267m | ❌ Errores |
| Barcelona | La Sagrera ↔ TMB | 100-200m | 59-153m | ⚠️ Revisar |
| Barcelona | Arc de Triomf ↔ TMB | 100m | 65m | ⚠️ 35% error |
| Barcelona | Sant Adrià ↔ Tram | 55m | 55m | ✅ OK |

### Recomendación
- Las conexiones de Bilbao, Málaga, Alicante, Zaragoza están bien
- Barcelona tiene muchos errores → importar desde OSM stop_area_group
- Valencia Àngel Guimerà necesita recálculo

---

## TMB_METRO

**Total manual:** 40

La mayoría son conexiones con RENFE, FGC o TRAM Barcelona en intercambiadores.

### Intercambiadores principales

| Intercambiador | Conexiones | Estado |
|----------------|------------|--------|
| Catalunya | TMB ↔ FGC ↔ RENFE | ⚠️ Errores 49-174% |
| Espanya | TMB ↔ FGC | ⚠️ Errores 16-160% |
| Passeig de Gràcia | TMB ↔ RENFE | ⚠️ Errores 47-155% |
| Sants | TMB ↔ RENFE | ⚠️ Errores 4-48% |
| La Sagrera | TMB ↔ RENFE | ⚠️ Errores 23-78% |
| Arc de Triomf | TMB ↔ RENFE | ⚠️ Error 35% |
| Conexiones TRAM | TMB ↔ TRAM | ✅ Errores <40% |

### Problema
- Muchas correspondencias TMB tienen versión duplicada en OSM
- Los valores manuales no coinciden con las distancias reales

### Recomendación
- Muchas ya tienen versión OSM → eliminar duplicados manuales
- Para las que no tienen OSM → recalcular con haversine
- Barcelona tiene OSM stop_area_group para casi todos los intercambiadores

---

## TRAM_BARCELONA

**Total manual:** 10

| Desde | Hasta | BD | Real | Error |
|-------|-------|-----|------|-------|
| Palau Reial | TMB Facultat Ciències | 23m | 28m | 22% |
| Ernest Lluch | TMB Avinguda Xile | 43m | 59m | 37% |
| Maria Cristina | TMB Gran Via | 25m | 22m | 12% |
| Cornellà Centre | TMB Plaça Estació | 23m | 30m | 30% |
| Gorg | TMB Guifré | 33m | 37m | 12% |
| Ciutadella V.O. | TMB Zoo | 120m | 110m | 8% |
| Besòs | TMB Tram Besòs | 8m | 14m | 75% |
| Estació St. Adrià | RENFE Sant Adrià | 55m | 55m | 0% |
| Glòries | TMB Plaça Glòries | 25m | 32m | 28% |
| Sant Roc | TMB Plaça Sant Roc | 36m | 44m | 22% |

### Estado
Errores moderados (8-37%), excepto Besòs (75%).

### Recomendación
- Recalcular con haversine
- Errores son aceptables pero podrían mejorarse

---

## TRAM_SEVILLA

**Total manual:** 5

| Desde | Hasta | BD | Real | Error |
|-------|-------|-----|------|-------|
| Eduardo Dato | Nervión (Metro) | 117m | 117m | 0% |
| Prado San Sebastián | Metro Prado | 33m | 33m | 0% |
| Puerta Jerez | Metro Puerta Jerez | 137m | 137m | 0% |
| San Bernardo | Metro San Bernardo | 51m | 51m | 0% |
| San Bernardo | RENFE San Bernardo | 96m | 96m | 0% |

### Estado
✅ Todas las distancias están correctas

### Recomendación
- Mantener como están
- Considerar cambiar source a 'proximity'

---

## TRAM_ALICANTE

**Total manual:** 1

| Desde | Hasta | BD | Real |
|-------|-------|-----|------|
| Luceros | RENFE Terminal | 447m | 447m |

### Estado
✅ Correcto

---

## TRANVIA_ZARAGOZA

**Total manual:** 1

| Desde | Hasta | BD | Real |
|-------|-------|-----|------|
| Fernando El Católico | RENFE Goya | 83m | 83m |

### Estado
✅ Correcto

---

## Acciones Recomendadas

### 1. ELIMINAR (erróneas)

```sql
-- FGC Plaça Espanya: 20 correspondencias entre andenes de misma estación
DELETE FROM stop_correspondence
WHERE from_stop_id LIKE 'FGC_PE%' AND to_stop_id LIKE 'FGC_PE%';
```

### 2. RECALCULAR (valores incorrectos)

Ejecutar `scripts/recalculate_correspondences.py`:
- Zazpikaleak (Bilbao): 50m → 125m
- Acacias ↔ Embajadores (Madrid): 200m → 363m
- Àngel Guimerà (Valencia): 300m → 768m
- Barcelona intercambiadores: múltiples errores

### 3. IMPORTAR desde OSM (faltan)

OSM stop_area_group disponibles que no se están usando:
- Casco Viejo / Zazpikaleak (Bilbao) - verificar si existe
- Catalunya, Espanya, Passeig de Gràcia (Barcelona) - ya existen, usar en lugar de manual

### 4. ELIMINAR DUPLICADOS

Correspondencias que existen tanto en 'manual' como en 'osm':
- Catalunya (Barcelona)
- Probablemente otros intercambiadores de Barcelona

### 5. MANTENER (correctas)

- Metro Sevilla ↔ Tram Sevilla: todas correctas
- Bilbao Abando ↔ RENFE: correctas
- Málaga El Perchel ↔ RENFE: correcta
- Alicante, Zaragoza: correctas

---

## Fuentes de Datos Disponibles

| Operador | GTFS transfers.txt | OSM stop_area_group |
|----------|-------------------|---------------------|
| TMB Metro | ❌ No tiene | ✅ Disponible |
| FGC | ❌ No tiene | ✅ Parcial |
| Metro Bilbao | ❌ No tiene | ⚠️ Solo Abando |
| Metro Madrid | ❌ No tiene | ✅ Disponible |
| Euskotren | ✅ Tiene (13) | ⚠️ Parcial |
| Metro Sevilla | ❌ No tiene | ❌ No disponible |
| Metro Málaga | ❌ No tiene | ❌ No disponible |
| Metro Valencia | ❌ No tiene | ⚠️ Parcial |
| Renfe Cercanías | ✅ Tiene (19) | ⚠️ Parcial |
| Tram Barcelona | ❌ No tiene | ✅ Parcial |
| Tram Sevilla | ❌ No tiene | ❌ No disponible |

---

## BARCELONA - Problema de Estaciones Virtuales BCN_*

### Descripción del Problema

En Barcelona se crearon **26 estaciones virtuales** con prefijo `BCN_*` para agrupar intercambiadores.
Estas estaciones **NO existen en los GTFS originales** de TMB ni FGC.

Los `parent_station_id` de los andenes fueron **modificados manualmente** para apuntar a estas virtuales,
en lugar de usar los padres reales que vienen en los GTFS.

### Análisis Completo de Estaciones Virtuales BCN_*

| Virtual | Nombre | Hijos | TMB | Accesos | FGC | RENFE |
|---------|--------|-------|-----|---------|-----|-------|
| BCN_ARC_TRIOMF | Arc de Triomf | 5 | 1 | 4 | 0 | 0 |
| BCN_CLOT | Clot | 7 | 2 | 5 | 0 | 0 |
| BCN_COLLBLANC | Collblanc | 9 | 2 | 4 | 0 | 0 |
| BCN_DIAGONAL | Diagonal | 6 | 2 | 4 | 0 | 0 |
| BCN_FABRA_PUIG | Fabra i Puig | 10 | 2 | 8 | 0 | 0 |
| BCN_FRANCA | Estació de França | 3 | 1 | 2 | 0 | 0 |
| BCN_GRACIA | Gràcia | 6 | 1 | 1 | 4 | 0 |
| BCN_HOSPITAL_CLINIC | Hospital Clínic | 4 | 1 | 3 | 0 | 0 |
| BCN_LA_PAU | La Pau | 7 | 1 | 3 | 0 | 0 |
| BCN_MARIA_CRISTINA | Maria Cristina | 8 | 2 | 6 | 0 | 0 |
| BCN_PARALEL | Paral·lel | 8 | 3 | 5 | 0 | 0 |
| BCN_PASSEIG_GRACIA | Passeig de Gràcia | 6 | 3 | 3 | 0 | 0 |
| BCN_PL_CATALUNYA | Plaça Catalunya | 21 | 2 | 14 | 5 | 0 |
| BCN_PL_ESPANYA | Plaça Espanya | 19 | 3 | 12 | 4 | 0 |
| BCN_PROVENCA | Provença | 3 | 0 | 0 | 3 | 0 |
| BCN_PUBILLA_CASES | Pubilla Cases | 8 | 2 | 6 | 0 | 0 |
| BCN_SAGRADA_FAMILIA | Sagrada Família | 8 | 2 | 6 | 0 | 0 |
| BCN_SAGRERA | La Sagrera | 13 | 3 | 10 | 0 | 0 |
| BCN_SANT_ANDREU | Sant Andreu | 4 | 1 | 3 | 0 | 0 |
| BCN_SANTS | Barcelona Sants | 10 | 2 | 8 | 0 | 0 |
| BCN_TORRE_BARO | Torre Baró / Vallbona | 6 | 1 | 5 | 0 | 0 |
| BCN_TRINITAT_NOVA | Trinitat Nova | 8 | 4 | 4 | 0 | 0 |
| BCN_UNIVERSITAT | Universitat | 8 | 2 | 6 | 0 | 0 |
| BCN_URQUINAONA | Urquinaona | 8 | 2 | 6 | 0 | 0 |
| BCN_VERDAGUER | Verdaguer | 7 | 2 | 3 | 0 | 0 |
| BCN_ZONA_UNIVERSITARIA | Zona Universitària | 10 | 2 | 5 | 0 | 0 |

### Resumen

- **Total estaciones virtuales BCN_*:** 26
- **Con FGC (intercambiadores reales TMB+FGC):** 4
  - BCN_GRACIA (TMB + FGC)
  - BCN_PL_CATALUNYA (TMB + FGC)
  - BCN_PL_ESPANYA (TMB + FGC)
  - BCN_PROVENCA (solo FGC)
- **Con RENFE:** 0 (las conexiones RENFE están en stop_correspondence, no en parent_station)
- **Solo TMB (podrían ser innecesarias):** 22

### Estructura Original de los GTFS

#### TMB Metro Barcelona

TMB tiene en su GTFS **139 estaciones padre reales** con formato `TMB_METRO_P.6660XXX`:

```
GTFS Original:
  TMB_METRO_P.6660122 (Espanya)     → location_type=1, parent=NULL
  TMB_METRO_1.122 (Espanya L1)      → location_type=0, parent=TMB_METRO_P.6660122
  TMB_METRO_1.321 (Espanya L3)      → location_type=0, parent=TMB_METRO_P.6660322
  TMB_METRO_E.12201 (Acceso)        → location_type=2, parent=TMB_METRO_P.6660122

Base de Datos Actual (MODIFICADO):
  TMB_METRO_P.6660122 (Espanya)     → location_type=1, parent=NULL (HUÉRFANA)
  TMB_METRO_1.122 (Espanya L1)      → location_type=0, parent=BCN_PL_ESPANYA
  TMB_METRO_1.321 (Espanya L3)      → location_type=0, parent=BCN_PL_ESPANYA
  TMB_METRO_E.12201 (Acceso)        → location_type=2, parent=BCN_PL_ESPANYA
```

#### FGC

FGC tiene en su GTFS estaciones padre con formato `PE`, `PC`, `GR`, etc.:

```
GTFS Original:
  FGC_PE (Plaça Espanya)            → location_type=1, parent=NULL
  FGC_PE1 (Andén 1)                 → location_type=0, parent=FGC_PE
  FGC_PE2 (Andén 2)                 → location_type=0, parent=FGC_PE

Base de Datos Actual (MODIFICADO):
  FGC_PE (Plaça Espanya)            → location_type=1, parent=NULL (HUÉRFANA)
  FGC_PE1 (Andén 1)                 → location_type=0, parent=BCN_PL_ESPANYA
  FGC_PE2 (Andén 2)                 → location_type=0, parent=BCN_PL_ESPANYA
```

### Archivos GTFS Relevantes

| Operador | Archivo | Tiene transfers.txt | Tiene pathways.txt |
|----------|---------|--------------------|--------------------|
| TMB Metro | api.tmb.cat/gtfs.zip | ❌ No | ✅ Sí |
| FGC | fgc.cat/google_transit.zip | ❌ No | ❌ No |

### Problema de las Correspondencias Manuales

Las 20 correspondencias entre `FGC_PE, PE1, PE2, PE3, PE4` fueron creadas porque
los andenes fueron reasignados a `BCN_PL_ESPANYA` y se perdió la relación padre-hijo original.

Si restauramos los padres reales del GTFS:
- `FGC_PE1, PE2, PE3, PE4` → parent=`FGC_PE`
- RAPTOR agrupará automáticamente los andenes de FGC
- Las correspondencias entre FGC_PE* serán **innecesarias**

### Solución Propuesta

1. **Restaurar parent_station_id original** de los GTFS para cada operador:
   - TMB andenes → parent = `TMB_METRO_P.*` (del GTFS)
   - FGC andenes → parent = `FGC_PE`, `FGC_PC`, etc. (del GTFS)

2. **Usar stop_correspondence** para conectar operadores diferentes:
   - FGC ↔ TMB (con distancias calculadas por haversine)
   - TMB ↔ RENFE
   - etc.

3. **Eliminar las estaciones virtuales BCN_*** que quedarán huérfanas

4. **Eliminar correspondencias redundantes** entre andenes de la misma estación

---

### ✅ CAMBIOS EJECUTADOS - FGC (2026-01-31)

#### Paso 1: Restaurar parent_station_id de FGC

```sql
-- Ejecutado:
UPDATE gtfs_stops SET parent_station_id = 'FGC_GR' WHERE id IN ('FGC_GR1','FGC_GR2','FGC_GR3','FGC_GR4');
UPDATE gtfs_stops SET parent_station_id = 'FGC_PC' WHERE id IN ('FGC_PC1','FGC_PC2','FGC_PC3','FGC_PC4','FGC_PC5');
UPDATE gtfs_stops SET parent_station_id = 'FGC_PE' WHERE id IN ('FGC_PE1','FGC_PE2','FGC_PE3','FGC_PE4');
UPDATE gtfs_stops SET parent_station_id = 'FGC_PR' WHERE id IN ('FGC_PR1','FGC_PR2');
UPDATE gtfs_stops SET parent_station_id = NULL WHERE id = 'FGC_PR';  -- Es padre
```

**Resultado:**
| Padre FGC | Hijos restaurados |
|-----------|-------------------|
| FGC_GR (Gràcia) | 4 |
| FGC_PC (Plaça Catalunya) | 5 |
| FGC_PE (Plaça Espanya) | 4 |
| FGC_PR (Provença) | 2 |

#### Paso 2: Eliminar BCN_* sin hijos

```sql
-- Ejecutado:
DELETE FROM gtfs_stops WHERE id = 'BCN_PROVENCA';
```

**Nota:** BCN_GRACIA, BCN_PL_CATALUNYA, BCN_PL_ESPANYA NO se eliminaron porque aún tienen hijos TMB.

#### Paso 3: Eliminar correspondencias FGC_PE* erróneas

```sql
-- Ejecutado:
DELETE FROM stop_correspondence
WHERE from_stop_id LIKE 'FGC_PE%' AND to_stop_id LIKE 'FGC_PE%';
-- Resultado: 20 filas eliminadas
```

#### Estado actual de correspondencias TMB ↔ FGC

28 correspondencias restantes. Algunas con distancias incorrectas:

| Intercambiador | Correspondencias | Estado |
|----------------|------------------|--------|
| Catalunya (TMB ↔ FGC) | 4 | ⚠️ Distancias incorrectas |
| Espanya (TMB ↔ FGC) | 20 | ⚠️ Algunas incorrectas |
| Provença (TMB ↔ FGC) | 4 | ✅ OSM - correctas |

**Pendiente:** Recalcular distancias de Catalunya y Espanya con haversine.

### Intercambiadores Reales TMB + FGC

Estos son los únicos que necesitan `stop_correspondence` entre operadores:

| Intercambiador | TMB | FGC | Conexión Necesaria |
|----------------|-----|-----|-------------------|
| Plaça Catalunya | L1, L3 | Línies Barcelona-Vallès | TMB_METRO_1.126 ↔ FGC_PC |
| Plaça Espanya | L1, L3 | Línies Llobregat-Anoia | TMB_METRO_1.122 ↔ FGC_PE |
| Gràcia | L3 | Línies Barcelona-Vallès | TMB_METRO_1.329 ↔ FGC_GR |
| Provença | - | Línies Barcelona-Vallès | Solo FGC (no necesita correspondencia) |

---

## Prioridad de Acciones

1. **ALTA**: Restaurar parent_station_id original de GTFS (TMB y FGC)
2. **ALTA**: Eliminar estaciones virtuales BCN_* huérfanas
3. **ALTA**: Eliminar 20 correspondencias FGC_PE* erróneas
4. **ALTA**: Recalcular Zazpikaleak (Bilbao) - error 150%
5. **MEDIA**: Recalcular Acacias-Embajadores (Madrid) - error 82%
6. **MEDIA**: Crear correspondencias TMB ↔ FGC con haversine
7. **BAJA**: Recalcular Valencia Àngel Guimerà
8. **BAJA**: Eliminar duplicados manual/OSM
