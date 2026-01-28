# Walking Shapes - Rutas Peatonales

## Descripción

Sistema para generar y cachear rutas peatonales realistas entre estaciones conectadas (correspondencias). Las rutas siguen aceras, cruces peatonales y caminos reales en lugar de líneas rectas.

## Funcionamiento

### Generación bajo demanda (lazy)

1. Cliente solicita correspondencias con `include_shape=true`
2. Si el shape no está cacheado, se genera usando servicios de routing
3. El shape se guarda en la BD para futuras peticiones
4. Se devuelve el shape junto con distancia y tiempo actualizados

### Servicios de routing

Se prueban en orden hasta que uno funcione:

1. **OSRM** (Open Source Routing Machine) - Más fiable
   - URL: `https://router.project-osrm.org/route/v1/foot/{coords}`
   - Perfil: `foot`

2. **BRouter** (fallback)
   - URL: `https://brouter.de/brouter`
   - Perfil: `trekking`

## API

### Endpoint

```
GET /api/v1/gtfs/stops/{stop_id}/correspondences?include_shape=true
```

### Parámetros

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| include_shape | bool | false | Incluir ruta peatonal |

### Respuesta

```json
{
  "stop_id": "TMB_METRO_1.122",
  "stop_name": "Espanya",
  "correspondences": [
    {
      "id": 123,
      "to_stop_id": "FGC_PE",
      "to_stop_name": "Barcelona - Plaça Espanya",
      "to_lines": "S3, S4, S8, R5, R6",
      "to_transport_types": ["cercanias"],
      "distance_m": 150,
      "walk_time_s": 180,
      "source": "osm",
      "walking_shape": [
        {"lat": 41.375, "lon": 2.149},
        {"lat": 41.3751, "lon": 2.1492},
        ...
      ]
    }
  ]
}
```

## Base de datos

### Columna añadida

```sql
ALTER TABLE stop_correspondence ADD COLUMN walking_shape TEXT;
```

Formato: JSON array de `[[lat, lon], [lat, lon], ...]`

## Scripts

### Pre-generar shapes

Para pre-calentar el cache con las rutas más importantes:

```bash
# Ver qué se generaría
python scripts/pregenerate_walking_shapes.py --dry-run

# Generar todas las pendientes
python scripts/pregenerate_walking_shapes.py

# Generar solo las primeras 50
python scripts/pregenerate_walking_shapes.py --limit 50
```

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `adapters/http/api/gtfs/utils/walking_route.py` | Servicio de routing (OSRM/BRouter) |
| `adapters/http/api/gtfs/routers/query_router.py` | Endpoint de correspondencias |
| `adapters/http/api/gtfs/schemas/stop_schemas.py` | Schema de respuesta |
| `src/gtfs_bc/stop/infrastructure/models/stop_correspondence_model.py` | Modelo con columna walking_shape |
| `scripts/pregenerate_walking_shapes.py` | Script de pre-generación |
| `alembic/versions/034_add_walking_shape_to_correspondence.py` | Migración |

## Filtro de Correspondencias Internas

Las correspondencias entre la misma estación (pasajes internos entre líneas) **no generan walking_shape** porque:
- Son conexiones subterráneas/internas sin ruta de superficie
- No tenemos planos de edificios

El filtro detecta misma estación si:
- Nombres iguales (case insensitive)
- Nombres iguales sin espacios
- Un nombre empieza con el otro

**Ejemplo**: `Nuevos Ministerios L6 ↔ Nuevos Ministerios L8` = interno (sin shape)

## Scripts Adicionales

### Fix C5 Shape

Script para corregir el shape de la línea C5 de Cercanías Sevilla (que terminaba en Bellavista en lugar de Dos Hermanas):

```bash
# Ver qué se haría
python scripts/fix_c5_shape.py --dry-run

# Aplicar corrección
python scripts/fix_c5_shape.py
```

El script genera el shape segmento a segmento usando OSRM/BRouter y actualiza los 1044 trips de la C5.

## Estado

- **Implementado**: 2026-01-28
- **Correspondencias totales**: 250
  - Con walking_shape (externas): 158
  - Sin walking_shape (internas): 92
- **Generación**: Bajo demanda + script opcional
- **Cache**: Persistente en BD
- **Servicios**: BRouter (prioridad) → OSRM (fallback)
