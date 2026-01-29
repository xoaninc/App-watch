# Plan de Acción: Importación Metro Sevilla GTFS

**Fecha:** 2026-01-29
**Estado:** APROBADO

---

## Resumen Ejecutivo

Actualizar los trips y stop_times de Metro Sevilla usando el GTFS oficial del NAP, expandiendo las frecuencias a trips individuales según los horarios oficiales de la web de Metro Sevilla.

---

## Datos a Importar

| Archivo | NAP | Acción |
|---------|-----|--------|
| stops.txt | 42 (21 estaciones + 21 plataformas) | NO importar (mantener actuales) |
| routes.txt | 1 (L1) | NO importar (ya existe) |
| calendar.txt | 40 | Importar/actualizar |
| calendar_dates.txt | 98 | Importar + añadir víspera Navidad |
| trips.txt | 104 (base) | Expandir a ~3,500 trips |
| stop_times.txt | 2,088 (base) | Expandir a ~73,500 stop_times |
| frequencies.txt | 594 | Usar para generar trips |
| shapes.txt | 0 (vacío) | NO importar (mantener actuales) |

---

## Horarios de Servicio

| Día | Horario | Nocturno |
|-----|---------|----------|
| **Lunes-Jueves** | 06:30 - 23:00 | No |
| **Viernes + Vísperas** | 06:30 - 02:00 | Sí |
| **Sábados** | 07:30 - 02:00 | Sí |
| **Domingos/Festivos** | 07:30 - 23:00 | No |

---

## Temporadas

| Temporada | Fechas | Código |
|-----------|--------|--------|
| **INVIERNO** | 16 sept - 15 junio | INV |
| **VERANO 1** | 16 junio - 15 julio | V1 |
| **VERANO 1** | 1 - 15 septiembre | V1 |
| **VERANO 2** | 16 julio - 31 agosto | V2 |

---

## Frecuencias Oficiales

### TEMPORADA INVIERNO (16 sept - 15 junio)

#### Lunes a Jueves Laborables

| Tramo | Frecuencia | Nota |
|-------|------------|------|
| 06:30 - 07:00 | 12-13 min | |
| 07:00 - 07:30 | 5-6 min (1) / 7-8 min (2) | |
| 07:30 - 09:30 | 4 min (1) / 8 min (2) | Hora punta mañana |
| 09:30 - 13:30 | 7-8 min | |
| 13:30 - 15:30 | 4 min (1) / 8 min (2) | Hora punta mediodía |
| 15:30 - 18:00 | 7-8 min | |
| 18:00 - 21:30 | 6-7 min | Hora punta tarde |
| 21:30 - 23:00 | 12-13 min | |

#### Viernes Laborables

| Tramo | Frecuencia |
|-------|------------|
| 06:30 - 18:00 | Igual que L-J |
| 18:00 - 22:00 | 5-6 min |
| 22:00 - 23:00 | 12-13 min |
| 23:00 - 02:00 | 15-16 min (nocturno) |

#### Sábados

| Tramo | Frecuencia |
|-------|------------|
| 07:30 - 08:00 | 12-13 min |
| 08:00 - 22:00 | 7-8 min |
| 22:00 - 23:00 | 12-13 min |
| 23:00 - 02:00 | 15-16 min (nocturno) |

#### Domingos y Festivos

| Tramo | Frecuencia |
|-------|------------|
| 07:30 - 08:00 | 12-13 min |
| 08:00 - 21:00 | 7-8 min |
| 21:00 - 23:00 | 12-13 min |

---

### TEMPORADA VERANO 1 (16 jun - 15 jul) y (1-15 sept)

#### Lunes a Viernes

| Tramo | Frecuencia |
|-------|------------|
| 06:30 - 07:00 | 12-13 min |
| 07:00 - 07:30 | 7-8 min |
| 07:30 - 09:30 | 4-5 min (1) / 9-10 min (2) |
| 09:30 - 13:30 | 8-9 min |
| 13:30 - 15:30 | 4-5 min (1) / 9-10 min (2) |
| 15:30 - 18:00 | 7-8 min |
| 18:00 - 22:00 | 7-8 min (L-J) / 8-9 min (V) |
| 22:00 - 23:00 | 12-13 min |
| 23:00 - 02:00 | 15-16 min (solo V) |

#### Sábados

| Tramo | Frecuencia |
|-------|------------|
| 07:30 - 08:00 | 12-13 min |
| 08:00 - 17:00 | 9-10 min |
| 17:00 - 22:00 | 8-9 min |
| 22:00 - 23:00 | 12-13 min |
| 23:00 - 02:00 | 15-16 min |

#### Domingos y Festivos

| Tramo | Frecuencia |
|-------|------------|
| 07:30 - 08:00 | 12-13 min |
| 08:00 - 17:00 | 10-11 min |
| 17:00 - 21:00 | 9-10 min |
| 21:00 - 23:00 | 12-13 min |

---

### TEMPORADA VERANO 2 (16 jul - 31 ago)

#### Lunes a Viernes

| Tramo | Frecuencia |
|-------|------------|
| 06:30 - 07:00 | 12-13 min |
| 07:00 - 09:30 | 7-8 min |
| 09:30 - 13:30 | 8-9 min |
| 13:30 - 15:30 | 7-8 min |
| 15:30 - 22:00 | 9-10 min |
| 22:00 - 23:00 | 12-13 min |
| 23:00 - 02:00 | 15-16 min (solo V) |

#### Sábados

| Tramo | Frecuencia |
|-------|------------|
| 07:30 - 08:00 | 12-13 min |
| 08:00 - 22:00 | 10-11 min |
| 22:00 - 23:00 | 12-13 min |
| 23:00 - 02:00 | 15-16 min |

#### Domingos y Festivos

| Tramo | Frecuencia |
|-------|------------|
| 07:30 - 23:00 | 12-13 min (todo el día) |

---

**Nota sobre tramos:**
- **(1)** = Tramo Ciudad Expo ↔ Pablo de Olavide (17 paradas)
- **(2)** = Tramo Pablo de Olavide ↔ Olivar de Quintos (4 paradas)

---

## Tiempos Entre Paradas

| Parada | Nombre | Tiempo acum. |
|--------|--------|--------------|
| 1 | Ciudad Expo | 0:00 |
| 2 | Cavaleri | 2:00 |
| 3 | San Juan Alto | 5:00 |
| 4 | San Juan Bajo | 7:30 |
| 5 | Blas Infante | 10:15 |
| 6 | Parque de los Príncipes | 12:00 |
| 7 | Plaza de Cuba | 13:30 |
| 8 | Puerta Jerez | 15:00 |
| 9 | Prado de San Sebastián | 17:00 |
| 10 | San Bernardo | 18:30 |
| 11 | Nervión | 21:00 |
| 12 | Gran Plaza | 22:00 |
| 13 | 1º de Mayo | 24:00 |
| 14 | Amate | 25:30 |
| 15 | La Plata | 26:15 |
| 16 | Cocheras | 28:15 |
| 17 | Pablo de Olavide | 32:00 |
| 18 | Condequinto | 34:00 |
| 19 | Montequinto | 36:00 |
| 20 | Europa | 37:30 |
| 21 | Olivar de Quintos | 38:30 |

**Tiempo total:** 38 minutos 30 segundos

---

## Festivos Sevilla 2026

| Fecha | Día | Festivo | Servicio |
|-------|-----|---------|----------|
| 01/01 | Jueves | Año Nuevo | DOMINGO |
| 06/01 | Martes | Reyes | DOMINGO |
| 28/02 | Sábado | Día de Andalucía | SABADO (ya es sábado) |
| 02/04 | Jueves | Jueves Santo | DOMINGO |
| 03/04 | Viernes | Viernes Santo | DOMINGO |
| 22/04 | Miércoles | Miércoles de Feria | DOMINGO |
| 01/05 | Viernes | Día del Trabajo | DOMINGO |
| 04/06 | Jueves | Corpus Christi | DOMINGO |
| 15/08 | Sábado | Asunción | SABADO (ya es sábado) |
| 12/10 | Lunes | Fiesta Nacional | DOMINGO |
| 01/11 | Domingo | Todos los Santos | DOMINGO (ya es domingo) |
| 06/12 | Domingo | Constitución | DOMINGO (ya es domingo) |
| 08/12 | Martes | Inmaculada | DOMINGO |
| 25/12 | Viernes | Navidad | DOMINGO |

---

## Vísperas de Festivo 2026

Días que activan servicio nocturno (hasta 02:00):

| Fecha | Día | Víspera de | Servicio |
|-------|-----|------------|----------|
| 31/12/2025 | Miércoles | Año Nuevo | VIERNES |
| 05/01/2026 | Lunes | Reyes | SABADO |
| 01/04/2026 | Miércoles | Jueves Santo | VIERNES |
| 30/04/2026 | Jueves | Día del Trabajo | VIERNES |
| 03/06/2026 | Miércoles | Corpus Christi | VIERNES |
| 11/10/2026 | Domingo | Fiesta Nacional | SABADO |
| 07/12/2026 | Lunes | Inmaculada | SABADO |
| **24/12/2026** | **Jueves** | **Navidad** | **VIERNES** ⚠️ |

**⚠️ Nota:** El NAP no incluye 24/12/2026, hay que añadirlo manualmente.

---

## Semana Santa 2026

Servicio especial VIERNES (nocturno) todos los días:

| Fecha | Día | Nombre |
|-------|-----|--------|
| 29/03 | Domingo | Domingo de Ramos |
| 30/03 | Lunes | Lunes Santo |
| 31/03 | Martes | Martes Santo |
| 01/04 | Miércoles | Miércoles Santo |
| 02/04 | Jueves | Jueves Santo (festivo) |
| 03/04 | Viernes | Viernes Santo (festivo) |

---

## Feria de Abril 2026

Servicio especial VIERNES (nocturno) todos los días:

| Fecha | Día |
|-------|-----|
| 20/04 | Lunes |
| 21/04 | Martes |
| 22/04 | Miércoles (festivo local) |
| 23/04 | Jueves |

---

## Script de Importación

**Archivo:** `scripts/import_metro_sevilla_gtfs.py`

### Pasos:

1. **Crear/actualizar calendarios** (4 tipos × 3 temporadas = 12 por año)
2. **Importar calendar_dates** (festivos + vísperas + Semana Santa + Feria)
3. **Expandir frequencies a trips individuales**
4. **Generar stop_times** para cada trip
5. **NO tocar shapes** (mantener los actuales)
6. **Verificar importación**

### Mapeo de IDs:

| NAP | BD |
|-----|-----|
| L1-CE-OQ | METRO_SEV_L1_CE_OQ |
| L1-1 ... L1-21 | METRO_SEV_L1_E1 ... METRO_SEV_L1_E21 |
| 2026_Laborable_ENE_JUN | METRO_SEV_2026_Laborable_ENE_JUN |

---

## Datos Importados (Reales)

| Concepto | Cantidad |
|----------|----------|
| Calendarios | 40 (4 tipos × 5 temp × 2 años) |
| Calendar_dates | 100 (98 NAP + 2 víspera Navidad) |
| Trips por laborable (2026 ENE_JUN) | 308 |
| Trips por viernes (2026 ENE_JUN) | 346 |
| Trips por sábado (2026 ENE_JUN) | 250 |
| Trips por domingo (2026 ENE_JUN) | 222 |
| **Total trips** | 9,862 |
| **Total stop_times** | 204,414 |

*Nota: Los trips incluyen 2025 y 2026, todas las temporadas (5) y ambas direcciones.*

---

## Verificación Post-Importación

```sql
-- 1. Calendarios
SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'METRO_SEV%';
-- Esperado: 40 ✓

-- 2. Calendar_dates
SELECT COUNT(*) FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_SEV%';
-- Esperado: 100 ✓

-- 3. Trips por servicio
SELECT service_id, COUNT(*) FROM gtfs_trips
WHERE route_id LIKE 'METRO_SEV%'
GROUP BY service_id;

-- 4. Stop_times
SELECT COUNT(*) FROM gtfs_stop_times
WHERE trip_id LIKE 'METRO_SEV%';
-- Esperado: 204,414 ✓
```

---

## Verificación Post-Importación

### Paso 1: Verificar SQL

```sql
-- Calendarios (esperado: 40)
SELECT COUNT(*) FROM gtfs_calendar WHERE service_id LIKE 'METRO_SEV%';

-- Calendar_dates (esperado: 100)
SELECT COUNT(*) FROM gtfs_calendar_dates WHERE service_id LIKE 'METRO_SEV%';

-- Trips por servicio
SELECT service_id, COUNT(*) FROM gtfs_trips
WHERE route_id LIKE 'METRO_SEV%'
GROUP BY service_id;

-- Stop_times (esperado: 204,414)
SELECT COUNT(*) FROM gtfs_stop_times WHERE trip_id LIKE 'METRO_SEV%';

-- Verificar víspera Navidad (debe mostrar 2 filas)
SELECT * FROM gtfs_calendar_dates
WHERE service_id LIKE 'METRO_SEV%' AND date = '2026-12-24';
```

### Paso 2: Verificar GTFSStore (logs)

```bash
journalctl -u renfeserver --since "5 minutes ago" | grep -i "metro_sev\|trips\|stop_times"
```

Debe mostrar que se cargaron 9,862 trips y 204,414 stop_times de Metro Sevilla.

### Paso 3: Verificar API Departures

```bash
# Próximas salidas desde Ciudad Expo
curl "http://localhost:8002/api/v1/gtfs/stops/METRO_SEV_L1_E1/departures?limit=5"

# Próximas salidas desde Olivar de Quintos
curl "http://localhost:8002/api/v1/gtfs/stops/METRO_SEV_L1_E21/departures?limit=5"
```

Verificar que las frecuencias coinciden con las oficiales.

---

## Test RAPTOR Routing

### Test 1: Laborable mañana (hora punta)

```bash
curl "http://localhost:8002/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E1&to=METRO_SEV_L1_E21&departure_time=08:00"
```
**Esperado:** Viaje de ~38 min, siguiente tren en ~4-8 min.

### Test 2: Viernes noche (nocturno)

```bash
curl "http://localhost:8002/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E1&to=METRO_SEV_L1_E21&departure_time=01:00"
```
**Esperado:** Encuentra ruta (servicio nocturno hasta 02:00), frecuencia 15-16 min.

### Test 3: Festivo (1 enero 2026)

```bash
curl "http://localhost:8002/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E1&to=METRO_SEV_L1_E21&departure_time=2026-01-01T10:00"
```
**Esperado:** Servicio DOMINGO, empieza a las 07:30, frecuencia 7-8 min.

### Test 4: Feria de Abril (21 abril 2026 - martes)

```bash
curl "http://localhost:8002/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E1&to=METRO_SEV_L1_E21&departure_time=2026-04-21T01:00"
```
**Esperado:** Servicio nocturno activo (Feria), encuentra ruta a la 01:00.

### Test 5: Víspera Navidad (24 dic 2026 - jueves)

```bash
curl "http://localhost:8002/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E1&to=METRO_SEV_L1_E21&departure_time=2026-12-24T01:00"
```
**Esperado:** Servicio nocturno activo (víspera), encuentra ruta a la 01:00.

---

## Checklist

- [x] Crear script `scripts/import_metro_sevilla_gtfs.py`
- [x] Implementar expansión de frequencies a trips
- [x] Implementar generación de stop_times
- [x] Añadir víspera Navidad (24/12/2026) al calendar_dates
- [x] Ejecutar en dry-run
- [x] Ejecutar importación real
- [x] Verificar datos importados (SQL)
- [x] Reiniciar servidor para recargar GTFSStore
- [x] Verificar carga en GTFSStore (logs)
- [x] Test API departures (próximas salidas) ✓ Frecuencias correctas
- [x] Test RAPTOR routing laborable ✓ 38 min 30 seg
- [x] Test RAPTOR routing viernes nocturno ✓ Trips hasta 26:00 (02:00)
- [x] Test RAPTOR routing festivo ✓ 1 enero funciona
- [x] Test RAPTOR routing Feria de Abril ✓ Servicio VIERNES añadido
- [ ] Deploy a producción

---

## Archivos GTFS NAP

**Ubicación local:** `/tmp/gtfs_metro_sevilla/`
**NAP File ID:** 1583
**Validez:** 2025-01-01 a 2026-12-31

---

## Historial

| Fecha | Cambio |
|-------|--------|
| 2026-01-29 | Creación del plan de acción |
| 2026-01-29 | Importación completada: 9,862 trips, 204,414 stop_times |
