# Renfe GTFS-RT Merge System

## Problema Original

Renfe proporciona datos GTFS-RT con `trip_id` que **no coinciden** con los `trip_id` del GTFS estático. Esto impedía:
- Mostrar headsigns correctos (destinos como "Parla", "Aranjuez")
- Aplicar tiempos RT a las salidas estáticas

## Solución Implementada

### 1. Merge por Línea + Tiempo (Enhanced)

En lugar de hacer match por `trip_id`, hacemos match por:
- **Línea**: Extraída del trip_id RT (ej: `RENFE_3027S23611C4` → `C4`)
- **Tiempo**: Ventana de ±5 minutos entre hora programada y hora RT
- **Start Time** (nuevo): Hora de inicio del viaje para desambiguar
- **Headsign** (nuevo): Dirección del tren para validación

```
Static: C4 sale a 08:51 (31860 segundos), start_time=08:15, headsign="Parla"
RT:     C4 llega a 08:53 (31980 segundos)
Diferencia: 2 min < 5 min → MATCH ✓
```

**Matching mejorado con múltiples candidatos:**
```
Si hay varios trips estáticos que podrían matchear:
1. Calcular el retraso implícito de cada candidato
2. Preferir candidatos con retraso más realista (menor)
3. Usar start_time para desambiguar trips similares
```

### 2. Cache de Matches Persistente

Una vez que un tren RT hace match con un tren estático, se guarda en cache:

```python
_rt_static_match_cache[rt_trip_id] = {
    'static_trip_id': '1013S27228C4a',
    'headsign': 'Parla',
    'route_color': '#2C2A86',
    'matched_at': datetime(...)
}
```

**Beneficio**: Si el tren se retrasa mucho (>5 min), el cache mantiene la asociación.

```
Escenario: Tren con 20 min de retraso

Sin cache:
  RT (08:50) vs Static (08:30) = 20 min > 5 min → NO MATCH
  Resultado: Se pierde el RT o muestra "Línea C4"

Con cache:
  RT (08:50) → Cache dice: "este RT = Static 1013S27228C4a"
  Resultado: Muestra "Parla" correctamente ✓
```

TTL del cache: 12 horas (se limpia automáticamente)

### 3. Fallback para RT sin Match

Si un RT no tiene match ni cache, se muestra igual con headsign genérico:

```
RT sin match → "Línea C4" (fallback)
```

Esto asegura que ningún tren RT se pierda.

## Flujo Completo

```
┌─────────────────────────────────────────────────────────────────┐
│                    REQUEST: /departures/RENFE_18002              │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Obtener datos RT para esta parada                            │
│    - Query: stop_time_updates WHERE stop_id IN (...)            │
│    - Indexar por línea: {C4: [...], C3: [...]}                  │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Obtener salidas estáticas                                    │
│    - Incluir últimos 5 min (para catch RT de trenes saliendo)   │
│    - Filtrar por calendario activo                              │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Para cada salida estática:                                   │
│    a) Buscar en cache: ¿algún RT ya matcheó con este trip?      │
│    b) Si no, intentar match por línea + tiempo (±5 min)         │
│    c) Si hay match → aplicar tiempo RT + cachear                │
│    d) Si no hay match → mantener tiempo estático                │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Añadir RT sin match (fallback)                               │
│    - RT que no matcheó con ningún estático                      │
│    - Usar headsign del cache si existe                          │
│    - Si no, usar "Línea X" como fallback                        │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Deduplicar y ordenar                                         │
│    a) Paso 1: Eliminar estáticos duplicados cuando hay RT       │
│       - Si un RT matchea con un slot de tiempo, eliminar otros  │
│         estáticos del mismo slot (buckets de 2 min)             │
│    b) Paso 2: Deduplicar por tiempo efectivo (gap mín 90s)      │
│    c) Filtrar salidas pasadas sin RT                            │
│    d) Ordenar por tiempo efectivo (RT o estático)               │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Devolver respuesta                                           │
│    - Headsigns correctos del GTFS estático                      │
│    - Tiempos RT cuando hay match                                │
│    - Tiempos estáticos cuando no hay RT                         │
└─────────────────────────────────────────────────────────────────┘
```

## Archivos Modificados

- `adapters/http/api/gtfs/routers/query_router.py`:
  - `_get_renfe_rt_by_line()`: Obtiene RT indexado por línea
  - `_match_static_to_rt()`: Match por línea + tiempo
  - `_get_cached_rt_match()`: Busca match en cache
  - `_cache_rt_match()`: Guarda match en cache
  - `get_stop_departures()`: Lógica principal de merge

## Ejemplo de Respuesta

```json
{
  "trip_id": "1013S27228C4a",
  "route_short_name": "C4a",
  "headsign": "Parla",              // ← Del GTFS estático
  "departure_time": "09:16:00",     // ← Hora programada
  "delay_seconds": 120,             // ← Retraso calculado
  "realtime_departure_time": "09:18:00",  // ← Hora RT
  "realtime_minutes_until": 2,      // ← Minutos hasta llegada RT
  "is_delayed": true
}
```

## Algoritmo de Matching Mejorado

Inspirado en OpenTripPlanner's `fuzzyTripMatching`, el algoritmo:

```python
def _match_static_to_rt(...):
    # 1. Filtrar candidatos por línea + ventana de tiempo (±5 min)
    candidates = [rt for rt in rt_by_line[line] if abs(rt_time - static_time) <= 300]

    # 2. Si solo hay un candidato, usarlo
    if len(candidates) == 1:
        return candidates[0]

    # 3. Si hay múltiples, desambiguar:
    #    - Usar start_seconds (hora inicio del viaje)
    #    - Calcular retraso implícito
    #    - Preferir el más realista (menor retraso absoluto)
    for c in candidates:
        c['implied_delay'] = c['rt_time'] - static_departure
        c['score'] = abs(c['implied_delay'])

    return sorted(candidates, key=lambda x: x['score'])[0]
```

**Ventaja vs sistema anterior:**
- Mejor precisión cuando hay múltiples trips en horarios similares
- Usa el contexto del viaje completo (start_time) no solo la parada actual

## Deduplicación Inteligente

### Problema
El GTFS estático de Renfe tiene múltiples `trip_id` para el mismo horario:
```
1013S75309C10  →  C10 Chamartín 09:27
1027S75309C10  →  C10 Chamartín 09:27  (mismo tren, diferente trip_id)
```

Cuando solo uno de estos trips matchea con RT (porque el RT usa un trip_id diferente),
podría aparecer duplicado: uno con RT y otro sin RT.

### Solución
Deduplicación en dos pasos:

1. **Paso 1**: Si hay un RT para un slot de tiempo (buckets de 2 min), eliminar
   todos los estáticos del mismo slot que NO tienen RT.

2. **Paso 2**: Deduplicación estándar por tiempo efectivo (gap mínimo 90s).

```
Antes (bug):
  C10 Chamartín 09:27 [sin RT]
  C10 Chamartín 09:27 [RT: 09:29]  ← Duplicado!

Después (fix):
  C10 Chamartín 09:27 [RT: 09:29]  ← Solo el que tiene RT
```

## Limitaciones

1. **Renfe RT solo da 1 parada por viaje**: El RT solo incluye la próxima parada, no todo el recorrido.

2. **Match inicial requiere ±5 min**: Si un tren empieza con >5 min de retraso desde el inicio, no hará match inicial (pero aparecerá con fallback).

3. **Cache en memoria**: Se pierde al reiniciar el servidor. Podría migrarse a Redis/BD si es necesario.

## Operadores Soportados

| Operador | RT Coverage | Match Method |
|----------|-------------|--------------|
| Renfe Cercanías | 1 parada/viaje | Línea + Tiempo + Cache |
| TMB Metro | Todas las paradas | Trip ID directo |
| Euskotren | 30-40 paradas/viaje | Trip ID directo |
| FGC | ~30 paradas/viaje | Trip ID directo |
