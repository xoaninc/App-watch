# Documentación API Renfe Server

**Última actualización:** 2026-01-27

---

## IMPORTANTE: Entornos y Ubicaciones

### Los 3 entornos son DIFERENTES

| Entorno | Ubicación | Propósito |
|---------|-----------|-----------|
| **Local (Mac)** | `/Users/juanmaciasgomez/Projects/renfeserver/` | Desarrollo, edición de código |
| **GitHub** | `https://github.com/xoaninc/App-watch` | Control de versiones, backup |
| **Servidor** | `root@juanmacias.com:/var/www/renfeserver/` | Producción, API en vivo |

### Flujo de trabajo CORRECTO

```
1. Editar código en LOCAL
         ↓
2. git add + git commit + git push  →  Sube a GITHUB
         ↓
3. rsync al servidor  →  Despliega en SERVIDOR
         ↓
4. systemctl restart renfeserver  →  Reinicia API
```

### NO confundir

| Acción | Qué hace | Qué NO hace |
|--------|----------|-------------|
| `git push` | Sube código a GitHub | NO actualiza el servidor |
| `rsync` | Copia archivos al servidor | NO hace commit en git |
| `ssh servidor` | Conecta al servidor | NO es tu máquina local |

---

## Archivos de Configuración

### Variables de entorno (.env)

| Archivo | Ubicación | Propósito |
|---------|-----------|-----------|
| `.env` | Servidor `/var/www/renfeserver/` | Producción (BD, API keys) |
| `.env.local` | Local Mac | Desarrollo local |

**NUNCA subir .env a git** - contiene credenciales.

### Base de datos

| Entorno | Host | Base de datos |
|---------|------|---------------|
| Local | localhost | renfe_dev (o igual que prod) |
| Servidor | localhost | renfe |

---

## Indice

1. [Estado del Proyecto](#estado-del-proyecto)
2. [Arquitectura](#arquitectura)
3. [Endpoints API](#endpoints-api)
4. [Base de Datos](#base-de-datos)
5. [Scripts de Importación](#scripts-de-importación)
6. [Despliegue Paso a Paso](#despliegue-paso-a-paso)
7. [Tareas Pendientes](#tareas-pendientes)
8. [Documentación Detallada](#documentación-detallada)
9. [Errores Comunes](#errores-comunes)

---

## Estado del Proyecto

### Resumen

| Métrica | Valor |
|---------|-------|
| Operadores | 18 |
| Redes (networks) | 31 |
| Paradas | ~6,700 |
| Rutas | ~400 |
| Trips | ~150,000 |
| Stop Times | ~2,170,000 |
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
| Metrovalencia | ✅ | - | ✅ 900 pts | ✅ 181,995 |
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

### Algoritmo de Routing (RAPTOR)

| Fase | Estado | Descripción |
|------|--------|-------------|
| Fase 1: Preparación | ✅ Completado | Estructuras de datos, carga de trips/stop_times |
| Fase 2: Algoritmo Core | ✅ Completado | RAPTOR con rondas y filtro Pareto |
| Fase 3: Integración | ✅ Completado | Endpoint `/route-planner` con RAPTOR |
| **Fase 4: Optimización** | **PENDIENTE** | Tests unitarios, cache, rendimiento |

---

## Arquitectura

### Estructura de Carpetas

```
renfeserver/
├── src/
│   └── gtfs_bc/                    # Código principal
│       ├── network/                # Redes de transporte
│       ├── route/                  # Rutas y shapes
│       ├── stop/                   # Paradas y plataformas
│       ├── trip/                   # Viajes y horarios
│       ├── realtime/               # GTFS-RT (tiempo real)
│       ├── routing/                # Algoritmo RAPTOR
│       │   ├── raptor.py           # Algoritmo core
│       │   └── raptor_service.py   # Servicio para API
│       └── province/               # Lookup por coordenadas
│
├── adapters/http/api/gtfs/
│   ├── routers/                    # Endpoints FastAPI
│   │   └── query_router.py         # /route-planner, /departures
│   └── schemas/                    # Pydantic models
│
├── scripts/                        # Scripts de importación
│   ├── import_gtfs_static.py       # Importar Renfe GTFS
│   ├── import_metro_sevilla_gtfs.py
│   ├── import_metro_granada_gtfs.py
│   └── import_osm_correspondences.py
│
├── alembic/                        # Migraciones de BD
│   └── versions/
│
├── data/                           # Archivos GTFS descargados (solo en servidor)
│
└── docs/                           # Esta documentación
```

### Tecnologías

| Componente | Tecnología | Versión |
|------------|------------|---------|
| Backend | FastAPI | - |
| Python | Python | 3.14 |
| Base de datos | PostgreSQL + PostGIS | 16 |
| Servidor web | Uvicorn + systemd | - |
| Cache | Redis | opcional |

---

## Endpoints API

**Base URL:** `https://juanmacias.com/api/v1/gtfs/`

### Route Planner (RAPTOR)

Calcula rutas entre dos paradas usando horarios reales.

```
GET /route-planner?from={stop_id}&to={stop_id}&departure_time={HH:MM}
```

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| from | string | SÍ | - | ID parada origen (ej: `METRO_SEV_L1_E1`) |
| to | string | SÍ | - | ID parada destino |
| departure_time | string | NO | hora actual | Formato HH:MM |
| max_transfers | int | NO | 3 | Máximo transbordos (0-5) |

**Ejemplo:**
```bash
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_GRANADA_1&to=METRO_GRANADA_26"
```

### Shapes (geometría de rutas)

Devuelve los puntos para dibujar una línea en el mapa.

```
GET /routes/{route_id}/shape?max_gap={metros}
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| max_gap | float | null | Si se especifica, interpola puntos para que no haya gaps mayores (10-500m) |

**Ejemplo:**
```bash
curl "https://juanmacias.com/api/v1/gtfs/routes/METRO_SEV_L1_CE_OQ/shape"
```

### Platforms (andenes)

Devuelve coordenadas de cada andén por línea en una estación.

```
GET /stops/{stop_id}/platforms
```

**Ejemplo:**
```bash
curl "https://juanmacias.com/api/v1/gtfs/stops/METRO_120/platforms"
```

### Correspondences (transbordos a pie)

Devuelve conexiones a pie a otras estaciones cercanas.

```
GET /stops/{stop_id}/correspondences
```

**Ejemplo:**
```bash
curl "https://juanmacias.com/api/v1/gtfs/stops/METRO_SEV_L1_E10/correspondences"
```

### Departures (salidas)

Devuelve próximas salidas desde una parada.

```
GET /stops/{stop_id}/departures
```

**Ejemplo:**
```bash
curl "https://juanmacias.com/api/v1/gtfs/stops/METRO_GRANADA_1/departures"
```

### Networks por Coordenadas

Devuelve redes de transporte disponibles en unas coordenadas.

```
GET /coordinates/routes?lat={lat}&lon={lon}
```

**Ejemplo:**
```bash
curl "https://juanmacias.com/api/v1/gtfs/coordinates/routes?lat=41.3851&lon=2.1734"
```

---

## Base de Datos

### Tablas Principales

| Tabla | Registros | Descripción |
|-------|-----------|-------------|
| gtfs_networks | 31 | Redes de transporte (10T, TMB_METRO, etc.) |
| gtfs_routes | 325 | Líneas/rutas (C1, L1, R1, etc.) |
| gtfs_stops | 6,709 | Paradas con coordenadas |
| gtfs_trips | 139,820 | Viajes individuales |
| gtfs_stop_times | 1,988,956 | Horarios: qué trip para en qué parada a qué hora |
| gtfs_calendar | ~400 | Qué servicios operan qué días |
| gtfs_calendar_dates | ~130 | Excepciones (festivos, servicios especiales) |
| gtfs_shape_points | 650,332 | Puntos de geometría para dibujar rutas |
| stop_platform | 2,989 | Coordenadas de andenes por línea |
| stop_correspondence | 218 | Transbordos a pie entre estaciones |
| network_provinces | 37 | Qué redes operan en qué provincias |
| spanish_provinces | 52 | Polígonos PostGIS de provincias |

### Migraciones Importantes

| Número | Descripción |
|--------|-------------|
| 024 | Reemplaza gtfs_nucleos por network_provinces |
| 029 | Crea tabla stop_platform |
| 031 | Crea tabla stop_correspondence |

---

## Scripts de Importación

**IMPORTANTE:** Los scripts se ejecutan en el SERVIDOR, no en local, porque necesitan acceso a la BD de producción y a los archivos GTFS.

### Conectar al servidor

```bash
ssh root@juanmacias.com
cd /var/www/renfeserver
```

### Renfe Cercanías

```bash
# Importar TODAS las redes de Cercanías
python scripts/import_gtfs_static.py --nucleo all

# Importar red específica (ej: 30 = Sevilla)
python scripts/import_gtfs_static.py --nucleo 30
```

**Códigos de núcleo Renfe:**
| Código | Red |
|--------|-----|
| 10 | Madrid |
| 20 | Asturias |
| 30 | Sevilla |
| 31 | Cádiz |
| 32 | Málaga |
| 40 | Valencia |
| 41 | Murcia/Alicante |
| 51 | Rodalies Catalunya |
| 60 | Bilbao |
| 61 | San Sebastián |
| 62 | Santander |
| 70 | Zaragoza |

### Metro Sevilla

```bash
python scripts/import_metro_sevilla_gtfs.py
```

**Requiere:** Archivo GTFS en `/var/www/renfeserver/data/metro_sevilla.zip`

### Metro Granada

```bash
python scripts/import_metro_granada_gtfs.py
```

**Requiere:** Archivo GTFS en `/var/www/renfeserver/data/metro_granada.zip`

### Metrovalencia

```bash
# Descargar desde NAP (requiere NAP_API_KEY en .env.local)
curl -s "https://nap.transportes.gob.es/api/Fichero/download/1168" \
    -H "ApiKey: $NAP_API_KEY" -o /tmp/metrovalencia.zip
unzip /tmp/metrovalencia.zip -d /tmp/metrovalencia_gtfs

# Importar
python scripts/import_metrovalencia_gtfs.py --gtfs-dir /tmp/metrovalencia_gtfs
```

**NAP:** conjuntoDatoId=967, ficheroId=1168

### Correspondencias desde OSM

```bash
# Todas las ciudades
python scripts/import_osm_correspondences.py --all

# Ciudad específica
python scripts/import_osm_correspondences.py --city madrid
python scripts/import_osm_correspondences.py --city barcelona
python scripts/import_osm_correspondences.py --city bilbao
```

### Plataformas

```bash
python scripts/import_stop_platforms.py
```

---

## Despliegue Paso a Paso

### 1. Hacer cambios en LOCAL

```bash
cd /Users/juanmaciasgomez/Projects/renfeserver
# Editar archivos...
```

### 2. Commit y push a GITHUB

```bash
git add <archivos>
git commit -m "Descripción del cambio"
git push origin main
```

**Esto solo sube el código a GitHub. El servidor NO se actualiza todavía.**

### 3. Desplegar al SERVIDOR

```bash
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.env' --exclude='.env.local' --exclude='venv' --exclude='.venv' \
  --exclude='data' --exclude='*.sql' \
  /Users/juanmaciasgomez/Projects/renfeserver/ root@juanmacias.com:/var/www/renfeserver/
```

### 4. Reiniciar el servicio (si hay cambios de código Python)

```bash
ssh root@juanmacias.com "systemctl restart renfeserver"
```

### 5. Verificar que funciona

```bash
curl "https://juanmacias.com/api/v1/gtfs/stops/METRO_GRANADA_1/departures"
```

---

## Tareas Pendientes

### Fase 4 RAPTOR - Optimización

| Tarea | Prioridad | Descripción |
|-------|-----------|-------------|
| Tests unitarios RAPTOR | Alta | Crear tests en `tests/` para el algoritmo |
| Cache de patrones de trips | Media | Cachear trips activos por fecha |
| Índices para búsqueda binaria | Media | Optimizar búsqueda en stop_times |
| Paralelización | Baja | Paralelizar escaneo de rutas |

### Baja Prioridad (ignorar por ahora)

| Tarea | Notas |
|-------|-------|
| API Valencia tiempo real | La API de FGV devuelve vacío |

---

## Documentación Detallada

| Documento | Cuándo consultarlo |
|-----------|-------------------|
| [RAPTOR_IMPLEMENTATION_PLAN.md](RAPTOR_IMPLEMENTATION_PLAN.md) | Para entender el algoritmo de routing, bugs conocidos, notas técnicas |
| [TODO_PENDIENTE.md](TODO_PENDIENTE.md) | Para ver historial de lo que se ha hecho, estado de shapes por red |
| [GTFS_OPERATORS_STATUS.md](GTFS_OPERATORS_STATUS.md) | Para ver URLs de GTFS de cada operador, qué tiene cada uno |
| [PLATFORMS_AND_CORRESPONDENCES.md](PLATFORMS_AND_CORRESPONDENCES.md) | Para entender el sistema de andenes y transbordos |
| [ARCHITECTURE_NETWORK_PROVINCES.md](ARCHITECTURE_NETWORK_PROVINCES.md) | Para entender cómo se organizan las redes por provincia |

### Archivados (docs/archive/)

Documentación antigua que ya no se usa pero se guarda como referencia:
- Algoritmo Dijkstra (reemplazado por RAPTOR)
- Research de algoritmos
- Guías de importación completadas
- Instrucciones para app iOS

---

## Errores Comunes

### "No encuentro los cambios en producción"

**Causa:** Hiciste `git push` pero no `rsync`.

**Solución:** Ejecuta el comando rsync del paso 3 de Despliegue.

### "El endpoint devuelve error 500"

**Causa:** El servicio necesita reiniciarse.

**Solución:**
```bash
ssh root@juanmacias.com "systemctl restart renfeserver"
```

### "Los stop_times no se importaron"

**Causa:** El archivo GTFS no está en el servidor.

**Solución:**
1. Descargar el GTFS del NAP o URL del operador
2. Subir a `/var/www/renfeserver/data/`
3. Ejecutar el script de importación

### "Foreign key constraint en calendar_dates"

**Causa:** El GTFS tiene service_ids en calendar_dates que no existen en calendar.

**Solución:** Los scripts de Metro Sevilla y Granada ya manejan esto creando entradas dummy en calendar.

### "Permission denied al hacer git push"

**Causa:** Credenciales de git mal cacheadas.

**Solución:**
```bash
git credential-osxkeychain erase
host=github.com
protocol=https
# Presionar Enter dos veces
```

---

## URLs de Producción

- **API principal:** https://juanmacias.com/api/v1/gtfs/
- **API alternativa:** https://redcercanias.com/api/v1/gtfs/
- **GitHub:** https://github.com/xoaninc/App-watch

---

## Historial de Cambios

### 2026-01-31

- **Metrovalencia:** Importados 10,348 trips y 181,995 stop_times desde NAP
- Añadidas 75 rutas nuevas (variantes L4, L6, L8)
- Configurados 4 calendarios (L-J, V, S, D) y 14 festivos Valencia 2026
- Creado script `import_metrovalencia_gtfs.py`
- Documentación NAP actualizada con instrucciones de API

### 2026-01-27

- Metro Granada: Importados 5,693 trips y 143,098 stop_times
- Metro Sevilla: Verificado funcionamiento (válido hasta 2026-12-31)
- Shapes bidireccionales corregidos
- Documentación reorganizada

### 2026-01-26

- Metro Madrid shapes importados (57k puntos)
- Shapes OSM para Metrovalencia y TRAM Alicante
- Correspondencias completadas para todas las ciudades principales
- Fix headsigns vacíos y CIVIS
