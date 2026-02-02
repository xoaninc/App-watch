# Reemplazo de Segmentos de Shape con OSM Ways

Documentación del proceso para corregir shapes GTFS usando datos de OpenStreetMap.

## Caso de Uso

Cuando un shape GTFS tiene una geometría incorrecta (ej: sigue la vía equivocada en una bifurcación), se puede reemplazar el segmento problemático con coordenadas exactas de OpenStreetMap.

## Ejemplo: C1 Asturias - Bifurcación Villabona

### Problema
La línea C1 (Gijón-Oviedo) seguía la vía incorrecta en la bifurcación de Villabona, usando las coordenadas de la línea C3 (San Juan de Nieva) en lugar del Ferrocarril León-Gijón.

### Solución
Reemplazar el segmento con el OSM way correcto: https://www.openstreetmap.org/way/1471586131

## Proceso Paso a Paso

### 1. Identificar el OSM Way correcto

Usar OpenRailwayMap (https://www.openrailwaymap.org) para identificar la vía correcta y obtener el ID del way en OSM.

### 2. Obtener coordenadas del OSM Way

```bash
curl -s "https://api.openstreetmap.org/api/0.6/way/{WAY_ID}/full.json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
way = [e for e in data['elements'] if e['type'] == 'way'][0]
nodes = {e['id']: (e['lat'], e['lon']) for e in data['elements'] if e['type'] == 'node'}

print('Coordenadas del OSM Way:')
for i, nid in enumerate(way['nodes']):
    lat, lon = nodes[nid]
    print(f'({lat:.7f}, {lon:.7f})')
"
```

### 3. Encontrar puntos de conexión en el shape

Identificar dónde empieza y termina el segmento a reemplazar:

```sql
-- Punto de conexión NORTE (justo antes del inicio del OSM way)
SELECT sequence, lat, lon FROM gtfs_shape_points
WHERE shape_id = '{SHAPE_ID}' AND lat > {OSM_WAY_START_LAT}
ORDER BY lat ASC LIMIT 3;

-- Punto de conexión SUR (justo después del final del OSM way)
SELECT sequence, lat, lon FROM gtfs_shape_points
WHERE shape_id = '{SHAPE_ID}' AND lat < {OSM_WAY_END_LAT}
ORDER BY lat DESC LIMIT 3;
```

### 4. Ejecutar el reemplazo

```sql
BEGIN;

-- 1. Eliminar puntos del segmento incorrecto
DELETE FROM gtfs_shape_points
WHERE shape_id = '{SHAPE_ID}'
  AND sequence BETWEEN {SEQ_START} AND {SEQ_END};

-- 2. Calcular desplazamiento de secuencias
-- shift = puntos_nuevos - puntos_eliminados
-- Si shift < 0: secuencias posteriores bajan
-- Si shift > 0: secuencias posteriores suben

-- 3. Desplazar secuencias posteriores
UPDATE gtfs_shape_points
SET sequence = sequence + {SHIFT}
WHERE shape_id = '{SHAPE_ID}' AND sequence > {SEQ_END};

-- 4. Insertar puntos del OSM way
INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon, dist_traveled) VALUES
('{SHAPE_ID}', {SEQ_START}, {LAT1}, {LON1}, 0),
('{SHAPE_ID}', {SEQ_START+1}, {LAT2}, {LON2}, 0),
-- ... más puntos ...
;

-- 5. Verificar
SELECT sequence, lat, lon FROM gtfs_shape_points
WHERE shape_id = '{SHAPE_ID}'
  AND sequence BETWEEN {SEQ_START-2} AND {SEQ_START+NUM_POINTS+2}
ORDER BY sequence;

COMMIT;
```

### 5. Reiniciar servidor

```bash
ssh root@juanmacias.com "systemctl restart renfeserver"
```

## Ejemplo Completo: Way 1471586131 en C1

### Coordenadas del OSM Way (35 puntos)

```sql
INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon, dist_traveled) VALUES
('20_C1', 728, 43.4659077, -5.8302769, 0),
('20_C1', 729, 43.4658210, -5.8303431, 0),
('20_C1', 730, 43.4655730, -5.8305011, 0),
('20_C1', 731, 43.4651032, -5.8307095, 0),
('20_C1', 732, 43.4648857, -5.8307777, 0),
('20_C1', 733, 43.4646776, -5.8308197, 0),
('20_C1', 734, 43.4644058, -5.8308199, 0),
('20_C1', 735, 43.4641621, -5.8308251, 0),
('20_C1', 736, 43.4638847, -5.8307761, 0),
('20_C1', 737, 43.4635204, -5.8306402, 0),
('20_C1', 738, 43.4633914, -5.8305729, 0),
('20_C1', 739, 43.4631477, -5.8304168, 0),
('20_C1', 740, 43.4628572, -5.8301793, 0),
('20_C1', 741, 43.4625997, -5.8298985, 0),
('20_C1', 742, 43.4622510, -5.8294218, 0),
('20_C1', 743, 43.4620244, -5.8290097, 0),
('20_C1', 744, 43.4617883, -5.8283760, 0),
('20_C1', 745, 43.4617876, -5.8283734, 0),
('20_C1', 746, 43.4616395, -5.8277912, 0),
('20_C1', 747, 43.4615791, -5.8274826, 0),
('20_C1', 748, 43.4614826, -5.8269034, 0),
('20_C1', 749, 43.4613250, -5.8260239, 0),
('20_C1', 750, 43.4611862, -5.8251988, 0),
('20_C1', 751, 43.4610580, -5.8244503, 0),
('20_C1', 752, 43.4610019, -5.8241234, 0),
('20_C1', 753, 43.4609755, -5.8239695, 0),
('20_C1', 754, 43.4608948, -5.8234835, 0),
('20_C1', 755, 43.4608021, -5.8229306, 0),
('20_C1', 756, 43.4606836, -5.8222199, 0),
('20_C1', 757, 43.4606060, -5.8217877, 0),
('20_C1', 758, 43.4605605, -5.8214880, 0),
('20_C1', 759, 43.4605176, -5.8212373, 0),
('20_C1', 760, 43.4604219, -5.8207056, 0),
('20_C1', 761, 43.4602796, -5.8200419, 0),
('20_C1', 762, 43.4600776, -5.8193556, 0);
```

### Operación ejecutada

```sql
-- Eliminados: seq 728-807 (80 puntos)
-- Insertados: seq 728-762 (35 puntos del OSM way)
-- Shift: -45 para secuencias >= 808
-- Total shape: 3051 -> 3006 puntos
```

## Script Python para automatizar

```python
import subprocess
import json
import psycopg2

def get_osm_way_coords(way_id: int) -> list[tuple[float, float]]:
    """Obtiene coordenadas de un OSM way."""
    result = subprocess.run([
        'curl', '-s',
        f'https://api.openstreetmap.org/api/0.6/way/{way_id}/full.json'
    ], capture_output=True, text=True)

    data = json.loads(result.stdout)
    way = [e for e in data['elements'] if e['type'] == 'way'][0]
    nodes = {e['id']: (e['lat'], e['lon']) for e in data['elements'] if e['type'] == 'node'}

    return [nodes[nid] for nid in way['nodes']]

def replace_shape_segment(
    conn,
    shape_id: str,
    seq_start: int,
    seq_end: int,
    new_coords: list[tuple[float, float]]
):
    """Reemplaza un segmento de shape con nuevas coordenadas."""
    cur = conn.cursor()

    old_count = seq_end - seq_start + 1
    new_count = len(new_coords)
    shift = new_count - old_count

    # 1. Eliminar segmento antiguo
    cur.execute("""
        DELETE FROM gtfs_shape_points
        WHERE shape_id = %s AND sequence BETWEEN %s AND %s
    """, (shape_id, seq_start, seq_end))

    # 2. Desplazar secuencias posteriores
    if shift != 0:
        cur.execute("""
            UPDATE gtfs_shape_points
            SET sequence = sequence + %s
            WHERE shape_id = %s AND sequence > %s
        """, (shift, shape_id, seq_end))

    # 3. Insertar nuevos puntos
    for i, (lat, lon) in enumerate(new_coords):
        cur.execute("""
            INSERT INTO gtfs_shape_points (shape_id, sequence, lat, lon, dist_traveled)
            VALUES (%s, %s, %s, %s, 0)
        """, (shape_id, seq_start + i, lat, lon))

    conn.commit()
    print(f"Reemplazado: {old_count} puntos -> {new_count} puntos (shift: {shift})")

# Ejemplo de uso:
# coords = get_osm_way_coords(1471586131)
# replace_shape_segment(conn, '20_C1', 728, 807, coords)
```

## Verificación

Después de aplicar cambios, verificar:

1. **Continuidad del shape**: No debe haber saltos bruscos en las coordenadas
2. **Dirección correcta**: Los puntos deben seguir el orden correcto (norte a sur o viceversa)
3. **Visual**: Comprobar en el mapa que la línea sigue la vía correcta

```sql
-- Verificar continuidad alrededor del segmento insertado
SELECT sequence, lat, lon,
  LAG(lat) OVER (ORDER BY sequence) as prev_lat,
  LAG(lon) OVER (ORDER BY sequence) as prev_lon
FROM gtfs_shape_points
WHERE shape_id = '{SHAPE_ID}'
  AND sequence BETWEEN {SEQ_START-5} AND {SEQ_END+5}
ORDER BY sequence;
```

## Recursos

- **OpenRailwayMap**: https://www.openrailwaymap.org - Para identificar vías ferroviarias
- **OpenStreetMap API**: https://wiki.openstreetmap.org/wiki/API_v0.6
- **Overpass API**: Para consultas más complejas de datos OSM
