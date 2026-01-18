# GTFS Import System Changes

## Overview

This document summarizes the changes made to standardize and improve the GTFS import system for adding new Spanish transit systems.

## Transit Systems Status

| Sistema | Network | Agency | Colores | location_type | Correspondencias |
|---------|---------|--------|---------|---------------|------------------|
| Metro Madrid | ✅ METRO | ✅ METRO_MADRID | ✅ Por línea | ✅ 1 (station) | ✅ automático |
| Metro Ligero | ✅ ML | ✅ METRO_LIGERO | ✅ Por línea | ✅ 1 (station) | ✅ automático |
| Metro Sevilla | ✅ METRO_SEV | ✅ METRO_SEVILLA | ✅ Verde (#0D6928) | ✅ 1 (station) | ✅ automático |
| Tranvía Sevilla | ✅ TRAM_SEV | ✅ TRANVIA_SEVILLA | ✅ Rojo (#E4002B) | ✅ 1 (station) | ✅ automático |
| Renfe Cercanías | N/A | N/A | N/A | N/A | ✅ automático |

## Correspondences System

Correspondences between transit systems are now calculated **automatically** when importing GTFS data:

1. **Proximity matching** (default 150m) - stops within distance are connected
2. **Name matching** - stops with same/similar normalized names are connected (e.g., "San Bernardo" in Metro and Cercanías)

Each import script calls `populate_connections_for_nucleo()` at the end to find connections with other transit systems in the same núcleo.

## New Files Created

### `scripts/gtfs_validator.py`
GTFS data validator that checks data integrity before importing.

**Features:**
- Structure validation (required files and columns)
- Data integrity checks (empty fields, valid coordinates, time/date formats)
- Cross-reference validation (trips→routes, stop_times→trips/stops)
- Metrics collection (counts, date ranges)
- Suspicious data detection (zero counts, expired calendars)

**Usage:**
```bash
python scripts/gtfs_validator.py /path/to/gtfs.zip
```

### `scripts/gtfs_importer_base.py`
Base class for all GTFS importers to ensure consistent patterns.

**Features:**
- `NetworkConfig`, `AgencyConfig`, `RouteConfig` dataclasses
- `GTFSImporterBase` abstract class with common methods
- Automatic network, agency, route, stop creation
- Import statistics tracking
- CLI helper functions

**Usage:**
```python
from scripts.gtfs_importer_base import GTFSImporterBase, NetworkConfig, AgencyConfig

class MyTransitImporter(GTFSImporterBase):
    NETWORK_CONFIG = NetworkConfig(
        code='MY_TRANSIT',
        name='My Transit System',
        city='City',
        region='Region',
        color='FF0000',
    )
    AGENCY_CONFIG = AgencyConfig(
        id='MY_TRANSIT_AGENCY',
        name='My Transit Agency',
    )
    NUCLEO_ID = 99

    def import_routes(self, agency_id):
        # Implementation
        pass

    def import_stops(self):
        # Implementation
        pass
```

## Modified Files

### `scripts/import_gtfs_static.py`
Added import by núcleo functionality.

**New arguments:**
```bash
# Import all núcleos
python scripts/import_gtfs_static.py /path/to/fomento_transit.zip

# Import specific núcleo by ID or name
python scripts/import_gtfs_static.py fomento_transit.zip --nucleo 10
python scripts/import_gtfs_static.py fomento_transit.zip --nucleo madrid

# List available núcleos
python scripts/import_gtfs_static.py fomento_transit.zip --list-nucleos
```

**Changes:**
- Added `argparse` for CLI
- Added `NUCLEO_NAMES` and `NUCLEO_MAPPING` constants
- Added `parse_nucleo_arg()` function
- Added `list_nucleos()` and `print_nucleos()` functions
- Modified `build_route_mapping()` to accept `nucleo_filter` parameter
- Added `clear_nucleo_data()` for partial deletes
- Added `clear_all_data()` for full deletes

### `scripts/auto_update_gtfs.py`
Integrated validation and added núcleo support.

**New arguments:**
```bash
# Update all sources
python scripts/auto_update_gtfs.py [--dry-run]

# Update specific Renfe núcleo only
python scripts/auto_update_gtfs.py --nucleo 10
python scripts/auto_update_gtfs.py --nucleo madrid

# List available sources and núcleos
python scripts/auto_update_gtfs.py --list

# Skip validation (not recommended)
python scripts/auto_update_gtfs.py --skip-validation
```

**Changes:**
- Added `argparse` for CLI
- Added `GTFSValidator` integration
- Added `download_and_validate()` function
- Added `update_renfe_nucleo()` function
- Added `parse_nucleo_arg()` and `list_sources_and_nucleos()` functions
- Better logging configuration (fallback if no write permission)

### `scripts/import_tranvia_sevilla.py`
Fixed issues reported by app developer.

**Fixes:**
1. **route_count = 0**: Added `NetworkModel` with code `TRAM_SEV`
2. **correspondencias missing**: Added `TRANVIA_CORRESPONDENCES` dict and set `cor_metro`/`cor_cercanias` on stops
3. **location_type = 0**: Changed to `location_type = 1` (station)

**Changes:**
- Added `NetworkModel` import
- Added `NETWORK_CONFIG` constant
- Added `TRANVIA_CORRESPONDENCES` for known connections
- Added `import_network()` function
- Updated `import_stops()` to set `location_type=1` and correspondences
- Renamed `add_correspondences()` to `add_reverse_correspondences()`

### `src/gtfs_bc/metro/infrastructure/services/crtm_metro_importer.py`
Fixed network and location_type for Metro Madrid and Metro Ligero.

**Fixes:**
- Added `NetworkModel` for route_count to work (METRO and ML networks)
- Changed `location_type` from 0 to 1 (station) for all stops

**Changes:**
- Added `NetworkModel` import
- Added `METRO_NETWORK_CONFIG` and `ML_NETWORK_CONFIG` constants
- Added `_create_networks()` method
- Updated `import_all()` to call `_create_networks()`
- Changed `location_type=0` to `location_type=1` in Metro and ML stops

### `scripts/import_metro_sevilla.py`
Fixed color and added network support.

**Fixes:**
- Set official Metro Sevilla green color `#0D6928`
- Added `NetworkModel` for route_count to work

**Changes:**
- Added `NetworkModel` import
- Added `NETWORK_CONFIG` constant
- Set `DEFAULT_ROUTE_COLOR` to `#0D6928` (green)
- Set `DEFAULT_TEXT_COLOR` to `#FFFFFF`
- Added `import_network()` function
- Updated main() to call `import_network()`
- Added automatic correspondence calculation with `populate_connections_for_nucleo()`

### `scripts/populate_stop_connections.py`
Extended to handle Sevilla transit systems and name-based matching.

**New stop types supported:**
- `RENFE_` - Cercanías
- `METRO_` - Metro Madrid
- `ML_` - Metro Ligero Madrid
- `METRO_SEV_` - Metro Sevilla
- `TRAM_SEV_` - Tranvía Sevilla

**New matching features:**
- **Proximity matching** (150m default) - unchanged
- **Name matching** - `normalize_name()` removes accents, prefixes ("Estación de", etc.), and normalizes whitespace
- **Combined matching** - both methods are used to find connections

**New functions:**
- `normalize_name(name)` - Normalizes station name for comparison
- `names_match(name1, name2)` - Checks if two names refer to same place
- `populate_connections_for_nucleo(db, nucleo_id)` - Called by import scripts to auto-calculate connections

**Changes:**
- Added `STOP_PREFIXES` constant
- Added `get_stop_type()` function
- Added `normalize_name()` and `names_match()` for name-based matching
- Added `populate_connections_for_nucleo()` for per-núcleo calculation
- Updated `populate_connections()` to use both proximity AND name matching
- Added Sevilla-specific connection logic
- Updated statistics output

## Núcleos de Cercanías Reference

| ID | Name |
|----|------|
| 10 | Madrid |
| 20 | Asturias |
| 30 | Sevilla |
| 31 | Cádiz |
| 32 | Málaga |
| 40 | Valencia |
| 41 | Murcia/Alicante |
| 50 | Rodalies de Catalunya |
| 60 | Bilbao |
| 61 | San Sebastián |
| 62 | Cantabria |
| 70 | Zaragoza |

## Adding New Transit Systems

To add a new transit system:

1. **Create import script** inheriting from `GTFSImporterBase`:
   ```python
   from scripts.gtfs_importer_base import (
       GTFSImporterBase, NetworkConfig, AgencyConfig, create_cli_main
   )

   class NewTransitImporter(GTFSImporterBase):
       NETWORK_CONFIG = NetworkConfig(...)
       AGENCY_CONFIG = AgencyConfig(...)
       NUCLEO_ID = XX

       def import_routes(self, agency_id):
           ...

       def import_stops(self):
           ...

   if __name__ == "__main__":
       create_cli_main(NewTransitImporter)()
   ```

2. **Add to auto_update_gtfs.py**:
   - Add source to `GTFS_SOURCES` dict
   - Create `update_new_transit()` function
   - Add to main() update sequence

3. **Update populate_stop_connections.py** if needed:
   - Add new prefix to `STOP_PREFIXES`
   - Update `get_stop_type()` function
   - Add connection logic in `populate_connections()`

4. **Validate before importing**:
   ```bash
   python scripts/gtfs_validator.py /path/to/new_gtfs.zip
   ```

## Network Code Convention

Network codes must match route ID prefixes for `route_count` to work:

| Network Code | Route ID Pattern | Example Route ID |
|--------------|------------------|------------------|
| `METRO_SEV` | `METRO_SEV_*` | `METRO_SEV_L1` |
| `TRAM_SEV` | `TRAM_SEV_*` | `TRAM_SEV_T1` |
| `METRO` | `METRO_*` | `METRO_1` |
| `ML` | `ML_*` | `ML_ML1` |

## Color Format Convention

**All colors MUST include the `#` prefix** for CSS compatibility:

```python
# CORRECT
'color': '#ED1C24'
'text_color': '#FFFFFF'
DEFAULT_ROUTE_COLOR = '#0D6928'

# WRONG - will not display correctly in apps
'color': 'ED1C24'
```

**Color columns in database:**
- `gtfs_routes.color`: VARCHAR(7) - e.g., `#2DBEF0`
- `gtfs_routes.text_color`: VARCHAR(7) - e.g., `#FFFFFF`
- `gtfs_networks.color`: VARCHAR(7) - e.g., `#ED1C24`
- `gtfs_networks.text_color`: VARCHAR(7) - e.g., `#FFFFFF`

## Correspondence Format Convention

The correspondence fields (`cor_metro`, `cor_ml`, `cor_cercanias`, `cor_tranvia`) use specific formats:

### cor_metro (Metro line connections)
- **Format**: `L1, L2, L3` or `R` for Ramal
- **Example**: `L1, L3, L5` (for Sol)
- **Filtering**: Only Metro lines 1-12 and R are included (Cercanías lines like C1, C4 are filtered out)

### cor_ml (Metro Ligero connections)
- **Format**: `ML1, ML2, ML3, ML4`
- **Example**: `ML2` (for Aravaca)
- **Filtering**: Only ML lines 1-4 are included (Cercanías lines are filtered out)

### cor_cercanias (Cercanías connections)
- **Format**: `C1, C2, C3, C4, C4a, C4b, C5, etc.`
- **Example**: `C4, C4a, C4b, C5` (for Villaverde Alto)
- **No filtering**: All Cercanías lines are included

### cor_tranvia (Tranvía connections)
- **Format**: `T1`
- **Example**: `T1` (for Sevilla stops)

### Filtering Functions in populate_stop_connections.py

| Function | Purpose | Valid Lines |
|----------|---------|-------------|
| `is_metro_line()` | Check if line is Metro | 1-12, L1-L12, R |
| `is_ml_line()` | Check if line is ML | 1-4, ML1-ML4 |
| `normalize_metro_line()` | Add L prefix | 1→L1, 2→L2, etc. |
| `normalize_ml_line()` | Add ML prefix | 1→ML1, 2→ML2, etc. |

**Important:** The `sort_lines()` function takes parameters:
- `add_l_prefix=True` for cor_metro (filters non-Metro lines)
- `add_ml_prefix=True` for cor_ml (filters non-ML lines)

## Note About Other Cities

Stops in cities without dedicated Metro import scripts (Barcelona, Valencia, Bilbao, Málaga) may have **descriptive text** in `cor_metro` from the original RENFE GTFS data:

```
# Examples from RENFE data (not managed by us):
Barcelona-Sants: "Metro líneas L3 y L5"
València Estació del Nord: "Metro: Líneas 3 y 5"
Bilbao Abando: "Metro: Líneas 1 y 2"
```

These are **NOT errors** - they come from RENFE's original data. Our import system only manages Madrid (nucleo_id=10) and Sevilla (nucleo_id=30) correspondences with proper code format.

## Frequency-Based Services (Metro, Metro Ligero, Tranvía)

Systems that use frequency-based departures instead of fixed schedules (stop_times):

| Sistema | Tipo | Tabla de Datos |
|---------|------|----------------|
| Metro Madrid | frequency | `gtfs_route_frequencies` |
| Metro Ligero | frequency | `gtfs_route_frequencies` |
| Metro Sevilla | frequency | `gtfs_route_frequencies` |
| Tranvía Sevilla | frequency | `gtfs_route_frequencies` |
| Renfe Cercanías | schedule | `gtfs_stop_times` |

### Frequency Data Structure

```sql
CREATE TABLE gtfs_route_frequencies (
    id SERIAL PRIMARY KEY,
    route_id VARCHAR(100) NOT NULL,
    day_type VARCHAR(20) NOT NULL,  -- 'weekday', 'saturday', 'sunday'
    start_time TIME NOT NULL,        -- Hora inicio del período
    end_time TIME NOT NULL,          -- Hora fin del período
    headway_secs INTEGER NOT NULL    -- Intervalo entre trenes (segundos)
);
```

### Day Type Values

| day_type | Días | Ejemplo |
|----------|------|---------|
| `weekday` | Lunes a Viernes | L-V |
| `saturday` | Sábado | S |
| `sunday` | Domingo y Festivos | D/F |

### Import de Frecuencias

Los scripts de import leen `frequencies.txt` y `calendar.txt` del GTFS:

```python
# En import_metro_sevilla.py, import_tranvia_sevilla.py
def import_frequencies(db, gtfs_path, route_mapping):
    # 1. Leer frequencies.txt y calendar.txt
    # 2. Mapear service_id → day_type usando calendar.txt
    # 3. Agrupar por (route_id, day_type, start_time, end_time)
    # 4. Guardar mínimo headway para cada período

    freq_model = RouteFrequencyModel(
        route_id=route_id,
        start_time=time(6, 30),      # ← Hora inicio servicio
        end_time=time(23, 30),       # ← Hora fin servicio
        headway_secs=360,            # ← 6 minutos entre trenes
        day_type='weekday',
    )
```

### Comportamiento de la API (Fuera de Horario)

**Importante:** La API maneja correctamente las consultas fuera de horario:

| Hora actual | Servicio | Respuesta API |
|-------------|----------|---------------|
| 14:00 (servicio activo) | ✅ | Salidas desde ahora |
| 04:35 (sin servicio) | ❌ | Salidas desde hora de inicio |

**Ejemplo a las 04:35 AM (domingo):**
```json
{
  "route_short_name": "L1",
  "departure_time": "07:30:00",  // ← Hora real de inicio, NO 04:35
  "minutes_until": 175,
  "frequency_based": true
}
```

### Frecuencias por Defecto

Si el GTFS no tiene `frequencies.txt`, los scripts usan valores por defecto:

```python
# En import_tranvia_sevilla.py
default_frequencies = [
    # Weekday
    {'day_type': 'weekday', 'start': (6, 30), 'end': (9, 0), 'headway': 360},   # 6min
    {'day_type': 'weekday', 'start': (9, 0), 'end': (14, 0), 'headway': 480},   # 8min
    # ...
    # Saturday
    {'day_type': 'saturday', 'start': (7, 0), 'end': (14, 0), 'headway': 480},
    # Sunday
    {'day_type': 'sunday', 'start': (8, 0), 'end': (14, 0), 'headway': 600},
]
```

### Verificar Frecuencias Importadas

```sql
-- Ver frecuencias de un sistema
SELECT route_id, day_type, start_time, end_time, headway_secs
FROM gtfs_route_frequencies
WHERE route_id LIKE 'METRO_SEV%'
ORDER BY route_id, day_type, start_time;

-- Verificar que hay datos para todos los días
SELECT route_id, day_type, COUNT(*) as periods
FROM gtfs_route_frequencies
WHERE route_id LIKE 'TRAM_SEV%'
GROUP BY route_id, day_type;
```

### Checklist para Nuevos Sistemas Frequency-Based

1. ✅ Importar frecuencias desde `frequencies.txt` (o usar defaults)
2. ✅ Asegurar que hay datos para `weekday`, `saturday`, `sunday`
3. ✅ Verificar que `start_time` y `end_time` son correctos
4. ✅ El `headway_secs` debe ser razonable (60-1200 segundos)
5. ✅ La API mostrará salidas desde `start_time` si se consulta antes

### API Endpoint: GET /routes/{route_id}/frequencies

Endpoint para obtener los horarios de operación y frecuencias de una línea:

```bash
# Metro Madrid L1
curl https://juanmacias.com/api/v1/gtfs/routes/METRO_1/frequencies

# Metro Sevilla L1
curl https://juanmacias.com/api/v1/gtfs/routes/METRO_SEV_L1_CE_OQ/frequencies

# Tranvía Sevilla T1
curl https://juanmacias.com/api/v1/gtfs/routes/TRAM_SEV_T1/frequencies

# Cercanías (devuelve [] porque usa stop_times)
curl https://juanmacias.com/api/v1/gtfs/routes/RENFE_C1_19/frequencies
```

**Respuesta:**
```json
[
  {
    "route_id": "METRO_1",
    "day_type": "weekday",
    "start_time": "06:05:00",
    "end_time": "07:00:00",
    "headway_secs": 540,
    "headway_minutes": 9.0
  },
  {
    "route_id": "METRO_1",
    "day_type": "weekday",
    "start_time": "07:00:00",
    "end_time": "22:00:00",
    "headway_secs": 300,
    "headway_minutes": 5.0
  }
]
```

**Obtener inicio/fin del servicio por día:**
```python
# El primer start_time del día es el inicio del servicio
# El último end_time del día es el fin del servicio

# Ejemplo: Para obtener horario de apertura/cierre de Metro L1 en weekday:
frequencies = requests.get(".../routes/METRO_1/frequencies").json()
weekday_freqs = [f for f in frequencies if f["day_type"] == "weekday"]
service_start = min(f["start_time"] for f in weekday_freqs)  # "06:05:00"
service_end = max(f["end_time"] for f in weekday_freqs)      # "01:00:00" (siguiente día)
```

### Cómo se Obtienen los Horarios de Servicio

Los horarios provienen de **dos fuentes**:

#### 1. GTFS frequencies.txt (Fuente principal)

Los datos GTFS de Metro/Tranvía incluyen `frequencies.txt`:

```csv
trip_id,start_time,end_time,headway_secs
trip_001,06:05:00,07:00:00,540
trip_001,07:00:00,10:00:00,420
trip_001,22:00:00,25:00:00,450  # 25:00 = 01:00 del día siguiente
```

**Proceso de import:**
1. Leer `trips.txt` → mapear trip_id a route_id y service_id
2. Leer `calendar.txt` → mapear service_id a day_type (weekday/saturday/sunday)
3. Leer `frequencies.txt` → extraer start_time, end_time, headway_secs
4. Agrupar por (route_id, day_type, start_time, end_time)
5. Guardar en `gtfs_route_frequencies`

```python
# En import_metro_sevilla.py, import_tranvia_sevilla.py
def import_frequencies(db, gtfs_path, route_mapping):
    frequencies = read_csv(gtfs_path / 'frequencies.txt')
    trips = read_csv(gtfs_path / 'trips.txt')
    calendars = read_csv(gtfs_path / 'calendar.txt')

    # Mapear service_id → day_type
    service_days = {}
    for cal in calendars:
        if cal['saturday'] == '1' and cal['sunday'] != '1':
            service_days[cal['service_id']] = 'saturday'
        elif cal['sunday'] == '1':
            service_days[cal['service_id']] = 'sunday'
        else:
            service_days[cal['service_id']] = 'weekday'

    # Procesar frequencies
    for freq in frequencies:
        trip_id = freq['trip_id']
        service_id = trip_info[trip_id]['service_id']
        day_type = service_days.get(service_id, 'weekday')

        # Guardar en BD
        RouteFrequencyModel(
            route_id=route_id,
            day_type=day_type,
            start_time=parse_time(freq['start_time']),
            end_time=parse_time(freq['end_time']),
            headway_secs=int(freq['headway_secs']),
        )
```

#### 2. Valores por Defecto (Fallback)

Si el GTFS no tiene `frequencies.txt`, los scripts usan horarios predefinidos:

```python
# En import_tranvia_sevilla.py
default_frequencies = [
    # Weekday: 06:30 - 23:30
    {'day_type': 'weekday', 'start': (6, 30), 'end': (9, 0), 'headway': 360},
    {'day_type': 'weekday', 'start': (9, 0), 'end': (14, 0), 'headway': 480},
    {'day_type': 'weekday', 'start': (21, 0), 'end': (23, 30), 'headway': 600},

    # Saturday: 07:00 - 23:30
    {'day_type': 'saturday', 'start': (7, 0), 'end': (14, 0), 'headway': 480},

    # Sunday: 08:00 - 22:00
    {'day_type': 'sunday', 'start': (8, 0), 'end': (14, 0), 'headway': 600},
]
```

### Resumen de Horarios Actuales

| Sistema | Weekday | Saturday | Sunday |
|---------|---------|----------|--------|
| Metro Madrid | 06:05 - 01:30 | 06:05 - 02:00 | 06:05 - 02:00 |
| Metro Ligero ML1 | 06:00 - 01:30 | 06:00 - 01:30 | 06:00 - 01:30 |
| Metro Ligero ML2-4 | 06:00 - 00:00 | 07:00 - 00:00 | 07:00 - 00:00 |
| Metro Sevilla | 06:30 - 02:00 | 07:30 - 02:00 | 07:30 - 23:00 |
| Tranvía Sevilla | 06:30 - 23:30 | 07:00 - 23:30 | 08:00 - 22:00 |
