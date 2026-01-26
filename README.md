# RenfeServer

API de información de transporte ferroviario en España. Proporciona datos de líneas, estaciones, horarios y tiempos en tiempo real para múltiples operadores.

## Operadores Soportados

### Con GTFS-RT (Tiempo Real)
| Operador | Prefijo | Datos |
|----------|---------|-------|
| **Renfe Cercanías** | `RENFE_` | Posiciones, retrasos, alertas |
| **TMB Metro Barcelona** | `TMB_METRO_` | Predicciones, ocupación por vagón |
| **FGC** | `FGC_` | Posiciones, retrasos, alertas |
| **Euskotren** | `EUSKOTREN_` | Posiciones, retrasos, alertas |
| **Metro Bilbao** | `METRO_BILBAO_` | Posiciones, retrasos, alertas |

### GTFS Estático (Horarios)
| Operador | Prefijo |
|----------|---------|
| Metro de Madrid | `METRO_` |
| Metro Ligero Madrid | `ML_` |
| Metro Sevilla | `METRO_SEV_` |
| Metro Valencia | `METRO_VAL_` |
| Metro Málaga | `METRO_MAL_` |
| Metro Granada | `METRO_GRA_` |
| Metro Tenerife | `METRO_TEN_` |
| TRAM Barcelona | `TRAM_BCN_` / `TRAM_BARCELONA_` |
| TRAM Alicante | `TRAM_ALI_` |
| Tranvía Zaragoza | `TRANVIA_ZARAGOZA_` |
| Tranvía Murcia | `TRANVIA_MURCIA_` |
| Tranvía Sevilla | `TRAM_SEV_` |
| SFM Mallorca | `SFM_MALLORCA_` |

## Tech Stack

### Backend
- **Python 3.13+** con **FastAPI**
- **PostgreSQL 16+** con **PostGIS** (geolocalización)
- **Redis** para cache
- DDD + Hexagonal Architecture

### Infraestructura
- Scheduler automático GTFS-RT (cada 30 segundos)
- Systemd service en producción

## API Endpoints Principales

### Redes y Rutas
```
GET /api/v1/gtfs/networks                    # Todas las redes
GET /api/v1/gtfs/networks/{code}             # Detalle de red con líneas
GET /api/v1/gtfs/routes                      # Todas las rutas
GET /api/v1/gtfs/coordinates/routes?lat=&lon= # Rutas por coordenadas
```

### Paradas y Salidas
```
GET /api/v1/gtfs/stops/by-coordinates?lat=&lon=  # Paradas cercanas
GET /api/v1/gtfs/stops/{stop_id}/departures      # Próximas salidas
GET /api/v1/gtfs/stops/{stop_id}/platforms       # Andenes/plataformas de la parada
GET /api/v1/gtfs/stops/{stop_id}/correspondences # Conexiones a pie con otras paradas
GET /api/v1/gtfs/routes/{route_id}/stops         # Paradas de una línea
GET /api/v1/gtfs/routes/{route_id}/shape         # Geometría de la ruta (949 shapes)
```

### Tiempo Real
```
GET /api/v1/gtfs/realtime/vehicles           # Posiciones de trenes
GET /api/v1/gtfs/realtime/delays             # Retrasos actuales
GET /api/v1/gtfs/realtime/alerts             # Alertas de servicio
GET /api/v1/gtfs/realtime/scheduler/status   # Estado del scheduler
```

## Características

### Salidas (`/departures`)
- **Retrasos en tiempo real** para operadores con GTFS-RT
- **Posición del tren** (real o estimada)
- **Andén/vía** (real de GTFS-RT o estimado de histórico)
- **Filtro de horarios**: Redes estáticas no muestran salidas fuera de horario de servicio

### Redes (`/networks`)
- 31 redes de transporte en España
- Logos de cada operador
- Líneas ordenadas por `sort_order`
- Colores por línea
- Campo `transport_type`: cercanias, metro, metro_ligero, tranvia, fgc, euskotren, other

### Paradas
- Campo `is_hub`: true si conecta 2+ tipos de transporte (Metro↔Cercanías, etc.)
- **Plataformas** (`/platforms`): 2,989 andenes con coordenadas por línea
- **Correspondencias** (`/correspondences`): 218 conexiones a pie entre paradas

### Shapes (Geometrías)
- **949 shapes** con **650,332 puntos** para todas las redes
- Trazados bidireccionales (ida y vuelta)
- Fuentes: GTFS oficial, NAP, OpenStreetMap

## Server

- **Servidor:** juanmacias.com
- **Dominio:** redcercanias.com
- **Puerto:** 8002
- **Servicio:** `systemctl restart renfeserver`

## Desarrollo Local

### Requisitos
- Python 3.13+
- PostgreSQL 16+ con PostGIS
- Redis

### Iniciar
```bash
# Backend
PYTHONPATH=. uv run uvicorn app:app --reload --port 8000

# Base de datos local
PGPASSWORD=postgres psql -h localhost -p 5443 -U postgres -d renfeserver_dev
```

### Deploy a Producción
```bash
# Subir cambios
rsync -avz --exclude='__pycache__' --exclude='.git' \
  src/ root@juanmacias.com:/var/www/renfeserver/src/

rsync -avz adapters/ root@juanmacias.com:/var/www/renfeserver/adapters/

# Reiniciar servicio
ssh root@juanmacias.com "systemctl restart renfeserver"
```

## Documentación

- [docs/GTFS_OPERATORS_STATUS.md](./docs/GTFS_OPERATORS_STATUS.md) - Estado de operadores y URLs
- [docs/TODO_PENDIENTE.md](./docs/TODO_PENDIENTE.md) - Tareas y estado actual
- [docs/PLATFORMS_AND_CORRESPONDENCES.md](./docs/PLATFORMS_AND_CORRESPONDENCES.md) - Plataformas y correspondencias

## Licencia

Proprietary - All rights reserved.
