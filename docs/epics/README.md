# RenfeServer - Épicas de Implementación

## Visión del Proyecto
Plataforma de información de transporte ferroviario en España, proporcionando datos de líneas, estaciones, horarios y tiempos estimados de llegada en tiempo real.

## Alcance Inicial
- **Zona geográfica:** Cercanías Sevilla
- **Operador:** Renfe Cercanías
- **Expansión futura:** Resto de núcleos de Cercanías, Metro de Madrid, Metro de Barcelona, etc.

## Épicas

| # | Épica | Descripción | Prioridad |
|---|-------|-------------|-----------|
| 01 | [GTFS Static Import](epic-01-gtfs-static-import.md) | Importar datos estáticos de líneas, estaciones y horarios | Alta |
| 02 | [GTFS Realtime](epic-02-gtfs-realtime.md) | Integrar datos en tiempo real de posiciones y actualizaciones | Alta |
| 03 | [ETA Calculation](epic-03-eta-calculation.md) | Calcular tiempos estimados de llegada | Alta |
| 04 | [API Endpoints](epic-04-api-endpoints.md) | Exponer API REST pública | Alta |
| 05 | [Wikipedia Data](epic-05-wikipedia-data.md) | Enriquecer con datos de Wikipedia (colores, logos) | Media |

## Orden de Implementación Sugerido

### Fase 1: Fundamentos (MVP)
1. **Epic 01** - Sin datos estáticos no hay nada
2. **Epic 04** (parcial) - Endpoints básicos de líneas y estaciones
3. **Epic 02** - Datos en tiempo real
4. **Epic 04** (completo) - Todos los endpoints

### Fase 2: Valor Añadido
5. **Epic 03** - Cálculo de ETAs mejorado
6. **Epic 05** - Datos enriquecidos de Wikipedia

### Fase 3: Expansión
- Añadir más núcleos de Cercanías
- Integrar Metro de Madrid
- Integrar Metro de Barcelona
- etc.

## Stack Técnico

### Backend (existente)
- Python 3.13+ / FastAPI
- PostgreSQL + PostGIS (para datos geográficos)
- Redis (cache + Celery broker)
- Celery (workers background)

### Dependencias Adicionales Necesarias
- `gtfs-realtime-bindings` - Parser de Protocol Buffers GTFS-RT
- `shapely` - Operaciones geométricas
- `geopandas` - Datos geoespaciales (opcional)
- `beautifulsoup4` - Scraping Wikipedia (ya instalado)

## Fuentes de Datos

| Fuente | URL | Tipo | Frecuencia |
|--------|-----|------|------------|
| GTFS Estático | https://data.renfe.com/dataset | ZIP/CSV | Semanal |
| GTFS Realtime Renfe | https://gtfsrt.renfe.com/*.json | **JSON** | 30 seg (auto) |
| GTFS-RT Metro Bilbao | opendata.euskadi.eus | Protobuf | 30 seg (auto) |
| GTFS-RT Euskotren | opendata.euskadi.eus | Protobuf | 30 seg (auto) |
| GTFS-RT FGC | dadesobertes.fgc.cat | JSON/Protobuf | 30 seg (auto) |
| TMB iMetro API | api.tmb.cat | REST API | 30 seg (auto) |
| Wikipedia | es.wikipedia.org | HTML | Manual |

**Nota:** Renfe usa **JSON**, no Protobuf. El scheduler automático hace fetch cada 30 segundos.

## Consideraciones Técnicas

### Base de Datos
- Usar PostGIS para datos geográficos (lat/lon, shapes)
- Particionar tabla de posiciones históricas por fecha
- Índices espaciales para búsquedas por proximidad

### Performance
- Cache de respuestas frecuentes en Redis
- Precalcular próximas salidas cada minuto
- WebSockets para actualizaciones en tiempo real (futuro)

### Escalabilidad
- Diseño multi-tenant para diferentes operadores/ciudades
- Workers separados por tipo de tarea (import, realtime, ETA)
