# Flujo API: Coordenadas → Núcleo → Stops

## Endpoint: `/stops/by-coordinates`

Cuando se llama al endpoint con coordenadas, el sistema sigue este flujo exacto:

### Flow Diagram

```
Coordinates (lat, lon)
        ↓
┌─────────────────────────────────────┐
│ Step 1: Find Province (PostGIS)     │
│ Query: ST_Contains(geometry, point) │
└─────────────────────────────────────┘
        ↓
    ┌───┴───┐
    │       │
   YES     NO
    │       │
    ↓       ↓
Province  Outside Spain
Found     → Return []
    │       (empty list)
    ↓
┌──────────────────────────────────────┐
│ Step 2: Find Nucleo from Mapping     │
│ Query: province.nucleo_id            │
└──────────────────────────────────────┘
    ↓
    ┌───┴─────┐
    │         │
   YES       NO
    │         │
    ↓         ↓
Nucleo    No Renfe Service
Found     → Return []
    │       (empty list)
    ↓
┌──────────────────────────────────────┐
│ Step 3: Get Stops by Nucleo          │
│ Query: SELECT * FROM gtfs_stops      │
│        WHERE nucleo_name = ?         │
└──────────────────────────────────────┘
    ↓
Return List[StopResponse]
```

## Implementation Details

### Step 1: Find Province from Coordinates

```python
from src.gtfs_bc.province.province_lookup import get_province_and_nucleo_by_coordinates

result = get_province_and_nucleo_by_coordinates(db, lat, lon)
# Returns: (province_name, nucleo_name) or None

if not result:
    # Coordinates are outside Spain
    return []
```

**Query SQL:**
```sql
SELECT name, nucleo_name
FROM spanish_provinces
WHERE ST_Contains(
    geometry,
    ST_SetSRID(ST_MakePoint(lon, lat), 4326)
)
LIMIT 1
```

### Step 2: Extract Nucleo from Province Mapping

```python
province_name, nucleo_name = result

if not nucleo_name:
    # Province exists but has no Renfe service
    return []
```

**Examples:**
- Madrid coordinates → Province: "Madrid" → Nucleo: "Madrid"
- Barcelona coordinates → Province: "Barcelona" → Nucleo: "Rodalies de Catalunya"
- Murcia coordinates → Province: "Murcia" → Nucleo: "Murcia/Alicante"
- Almería coordinates → Province: "Almería" → Nucleo: None
- Atlantic Ocean coordinates → Province: None → Return []

### Step 3: Get Stops by Nucleo

```python
stops = (
    db.query(StopModel)
    .filter(StopModel.nucleo_name == nucleo_name)
    .order_by(StopModel.name)
    .limit(limit)
    .all()
)
return stops
```

**Query SQL:**
```sql
SELECT *
FROM gtfs_stops
WHERE nucleo_name = 'Madrid'
ORDER BY name
LIMIT 100
```

## Error Handling

✅ **No Error Cases** - All scenarios return empty list or results, never error

| Scenario | Result |
|----------|--------|
| Coordinates outside Spain | `[]` (empty list) |
| Coordinates in province without Renfe service | `[]` (empty list) |
| Coordinates in valid Renfe province | List of stops in that núcleo |
| Valid coordinates but no stops found | `[]` (empty list) |

**Important**: The endpoint NEVER returns HTTP error. Always returns 200 with empty list if no results.

## Examples

### Example 1: Madrid (Nucleus exists)

```bash
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=40.42&lon=-3.72&limit=5"
```

**Flow:**
1. Coordinates (40.42, -3.72)
2. Province: "Madrid"
3. Nucleo: "Madrid"
4. Returns: 5 stops from Madrid

**Response:**
```json
[
  {
    "id": "ES22001001",
    "name": "Atocha",
    "lat": 40.4054,
    "lon": -3.6925,
    "nucleo_id": 10,
    "nucleo_name": "Madrid",
    ...
  },
  ...
]
```

### Example 2: Barcelona (Rodalies de Catalunya nucleus)

```bash
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=41.38&lon=2.17&limit=5"
```

**Flow:**
1. Coordinates (41.38, 2.17)
2. Province: "Barcelona"
3. Nucleo: "Rodalies de Catalunya"
4. Returns: 5 stops from Rodalies de Catalunya

**Response:**
```json
[
  {
    "id": "08019001",
    "name": "Barcelona Sants",
    "lat": 41.3783,
    "lon": 2.1403,
    "nucleo_id": 50,
    "nucleo_name": "Rodalies de Catalunya",
    ...
  },
  ...
]
```

### Example 3: Almería (No Renfe service)

```bash
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=36.84&lon=-2.40&limit=5"
```

**Flow:**
1. Coordinates (36.84, -2.40)
2. Province: "Almería"
3. Nucleo: None (no Renfe service)
4. Returns: empty list

**Response:**
```json
[]
```

### Example 4: Atlantic Ocean (Outside Spain)

```bash
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=30.0&lon=-30.0&limit=5"
```

**Flow:**
1. Coordinates (30.0, -30.0)
2. Province: None (outside Spain)
3. Returns: empty list

**Response:**
```json
[]
```

### Example 5: Murcia/Alicante (Multi-province nucleus)

```bash
# Murcia
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=37.99&lon=-1.13&limit=5"

# Alicante
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=38.35&lon=-0.48&limit=5"
```

Both return stops from "Murcia/Alicante" nucleus:

**Response:**
```json
[
  {
    "id": "30029001",
    "name": "Murcia",
    "lat": 37.9922,
    "lon": -1.1307,
    "nucleo_id": 41,
    "nucleo_name": "Murcia/Alicante",
    ...
  },
  ...
]
```

## Special Cases

### Rodalies de Catalunya (Nucleus 50)

Covers 4 provinces but same nucleus:

```bash
# Barcelona
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=41.38&lon=2.17"
# Returns: stops from "Rodalies de Catalunya"

# Tarragona
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=41.12&lon=1.25"
# Returns: stops from "Rodalies de Catalunya"

# Lleida
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=41.61&lon=0.63"
# Returns: stops from "Rodalies de Catalunya"

# Girona
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=41.98&lon=2.82"
# Returns: stops from "Rodalies de Catalunya"
```

### Murcia/Alicante (Nucleus 41)

Covers 2 provinces but same nucleus:

```bash
# Murcia
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=37.99&lon=-1.13"
# Returns: stops from "Murcia/Alicante"

# Alicante
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=38.35&lon=-0.48"
# Returns: stops from "Murcia/Alicante"
```

## Database Tables Involved

### 1. spanish_provinces (PostGIS geometry)

```sql
SELECT id, code, name, nucleo_id, nucleo_name
FROM spanish_provinces
WHERE name = 'Madrid'
```

**Result:**
```
id   code  name    nucleo_id  nucleo_name
---  ----  -----   ---------  -----------
28   28    Madrid  10         Madrid
```

### 2. gtfs_nucleos (Master table)

```sql
SELECT id, name
FROM gtfs_nucleos
WHERE id = 10
```

**Result:**
```
id   name
--   -----
10   Madrid
```

### 3. gtfs_stops (Contains stops with nucleo_id)

```sql
SELECT id, name, nucleo_id, nucleo_name, province
FROM gtfs_stops
WHERE nucleo_name = 'Madrid'
LIMIT 5
```

**Result:**
```
id          name          nucleo_id  nucleo_name  province
----------  ----------    ---------  -----------  ---------
ES22001001  Atocha        10         Madrid       Madrid
ES22001002  Chamartín     10         Madrid       Madrid
ES22001003  Delicias      10         Madrid       Madrid
...
```

## API Contract

### Request

```
GET /api/v1/gtfs/stops/by-coordinates
Query Parameters:
  - lat: float (required, -90 to 90)
  - lon: float (required, -180 to 180)
  - limit: int (optional, default 100, max 1000)
```

### Response

```
HTTP 200 OK
Content-Type: application/json

[
  {
    "id": string,
    "name": string,
    "lat": float,
    "lon": float,
    "code": string | null,
    "location_type": int,
    "parent_station_id": string | null,
    "zone_id": string | null,
    "province": string | null,
    "nucleo_id": int | null,
    "nucleo_name": string | null,
    "parking_bicis": string | null,
    "accesibilidad": string | null,
    "cor_bus": string | null,
    "cor_metro": string | null
  },
  ...
]
```

### No Error Scenarios

All edge cases return `200 OK` with data or empty array:
- ✅ Outside Spain → `200 []`
- ✅ Province without service → `200 []`
- ✅ No stops found → `200 []`
- ✅ Invalid coordinates → HTTP validation error (coordinates validation)
- ✅ Valid coords, valid nucleus → `200 [stops]`

## Testing Checklist

- [ ] Coordinates in Madrid → Returns Madrid stops
- [ ] Coordinates in Barcelona → Returns Rodalies de Catalunya stops
- [ ] Coordinates in Murcia → Returns Murcia/Alicante stops
- [ ] Coordinates in Almería → Returns empty list (no error)
- [ ] Coordinates in Atlantic → Returns empty list (no error)
- [ ] Check all 4 Catalonia provinces return same nucleus
- [ ] Check both Murcia/Alicante provinces return same nucleus
- [ ] Verify nucleo_name matches in response
- [ ] Verify stops are ordered by name
- [ ] Verify limit parameter works correctly
