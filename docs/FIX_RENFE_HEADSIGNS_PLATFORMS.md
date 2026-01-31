# Fix: Headsigns y Estimación de Vías en Cercanías Renfe

**Fecha:** 2026-01-31
**Problema:** Headsigns vacíos y estimación de vías incorrecta
**Ámbito:** Cercanías Málaga (núcleo 32 / network_id 34T)
**Estado:** RESUELTO

---

## Problema Detectado

### Síntomas
1. En Victoria Kent, todos los trenes mostraban "vía 2" independientemente del destino
2. La estimación de vías no funcionaba correctamente para trenes hacia Málaga Centro

### Diagnóstico

El GTFS estático de Renfe (fomento_transit.zip) tiene el campo `trip_headsign` **vacío** para todos los trips. Esto causaba:

1. Los trips se importaban sin headsign
2. La estimación de vías usa headsign + route para buscar en el histórico de plataformas
3. Sin headsign, el sistema hacía fallback a buscar solo por route, devolviendo la vía más común (ignorando la dirección)

```sql
-- Antes del fix: headsigns vacíos
SELECT headsign, COUNT(*) FROM gtfs_trips
WHERE route_id LIKE 'RENFE_%' AND route_id IN (
    SELECT id FROM gtfs_routes WHERE network_id = '34T'
) GROUP BY headsign;

headsign | count
---------|------
         | 3900   -- Todos vacíos!
```

### Problema Adicional: Naming Mismatch

Incluso después de calcular headsigns, había un problema de naming:
- GTFS Estático (calculado): `Málaga-Centro Alameda` (nombre completo de la parada)
- GTFS-RT (del feed): `Málaga Centro` (nombre abreviado)

El sistema buscaba coincidencia exacta, fallando al encontrar la vía correcta.

---

## Solución Implementada

### Fix Part 1: Calcular Headsigns desde Última Parada

**Archivo:** `scripts/import_gtfs_static.py`

Se añadió la función `build_headsigns_from_last_stop()` que:

1. Lee `stops.txt` para obtener nombres de paradas
2. Lee `stop_times.txt` para encontrar la última parada de cada trip (mayor stop_sequence)
3. Asigna el nombre de esa última parada como headsign del trip

```python
def build_headsigns_from_last_stop(zf: zipfile.ZipFile, route_mapping: dict) -> dict:
    """Build headsign mapping from the last stop of each trip.

    Since Renfe GTFS has empty trip_headsign, we calculate it from the
    last stop name of each trip (the destination).
    """
    # Step 1: Read stops.txt to get stop names
    stop_names = {}
    with zf.open('stops.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        for row in reader:
            stop_names[row['stop_id'].strip()] = row.get('stop_name', '').strip()

    # Step 2: Read stop_times.txt to find last stop of each trip
    trip_last_stop = {}  # trip_id -> (max_sequence, stop_id)
    with zf.open('stop_times.txt') as f:
        reader = csv.DictReader(TextIOWrapper(f, encoding='utf-8'))
        for row in reader:
            trip_id = row['trip_id'].strip()
            sequence = int(row['stop_sequence'].strip())
            if trip_id not in trip_last_stop or sequence > trip_last_stop[trip_id][0]:
                trip_last_stop[trip_id] = (sequence, row['stop_id'].strip())

    # Step 3: Build headsign mapping
    headsigns = {}
    for trip_id, (_, stop_id) in trip_last_stop.items():
        if stop_id in stop_names:
            headsigns[trip_id] = stop_names[stop_id]

    return headsigns
```

**Modificación en `import_trips()`:**
```python
def import_trips(db, zf: zipfile.ZipFile, route_mapping: dict, headsigns: dict = None) -> tuple:
    # ...
    # Use headsign from GTFS if available, otherwise use calculated from last stop
    gtfs_headsign = row.get('trip_headsign', '').strip()
    if gtfs_headsign:
        headsign = gtfs_headsign
    elif headsigns and trip_id in headsigns:
        headsign = headsigns[trip_id]
    else:
        headsign = None
```

**Resultado después del fix:**
```sql
SELECT headsign, COUNT(*) FROM gtfs_trips
WHERE route_id IN (SELECT id FROM gtfs_routes WHERE network_id = '34T')
GROUP BY headsign ORDER BY count DESC;

       headsign        | count
-----------------------+-------
 Málaga-Centro Alameda |  1908
 Fuengirola            |  1536
 Álora                 |   372
 Pizarra               |    60
```

---

### Fix Part 2: Partial Headsign Matching (Solo Málaga)

**Archivo:** `adapters/http/api/gtfs/routers/query_router.py`

**Problema:** El headsign calculado (`Málaga-Centro Alameda`) no coincide exactamente con el del histórico RT (`Málaga Centro`).

**Solución:** Añadir un paso intermedio de búsqueda por coincidencia parcial usando la primera palabra del headsign, pero **SOLO para Cercanías Málaga** donde los destinos son consistentes.

```python
def get_estimated_platform(route_short: str, headsign: str) -> tuple[Optional[str], bool]:
    # 1. Primero: búsqueda exacta por headsign
    platform_counts = db.query(...).filter(
        PlatformHistoryModel.headsign == headsign,
    ).all()

    # 2. Si no hay match exacto Y es Málaga Cercanías: búsqueda parcial
    # SOLO para Málaga (RENFE_544xx, RENFE_545xx) donde destinos son consistentes
    is_malaga_cercanias = any(
        sv.startswith('RENFE_544') or sv.startswith('RENFE_545') or
        sv.startswith('544') or sv.startswith('545')
        for sv in queried_stop_variants
    )
    if not platform_counts and headsign and is_malaga_cercanias:
        first_word = re.split(r'[\s\-]', headsign)[0]  # "Málaga-Centro Alameda" -> "Málaga"
        if first_word and len(first_word) >= 3:
            platform_counts = db.query(...).filter(
                PlatformHistoryModel.headsign.ilike(f"{first_word}%"),
                PlatformHistoryModel.headsign != "Unknown",
            ).all()

    # 3. Fallback: solo por route (sin headsign)
    if not platform_counts:
        platform_counts = db.query(...).filter(
            PlatformHistoryModel.route_short_name == route_short,
        ).all()
```

**Por qué solo Málaga:**
- Málaga Cercanías tiene solo 4 destinos posibles: Fuengirola, Málaga-Centro Alameda, Álora, Pizarra
- Los nombres abreviados del RT siempre empiezan igual que los nombres completos
- En otros núcleos (Madrid, Barcelona, etc.) hay muchos más destinos y el partial matching podría dar resultados incorrectos

---

## Verificación

### Histórico de Plataformas en Victoria Kent
```sql
SELECT headsign, platform, SUM(count) as total
FROM gtfs_rt_platform_history
WHERE stop_id = 'RENFE_54501' AND headsign <> 'Unknown'
GROUP BY headsign, platform;

   headsign    | platform | total
---------------+----------+-------
 Fuengirola    | 1        |   156
 Málaga Centro | 2        |    48
```

### Resultado Esperado
- Trenes hacia **Fuengirola** → Vía 1
- Trenes hacia **Málaga Centro** (o Málaga-Centro Alameda) → Vía 2

---

## Ejecución

```bash
# Reimportar trips de Málaga con headsigns calculados
ssh root@juanmacias.com
cd /var/www/renfeserver
source .venv/bin/activate
PYTHONPATH=/var/www/renfeserver python scripts/import_gtfs_static.py \
    /var/www/renfeserver/data/fomento_transit.zip --nucleo 32

# Reiniciar servidor
systemctl restart renfeserver
```

---

## Fix Part 3: Paradas Faltantes en Itinerario

### Problema

Victoria Kent y Torreblanca no aparecían en el endpoint `/routes/{route_id}/stops` aunque sí existían en la base de datos.

### Diagnóstico

El endpoint usa la tabla `gtfs_stop_route_sequence` para ordenar las paradas. Esta tabla se genera normalmente desde shapes, pero las secuencias de Málaga estaban incompletas:

```sql
-- Antes: C1 solo tenía 15 paradas (faltaban Victoria Kent y Torreblanca)
SELECT COUNT(*) FROM gtfs_stop_route_sequence WHERE route_id = 'RENFE_C1_6';
-- 15 (debían ser 17)
```

### Solución

Regenerar las secuencias directamente desde `gtfs_stop_times`, que tiene el orden correcto de todas las paradas:

```sql
-- Eliminar secuencias existentes
DELETE FROM gtfs_stop_route_sequence
WHERE route_id IN ('RENFE_C1_6', 'RENFE_C2_7');

-- Regenerar desde stop_times (C1)
WITH representative_trip AS (
    SELECT MIN(id) as trip_id FROM gtfs_trips WHERE route_id = 'RENFE_C1_6'
)
INSERT INTO gtfs_stop_route_sequence (route_id, stop_id, sequence)
SELECT 'RENFE_C1_6', st.stop_id, st.stop_sequence
FROM representative_trip rt
JOIN gtfs_stop_times st ON rt.trip_id = st.trip_id;

-- Regenerar desde stop_times (C2)
INSERT INTO gtfs_stop_route_sequence (route_id, stop_id, sequence)
SELECT DISTINCT 'RENFE_C2_7', st.stop_id, st.stop_sequence
FROM gtfs_trips t
JOIN gtfs_stop_times st ON t.id = st.trip_id
WHERE t.route_id = 'RENFE_C2_7'
AND t.id = '3210X23151C2';  -- Trip representativo
```

### Resultado

```
=== C1: 17 paradas ===
 1 Fuengirola
 2 Los Boliches
 3 Torreblanca        <<<
 ...
15 Victoria Kent      <<<
16 Málaga-María Zambrano
17 Málaga Centro

=== C2: 9 paradas ===
 1 Málaga Centro
 2 Málaga-María Zambrano
 3 Victoria Kent      <<<
 ...
 9 Álora
```

---

## Notas

- Este fix es específico para núcleos donde Renfe tiene `trip_headsign` vacío
- El partial matching está limitado a Málaga para evitar falsos positivos en otros núcleos
- Si Renfe actualiza su GTFS para incluir headsigns, el código usará esos valores preferentemente
- El histórico de plataformas seguirá acumulando datos con los headsigns del RT
- Las secuencias de paradas se regeneraron desde stop_times porque los shapes no incluían todas las paradas
