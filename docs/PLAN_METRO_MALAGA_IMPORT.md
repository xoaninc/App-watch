# Plan de Acción: Importación Completa Metro Málaga

**Fecha:** 2026-01-29
**Estado:** APROBADO

---

## Resumen Ejecutivo

Importar el GTFS completo de Metro Málaga con **5 tipos de servicio diferentes** según el día:

| Servicio | Días | Primer tren | Último tren | Trips |
|----------|------|-------------|-------------|-------|
| LABORABLE | Lunes-Jueves | 06:30 | 23:00 | 1,208 |
| VIERNES | Viernes + **Vísperas festivo** | 06:30 | **01:30** | 1,296 |
| SABADO | Sábado | 07:00 | **01:30** | 916 |
| DOMINGO | Domingo | 07:00 | 23:00 | 808 |
| FESTIVO | Festivos | 07:00 | 23:00 | **453** (reducido) |

**Nota:** Las vísperas de festivo usan horario de VIERNES (servicio nocturno hasta 01:30)

---

## Datos a Importar

| Archivo | Registros | Acción |
|---------|-----------|--------|
| trips.txt | 4,682 | Importar con mapeo IDs |
| stop_times.txt | 48,945 | Importar con mapeo IDs |
| shapes.txt | 260 puntos | Importar 4 shapes |
| calendar_dates.txt | 67 | Convertir a calendar + excepciones |

---

## Paso 1: Crear Services en gtfs_calendar

Crear 5 registros en `gtfs_calendar`:

```sql
-- Laborables (Lunes a Jueves)
INSERT INTO gtfs_calendar (id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
VALUES ('METRO_MALAGA_LABORABLE', true, true, true, true, false, false, false, '2026-01-01', '2026-12-31');

-- Viernes
INSERT INTO gtfs_calendar (id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
VALUES ('METRO_MALAGA_VIERNES', false, false, false, false, true, false, false, '2026-01-01', '2026-12-31');

-- Sábado
INSERT INTO gtfs_calendar (id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
VALUES ('METRO_MALAGA_SABADO', false, false, false, false, false, true, false, '2026-01-01', '2026-12-31');

-- Domingo
INSERT INTO gtfs_calendar (id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
VALUES ('METRO_MALAGA_DOMINGO', false, false, false, false, false, false, true, '2026-01-01', '2026-12-31');

-- Festivos (sin días fijos, se activa por calendar_dates)
INSERT INTO gtfs_calendar (id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
VALUES ('METRO_MALAGA_FESTIVO', false, false, false, false, false, false, false, '2026-01-01', '2026-12-31');
```

---

## Paso 2: Importar Festivos en gtfs_calendar_dates

Los festivos activan METRO_MALAGA_FESTIVO y desactivan el servicio normal del día.

### Festivos de Málaga 2026

| Fecha | Día semana | Festivo |
|-------|------------|---------|
| 01/01 | Miércoles | Año Nuevo |
| 06/01 | Lunes | Reyes |
| 28/02 | Sábado | Día de Andalucía |
| 02/04 | Jueves | Jueves Santo |
| 03/04 | Viernes | Viernes Santo |
| 01/05 | Viernes | Día del Trabajo |
| 15/08 | Sábado | Asunción |
| 08/09 | Martes | Virgen de la Victoria (local) |
| 12/10 | Lunes | Fiesta Nacional |
| 01/11 | Domingo | Todos los Santos |
| 06/12 | Domingo | Constitución |
| 08/12 | Martes | Inmaculada |
| 25/12 | Viernes | Navidad |

### SQL para festivos

```sql
-- Para cada festivo: añadir FESTIVO y quitar el servicio del día normal

-- 1 Enero (Miércoles - quitar LABORABLE)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-01-01', 1),
('METRO_MALAGA_LABORABLE', '2026-01-01', 2);

-- 6 Enero (Lunes - quitar LABORABLE)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-01-06', 1),
('METRO_MALAGA_LABORABLE', '2026-01-06', 2);

-- 28 Febrero (Sábado - quitar SABADO)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-02-28', 1),
('METRO_MALAGA_SABADO', '2026-02-28', 2);

-- 2 Abril (Jueves - quitar LABORABLE)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-04-02', 1),
('METRO_MALAGA_LABORABLE', '2026-04-02', 2);

-- 3 Abril (Viernes - quitar VIERNES)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-04-03', 1),
('METRO_MALAGA_VIERNES', '2026-04-03', 2);

-- 1 Mayo (Viernes - quitar VIERNES)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-05-01', 1),
('METRO_MALAGA_VIERNES', '2026-05-01', 2);

-- 15 Agosto (Sábado - quitar SABADO)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-08-15', 1),
('METRO_MALAGA_SABADO', '2026-08-15', 2);

-- 8 Septiembre (Martes - quitar LABORABLE)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-09-08', 1),
('METRO_MALAGA_LABORABLE', '2026-09-08', 2);

-- 12 Octubre (Lunes - quitar LABORABLE)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-10-12', 1),
('METRO_MALAGA_LABORABLE', '2026-10-12', 2);

-- 1 Noviembre (Domingo - quitar DOMINGO)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-11-01', 1),
('METRO_MALAGA_DOMINGO', '2026-11-01', 2);

-- 6 Diciembre (Domingo - quitar DOMINGO)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-12-06', 1),
('METRO_MALAGA_DOMINGO', '2026-12-06', 2);

-- 8 Diciembre (Martes - quitar LABORABLE)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-12-08', 1),
('METRO_MALAGA_LABORABLE', '2026-12-08', 2);

-- 25 Diciembre (Viernes - quitar VIERNES)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_FESTIVO', '2026-12-25', 1),
('METRO_MALAGA_VIERNES', '2026-12-25', 2);
```

**Total:** 13 festivos × 2 operaciones = 26 registros en calendar_dates

---

### Vísperas de Festivo (servicio nocturno hasta 01:30)

Las vísperas usan horario de VIERNES para tener servicio nocturno:

| Víspera | Día semana | Festivo siguiente |
|---------|------------|-------------------|
| 31/12/2025 | Miércoles | Año Nuevo |
| 05/01 | Lunes | Reyes |
| 27/02 | Viernes | Día de Andalucía (ya es viernes) |
| 01/04 | Miércoles | Jueves Santo |
| 02/04 | Jueves | Viernes Santo |
| 30/04 | Jueves | Día del Trabajo |
| 14/08 | Viernes | Asunción (ya es viernes) |
| 07/09 | Lunes | Virgen de la Victoria |
| 11/10 | Domingo | Fiesta Nacional |
| 31/10 | Sábado | Todos los Santos (ya es sábado) |
| 05/12 | Sábado | Constitución (ya es sábado) |
| 07/12 | Lunes | Inmaculada |
| 24/12 | Jueves | Navidad |

**Nota:** Si la víspera ya es viernes o sábado, no hace falta cambiar nada (ya tiene servicio nocturno).

### SQL para vísperas

```sql
-- Vísperas que NO son viernes ni sábado (necesitan activar horario nocturno)

-- 31 Dic 2025 (Miércoles - víspera Año Nuevo) - OJO: 2025!
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_VIERNES', '2025-12-31', 1),
('METRO_MALAGA_LABORABLE', '2025-12-31', 2);

-- 5 Enero (Lunes - víspera Reyes)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_VIERNES', '2026-01-05', 1),
('METRO_MALAGA_LABORABLE', '2026-01-05', 2);

-- 1 Abril (Miércoles - víspera Jueves Santo)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_VIERNES', '2026-04-01', 1),
('METRO_MALAGA_LABORABLE', '2026-04-01', 2);

-- 2 Abril (Jueves - víspera Viernes Santo)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_VIERNES', '2026-04-02', 1),
('METRO_MALAGA_LABORABLE', '2026-04-02', 2);

-- 30 Abril (Jueves - víspera 1 Mayo)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_VIERNES', '2026-04-30', 1),
('METRO_MALAGA_LABORABLE', '2026-04-30', 2);

-- 7 Septiembre (Lunes - víspera Virgen Victoria)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_VIERNES', '2026-09-07', 1),
('METRO_MALAGA_LABORABLE', '2026-09-07', 2);

-- 11 Octubre (Domingo - víspera Fiesta Nacional)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_VIERNES', '2026-10-11', 1),
('METRO_MALAGA_DOMINGO', '2026-10-11', 2);

-- 7 Diciembre (Lunes - víspera Inmaculada)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_VIERNES', '2026-12-07', 1),
('METRO_MALAGA_LABORABLE', '2026-12-07', 2);

-- 24 Diciembre (Jueves - víspera Navidad)
INSERT INTO gtfs_calendar_dates (service_id, date, exception_type) VALUES
('METRO_MALAGA_VIERNES', '2026-12-24', 1),
('METRO_MALAGA_LABORABLE', '2026-12-24', 2);
```

**Total vísperas:** 9 vísperas × 2 operaciones = 18 registros adicionales

---

## Paso 3: Importar Trips

Mapeo de service_id del GTFS a nuestra BD:

| GTFS service_id | BD service_id |
|-----------------|---------------|
| M01_* | METRO_MALAGA_LABORABLE |
| M02_* | METRO_MALAGA_VIERNES |
| M03_* | METRO_MALAGA_SABADO |
| M04_* | METRO_MALAGA_DOMINGO |
| M84_* | METRO_MALAGA_FESTIVO |

Mapeo de route_id:

| GTFS | BD |
|------|-----|
| 1 | METRO_MALAGA_1 |
| 2 | METRO_MALAGA_2 |

Mapeo de trip_id: `METRO_MALAGA_` + trip_id original

---

## Paso 4: Importar Stop Times

Mapeo de stop_id:

| GTFS | BD |
|------|-----|
| TCH | METRO_MALAGA_TCH |
| PRF | METRO_MALAGA_PRF |
| PC1 | METRO_MALAGA_PC1 |
| ... | METRO_MALAGA_... |

---

## Paso 5: Importar Shapes

| GTFS shape_id | BD shape_id | Puntos |
|---------------|-------------|--------|
| L1V1 | METRO_MALAGA_L1_DIR1 | ~65 |
| L1V2 | METRO_MALAGA_L1_DIR2 | ~65 |
| L2V1 | METRO_MALAGA_L2_DIR1 | ~65 |
| L2V2 | METRO_MALAGA_L2_DIR2 | ~65 |

Asignar shapes a trips según direction_id:
- direction_id=0 → _DIR1
- direction_id=1 → _DIR2

---

## Paso 6: Verificar RAPTOR

El sistema RAPTOR usa `gtfs_store.get_active_services(date)` que:
1. Consulta `gtfs_calendar` para el día de la semana
2. Consulta `gtfs_calendar_dates` para excepciones (festivos)
3. Devuelve los service_ids activos

**Verificar que funciona:**
```python
# Para un lunes normal
active = store.get_active_services(date(2026, 2, 2))  # Lunes
# Debe devolver: {'METRO_MALAGA_LABORABLE'}

# Para el festivo
active = store.get_active_services(date(2026, 2, 8))  # Domingo festivo
# Debe devolver: {'METRO_MALAGA_FESTIVO'} (NO 'METRO_MALAGA_DOMINGO')
```

---

## Script: import_metro_malaga_gtfs.py

```python
#!/usr/bin/env python3
"""Import Metro Málaga GTFS data."""

# Estructura del script:
# 1. Leer archivos GTFS de data/gtfs_metro_malaga/
# 2. Crear calendarios (5 services)
# 3. Importar calendar_dates (festivos)
# 4. Importar trips (4,682) con mapeo de IDs
# 5. Importar stop_times (48,945) con mapeo de IDs
# 6. Importar shapes (4)
# 7. Actualizar trips con shape_id
```

---

## Verificación Post-Importación

```sql
-- 1. Calendarios creados
SELECT * FROM gtfs_calendar WHERE id LIKE 'METRO_MALAGA%';
-- Esperado: 5 registros

-- 2. Trips importados
SELECT service_id, COUNT(*) FROM gtfs_trips
WHERE route_id LIKE 'METRO_MALAGA%'
GROUP BY service_id;
-- Esperado: 5 services con trips

-- 3. Stop times importados
SELECT COUNT(*) FROM gtfs_stop_times st
JOIN gtfs_trips t ON st.trip_id = t.id
WHERE t.route_id LIKE 'METRO_MALAGA%';
-- Esperado: 48,945

-- 4. Shapes importados
SELECT shape_id, COUNT(*) FROM gtfs_shape_points
WHERE shape_id LIKE 'METRO_MALAGA%'
GROUP BY shape_id;
-- Esperado: 4 shapes
```

---

## Test de Routing

```bash
# Ruta L1 un lunes a las 08:00
curl "https://juanmacias.com/api/v1/route-planner?\
origin=METRO_MALAGA_TCH&dest=METRO_MALAGA_ATZ&time=08:00&date=2026-02-02"

# Ruta L1 un viernes a las 01:00 (servicio nocturno)
curl "https://juanmacias.com/api/v1/route-planner?\
origin=METRO_MALAGA_TCH&dest=METRO_MALAGA_ATZ&time=01:00&date=2026-02-06"

# Ruta el día festivo
curl "https://juanmacias.com/api/v1/route-planner?\
origin=METRO_MALAGA_TCH&dest=METRO_MALAGA_ATZ&time=10:00&date=2026-02-08"
```

---

## Checklist

- [ ] Crear script `scripts/import_metro_malaga_gtfs.py`
- [ ] Insertar 5 calendarios en gtfs_calendar
- [ ] Insertar 26 excepciones festivos en gtfs_calendar_dates
- [ ] Insertar 18 excepciones vísperas en gtfs_calendar_dates
- [ ] Importar 4,682 trips
- [ ] Importar 48,945 stop_times
- [ ] Importar 4 shapes (260 puntos)
- [ ] Verificar RAPTOR con los 5 tipos de servicio
- [ ] Test routing laborable
- [ ] Test routing viernes/sábado noche (hasta 01:30)
- [ ] Test routing víspera de festivo (hasta 01:30)
- [ ] Test routing festivo (servicio reducido)
- [ ] Deploy a producción

---

## Resumen Final

| Concepto | Valor |
|----------|-------|
| Trips a importar | 4,682 |
| Stop times a importar | 48,945 |
| Shapes a importar | 4 |
| Services a crear | 5 |
| Festivos | 13 |
| Vísperas de festivo | 9 (las que no son V/S) |
| Calendar_dates | **44 registros** (26 festivos + 18 vísperas) |
| Validez | 01/01/2026 - 31/12/2026 |
