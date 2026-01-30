# Plan de Importación - Metro Tenerife

**Fecha:** 2026-01-30

---

## Fuentes de Datos

### GTFS Estático
- **URL:** `https://metrotenerife.com/transit/google_transit.zip`
- **Método:** Descarga directa (sin autenticación)
- **Última actualización archivo:** 12 Feb 2025
- **Validez calendario:** 2024-09-08 hasta 2025-07-15 (CADUCADO)

### APIs Tiempo Real (tranviaonline.metrotenerife.com)
| Endpoint | Estado | Datos |
|----------|--------|-------|
| `/api/stops` | ✅ Funciona | 25 paradas con coordenadas |
| `/api/cargaVehiculo` | ✅ Funciona | Carga de vehículos (ID, fecha, servicio, nivel carga) |
| `/api/lines` | ⚠️ Vacío | Devuelve `[]` |
| `/api/infoStops/vehicleLocation` | ⚠️ Vacío | Sin datos (posiblemente fuera de horario) |

---

## Estado Actual en BD

### Lo que YA existe:
| Elemento | Cantidad | Estado |
|----------|----------|--------|
| Paradas | 25 | ✅ METRO_TENERIFE_01 a _26 (sin 25) |
| Rutas | 2 | ✅ METRO_TENERIFE_L1, METRO_TENERIFE_L2 |
| Calendarios | 7 | ✅ Configurados para 2025-2026 |
| Stop Route Sequence | 36 | ✅ L1: 21 paradas, L2: 6 paradas |

### Lo que FALTA:
| Elemento | Cantidad | Estado |
|----------|----------|--------|
| Trips | 0 | ❌ Pendiente de expandir desde frequencies |
| Stop Times | 0 | ❌ Pendiente de generar |
| Shapes | 0 | ❌ Pendiente de importar (4 en GTFS) |
| Transfers | 0 | ❌ Pendiente de importar (2 en GTFS) |

---

## Contenido del GTFS

### Líneas
| route_id | Nombre | Recorrido | Paradas | Tiempo |
|----------|--------|-----------|---------|--------|
| L1 | Línea 1 | Intercambiador ↔ La Trinidad | 21 | ~37 min |
| L2 | Línea 2 | La Cuesta ↔ Tíncer | 6 | ~10 min |

### Paradas (25 total)
```
L1 (21 paradas):
01-Intercambiador → 02-Fundación → 03-Teatro Guimerá → 04-Weyler →
05-La Paz → 06-Puente Zurita → 07-Cruz del Señor → 08-Conservatorio →
09-Chimisay → 10-Príncipes de España → 11-Hospital La Candelaria →
12-Taco → 13-El Cardonal* → 14-Hospital Universitario* → 15-Las Mantecas →
16-Campus Guajara → 17-Gracia → 18-Museo de la Ciencia → 19-Cruz de Piedra →
20-Padre Anchieta → 21-La Trinidad

L2 (6 paradas):
22-La Cuesta → 23-Ingenieros → 14-Hospital Universitario* →
13-El Cardonal* → 24-San Jerónimo → 26-Tíncer

* Paradas de transbordo L1↔L2
```

### Servicios (calendar.txt)
| service_id | Días | Validez Original |
|------------|------|------------------|
| S1 | Lunes-Viernes | 2024-09-08 a 2025-07-15 |
| S2 | Sábados | 2024-09-08 a 2025-07-15 |
| S3 | Domingos | 2024-09-08 a 2025-07-15 |

### Trips Base (12 total)
| trip_id | Línea | Servicio | Dirección | Destino |
|---------|-------|----------|-----------|---------|
| IT | L1 | S1 | 0 | Trinidad |
| TI | L1 | S1 | 1 | Intercambiador |
| LT | L2 | S1 | 0 | Tíncer |
| TL | L2 | S1 | 1 | La Cuesta |
| ITSA | L1 | S2 | 0 | Trinidad |
| TISA | L1 | S2 | 1 | Intercambiador |
| LTSA | L2 | S2 | 0 | Tíncer |
| TLSA | L2 | S2 | 1 | La Cuesta |
| ITDO | L1 | S3 | 0 | Trinidad |
| TIDO | L1 | S3 | 1 | Intercambiador |
| LTDO | L2 | S3 | 0 | Tíncer |
| TLDO | L2 | S3 | 1 | La Cuesta |

### Frequencies (60 entradas)
**L1 Laborables (S1):**
| Franja | Frecuencia |
|--------|------------|
| 06:00-07:00 | 15 min |
| 07:00-15:00 | 5 min |
| 15:00-20:00 | 6 min |
| 20:00-21:00 | 7.5 min |
| 21:00-24:00 | 15 min |

**L2 Laborables (S1):**
| Franja | Frecuencia |
|--------|------------|
| 06:00-07:00 | 15 min |
| 07:00-15:00 | 9 min |
| 15:00-20:00 | 12 min |
| 20:00-24:00 | 15 min |

**Sábados (S2):** 10-30 min según franja
**Domingos (S3):** 15-30 min según franja

### Shapes (4)
| shape_id | Línea | Dirección | Puntos |
|----------|-------|-----------|--------|
| Shape1 | L1 | Intercambiador → Trinidad | ~54 |
| Shape2 | L1 | Trinidad → Intercambiador | ~54 |
| Shape3 | L2 | La Cuesta → Tíncer | ~13 |
| Shape4 | L2 | Tíncer → La Cuesta | ~13 |

### Transfers (2)
| from_stop | to_stop | Tipo |
|-----------|---------|------|
| 14 (Hospital Universitario) | 14 | Transbordo recomendado |
| 13 (El Cardonal) | 13 | Transbordo recomendado |

---

## Horarios Oficiales Verificados (Web metrotenerife.com)

### Horario de Servicio
- **Laborables (L-V):** 06:00 - 24:00
- **Fines de semana/Festivos:** Servicio continuo con frecuencias reducidas

### Frecuencias Verificadas (Invierno - Laborables)

**Línea 1:**
| Franja | GTFS | Web Oficial | Match |
|--------|------|-------------|-------|
| 06-07h | 15 min | 15 min | ✅ |
| 07-15h | 5 min | 5 min | ✅ |
| 15-20h | 6 min | 6 min | ✅ |
| 20-21h | 7.5 min | 6-12 min | ≈ |
| 21-24h | 15 min | 15 min | ✅ |

**Línea 2:**
| Franja | GTFS | Web Oficial | Match |
|--------|------|-------------|-------|
| 06-07h | 15 min | 15 min | ✅ |
| 07-15h | 9 min | 10 min | ≈ |
| 15-20h | 12 min | 12 min | ✅ |
| 20-24h | 15 min | 15 min | ✅ |

**Conclusión:** Las frecuencias del GTFS coinciden con la web oficial.

---

## Festivos Canarias 2026

### Nacionales
| Fecha | Festivo |
|-------|---------|
| 01-01 | Año Nuevo |
| 06-01 | Reyes |
| 02-04 | Jueves Santo |
| 03-04 | Viernes Santo |
| 01-05 | Día del Trabajo |
| 15-08 | Asunción |
| 12-10 | Fiesta Nacional |
| 01-11 | Todos los Santos |
| 06-12 | Constitución |
| 08-12 | Inmaculada |
| 25-12 | Navidad |

### Autonómicos Canarias
| Fecha | Festivo |
|-------|---------|
| 02-02 | Día de la Candelaria (Virgen de Candelaria) |
| 30-05 | Día de Canarias |

### Locales Santa Cruz de Tenerife (pendiente confirmar)
- Carnaval (fecha variable, febrero-marzo)
- Fiestas de Mayo

---

## Plan de Importación

### Script: `import_metro_tenerife_gtfs.py`

#### 1. Calendarios
- Usar los calendarios existentes en BD (METRO_TENERIFE_S1, S2, S3)
- Ya tienen validez 2025-2026 ✅
- Añadir calendar_dates para festivos de Canarias 2026

#### 2. Trips a Generar (estimación)
| Servicio | L1 trips | L2 trips | Total |
|----------|----------|----------|-------|
| S1 (L-V) | ~400 | ~150 | ~550 |
| S2 (Sábado) | ~150 | ~100 | ~250 |
| S3 (Domingo) | ~100 | ~80 | ~180 |
| **Total** | **~650** | **~330** | **~980** |

**Nota:** Estimación por día. Total con 2 direcciones: ~1,960 trips

#### 3. Stop Times a Generar
- L1: 21 paradas × ~1,300 trips ≈ 27,300 stop_times
- L2: 6 paradas × ~660 trips ≈ 3,960 stop_times
- **Total estimado:** ~31,260 stop_times

#### 4. Shapes a Importar
| shape_id BD | GTFS shape_id | Puntos |
|-------------|---------------|--------|
| METRO_TENERIFE_L1_INT_TRI | Shape1 | ~54 |
| METRO_TENERIFE_L1_TRI_INT | Shape2 | ~54 |
| METRO_TENERIFE_L2_CUE_TIN | Shape3 | ~13 |
| METRO_TENERIFE_L2_TIN_CUE | Shape4 | ~13 |
| **Total** | 4 shapes | ~134 puntos |

#### 5. Transfers a Importar
| from_stop_id | to_stop_id | transfer_type |
|--------------|------------|---------------|
| METRO_TENERIFE_13 | METRO_TENERIFE_13 | 0 |
| METRO_TENERIFE_14 | METRO_TENERIFE_14 | 0 |

---

## Mapeo de IDs

### Paradas
```
GTFS stop_id → BD stop_id
01 → METRO_TENERIFE_01 (Intercambiador)
02 → METRO_TENERIFE_02 (Fundación)
...
21 → METRO_TENERIFE_21 (La Trinidad)
22 → METRO_TENERIFE_22 (La Cuesta)
23 → METRO_TENERIFE_23 (Ingenieros)
24 → METRO_TENERIFE_24 (San Jerónimo)
26 → METRO_TENERIFE_26 (Tíncer)
```

### Rutas
```
GTFS route_id → BD route_id
L1 → METRO_TENERIFE_L1
L2 → METRO_TENERIFE_L2
```

### Servicios
```
GTFS service_id → BD service_id
S1 → METRO_TENERIFE_S1 (ya existe)
S2 → METRO_TENERIFE_S2 (ya existe)
S3 → METRO_TENERIFE_S3 (ya existe)
```

---

## Ejecución

```bash
# 1. Descargar GTFS
cd /tmp && curl -sL "https://metrotenerife.com/transit/google_transit.zip" -o metro_tenerife.zip && unzip -o metro_tenerife.zip -d gtfs_metro_tenerife

# 2. Analizar (sin cambios)
python scripts/import_metro_tenerife_gtfs.py /tmp/gtfs_metro_tenerife --analyze

# 3. Dry run
python scripts/import_metro_tenerife_gtfs.py /tmp/gtfs_metro_tenerife --dry-run

# 4. Importar
python scripts/import_metro_tenerife_gtfs.py /tmp/gtfs_metro_tenerife

# 5. Verificar
curl "https://juanmacias.com/api/v1/gtfs/stops/METRO_TENERIFE_01/departures?limit=5"
```

---

## GTFS-RT Futuro

La API de tiempo real tiene endpoints disponibles pero con datos limitados:

```python
# En multi_operator_fetcher.py (futuro)
GTFS_RT_OPERATORS['metro_tenerife'] = {
    'vehicle_positions_url': 'https://tranviaonline.metrotenerife.com/api/infoStops/vehicleLocation',
    'vehicle_load_url': 'https://tranviaonline.metrotenerife.com/api/cargaVehiculo',
    'format': 'json',
    'enabled': False,  # Habilitar cuando funcione
}
```

---

## Referencias

- Web oficial: https://metrotenerife.com
- Horarios: https://metrotenerife.com/recorridos-y-horarios/
- Tiempo real: https://tranviaonline.metrotenerife.com
- GTFS: https://metrotenerife.com/transit/google_transit.zip
