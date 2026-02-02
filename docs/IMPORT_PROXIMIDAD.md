# Importación de GTFS Proximidad

## Descripción

**Proximidad** es un servicio de Renfe que funciona como cercanías en zonas sin red oficial de Cercanías. Son trenes regionales frecuentes con paradas en todas las estaciones, orientados a desplazamientos locales.

El GTFS de Proximidad está **incluido dentro del feed AVE/LD** (`RENFE_AVLD`), identificado por `route_short_name = 'PROXIMDAD'` (sic, así lo escribe Renfe).

## Estrategia de integración

### Problema
Si creamos paradas separadas para Proximidad, estaciones como Álora aparecerían duplicadas en la app:
- ❌ "Álora (Cercanías)"
- ❌ "Álora (Proximidad)"

### Solución
**Usar los mismos stop_id, diferentes redes/rutas:**

```
Parada: RENFE_54405 (Álora)
├── Red: 34T (Cercanías Málaga)
│   └── Ruta: C2 → servicios Cercanías
└── Red: PROX_MAL (Proximidad Málaga)
    └── Ruta: PROX → servicios a El Chorro
```

### Resultado en la app
El usuario ve **una sola parada** con salidas de ambos servicios mezcladas:

```
Álora - Próximas salidas:
┌──────┬────────┬─────────────────┬─────────────┐
│ Hora │ Línea  │ Destino         │ Tipo        │
├──────┼────────┼─────────────────┼─────────────┤
│07:15 │ C2     │ Málaga Centro   │ Cercanías   │
│07:45 │ PROX   │ El Chorro       │ Proximidad  │
│08:00 │ C2     │ Málaga Centro   │ Cercanías   │
│08:30 │ PROX   │ Málaga Centro   │ Proximidad  │
└──────┴────────┴─────────────────┴─────────────┘
```

### Implementación
1. **Stop IDs**: Usar formato `RENFE_{código}` (igual que Cercanías)
2. **Route IDs**: Usar formato `RENFE_PROX_{zona}` (ej: `RENFE_PROX_MAL`)
3. **Network IDs**: Crear redes separadas (PROX_MAL, PROX_CYL, etc.)
4. **Stops**: UPSERT - si existe usa el existente, si no lo crea
5. **Logo**: Cada red Proximidad usa `/static/logos/proximidad.png`

### Ventajas
- ✅ Una sola parada por estación (sin duplicados)
- ✅ Salidas de Cercanías y Proximidad juntas
- ✅ Badge de línea diferencia el servicio (C2 vs PROX)
- ✅ Logo de red diferencia visualmente
- ✅ Correspondencias automáticas (misma parada)

## Redes de Proximidad

| Red | Código | Estaciones | Viajes |
|-----|--------|------------|--------|
| Castilla y León | PROX_CYL | Medina del Campo, Valladolid, Venta de Baños, Palencia | ~63 |
| Madrid-Illescas | PROX_MAD | Madrid Atocha, Illescas | ~42 |
| Córdoba | PROX_COR | Córdoba, Villa del Río, Alcolea, Palma del Río, Villarrubia, Campus Rabanales | ~65 |
| Málaga | PROX_MAL | Málaga Centro, María Zambrano, El Chorro-Caminito del Rey | ~15 |
| Murcia-Cartagena | PROX_MUR | Murcia, Cartagena | ~30 |

**Total: ~215 servicios de Proximidad**

## Diferencias con otros servicios

| Servicio | Tipo | En app |
|----------|------|--------|
| **Cercanías** | Suburban commuter (núcleos 10T-70T) | ✅ |
| **FEVE** | Vía estrecha (45T-47T) | ✅ |
| **Proximidad** | Regional frecuente tipo cercanías | ✅ (a importar) |
| Media Distancia | Regional largo | ❌ |
| Regional/REG.EXP | Regional | ❌ |
| AVE/ALVIA/AVANT | Larga distancia | ❌ |

## Descarga del GTFS

El GTFS de Proximidad está dentro del feed AVE/Larga Distancia:
```
https://ssl.renfe.com/ftransit/Fichero_AVLD_FOMENTO/
```

**Nota:** Es una carpeta (no ZIP) que contiene AVE, ALVIA, MD, Regional Y Proximidad mezclados. El script debe filtrar solo `route_short_name = 'PROXIMDAD'`.

## Estructura del GTFS AVLD

```
RENFE_AVLD/
├── agency.txt      (1 agencia: RENFE OPERADORA)
├── calendar.txt    (~2MB)
├── calendar_dates.txt (~20MB)
├── routes.txt      (629 rutas, 38 son PROXIMDAD)
├── stops.txt       (~4,400 paradas)
├── stop_times.txt  (~16MB)
└── trips.txt       (~2MB)
```

## Identificación de rutas Proximidad

### Por route_short_name
```
route_short_name = 'PROXIMDAD'
```

### Formato de route_id
```
{origen}{destino}VRN

Ejemplos:
- 5451754403VRN = Málaga Centro (54517) → El Chorro (54403)
- 1050010600VRN = Medina del Campo (10500) → Valladolid (10600)
- 6120061307VRN = Murcia (61200) → Cartagena (61307)
```

### Códigos de estación por zona

| Zona | Prefijo | Ejemplo |
|------|---------|---------|
| Castilla y León | 105xx, 106xx, 110xx, 141xx | 10600 = Valladolid |
| Madrid | 180xx | 18000 = Madrid Atocha |
| Toledo/Illescas | 350xx | 35005 = Illescas |
| Córdoba | 504xx, 505xx | 50500 = Córdoba |
| Málaga | 544xx, 545xx | 54403 = El Chorro |
| Murcia | 612xx, 613xx | 61200 = Murcia |

## Detalle por red

### PROX_CYL (Castilla y León)
```
Medina del Campo (10500)
    ↓
Valladolid (10600)
    ↓
Valladolid-Universidad (10610)
    ↓
Venta de Baños (11000)
    ↓
Palencia (14100)
```
- **63 servicios/día**
- Conecta las principales ciudades de CyL

### PROX_MAD (Madrid-Illescas)
```
Madrid Atocha Cercanías (18000)
    ↓
Leganés (35001)
    ↓
Fuenlabrada (35002)
    ↓
Humanes (35012)
    ↓
Illescas (35005)
```
- **42 servicios/día**
- Extensión sur de Madrid hacia Toledo
- Fuenlabrada y Humanes también tienen Cercanías C5 (línea diferente)

### PROX_COR (Córdoba)
```
Córdoba (50500)
    ↓
Villarrubia de Córdoba (50502)
    ↓
Alcolea de Córdoba (50413)
    ↓
Campus Rabanales (50417)
    ↓
Villa del Río (50407)
    ↓
Palma del Río (50506)
```
- **65 servicios/día**
- Red regional de Córdoba

### PROX_MAL (Málaga)
```
Málaga Centro Alameda (54517)
    ↓
Málaga María Zambrano (54413)
    ↓
El Chorro-Caminito del Rey (54403)
```
- **15 servicios/día**
- Incluye la famosa parada de El Chorro

### PROX_MUR (Murcia-Cartagena)
```
Murcia (61200)
    ↓
Cartagena (61307)
```
- **30 servicios/día**
- **Nota:** Diferente de FEVE 45T (Cartagena-Los Nietos)

## Uso del script

### Listar redes disponibles
```bash
cd /var/www/renfeserver
source .venv/bin/activate
PYTHONPATH=/var/www/renfeserver python scripts/import_proximidad_gtfs.py /path/to/RENFE_AVLD/ --list-networks
```

### Importar todas las redes Proximidad
```bash
PYTHONPATH=/var/www/renfeserver python scripts/import_proximidad_gtfs.py /path/to/RENFE_AVLD/
```

### Importar una red específica
```bash
# Solo Málaga (El Chorro)
PYTHONPATH=/var/www/renfeserver python scripts/import_proximidad_gtfs.py /path/to/RENFE_AVLD/ --network PROX_MAL

# Solo Castilla y León
PYTHONPATH=/var/www/renfeserver python scripts/import_proximidad_gtfs.py /path/to/RENFE_AVLD/ --network PROX_CYL
```

## Configuración de redes

| Red | Código | Color | Logo |
|-----|--------|-------|------|
| Castilla y León | PROX_CYL | Por definir | `/static/logos/proximidad.png` |
| Madrid-Illescas | PROX_MAD | Por definir | `/static/logos/proximidad.png` |
| Córdoba | PROX_COR | Por definir | `/static/logos/proximidad.png` |
| Málaga | PROX_MAL | Por definir | `/static/logos/proximidad.png` |
| Murcia-Cartagena | PROX_MUR | Por definir | `/static/logos/proximidad.png` |

## GTFS-RT (Tiempo Real)

**⚠️ Estado desconocido:** No se ha verificado si Renfe proporciona GTFS-RT para servicios de Proximidad.

Posibilidades:
1. Incluido en el feed general de Renfe (`gtfsrt.renfe.com`) - **a verificar**
2. Sin soporte RT (como FEVE)

## Correspondencias

### Correspondencias automáticas (mismo stop_id)

Al usar los mismos stop_id que Cercanías, las correspondencias son **automáticas**:

| Parada | ID | Cercanías | Proximidad |
|--------|-----|-----------|------------|
| Málaga Centro | RENFE_54517 | C1, C2 (34T) | PROX_MAL |
| Madrid Atocha | RENFE_18000 | C1-C10 (10T) | PROX_MAD |
| Murcia | RENFE_61200 | C1, C2 (41T) | PROX_MUR |

**No hay que crear correspondencias** - al ser la misma parada, el usuario ve todos los servicios juntos.

### Correspondencias manuales necesarias

Solo hay que crear correspondencia cuando son **estaciones diferentes pero cercanas**:

| Proximidad | Conecta con | Tipo | Distancia |
|------------|-------------|------|-----------|
| RENFE_54413 (M. Zambrano Prox) | RENFE_54500 (M. Zambrano Cerc) | Cercanías 34T | ~0m (misma estación) |
| RENFE_61307 (Cartagena) | RENFE_5951 (Cartagena-Plaza Bastarreche) | FEVE 45T | ~500m |

```sql
-- María Zambrano: Proximidad usa ID diferente a Cercanías (misma estación física)
INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
VALUES ('RENFE_54413', 'RENFE_54500', 0, 0, 'manual')
ON CONFLICT DO NOTHING;

INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
VALUES ('RENFE_54500', 'RENFE_54413', 0, 0, 'manual')
ON CONFLICT DO NOTHING;

-- Cartagena Proximidad ↔ FEVE (estaciones diferentes)
INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
VALUES ('RENFE_61307', 'RENFE_5951', 500, 360, 'manual')
ON CONFLICT DO NOTHING;

INSERT INTO stop_correspondence (from_stop_id, to_stop_id, distance_m, walk_time_s, source)
VALUES ('RENFE_5951', 'RENFE_61307', 500, 360, 'manual')
ON CONFLICT DO NOTHING;
```

**Nota:** María Zambrano usa stop_id diferentes en el GTFS de Cercanías (54500) y Proximidad (54413), por lo que requiere correspondencia manual.

### Paradas exclusivas de Proximidad

Estas paradas **solo tendrán servicios de Proximidad** (no hay Cercanías):

| ID | Nombre | Red | Nota |
|----|--------|-----|------|
| RENFE_54403 | El Chorro-Caminito del Rey | PROX_MAL | Turístico |
| RENFE_35005 | Illescas | PROX_MAD | Sur de Madrid |
| RENFE_50500 | Córdoba | PROX_COR | Central |
| RENFE_50502 | Villarrubia de Córdoba | PROX_COR | |
| RENFE_50413 | Alcolea de Córdoba | PROX_COR | |
| RENFE_50417 | Campus Rabanales | PROX_COR | Universidad |
| RENFE_50407 | Villa del Río | PROX_COR | |
| RENFE_50506 | Palma del Río | PROX_COR | |
| RENFE_10500 | Medina del Campo | PROX_CYL | |
| RENFE_10600 | Valladolid-Campo Grande | PROX_CYL | Central |
| RENFE_10610 | Valladolid-Universidad | PROX_CYL | Universidad |
| RENFE_11000 | Venta de Baños | PROX_CYL | Nudo ferroviario |
| RENFE_14100 | Palencia | PROX_CYL | Central |

## Paradas especiales

### El Chorro-Caminito del Rey (54403)
- **Red:** PROX_MAL
- **Atractivo turístico:** Acceso al famoso Caminito del Rey
- **Servicios:** ~15/día desde Málaga
- **Nota:** NO está en el GTFS de Cercanías, solo en Proximidad

## Troubleshooting

### "Stop not found"
Las paradas de Proximidad usan IDs de 5 dígitos (ej: 54403). Verificar que el mapping maneja correctamente el formato.

### Conflicto con Cercanías
Algunas paradas existen tanto en Cercanías como en Proximidad (ej: Málaga María Zambrano). El script debe manejar esto con UPSERT.

### Datos duplicados
El GTFS AVLD contiene rutas en ambas direcciones. El script debe normalizar para evitar duplicados.

## Post-importación: Corrección de paradas

Después de importar Proximidad, ejecutar el script de corrección:

```bash
cd /var/www/renfeserver
source .venv/bin/activate
PYTHONPATH=/var/www/renfeserver python scripts/fix_proximidad_stops.py
```

Este script:
1. **María Zambrano**: Migra stop_times de RENFE_54413 → RENFE_54500
   - Cercanías usa 54500 (ligado a GTFS-RT, no se puede cambiar)
   - Proximidad usa 54413 en el GTFS (diferente ID)
   - Solución: mover los stop_times al ID de Cercanías
2. **Cartagena**: Crea correspondencia FEVE ↔ Proximidad
   - RENFE_5951 (Plaza Bastarreche) ↔ RENFE_61307 (Cartagena)
   - Distancia: 320m andando (calculado con OSM)
   - Tiempo: ~4 minutos

## Historial

- **2026-02-01**: Importación inicial de Proximidad completada
  - Script: `scripts/import_proximidad_gtfs.py`
  - Networks: 5 creadas (PROX_CYL, PROX_MAD, PROX_COR, PROX_MAL, PROX_MUR)
  - Routes: 5 importadas (una por red)
  - Trips: 215 importados
  - Stop times: 985 importados
  - Stops: 41 usados (todos ya existían de Cercanías)
  - Logo: `/static/logos/proximidad.png`
  - Script corrección: `scripts/fix_proximidad_stops.py`
  - Correspondencia Cartagena: 320m / 4 min (OSM)
