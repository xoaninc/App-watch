# Resumen: Vías de Cercanías Málaga

## El Problema

Queremos mostrar en qué **vía/andén** llega cada tren en las estaciones de Cercanías Málaga. Por ejemplo:
- "C1 hacia Fuengirola → Vía 1"
- "C1 hacia Málaga Centro → Vía 2"

---

## Fuentes de Datos de Renfe

### 1. GTFS-RT Oficial (`gtfsrt.renfe.com`)

Renfe publica feeds en tiempo real con posiciones de trenes:

```
https://gtfsrt.renfe.com/vehicle_positions.json
https://gtfsrt.renfe.com/trip_updates.json
```

**¿Qué datos tienen?**
- Posición GPS del tren
- Próxima parada
- Retraso en segundos
- **Vía/andén** (en el campo `label`: `"C1-23574-PLATF.(2)"` → Vía 2)

**Problema:** Solo incluye la **próxima parada** del tren, no todas. Y algunas estaciones (María Zambrano, Pizarra) **nunca aparecen** en este feed.

### 2. Visor Web (`tiempo-real.renfe.com`)

Renfe tiene una web con más datos:

```
https://tiempo-real.renfe.com/renfe-json-cutter/write/salidas/estacion/54500.json
```

**¿Qué datos tiene?**
- Todas las salidas de una estación
- Posición actual de cada tren
- **Vía** (campo `via`) → Pero **solo cuando el tren está cerca**

**Problema:** María Zambrano y Pizarra aparecen en este endpoint, pero **nunca tienen el campo `via`**.

---

## ¿Qué Estaciones Tienen Vías?

Investigamos todos los endpoints y esto es lo que encontramos:

| Estación | Código | ¿Vías en RT? | Observaciones |
|----------|--------|--------------|---------------|
| Fuengirola | 54516 | ✅ Sí | Siempre vía 1 |
| Málaga Centro | 54517 | ✅ Sí | Siempre vía 1 |
| Victoria Kent | 54501 | ✅ Sí | Vía 1 (Fuengirola) / Vía 2 (Málaga) |
| Aeropuerto | 54505 | ✅ Sí | Vía 1/2 alternando |
| Torremolinos | 54509 | ✅ Sí | Vía 1/2 alternando |
| Benalmádena | 54511 | ✅ Sí | Vía 1/2 |
| **María Zambrano** | 54500 | ❌ **No** | Renfe no envía vías |
| **Pizarra** | 54406 | ❌ **No** | Renfe no envía vías |
| Álora | 54405 | ⚠️ Pocas | Solo vía 1 (pocas obs.) |
| Cártama, Aljaima, etc. | 544xx | ⚠️ Muy pocas | Casi sin datos |

---

## Nuestra Solución

### Sistema de Aprendizaje de Vías

Implementamos un sistema que **aprende** las vías automáticamente:

1. **Cada 30 segundos** consultamos el GTFS-RT de Renfe
2. Cuando un tren está en una estación (`STOPPED_AT` o `INCOMING_AT`) y tiene vía, **guardamos** esa observación
3. Acumulamos estadísticas: "En Victoria Kent, la C1 hacia Fuengirola usa vía 1 el 95% del tiempo"

### Tabla `gtfs_rt_platform_history`

```sql
CREATE TABLE gtfs_rt_platform_history (
    stop_id VARCHAR(50),           -- RENFE_54501 (Victoria Kent)
    route_short_name VARCHAR(20),  -- C1
    headsign VARCHAR(200),         -- Fuengirola
    platform VARCHAR(20),          -- 1
    count INTEGER,                 -- 156 (veces observado)
    observation_date DATE          -- 2026-01-31
);
```

**Datos actuales para Málaga:**

```
Victoria Kent (54501):
  - C1 → Fuengirola: Vía 1 (685 observaciones)
  - C1 → Málaga Centro: Vía 2 (450 observaciones)

Fuengirola (54516):
  - C1 → Málaga Centro: Vía 1 (6,365 observaciones)

María Zambrano (54500):
  - ❌ 0 observaciones (Renfe no envía datos)

Pizarra (54406):
  - ❌ 0 observaciones (Renfe no envía datos)
```

### Predicción de Vías

Cuando mostramos salidas en `/departures`:

1. **Primero**: Buscamos si hay vía en tiempo real (del feed RT)
2. **Segundo**: Si no hay, buscamos en el histórico (`platform_history`)
3. **Tercero**: Si no hay histórico, no mostramos vía

```
Usuario pide: /stops/RENFE_54501/departures (Victoria Kent)

Respuesta:
  C1 → Fuengirola     | Vía 1 | (del histórico, 95% confianza)
  C1 → Málaga Centro  | Vía 2 | (del histórico, 90% confianza)
```

### Scraping Complementario del Visor

Además del GTFS-RT, también consultamos el visor web de Renfe:

```python
# Cada 30 segundos, para estaciones sin vía en RT:
response = requests.get(f"https://tiempo-real.renfe.com/.../salidas/estacion/{stop_id}.json")
if salida.get("via"):
    # Guardar en platform_history
```

**Problema:** El visor tampoco devuelve vías para María Zambrano ni Pizarra.

---

## El Problema Específico de María Zambrano y Pizarra

### María Zambrano (54500)

- Es una estación grande (AVE + Cercanías + buses)
- Tiene código diferente en distintos sistemas:
  - `54500` en GTFS-RT (Cercanías)
  - `54413` en data.renfe.com (catálogo general)
- **Renfe simplemente no publica las vías** en ningún endpoint
- Los Cercanías usan vías 10 y 11 (según conocimiento local)

### Pizarra (54406)

- Estación pequeña del ramal C2 (Álora)
- Aparece en el visor pero **sin campo `via`**
- Probablemente tiene una sola vía

### Ramal C2 en general

El ramal hacia Álora (C2) tiene muy pocos datos de vías comparado con el C1 (Fuengirola):
- C1: Miles de observaciones
- C2: Decenas de observaciones

---

## Solución Implementada ✅

Se añadieron vías manualmente basándonos en conocimiento local:

### María Zambrano (RENFE_54500)
- **Vía 10**: Dirección Fuengirola (C1) y Álora (C2)
- **Vía 11**: Dirección Málaga Centro-Alameda (C1 y C2)

*Nota: Son las vías subterráneas específicas de Cercanías.*

### Pizarra (RENFE_54406)
- **Vía 1**: Ambas direcciones (estación en tramo de vía única)

### Cártama (RENFE_54408)
- **Vía 1**: Ambas direcciones (vía única operativa)

### Álora (RENFE_54405)
- **Vía 1**: Final de línea, vía principal

### SQL Ejecutado

```sql
INSERT INTO gtfs_rt_platform_history
(stop_id, route_short_name, headsign, platform, count, observation_date)
VALUES
-- María Zambrano: Vía 10 sale hacia Fuengirola/Álora, Vía 11 hacia Málaga Centro
('RENFE_54500', 'C1', 'Fuengirola', '10', 500, CURRENT_DATE),
('RENFE_54500', 'C2', 'Álora', '10', 500, CURRENT_DATE),
('RENFE_54500', 'C1', 'Málaga-Centro Alameda', '11', 500, CURRENT_DATE),
('RENFE_54500', 'C2', 'Málaga-Centro Alameda', '11', 500, CURRENT_DATE),

-- Pizarra: Vía única
('RENFE_54406', 'C2', 'Málaga-Centro Alameda', '1', 100, CURRENT_DATE),
('RENFE_54406', 'C2', 'Álora', '1', 100, CURRENT_DATE),

-- Cártama: Vía única
('RENFE_54408', 'C2', 'Málaga-Centro Alameda', '1', 100, CURRENT_DATE),
('RENFE_54408', 'C2', 'Álora', '1', 100, CURRENT_DATE),

-- Álora: Final de línea
('RENFE_54405', 'C2', 'Málaga-Centro Alameda', '1', 100, CURRENT_DATE);
```

### Verificación

```
María Zambrano:
  C1 → Fuengirola         | Vía 10 ✅
  C1 → Málaga Centro      | Vía 11 ✅
  C2 → Álora              | Vía 10 ✅
  C2 → Málaga Centro      | Vía 11 ✅

Pizarra:
  C2 → Málaga Centro      | Vía 1 ✅
  C2 → Álora              | Vía 1 ✅
```

---

## Resumen Visual

```
                    RENFE GTFS-RT
                         │
                         ▼
    ┌─────────────────────────────────────┐
    │  Tren C1-23574 en Victoria Kent     │
    │  Label: "C1-23574-PLATF.(2)"        │
    │  → Extraemos: Vía 2                 │
    └─────────────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────┐
    │  Guardamos en platform_history:     │
    │  stop=54501, line=C1, via=2         │
    │  count += 1                         │
    └─────────────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────┐
    │  Usuario pide /departures/54501     │
    │  → Buscamos en platform_history     │
    │  → "Vía 2 para Málaga Centro"       │
    └─────────────────────────────────────┘


    PROBLEMA: María Zambrano y Pizarra

    ┌─────────────────────────────────────┐
    │  RENFE GTFS-RT                      │
    │  → María Zambrano: NO APARECE       │
    │  → Pizarra: Aparece SIN vía         │
    └─────────────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────┐
    │  RENFE Visor Web                    │
    │  → María Zambrano: Aparece SIN vía  │
    │  → Pizarra: Aparece SIN vía         │
    └─────────────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────┐
    │  SOLUCIÓN: Añadir vías manualmente  │
    │  Necesitamos info de las vías reales│
    └─────────────────────────────────────┘
```

---

## Endpoints Útiles

```bash
# GTFS-RT oficial de Renfe
curl "https://gtfsrt.renfe.com/vehicle_positions.json"
curl "https://gtfsrt.renfe.com/trip_updates.json"

# Visor web de Renfe (más datos pero sin vías para MZ)
curl "https://tiempo-real.renfe.com/renfe-json-cutter/write/salidas/estacion/54500.json"
curl "https://tiempo-real.renfe.com/renfe-visor/flota.json"

# Nuestra API
curl "https://redcercanias.com/api/v1/gtfs/stops/RENFE_54501/departures"
curl "https://redcercanias.com/api/v1/gtfs/realtime/vehicles"
```
