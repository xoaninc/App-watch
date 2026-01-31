# FGC - Correspondencias Multimodales

**Última actualización:** 2026-01-31

---

## Estado Actual

**Correspondencias FGC: 112 total**

| Tipo | Cantidad | Notas |
|------|----------|-------|
| FGC ↔ TMB Metro | 78 | 6 intercambiadores |
| FGC ↔ RENFE | 30 | 6 intercambiadores |
| FGC ↔ TRAM | 0 | Sin intercambiadores directos |

---

## FGC ↔ TMB Metro (6 intercambiadores)

| FGC | TMB | Líneas | Distancia | Tiempo |
|-----|-----|--------|-----------|--------|
| FGC_PC (Catalunya) | Catalunya | L1/L3 | ~137-207m | 2-3 min |
| FGC_PE (Espanya) | Espanya | L1/L3 | ~140-270m | 2-4 min |
| FGC_PR (Provença) | Diagonal | L3/L5 | ~200-380m | 5 min |
| FGC_GR (Gràcia) | Fontana | L3 | ~325m | 5 min |
| FGC_LH (L'Hospitalet) | Av. Carrilet | L1 | ~69m | 1 min |
| FGC_EU (Europa | Fira) | Europa | Fira | L9S | ~181m | 2.5 min |

**Total:** 78 correspondencias (andenes FGC ↔ andenes TMB)

---

## FGC ↔ RENFE Rodalies (6 intercambiadores)

| FGC | RENFE | ID RENFE | Distancia | Tiempo | Notas |
|-----|-------|----------|-----------|--------|-------|
| FGC_PC (Plaça Catalunya) | Barcelona-Pl.Catalunya | RENFE_78805 | ~268m | 5 min | Mismo intercambiador |
| FGC_NO (Sabadell Nord) | Sabadell Nord | RENFE_78709 | ~90m | 2 min | Mismo edificio |
| FGC_EN (Terrassa Est. Nord) | Terrassa | RENFE_78700 | ~103m | 2 min | Mismo edificio |
| FGC_MC (Martorell Central) | Martorell Central | RENFE_72209 | ~3m | 1 min | Misma estación |
| FGC_SV (Sant Vicenç Castellet) | Sant Vicenç Castellet | RENFE_78604 | ~272m | 4-5 min | Cercano |
| FGC_GO (Gornal) | Bellvitge | RENFE_71708 | ~180m | 3 min | Mismo intercambiador R2 |

**Total:** 30 correspondencias (andenes FGC ↔ RENFE)

---

## FGC ↔ TRAM Barcelona

**No hay correspondencias directas.** Ninguna estación FGC tiene TRAM cercano.

---

## Accesos FGC

Los 14 accesos FGC están en la tabla `stop_access`:

| Estación | Accesos | Nombres |
|----------|---------|---------|
| FGC_PC (Catalunya) | 3 | Pelai, Bergara (FGC), Pelai (FGC) |
| FGC_PE (Espanya) | 3 | Gran Via (FGC) x2, Exposició |
| FGC_GR (Gràcia) | 4 | FGC - Gràcia x3, Via Augusta |
| FGC_PR (Provença) | 4 | FGC - Provença x4 |

---

## Script de Creación

**Archivo:** `fgc_multimodal_correspondences.py`

```bash
# Dry-run
python TRANSFER_DOC/FGC/fgc_multimodal_correspondences.py --dry-run

# Ejecutar
python TRANSFER_DOC/FGC/fgc_multimodal_correspondences.py
```

---

## Archivos Relacionados

```
TRANSFER_DOC/FGC/
├── FGC_PROBLEM.md                    # Documentación del problema
├── FGC_FIX.md                        # Cronología del proceso
├── FGC_CORRESPONDENCIAS.md           # Este archivo
├── fgc_multimodal_correspondences.py # Script de correspondencias
├── fgc_populate_tables.py            # Script de andenes/accesos
└── fgc_data.json                     # Datos OSM validados
```

---

## Checklist

- [x] Accesos FGC extraídos de OSM (14)
- [x] Accesos insertados en `stop_access`
- [x] Andenes actualizados con coords OSM (89)
- [x] Vías fantasma eliminadas (8)
- [x] Correspondencias FGC ↔ TMB creadas (78)
- [x] Correspondencias FGC ↔ RENFE creadas (30)
- [x] Gornal ↔ Bellvitge añadido
- [ ] RAPTOR: Pendiente pruebas multimodales
