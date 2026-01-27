# Algoritmos de Routing para Transporte Público

**Fecha:** 2026-01-27

## Resumen

Investigación sobre algoritmos de planificación de rutas en transporte público para mejorar el endpoint `/route-planner`.

---

## 1. Estado Actual: Dijkstra Básico

### Implementación
- Archivo: `src/gtfs_bc/routing/routing_service.py`
- Algoritmo: Dijkstra sobre grafo de transporte

### Características
| Aspecto | Implementación |
|---------|----------------|
| Tiempos de viaje | Estimados (velocidad comercial) |
| Hora de salida | No considera |
| Resultados | 1 ruta (la más rápida) |
| Transbordos | Penalización fija (3 min) |
| Multi-criterio | No |

### Velocidades comerciales usadas
```python
AVERAGE_SPEED_METRO_KMH = 30      # Metro
AVERAGE_SPEED_CERCANIAS_KMH = 45  # Cercanías
AVERAGE_SPEED_TRAM_KMH = 18       # Tranvía
WALKING_SPEED_KMH = 4.5           # Andando
```

### Limitaciones
1. No usa tiempos reales de `stop_times`
2. No considera horarios de servicio
3. Solo devuelve 1 ruta
4. No es time-dependent

---

## 2. RAPTOR Algorithm

### ¿Qué es?
**RAPTOR** = Round-bAsed Public Transit Optimized Router

Algoritmo diseñado específicamente para transporte público. Usado por:
- Google Maps
- Moovit
- Citymapper
- Transit App

### Cómo funciona

1. **Rondas**: Cada ronda representa 1 transferencia adicional
   - Ronda 0: Rutas directas
   - Ronda 1: 1 transbordo
   - Ronda 2: 2 transbordos
   - Máximo: 16 rondas

2. **Por cada ronda**:
   ```
   1. Relajar transferencias a pie
   2. Identificar rutas que pasan por paradas actualizadas
   3. Escanear cada ruta para encontrar mejores conexiones
   4. Actualizar tiempos de llegada
   ```

3. **Pareto-óptimo**: Encuentra TODAS las rutas que son óptimas en algún criterio:
   - Más rápida (aunque tenga 3 transbordos)
   - Menos transbordos (aunque tarde más)
   - Menos caminata

### Ventajas sobre Dijkstra

| Aspecto | Dijkstra | RAPTOR |
|---------|----------|--------|
| Tiempos | Estimados | Reales (stop_times) |
| Hora salida | No | Sí (time-dependent) |
| Resultados | 1 ruta | Múltiples alternativas |
| Optimización | Solo tiempo | Multi-criterio |
| Complejidad | O(E log V) | O(K × R × T) |

Donde K=rondas, R=rutas, T=trips

### Implementación de referencia

**Repositorio:** https://github.com/PatrickSteil/RAPTORPython

```python
# Uso básico
data = raptor.RAPTORData(PATH_TO_GTFS)
data.readGTFS()
data.run(source, target, departure_time)
journeys = data.getAllJourneys()
```

**Estructura de datos clave:**
- `EarliestArrivalLabel`: Tiempos de llegada por ronda
- `Transfer`: Conexiones a pie entre paradas
- `StopEvent`: Tiempos de llegada/salida en paradas

---

## 3. GraphHopper (Moovit fork)

### Repositorio
https://github.com/moovit/graphhopper

### Características
- Librería Java open source (Apache 2.0)
- Soporta GTFS + OpenStreetMap
- Multi-modal (transporte + caminar + bici)
- Modelo "time-expanded network"

### Algoritmos disponibles
- Dijkstra / A* bidireccional
- Contraction Hierarchies (CH) - modo rápido
- Híbrido

### Módulo GTFS
- `reader-gtfs`: Procesa datos GTFS
- Integra red de transporte + red peatonal
- Validación temporal en edges

---

## 4. Comparación de Opciones

### Opción A: Mejorar Dijkstra actual
- Añadir tiempos de `stop_times`
- Mantener estructura actual
- Esfuerzo: Bajo
- Resultado: Tiempos más precisos, pero sin alternativas

### Opción B: Implementar RAPTOR
- Reescribir routing service
- Usar tiempos reales + hora de salida
- Esfuerzo: Alto
- Resultado: Rutas Pareto-óptimas, time-dependent

### Opción C: Integrar GraphHopper
- Servicio Java separado
- Complejidad de infraestructura
- Esfuerzo: Muy alto
- Resultado: Solución enterprise-grade

### Recomendación

**RAPTOR** es la mejor opción a largo plazo porque:
1. Es el estándar de la industria
2. Diseñado específicamente para transporte público
3. Hay implementación Python de referencia
4. No requiere infraestructura adicional

---

## 5. ¿Por qué importa la hora de salida?

### Escenario real
Usuario quiere ir de Olivar de Quintos a Cartuja:

**A las 8:00 (hora punta):**
- Metro cada 5 min → espera ~2.5 min
- Cercanías cada 10 min → espera ~5 min
- Total: 40 min

**A las 23:00 (noche):**
- Metro cada 15 min → espera ~7.5 min
- Cercanías cada 30 min → espera ~15 min
- Total: 55 min
- O quizás el último tren ya pasó

### Sin time-dependent routing
- Siempre sugiere la misma ruta
- Puede sugerir rutas sin servicio
- Tiempos irreales

### Con time-dependent routing
- Rutas adaptadas a la hora
- Solo sugiere viajes posibles
- Tiempos realistas

---

## 6. Estructura de datos GTFS necesaria

Para implementar RAPTOR necesitamos:

### stop_times
```sql
SELECT trip_id, stop_id, arrival_time, departure_time, stop_sequence
FROM gtfs_stop_times
WHERE trip_id IN (SELECT id FROM gtfs_trips WHERE route_id = ?)
ORDER BY trip_id, stop_sequence
```

### calendar + calendar_dates
```sql
-- Verificar si un servicio opera en una fecha
SELECT service_id
FROM gtfs_calendar
WHERE monday = true AND start_date <= ? AND end_date >= ?

UNION

SELECT service_id
FROM gtfs_calendar_dates
WHERE date = ? AND exception_type = 1
```

### Datos ya disponibles
- ✅ stop_times (arrival_seconds, departure_seconds)
- ✅ calendar + calendar_dates
- ✅ stop_correspondence (transferencias a pie)
- ✅ stop_route_sequence

---

## 7. Plan de implementación RAPTOR

### Fase 1: Preparación de datos
1. Crear índices optimizados en stop_times
2. Pre-calcular transferencias por parada
3. Agrupar trips por patrón de paradas

### Fase 2: Algoritmo core
1. Implementar estructura `EarliestArrivalLabel`
2. Implementar bucle de rondas
3. Implementar escaneo de rutas

### Fase 3: Integración
1. Adaptar endpoint `/route-planner`
2. Añadir parámetro `departure_time`
3. Devolver alternativas en `alternatives[]`

### Fase 4: Optimización
1. Cache de patrones de trips
2. Índices para búsqueda binaria de trips
3. Paralelización opcional

---

## 8. Referencias

### Papers
- "Round-Based Public Transit Routing" (Delling et al., 2012)
- Original RAPTOR paper de Microsoft Research

### Implementaciones
- https://github.com/PatrickSteil/RAPTORPython (Python, MIT)
- https://github.com/Cata-Dev/RAPTOR (TypeScript)
- https://github.com/graphhopper/graphhopper (Java, Apache 2.0)

### Documentación
- GTFS Reference: https://gtfs.org/reference/static
- GTFS Realtime: https://gtfs.org/reference/realtime

---

## 9. Decisión Final

**Fecha:** 2026-01-27

### Algoritmo elegido: RAPTOR

**Razones:**
1. Estándar de la industria (Google Maps, Moovit, Citymapper)
2. Diseñado para transporte público
3. Multi-criterio (tiempo + transbordos + caminata)
4. Time-dependent (hora de salida)
5. Devuelve alternativas Pareto-óptimas

### Características a implementar:
- [x] Tiempos reales de `stop_times`
- [x] Parámetro `departure_time`
- [x] Rutas alternativas (2-3)
- [x] Validación contra `calendar`

### Estado: PENDIENTE DE IMPLEMENTACIÓN

Recopilando más información de repositorios antes de implementar.

---

## 10. Repositorios Investigados

### Moovit (GitHub)
- **URL:** https://github.com/moovit
- **Repos útiles:**
  - `graphhopper` - Fork de routing engine (Java)
  - `flatmap` - Vector tiles desde OSM
  - `tileserver-gl` - Servidor de mapas

### RAPTORPython
- **URL:** https://github.com/PatrickSteil/RAPTORPython
- **Lenguaje:** Python
- **Utilidad:** Implementación de referencia para RAPTOR
- **Licencia:** MIT

### RAPTOR TypeScript
- **URL:** https://github.com/Cata-Dev/RAPTOR
- **Lenguaje:** TypeScript
- **Utilidad:** Implementación con multi-criterio avanzado

---

## 11. Repositorios Pendientes de Investigar

(Se irán añadiendo conforme se investiguen)

---

## 12. Organización public-transport (GitHub)

**URL:** https://github.com/public-transport

### Repositorios clave investigados:

#### Transitous
- **URL:** https://github.com/public-transport/transitous
- **Estrellas:** 536
- **Descripción:** Motor de routing open source
- **Motor interno:** Usa MOTIS como backend
- **Lenguaje:** Lua + Python

#### MOTIS (Motor de Transitous)
- **URL:** https://github.com/motis-project/motis
- **Descripción:** Modular Open Transportation Information System
- **Características:**
  - Multi-modal (transporte + caminar + bici + sharing)
  - Soporta GTFS, GTFS-RT, GTFS Flex, Fares v2
  - API REST con OpenAPI spec
  - Optimizado para alto rendimiento y bajo uso de memoria
  - Bitsets para días de tráfico (carga timetables de año completo)
- **Lenguaje:** C++ (61.5%)
- **Utilidad:** Referencia de arquitectura enterprise-grade

#### gtfs-via-postgres
- **URL:** https://github.com/public-transport/gtfs-via-postgres
- **Estrellas:** 125
- **Descripción:** Procesa GTFS en PostgreSQL
- **Views útiles creadas:**
  - `service_days` - Días operativos por servicio
  - `arrivals_departures` - Tiempos absolutos con fechas
  - `connections` - **Útil para routing:** une salidas con llegadas
  - `shapes_aggregated` - LineStrings PostGIS
- **Funciones helper:**
  - `largest_arrival_time()` - Para filtrar por fecha eficientemente
  - `largest_departure_time()`
- **Rendimiento:** Filtrar por fecha reduce queries de 230ms a 55ms
- **Utilidad:** Referencia para optimizar nuestras queries

#### Friendly Public Transport Format (FPTF)
- **URL:** https://github.com/public-transport/friendly-public-transport-format
- **Estrellas:** 137
- **Descripción:** Formato estándar para datos de transporte
- **Filosofía:** JSON simple, flat, intuitivo (vs GTFS que parece DB dump)
- **Estructuras clave:**

```
Journey {
  type: 'journey'
  id: string
  legs: Leg[]
  price?: { amount, currency }
}

Leg {
  origin: Stop/Station
  destination: Stop/Station
  departure: ISO8601
  arrival: ISO8601
  departureDelay?: seconds
  arrivalDelay?: seconds
  departurePlatform?: string
  arrivalPlatform?: string
  stopovers?: Stopover[]
  mode?: string
  line?: Line
}

Stopover {
  stop: Stop
  arrival: ISO8601
  departure: ISO8601
  arrivalDelay?: seconds
  departureDelay?: seconds
  platform?: string
}
```

- **Utilidad:** Referencia para mejorar nuestro schema de response

#### HAFAS Client
- **URL:** https://github.com/public-transport/hafas-client
- **Estrellas:** 332
- **Descripción:** Cliente JS para APIs HAFAS
- **¿Qué es HAFAS?** Sistema de gestión de transporte de HaCon, usado por operadores europeos
- **Utilidad:** Solo consume APIs, no implementa algoritmos

---

## 13. Connection Scan Algorithm (CSA)

### trRouting
- **URL:** https://github.com/chairemobilite/trRouting
- **Estrellas:** 28
- **Lenguaje:** C++
- **Descripción:** Servidor de routing con CSA

### ¿Qué es CSA?
Connection Scan Algorithm - alternativa a RAPTOR para transit routing.

### Rendimiento trRouting (datos reales Montreal):
- CSA two-way: **~8 ms**
- Access/egress footpaths: ~150 ms
- Total: <200 ms por query

### Características:
- Múltiples paradas accesibles en origen/destino
- Footpaths de transferencia (hasta 10 min caminando)
- Cache con memcached opcional
- Integración OSRM para walking
- API REST documentada
- Docker disponible

### CSA vs RAPTOR

| Aspecto | CSA | RAPTOR |
|---------|-----|--------|
| Velocidad | Muy rápido (~8ms) | Rápido |
| Complejidad | Menor | Mayor |
| Multi-criterio | Limitado | Nativo (Pareto) |
| Implementación | Más simple | Más compleja |
| Alternativas | Requiere múltiples runs | Nativo |

---

## 14. Resumen de Opciones de Algoritmos

### Opción 1: RAPTOR (Recomendado)
- **Pros:** Multi-criterio, alternativas nativas, estándar industria
- **Cons:** Más complejo de implementar
- **Referencia:** PatrickSteil/RAPTORPython

### Opción 2: CSA (Connection Scan Algorithm)
- **Pros:** Muy rápido, más simple
- **Cons:** Menos flexible, sin alternativas nativas
- **Referencia:** chairemobilite/trRouting

### Opción 3: MOTIS (Enterprise)
- **Pros:** Completo, producción-ready, multi-modal
- **Cons:** Servicio separado (C++), complejidad infraestructura
- **Referencia:** motis-project/motis

### Opción 4: Dijkstra mejorado (Actual)
- **Pros:** Ya implementado, simple
- **Cons:** Sin time-dependent, sin alternativas, tiempos estimados

---

## 15. Decisión Actualizada

**Fecha:** 2026-01-27

Tras investigar public-transport:

### Algoritmo: RAPTOR (confirmado)
- Multi-criterio nativo es importante para UX
- Alternativas sin costo adicional
- Hay implementación Python de referencia

### Mejoras al schema de response:
- Adoptar estructura similar a FPTF
- Añadir `delay` fields para GTFS-RT futuro
- Añadir `platform` fields

### Optimizaciones de BD a considerar:
- View tipo `connections` de gtfs-via-postgres
- Filtrado por fecha para performance

---

## 16. UK Department for Transport (GitHub)

**URL:** https://github.com/department-for-transport-public

### Open_NaPTAN
- **URL:** https://github.com/department-for-transport-public/Open_NaPTAN
- **Estrellas:** 29
- **Lenguaje:** HTML
- **Descripción:** Validación y visualización de datos NaPTAN
- **¿Qué es NaPTAN?** National Public Transport Access Nodes - registro UK de puntos de acceso a transporte público
- **Utilidad:** Referencia para validación de datos de paradas

### D-TRO (Digital Traffic Regulation Orders)
- **URL:** https://github.com/department-for-transport-public/D-TRO
- **Estrellas:** 12
- **Descripción:** Sistema de gestión de órdenes de regulación de tráfico
- **Utilidad:** No relevante para routing

---

## 17. Implementaciones RAPTOR Destacadas

### planarnetwork/raptor (⭐ Recomendado)
- **URL:** https://github.com/planarnetwork/raptor
- **Estrellas:** 107
- **Lenguaje:** TypeScript
- **Licencia:** GPL-3.0
- **Descripción:** Implementación casi directa del paper original

**Características:**
- Implementa rRAPTOR (range query extension)
- Múltiples orígenes/destinos por query
- Tiempos de intercambio en estaciones
- Filtro multi-criterio Pareto (tiempo vs transbordos)
- Pickup/setdown marker compliance

**Tipos de Query:**
```typescript
DepartAfterQuery        // Origen único, llegada más temprana
GroupStationDepartAfterQuery  // Múltiples paradas origen/destino
RangeQuery              // Búsqueda en ventana de tiempo
TransferPatternQuery    // Análisis de alcanzabilidad
```

**Uso:**
```javascript
[trips, transfers, interchange, calendars] = await loadGTFS(stream);
raptor = RaptorAlgorithmFactory.create(trips, transfers, interchange, calendars);
query = new DepartAfterQuery(raptor, new JourneyFactory());
journeys = query.plan(originStop, destStop, date, departureSeconds);
```

**Filtro Pareto:**
> "Retiene journeys donde ningún viaje posterior llega antes Y tiene igual o menos transbordos"

---

### transnetlab/transit-routing (⭐ Toolkit de Algoritmos)
- **URL:** https://github.com/transnetlab/transit-routing
- **Estrellas:** 73
- **Lenguaje:** Python
- **Descripción:** Repositorio de múltiples algoritmos de routing

**Algoritmos implementados:**

| Familia | Variantes |
|---------|-----------|
| RAPTOR | Standard, HypRAPTOR, rRAPTOR, One-To-Many rRAPTOR |
| TBTR | Standard, rTBTR, One-To-Many, HypTBTR, MhypTBTR |
| Otros | Transfer Patterns, CSA, Time-Expanded Dijkstra |

**Características clave:**
- Optimización bicriteria (tiempo + transbordos)
- Particionamiento con KaHyPar (hypergraph decomposition)
- Dataset de prueba: Red de transporte de Suiza
- Queries One-To-Many para apps de mapas

**Utilidad:** Excelente para comparar rendimiento de diferentes algoritmos

---

### aubryio/minotor (⭐ Client-Side)
- **URL:** https://github.com/aubryio/minotor
- **Estrellas:** 56
- **Lenguaje:** TypeScript
- **Descripción:** RAPTOR ligero para ejecutar en cliente

**Arquitectura única:**
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ GTFS Parse  │ →  │ Protobuf    │ →  │ Browser/    │
│ (Node.js)   │    │ Binary      │    │ React Native│
└─────────────┘    └─────────────┘    └─────────────┘
```

**Características:**
- Todo el routing ejecuta client-side (sin latencia de red)
- Tiempos en 16 bits (nivel de minuto) para reducir memoria
- Datos Swiss GTFS: 20MB sin comprimir, 5MB comprimido
- Parsing: ~2 min para feed completo
- **Privacidad:** No envía ubicación al servidor

**Casos de uso:**
- Apps móviles offline-first
- Visualizaciones interactivas
- Research con queries en tiempo real

---

### naviqore/public-transit-service (Java Service)
- **URL:** https://github.com/naviqore/public-transit-service
- **Estrellas:** 8
- **Lenguaje:** Java (Maven multi-module)
- **Descripción:** Servicio REST completo con RAPTOR

**Arquitectura Maven:**
```
naviqore/
├── naviqore-app/                 # Spring REST application
└── naviqore-libs/
    ├── public-transit-service/   # Query logic
    ├── raptor/                   # RAPTOR algorithm
    ├── gtfs/                     # GTFS processing
    └── benchmark/                # Performance testing
```

**Deployment Docker:**
```bash
docker run -p 8080:8080 \
  -e GTFS_STATIC_URI=<URL_OR_PATH> \
  ghcr.io/naviqore/public-transit-service:latest
```

**API:**
- Acepta coordenadas geográficas además de stop IDs
- Publicado en Maven Central
- Módulo de benchmark incluido

---

## 18. Soluciones Enterprise

### OpenTripPlanner (⭐ Industry Standard)
- **URL:** https://github.com/opentripplanner/OpenTripPlanner
- **Estrellas:** 2,100+
- **Lenguaje:** Java (97%)
- **Commits:** 30,792+
- **Contributors:** 194
- **Versión actual:** v2.8.1 (Sep 2025)
- **Licencia:** LGPL

**Arquitectura:**
- Servidor Java con JAR unificado
- Cliente JavaScript con MapLibre
- API GraphQL

**Algoritmos:**
- A* para búsqueda espacial
- **RAPTOR** para transporte público
- Contraction Hierarchies para optimización

**Formatos soportados:**
- GTFS + GTFS Realtime
- OpenStreetMap
- Servicios de movilidad (bike share, ride hailing)

**Multi-modal:**
- Transporte público programado
- Bicicleta y caminata
- Disrupciones de servicio en tiempo real

**Deployment:**
```bash
java -jar otp-shaded-VERSION.jar --build /path/to/data
```

---

### Navitia (hove-io)
- **URL:** https://github.com/hove-io/navitia
- **Estrellas:** 447
- **Licencia:** AGPL-3.0
- **Descripción:** Sistema completo de información de transporte

**Arquitectura de 3 componentes:**
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Ed          │    │ Kraken      │    │ Jörmungandr │
│ (PostgreSQL)│ →  │ (C++)       │ ←  │ (Python)    │
│ Preproceso  │    │ Heavy Comp  │    │ API/Light   │
└─────────────┘    └─────────────┘    └─────────────┘
       ↓                  ↕
   Binarización      Protocol Buffers + ZMQ
```

**Formatos de datos:**
- NTFS (formato propietario)
- GTFS
- OpenStreetMap

**API HATEOAS:**
- Journey computation multi-modal
- Line schedules y departure predictions
- Location search y autocomplete
- Isochrone generation

**Instancia pública:** api.navitia.io

---

## 19. Librerías para Apps Móviles

### TripKit (Swift)
- **URL:** https://github.com/alexander-albers/tripkit
- **Estrellas:** 106
- **Lenguaje:** Swift
- **Plataformas:** iOS 12+, watchOS 5+, tvOS 12+, macOS 10.13+
- **Distribución:** Swift Package Manager

**Basado en:** public-transport-enabler (Java)

**Capabilities:**
```swift
// Location suggestions
suggestLocations(keyword: String) async -> Result<[Location], Error>

// Nearby stops
queryNearbyLocations(lat: Double, lon: Double) async -> Result<[Location], Error>

// Departures
queryDepartures(stationId: String) async -> Result<[Departure], Error>

// Trip planning
queryTrips(from: Location, to: Location) async -> Result<[Trip], Error>

// Journey details
queryJourneyDetail(context: QueryJourneyDetailContext) async -> Result<Trip, Error>
```

**Proveedores soportados:** Principalmente región DACH (Alemania, Austria, Suiza)

**Autenticación:** Archivo externo `secrets.json` para API keys

---

## 20. Tabla Comparativa Final

| Solución | Lenguaje | Algoritmo | Multi-criterio | Client-side | Production-ready |
|----------|----------|-----------|----------------|-------------|------------------|
| **planarnetwork/raptor** | TypeScript | RAPTOR | ✅ Pareto | ❌ | ✅ |
| **transnetlab/transit-routing** | Python | Varios | ✅ Bicriteria | ❌ | ⚠️ Research |
| **aubryio/minotor** | TypeScript | RAPTOR | ❌ | ✅ | ✅ |
| **naviqore/public-transit-service** | Java | RAPTOR | ❓ | ❌ | ✅ |
| **OpenTripPlanner** | Java | A* + RAPTOR | ✅ | ❌ | ✅✅ |
| **Navitia** | Python/C++ | Kraken | ✅ | ❌ | ✅✅ |
| **MOTIS** | C++ | Varios | ✅ | ❌ | ✅✅ |
| **TripKit** | Swift | Cliente API | N/A | ✅ (consume) | ✅ |

---

## 21. Recomendaciones para Implementación

### Para nuestra API (Python/FastAPI):

**Opción A: Implementar RAPTOR desde cero**
- Referencia: `planarnetwork/raptor` (TypeScript) o `PatrickSteil/RAPTORPython`
- Pros: Control total, sin dependencias externas
- Cons: Esfuerzo de desarrollo

**Opción B: Adaptar transnetlab/transit-routing**
- Ya está en Python
- Múltiples algoritmos para comparar
- Bien documentado para research

**Opción C: Minotor-style (client-side routing)**
- Generar protobuf desde servidor
- Routing ejecuta en app iOS
- Pros: Sin carga en servidor, offline
- Cons: Cambio de arquitectura significativo

### Para la App iOS:

**Opción 1: TripKit**
- Si queremos consumir APIs de otros operadores
- Formato de datos estándar

**Opción 2: Minotor port a Swift**
- Routing offline completo
- Privacidad máxima

**Opción 3: Consumir nuestra API mejorada**
- Mantener lógica en servidor
- App más simple

---

## 22. Próximos Pasos

1. **Decidir arquitectura:** ¿Routing en servidor o client-side?
2. **Si servidor:** Elegir entre implementar RAPTOR o adaptar transit-routing
3. **Si client-side:** Evaluar port de minotor a Swift
4. **Schema de response:** Adoptar estructura FPTF para futuro GTFS-RT
5. **Benchmark:** Comparar rendimiento con dataset real

---

## 23. Referencias Completas

### Papers
- "Round-Based Public Transit Routing" (Delling et al., 2012) - Microsoft Research
- "Trip-Based Public Transit Routing" (Witt, 2015)
- "Connection Scan Algorithm" (Dibbelt et al., 2013)

### Implementaciones RAPTOR
- https://github.com/planarnetwork/raptor (TypeScript, GPL-3.0) ⭐
- https://github.com/transnetlab/transit-routing (Python, research)
- https://github.com/aubryio/minotor (TypeScript, client-side)
- https://github.com/PatrickSteil/RAPTORPython (Python, MIT)
- https://github.com/naviqore/public-transit-service (Java, Maven)

### Soluciones Enterprise
- https://github.com/opentripplanner/OpenTripPlanner (Java, LGPL)
- https://github.com/hove-io/navitia (Python/C++, AGPL)
- https://github.com/motis-project/motis (C++)

### Móvil
- https://github.com/alexander-albers/tripkit (Swift)

### Utilidades
- https://github.com/public-transport/gtfs-via-postgres (SQL views)
- https://github.com/public-transport/friendly-public-transport-format (JSON spec)

---

## 24. Apps Android de Referencia

### Transportr (⭐ 1,100+)
- **URL:** https://github.com/grote/Transportr
- **Lenguaje:** Kotlin (62.5%) + Java (35.9%)
- **Licencia:** GPL-3.0
- **Descargas:** F-Droid, Google Play

**Características:**
- App de transporte público sin anuncios ni tracking
- Privacy-first design
- Integración con JawgMaps (basado en OSM)
- 49+ contributors, 37 releases

**Arquitectura:**
```
/app          → Código principal
/fastlane     → Deployment automatizado
/.github      → CI/CD (Build & Test)
```

**Dependencias clave:**
- JawgMaps para mapas vectoriales
- OpenStreetMap data
- public-transport-enabler (ver sección 25)

---

### OneBusAway Android (⭐ 530)
- **URL:** https://github.com/OneBusAway/onebusaway-android
- **Lenguaje:** Java (98.1%) + Kotlin
- **Descripción:** Cliente oficial OneBusAway

**Integración con routing:**
- **OneBusAway API** → Datos de paradas/rutas
- **OpenTripPlanner** → Journey planning multimodal
- **Open311** → Reporting de incidencias

**Features:**
- Real-time arrivals/departures
- Mapa de paradas cercanas
- Bike-share availability (via OTP)
- Trip planning multimodal
- Home screen shortcuts

**Arquitectura flexible:**
- Soporta servidores custom OBA/OTP
- Permite rebranding para agencias
- Multi-region deployment

---

## 25. public-transport-enabler (Librería Base)

**URL:** https://github.com/schildbach/public-transport-enabler
**Estrellas:** 429
**Lenguaje:** Java
**Importancia:** Base de TripKit (Swift) y Transportr (Android)

### ¿Qué es?
Librería Java para acceder a datos de transporte público de múltiples proveedores.

### Protocolos soportados:
- **HAFAS** (HaCon) - Sistema alemán usado en toda Europa
- **EFA** (Electronic Fare Management)
- **Navitia**

### API Principal:
Interface `NetworkProvider.java` que cada proveedor implementa.

### Autenticación:
```properties
# secrets.properties
provider.api_key=XXX
```

### Testing:
```bash
# Tests live por proveedor
gradle -Dtest.single=BvgProviderLive test
```

### Uso típico:
```java
NetworkProvider provider = new BvgProvider();
List<Location> locations = provider.suggestLocations("Berlin Hbf");
QueryTripsResult result = provider.queryTrips(from, via, to, date, options);
```

**Nota:** Se enfoca en data retrieval, no en algoritmos de routing propios.

---

## 26. transport.rest (API Pública)

**URL:** https://github.com/public-transport/transport.rest
**Estrellas:** 133
**Descripción:** APIs REST públicas para transporte europeo

### Instancias disponibles:

| Región | Endpoint | Status |
|--------|----------|--------|
| Deutsche Bahn (Alemania) | `v6.db.transport.rest` | ✅ |
| VBB (Berlin/Brandenburg) | `v6.vbb.transport.rest` | ✅ |
| BVG (Berlin) | `v6.bvg.transport.rest` | ✅ |
| Poland | `poland.transport.rest` | ✅ |
| Flixbus (Europa) | `1.flixbus.transport.rest` | ✅ |
| Nottingham (UK) | `v1.nottingham-city.transport.rest` | ✅ |

### Deployment:
- Ansible para infraestructura
- Cualquier API puede unirse si provee datos públicos

### Uso:
```bash
# Ejemplo: búsqueda de paradas en Berlin
curl "https://v6.bvg.transport.rest/stops/nearby?latitude=52.52&longitude=13.40"
```

---

## 27. transport-apis (Directorio de APIs)

**URL:** https://github.com/public-transport/transport-apis
**Estrellas:** 86
**Descripción:** Lista machine-readable de endpoints de APIs de transporte

### Protocolos documentados:
- HAFAS (mgate.exe, query.exe)
- EFA (XML/JSON)
- Navitia
- OpenTripPlanner (REST, GraphQL)
- TRIAS
- MOTIS

### Campos por API:
```json
{
  "name": "Deutsche Bahn",
  "protocol": "hafas-mgate",
  "coverage": {
    "realtime": ["DE"],
    "regular": ["AT", "CH"],
    "any": ["EU"]
  },
  "languages": ["de", "en"],
  "timezone": "Europe/Berlin",
  "attribution": "CC-BY-4.0"
}
```

### Categorías de cobertura:
- **Realtime:** Información precisa con datos live
- **Regular:** Datos razonablemente completos
- **Any:** Datos incompletos/superficiales

**Utilidad:** Para integrar múltiples sistemas regionales.

---

## 28. node-gtfs (GTFS a SQLite)

**URL:** https://github.com/BlinkTagInc/node-gtfs
**Estrellas:** 495
**Lenguaje:** TypeScript
**Descripción:** Import/Export GTFS a SQLite

### Capabilities:
- Import GTFS desde URL o archivo local
- Export a CSV
- Queries espaciales (paradas cercanas)
- GeoJSON conversion
- GTFS-Realtime integration

### GTFS-RT soportado:
```javascript
{
  realtimeAlerts: "https://...",
  realtimeTripUpdates: "https://...",
  realtimeVehiclePositions: "https://..."
}
```

### CLI:
```bash
gtfs-import --configPath config.json
gtfs-export --configPath config.json
```

### API Node.js:
```javascript
import { importGtfs, getStops, getRoutes } from 'gtfs';

await importGtfs(config);
const stops = getStops({ stop_name: 'Madrid' });
const routes = getRoutes({ route_type: 1 }); // Metro
```

### Multi-agency:
```javascript
{
  agencies: [
    { url: "https://metro.gtfs/feed.zip", prefix: "METRO_" },
    { url: "https://bus.gtfs/feed.zip", prefix: "BUS_" }
  ]
}
```

**Utilidad:** Referencia para manejo de GTFS en nuestra API.

---

## 29. Swiss Transport API

**URL:** https://github.com/OpendataCH/Transport
**Estrellas:** 259
**Lenguaje:** PHP (Silex)
**Instancia pública:** transport.opendata.ch

### Stack:
- PHP + Silex framework
- Redis (cache opcional)
- HAFAS backend (XML Fahrplan API)

### Endpoints:
```
GET /v1/locations?query=Zurich
GET /v1/connections?from=Bern&to=Geneva
GET /v1/stationboard?station=Lausanne
```

### Deployment:
```bash
# Docker
docker-compose up

# Local
composer install
php -S localhost:8000 -t web/
```

### Arquitectura:
```
/lib/Transport  → Core library
/web           → HTTP endpoints (api.php, stats.php)
/var           → Cache/runtime
```

**Utilidad:** Referencia para API PHP con HAFAS.

---

## 30. Otras Herramientas Útiles

### BusRouter SG (⭐ 360)
- **URL:** https://github.com/cheeaun/busrouter-sg
- **Descripción:** Visualización de rutas de bus en Singapore
- **Stack:** JavaScript + Parcel
- **Features:** 3D extrusion, offline via service worker
- **Nota:** No hace routing, solo visualización de datos LTA

### GTFS-to-HTML (⭐ 221)
- **URL:** https://github.com/BlinkTagInc/gtfs-to-html
- **Descripción:** Genera horarios HTML/PDF desde GTFS
- **Utilidad:** Para generar documentación de líneas

### VVO Tools (⭐ 109)
- **URL:** https://github.com/kiliankoe/vvo
- **Lenguaje:** Python
- **Descripción:** Herramientas para red de Dresden
- **Utilidad:** Ejemplo de integración regional

---

## 31. Resumen de Topics GitHub

### public-transit (Go)
Solo 2 repos relevantes:
- kiel-live (43⭐) - Real-time tracking
- gogtfs (0⭐) - GTFS structs

### publictransport
- thepublictransport-app (46⭐, Dart) - Flutter app
- gtfstools (45⭐, R) - Análisis GTFS
- tiamat (22⭐, Java) - Stop place management
- vallabus (4⭐, JS) - Valladolid buses

### transport-api
- OpendataCH/Transport (259⭐) - Swiss API
- otp-tutorial (102⭐) - Tutorial OTP
- israel-public-transport-api (8⭐) - SIRI wrapper

---

## 32. Tabla Resumen: Todos los Repos Investigados

| Categoría | Repo | ⭐ | Lang | Relevancia |
|-----------|------|-----|------|------------|
| **Algoritmos** | planarnetwork/raptor | 107 | TS | ⭐⭐⭐ RAPTOR completo |
| | transnetlab/transit-routing | 73 | Py | ⭐⭐⭐ Múltiples algos |
| | aubryio/minotor | 56 | TS | ⭐⭐⭐ Client-side |
| **Enterprise** | OpenTripPlanner | 2100+ | Java | ⭐⭐⭐ Industry standard |
| | Navitia | 447 | Py/C++ | ⭐⭐⭐ Completo |
| | MOTIS | 500+ | C++ | ⭐⭐⭐ Alto rendimiento |
| **Android** | Transportr | 1100+ | Kotlin | ⭐⭐⭐ App referencia |
| | OneBusAway | 530 | Java | ⭐⭐ Con OTP |
| **iOS/Swift** | TripKit | 106 | Swift | ⭐⭐ Consume APIs |
| **Librerías** | public-transport-enabler | 429 | Java | ⭐⭐⭐ Base de apps |
| | node-gtfs | 495 | TS | ⭐⭐ GTFS→SQLite |
| **APIs** | transport.rest | 133 | JS | ⭐⭐ APIs públicas |
| | Swiss Transport | 259 | PHP | ⭐⭐ HAFAS wrapper |
| **Specs** | FPTF | 137 | - | ⭐⭐⭐ JSON format |
| | transport-apis | 86 | - | ⭐⭐ Directorio |

---

## 33. Conclusiones Finales

### Para implementar RAPTOR:
1. **Referencia principal:** `planarnetwork/raptor` (TypeScript) - Implementación más clara y completa
2. **Alternativa Python:** `transnetlab/transit-routing` - Ya en Python, múltiples algoritmos
3. **Paper original:** Delling et al., 2012

### Para la App iOS:
1. **Mantener server-side:** Consumir nuestra API mejorada (simple)
2. **Client-side:** Port de minotor a Swift (offline, privacidad)
3. **Híbrido:** TripKit para otros operadores + nuestra API

### Para schema de response:
- Adoptar estructura FPTF (Journey → Legs → Stopovers)
- Preparar campos para GTFS-RT (delays)
- Incluir platform info

### Arquitectura recomendada:
```
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│   App iOS      │ ←── │   FastAPI      │ ←── │   PostgreSQL   │
│ (consume API)  │     │ + RAPTOR       │     │ + GTFS data    │
└────────────────┘     └────────────────┘     └────────────────┘
```

### Próximo paso inmediato:
Decidir entre implementar RAPTOR o adaptar transit-routing antes de escribir código.

---

## 34. VigoBusAPI (Ejemplo FastAPI España)

**URL:** https://github.com/David-Lor/VigoBusAPI
**Lenguaje:** Python (FastAPI)
**Base de datos:** MongoDB
**Relevancia:** Ejemplo español con stack similar al nuestro

### Arquitectura:
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Fuentes     │ ──► │ FastAPI     │ ──► │ MongoDB     │
│ externas    │     │ (async)     │     │ (cache)     │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Endpoints:
```
GET /stop/<stop_id>              → Metadata de parada
GET /buses/<stop_id>             → Buses llegando (ETAs)
GET /stops?stop_name=<query>     → Búsqueda por nombre
GET /stops?stop_id=<id1>&stop_id=<id2>  → Batch query
GET /docs                        → Swagger UI auto-generado
```

### Patrones interesantes:
- **Multi-layer caching:** Stop cache + Bus cache + MongoDB
- **Data normalization:** Corrige inconsistencias de fuentes externas
- **Async-first:** FastAPI con concurrencia nativa
- **Self-documenting:** Swagger/OpenAPI automático

**Utilidad:** Referencia de API de transporte en Python/FastAPI para España.

---

## 35. awesome-transit (Lista Curada)

**URL:** https://github.com/MobilityData/awesome-transit
**Mantenido por:** MobilityData (org oficial GTFS)
**Descripción:** Lista definitiva de recursos de transit open source

### Routing Engines destacados:
| Nombre | Descripción |
|--------|-------------|
| **R5** | Multimodal routing (Java) para análisis de escenarios |
| **RRRR** | Implementación RAPTOR en C (Rapid Real-time Routing) |
| **OpenTripPlanner** | Plataforma completa de trip planning |

### Librerías GTFS por lenguaje:

**Python:**
- `gtfsdb` - GTFS a database
- `gtfs_kit` - Toolkit análisis
- `partridge` - Parseo rápido
- `gtfspy` - Análisis de redes
- `gtfs2gps` - Convertir a GPS records

**JavaScript/Node:**
- `node-gtfs` - Import/query GTFS
- `gtfs-sequelize` - ORM para GTFS

**R:**
- `tidytransit` - Mapear stops/routes, calcular travel times
- `gtfstools` - Editar y analizar

**Java:**
- OneBusAway GTFS Modules

**Rust:**
- `transit_model` - Conversión entre GTFS, NeTEx, TransXChange

### Herramientas GTFS:
| Categoría | Herramientas |
|-----------|--------------|
| **Editores** | GTFS Editor, static-GTFS-manager, GTFS Studio, Uttu |
| **Validators** | gtfs-validator (MobilityData), Conveyal validator |
| **Converters** | hafas2gtfs, o2g (OSM→GTFS), transit_model |
| **Visualización** | GTFS-to-HTML, GTFS-to-Chart, Peartree |

### GTFS-Realtime:
- `gtfs-realtime-validator` - Validación oficial
- `gtfs-realtime-bindings` - Protocol buffers (Java, Python, Node, Ruby, .NET)
- `gtfsrdb`, `retro-gtfs` - Archivar feeds RT

**Utilidad:** Punto de partida para cualquier herramienta GTFS.

---

## 36. Google Maps Routes API (Transit)

**URL:** https://developers.google.com/maps/documentation/routes/transit-route
**Relevancia:** Referencia de API comercial de routing

### Endpoint:
```
POST https://routes.googleapis.com/directions/v2:computeRoutes
```

### Request básico:
```json
{
  "origin": { "address": "Madrid Atocha" },
  "destination": { "address": "Barcelona Sants" },
  "travelMode": "TRANSIT",
  "departureTime": "2026-01-28T08:00:00Z",
  "computeAlternativeRoutes": true,
  "transitPreferences": {
    "allowedTravelModes": ["SUBWAY", "TRAIN", "RAIL"],
    "routingPreference": "FEWER_TRANSFERS"
  }
}
```

### Headers requeridos:
```
X-Goog-Api-Key: YOUR_API_KEY
X-Goog-FieldMask: routes.legs.steps.transitDetails
```

### Transit Preferences:
| Opción | Valores |
|--------|---------|
| `allowedTravelModes` | BUS, SUBWAY, TRAIN, LIGHT_RAIL, RAIL |
| `routingPreference` | LESS_WALKING, FEWER_TRANSFERS |

### Response incluye:
- Stop info (arrival/departure names, coords)
- Timestamps por leg
- Headsign (dirección del tren)
- Transit agency details
- Vehicle type y line info
- Stop count por segmento
- Fare estimates (opcional)

### Limitaciones Transit:
- ❌ No intermediate waypoints
- ❌ No eco-friendly routes
- ❌ No traffic preferences
- ✅ Hasta 3 alternativas
- ✅ Ventana: 7 días antes a 100 días después

**Utilidad:** Referencia de schema de response para journey planning.

---

## 37. 2GIS Public Transport API

**URL:** https://docs.2gis.com/en/api/navigation/public-transport/overview
**Tipo:** API comercial (Cloud + On-Premise)
**Cobertura:** Rusia principalmente

### Modos soportados (13):
Metro, bus, tram, trolleybus, shuttle taxi, suburban train, light metro, monorail, funicular, river transport, cable car, light rail, underground tram

### Parámetros de ruta:
- Departure time
- Start/end coordinates
- Intermediate waypoints
- Specific transit types
- Schedule consideration
- Max alternatives
- Min direct routes (sin transbordos)

### Response incluye:
- **Geometría completa** en WKT format
- Transit stops y route lists
- **Horarios y arrival times** en cada parada
- Distance total y por segmento
- Pedestrian segment length
- Transfer info

### Pricing:
- Cloud: Por requests/mes
- On-Premise: Instalación privada disponible

**Utilidad:** Referencia de API con geometría WKT y horarios detallados.

---

## 38. Overpass API (OSM Data Extraction)

**URL:** https://wiki.openstreetmap.org/wiki/Overpass_API
**Descripción:** API para extraer datos de OpenStreetMap

### Endpoints públicos:
| Instancia | URL |
|-----------|-----|
| Principal | `https://overpass-api.de/api/interpreter` |
| Swiss | `https://overpass.osm.ch/api/interpreter` |
| VK Maps | `https://maps.mail.ru/osm/tools/overpass/api/interpreter` |

### Query Languages:
**Overpass QL** (recomendado):
```
[out:json];
node[railway=station](around:5000,37.39,-5.99);
out body;
```

**XML format** (alternativo):
```xml
<query type="node">
  <has-kv k="railway" v="station"/>
  <around lat="37.39" lon="-5.99" radius="5000"/>
</query>
```

### Output formats:
- JSON: `[out:json]`
- XML (default)
- CSV: `[out:csv(name,lat,lon)]`
- GeoJSON (via osmtogeojson converter)

### Queries útiles para transporte:

**Bus stops cercanos:**
```
[out:json];
node[highway=bus_stop](around:500,37.39,-5.99);
out body;
```

**Estaciones de metro:**
```
[out:json];
node[railway=station][station=subway](around:10000,37.39,-5.99);
out body;
```

**Línea de metro por ref:**
```
[out:json];
rel[ref="L1"][route=subway];
out body;
>;
out skel;
```

**Paradas de una ruta:**
```
[out:json];
rel[ref="C1"][route=train];
node(r:"stop");
out body;
```

### Rate limits:
- < 10,000 queries/día
- < 1 GB data/día
- Timeout default: 3 min (max ~900s)

**Utilidad:** Extraer datos de plataformas, paradas, geometrías de OSM.

---

## 39. Recursos Adicionales de awesome-transit

### RRRR - Rapid Real-time Routing on RAPTOR
- **Descripción:** Implementación en C del algoritmo RAPTOR
- **Características:** Muy rápido, bajo nivel
- **Uso:** Routing en tiempo real con constraints de memoria

### R5 - Rapid Realistic Routing
- **Lenguaje:** Java
- **Uso:** Análisis de accesibilidad, escenarios de planificación
- **Features:** Multimodal, análisis de cobertura

### gtfspy (Python)
- **URL:** En awesome-transit
- **Features:** Análisis de redes de transporte desde GTFS
- **Uso:** Investigación, visualización de conectividad

### Peartree
- **Descripción:** Convierte GTFS a grafos NetworkX
- **Uso:** Análisis de redes, accesibilidad, isócronas

---

## 40. Comparativa de APIs Comerciales vs Open Source

| Aspecto | Google Routes | 2GIS | OpenTripPlanner | Nuestra API |
|---------|---------------|------|-----------------|-------------|
| **Coste** | $$$ | $$ | Free | Free |
| **Hosting** | Cloud | Cloud/OnPrem | Self-hosted | Self-hosted |
| **Algoritmo** | Propietario | Propietario | RAPTOR + A* | Dijkstra (mejorable) |
| **Alternativas** | 3 max | Configurable | Múltiples | 1 (actualmente) |
| **Realtime** | ✅ | ✅ | ✅ (GTFS-RT) | ❌ (futuro) |
| **Waypoints** | ❌ Transit | ✅ | ✅ | ❌ |
| **Geometría** | Polyline | WKT | GeoJSON | Coords array |
| **Time-dependent** | ✅ | ✅ | ✅ | ❌ (mejorable) |

---

## 41. Stack Recomendado Final

Basado en toda la investigación:

### Corto plazo (mejoras incrementales):
1. **Añadir `departure_time`** al endpoint actual
2. **Usar `stop_times`** para tiempos reales
3. **Devolver 2-3 alternativas** (ejecutar Dijkstra múltiples veces excluyendo rutas previas)

### Medio plazo (RAPTOR):
1. **Referencia:** `planarnetwork/raptor` o `transnetlab/transit-routing`
2. **Implementar:** Core RAPTOR con rondas
3. **Schema:** Adoptar estructura FPTF
4. **Cache:** Pre-calcular stop patterns

### Largo plazo (features avanzados):
1. **GTFS-RT:** Integrar delays en routing
2. **Isócronas:** Calcular área alcanzable en X minutos
3. **Multi-origen:** Queries desde múltiples paradas
4. **OSM Integration:** Extraer walking paths con Overpass

### Herramientas a considerar:
- **Validación GTFS:** MobilityData gtfs-validator
- **Datos OSM:** Overpass API para plataformas/geometrías
- **Visualización:** GTFS-to-HTML para documentación pública
