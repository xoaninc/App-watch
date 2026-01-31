# Fix: Prefijo RENFE_ en datos RT y Scraping de Vías

**Fecha:** 2026-01-31
**Estado:** DESPLEGADO ✅

---

## Problema Detectado

### 1. Prefijo RENFE_ faltante en datos RT

Los datos de GTFS-RT se estaban guardando **sin el prefijo `RENFE_`** en los `stop_id`:

```sql
-- Antes (incorrecto)
stop_id: 54501   -- Victoria Kent sin prefijo

-- Después (correcto)
stop_id: RENFE_54501  -- Con prefijo para JOINs con datos estáticos
```

**Impacto:** Los datos RT no podían hacer JOIN con los datos estáticos (que sí tienen prefijo), rompiendo:
- Correlación de vías
- Predicción de plataformas desde histórico
- Alertas por parada

### 2. Vías faltantes para algunas estaciones

Renfe NO proporciona información de vías en el GTFS-RT para ciertas estaciones:
- **María Zambrano (54500)** - Nunca tiene vías
- **Pizarra (54406)** - Nunca tiene vías
- Otras estaciones del ramal C2 (Álora)

---

## APIs Descubiertas

### Endpoints de tiempo-real.renfe.com

| Endpoint | Datos | Uso |
|----------|-------|-----|
| `/renfe-visor/flota.json` | Posiciones de trenes con `via` y `nextVia` | Tiempo real |
| `/renfe-visor/flota_anterior.json` | Estado anterior (para comparar) | Debugging |
| `/renfe-json-cutter/write/salidas/estacion/{stopId}.json` | Salidas por estación con campo `via` | **Scraping complementario** |
| `/data/estaciones.geojson` | Catálogo de estaciones (sin vías) | Referencia |
| `/data/lineasnucleos.geojson` | Líneas y colores por núcleo | Referencia |

### Endpoint de salidas (el más útil)

```bash
curl "https://tiempo-real.renfe.com/renfe-json-cutter/write/salidas/estacion/54516.json"
```

Respuesta:
```json
{
  "estacion": {
    "stopId": "54516",
    "nombre": "Fuengirola",
    "salidas": [
      {
        "trenId": "23392",
        "tripId": "3227S23392C1",
        "linea": "C1",
        "destino": "54517",
        "destinoNombre": "Málaga-Centro Alameda",
        "horaSalida": "31-01-2026 22:19:00",
        "via": "2"  // ← VÍA DISPONIBLE
      }
    ]
  }
}
```

**Importante:** La vía solo aparece cuando el tren está **próximo a la estación**. Trenes lejanos no tienen vía asignada.

### Otras APIs útiles

| API | URL | Datos |
|-----|-----|-------|
| data.renfe.com | `https://data.renfe.com/api/3/action/datastore_search?resource_id=a2368cff-1562-4dde-8466-9635ea3a572a` | Catálogo de estaciones (código diferente: 54413 vs 54500 para MZ) |
| GTFS-RT oficial | `https://gtfsrt.renfe.com/vehicle_positions.json` | Feed JSON con plataforma en label: `C1-23574-PLATF.(2)` |

---

## Solución Implementada

### 1. Migración 040: Añadir prefijo RENFE_

**Archivo:** `alembic/versions/040_add_renfe_prefix_to_rt_data.py`

Actualiza todas las tablas RT:
- `gtfs_rt_vehicle_positions`
- `gtfs_rt_stop_time_updates`
- `gtfs_rt_platform_history`
- `gtfs_rt_alert_entities`

```sql
UPDATE gtfs_rt_vehicle_positions
SET stop_id = 'RENFE_' || stop_id
WHERE stop_id NOT LIKE 'RENFE_%'
  AND stop_id NOT LIKE 'FGC_%'
  AND stop_id NOT LIKE 'METRO_BILBAO_%'
  -- etc.
```

### 2. Scraping complementario del visor web

**Archivo:** `src/gtfs_bc/realtime/infrastructure/services/gtfs_rt_fetcher.py`

Nuevo método `_fetch_platforms_from_visor()`:

```python
def _fetch_platforms_from_visor(self) -> int:
    """Fetch platform data from Renfe's web visor for stations with missing platforms."""

    # 1. Buscar stop_time_updates sin vía
    stations_needing_platform = (
        self.db.query(StopTimeUpdateModel.stop_id)
        .filter(StopTimeUpdateModel.platform.is_(None))
        .distinct()
        .all()
    )

    # 2. Para cada estación, consultar el visor web
    for stop_id in stations_needing_platform:
        response = httpx.get(f"{visor_base_url}/{stop_code}.json")
        salidas = response.json().get("estacion", {}).get("salidas", [])

        for salida in salidas:
            via = salida.get("via")
            if via:
                # 3. Actualizar stop_time_update
                # 4. Guardar en platform_history para predicciones futuras
```

### Flujo actualizado de fetch_all_sync()

```
1. Cleanup datos antiguos
2. Fetch vehicle_positions (GTFS-RT)
3. Fetch trip_updates (GTFS-RT)
4. Fetch alerts (GTFS-RT)
5. Correlate platforms from vehicle_positions → stop_time_updates
6. ⭐ NUEVO: Fetch platforms from visor web
7. Predict platforms from history
```

---

## Estado de Vías por Estación (Málaga)

### Estaciones CON datos de vías

| Estación | Código | Observaciones | Patrón |
|----------|--------|---------------|--------|
| Fuengirola | 54516 | 6,365+ | Vía 1 siempre |
| Málaga Centro | 54517 | 6,306+ | Vía 1 (C1), Vía 1 (C2) |
| Victoria Kent | 54501 | 1,135+ | Vía 1 (60%), Vía 2 (40%) |
| Aeropuerto | 54505 | 2,401+ | Vía 1 (64%), Vía 2 (36%) |
| Torremolinos | 54509 | 2,609+ | Vía 1/2 alternando |
| Álora | 54405 | 1,163+ | Vía 1 siempre |

### Estaciones SIN datos de vías

| Estación | Código | Razón |
|----------|--------|-------|
| **María Zambrano** | 54500 | Renfe no publica vías para esta estación |
| **Pizarra** | 54406 | Renfe no publica vías |
| Aljaima | 54407 | Muy pocas observaciones (14) |
| Cártama | 54408 | Muy pocas observaciones (7) |

**Nota:** María Zambrano es una estación intermodal grande (AVE + Cercanías). Renfe usa código 54413 en data.renfe.com vs 54500 en GTFS-RT.

---

## Verificación Post-Despliegue

```bash
# Estado del scheduler
curl "https://redcercanias.com/api/v1/gtfs/realtime/scheduler/status"
{
  "running": true,
  "fetch_count": 3,
  "error_count": 0
}

# Vehículos con prefijo correcto
curl "https://redcercanias.com/api/v1/gtfs/realtime/vehicles?limit=5"
# stop_id: RENFE_54514 ✅

# Vías en Victoria Kent
curl "https://redcercanias.com/api/v1/gtfs/stops/RENFE_54501/departures"
# C1 → Fuengirola: vía 1 ✅
# C1 → Málaga Centro: vía 2 ✅
```

---

## Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `alembic/versions/040_add_renfe_prefix_to_rt_data.py` | Nueva migración |
| `src/gtfs_bc/realtime/infrastructure/services/gtfs_rt_fetcher.py` | Scraping visor web |
| `adapters/http/api/gtfs/routers/query_router.py` | Partial headsign matching |
| `scripts/import_gtfs_static.py` | Build headsigns from last stop |

---

## Notas Técnicas

### Por qué María Zambrano no tiene vías

1. **En el GTFS-RT oficial**: Renfe no incluye campo `platform` para esta estación
2. **En el visor web**: El endpoint de salidas tampoco devuelve `via` para María Zambrano
3. **Posible razón**: Es una estación terminal donde las vías de Cercanías (10/11) son fijas y no se gestionan dinámicamente

### Solución para María Zambrano

Para añadir vías manuales a María Zambrano, se puede insertar directamente en `platform_history`:

```sql
INSERT INTO gtfs_rt_platform_history
(stop_id, route_short_name, headsign, platform, count, observation_date)
VALUES
('RENFE_54500', 'C1', 'Fuengirola', '10', 100, CURRENT_DATE),
('RENFE_54500', 'C1', 'Málaga-Centro Alameda', '11', 100, CURRENT_DATE),
('RENFE_54500', 'C2', 'Álora', '10', 100, CURRENT_DATE),
('RENFE_54500', 'C2', 'Málaga-Centro Alameda', '11', 100, CURRENT_DATE);
```

### Códigos de estación duplicados

María Zambrano tiene diferentes códigos según la fuente:
- **54500** - GTFS-RT / tiempo-real.renfe.com (Cercanías)
- **54413** - data.renfe.com (catálogo general, incluye AVE)

---

## Commit

```
cfe7c45 fix(rt): Add RENFE_ prefix to RT data and visor web scraping for platforms
```
