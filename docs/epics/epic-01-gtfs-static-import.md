# Epic 01: Importación de Datos GTFS Estáticos

## Objetivo
Importar y almacenar los datos estáticos de GTFS (General Transit Feed Specification) desde Renfe para tener la información base de líneas, estaciones, rutas y horarios.

## Fuentes de Datos
- https://data.renfe.com/dataset
- Formato: GTFS (archivos ZIP con CSVs)

## User Stories

### US-01.1: Descarga automática de feeds GTFS
**Como** sistema
**Quiero** descargar automáticamente los feeds GTFS de Renfe
**Para** mantener actualizada la información estática

**Criterios de aceptación:**
- Endpoint o comando para iniciar descarga
- Descarga del archivo ZIP desde data.renfe.com
- Descompresión y validación del contenido
- Log de fecha/hora de última actualización

### US-01.2: Importación de Agencias (agency.txt)
**Como** sistema
**Quiero** importar la información de agencias de transporte
**Para** identificar el operador de cada servicio

**Datos a importar:**
- agency_id
- agency_name
- agency_url
- agency_timezone

### US-01.3: Importación de Rutas/Líneas (routes.txt)
**Como** sistema
**Quiero** importar las rutas/líneas de transporte
**Para** mostrar las líneas disponibles

**Datos a importar:**
- route_id
- agency_id
- route_short_name (ej: C1, C2)
- route_long_name
- route_type (tipo de transporte)
- route_color
- route_text_color

### US-01.4: Importación de Paradas/Estaciones (stops.txt)
**Como** sistema
**Quiero** importar las paradas y estaciones
**Para** mostrar los puntos de parada

**Datos a importar:**
- stop_id
- stop_name
- stop_lat
- stop_lon
- location_type
- parent_station
- zone_id

### US-01.5: Importación de Viajes (trips.txt)
**Como** sistema
**Quiero** importar los viajes programados
**Para** conocer las circulaciones

**Datos a importar:**
- trip_id
- route_id
- service_id
- trip_headsign
- direction_id
- shape_id

### US-01.6: Importación de Horarios (stop_times.txt)
**Como** sistema
**Quiero** importar los horarios de cada parada
**Para** mostrar cuándo pasa el tren

**Datos a importar:**
- trip_id
- arrival_time
- departure_time
- stop_id
- stop_sequence

### US-01.7: Importación de Calendario (calendar.txt / calendar_dates.txt)
**Como** sistema
**Quiero** importar el calendario de servicios
**Para** saber qué días opera cada servicio

**Datos a importar:**
- service_id
- monday, tuesday, ... sunday
- start_date, end_date
- Excepciones (calendar_dates)

### US-01.8: Importación de Formas/Trazados (shapes.txt)
**Como** sistema
**Quiero** importar las formas geográficas de las rutas
**Para** poder dibujar las líneas en un mapa

**Datos a importar:**
- shape_id
- shape_pt_lat
- shape_pt_lon
- shape_pt_sequence

## Modelo de Datos

```
Agency (id, name, url, timezone)
Route (id, agency_id, short_name, long_name, type, color, text_color)
Stop (id, name, lat, lon, location_type, parent_station_id, zone_id)
Trip (id, route_id, service_id, headsign, direction_id, shape_id)
StopTime (trip_id, stop_id, arrival_time, departure_time, stop_sequence)
Calendar (service_id, days[], start_date, end_date)
CalendarDate (service_id, date, exception_type)
Shape (id, points[])
```

## Tareas Técnicas
1. Crear modelos de dominio para entidades GTFS
2. Crear modelos de infraestructura (SQLAlchemy)
3. Crear migraciones de base de datos
4. Implementar servicio de descarga de feeds
5. Implementar parser de archivos GTFS (CSV)
6. Implementar repositorios para cada entidad
7. Crear comando CLI para importación manual
8. Crear job programado para actualización periódica

## Filtro Inicial: Sevilla
- Filtrar solo las líneas de Cercanías Sevilla (núcleo C)
- Estaciones del área metropolitana de Sevilla
