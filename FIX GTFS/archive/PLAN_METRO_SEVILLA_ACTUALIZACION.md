# Plan de Acción: Actualización Metro Sevilla desde NAP

**Fecha:** 2026-01-29
**Estado:** PENDIENTE REVISIÓN

---

## Resumen Ejecutivo

Comparar y sincronizar datos de Metro Sevilla entre el GTFS oficial del NAP y nuestra base de datos actual.

### Comparativa Actual

| Aspecto | GTFS NAP | BD Actual | Estado |
|---------|----------|-----------|--------|
| Paradas | 42 (21 estaciones + 21 plataformas) | 21 (solo estaciones) | ⚠️ Faltan plataformas |
| Rutas | 1 (L1) | 1 (L1) | ✅ OK |
| Calendarios | 40 (por temporada) | 44 (por temporada + base) | ✅ OK |
| Calendar_dates | 98 | 98 | ✅ OK |
| Trips | 104 (base con frequencies) | 3,340 (expandidos) | ✅ Mejor |
| Stop_times | 2,088 (base) | 70,140 (expandidos) | ✅ Mejor |
| Shapes | 0 (vacío en NAP) | 2 | ✅ OK |
| Servicio FESTIVO | No (usa DOMINGO) | No (usa DOMINGO) | ✅ OK |

---

## Análisis Detallado

### 1. Estructura de Calendarios

**NAP GTFS usa calendarios por temporada:**

| Temporada | Fechas | Laborable | Viernes | Sábado | Domingo |
|-----------|--------|-----------|---------|--------|---------|
| ENE_JUN | 01/01 - 15/06 | ✓ | ✓ | ✓ | ✓ |
| JUN_JUL | 16/06 - 15/07 | ✓ | ✓ | ✓ | ✓ |
| JUL_AGO | 16/07 - 31/08 | ✓ | ✓ | ✓ | ✓ |
| SEP_SEP | 01/09 - 15/09 | ✓ | ✓ | ✓ | ✓ |
| SEP_DIC | 16/09 - 31/12 | ✓ | ✓ | ✓ | ✓ |

**Total:** 5 temporadas × 4 tipos × 2 años = 40 calendarios

**BD actual:** Ya tiene estos 40 calendarios + 4 calendarios base (METRO_SEV_LABORABLE, etc.)

### 2. Excepciones de Calendario (Festivos)

**Festivos 2026 en el GTFS NAP:**

| Fecha | Festivo | Servicio aplicado |
|-------|---------|-------------------|
| 01/01 | Año Nuevo | DOMINGO |
| 05/01 | Víspera Reyes | SABADO |
| 06/01 | Reyes | DOMINGO |
| 29/03 | Domingo Ramos | SABADO (ya es domingo) |
| 30/03-03/04 | Semana Santa | VIERNES |
| 20-23/04 | Feria de Sevilla | VIERNES |
| 30/04 | Víspera 1 Mayo | VIERNES |
| 03/06 | Corpus (víspera) | VIERNES |
| 04/06 | Corpus | DOMINGO |
| 11/10 | Víspera Fiesta Nacional | SABADO |
| 12/10 | Fiesta Nacional | DOMINGO |
| 01/11 | Todos Santos | SABADO |
| 02/11 | Día siguiente | DOMINGO |
| 06/12 | Constitución | SABADO |
| 07/12 | Víspera Inmaculada | SABADO |
| 08/12 | Inmaculada | DOMINGO |
| 25/12 | Navidad | SABADO |

**Nota importante:** Metro Sevilla NO tiene servicio FESTIVO separado. Los festivos usan horario de DOMINGO o SABADO.

### 3. Sistema de Frequencies

El GTFS NAP usa `frequencies.txt` en lugar de trips individuales:

```
trip_id,start_time,end_time,headway_secs,exact_times
CE-OQ-LAB-INV1-2025,6:30:00,6:49:59,780    (cada 13 min)
CE-OQ-LAB-INV1-2025,6:50:00,7:19:59,480    (cada 8 min)
CE-OQ-LAB-INV1-2025,7:20:00,9:19:59,480    (cada 8 min)
...
```

**Nuestra BD:** Ya tiene los trips expandidos (3,340 trips con 70,140 stop_times), lo cual es MEJOR para RAPTOR porque permite calcular tiempos exactos.

### 4. Paradas (Stops)

**NAP tiene 42 stops:**
- 21 estaciones (location_type=1): L1-E1 a L1-E21
- 21 plataformas (location_type=0): L1-1 a L1-21

**BD actual tiene 21 stops:**
- Solo estaciones: METRO_SEV_L1_E1 a METRO_SEV_L1_E21

**Falta:** Las 21 plataformas con parent_station

---

## ❌ Lo que NO necesitamos actualizar

1. **Trips y stop_times:** Ya tenemos datos expandidos (mejor que frequencies)
2. **Calendarios:** Ya están sincronizados
3. **Calendar_dates:** Ya están los 98 festivos
4. **Shapes:** NAP no tiene shapes, nosotros sí (2 shapes)
5. **Ruta:** Ya existe METRO_SEV_L1_CE_OQ

---

## ✅ Lo que SÍ podríamos actualizar

### Opción A: No hacer nada (Recomendado)

Los datos actuales son **mejores** que los del NAP porque:
- Trips expandidos vs frequencies
- Tenemos shapes, NAP no
- Festivos ya sincronizados

### Opción B: Añadir plataformas (Opcional)

Añadir las 21 plataformas como hijos de las estaciones:

```sql
-- Ejemplo para Ciudad Expo
INSERT INTO gtfs_stops (id, name, lat, lon, location_type, parent_station_id)
VALUES ('METRO_SEV_L1_1', 'Ciudad Expo', 37.3490704814239, -6.052050356808763, 0, 'METRO_SEV_L1_E1');
```

**Beneficio:** Mejor modelado de la red
**Riesgo:** Requiere actualizar stop_times para usar plataformas

### Opción C: Verificar y sincronizar festivos 2026

Comparar los 98 calendar_dates actuales con los del NAP para asegurar que están correctos.

---

## Diferencias con Metro Málaga

| Característica | Metro Málaga | Metro Sevilla |
|----------------|--------------|---------------|
| Servicio FESTIVO | ✅ Trips específicos (453) | ❌ Usa DOMINGO |
| Vísperas nocturno | ✅ Hasta 01:30 | ❌ Horario normal |
| GTFS NAP | Trips individuales | Frequencies |
| Temporadas | No (año completo) | 5 por año |
| Shapes en NAP | ✅ 4 shapes | ❌ Vacío |

---

## Conclusión

**Metro Sevilla ya está bien configurado.** Los datos actuales son incluso mejores que los del NAP porque:

1. ✅ Trips expandidos (no frequencies)
2. ✅ Shapes disponibles
3. ✅ Festivos sincronizados
4. ✅ Calendarios por temporada

**Acción recomendada:** Ninguna actualización necesaria.

Si se desea mejorar, la única opción sería añadir las 21 plataformas como stops hijos, pero esto requiere migrar los stop_times.

---

## Archivos GTFS NAP descargados

Ubicación: `/tmp/gtfs_metro_sevilla/`

| Archivo | Registros |
|---------|-----------|
| agency.txt | 1 |
| calendar.txt | 40 |
| calendar_dates.txt | 98 |
| routes.txt | 1 |
| stops.txt | 42 |
| trips.txt | 104 |
| stop_times.txt | 2,088 |
| frequencies.txt | 594 |
| shapes.txt | 0 (vacío) |

**NAP File ID:** 1583
**Validez:** 2025-01-01 a 2026-12-31

---

## Checklist

- [x] Descargar GTFS del NAP (ID 1583)
- [x] Analizar estructura de calendarios
- [x] Comparar festivos
- [x] Comparar trips y stop_times
- [x] Verificar shapes
- [x] Documentar diferencias
- [ ] Decisión: ¿Actualizar algo?

---

## Historial

| Fecha | Cambio |
|-------|--------|
| 2026-01-29 | Creación del documento y análisis completo |
