# País Vasco - Revisión de Correspondencias

**Fecha:** 2026-01-31

## 1. Datos OSM Extraídos

| Operador | Estaciones OSM | Andenes OSM | Accesos OSM |
|----------|----------------|-------------|-------------|
| Metro Bilbao | 49 | 5 | 4 |
| Euskotren | 68 | 1 | - |
| Funicular Artxanda | 43 elementos | - | - |

**Stop Areas:** 17 encontrados
**Stop Area Groups:** 0 encontrados

---

## 2. Intercambiadores Identificados en OSM

### 2.1 Abando (PRINCIPAL)

| Operador | OSM ID | Nombre | Coordenadas |
|----------|--------|--------|-------------|
| Metro Bilbao | 3271221734 | Abando | 43.2614, -2.9275 |
| Euskotren | 582149252 | Abando | 43.2610, -2.9266 |
| RENFE/Adif | 5299959452 | Bilbao Abando | 43.2605, -2.9276 |

**Stop Areas OSM:**
- 7563396: Abando (Metro Bilbao) - 12 miembros
- 7833427: Abando Indalecio Prieto (Adif/RENFE) - 23 miembros
- 8112120: Abando (Euskotren) - 2 miembros

### 2.2 Casco Viejo / Zazpikaleak

| Operador | OSM ID | Nombre | Coordenadas |
|----------|--------|--------|-------------|
| Metro Bilbao | 7718058 | Zazpikaleak/Casco Viejo | 43.2602, -2.9219 |
| Euskotren | (2577) | Zazpikaleak/Casco Viejo | 43.2600, -2.9222 |

### 2.3 San Mamés

| Operador | OSM ID | Nombre | Coordenadas |
|----------|--------|--------|-------------|
| Metro Bilbao | 7718032 | Santimami/San Mamés | 43.2621, -2.9475 |
| Euskotren | 582138782 | San Mamés | 43.2618, -2.9491 |
| RENFE | 5299959452 | San Mamés | 43.2621, -2.9493 |

### 2.4 Matiko (Funicular)

| Operador | OSM ID | Nombre | Coordenadas |
|----------|--------|--------|-------------|
| Euskotren | 5061716164 | Matiko | 43.2690, -2.9255 |
| Funicular | (ver abajo) | Plaza Funicular | 43.2687, -2.9261 |

### 2.5 Lutxana (¡NUEVO!)

| Operador | OSM ID | Nombre | Coordenadas |
|----------|--------|--------|-------------|
| Metro Bilbao | - | Lutxana | 43.2910, -2.9699 |
| Euskotren | - | Lutxana-Erandio | 43.2913, -2.9698 |

**Stop Area OSM:** 7203811 - `operator: "Metro Bilbao S.A.;Eusko Trenbideak"`

---

## 3. Comparativa BD vs OSM

### 3.1 Estaciones en BD

| Intercambiador | Metro Bilbao | Euskotren | RENFE | Funicular |
|----------------|--------------|-----------|-------|-----------|
| **Abando** | METRO_BILBAO_7 | ES:...:1471 | RENFE_05451 | - |
| **Casco Viejo** | METRO_BILBAO_6 | ES:...:2577 | - | - |
| **San Mamés** | METRO_BILBAO_10 | ES:...:1470 | RENFE_05455* | - |
| **Matiko** | - | ES:...:2597 | - | FUNICULAR_12 |
| **Lutxana** | METRO_BILBAO_14 | ES:...:2576 | - | - |

*San Mamés RENFE es "Basurto Hospital" (RENFE_05455), no exactamente San Mamés

### 3.2 Distancias Calculadas (BD)

| Intercambiador | Operadores | Distancia | En BD |
|----------------|------------|-----------|-------|
| Abando | Metro ↔ Euskotren 1471 | **86m** | ❌ |
| Abando | Metro ↔ RENFE | **167m** | ❌ |
| Abando | Euskotren ↔ RENFE | **98m** | ❌ |
| Casco Viejo | Metro ↔ Euskotren | **125m** | ❌ |
| San Mamés | Metro ↔ Euskotren | **144m** | ❌ |
| Matiko | Funicular ↔ Euskotren | **90m** | ❌ |
| **Lutxana** | Metro ↔ Euskotren | **40m** | ❌ |

---

## 4. Correspondencias a Añadir

### Alta Prioridad 🔴

| # | From | To | Distancia | Tiempo |
|---|------|-----|-----------|--------|
| 1 | METRO_BILBAO_7 | EUSKOTREN_ES:Euskotren:StopPlace:1471: | 86m | 90s |
| 2 | METRO_BILBAO_6 | EUSKOTREN_ES:Euskotren:StopPlace:2577: | 125m | 120s |
| 3 | METRO_BILBAO_10 | EUSKOTREN_ES:Euskotren:StopPlace:1470: | 144m | 150s |
| 4 | METRO_BILBAO_14 | EUSKOTREN_ES:Euskotren:StopPlace:2576: | 40m | 60s |
| 5 | FUNICULAR_ARTXANDA_12 | EUSKOTREN_ES:Euskotren:StopPlace:2597: | 90m | 90s |
| 6 | METRO_BILBAO_7 | RENFE_05451 | 167m | 180s |

### Media Prioridad 🟡

| # | From | To | Distancia | Tiempo |
|---|------|-----|-----------|--------|
| 7 | EUSKOTREN_ES:Euskotren:StopPlace:1471: | RENFE_05451 | 98m | 120s |
| 8 | EUSKOTREN_ES:Euskotren:StopPlace:1472: | RENFE_05455 | 209m | 180s |

---

## 5. Resumen para Revisión Manual

### ✅ Confirmados por OSM

- [x] **Abando**: Metro + Euskotren + RENFE (stop_areas separados)
- [x] **Casco Viejo**: Metro + Euskotren (stop_areas presentes)
- [x] **San Mamés**: Metro + Euskotren + RENFE (stop_areas presentes)
- [x] **Matiko**: Funicular + Euskotren (stop_area presente)
- [x] **Lutxana**: Metro + Euskotren (stop_area con ambos operadores!)

### ⚠️ Requieren verificación

- [ ] San Mamés ↔ Basurto Hospital (RENFE): ¿Son el mismo intercambiador?
- [ ] Arriaga (Euskotren 1480) ↔ Abando: OSM muestra proximidad

---

## 6. Cobertura Geográfica

### San Sebastián / Donostia
- **RENFE Cercanías:** ❌ No existe (RENFE no llega a Donostia)
- **Euskotren:** ✅ 9 estaciones (Amara, Loiola, Herrera, etc.)
- **Correspondencias multimodales:** Ninguna necesaria (solo Euskotren)

### Vitoria-Gasteiz
- **RENFE:** ❌ No existe
- **Euskotren:** ✅ ~20 estaciones (Tren + Tranvía integrado)
- **Correspondencias multimodales:** Ninguna necesaria (todo es Euskotren)

### Bilbao
- **RENFE:** ✅ Línea Bilbao-Balmaseda (RENFE_05451-05497)
- **Metro Bilbao:** ✅ L1 + L2 (42 estaciones)
- **Euskotren:** ✅ Múltiples líneas
- **Funicular Artxanda:** ✅
- **Correspondencias necesarias:** ✅ Ver sección 4

---

## 7. Correspondencias Finales a Crear

### Bilbao - Alta Prioridad 🔴

| # | From | To | Distancia | Tiempo |
|---|------|-----|-----------|--------|
| 1 | METRO_BILBAO_7 (Abando) | EUSKOTREN_ES:Euskotren:StopPlace:1471: | 86m | 90s |
| 2 | METRO_BILBAO_6 (Casco Viejo) | EUSKOTREN_ES:Euskotren:StopPlace:2577: | 125m | 120s |
| 3 | METRO_BILBAO_10 (San Mamés) | EUSKOTREN_ES:Euskotren:StopPlace:1470: | 144m | 150s |
| 4 | METRO_BILBAO_14 (Lutxana) | EUSKOTREN_ES:Euskotren:StopPlace:2576: | 40m | 60s |
| 5 | FUNICULAR_ARTXANDA_12 | EUSKOTREN_ES:Euskotren:StopPlace:2597: | 90m | 90s |
| 6 | METRO_BILBAO_7 (Abando) | RENFE_05451 | 167m | 180s |

### Bilbao - Media Prioridad 🟡

| # | From | To | Distancia | Tiempo |
|---|------|-----|-----------|--------|
| 7 | EUSKOTREN_ES:Euskotren:StopPlace:1471: (Abando) | RENFE_05451 | 98m | 120s |
| 8 | EUSKOTREN_ES:Euskotren:StopPlace:1472: (Hospital) | RENFE_05455 | 209m | 180s |

---

## 8. Resumen

| Ciudad | Operadores | Correspondencias |
|--------|------------|------------------|
| **Bilbao** | Metro + Euskotren + RENFE + Funicular | **8 pares** |
| San Sebastián | Solo Euskotren | 0 |
| Vitoria | Solo Euskotren (tren+tranvía) | 0 |

**Total:** 8 pares = 16 registros bidireccionales
