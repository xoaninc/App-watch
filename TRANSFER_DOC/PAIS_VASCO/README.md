# País Vasco - Correspondencias Multimodales

**Fecha:** 2026-01-31
**Estado:** Completado

## Operadores

| Operador | Estaciones | Andenes | Accesos | Correspondencias |
|----------|------------|---------|---------|------------------|
| Metro Bilbao | 42 | 42 | 107 | 6 pares |
| Euskotren | 128 | 239 | 149 | 6 pares |
| Funicular Artxanda | 2 | 2 | - | 1 par |
| RENFE (enlaces) | - | - | - | 4 pares |

## Correspondencias Multimodales

### Bilbao

| Origen | Destino | Distancia | Tiempo |
|--------|---------|-----------|--------|
| Metro Lutxana | Euskotren Lutxana | 40m | 1 min |
| Metro Abando | Euskotren Abando | 86m | 1.5 min |
| Metro Casco Viejo | Euskotren Zazpikaleak | 125m | 2 min |
| Metro San Mamés | Euskotren San Mamés | 144m | 2.5 min |
| Metro Abando | RENFE Concordia | 167m | 3 min |
| Euskotren Abando | RENFE Concordia | 98m | 2 min |
| Euskotren Hospital | RENFE Basurto | 209m | 3 min |
| Funicular Artxanda | Euskotren Matiko | 90m | 1.5 min |

### Gipuzkoa (C1)

| Origen | Destino | Distancia | Tiempo |
|--------|---------|-----------|--------|
| Euskotren Amara | RENFE Donostia | 675m | 10 min |
| Euskotren Irun Colón | RENFE Irun | 900m | 12 min |

## Scripts

### `pais_vasco_multimodal_correspondences.py`
Crea correspondencias bidireccionales en `stop_correspondence`.

```bash
cd /var/www/renfeserver
source .venv/bin/activate
python TRANSFER_DOC/PAIS_VASCO/pais_vasco_multimodal_correspondences.py
```

### `update_platform_coords.py`
Actualiza coordenadas de andenes Metro Bilbao desde OSM.

```bash
python TRANSFER_DOC/PAIS_VASCO/update_platform_coords.py
```

### `update_euskotren_coords.py`
Actualiza coordenadas de estaciones Euskotren desde OSM.

```bash
python TRANSFER_DOC/PAIS_VASCO/update_euskotren_coords.py
```

### `fix_euskotren_duplicates.py`
Separa andenes Q1/Q2 que tenían coordenadas idénticas (~17m offset).

```bash
python TRANSFER_DOC/PAIS_VASCO/fix_euskotren_duplicates.py
```

## IDs de Referencia

### Metro Bilbao
- Formato: `METRO_BILBAO_X.0` (andenes)
- Ejemplo: `METRO_BILBAO_7.0` = Abando

### Euskotren
- Estaciones: `EUSKOTREN_ES:Euskotren:StopPlace:XXXX:`
- Andenes: `EUSKOTREN_ES:Euskotren:Quay:XXXX_Plataforma_QX:`

### RENFE C1 Gipuzkoa
- `RENFE_11511` = Donostia-San Sebastián
- `RENFE_11600` = Irun

## Verificación

```bash
# Test routing multimodal
curl "https://juanmacias.com/api/v1/gtfs/route-planner?from=METRO_BILBAO_1.0&to=RENFE_11511&departure_time=08:00"
```

Resultado esperado: Metro L2 → Euskotren E1 → Walking a RENFE
