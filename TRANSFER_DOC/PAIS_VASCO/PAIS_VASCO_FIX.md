# País Vasco - Plan de Solución

## Proceso

Ver [ESTRUCTURA_PROCESO.md](../ESTRUCTURA_PROCESO.md) para el proceso general.

## Estado Actual

| Paso | Estado | Archivo | Fecha |
|------|--------|---------|-------|
| 0. Limpiar datos erróneos | ✅ | `PAIS_VASCO_FIX.md` | 2026-01-31 |
| 1. Documentar problema | ✅ | `PAIS_VASCO_PROBLEM.md` | 2026-01-31 |
| 2. Análisis GTFS | ✅ | `PAIS_VASCO_PROBLEM.md` | 2026-01-31 |
| 3. Extracción OSM | ⏳ | `pais_vasco_extract_osm.py` | - |
| 4. Revisión manual | ⏳ | - | - |
| 5. Población tablas | ⏳ | `pais_vasco_multimodal_correspondences.py` | - |
| 6. Pruebas | ⏳ | - | - |
| 7. Producción | ⏳ | - | - |

---

## Operadores

| Operador | Estaciones | Andenes | transfers.txt |
|----------|------------|---------|---------------|
| Metro Bilbao | 42 | ~84 | ❌ No tiene |
| Euskotren | ~100 | ~200 | ✅ 13 (internos) |
| Funicular Artxanda | 2 | 2 | ❌ No tiene |
| RENFE Cercanías (Bilbao) | ~15 | ~30 | ✅ (general) |

---

## Cronología

### 2026-01-31: Paso 0 - Limpieza de datos erróneos ✅

**Datos eliminados:**
```sql
DELETE FROM stop_correspondence
WHERE source != 'gtfs'
  AND (from_stop_id LIKE 'METRO_BILBAO_%' OR to_stop_id LIKE 'METRO_BILBAO_%'
    OR from_stop_id LIKE 'EUSKOTREN_%' OR to_stop_id LIKE 'EUSKOTREN_%'
    OR from_stop_id LIKE 'FUNICULAR_%' OR to_stop_id LIKE 'FUNICULAR_%');
-- DELETE 12
```

### 2026-01-31: Paso 1-2 - Documentación y análisis GTFS ✅

Ver `PAIS_VASCO_PROBLEM.md` para el análisis completo.

**Resumen:**
- Metro Bilbao: NO tiene transfers.txt
- Euskotren: 13 transfers internos (cambio de andén)
- Funicular: NO tiene transfers.txt
- Ningún operador declara correspondencias multimodales

---

## Intercambiadores Identificados

### Bilbao Centro

| Intercambiador | Operadores | Distancia | Prioridad |
|----------------|------------|-----------|-----------|
| **Abando** | Metro L1/L2 + Euskotren + RENFE | 86-167m | 🔴 Alta |
| **Casco Viejo** | Metro L1/L2 + Euskotren | 125m | 🔴 Alta |
| **San Mamés** | Metro L1/L2 + Euskotren | 144m | 🔴 Alta |

### Otros

| Intercambiador | Operadores | Distancia | Prioridad |
|----------------|------------|-----------|-----------|
| **Matiko** | Funicular Artxanda + Euskotren | 90m | 🔴 Alta |
| **Basurto** | Euskotren + RENFE | 209m | 🟡 Media |

---

## Correspondencias a Crear

### Metro Bilbao ↔ Euskotren (6 pares, 12 registros)

| Metro | Euskotren | Distancia | Tiempo |
|-------|-----------|-----------|--------|
| METRO_BILBAO_7 (Abando) | EUSKOTREN_...1471 (Abando) | 86m | 90s |
| METRO_BILBAO_6 (Casco Viejo) | EUSKOTREN_...2577 (Casco Viejo) | 125m | 120s |
| METRO_BILBAO_10 (San Mamés) | EUSKOTREN_...1470 (San Mamés) | 144m | 150s |

### Metro Bilbao ↔ RENFE (1 par, 2 registros)

| Metro | RENFE | Distancia | Tiempo |
|-------|-------|-----------|--------|
| METRO_BILBAO_7 (Abando) | RENFE_05451 (Concordia) | 167m | 180s |

### Euskotren ↔ RENFE (2 pares, 4 registros)

| Euskotren | RENFE | Distancia | Tiempo |
|-----------|-------|-----------|--------|
| EUSKOTREN_...1471 (Abando) | RENFE_05451 (Concordia) | 98m | 120s |
| EUSKOTREN_...1472 (Hospital) | RENFE_05455 (Basurto) | 209m | 180s |

### Funicular ↔ Euskotren (1 par, 2 registros)

| Funicular | Euskotren | Distancia | Tiempo |
|-----------|-----------|-----------|--------|
| FUNICULAR_ARTXANDA_12 | EUSKOTREN_...2597 (Matiko) | 90m | 90s |

**Total estimado:** 10 pares = 20 registros bidireccionales

---

## Archivos del Proyecto

```
TRANSFER_DOC/PAIS_VASCO/
├── PAIS_VASCO_PROBLEM.md              ✅ Documentación del problema
├── PAIS_VASCO_FIX.md                  ✅ Este archivo
├── PAIS_VASCO_OLD.md                  📦 Documento antiguo (referencia)
├── pais_vasco_extract_osm.py          ⏳ Script extracción OSM
└── pais_vasco_multimodal_correspondences.py  ⏳ Script correspondencias
```

---

## Próximos Pasos

1. ⏳ **Extracción OSM** - Verificar intercambiadores con datos de OpenStreetMap
2. ⏳ **Revisión manual** - Usuario confirma correspondencias
3. ⏳ **Crear script** - `pais_vasco_multimodal_correspondences.py`
4. ⏳ **Ejecutar local** - Probar correspondencias
5. ⏳ **Producción** - Desplegar a servidor
