# Corrección de Shapes con OpenStreetMap

## Problema

Los datos GTFS oficiales de RENFE tienen huecos (saltos) en algunos shapes donde faltan puntos intermedios. Esto causa que las líneas se dibujen con saltos bruscos en el mapa.

## Solución

Se crearon scripts que detectan gaps en los shapes y los rellenan usando datos de vías férreas de OpenStreetMap (Overpass API).

## Scripts creados

| Script | Función |
|--------|---------|
| `interpolate_shapes_osm.py` | Detecta gaps y consulta OSM Overpass API |
| `apply_shape_interpolations.py` | Aplica correcciones a archivos GTFS |
| `apply_shape_interpolations_db.py` | Aplica correcciones directamente a la BD |

## Resultado C1 Asturias (20_C1)

| Métrica | Antes | Después |
|---------|-------|---------|
| Puntos totales | 3039 | 3062 |
| Gaps > 300m | 6 | 3 |
| Mayor gap | 935m | 346m |

### Gaps corregidos

| Secuencia | Antes | Después |
|-----------|-------|---------|
| 1638→1639 | 935m | Corregido |
| 269→270 | 777m | Corregido |
| 1639→1640 | 527m | ~346m |
| 267→268 | 418m | Corregido |
| 322→323 | 316m | Corregido |
| 98→99 | 326m | 326m (OSM sin datos) |

## Uso

### Detectar gaps en cualquier shape

```bash
# Detectar todos los gaps > 300m
python scripts/interpolate_shapes_osm.py --detect --gtfs /path/to/shapes.txt

# Detectar gaps en un shape específico
python scripts/interpolate_shapes_osm.py --detect --shape 20_C1 --gtfs /path/to/shapes.txt
```

### Corregir usando OSM

```bash
# Corregir gaps consultando OpenStreetMap
python scripts/interpolate_shapes_osm.py --fix --shape 20_C1 --gtfs /path/to/shapes.txt

# Esto genera: data/shapes_interpolated.json
```

### Aplicar correcciones a la base de datos

```bash
# Ver qué cambios se harían (dry-run)
python scripts/apply_shape_interpolations_db.py --dry-run

# Aplicar los cambios
python scripts/apply_shape_interpolations_db.py

# Aplicar solo a un shape específico
python scripts/apply_shape_interpolations_db.py --shape 20_C1
```

## Archivos generados

- `data/shapes_interpolated.json` - Puntos interpolados pendientes de aplicar
- `data/shapes_merged.json` - Shape completo con interpolaciones (para debug)

## Notas técnicas

- Solo se modifican shapes donde hay saltos > 300m
- Se usa la Overpass API de OpenStreetMap (`railway=rail`)
- Los puntos interpolados se insertan con secuencias decimales y luego se renumeran
- Los datos originales de RENFE no se pierden, solo se añaden puntos intermedios
- Algunos gaps pueden quedar sin corregir si OSM no tiene cobertura en esa zona

## Corrección de Zigzags

Además de los gaps, algunos shapes tienen patrones de "zigzag" donde la línea va y vuelve (apartaderos, vías muertas). Esto causa líneas dobles en el mapa.

### Script

```bash
# Detectar zigzags
python scripts/fix_shape_zigzags.py --detect --shape 20_C1

# Corregir zigzags
python scripts/fix_shape_zigzags.py --fix --shape 20_C1
```

### Resultado C1 Asturias (zigzags)

Se eliminaron **101 puntos** de zigzag, reduciendo el shape de 3062 a 2961 puntos.

Zonas afectadas:
- Calzada de Asturias
- Múltiples apartaderos a lo largo de la línea

## Fecha de aplicación

- **2026-02-01**: Corregido shape 20_C1 (C1 Asturias/Gijón)
  - Interpolación OSM: +23 puntos
  - Eliminación zigzags: -101 puntos
  - Resultado final: 2961 puntos
