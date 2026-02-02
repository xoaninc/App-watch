# Interpolación de Shapes con OpenStreetMap

## Problema

Los datos GTFS oficiales de RENFE tienen huecos (saltos) en algunos shapes donde faltan puntos intermedios. Esto causa que las líneas se dibujen con saltos bruscos en el mapa.

### Shapes afectados identificados

| Shape | Secuencia | Distancia | Zona |
|-------|-----------|-----------|------|
| 20_C1 | 98→99 | 449m | Gijón |
| 20_C1 | 267→268 | 503m | Gijón |
| 20_C1 | 268→269 | 342m | Gijón |
| 20_C1 | 269→270 | 933m | Gijón |
| 20_C1 | 322→323 | 416m | Gijón |
| 20_C1 | 1638→1639 | 937m | La Pereda-Riosa |
| 20_C1 | 1639→1640 | 528m | La Pereda-Riosa |

## Solución

Usar la API Overpass de OpenStreetMap para obtener los nodos de las vías férreas (`railway=rail`) en las zonas donde hay saltos, e interpolar los puntos faltantes.

### Proceso

1. **Detección**: Identificar saltos > 300m entre puntos consecutivos del shape
2. **Consulta OSM**: Usar Overpass API para obtener nodos de vía férrea en el bounding box del salto
3. **Filtrado**: Seleccionar solo los nodos que están entre los dos puntos del salto
4. **Inserción**: Añadir los puntos interpolados con secuencias intermedias (ej: 98.1, 98.2, etc.)

### API Overpass

```
[out:json];
way["railway"="rail"]({{bbox}});
(._;>;);
out body;
```

### Script

`scripts/interpolate_shapes_osm.py`

### Uso

```bash
# Detectar saltos sin corregir
python scripts/interpolate_shapes_osm.py --detect

# Corregir saltos usando OSM
python scripts/interpolate_shapes_osm.py --fix

# Corregir un shape específico
python scripts/interpolate_shapes_osm.py --fix --shape 20_C1
```

## Notas

- Solo se modifican shapes donde hay saltos > 300m
- Los datos originales de RENFE no se eliminan, solo se añaden puntos intermedios
- Los puntos interpolados se marcan con secuencias decimales para preservar el orden
- Se mantiene un log de las interpolaciones realizadas

## Limitaciones

- OSM puede no tener cobertura completa de todas las vías
- Las vías en OSM pueden no coincidir exactamente con el trazado real de RENFE
- Algunos tramos pueden tener múltiples vías paralelas (requiere filtrado manual)
