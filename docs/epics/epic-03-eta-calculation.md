# Epic 03: Cálculo de Tiempo Estimado de Llegada (ETA)

## Objetivo
Calcular el tiempo estimado de llegada de los trenes a cada estación basándose en los datos históricos de movimiento y los datos en tiempo real.

## User Stories

### US-03.1: Cálculo de ETA basado en horario programado
**Como** usuario
**Quiero** ver el horario programado de llegada
**Para** saber cuándo debería llegar el tren

**Criterios de aceptación:**
- Mostrar hora programada según GTFS estático
- Indicar si el servicio opera hoy (calendar)

### US-03.2: Cálculo de ETA con datos en tiempo real
**Como** usuario
**Quiero** ver el tiempo estimado real de llegada
**Para** saber cuándo llegará realmente el tren

**Criterios de aceptación:**
- Usar delay de TripUpdates si está disponible
- Calcular ETA = hora_programada + delay
- Mostrar diferencia con horario programado

### US-03.3: Cálculo de ETA basado en posición
**Como** sistema
**Quiero** estimar ETA basándome en la posición actual del tren
**Para** dar estimaciones cuando no hay TripUpdates

**Algoritmo:**
1. Obtener posición actual del tren
2. Identificar en qué tramo está (entre qué paradas)
3. Calcular distancia restante a la estación destino
4. Usar velocidad media histórica del tramo
5. ETA = distancia / velocidad_media

### US-03.4: Cálculo de velocidad media por tramo
**Como** sistema
**Quiero** calcular la velocidad media entre estaciones
**Para** mejorar las estimaciones de ETA

**Criterios de aceptación:**
- Usar datos históricos de VehiclePositions
- Calcular por tramo (stop_A -> stop_B)
- Diferenciar por franja horaria (punta/valle)
- Diferenciar por día de semana

### US-03.5: Predicción de retrasos
**Como** sistema
**Quiero** predecir si habrá retraso
**Para** anticipar al usuario

**Criterios de aceptación:**
- Detectar si el tren va más lento de lo normal
- Comparar con velocidad media histórica
- Generar alerta si retraso > umbral

### US-03.6: Confianza en la estimación
**Como** usuario
**Quiero** saber cuán fiable es la estimación
**Para** tomar decisiones informadas

**Niveles de confianza:**
- Alta: Datos RT disponibles con delay reportado
- Media: Posición conocida, cálculo por velocidad
- Baja: Solo horario programado, sin datos RT

## Modelo de Datos

```
TrackSegment (
    id,
    from_stop_id,
    to_stop_id,
    route_id,
    distance_meters,
    avg_travel_time_seconds,
    avg_speed_kmh
)

SegmentStats (
    segment_id,
    day_type (weekday/weekend),
    hour_range,
    avg_travel_time,
    std_deviation,
    sample_count,
    updated_at
)

ETAResult (
    trip_id,
    stop_id,
    scheduled_arrival,
    estimated_arrival,
    delay_seconds,
    confidence_level,
    calculation_method,
    calculated_at
)
```

## Tareas Técnicas
1. Implementar servicio de cálculo de ETA
2. Crear algoritmo de interpolación de posición
3. Implementar cálculo de distancia geográfica (Haversine)
4. Crear job para calcular estadísticas de tramos
5. Implementar cache de ETAs calculados
6. Crear endpoint API para consulta de ETA
7. Añadir tests con diferentes escenarios
