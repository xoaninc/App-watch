# Epic 05: Enriquecimiento con Datos de Wikipedia

## Objetivo
Obtener información adicional de las líneas desde Wikipedia, como colores oficiales, logos y descripciones, para enriquecer la información mostrada al usuario.

## Fuentes de Datos
- Wikipedia: Artículos de Cercanías Sevilla
- Wikimedia Commons: Logos e iconos

## User Stories

### US-05.1: Scraping de información de líneas
**Como** sistema
**Quiero** obtener información de líneas desde Wikipedia
**Para** tener datos enriquecidos

**Datos a obtener:**
- Color oficial de cada línea
- Logo/icono de la línea
- Descripción de la línea
- Estaciones principales
- Longitud del recorrido
- Frecuencia típica

### US-05.2: Descarga de logos
**Como** sistema
**Quiero** descargar los logos de las líneas
**Para** mostrarlos en la UI

**Criterios de aceptación:**
- Descargar SVG o PNG de Wikimedia
- Almacenar localmente o en S3
- Generar diferentes tamaños

### US-05.3: Mapeo de datos Wikipedia a GTFS
**Como** sistema
**Quiero** relacionar datos de Wikipedia con entidades GTFS
**Para** enriquecer la información

**Criterios de aceptación:**
- Mapear por nombre de línea
- Validar consistencia de datos
- Manejar discrepancias

### US-05.4: Información de estaciones emblemáticas
**Como** sistema
**Quiero** obtener información extra de estaciones principales
**Para** mostrar datos interesantes

**Datos a obtener:**
- Foto de la estación
- Año de inauguración
- Servicios disponibles
- Conexiones con otros transportes

## Modelo de Datos

```
RouteMetadata (
    route_id,
    wikipedia_url,
    official_color,
    logo_url,
    description,
    length_km,
    typical_frequency_minutes,
    updated_at
)

StopMetadata (
    stop_id,
    wikipedia_url,
    photo_url,
    inauguration_year,
    services[],
    connections[],
    updated_at
)
```

## Tareas Técnicas
1. Implementar scraper de Wikipedia (BeautifulSoup)
2. Crear parser de tablas de Wikipedia
3. Implementar descarga de imágenes de Wikimedia
4. Crear modelos de metadatos
5. Implementar servicio de mapeo
6. Crear comando de actualización manual
7. Añadir job periódico de actualización
