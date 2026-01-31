# Tranvía de Sevilla (Metrocentro) - Shapes

## Información General

- **Operador:** Tussam
- **Línea:** T1
- **Terminus actual:**
  - **Oeste:** Archivo de Indias (lat=37.384682, lon=-5.993986)
  - **Este:** Luis de Morales (lat=37.386017, lon=-5.972504)
- **Shape IDs en BD:**
  - `TRAM_SEV_T1_IDA`
  - `TRAM_SEV_T1_VUELTA`

## Fuente de Datos

Los shapes se obtienen de OpenStreetMap via Overpass Turbo.

### Query Overpass

```
[out:json];
way["railway"="tram"](37.37,-6.0,37.40,-5.97);
out geom;
```

URL: https://overpass-turbo.eu/

Exportar como GeoJSON.

## Estructura de la Línea

La línea T1 tiene dos vías separadas (ida y vuelta) en la mayor parte del recorrido.

### Segmentos por Dirección

**IDA (Archivo de Indias → Luis de Morales):**
- Segmentos con nombre `"T1 - Plaza Nueva - San Bernardo"`
- Túneles: `way/1107321527` + `way/1219525660`
- Tramo este: `way/803753858`

**VUELTA (Luis de Morales → Archivo de Indias):**
- Segmentos con nombre `"T1 - San Bernardo Plaza Nueva"`
- Túnel: `way/1236590036`
- Tramo este: `way/1236590037`

### Túnel (entre San Bernardo y San Francisco Javier)

El túnel está entre lon=-5.9776 y lon=-5.9748. Los segmentos son:

| Way ID | Tipo | Dirección | Rango lon |
|--------|------|-----------|-----------|
| way/1107321529 | Conexión pre-túnel | IDA | -5.9772 → -5.9761 |
| way/1107321527 | Túnel | IDA | -5.9761 → -5.9752 |
| way/1219525660 | Túnel | IDA | -5.9752 → -5.9748 |
| way/1236590036 | Túnel | VUELTA | -5.9748 → -5.9761 |
| way/1236590035 | Conexión post-túnel | VUELTA | -5.9761 → -5.9776 |

## Proceso de Actualización

### 1. Descargar datos de OSM

```bash
# Ir a https://overpass-turbo.eu/
# Ejecutar query y exportar como GeoJSON
# Guardar en /Users/juanmaciasgomez/Downloads/export-2.geojson
```

### 2. Procesar el GeoJSON

```python
import json

with open('/Users/juanmaciasgomez/Downloads/export-2.geojson', 'r') as f:
    geojson = json.load(f)

# Crear diccionario de segmentos
segments = {}
for feature in geojson['features']:
    way_id = feature['properties'].get('@id', '')
    segments[way_id] = feature['geometry']['coordinates']

# Identificar segmentos por nombre
# "T1 - Plaza Nueva - San Bernardo" = IDA
# "T1 - San Bernardo Plaza Nueva" = VUELTA
```

### 3. Construir shapes

**IDA:** Concatenar segmentos de oeste a este
**VUELTA:** Concatenar segmentos de este a oeste

### 4. Filtrar por terminus

Eliminar puntos fuera de los terminus:
- **Oeste:** Excluir puntos con lon < -5.9942 AND lat > 37.3855 (zona Plaza Nueva)
- **Este:** Excluir puntos con lon > -5.974 AND lat > 37.3868 (más allá de Luis de Morales)

### 5. Importar a producción

```bash
# Copiar JSON al servidor
scp /tmp/tram_sevilla_shapes_final.json root@juanmacias.com:/tmp/

# Conectar y ejecutar
ssh root@juanmacias.com

cd /var/www/renfeserver
source .venv/bin/activate

python3 << 'EOF'
import json
from sqlalchemy import create_engine, text

with open('/tmp/tram_sevilla_shapes_final.json', 'r') as f:
    data = json.load(f)

engine = create_engine('postgresql://renfeserver:renfeserver@localhost:5432/renfeserver_prod')

with engine.begin() as conn:
    # Eliminar shapes existentes
    conn.execute(text("DELETE FROM gtfs_shape_points WHERE shape_id IN ('TRAM_SEV_T1_IDA', 'TRAM_SEV_T1_VUELTA')"))

    # Insertar nuevos
    for direction, shape_id in [('ida', 'TRAM_SEV_T1_IDA'), ('vuelta', 'TRAM_SEV_T1_VUELTA')]:
        points = data[direction]
        for seq, (lon, lat) in enumerate(points):
            conn.execute(text(
                "INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon) VALUES (:shape_id, :seq, :lat, :lon)"
            ), {'shape_id': shape_id, 'seq': seq, 'lat': lat, 'lon': lon})
        print(f'{shape_id}: {len(points)} puntos')

print('OK')
EOF

# Reiniciar servidor
systemctl restart renfeserver
```

## Verificación

```sql
-- Contar puntos
SELECT shape_id, COUNT(*), MIN(lon), MAX(lon)
FROM gtfs_shape_points
WHERE shape_id LIKE 'TRAM_SEV%'
GROUP BY shape_id;

-- Esperado:
-- TRAM_SEV_T1_IDA: ~108 puntos, lon de -5.994 a -5.973
-- TRAM_SEV_T1_VUELTA: ~119 puntos, lon de -5.994 a -5.973
```

## Historial

| Fecha | Cambio |
|-------|--------|
| 2026-01-29 | Corregidos shapes: cortados en Archivo de Indias y Luis de Morales, añadido túnel |

## Notas

- La línea se acortó en 2024, ya no llega a Plaza Nueva
- El terminus oeste actual es Archivo de Indias
- El túnel pasa por debajo del centro, entre San Bernardo y San Francisco Javier
