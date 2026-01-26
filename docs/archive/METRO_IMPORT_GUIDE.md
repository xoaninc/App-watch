# Guía de Importación de Metro Madrid, Metro Ligero y Metro de Sevilla

## Resumen de Datos

### Metro Madrid
- **Agency ID**: `METRO_MADRID`
- **Route IDs**: `METRO_1`, `METRO_2`, ... `METRO_12`, `METRO_R`
- **Stop IDs**: `METRO_{codigo}` (ej: `METRO_44`)
- **short_name**: `L1`, `L2`, ... `L12`, `R` (con prefijo L excepto Ramal)
- **Líneas**: 13 (L1-L12 + R)
- **Estaciones**: ~242 (deduplicadas)

### Metro Ligero
- **Agency ID**: `METRO_LIGERO`
- **Route IDs**: `ML_ML1`, `ML_ML2`, `ML_ML3`, `ML_ML4`
- **Stop IDs**: `ML_{codigo}` (ej: `ML_1`)
- **short_name**: `ML1`, `ML2`, `ML3`, `ML4`
- **Líneas**: 4
- **Estaciones**: ~56

### Metro de Sevilla
- **Agency ID**: `METRO_SEV_MSVQL1`
- **Route IDs**: `METRO_SEV_L1_CE_OQ`
- **Stop IDs**: `METRO_SEV_L1_E{n}` (ej: `METRO_SEV_L1_E1`)
- **short_name**: `L1`
- **Líneas**: 1 (Línea 1)
- **Estaciones**: 21 (Ciudad Expo - Olivar de Quintos)
- **Nucleo**: Sevilla (id=30)
- **Fuente**: GTFS de Metro de Sevilla

---

## Scripts de Importación

### 1. Importar estaciones y rutas de Metro/ML
```bash
cd /var/www/renfeserver
source .venv/bin/activate
PYTHONPATH=/var/www/renfeserver python scripts/import_metro.py
```

**Fuente de datos**: CRTM Feature Service (ArcGIS)
- Metro: https://services5.arcgis.com/.../M4_Red/FeatureServer/
- ML: https://services5.arcgis.com/.../M10_Red/FeatureServer/

### 2. Importar frecuencias de Metro/ML
```bash
python scripts/import_metro_frequencies.py <metro_gtfs_path> [ml_gtfs_path]

# Ejemplo:
python scripts/import_metro_frequencies.py ./data/google_transit_M4.zip ./data/google_transit_M10.zip
```

**Fuente de datos**: GTFS de CRTM
- Descargar de: https://www.crtm.es/tu-transporte-publico/metro/

### 2b. Importar Metro de Sevilla
```bash
python scripts/import_metro_sevilla.py <gtfs_folder_path>

# Ejemplo:
python scripts/import_metro_sevilla.py ./data/20251211_130028_Metro_Sevilla
```

**Fuente de datos**: GTFS de Metro de Sevilla
- Descargar de: https://www.metro-sevilla.es/
- Incluye: agency, routes, stops, frequencies
- El script importa estaciones (location_type=1) y frecuencias automáticamente
- Soporta wheelchair_boarding

### 3. Poblar correspondencias (cor_metro, cor_ml, cor_cercanias)
```bash
python scripts/populate_stop_connections.py [max_distance_meters]

# Por defecto: 150 metros
python scripts/populate_stop_connections.py
python scripts/populate_stop_connections.py 200  # Para 200m
```

**Este script**:
- Calcula paradas cercanas (<150m por defecto)
- Añade `cor_metro` y `cor_ml` a paradas RENFE
- Añade `cor_cercanias` a paradas de Metro/ML

---

## Campos de Correspondencias

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `cor_metro` | Líneas de Metro cercanas | `"1, 10"` |
| `cor_ml` | Líneas de Metro Ligero cercanas | `"2"` |
| `cor_cercanias` | Líneas de Cercanías cercanas | `"C1, C10, C2"` |
| `cor_bus` | Líneas de bus cercanas (reservado) | - |

---

## Deduplicación de Estaciones

El importador deduplica estaciones por nombre normalizado:
- Estaciones con correspondencia (ej: Sol) aparecen una vez
- Las líneas se fusionan automáticamente
- Ejemplo: Sol tiene `lineas: "1,2,3"` (no 3 registros separados)

---

## Nomenclatura de IDs

### Rutas
| Tipo | Formato ID | short_name |
|------|-----------|------------|
| Metro Madrid | `METRO_{num}` | `L{num}` |
| Metro Ramal | `METRO_R` | `R` |
| Metro Ligero | `ML_ML{num}` | `ML{num}` |
| Metro Sevilla | `METRO_SEV_L1_CE_OQ` | `L1` |
| Cercanías | `RENFE_C{num}_{nucleo}` | `C{num}` |

### Paradas
| Tipo | Formato ID |
|------|-----------|
| Metro Madrid | `METRO_{codigo}` |
| Metro Ligero | `ML_{codigo}` |
| Metro Sevilla | `METRO_SEV_L1_E{n}` |
| Cercanías | `RENFE_{codigo}` |

---

## Paradas Renombradas (Intercambiadores)

Para distinguir estaciones de Cercanías de Metro en intercambiadores:

| Original | Renombrado |
|----------|------------|
| Chamartín-Clara Campoamor | Chamartín RENFE |
| Atocha Cercanías | Atocha RENFE |
| Príncipe Pío | Príncipe Pío RENFE |
| Méndez Álvaro | Méndez Álvaro RENFE |

**SQL para renombrar**:
```sql
UPDATE gtfs_stops SET name = 'Chamartín RENFE' WHERE id LIKE 'RENFE_%' AND name LIKE 'Chamart%';
UPDATE gtfs_stops SET name = 'Atocha RENFE' WHERE id LIKE 'RENFE_%' AND name LIKE 'Atocha%';
UPDATE gtfs_stops SET name = 'Príncipe Pío RENFE' WHERE id LIKE 'RENFE_%' AND name = 'Príncipe Pío';
UPDATE gtfs_stops SET name = 'Méndez Álvaro RENFE' WHERE id LIKE 'RENFE_%' AND name = 'Méndez Álvaro';
```

---

## Orden de Importación Recomendado

1. **Importar GTFS de Renfe** (Cercanías)
   ```bash
   python scripts/import_gtfs_static.py
   ```

2. **Importar Metro/ML**
   ```bash
   python scripts/import_metro.py
   ```

3. **Importar frecuencias de Metro** (opcional)
   ```bash
   python scripts/import_metro_frequencies.py <gtfs_metro> <gtfs_ml>
   ```

4. **Poblar correspondencias**
   ```bash
   python scripts/populate_stop_connections.py
   ```

5. **Renombrar intercambiadores** (SQL manual)

6. **Reiniciar servicio**
   ```bash
   systemctl restart renfeserver
   ```

---

## Validación Post-Importación

### Verificar conteos
```sql
-- Paradas por tipo (Madrid)
SELECT
  CASE
    WHEN id LIKE 'RENFE_%' THEN 'Cercanías'
    WHEN id LIKE 'METRO_%' AND id NOT LIKE 'METRO_SEV%' THEN 'Metro Madrid'
    WHEN id LIKE 'ML_%' THEN 'Metro Ligero'
  END as tipo,
  COUNT(*) as total
FROM gtfs_stops
WHERE nucleo_name = 'Madrid'
GROUP BY 1;

-- Paradas Metro Sevilla
SELECT COUNT(*) as total
FROM gtfs_stops
WHERE id LIKE 'METRO_SEV_%';

-- Rutas por tipo
SELECT
  CASE
    WHEN id LIKE 'RENFE_%' THEN 'Cercanías'
    WHEN id LIKE 'METRO_SEV_%' THEN 'Metro Sevilla'
    WHEN id LIKE 'METRO_%' THEN 'Metro Madrid'
    WHEN id LIKE 'ML_%' THEN 'Metro Ligero'
  END as tipo,
  COUNT(*) as total
FROM gtfs_routes
GROUP BY 1;
```

### Verificar correspondencias
```sql
-- Paradas con correspondencias
SELECT name, cor_metro, cor_ml
FROM gtfs_stops
WHERE id LIKE 'RENFE_%' AND (cor_metro IS NOT NULL OR cor_ml IS NOT NULL)
ORDER BY name;

-- Metro con conexiones a Cercanías
SELECT name, lineas, cor_cercanias
FROM gtfs_stops
WHERE id LIKE 'METRO_%' AND cor_cercanias IS NOT NULL
ORDER BY name;
```

### API Tests
```bash
# Verificar orden por distancia (Madrid)
curl "https://redcercanias.com/api/v1/gtfs/stops/by-coordinates?lat=40.4725&lon=-3.6826&limit=5"

# Verificar prefijo L en Metro Madrid
curl "https://redcercanias.com/api/v1/gtfs/routes?nucleo_id=10" | jq '.[] | select(.id | startswith("METRO_")) | {id, short_name}'

# Verificar Metro Sevilla (nucleo_id=30)
curl "https://redcercanias.com/api/v1/gtfs/routes?nucleo_id=30" | jq '.[] | select(.id | startswith("METRO_SEV")) | {id, short_name}'

# Paradas Metro Sevilla
curl "https://redcercanias.com/api/v1/gtfs/stops/by-coordinates?lat=37.38&lon=-5.97&limit=5"
```

---

## Troubleshooting

### Error: "NucleoModel not found"
Asegúrate de importar todos los modelos al inicio del script:
```python
from src.gtfs_bc.nucleo.infrastructure.models import NucleoModel
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel
```

### Paradas duplicadas
El importador deduplica por nombre normalizado. Si hay duplicados:
```sql
-- Ver duplicados
SELECT name, COUNT(*) FROM gtfs_stops WHERE id LIKE 'METRO_%' GROUP BY name HAVING COUNT(*) > 1;

-- Limpiar y reimportar
DELETE FROM gtfs_stop_route_sequence WHERE route_id LIKE 'METRO_%' OR route_id LIKE 'ML_%';
DELETE FROM gtfs_stops WHERE id LIKE 'METRO_%' OR id LIKE 'ML_%';
```

### Correspondencias no aparecen
Ejecutar script de correspondencias después de importar:
```bash
python scripts/populate_stop_connections.py
```

---

## Cambios Importantes (2026-01-17)

1. **SECRET_KEY validation**: La app falla en producción si SECRET_KEY no está configurado
2. **Deduplicación de paradas Metro**: Una parada por estación con líneas fusionadas
3. **Prefijo L en Metro**: short_name usa L1-L12 en vez de 1-12
4. **Campo cor_cercanias**: Nuevo campo para correspondencias Metro → Cercanías
5. **Orden por distancia**: `/stops/by-coordinates` ordena por distancia, no alfabético
6. **Límite por defecto**: Aumentado de 100 a 600 paradas
