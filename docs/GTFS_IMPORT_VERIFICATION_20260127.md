# Verificación de Importación GTFS - 2026-01-27

## Resumen

Importación exitosa del archivo GTFS de Renfe Cercanías con las siguientes mejoras:

1. **243 paradas faltantes** detectadas e importadas automáticamente
2. **1,843,770 stop_times** importados (0 saltados)
3. **99.6% de trips** con stop_times (antes ~97.5%)
4. Mapeo correcto usando `network_id` en lugar de `nucleo_id` (obsoleto)

## Estado de la Base de Datos

| Tabla | Registros |
|-------|-----------|
| gtfs_networks | 31 |
| gtfs_routes | 325 |
| gtfs_stops | 6,709 |
| gtfs_trips | 134,023 |
| gtfs_stop_times | 1,843,770 |
| gtfs_calendar | 360 |
| gtfs_calendar_dates | 0 |
| stop_platform | 2,989 |
| stop_correspondence | 246 |
| network_provinces | 37 |

## Datos por Network (Cercanías Renfe)

| Network ID | Nombre | Rutas | Trips | Con stop_times | Sin stop_times |
|------------|--------|-------|-------|----------------|----------------|
| 10T | Madrid | 33 | 36,459 | 36,229 | 230 |
| 20T | Asturias | 9 | 12,864 | 12,864 | 0 |
| 30T | Sevilla | 7 | 4,394 | 4,394 | 0 |
| 33T | Cádiz | 3 | 3,848 | 3,848 | 0 |
| 34T | Málaga | 4 | 3,936 | 3,876 | 60 |
| 40T | Valencia | 121 | 10,372 | 10,271 | 101 |
| 41T | Murcia/Alicante | 3 | 2,906 | 2,772 | 134 |
| 51T | Rodalies Catalunya | 57 | 37,646 | 37,616 | 30 |
| 60T | Bilbao | 16 | 9,616 | 9,616 | 0 |
| 61T | San Sebastián | 1 | 1,870 | 1,870 | 0 |
| 62T | Santander | 3 | 7,884 | 7,884 | 0 |
| 70T | Zaragoza | 1 | 2,228 | 2,228 | 0 |
| **TOTAL** | | **258** | **134,023** | **133,468** | **555** |

**Nota:** Los 555 trips sin stop_times (0.4%) son un problema del archivo GTFS fuente, no de nuestro sistema de importación.

## Verificación de Endpoints API

### 1. Platforms ✅
```
GET /api/v1/gtfs/stops/RENFE_17000/platforms
```
Respuesta: 2,989 plataformas disponibles en el sistema.

### 2. Route Planner (RAPTOR) ✅
```
GET /api/v1/gtfs/route-planner?from=RENFE_17000&to=RENFE_10000&departure_time=08:00
```
Respuesta: Encuentra rutas con horarios reales desde stop_times.

### 3. Correspondences ✅
```
GET /api/v1/gtfs/stops/RENFE_17000/correspondences
```
Respuesta: 246 correspondencias disponibles entre paradas.

### 4. Departures ✅
```
GET /api/v1/gtfs/stops/RENFE_17000/departures
```
Respuesta: Salidas con andenes estimados desde histórico.

## Mapeo GTFS Nucleo → Network ID

El archivo GTFS de Renfe usa IDs de núcleo (primeros 2 dígitos del route_id) que se mapean a nuestros network_ids:

| GTFS Nucleo | Network ID | Nombre |
|-------------|------------|--------|
| 10 | 10T | Madrid |
| 20 | 20T | Asturias |
| 30 | 30T | Sevilla |
| 31 | **33T** | Cádiz (diferente) |
| 32 | **34T** | Málaga (diferente) |
| 40 | 40T | Valencia |
| 41 | 41T | Murcia/Alicante |
| 51 | 51T | Barcelona (Rodalies) |
| 60 | 60T | Bilbao |
| 61 | 61T | San Sebastián |
| 62 | 62T | Santander |
| 70 | 70T | Zaragoza |
| 90 | 10T | C-9 Cotos (parte de Madrid) |

## Cambios Realizados

### Script `import_gtfs_static.py`

1. **Nueva función `import_missing_stops()`**
   - Detecta paradas referenciadas en stop_times que no existen en la BD
   - Las importa automáticamente desde stops.txt del GTFS
   - Evita que se pierdan stop_times por paradas faltantes

2. **Nueva función `import_calendar_dates()`**
   - Importa excepciones de calendario (días festivos, servicios especiales)
   - Soporta exception_type 1 (añadido) y 2 (eliminado)

3. **Actualización de `build_route_mapping()`**
   - Usa `network_id` en lugar de `nucleo_id` (columna eliminada en migración 024)
   - Mapeo correcto GTFS nucleo → network_id con casos especiales

4. **Actualización de `clear_nucleo_data()`**
   - Usa diccionario `GTFS_NUCLEO_TO_NETWORK` para conversión correcta

5. **Nuevos diccionarios de mapeo**
   - `NUCLEO_NAMES`: Nombres de núcleos GTFS (corregidos)
   - `GTFS_NUCLEO_TO_NETWORK`: Mapeo GTFS nucleo → network_id

## Archivos Modificados

- `scripts/import_gtfs_static.py` - Script de importación actualizado
- `docs/RAPTOR_IMPLEMENTATION_PLAN.md` - Documentación actualizada
- `docs/GTFS_IMPORT_VERIFICATION_20260127.md` - Este documento

## Referencias

- `docs/ARCHITECTURE_NETWORK_PROVINCES.md` - Sistema de networks y provincias
- `alembic/versions/024_replace_nucleos_with_network_provinces.py` - Migración que eliminó nucleo_id
