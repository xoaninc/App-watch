# Documentación API Renfe Server

**Última actualización:** 2026-01-27

---

## Indice

1. [Estado del Proyecto](#estado-del-proyecto)
2. [Arquitectura](#arquitectura)
3. [Endpoints API](#endpoints-api)
4. [Base de Datos](#base-de-datos)
5. [Scripts de Importación](#scripts-de-importación)
6. [Tareas Pendientes](#tareas-pendientes)
7. [Documentación Detallada](#documentación-detallada)

---

## Estado del Proyecto

### Resumen

| Métrica | Valor |
|---------|-------|
| Operadores | 18 |
| Redes (networks) | 31 |
| Paradas | ~6,700 |
| Rutas | 325 |
| Trips | 139,820 |
| Stop Times | 1,988,956 |
| Shapes | 949 |
| Shape Points | 650,332 |
| Platforms | 2,989 |
| Correspondencias | 218 |

### Operadores Implementados

| Operador | GTFS Estático | GTFS-RT | Shapes | Stop Times |
|----------|---------------|---------|--------|------------|
| Renfe Cercanías | ✅ | ✅ JSON | ✅ 74k pts | ✅ 1.84M |
| Metro Madrid | ✅ | - | ✅ 57k pts | ✅ |
| Metro Bilbao | ✅ | ✅ Protobuf | ✅ 13k pts | ✅ |
| Euskotren | ✅ | ✅ Protobuf | ✅ 61k pts | ✅ |
| TMB Metro Barcelona | ✅ | ✅ API | ✅ 103k pts | ✅ |
| FGC | ✅ | ✅ Protobuf | ✅ 12k pts | ✅ |
| Metrovalencia | ✅ | - | ✅ 11k pts (OSM) | ✅ |
| Metro Sevilla | ✅ | - | ✅ 424 pts (OSM) | ✅ 2,088 |
| Metro Granada | ✅ | - | ✅ 52 pts | ✅ 143,098 |
| Metro Málaga | ✅ | - | ✅ 260 pts | ✅ |
| TRAM Barcelona | ✅ | - | ✅ 5k pts (OSM) | ✅ |
| TRAM Alicante | ✅ | - | ✅ 7k pts (OSM) | ✅ |
| Tranvía Zaragoza | ✅ | - | ✅ 252 pts | ✅ |
| Tranvía Murcia | ✅ | - | ✅ 989 pts | ✅ |
| Tranvía Sevilla | ✅ | - | ✅ 552 pts (OSM) | ✅ |
| Metro Ligero Madrid | ✅ | - | ✅ 62k pts | ✅ |
| Metro Tenerife | ✅ | - | ✅ 132 pts | ✅ |
| SFM Mallorca | ✅ | - | ✅ 258k pts | ✅ |

### Algoritmo de Routing

| Fase | Estado | Descripción |
|------|--------|-------------|
| Fase 1: Preparación | ✅ | Estructuras de datos, carga de trips/stop_times |
| Fase 2: Algoritmo Core | ✅ | RAPTOR con rondas y filtro Pareto |
| Fase 3: Integración | ✅ | Endpoint `/route-planner` con RAPTOR |
| Fase 4: Optimización | **PENDIENTE** | Tests unitarios, cache, rendimiento |

---

## Arquitectura

```
src/
├── gtfs_bc/                    # Bounded Context GTFS
│   ├── network/                # Redes de transporte
│   ├── route/                  # Rutas y shapes
│   ├── stop/                   # Paradas y plataformas
│   ├── trip/                   # Viajes y horarios
│   ├── realtime/               # GTFS-RT (tiempo real)
│   ├── routing/                # Algoritmo RAPTOR
│   └── province/               # Lookup por coordenadas
│
├── adapters/
│   └── http/api/gtfs/
│       ├── routers/            # Endpoints FastAPI
│       └── schemas/            # Pydantic models
│
└── alembic/                    # Migraciones de BD
```

### Tecnologías

- **Backend:** FastAPI + Python 3.14
- **Base de datos:** PostgreSQL 16 + PostGIS
- **Cache:** Redis (opcional)
- **Servidor:** Uvicorn + systemd

---

## Endpoints API

### Route Planner (RAPTOR)

```
GET /api/v1/gtfs/route-planner?from={stop_id}&to={stop_id}&departure_time={HH:MM}
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| from | string | requerido | ID parada origen |
| to | string | requerido | ID parada destino |
| departure_time | string | hora actual | Formato HH:MM |
| max_transfers | int | 3 | Máximo transbordos (0-5) |

**Response:** Múltiples journeys Pareto-óptimos con tiempos reales de stop_times.

### Shapes

```
GET /api/v1/gtfs/routes/{route_id}/shape?max_gap={metros}
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| max_gap | float | null | Interpola puntos si gap > valor (10-500m) |

### Platforms

```
GET /api/v1/gtfs/stops/{stop_id}/platforms
```

Devuelve coordenadas de andenes por línea en una estación.

### Correspondences

```
GET /api/v1/gtfs/stops/{stop_id}/correspondences
```

Devuelve conexiones a pie a otras estaciones (transbordos).

### Departures

```
GET /api/v1/gtfs/stops/{stop_id}/departures
```

Devuelve próximas salidas desde una parada.

### Networks por Coordenadas

```
GET /api/v1/gtfs/coordinates/routes?lat={lat}&lon={lon}
```

Devuelve redes de transporte disponibles en esas coordenadas.

---

## Base de Datos

### Tablas Principales

| Tabla | Registros | Descripción |
|-------|-----------|-------------|
| gtfs_networks | 31 | Redes de transporte |
| gtfs_routes | 325 | Líneas/rutas |
| gtfs_stops | 6,709 | Paradas |
| gtfs_trips | 139,820 | Viajes |
| gtfs_stop_times | 1,988,956 | Horarios por parada |
| gtfs_calendar | ~400 | Servicios por día |
| gtfs_calendar_dates | ~130 | Excepciones (festivos) |
| gtfs_shape_points | 650,332 | Geometría de rutas |
| stop_platform | 2,989 | Coordenadas de andenes |
| stop_correspondence | 218 | Transbordos a pie |
| network_provinces | 37 | Relación red-provincia |
| spanish_provinces | 52 | Polígonos PostGIS |

### Migraciones Importantes

| Migración | Descripción |
|-----------|-------------|
| 024 | Reemplaza nucleos por network_provinces |
| 029 | Crea tabla stop_platform |
| 031 | Crea tabla stop_correspondence |

---

## Scripts de Importación

### GTFS Estático

```bash
# Renfe Cercanías (todas las redes)
python scripts/import_gtfs_static.py --nucleo all

# Red específica (ej: 30T Sevilla)
python scripts/import_gtfs_static.py --nucleo 30
```

### Metros Andalucía

```bash
# Metro Sevilla
python scripts/import_metro_sevilla_gtfs.py

# Metro Granada
python scripts/import_metro_granada_gtfs.py
```

### Correspondencias OSM

```bash
# Todas las ciudades
python scripts/import_osm_correspondences.py --all

# Ciudad específica
python scripts/import_osm_correspondences.py --city madrid
```

### Plataformas

```bash
python scripts/import_stop_platforms.py
```

---

## Tareas Pendientes

### Fase 4 RAPTOR - Optimización

| Tarea | Prioridad | Estado |
|-------|-----------|--------|
| Tests unitarios RAPTOR | Alta | Pendiente |
| Cache de patrones de trips | Media | Pendiente |
| Índices para búsqueda binaria | Media | Pendiente |
| Paralelización opcional | Baja | Pendiente |

### Baja Prioridad

| Tarea | Notas |
|-------|-------|
| API Valencia tiempo real | Devuelve vacío actualmente |

---

## Documentación Detallada

| Documento | Contenido |
|-----------|-----------|
| [RAPTOR_IMPLEMENTATION_PLAN.md](RAPTOR_IMPLEMENTATION_PLAN.md) | Plan de implementación RAPTOR, progreso, bugs conocidos |
| [TODO_PENDIENTE.md](TODO_PENDIENTE.md) | Historial de tareas completadas, estado de shapes |
| [GTFS_OPERATORS_STATUS.md](GTFS_OPERATORS_STATUS.md) | URLs de GTFS, estado de cada operador |
| [PLATFORMS_AND_CORRESPONDENCES.md](PLATFORMS_AND_CORRESPONDENCES.md) | Sistema de plataformas y transbordos |
| [ARCHITECTURE_NETWORK_PROVINCES.md](ARCHITECTURE_NETWORK_PROVINCES.md) | Sistema de redes y provincias |

### Archivados (referencia histórica)

En `docs/archive/`:
- Documentación de algoritmo Dijkstra (reemplazado por RAPTOR)
- Research de algoritmos de routing
- Guías de importación completadas
- Instrucciones de migración de app iOS

---

## Despliegue

### Servidor de Producción

```bash
# Desde local
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.env' \
  /path/to/renfeserver/ root@server:/var/www/renfeserver/

# Reiniciar servicio
ssh root@server "systemctl restart renfeserver"
```

### URLs

- **Producción:** https://juanmacias.com/api/v1/gtfs/
- **Alternativa:** https://redcercanias.com/api/v1/gtfs/

---

## Historial de Cambios Recientes

### 2026-01-27

- Metro Granada: Importados 5,693 trips y 143,098 stop_times
- Metro Sevilla: Verificado funcionamiento (valid hasta 2026-12-31)
- Shapes bidireccionales corregidos (Granada, TRAM BCN, Murcia L1B)
- Tranvía Sevilla (Metrocentro) shapes añadidos desde OSM
- Documentación reorganizada (obsoletos movidos a archive)

### 2026-01-26

- Metro Madrid shapes importados desde CRTM (57k puntos)
- Shapes OSM para Metrovalencia y TRAM Alicante
- Fix headsign CIVIS (735 trips)
- Fix headsigns vacíos (155,834 trips)
- Correspondencias principales completadas (Barcelona, Madrid, Bilbao, Sevilla, Valencia)
- Limpieza de shapes corruptos (colisión de IDs numéricos)
