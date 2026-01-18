# GTFS Import System Changes

## Overview

This document summarizes the changes made to standardize and improve the GTFS import system for adding new Spanish transit systems.

## Transit Systems Status

| Sistema | Network | Agency | Colores | location_type | Correspondencias |
|---------|---------|--------|---------|---------------|------------------|
| Metro Madrid | ✅ METRO | ✅ METRO_MADRID | ✅ Por línea | ✅ 1 (station) | ✅ automático |
| Metro Ligero | ✅ ML | ✅ METRO_LIGERO | ✅ Por línea | ✅ 1 (station) | ✅ automático |
| Metro Sevilla | ✅ METRO_SEV | ✅ METRO_SEVILLA | ✅ Verde (#0D6928) | ✅ 1 (station) | ✅ automático |
| Tranvía Sevilla | ✅ TRANVIA_SEV | ✅ TRANVIA_SEVILLA | ✅ Rojo (#E4002B) | ✅ 1 (station) | ✅ automático |
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
1. **route_count = 0**: Added `NetworkModel` with code `TRANVIA_SEV`
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
- Changed default color from `F8B500` (yellow) to `E4002B` (red)
- Added `NetworkModel` for route_count to work

**Changes:**
- Added `NetworkModel` import
- Added `NETWORK_CONFIG` constant
- Changed `DEFAULT_ROUTE_COLOR` to `E4002B`
- Changed `DEFAULT_TEXT_COLOR` to `FFFFFF`
- Added `import_network()` function
- Updated main() to call `import_network()`

### `scripts/populate_stop_connections.py`
Extended to handle Sevilla transit systems and name-based matching.

**New stop types supported:**
- `RENFE_` - Cercanías
- `METRO_` - Metro Madrid
- `ML_` - Metro Ligero Madrid
- `METRO_SEV_` - Metro Sevilla
- `TRANVIA_SEV_` - Tranvía Sevilla

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
| 30 | Santander |
| 31 | Bilbao |
| 32 | San Sebastián |
| 40 | Zaragoza |
| 50 | Barcelona (Rodalies) |
| 60 | Valencia |
| 61 | Murcia/Alicante |
| 62 | Castellón |
| 70 | Sevilla |
| 71 | Cádiz |
| 72 | Málaga |

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
| `TRANVIA_SEV` | `TRANVIA_SEV_*` | `TRANVIA_SEV_T1` |
| `METRO_` | `METRO_*` | `METRO_L1` |
| `ML_` | `ML_*` | `ML_ML1` |
