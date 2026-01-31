# TMB Metro Barcelona - Documentación del Problema

## Estado Actual

**Fecha:** 2026-01-31

### Problema Principal

1. **Datos manuales/OSM erróneos:** Se añadieron datos de accesos, correspondencias y/o estructura que no estaban en el GTFS oficial, causando inconsistencias.

2. **Estructura de intercambiadores BCN_* mal configurada:** Impide que RAPTOR funcione correctamente para rutas multimodales.

### Impacto

- RAPTOR FGC bloqueado (depende de TMB)
- Correspondencias FGC ↔ TMB no se pueden crear
- Rutas multimodales Barcelona no funcionan

---

## PASO 0: Limpiar datos erróneos

**ANTES de cualquier otra acción**, identificar y eliminar:
- Accesos añadidos manualmente (no vienen del GTFS)
- Correspondencias erróneas
- Cualquier modificación que no esté en el GTFS estático/RT oficial

### Consultas para identificar datos a eliminar

```sql
-- Accesos TMB en stop_access (probablemente manuales)
SELECT * FROM stop_access WHERE stop_id LIKE 'TMB_METRO_%';

-- Accesos TMB en gtfs_stops con location_type=2 (si los hay)
SELECT * FROM gtfs_stops
WHERE id LIKE 'TMB_METRO_%' AND location_type = 2;

-- Correspondencias TMB
SELECT * FROM stop_correspondence
WHERE from_stop_id LIKE 'TMB_METRO_%' OR to_stop_id LIKE 'TMB_METRO_%';

-- Correspondencias BCN (intercambiadores)
SELECT * FROM stop_correspondence
WHERE from_stop_id LIKE 'BCN_%' OR to_stop_id LIKE 'BCN_%';

-- Paradas con source != 'gtfs' (si existe ese campo)
SELECT * FROM gtfs_stops
WHERE id LIKE 'TMB_METRO_%' AND source IS NOT NULL AND source != 'gtfs';
```

### Datos a conservar

Solo conservar lo que viene del GTFS oficial de TMB:
- `gtfs_stops` con datos del GTFS
- `gtfs_stop_times`
- `gtfs_trips`
- `gtfs_routes`

---

## Análisis Pendiente

### 1. Estructura de datos actual

Verificar estructura de:
- `BCN_PL_CATALUNYA` (intercambiador Plaça Catalunya)
- `BCN_GRACIA` (intercambiador Gràcia)
- `BCN_PL_ESPANYA` (intercambiador Plaça Espanya)
- `BCN_PROVENCA` (intercambiador Provença/Diagonal)

```sql
-- Consultar estructura de intercambiadores
SELECT id, name, parent_station_id, location_type
FROM gtfs_stops
WHERE id LIKE 'BCN_%' OR parent_station_id LIKE 'BCN_%'
ORDER BY id;
```

### 2. Paradas TMB Metro

```sql
-- Consultar estructura TMB Metro
SELECT id, name, parent_station_id, location_type
FROM gtfs_stops
WHERE id LIKE 'TMB_METRO_%'
ORDER BY id;
```

### 3. Correspondencias existentes

```sql
-- Correspondencias TMB
SELECT * FROM stop_correspondence
WHERE from_stop_id LIKE 'TMB_METRO_%' OR to_stop_id LIKE 'TMB_METRO_%';
```

---

## GTFS TMB

- **URL:** https://www.tmb.cat/es/sobre-tmb/open-data
- **Formato:** GTFS estático + GTFS-RT
- **Verificar:** transfers.txt, pathways.txt

---

## Tareas

- [ ] Analizar GTFS TMB oficial
- [ ] Documentar estructura actual de paradas TMB en BD
- [ ] Identificar errores en intercambiadores BCN_*
- [ ] Definir plan de corrección

---

## Referencias

- `TRANSFER_DOC/FGC/FGC_CORRESPONDENCIAS.md` - Describe el problema de BCN_*
- `TRANSFER_DOC/ESTRUCTURA_PROCESO.md` - Proceso estándar de importación
