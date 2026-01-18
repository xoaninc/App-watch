# Arquitectura de Networks y Provincias

Este documento describe la estructura de datos para la organización geográfica del transporte público en España.

## Conceptos

### Network (Red de Transporte)
Una red de transporte es una agrupación de servicios bajo un mismo operador o marca. Ejemplos:
- **Rodalies de Catalunya (51T)** - opera en Barcelona, Lleida, Girona, Tarragona
- **Cercanías Madrid (10T)** - opera solo en Madrid
- **Metro de Barcelona (TMB_METRO)** - opera solo en Barcelona
- **FGC** - opera en Barcelona y Lleida

### Provincia (spanish_provinces)
Tabla con los polígonos PostGIS de las 52 provincias españolas para geolocalización.

### Network-Provinces (Relación N:M)
Tabla que relaciona qué redes operan en cada provincia. Permite que:
- Una red opere en múltiples provincias (ej: Rodalies en 4 provincias catalanas)
- Una provincia tenga múltiples redes (ej: Barcelona tiene Rodalies, Metro, FGC, Tram)

## Diagrama de Relaciones

```
┌─────────────────────────────────────────────────────────────────┐
│                      FLUJO DE COORDENADAS                       │
└─────────────────────────────────────────────────────────────────┘

   Usuario envía coordenadas
            │
            ▼
   ┌─────────────────────┐
   │  spanish_provinces  │  ← PostGIS ST_Contains()
   │  (geometría)        │
   └─────────────────────┘
            │
            │ province_code (ej: "BAR")
            ▼
   ┌─────────────────────┐
   │  network_provinces  │  ← Tabla N:M
   │  network_id ←→ province_code
   └─────────────────────┘
            │
            │ network_id (ej: "51T", "TMB_METRO", "FGC")
            ▼
   ┌─────────────────────┐
   │   gtfs_networks     │
   │   (31 redes)        │
   └─────────────────────┘
            │
            │ network_id (FK en routes)
            ▼
   ┌─────────────────────┐
   │    gtfs_routes      │  ← Rutas de cada red
   └─────────────────────┘
```

## Tablas

### spanish_provinces

| Columna | Tipo | Descripción |
|---------|------|-------------|
| code | VARCHAR(5) PK | Código provincia (BAR, MAD, etc.) |
| name | VARCHAR(100) | Nombre de la provincia |
| geometry | MULTIPOLYGON | Polígono PostGIS |

### network_provinces (N:M)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| network_id | VARCHAR(20) PK, FK | Código de red |
| province_code | VARCHAR(5) PK, FK | Código de provincia |

### gtfs_networks

| Columna | Tipo | Descripción |
|---------|------|-------------|
| code | VARCHAR(20) PK | Código único (10T, TMB_METRO, FGC) |
| name | VARCHAR(100) | Nombre de la red |
| region | VARCHAR(100) | Región/comunidad autónoma |
| color | VARCHAR(10) | Color en formato #XXXXXX |
| text_color | VARCHAR(10) | Color del texto |
| logo_url | VARCHAR(500) | URL del logo |
| wikipedia_url | VARCHAR(500) | URL de Wikipedia |
| description | TEXT | Descripción de la red |
| nucleo_id_renfe | INTEGER | ID de núcleo Renfe (solo Cercanías) |

### gtfs_routes

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | VARCHAR(100) PK | ID de la ruta |
| network_id | VARCHAR(20) FK | Referencia a gtfs_networks.code |
| short_name | VARCHAR(50) | Nombre corto (C1, L1, R1) |
| long_name | VARCHAR(255) | Nombre largo |
| ... | ... | ... |

## Mapeo Network → Provincias

### Cercanías Renfe
| Network | Provincias |
|---------|-----------|
| 10T (Madrid) | MAD |
| 20T (Asturias) | AST |
| 30T (Sevilla) | SEV |
| 33T (Cádiz) | CÁD |
| 34T (Málaga) | MÁL |
| 40T (Valencia) | VAL |
| 41T (Murcia/Alicante) | ALI, MUR |
| 51T (Rodalies) | BAR, LLE, GIR, TAR |
| 60T (Bilbao) | VIZ |
| 61T (San Sebastián) | GUI |
| 62T (Santander) | CAN |
| 70T (Zaragoza) | ZAR |
| 90T (C-9 Cotos) | MAD |

### Metro
| Network | Provincias |
|---------|-----------|
| 11T (Metro Madrid) | MAD |
| 12T (ML Madrid) | MAD |
| 32T (Metro Sevilla) | SEV |
| METRO_BILBAO | VIZ |
| TMB_METRO | BAR |
| METRO_VALENCIA | VAL |
| METRO_MALAGA | MÁL |
| METRO_GRANADA | GRA |
| METRO_TENERIFE | SAN |

### Tranvía
| Network | Provincias |
|---------|-----------|
| 31T (Tranvía Sevilla) | SEV |
| TRAM_BCN | BAR |
| TRAM_ALICANTE | ALI |
| TRANVIA_ZARAGOZA | ZAR |
| TRANVIA_MURCIA | MUR |
| TRANVIA_VITORIA | ÁLA |

### Ferrocarril Regional
| Network | Provincias |
|---------|-----------|
| FGC | BAR, LLE |
| EUSKOTREN | VIZ, GUI |
| SFM_MALLORCA | BAL |

## Ejemplos de Uso

### Ejemplo 1: Usuario en Barcelona

**Request:**
```
GET /api/v1/gtfs/coordinates/routes?lat=41.3851&lon=2.1734
```

**Proceso interno:**
```json
{
  "paso_1_coordenadas": {
    "lat": 41.3851,
    "lon": 2.1734
  },

  "paso_2_provincia_detectada": {
    "province_code": "BAR",
    "province_name": "Barcelona"
  },

  "paso_3_networks_en_provincia": [
    {"code": "51T", "name": "Rodalies de Catalunya"},
    {"code": "TMB_METRO", "name": "Metro de Barcelona"},
    {"code": "FGC", "name": "FGC"},
    {"code": "TRAM_BCN", "name": "TRAM Barcelona"}
  ],

  "paso_4_routes_de_esos_networks": [
    {"id": "51T_R1_IDA", "short_name": "R1", "network_id": "51T"},
    {"id": "51T_R2_IDA", "short_name": "R2", "network_id": "51T"},
    {"id": "TMB_METRO_L1", "short_name": "L1", "network_id": "TMB_METRO"},
    {"id": "TMB_METRO_L3", "short_name": "L3", "network_id": "TMB_METRO"},
    {"id": "FGC_S1", "short_name": "S1", "network_id": "FGC"}
  ]
}
```

### Ejemplo 2: Usuario en Lleida

**Request:**
```
GET /api/v1/gtfs/coordinates/routes?lat=41.6176&lon=0.6200
```

**Resultado:**
```json
{
  "provincia_detectada": {
    "code": "LLE",
    "name": "Lleida"
  },

  "networks_disponibles": [
    {"code": "51T", "name": "Rodalies de Catalunya"},
    {"code": "FGC", "name": "FGC"}
  ]
}
```

**Nota:** En Lleida NO aparece TMB_METRO ni TRAM_BCN porque solo operan en Barcelona.

### Ejemplo 3: Usuario en Madrid

**Request:**
```
GET /api/v1/gtfs/coordinates/routes?lat=40.4168&lon=-3.7038
```

**Resultado:**
```json
{
  "provincia_detectada": {
    "code": "MAD",
    "name": "Madrid"
  },

  "networks_disponibles": [
    {"code": "10T", "name": "Cercanías Madrid"},
    {"code": "11T", "name": "Metro de Madrid"},
    {"code": "12T", "name": "Metro Ligero de Madrid"},
    {"code": "90T", "name": "Línea C-9 Cotos"}
  ]
}
```

## Código de Lookup

```python
from src.gtfs_bc.province.province_lookup import get_province_and_networks_by_coordinates

# Obtener provincia y redes por coordenadas
result = get_province_and_networks_by_coordinates(db, lat=41.3851, lon=2.1734)

# Resultado:
# {
#     'province_code': 'BAR',
#     'province_name': 'Barcelona',
#     'networks': [
#         {'code': 'FGC', 'name': 'FGC'},
#         {'code': 'TMB_METRO', 'name': 'Metro de Barcelona'},
#         {'code': '51T', 'name': 'Rodalies de Catalunya'},
#         {'code': 'TRAM_BCN', 'name': 'TRAM Barcelona'}
#     ]
# }
```

## SQL de Ejemplo

```sql
-- Encontrar provincia por coordenadas
SELECT code, name
FROM spanish_provinces
WHERE ST_Contains(
    geometry,
    ST_SetSRID(ST_MakePoint(2.1734, 41.3851), 4326)
);
-- Resultado: BAR, Barcelona

-- Encontrar redes en esa provincia
SELECT n.code, n.name
FROM gtfs_networks n
JOIN network_provinces np ON np.network_id = n.code
WHERE np.province_code = 'BAR';
-- Resultado: 51T, TMB_METRO, FGC, TRAM_BCN

-- Encontrar rutas de esas redes
SELECT r.id, r.short_name, r.network_id
FROM gtfs_routes r
WHERE r.network_id IN ('51T', 'TMB_METRO', 'FGC', 'TRAM_BCN');
```

## Migraciones

- **023**: Reestructuración inicial de nucleos (ya revertida)
- **024**: Reemplazo de gtfs_nucleos por network_provinces
  - Crea tabla `network_provinces`
  - Añade `network_id` a `gtfs_routes`
  - Elimina `nucleo_id` y `nucleo_name` de stops y routes
  - Elimina tabla `gtfs_nucleos`

## Archivos Clave

- `src/gtfs_bc/network/infrastructure/models/__init__.py` - NetworkModel
- `src/gtfs_bc/network/infrastructure/models/network_province_model.py` - NetworkProvinceModel
- `src/gtfs_bc/province/province_lookup.py` - Funciones de lookup por coordenadas
- `adapters/http/api/gtfs/routers/network_router.py` - API de networks
- `alembic/versions/024_replace_nucleos_with_network_provinces.py` - Migración
