# Importación de GTFS FEVE

## Descripción

El feed GTFS de FEVE (Ferrocarriles de Vía Estrecha) es **separado** del feed principal de Cercanías (`fomento_transit.zip`). Contiene las líneas de cercanías que no están incluidas en el feed principal:

| Red | Línea | Ruta | Región | Color |
|-----|-------|------|--------|-------|
| 45T | C4 | Cartagena - Los Nietos | Murcia | #EF3340 (rojo) |
| 46T | C1 | Ferrol - Ortigueira | Galicia | #EF3340 (rojo) |
| 47T | C1/BUS | León - Cistierna | León | #EF3340 (rojo) |

## Descarga del GTFS

El GTFS de FEVE se descarga desde:
```
https://ssl.renfe.com/ftransit/Fichero_FEVE_FOMENTO/
```

**Nota:** A diferencia de Cercanías, el GTFS de FEVE se distribuye como una **carpeta**, no como un archivo ZIP.

## Uso del script

### Listar redes disponibles

```bash
cd /var/www/renfeserver
source .venv/bin/activate
PYTHONPATH=/var/www/renfeserver python scripts/import_feve_gtfs.py /path/to/RENFE_FEVE/ --list-networks
```

### Importar todas las redes FEVE

```bash
PYTHONPATH=/var/www/renfeserver python scripts/import_feve_gtfs.py /path/to/RENFE_FEVE/
```

### Importar una red específica

```bash
# Solo Galicia (Ferrol - Ortigueira)
PYTHONPATH=/var/www/renfeserver python scripts/import_feve_gtfs.py /path/to/RENFE_FEVE/ --network 46T

# Solo Murcia (Cartagena - Los Nietos)
PYTHONPATH=/var/www/renfeserver python scripts/import_feve_gtfs.py /path/to/RENFE_FEVE/ --network 45T

# Solo León
PYTHONPATH=/var/www/renfeserver python scripts/import_feve_gtfs.py /path/to/RENFE_FEVE/ --network 47T
```

### Limpiar datos existentes antes de importar

```bash
PYTHONPATH=/var/www/renfeserver python scripts/import_feve_gtfs.py /path/to/RENFE_FEVE/ --clear
```

## Contenido del GTFS FEVE

El feed FEVE típicamente contiene:

- **~83 paradas** (stops.txt)
- **~3,700 viajes** (trips.txt)
- **~55,000 stop_times** (stop_times.txt)
- **12 rutas** (routes.txt)
- **93 servicios** (calendar.txt)

**Nota:** El GTFS FEVE **no incluye** `transfers.txt`, por lo que no se importan correspondencias.

## Estructura de IDs

### Stop IDs
- GTFS: `05102`, `05753`, etc. (con ceros iniciales)
- Nuestra DB: `RENFE_5102`, `RENFE_5753` (sin ceros iniciales)

El script maneja automáticamente la conversión de ceros iniciales.

### Route IDs
- GTFS: `45T0001C4`, `46T0001C1`, etc.
- Nuestra DB: `RENFE_C4_45T`, `RENFE_C1_46T`, etc.

### Network IDs
- `45T` - Cartagena (Murcia)
- `46T` - Ferrol (Galicia)
- `47T` - León

## Colores

El GTFS original de Renfe usa cyan (`00FFFF`) para todas las líneas FEVE. Nosotros usamos el color rojo de la C1 (`#EF3340`) que es consistente con otras redes de Cercanías.

El script `import_feve_gtfs.py` importa con el color del GTFS, pero después se actualiza manualmente:

```sql
-- Actualizar colores a rojo C1
UPDATE gtfs_routes SET color = '#EF3340', text_color = '#FFFFFF'
WHERE network_id IN ('45T', '46T', '47T');

UPDATE gtfs_networks SET color = 'EF3340', text_color = 'FFFFFF'
WHERE code IN ('45T', '46T', '47T');
```

## Correspondencias

Las redes FEVE están en zonas rurales sin conexiones con metro u otros sistemas de transporte urbano:
- **Ferrol**: Sin metro ni tranvía
- **Cartagena**: Sin metro ni tranvía
- **León**: Sin metro ni tranvía

Por lo tanto, no hay correspondencias que crear para estas paradas.

## GTFS-RT (Tiempo Real)

**⚠️ IMPORTANTE: Las redes FEVE NO tienen soporte GTFS-RT.**

Renfe no proporciona datos de tiempo real para las redes FEVE:
- El feed `gtfsrt.renfe.com` solo incluye núcleos: 10, 20, 30, 31, 32, 40, 41, 51, 60, 61, 62, 70
- Los núcleos FEVE (45, 46, 47) **no están incluidos**
- El visor `tiempo-real.renfe.com` tampoco tiene datos para estas estaciones

Esto significa que para las líneas FEVE:
- ❌ No hay posiciones de vehículos en tiempo real
- ❌ No hay actualizaciones de retrasos
- ❌ No hay predicción de vías/andenes
- ✅ Los horarios estáticos funcionan correctamente

**Configuración aplicada:**
```sql
-- nucleo_id_renfe configurado (para futura compatibilidad si Renfe añade RT)
UPDATE gtfs_networks SET nucleo_id_renfe = 45 WHERE code = '45T';
UPDATE gtfs_networks SET nucleo_id_renfe = 46 WHERE code = '46T';
UPDATE gtfs_networks SET nucleo_id_renfe = 47 WHERE code = '47T';
```

## Diferencias con el feed de Cercanías

| Aspecto | Cercanías | FEVE |
|---------|-----------|------|
| Archivo | `fomento_transit.zip` | Carpeta `RENFE_FEVE/` |
| Núcleos | 10T, 20T, 30T, etc. | 45T, 46T, 47T |
| Script | `import_gtfs_static.py` | `import_feve_gtfs.py` |
| Redes | Grandes ciudades | Líneas rurales |
| Transfers | Sí incluye | No incluye |

## Verificación post-importación

Después de importar, verificar que las paradas tienen salidas:

```bash
# Ferrol (Galicia) - Estación principal
curl "https://redcercanias.com/api/v1/gtfs/stops/RENFE_5102/departures?limit=5"

# Cartagena (Murcia) - Plaza Bastarreche
curl "https://redcercanias.com/api/v1/gtfs/stops/RENFE_5951/departures?limit=5"

# León - Estación principal
curl "https://redcercanias.com/api/v1/gtfs/stops/RENFE_5753/departures?limit=5"
```

## Limpieza de duplicados

El GTFS de Cercanías y FEVE pueden crear paradas duplicadas con/sin ceros iniciales (ej: `RENFE_05770` y `RENFE_5770`). Para limpiar:

```python
# En Python, ejecutar:
from core.database import SessionLocal
from sqlalchemy import text

with SessionLocal() as db:
    # 1. Migrar stop_times a versión sin ceros
    # 2. Migrar correspondencias
    # 3. Eliminar duplicados
    # Ver script completo en historial
```

**Ejecutado 2026-02-01:**
- Encontrados: 210 duplicados
- Migrados: 1,020 stop_times
- Migradas: 6 correspondencias
- Eliminados: 210 stops duplicados

## Automatización

Para automatizar la actualización, añadir al cron o al script `auto_update_gtfs.py`:

```python
# En auto_update_gtfs.py, añadir:
def update_feve():
    """Update FEVE GTFS data."""
    # Download FEVE GTFS
    feve_url = "https://ssl.renfe.com/ftransit/Fichero_FEVE_FOMENTO/"
    # ... download and extract ...

    # Import
    run_script("import_feve_gtfs.py", feve_folder)

    # Update colors to red
    update_feve_colors()
```

## Troubleshooting

### "Stop not found"
Si aparecen muchos "stop not found", verificar que el mapping de stop_ids maneja correctamente los ceros iniciales.

### "Trip not found"
Verificar que los service_ids del calendario coinciden con los trips.

### Datos desactualizados
Renfe actualiza el GTFS periódicamente. Verificar la fecha de los archivos descargados.

### Paradas duplicadas
Si aparecen paradas duplicadas con/sin ceros, ejecutar el script de limpieza descrito arriba.

## Paradas sin servicio en el GTFS

Algunas paradas existen en el GTFS de Renfe pero **sin servicios programados**:

| Parada | ID | Motivo |
|--------|-----|--------|
| El Chorro-Caminito Del Rey | 54403 | Solo Media Distancia (no Cercanías) |
| Las Mellizas | 54404 | Solo Media Distancia (no Cercanías) |

Estas paradas aparecen en `stops.txt` pero no tienen `stop_times`. El servicio real es de **Media Distancia** (regional), que Renfe no publica en GTFS.

## Historial

- **2026-02-01**: Creación del script de importación FEVE
  - Motivo: Las líneas de Ferrol, Cartagena y León no estaban en el feed principal de Cercanías
  - Importados: 3 redes, 12 rutas, 3,704 trips, 54,971 stop_times
  - Colores actualizados a rojo C1 (#EF3340)
  - Limpiados 210 stops duplicados
