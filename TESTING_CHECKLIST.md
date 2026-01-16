# Testing Checklist: Núcleo System

## Ambiente: Producción (juanmacias.com)

Como PostgreSQL no está disponible en desarrollo local, los tests se ejecutarán directamente en producción (juanmacias.com:8002).

## Pre-Testing Checklist

- [ ] Backup de base de datos realizado
- [ ] SSH acceso a juanmacias.com confirmado
- [ ] Virtualenv disponible en `/var/www/renfeserver/.venv`
- [ ] Git cambios committeados y pushed

## Phase 1: Migrations Testing

### Comando
```bash
cd /var/www/renfeserver
alembic current
alembic upgrade head
alembic current
```

### Verificaciones
- [ ] Migration 008 ejecutada (gtfs_nucleos table created)
- [ ] Migration 009 ejecutada (nucleo fields added to gtfs_stops)
- [ ] Migration 010 ejecutada (nucleo fields added to gtfs_routes)
- [ ] Migration 011 ejecutada (nucleo fields added to spanish_provinces)
- [ ] Alembic current muestra revision = '011'

### SQL Verification (connect to database)
```sql
-- Verificar tablas
\dt gtfs_nucleos
\dt gtfs_stops
\dt gtfs_routes
\dt spanish_provinces

-- Verificar columnas
\d gtfs_nucleos
\d gtfs_stops
\d gtfs_routes
\d spanish_provinces

-- Verificar índices
SELECT * FROM pg_indexes WHERE tablename = 'gtfs_nucleos';
SELECT * FROM pg_indexes WHERE tablename = 'spanish_provinces';
```

**Expected Results:**
- gtfs_nucleos table exists with 10 columns
- gtfs_stops has nucleo_id, nucleo_name, + amenity fields
- gtfs_routes has nucleo_id, nucleo_name, renfe_idlinea, geometry
- spanish_provinces has nucleo_id, nucleo_name columns

## Phase 2: Data Import Testing

### Step 1: Import Renfe Nucleos

```bash
python scripts/import_renfe_nucleos.py
```

**Expected Output:**
```
INFO: Starting Renfe GeoJSON import...
INFO: Downloading Renfe GeoJSON files...
INFO: Extracting nucleos from estaciones data...
INFO: Importing nucleos into database...

INFO: ======================================================
INFO: Import Summary
INFO: ======================================================
INFO: Nucleos created: 12
INFO: Nucleos updated: 0
INFO: Stops updated: 791 (or fewer, depends on matching)
INFO: Stops not matched: X
INFO: Routes updated: 69 (or fewer)
INFO: Routes not matched: X
INFO: ======================================================

INFO: Renfe GeoJSON import completed successfully!
```

**Verification:**
```sql
SELECT COUNT(*) FROM gtfs_nucleos;
-- Should return: 12

SELECT name FROM gtfs_nucleos ORDER BY id;
-- Should return 12 nucleos:
-- Madrid
-- Asturias
-- Sevilla
-- Cádiz
-- Málaga
-- Valencia
-- Murcia/Alicante
-- Rodalies de Catalunya
-- Bilbao
-- San Sebastián
-- Cantabria
-- Zaragoza

SELECT nucleo_name, COUNT(*) FROM gtfs_stops WHERE nucleo_id IS NOT NULL GROUP BY nucleo_name ORDER BY nucleo_name;
-- Should show all 12 nucleos with stop counts
```

### Step 2: Populate Stops with Nucleos

```bash
python scripts/populate_stops_nucleos.py
```

**Expected Output:**
```
INFO: Processing 1092 stops (force_update=False)
...
INFO: Processed 1092/1092 stops

INFO: ==================================================
INFO: Stop Population Summary
INFO: ==================================================
INFO: Total stops processed: 1092
INFO: Updated: 1000+ (depends on matching)
INFO: Unchanged: X
INFO: Not found: X
INFO: ==================================================

INFO: Nucleo distribution:
  Madrid: 95 stops
  Asturias: 149 stops
  ...
  Zaragoza: 6 stops

INFO: Stop population completed successfully
```

**Verification:**
```sql
SELECT nucleo_name, COUNT(*) as stops
FROM gtfs_stops
WHERE nucleo_id IS NOT NULL
GROUP BY nucleo_name
ORDER BY stops DESC;

-- Should show approximately:
-- Rodalies de Catalunya: ~200 stops
-- Asturias: ~150 stops
-- Madrid: ~95 stops
-- Valencia: ~70 stops
-- Bilbao: ~60 stops
-- Cantabria: ~60 stops
-- Barcelona: ~50 stops
-- ... others
```

### Step 3: Populate Routes with Nucleos

```bash
python scripts/populate_routes_nucleos.py
```

**Expected Output:**
```
INFO: Processing X routes (force_update=False)
...

INFO: ==================================================
INFO: Route Population Summary
INFO: ==================================================
INFO: Total routes processed: 75
INFO: Updated: 70+ (depends on matching)
INFO: Unchanged: X
INFO: Not found: X
INFO: ==================================================

INFO: Route distribution:
  Rodalies de Catalunya: 19 lines
  Madrid: 13 lines
  ...
```

**Verification:**
```sql
SELECT nucleo_name, COUNT(*) as routes
FROM gtfs_routes
WHERE nucleo_id IS NOT NULL
GROUP BY nucleo_name
ORDER BY routes DESC;

-- Should show approximately:
-- Rodalies de Catalunya: 19
-- Madrid: 13
-- Asturias: 9
-- Valencia: 6
-- ... others
```

### Step 4: Populate Province-Nucleo Mapping

```bash
python scripts/populate_province_nucleo_mapping.py
```

**Expected Output:**
```
INFO: Starting province-nucleo mapping population...
...

INFO: ==================================================
INFO: Province Mapping Summary
INFO: ==================================================
INFO: Total provinces: 52
INFO: Mapped: 14
INFO: Not mapped: 38
INFO: Errors: 0
INFO: ==================================================

INFO: Province to Nucleo Mapping:
  Madrid: 1 province
  Murcia/Alicante: 2 provinces (Murcia, Alicante)
  Rodalies de Catalunya: 4 provinces (Barcelona, Tarragona, Lleida, Girona)
  ... others

INFO: Unmapped provinces (no Renfe service):
  - Almería
  - Ávila
  - ... (38 total)
```

**Verification:**
```sql
SELECT nucleo_name, GROUP_CONCAT(name) as provinces
FROM spanish_provinces
WHERE nucleo_id IS NOT NULL
GROUP BY nucleo_name
ORDER BY nucleo_name;

-- Should show 12 mappings with provinces

SELECT COUNT(*) FROM spanish_provinces WHERE nucleo_name IS NOT NULL;
-- Should return: 14 (14 provinces with Renfe service)

SELECT COUNT(*) FROM spanish_provinces WHERE nucleo_name IS NULL;
-- Should return: 38 (38 provinces without Renfe service)
```

## Phase 3: Validation Testing

### Step 1: Validate Nucleos

```bash
python scripts/validate_nucleos.py
```

**Expected Output:**
```
✓ PASS: PostGIS extension enabled
✓ PASS: Nucleos table exists
✓ PASS: Nucleos count (should be 12) - Found 12 nucleos
✓ PASS: Nucleos have complete data
✓ PASS: Stop coverage (≥95%) - 1050/1092 (96.2%)
✓ PASS: Route coverage (≥90%) - 70/75 (93.3%)
✓ PASS: Foreign key relationships - Invalid stop FKs: 0, Invalid route FKs: 0
✓ PASS: Query performance - Query time: X.XXms

Validation Summary
Total checks: 10
Passed: 10
Failed: 0
Warnings: 0

✓ All validation checks passed!
```

**All checks must PASS** ✅

### Step 2: Validate Province-Nucleo Mapping

```bash
python scripts/validate_province_nucleo_mapping.py
```

**Expected Output:**
```
✓ PASS: Mapping columns exist - Found 2/2 mapping columns
✓ PASS: Provinces mapped - 14 mapped
✓ PASS: Mapping for Madrid - Madrid (id: 10)
✓ PASS: Mapping for Barcelona - Rodalies de Catalunya (id: 50)
✓ PASS: Mapping for Murcia - Murcia/Alicante (id: 41)
✓ PASS: Mapping for Alicante - Murcia/Alicante (id: 41)
✓ PASS: Mapping for Vizcaya - Bilbao (id: 60)
✓ PASS: Foreign key integrity - Invalid foreign keys: 0
✓ PASS: Murcia/Alicante coverage - Covers 2/2 provinces
✓ PASS: Rodalies de Catalunya coverage - Covers 4/4 provinces

Validation Summary
Total checks: 10
Passed: 10
Failed: 0
Warnings: 0

✓ Province-nucleo mapping is valid!
```

**All checks must PASS** ✅

### Step 3: Validate Existing Province System

```bash
python scripts/validate_provinces.py
```

**Expected Output:**
```
✓ PASS: PostGIS extension enabled
✓ PASS: Provinces table exists
✓ PASS: Provinces count (45-55) - Found 52 provinces
✓ PASS: All geometries valid - 0 invalid geometries
✓ PASS: Spatial index exists
✓ PASS: Coordinate test: Madrid - Province: Madrid
✓ PASS: Coordinate test: Barcelona - Province: Barcelona
✓ PASS: Coordinate test: Valencia - Province: Valencia
✓ PASS: Coordinate test: Seville - Province: Sevilla
✓ PASS: Coordinate test: Bilbao - Province: Vizcaya
✓ PASS: Invalid coordinates (Atlantic) - Correctly returned None
✓ PASS: Query performance (<10ms avg) - Avg: X.XXms, Max: X.XXms
✓ PASS: Stop coverage (≥95%) - 1092/1092 (100.0%)

Validation Summary
Total checks: 13
Passed: 13
Failed: 0
Warnings: 0

✓ All validation checks passed!
```

**All checks must PASS** ✅

## Phase 4: API Testing

### Pre-test: Restart FastAPI Service

```bash
sudo systemctl restart renfe-api
sleep 3
sudo systemctl status renfe-api
```

### Test 1: Get Nucleos List

```bash
curl "https://juanmacias.com:8002/api/v1/gtfs/nucleos" | jq '.' | head -50
```

**Expected Response:**
- 12 nucleos objects
- Each with: id, name, color, bounding_box_*, center_*, stations_count, lines_count
- Example:
```json
[
  {
    "id": 10,
    "name": "Madrid",
    "color": "215,0,30",
    "bounding_box_min_lat": 40.1,
    "bounding_box_max_lat": 40.8,
    "bounding_box_min_lon": -3.9,
    "bounding_box_max_lon": -3.5,
    "center_lat": 40.4,
    "center_lon": -3.7,
    "stations_count": 95,
    "lines_count": 13
  },
  ...
]
```

**Verify:**
- [ ] Response is 200 OK
- [ ] 12 nucleos returned
- [ ] All have id, name, color, stations_count, lines_count
- [ ] Stations/lines counts are > 0 for all

### Test 2: Get Specific Nucleo (Madrid - id 10)

```bash
curl "https://juanmacias.com:8002/api/v1/gtfs/nucleos/10" | jq '.'
```

**Expected Response:**
```json
{
  "id": 10,
  "name": "Madrid",
  "color": "215,0,30",
  "bounding_box_min_lat": 40.1,
  "bounding_box_max_lat": 40.8,
  "bounding_box_min_lon": -3.9,
  "bounding_box_max_lon": -3.5,
  "center_lat": 40.4,
  "center_lon": -3.7,
  "stations_count": 95,
  "lines_count": 13
}
```

**Verify:**
- [ ] Response is 200 OK
- [ ] Correct nucleo data
- [ ] Accurate station and line counts

### Test 3: Get Nucleos for Rodalies de Catalunya (id 50)

```bash
curl "https://juanmacias.com:8002/api/v1/gtfs/nucleos/50" | jq '.name, .stations_count, .lines_count'
```

**Expected Response:**
```
"Rodalies de Catalunya"
~202
19
```

### Test 4: Coordinates → Nucleo Flow (Madrid)

```bash
# Madrid coordinates (40.42, -3.72)
curl "https://juanmacias.com:8002/api/v1/gtfs/stops/by-coordinates?lat=40.42&lon=-3.72&limit=3" | jq '.[] | {name, nucleo_name, nucleo_id}'
```

**Expected Response:**
```json
[
  {
    "name": "Atocha",
    "nucleo_name": "Madrid",
    "nucleo_id": 10
  },
  {
    "name": "Chamartín",
    "nucleo_name": "Madrid",
    "nucleo_id": 10
  },
  {
    "name": "Delicias",
    "nucleo_name": "Madrid",
    "nucleo_id": 10
  }
]
```

**Verify:**
- [ ] Response is 200 OK
- [ ] Returns stops from Madrid
- [ ] All have nucleo_name = "Madrid"
- [ ] All have nucleo_id = 10
- [ ] Stops are ordered by name

### Test 5: Coordinates → Nucleo Flow (Barcelona / Rodalies)

```bash
# Barcelona coordinates (41.38, 2.17)
curl "https://juanmacias.com:8002/api/v1/gtfs/stops/by-coordinates?lat=41.38&lon=2.17&limit=3" | jq '.[] | {name, nucleo_name, nucleo_id}'
```

**Expected Response:**
```json
[
  {
    "name": "Barcelona Sants",
    "nucleo_name": "Rodalies de Catalunya",
    "nucleo_id": 50
  },
  ...
]
```

**Verify:**
- [ ] Response is 200 OK
- [ ] Returns stops from Rodalies de Catalunya
- [ ] All have nucleo_id = 50

### Test 6: Coordinates → Nucleo Flow (Murcia/Alicante)

```bash
# Murcia coordinates (37.99, -1.13)
curl "https://juanmacias.com:8002/api/v1/gtfs/stops/by-coordinates?lat=37.99&lon=-1.13&limit=3" | jq '.[] | {name, nucleo_name, nucleo_id}'
```

**Expected Response:**
```json
[
  {
    "name": "...",
    "nucleo_name": "Murcia/Alicante",
    "nucleo_id": 41
  },
  ...
]
```

**Verify:**
- [ ] Response is 200 OK
- [ ] Returns stops from Murcia/Alicante nucleus
- [ ] All have nucleo_id = 41

### Test 7: Coordinates → Empty List (Almería - No Service)

```bash
# Almería coordinates (36.84, -2.40) - no Renfe service
curl "https://juanmacias.com:8002/api/v1/gtfs/stops/by-coordinates?lat=36.84&lon=-2.40&limit=3" | jq '.'
```

**Expected Response:**
```json
[]
```

**Verify:**
- [ ] Response is 200 OK (not error!)
- [ ] Returns empty array
- [ ] No error message

### Test 8: Coordinates → Empty List (Atlantic - Outside Spain)

```bash
# Atlantic Ocean (30.0, -30.0) - outside Spain
curl "https://juanmacias.com:8002/api/v1/gtfs/stops/by-coordinates?lat=30.0&lon=-30.0&limit=3" | jq '.'
```

**Expected Response:**
```json
[]
```

**Verify:**
- [ ] Response is 200 OK (not error!)
- [ ] Returns empty array
- [ ] No error message

### Test 9: Get Stops by Nucleo (Madrid)

```bash
curl "https://juanmacias.com:8002/api/v1/gtfs/stops/by-nucleo?nucleo_id=10&limit=3" | jq '.[] | {name, nucleo_name}'
```

**Expected Response:**
```json
[
  {
    "name": "...",
    "nucleo_name": "Madrid"
  },
  ...
]
```

**Verify:**
- [ ] Response is 200 OK
- [ ] Returns stops from Madrid

### Test 10: Get Routes by Nucleo (Rodalies)

```bash
curl "https://juanmacias.com:8002/api/v1/gtfs/routes?nucleo_id=50&limit=5" | jq '.[] | {short_name, nucleo_name}'
```

**Expected Response:**
```json
[
  {
    "short_name": "C1",
    "nucleo_name": "Rodalies de Catalunya"
  },
  {
    "short_name": "C2",
    "nucleo_name": "Rodalies de Catalunya"
  },
  ...
]
```

**Verify:**
- [ ] Response is 200 OK
- [ ] Returns routes from Rodalies
- [ ] All have nucleo_name = "Rodalies de Catalunya"

### Test 11: Get Stops with Amenity Fields

```bash
curl "https://juanmacias.com:8002/api/v1/gtfs/stops/by-coordinates?lat=40.42&lon=-3.72&limit=1" | jq '.[] | {name, parking_bicis, accesibilidad, cor_bus}'
```

**Expected Response:**
```json
{
  "name": "...",
  "parking_bicis": "..." or null,
  "accesibilidad": "Accesible" or null,
  "cor_bus": "..." or null
}
```

**Verify:**
- [ ] Response includes amenity fields
- [ ] Fields are populated (or null if not available)

## Performance Testing

### Query Performance

```bash
# Measure response time for coordinates endpoint
time curl -s "https://juanmacias.com:8002/api/v1/gtfs/stops/by-coordinates?lat=40.42&lon=-3.72&limit=100" > /dev/null
```

**Expected:**
- [ ] Response time < 500ms
- [ ] No database timeout errors

### Database Query Time

```sql
-- Test PostGIS query
EXPLAIN ANALYZE
SELECT name, nucleo_name
FROM spanish_provinces
WHERE ST_Contains(
    geometry,
    ST_SetSRID(ST_MakePoint(-3.72, 40.42), 4326)
)
LIMIT 1;

-- Expected: < 10ms execution time
```

## Regression Testing

Verify that existing functionality still works:

### Test: Province System Still Works

```bash
# Old endpoint should still work
curl "https://juanmacias.com:8002/api/v1/gtfs/stops/by-coordinates?lat=40.42&lon=-3.72&limit=1" | jq '.[] | {province, lat, lon}'
```

**Expected:**
- [ ] Province field still populated
- [ ] Stops grouped by province correctly

### Test: Routes Filtering Still Works

```bash
# Get Madrid routes (old way, without nucleo)
curl "https://juanmacias.com:8002/api/v1/gtfs/routes?search=madrid" | jq '.'
```

**Expected:**
- [ ] Response is 200 OK
- [ ] Filtering works correctly

### Test: Agency Endpoints Still Work

```bash
curl "https://juanmacias.com:8002/api/v1/gtfs/agencies" | jq '.[] | {id, name}'
```

**Expected:**
- [ ] Response is 200 OK
- [ ] Agencies listed correctly

## Summary Checklist

### Phase 1: Migrations
- [ ] All 4 migrations applied successfully
- [ ] Database schema correct

### Phase 2: Data Import
- [ ] 12 nucleos imported
- [ ] 791 stops updated with nucleo data
- [ ] 69 routes updated with nucleo data
- [ ] 14 provinces mapped to nucleos
- [ ] 38 provinces unmapped (no service)

### Phase 3: Validation
- [ ] validate_nucleos.py: All checks PASS
- [ ] validate_province_nucleo_mapping.py: All checks PASS
- [ ] validate_provinces.py: All checks PASS

### Phase 4: API Testing
- [ ] GET /nucleos: Returns 12 nucleos ✓
- [ ] GET /nucleos/{id}: Returns correct nucleo ✓
- [ ] Coordinates → Nucleo flow working ✓
- [ ] Coordinates in no-service province → [] ✓
- [ ] Coordinates outside Spain → [] ✓
- [ ] Special cases (Rodalies, Murcia/Alicante) → [] ✓
- [ ] Amenity fields populated ✓
- [ ] Performance acceptable ✓
- [ ] Existing functionality preserved ✓

### Phase 5: Regression Testing
- [ ] Old province system still works ✓
- [ ] Route filtering still works ✓
- [ ] Agency endpoints still work ✓

## Sign-off

When all checkmarks are complete:

```
Date: [DATE]
Tester: [NAME]
Status: ✅ ALL TESTS PASSED
Ready for production: YES
```

## Troubleshooting

If any test fails, refer to:
1. Check database connection
2. Verify all migrations completed
3. Run validation scripts again
4. Check application logs: `sudo journalctl -u renfe-api -f`
5. Verify environment variables in .env
6. Check database user permissions
