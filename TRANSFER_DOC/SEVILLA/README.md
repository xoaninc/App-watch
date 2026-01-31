# Sevilla - Correspondencias Multimodales

**Fecha:** 2026-01-31
**Estado:** Completado

## Operadores

| Operador | Líneas | Estaciones | Accesos | Correspondencias |
|----------|--------|------------|---------|------------------|
| Metro Sevilla | L1 | 21 | 9 (2♿) | 6 pares |
| Tranvía Sevilla | T1 | 7 | - | 6 pares |
| RENFE Cercanías | C1-C5 | 52 | - | 2 pares |

## Red Metro Sevilla L1

**Recorrido:** Ciudad Expo ↔ Olivar de Quintos (21 estaciones)

| ID | Estación | Coords |
|----|----------|--------|
| E1 | Ciudad Expo | 37.349, -6.052 |
| E2 | Cavaleri | 37.353, -6.047 |
| E3 | San Juan Alto | 37.362, -6.039 |
| E4 | San Juan Bajo | 37.367, -6.025 |
| E5 | Blas Infante | 37.373, -6.011 |
| E6 | Parque de los Príncipes | 37.377, -6.004 |
| E7 | Plaza de Cuba | 37.379, -6.000 |
| E8 | **Puerta Jerez** | 37.382, -5.994 |
| E9 | **Prado de San Sebastián** | 37.381, -5.987 |
| E10 | **San Bernardo** | 37.378, -5.979 |
| E11 | **Nervión** | 37.383, -5.974 |
| E12 | Gran Plaza | 37.382, -5.967 |
| E13 | 1º de Mayo | 37.381, -5.956 |
| E14 | Amate | 37.376, -5.953 |
| E15 | La Plata | 37.371, -5.952 |
| E16 | Cocheras | 37.368, -5.950 |
| E17 | Pablo de Olavide | 37.354, -5.943 |
| E18 | Condequinto | 37.346, -5.936 |
| E19 | Montequinto | 37.342, -5.935 |
| E20 | Europa | 37.338, -5.935 |
| E21 | Olivar de Quintos | 37.329, -5.939 |

**Negrita** = Estaciones con correspondencia multimodal

## Red Tranvía Sevilla T1 (MetroCentro)

**Recorrido:** Archivo de Indias ↔ Luis de Morales (7 paradas)

| ID | Parada |
|----|--------|
| ARCHIVO_DE_INDIAS | Archivo de Indias |
| PUERTA_JEREZ | Puerta Jerez |
| PRADO_SAN_SEBASTIÁN | Prado San Sebastián |
| SAN_BERNARDO | San Bernardo |
| SAN_FRANCISCO_JAVIER | San Francisco Javier |
| EDUARDO_DATO | Eduardo Dato |
| LUIS_DE_MORALES | Luis de Morales |

## Correspondencias Multimodales

### Hub San Bernardo (Trimodal)

Intercambiador principal con Metro L1, Tranvía T1 y RENFE Cercanías.

| Origen | Destino | Distancia | Tiempo |
|--------|---------|-----------|--------|
| Metro San Bernardo | Tram San Bernardo | 51m | <1 min |
| Metro San Bernardo | RENFE San Bernardo | 87m | 1 min |
| Tram San Bernardo | RENFE San Bernardo | 96m | 1 min |

### Zona Centro (Metro ↔ Tram)

| Origen | Destino | Distancia | Tiempo |
|--------|---------|-----------|--------|
| Metro Prado | Tram Prado San Sebastián | 33m | <1 min |
| Metro Puerta Jerez | Tram Puerta Jerez | 137m | 2 min |

### Zona Este (Metro ↔ Tram)

| Origen | Destino | Distancia | Tiempo |
|--------|---------|-----------|--------|
| Metro Nervión | Tram Eduardo Dato | 117m | 1.5 min |

## Accesos (Entradas OSM)

| Estación | Accesos | Ascensor |
|----------|---------|----------|
| E6 Parque de los Príncipes | 1 | - |
| E8 Puerta de Jerez | 1 | - |
| E9 Prado San Sebastián | 1 | ♿ |
| E10 San Bernardo | 2 | ♿ (Calle Enramadilla) |
| E15 La Plata | 2 (Norte/Sur) | - |
| E16 Cocheras | 1 | - |
| E17 Pablo de Olavide | 1 | - |

**Total:** 9 accesos, 2 con ascensor

**Sin datos OSM:** E1-E5, E7, E11-E14, E18-E21 (14 estaciones)

## Scripts

### `sevilla_multimodal_correspondences.py`
Crea correspondencias bidireccionales en `stop_correspondence`.

```bash
cd /var/www/renfeserver
source .venv/bin/activate
python TRANSFER_DOC/SEVILLA/sevilla_multimodal_correspondences.py
```

### `sevilla_update_accesses.py`
Importa accesos de Metro desde OSM a `stop_access`.

```bash
python TRANSFER_DOC/SEVILLA/sevilla_update_accesses.py
```

### `sevilla_extract_osm.py`
Extrae datos de OSM para análisis (no modifica BD).

```bash
python TRANSFER_DOC/SEVILLA/sevilla_extract_osm.py
```

## IDs de Referencia

### Metro Sevilla
- Formato: `METRO_SEV_L1_EXX`
- Ejemplo: `METRO_SEV_L1_E10` = San Bernardo

### Tranvía Sevilla
- Formato: `TRAM_SEV_NOMBRE`
- Ejemplo: `TRAM_SEV_SAN_BERNARDO`

### RENFE Cercanías Sevilla
- `RENFE_51003` = Santa Justa (estación principal)
- `RENFE_51100` = San Bernardo
- `RENFE_51110` = Virgen del Rocío

## Notas

- **Santa Justa** (RENFE) está a >1km de Metro/Tram, no hay correspondencia peatonal directa
- **L3 Metro** en construcción (7 estaciones): Pino Montano → La Macarena (no incluido aún)
- Metro Sevilla usa **location_type=1** (estaciones sin andenes separados)

## Verificación

```bash
# Test routing multimodal
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_SEV_L1_E1&to=RENFE_51100&departure_time=08:00"
```

Resultado esperado: Metro L1 Ciudad Expo → San Bernardo + Walking a RENFE
