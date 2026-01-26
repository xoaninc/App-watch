# TODO - Tareas Pendientes

**Última actualización:** 2026-01-26 14:30

---

## Estado Actual

### Funcionando en Producción ✅

| Feature | Estado | Endpoint |
|---------|--------|----------|
| Platforms | ✅ | `GET /stops/{stop_id}/platforms` |
| Correspondences | ✅ | `GET /stops/{stop_id}/correspondences` |
| Shapes | ✅ COMPLETO | `GET /routes/{route_id}/shape` |

### Shapes - Estado por Red

| Red | Shapes | Puntos | Estado |
|-----|--------|--------|--------|
| TMB Metro Barcelona | 290 | 103,248 | ✅ Funciona |
| SFM Mallorca | 243 | 257,515 | ✅ Importado 2026-01-26 |
| Renfe Cercanías | 118 | 74,420 | ✅ Funciona |
| Euskotren | 115 | 60,886 | ✅ Funciona |
| Metro Ligero Madrid | 38 | 61,816 | ✅ Funciona |
| Metro Bilbao | 33 | 13,271 | ✅ Funciona |
| FGC | 42 | 11,591 | ✅ Funciona |
| Metrovalencia | 20 | 900 | ✅ Importado 2026-01-26 |
| TRAM Alicante | 12 | 2,719 | ✅ Importado 2026-01-26 |
| Metro Granada | 2 | 784 | ✅ Importado 2026-01-26 |
| Tranvía Murcia | 2 | 634 | ✅ Importado 2026-01-26 |
| Metro Málaga | 4 | 260 | ✅ Importado 2026-01-26 |
| Tranvía Zaragoza | 2 | 252 | ✅ Importado 2026-01-26 |
| Metro Tenerife | 4 | 132 | ✅ Importado 2026-01-26 |
| Metro Sevilla | 2 | 1,227 | ✅ Extraído de OSM 2026-01-26 |
| TRAM Barcelona | 12 | 5,136 | ✅ Extraído de OSM 2026-01-26 |

**Total en producción:** 882 shapes, 578,594 puntos

---

## Tareas Completadas (2026-01-26)

### ✅ Shapes de Metros Secundarios

Importados automáticamente desde NAP usando credenciales de `.env.local`:

| Red | NAP ID | Shapes | Puntos |
|-----|--------|--------|--------|
| Metro Málaga | 1296 | 4 | 260 |
| Metro Granada | 1370 | 2 | 784 |
| Metrovalencia | 967 | 20 | 900 |
| Tranvía Zaragoza | 1394 | 2 | 252 |
| Tranvía Murcia | 1371 | 2 | 634 |
| TRAM Alicante | 966 | 12 | 2,719 |
| SFM Mallorca | 1071 | 243 | 257,515 |
| Metro Tenerife | URL directa | 4 | 132 |

**Nota:** Metro Sevilla (NAP ID 1385, no 1583) tiene el archivo shapes.txt pero está VACÍO (solo header). Se extrajeron de OSM.

### ✅ Shapes de OSM (Metro Sevilla y TRAM Barcelona)

Extraídos desde OpenStreetMap usando Overpass API:

| Red | Shapes | Puntos | Fuente OSM |
|-----|--------|--------|------------|
| TRAM Barcelona | 12 | 5,136 | Relations T1-T6 (ida/vuelta) |
| Metro Sevilla | 2 | 1,227 | Relations L1 (ida/vuelta) |

**IDs de shapes OSM:**
- `TRAM_BCN_T1_4666995`, `TRAM_BCN_T1_4666996` (T1 ida/vuelta)
- `TRAM_BCN_T2_4666997`, `TRAM_BCN_T2_4666998` (T2 ida/vuelta)
- `TRAM_BCN_T3_4666999`, `TRAM_BCN_T3_4667000` (T3 ida/vuelta)
- `TRAM_BCN_T4_4665781`, `TRAM_BCN_T4_4665782` (T4 ida/vuelta)
- `TRAM_BCN_T5_4665783`, `TRAM_BCN_T5_4665784` (T5 ida/vuelta)
- `TRAM_BCN_T6_4665785`, `TRAM_BCN_T6_4665786` (T6 ida/vuelta)
- `METRO_SEV_L1_255088`, `METRO_SEV_L1_7781388` (L1 ida/vuelta)

### ✅ Correspondencias Barcelona (TMB ↔ FGC ↔ Rodalies)

Añadidas 22 correspondencias nuevas:

| Estación | Conexiones |
|----------|------------|
| Catalunya | TMB L1 ↔ FGC ↔ RENFE, TMB L3 ↔ FGC ↔ RENFE |
| Passeig de Gràcia | TMB L2/L4 ↔ RENFE, TMB L3 ↔ RENFE |
| Sants Estació | TMB L3 ↔ RENFE, TMB L5 ↔ RENFE |
| Arc de Triomf | TMB L1 ↔ RENFE |

**IDs usados:**
- Catalunya: TMB_METRO_1.126 (L1), TMB_METRO_1.326 (L3), FGC_PC, RENFE_78805
- Passeig de Gràcia: TMB_METRO_1.213 (L2/L4), TMB_METRO_1.327 (L3), TMB_METRO_1.425 (L4), RENFE_71802
- Sants: TMB_METRO_1.319 (L3), TMB_METRO_1.518 (L5), RENFE_71801
- Arc de Triomf: TMB_METRO_1.128 (L1), RENFE_78804

---

## Tareas Pendientes

### Todo completado ✅

No hay tareas pendientes de shapes o correspondencias.

### Mejoras opcionales (baja prioridad)

- [ ] Investigar API Valencia tiempo real (devuelve vacío)
- [x] ~~Mapear shapes OSM a route_ids existentes~~ ✅ Completado 2026-01-26

### ✅ Shapes OSM mapeados a rutas (2026-01-26)

Creadas rutas y trips para acceder a los shapes via endpoint estándar:

| Ruta | Endpoint | Puntos |
|------|----------|--------|
| `TRAM_BCN_T1` | `/routes/TRAM_BCN_T1/shape` | 405 |
| `TRAM_BCN_T2` | `/routes/TRAM_BCN_T2/shape` | 532 |
| `TRAM_BCN_T3` | `/routes/TRAM_BCN_T3/shape` | 478 |
| `TRAM_BCN_T4` | `/routes/TRAM_BCN_T4/shape` | 311 |
| `TRAM_BCN_T5` | `/routes/TRAM_BCN_T5/shape` | 436 |
| `TRAM_BCN_T6` | `/routes/TRAM_BCN_T6/shape` | 400 |
| `METRO_SEV_L1_CE_OQ` | `/routes/METRO_SEV_L1_CE_OQ/shape` | 1,227 |

---

## Resumen de Producción

### Correspondencias
| Fuente | Cantidad |
|--------|----------|
| manual | 82 |
| osm | 74 |
| proximity | 62 |
| **TOTAL** | **218** |

### Shapes
- 882 shapes
- 578,594 puntos

---

## Ejemplos de Uso de la API

### IDs Correctos (IMPORTANTE)

El compañero de la app debe usar los IDs **completos con prefijo**:

```bash
# ❌ INCORRECTO
curl ".../stops/79600/platforms"
curl ".../stops/TMB_232/correspondences"
curl ".../routes/METRO_1/shape"

# ✅ CORRECTO
curl ".../stops/RENFE_79600/platforms"
curl ".../stops/TMB_METRO_1.126/correspondences"
curl ".../routes/TMB_METRO_1.1.1/shape"
```

### Correspondencias Barcelona (NUEVAS)

```bash
# Catalunya - ahora incluye FGC y RENFE
curl "https://juanmacias.com/api/v1/gtfs/stops/TMB_METRO_1.126/correspondences"
# → FGC_PC, RENFE_78805, TMB_METRO_1.326

# Passeig de Gràcia - ahora incluye RENFE
curl "https://juanmacias.com/api/v1/gtfs/stops/TMB_METRO_1.327/correspondences"
# → RENFE_71802, TMB_METRO_1.213, TMB_METRO_1.425

# Sants - ahora incluye RENFE
curl "https://juanmacias.com/api/v1/gtfs/stops/TMB_METRO_1.518/correspondences"
# → RENFE_71801, TMB_METRO_1.319
```

### Shapes Nuevos (desde NAP)

```bash
# Metrovalencia
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_VAL_L1/shape"

# Metro Málaga
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_MAL_L1/shape"

# Metro Granada
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_GRA_L1/shape"

# Metro Tenerife (tranvía)
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_TEN_L1/shape"
```

### Shapes OSM (TRAM Barcelona y Metro Sevilla)

```bash
# TRAM Barcelona T1-T6
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T1/shape"
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T2/shape"
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T3/shape"
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T4/shape"
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T5/shape"
curl "https://redcercanias.com/api/v1/gtfs/routes/TRAM_BCN_T6/shape"

# Metro Sevilla L1
curl "https://redcercanias.com/api/v1/gtfs/routes/METRO_SEV_L1_CE_OQ/shape"
```
