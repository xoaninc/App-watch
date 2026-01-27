# Preguntas de Bloqueo - RAPTOR In-Memory

**Fecha:** 2026-01-28
**Revisado por:** Experto externo

---

## Pregunta 1: Stop Times de Frequencies (Metro Madrid/Sevilla)

### Pregunta
> "Se ha ejecutado ya el script para convertir frecuencias a stop_times en la base de datos?"

### Respuesta: SI - RESUELTO

Los scripts de generacion YA se han ejecutado. La base de datos tiene stop_times para todas las redes:

| Red | Trips con stop_times |
|-----|---------------------|
| RENFE | 130,616 |
| METRO_MAD | 19,658 |
| TMB_METRO | 15,630 |
| FGC | 15,495 |
| EUSKOTREN | 11,088 |
| METRO_BIL | 10,620 |
| METRO_GR | 5,693 |
| METRO_MAL | 4,681 |
| METRO_SEV | 3,340 |
| ML (Metro Ligero) | 3,001 |
| SFM | 808 |
| METRO_VALENCIA | ~10,000 (fragmentado) |
| METRO_TENERIFE | 12 |

**Total trips con stop_times:** ~260,000

### Scripts ejecutados
- `scripts/generate_metro_madrid_trips.py`
- `scripts/generate_metro_madrid_full_trips.py`
- `scripts/generate_metro_sevilla_trips.py`
- `scripts/generate_network_trips.py` (para ML, TMB, FGC, etc.)

### Semaforo: VERDE

---

## Pregunta 2: Logica de Patterns

### Pregunta
> "El gtfs_store.py nuevo esta simplificando demasiado. Tienes que copiar la logica de _build_route_patterns_from_trips."

### Respuesta: CONFIRMADO - Se implementara en Hora 1

El `gtfs_store.py` actual agrupa trips por `route_id`, no por patterns (secuencias unicas de paradas).

**Problema:** Si metes trips ida/vuelta en la misma "bolsa", el algoritmo devolvera rutas imposibles (teletransportacion).

**Solucion:** Implementar agrupacion por patterns en `_do_load()`:

```python
# Agrupar trips por secuencia exacta de paradas
temp_patterns = defaultdict(list)
for trip_id, stops_data in self.stop_times_by_trip.items():
    stop_sequence = tuple(s[0] for s in stops_data)
    route_id = self.trips_info[trip_id][0]
    temp_patterns[(route_id, stop_sequence)].append(trip_id)
```

### Semaforo: AMARILLO (pendiente implementacion)

---

## Pregunta 3: Memoria en Produccion

### Pregunta
> "Nuestro contenedor/servidor en produccion tiene al menos 1GB de RAM libre garantizada?"

### Respuesta: SI - SUFICIENTE

```
Servidor: juanmacias.com (root@juanmacias.com)

RAM Total:      3.7 GB
RAM Usada:      1.7 GB
RAM Disponible: 2.0 GB
Swap:           0 B
```

**Plan estima:** ~300-400 MB para GTFS en memoria

**Margen disponible:** 2.0 GB - 0.4 GB = 1.6 GB de sobra

No se necesita optimizacion con `__slots__` o arrays de C por ahora.

### Semaforo: VERDE

---

## Pregunta 4: Metro Valencia

### Pregunta
> "Y el Metro de Valencia todo bien?"

### Respuesta: SI - YA TIENE PATTERNS

Metro Valencia tiene una estructura especial en su GTFS: los route_id YA incluyen la direccion.

**Datos:**
| Metrica | Valor |
|---------|-------|
| Routes (separadas por direccion) | 114 |
| Trips con stop_times | 11,230 |

**Estructura de route_id:**
```
METRO_VALENCIA_V5-182-123  = Linea 5, de parada 182 a 123
METRO_VALENCIA_V5-123-182  = Linea 5, de parada 123 a 182 (opuesta)
METRO_VALENCIA_V10-190-197 = Linea 10, de 190 a 197
METRO_VALENCIA_V10-197-190 = Linea 10, de 197 a 190 (opuesta)
```

**Comparacion con otras redes:**

| Red | Patterns en route_id | Necesita separar en codigo |
|-----|---------------------|---------------------------|
| Metro Valencia | SI (V5-182-123) | NO |
| Metro Madrid | NO (METRO_1) | SI |
| Metro Sevilla | NO (METRO_SEV_L1) | SI |
| RENFE | NO (RENFE_C1) | SI |
| TMB Metro | NO (TMB_METRO_L1) | SI |

### Semaforo: VERDE

---

## Resumen Final

| Bloqueo | Estado | Accion |
|---------|--------|--------|
| Stop Times frequencies | VERDE | Ninguna - ya resuelto |
| Logica Patterns | AMARILLO | Implementar en Hora 1 |
| Memoria produccion | VERDE | Ninguna - suficiente |
| Metro Valencia | VERDE | Ya tiene patterns en route_id |

**Conclusion:** Se puede proceder con la implementacion. Solo hay que asegurar la logica de patterns en Hora 1 (principalmente para RENFE, Metro Madrid, Metro Sevilla, TMB).
