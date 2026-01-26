# Análisis de Correspondencias - Servidor de Producción

**Fecha:** 2026-01-26
**Servidor:** juanmacias.com (renfeserver)

---

## 1. Resumen de Datos en Producción

| Métrica | Valor |
|---------|-------|
| Total stops | 6466 |
| Line transfers | 98 |
| Stops con cor_metro | 2122 |
| Stops con cor_cercanias | 2085 |
| Stops con cor_tranvia | 358 |
| Stops con cor_ml | 62 |

---

## 2. Estado por Red

### Redes Completas (90%+ cor_* poblado)

| Red | Total | cor_metro | cor_cercanias | cor_tranvia | cor_ml |
|-----|-------|-----------|---------------|-------------|--------|
| Metro Madrid | 674 | 96% | 7% | 4% | 0% |
| ML Madrid | 56 | 5% | 5% | 0% | **100%** |
| Metro Bilbao | 191 | **100%** | 10% | 0% | 0% |
| Renfe Cercanías | 791 | 5% | **100%** | 0% | 0% |
| FGC | 302 | 26% | **94%** | 0% | 0% |
| Euskotren | 798 | 10% | **92%** | 0% | 0% |
| Tram Alicante | 70 | 0% | 0% | **100%** | 0% |
| Metro Valencia | 144 | **100%** | 1% | 0% | 0% |
| Metro Sevilla | 21 | **100%** | 4% | 19% | 0% |
| Metro Málaga | 25 | **100%** | 0% | 0% | 0% |
| Metro Granada | 26 | **100%** | 0% | 0% | 0% |
| Metro Tenerife | 25 | 0% | 0% | **100%** | 0% |
| Tranvía Zaragoza | 50 | 0% | 4% | **100%** | 0% |
| Tranvía Murcia | 28 | 0% | 0% | **100%** | 0% |

### Redes con Problemas

| Red | Total | cor_metro | cor_tranvia | Problema |
|-----|-------|-----------|-------------|----------|
| TMB Metro BCN | 3461 | 35% | 0% | Incluye paradas de BUS |
| Tram Barcelona | 172 | 18% | **100%** | ~~Falta cor_tranvia~~ RESUELTO |
| SFM Mallorca | 31 | 32% | 0% | Incompleto |

---

## 3. Detalle TMB Metro Barcelona

El dataset TMB incluye **paradas de BUS mezcladas con metro**:

| Prefijo ID | Total | cor_metro | Tipo |
|------------|-------|-----------|------|
| TMB_METRO_E.* | 504 | 495 (98%) | Estaciones/Entrances |
| TMB_METRO_P.* | 139 | 138 (99%) | Platforms |
| TMB_METRO_1.* | 165 | 164 (99%) | Estaciones L1 |
| TMB_METRO_2.* | 2653 | 417 (16%) | **PARADAS DE BUS** |

**Conclusión:** Las estaciones de metro real (E.*, P.*, 1.*) están bien pobladas (98%+).
Los 2653 registros "TMB_METRO_2.*" son paradas de bus y no necesitan cor_metro.

---

## 4. Intercambiadores Verificados

### Madrid
| Estación | cor_metro | cor_cercanias |
|----------|-----------|---------------|
| Sol | L1, L2, L3 | C3, C4a, C4b |
| Atocha | L1 | C2, C3, C4a, C4b, C5, C7, C8a, C8b, C10 |
| Nuevos Ministerios | L6, L8, L10 | C2, C3, C4a, C4b, C7, C8a, C8b, C10 |
| Chamartín | L1, L10 | C1, C2, C3, C4a, C4b, C7, C8a, C8b, C10 |
| Embajadores | L3, L5 | C5 |

### Bilbao
| Estación | cor_metro | cor_cercanias |
|----------|-----------|---------------|
| Abando | L1, L2 | C1, C2, C3, TR |
| San Mamés | L1, L2 | C1, C2, TR |

### Barcelona
| Estación | cor_metro | cor_cercanias |
|----------|-----------|---------------|
| Sants | L5 | R1, R11, R13-17, R2, R2N, R2S, R3, R4, RG1 |
| Passeig de Gràcia | L1, L3 | R1, R3, R4, RG1 (parcial) |

---

## 5. Pendientes Identificados

### Alta Prioridad
1. ~~**TRAM_BARCELONA**: 172 paradas sin cor_tranvia~~ **RESUELTO 2026-01-26** (OSM data)
2. **Passeig de Gràcia**: Falta L2, L4 en cor_metro

### Media Prioridad
3. **SFM_MALLORCA**: Solo 32% cor_metro, 77% cor_cercanias

### Baja Prioridad (no afecta funcionalidad)
4. TMB_METRO_2.*: Son paradas de bus, no necesitan cor_metro

---

## 6. Comparación con CSV Local

El archivo `docs/estaciones_espana_completo.csv` contenía:
- Renfe Cercanías: 856 estaciones
- Euskotren: 128 estaciones
- FGC: 100 estaciones
- Metro Madrid: 42 estaciones
- Metro Bilbao: 42 estaciones

**Total CSV:** 1168 estaciones con coordenadas de andenes

**Diferencia con servidor:**
- Servidor tiene más paradas (6466) por incluir todas las entradas/plataformas
- CSV tenía datos de coordenadas por andén/línea que el servidor NO tiene
- CSV tenía columna `platform_coords_by_line` que no existe en BD

---

## 7. Próximos Pasos

1. [x] ~~Poblar cor_tranvia en TRAM_BARCELONA (172 paradas)~~ **COMPLETADO 2026-01-26**
2. [ ] Completar Passeig de Gràcia con L2, L4
3. [ ] Decidir si añadir coordenadas por andén a line_transfer (migración 028 ya ejecutada)
4. [ ] Revisar SFM_MALLORCA

---

## 8. Cambios Realizados

### 2026-01-26

**TRAM_BARCELONA cor_tranvia poblado:**
- Fuente: OpenStreetMap (Overpass API)
- Método: Extracción de líneas T1-T6 de rutas TRAM en OSM
- Paradas actualizadas: 172 (100%)
- Líneas asignadas:
  - Trambaix (T1, T2, T3): zona oeste
  - Trambesòs (T4, T5, T6): zona este
  - Ejemplos: Glòries (T4,T5,T6), Francesc Macià (T1,T2,T3)
