# Fix: Metro Málaga Duplicados de Horarios

**Fecha:** 2026-01-31
**Problema:** Salidas duplicadas en Metro Málaga
**Estado:** RESUELTO

---

## Problema Detectado

Los usuarios reportaban salidas duplicadas/fantasma en Metro Málaga. Por ejemplo, en la parada El Torcal a las 19:03 aparecían:

- Salidas correctas (verificadas en estación real)
- Salidas incorrectas que no existían

### Captura del problema

```
19:03 - El Torcal (L2)
─────────────────────────────────────
Now    → Guadalmedina      ❌ FALSO
1 min  → Guadalmedina      ✅ REAL
3 min  → Palacio Deportes  ❌ FALSO
6 min  → Palacio Deportes  ✅ REAL
8 min  → Guadalmedina      ✅ REAL
10 min → Guadalmedina      ❌ FALSO
```

---

## Diagnóstico

### Causa raíz

El GTFS de Metro Málaga contiene **dos versiones temporales** de los mismos trips:

| Versión | Patrón | Periodo | Estado |
|---------|--------|---------|--------|
| `_25_02_ogt` | Antigua | ~Febrero 2025 | OBSOLETA |
| `_26_01_ogt` | Actual | Enero 2026+ | VÁLIDA |

El script `import_metro_malaga_gtfs.py` importaba **AMBAS versiones** mapeándolas al mismo `service_id`, causando duplicados.

### Ejemplo de duplicación en BD

```sql
-- Consulta en producción mostraba:
20:26 | Palacio de los Deportes | VIEJO   ← NO DEBERÍA APARECER
20:28 | Palacio de los Deportes | ACTUAL  ← CORRECTO
20:31 | Guadalmedina            | ACTUAL  ← CORRECTO
20:36 | Palacio de los Deportes | VIEJO   ← NO DEBERÍA APARECER
```

### Conteo de trips antes del fix

```
METRO_MALAGA_LABORABLE: 1208 (604 + 604 duplicados)
METRO_MALAGA_VIERNES:   1296 (648 + 648 duplicados)
METRO_MALAGA_SABADO:     916 (448 + 468 duplicados)
METRO_MALAGA_DOMINGO:    808 (404 + 404 duplicados)
METRO_MALAGA_FESTIVO:    453 (solo versión actual)
```

---

## Solución Implementada

### Cambios en `scripts/import_metro_malaga_gtfs.py`

1. **Añadida constante de versión actual:**
```python
CURRENT_VERSION = '_26_01_'
```

2. **Filtro en `import_trips()`:**
```python
# Filter: only import current version trips
if CURRENT_VERSION not in gtfs_service:
    skipped += 1
    continue
```

3. **Filtro en `import_stop_times()`:**
```python
# Filter: only import stop_times for imported trips
if imported_trip_ids and row['trip_id'] not in imported_trip_ids:
    skipped += 1
    continue
```

4. **Filtro en `import_stop_sequences()`:**
```python
# Filter: only process current version trips
if CURRENT_VERSION not in row['service_id']:
    continue
```

---

## Verificación

### Comparación con datos reales de estación

**Hora:** 20:38 - Parada: El Torcal

| GTFS _26_01 | Estación Real | Estado |
|-------------|---------------|--------|
| 20:40:10 → Guadalmedina (2 min) | Guadalmedina 2 min | ✅ |
| 20:45:17 → Palacio (7 min) | Palacio 7 min | ✅ |
| 20:48:25 → Guadalmedina (10 min) | Guadalmedina 10 min | ✅ |
| 20:53:32 → Palacio (15 min) | Palacio 15 min | ✅ |

**Resultado:** 100% coincidencia con horarios reales.

---

## Ejecución del Fix

```bash
# En servidor producción
ssh root@juanmacias.com
cd /var/www/renfeserver
source .venv/bin/activate
python scripts/import_metro_malaga_gtfs.py
```

### Conteo esperado después del fix

```
METRO_MALAGA_LABORABLE: ~604 trips (solo versión actual)
METRO_MALAGA_VIERNES:   ~648 trips
METRO_MALAGA_SABADO:    ~468 trips
METRO_MALAGA_DOMINGO:   ~404 trips
METRO_MALAGA_FESTIVO:   ~453 trips
TOTAL: ~2,577 trips (antes: ~4,681)
```

---

## Notas Adicionales

- El calendario (`gtfs_calendar`) estaba correcto, el filtro por día funcionaba bien
- El problema era exclusivamente en los datos importados (trips duplicados)
- Los shapes no se ven afectados (no tienen versiones temporales)
- Si Metro Málaga actualiza su GTFS con nueva versión, actualizar `CURRENT_VERSION` en el script
