# Barcelona - Correspondencias Multimodales (Revisión)

**Fecha:** 2026-01-31

Este documento contiene todas las correspondencias multimodales de Barcelona para revisión antes de despliegue a producción.

---

## Resumen por Operador

| Operador | Estaciones | Andenes | Accesos | Correspondencias |
|----------|------------|---------|---------|------------------|
| TMB Metro | 139 | 165 | 504 | 212 (50 gtfs + 162 manual) |
| FGC | 104 | 190 | 0* | 108 manual |
| TRAM Barcelona | 58 | 114 | - | 28 (26 manual + 2 gtfs) |

*FGC: 14 accesos en stop_access (tabla separada)

---

## Correspondencias TMB Metro

### TMB ↔ FGC (6 intercambiadores)

| TMB | FGC | Distancia | Tiempo | Notas |
|-----|-----|-----------|--------|-------|
| Catalunya (L1/L3) | FGC_PC | ~137-207m | 2-3 min | Mismo intercambiador |
| Espanya (L1/L3) | FGC_PE | ~140-270m | 2-4 min | Mismo intercambiador |
| Diagonal (L3/L5) | FGC_PR | ~200-380m | 5 min | ~200m caminando |
| Fontana (L3) | FGC_GR | ~325m | 5 min | Gràcia FGC |
| Av. Carrilet (L1) | FGC_LH | ~69m | 1 min | Conexión subterránea |
| Europa \| Fira (L9S) | FGC_EU | ~181m | 2.5 min | Intercambiador Fira |

### TMB ↔ RENFE (11 intercambiadores)

| TMB | RENFE | Distancia | Tiempo | Notas |
|-----|-------|-----------|--------|-------|
| Sants Estació (L3/L5) | RENFE_71801 | ~150-192m | 3-4 min | Barcelona-Sants |
| Passeig de Gràcia (L2/L3/L4) | RENFE_71802 | ~100-383m | 3-5 min | Barcelona-P.Gràcia |
| Catalunya (L1/L3) | RENFE_78805 | ~150-180m | 2.5-4 min | Barcelona-Pl.Catalunya |
| Clot (L1/L2) | RENFE_79009 | ~100-121m | 2-3 min | Barcelona-El Clot |
| Arc de Triomf (L1) | RENFE_78804 | ~200m | 5 min | Barcelona-Arc de Triomf |
| La Sagrera (L1/L5/L9N) | RENFE_78806 | ~150-154m | 2-4 min | Barcelona-La Sagrera |
| Fabra i Puig (L1) | RENFE_78802 | ~100m | 3 min | Sant Andreu Arenal |
| Cornellà Centre (L5) | RENFE_72303 | ~200m | 4 min | Cornellà R1/R4 |
| Torre Baró \| Vallbona (L11) | RENFE_78801 | ~218m | 3 min | Torre Baró Rodalies |
| **Sant Andreu (L1)** | RENFE_79004 | ~175m | 3 min | **NUEVO** - Barcelona-Sant Andreu |
| **Aeroport T2 (L9S)** | RENFE_72400 | ~46m | 1 min | **NUEVO** - Aeroport RENFE |

### TMB ↔ TRAM (11 intercambiadores)

#### Trambesòs (T4/T5/T6)

| TMB | TRAM | Distancia | Tiempo | Notas |
|-----|------|-----------|--------|-------|
| Glòries (L1) | TRAM_BARCELONA_BESOS_2003 | ~50m | 2 min | T4/T5/T6 |
| Ciutadella \| Vila Olímpica (L4) | TRAM_BARCELONA_BESOS_2020 | ~138m | 2 min | T4 |
| **Besòs (L4)** | TRAM_BARCELONA_BESOS_2026 | ~56m | 2 min | **NUEVO** - T5/T6 |
| **El Maresme \| Fòrum (L4)** | TRAM_BARCELONA_BESOS_2008 | ~170m | 3 min | **NUEVO** - T4 |
| **Marina (L1)** | TRAM_BARCELONA_BESOS_2022 | ~122m | 2 min | **NUEVO** - T4 |
| **Selva de Mar (L4)** | TRAM_BARCELONA_BESOS_2007 | ~165m | 3 min | **NUEVO** - T4 |
| **Gorg (L2/L10N)** | TRAM_BARCELONA_BESOS_2019 | ~55m | 1 min | **NUEVO** - T5 intercambiador |
| **Sant Roc (L2)** | TRAM_BARCELONA_BESOS_2017 | ~105m | 2 min | **NUEVO** - T5 |

#### Trambaix (T1/T2/T3)

| TMB | TRAM | Distancia | Tiempo | Notas |
|-----|------|-----------|--------|-------|
| Ernest Lluch (L5/L9S) | TRAM_BARCELONA_1011 | ~137m | 2 min | T1/T2/T3 |
| Maria Cristina (L3) | TRAM_BARCELONA_1004 | ~100m | 3 min | T1/T2/T3 |
| Palau Reial (L3) | TRAM_BARCELONA_1008 | ~100m | 3 min | T1/T2/T3 |
| **Cornellà Centre (L5)** | TRAM_BARCELONA_1019 | ~47m | 1 min | **NUEVO** - T1/T2/T3 |
| **Zona Universitària (L3/L9S)** | TRAM_BARCELONA_1009 | ~239-270m | 4 min | **NUEVO** - T1/T2/T3 |

---

## Correspondencias FGC

### FGC ↔ TMB Metro

(Ver sección anterior - bidireccional)

### FGC ↔ RENFE (6 intercambiadores)

| FGC | RENFE | Distancia | Tiempo | Notas |
|-----|-------|-----------|--------|-------|
| Plaça Catalunya (FGC_PC) | RENFE_78805 | ~268m | 5 min | Mismo intercambiador |
| Sabadell Nord (FGC_NO) | RENFE_78709 | ~90m | 2 min | Mismo edificio |
| Terrassa Estació Nord (FGC_EN) | RENFE_78700 | ~103m | 2 min | Mismo edificio |
| Martorell Central (FGC_MC) | RENFE_72209 | ~3m | 1 min | Misma estación |
| Sant Vicenç Castellet (FGC_SV) | RENFE_78604 | ~272-279m | 4-5 min | Cercano |
| **Gornal (FGC_GO)** | RENFE_71708 | ~180m | 3 min | **NUEVO** - Bellvitge R2 |

### FGC ↔ TRAM

**No hay correspondencias directas** - Ninguna estación FGC tiene TRAM cercano.

---

## Transfers Internos (GTFS)

### TMB Metro (50 transfers)

Transfers entre líneas de metro definidos en el GTFS oficial:

| Estación | Líneas | Tiempo |
|----------|--------|--------|
| Diagonal | L3 ↔ L5 | 5 min |
| Passeig de Gràcia | L2 ↔ L3 ↔ L4 | 3-5 min |
| Torrassa | L1 ↔ L9S | 45 seg |
| La Pau | L2 ↔ L4 | 2 min |
| Sagrada Família | L2 ↔ L5 | 2 min |
| Verdaguer | L4 ↔ L5 | 2 min |
| ... | ... | ... |

---

## Correspondencias Añadidas (2026-01-31)

### Nuevas TMB ↔ RENFE

1. **Sant Andreu (L1) ↔ RENFE_79004** - 175m, 3 min
   - Barcelona-Sant Andreu (R1/R3/R4)

2. **Aeroport T2 (L9S) ↔ RENFE_72400** - 46m, 1 min
   - Aeroport RENFE - mismo edificio

### Nuevas TMB ↔ TRAM

1. **Besòs (L4) ↔ TRAM T5/T6** - 56m
2. **El Maresme | Fòrum (L4) ↔ TRAM T4** - 170m
3. **Marina (L1) ↔ TRAM T4** - 122m
4. **Selva de Mar (L4) ↔ TRAM T4** - 165m
5. **Cornellà Centre (L5) ↔ TRAM T1/T2/T3** - 47m
6. **Zona Universitària (L3/L9S) ↔ TRAM T1/T2/T3** - 239m

---

## Verificación de Completitud

### Checklist TMB ↔ FGC

- [x] Catalunya
- [x] Espanya
- [x] Diagonal/Provença
- [x] Fontana/Gràcia
- [x] Av. Carrilet/L'Hospitalet
- [x] Europa | Fira

### Checklist TMB ↔ RENFE

- [x] Sants Estació
- [x] Passeig de Gràcia
- [x] Catalunya
- [x] Clot
- [x] Arc de Triomf
- [x] La Sagrera
- [x] Fabra i Puig
- [x] Cornellà Centre
- [x] Torre Baró | Vallbona
- [x] Sant Andreu (NUEVO)
- [x] Aeroport T2 (NUEVO)

### Checklist TMB ↔ TRAM

#### Trambesòs

- [x] Glòries
- [x] Ciutadella | Vila Olímpica
- [x] Besòs (NUEVO)
- [x] El Maresme | Fòrum (NUEVO)
- [x] Marina (NUEVO)
- [x] Selva de Mar (NUEVO)
- [x] Gorg (NUEVO)
- [x] Sant Roc (NUEVO)

#### Trambaix

- [x] Ernest Lluch
- [x] Maria Cristina
- [x] Palau Reial
- [x] Cornellà Centre (NUEVO)
- [x] Zona Universitària (NUEVO)

### Checklist FGC ↔ RENFE

- [x] Plaça Catalunya
- [x] Sabadell Nord
- [x] Terrassa Estació Nord
- [x] Martorell Central
- [x] Sant Vicenç Castellet
- [x] Gornal ↔ Bellvitge (NUEVO)

---

## Notas de Implementación

1. **Correspondencias bidireccionales**: Todas las correspondencias se insertan en ambas direcciones (A→B y B→A)

2. **Distancias calculadas**: Se usa la distancia real (haversine) entre coordenadas de andenes, no la distancia estimada

3. **Tiempos de transferencia**:
   - <100m: 1-2 min
   - 100-200m: 2-3 min
   - 200-300m: 4-5 min
   - >300m: variable

4. **Source**: Todas las correspondencias multimodales tienen `source='manual_multimodal'`

---

## Archivos Relacionados

```
TRANSFER_DOC/TMB/
├── tmb_multimodal_correspondences.py  # Script de creación
├── TMB_FIX.md                         # Documentación del proceso
└── tmb_api_data.json                  # Datos API TMB

TRANSFER_DOC/FGC/
├── fgc_multimodal_correspondences.py  # Script de creación
└── FGC_FIX.md                         # Documentación del proceso
```

---

## Estado

- [x] **Pruebas RAPTOR** - Verificar que las correspondencias funcionan en routing ✅
- [x] **Despliegue a producción** - Scripts ejecutados en servidor ✅

## ✅ PROCESO COMPLETADO - 2026-01-31

### Resumen del despliegue

| Acción | Resultado |
|--------|-----------|
| TMB correspondencias multimodales | 74 creadas |
| FGC correspondencias multimodales | 26 creadas |
| Total correspondencias Barcelona | 324+ |
| Reinicio servidor | ✅ |
| Health check | ✅ |

### Rutas multimodales verificadas en producción

| Ruta | Tiempo | Transbordos | Estado |
|------|--------|-------------|--------|
| FGC Sarrià → TMB Glòries | 110 min | 2 | ✅ Producción |
| FGC Sabadell Nord → RENFE Sants | 51 min | 0 | ✅ Producción |
| TMB Gorg → TRAM Gorg | 4 min | 0 (walk) | ✅ Producción |

### Changelog

- **2026-01-31 (PM)**: Despliegue a producción completado
- **2026-01-31 (AM)**: Pruebas RAPTOR completadas - Routing multimodal funciona
- **2026-01-31 (AM)**: Añadido Gorg (L2/L10N) ↔ TRAM T5 - intercambiador Badalona
- **2026-01-31 (AM)**: Añadido Sant Roc (L2) ↔ TRAM T5 - Badalona

