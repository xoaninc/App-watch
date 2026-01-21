# RenfeServer - Épicas de Implementación

## Visión del Proyecto
Plataforma de información de transporte ferroviario en España, proporcionando datos de líneas, estaciones, horarios y tiempos en tiempo real para múltiples operadores.

## Estado Actual

### Operadores con GTFS-RT (Tiempo Real)
| Operador | Estado | Datos |
|----------|--------|-------|
| Renfe Cercanías | ✅ Activo | Posiciones, retrasos, alertas |
| TMB Metro Barcelona | ✅ Activo | Predicciones, ocupación, headsign |
| FGC | ✅ Activo | Posiciones, retrasos, alertas |
| Euskotren | ✅ Activo | Posiciones, retrasos, alertas |
| Metro Bilbao | ✅ Activo | Posiciones, retrasos, alertas |

### Operadores con GTFS Estático
| Operador | Estado |
|----------|--------|
| Metro de Madrid | ✅ Importado (frecuencias) |
| Metro Ligero Madrid | ✅ Importado (frecuencias) |
| Metro Sevilla | ✅ Importado |
| Metro Valencia | ✅ Importado |
| Metro Málaga | ✅ Importado |
| Tranvías (Sevilla, Zaragoza, etc.) | ✅ Importado |
| SFM Mallorca | ✅ Importado |

## Épicas

| # | Épica | Estado | Descripción |
|---|-------|--------|-------------|
| 01 | [GTFS Static Import](epic-01-gtfs-static-import.md) | ✅ Completada | Importar datos estáticos de todos los operadores |
| 02 | [GTFS Realtime](epic-02-gtfs-realtime.md) | ✅ Completada | Integrar datos en tiempo real multi-operador |
| 03 | [ETA Calculation](epic-03-eta-calculation.md) | ✅ Completada | Posiciones estimadas desde horarios |
| 04 | [API Endpoints](epic-04-api-endpoints.md) | ✅ Completada | API REST completa |
| 05 | [Wikipedia Data](epic-05-wikipedia-data.md) | ⏳ Parcial | Colores y logos de operadores |

## Arquitectura

### Sistema de Redes (Networks)
- 31 redes de transporte definidas en `gtfs_networks`
- Relación N:M con provincias vía `network_provinces`
- Lookup por coordenadas usando PostGIS

### GTFS-RT Multi-Operador
- Scheduler automático cada 30 segundos
- Parsers para JSON (Renfe) y Protobuf (otros)
- API TMB iMetro para Metro Barcelona

### Características API
- **Departures**: Incluye retrasos RT, posición del tren, andén estimado
- **Operating Hours Filter**: Redes estáticas no muestran salidas fuera de horario
- **Platform History**: Estimación de andén basada en histórico

## Stack Técnico

### Backend
- Python 3.13+ / FastAPI
- PostgreSQL 16+ con PostGIS
- Redis (cache)
- Scheduler AsyncIO integrado con lifespan

### Base de Datos
- `gtfs_networks` - 31 redes de transporte
- `gtfs_routes` - Rutas con `network_id`
- `gtfs_stops` - Paradas con geolocalización
- `gtfs_rt_*` - Tablas de tiempo real
- `spanish_provinces` - Polígonos PostGIS

## Fuentes de Datos

| Fuente | URL | Formato | Frecuencia |
|--------|-----|---------|------------|
| GTFS Renfe | data.renfe.com | ZIP | Semanal |
| GTFS-RT Renfe | gtfsrt.renfe.com | JSON | 30 seg |
| GTFS-RT Metro Bilbao | opendata.euskadi.eus | Protobuf | 30 seg |
| GTFS-RT Euskotren | opendata.euskadi.eus | Protobuf | 30 seg |
| GTFS-RT FGC | dadesobertes.fgc.cat | Protobuf | 30 seg |
| TMB iMetro | api.tmb.cat | REST API | 30 seg |

## Documentación Relacionada

- [README.md](../../README.md) - Documentación principal
- [GTFS_REALTIME.md](../../GTFS_REALTIME.md) - Detalles de integración RT
- [ARCHITECTURE_NETWORK_PROVINCES.md](../ARCHITECTURE_NETWORK_PROVINCES.md) - Sistema de redes
