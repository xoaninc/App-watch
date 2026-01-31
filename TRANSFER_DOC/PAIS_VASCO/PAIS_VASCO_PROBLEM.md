# País Vasco - Documentación del Problema

**Fecha:** 2026-01-31

## 1. Operadores Involucrados

| Operador | Prefijo ID | Tipo | GTFS |
|----------|------------|------|------|
| Metro Bilbao | METRO_BILBAO_ | Metro (L1/L2) | ✅ |
| Euskotren | EUSKOTREN_ | Tren cercanías | ✅ |
| Funicular Artxanda | FUNICULAR_ARTXANDA_ | Funicular | ✅ |
| RENFE Cercanías | RENFE_054xx | Cercanías | ✅ |

## 2. Análisis de transfers.txt

### Metro Bilbao
- **URL GTFS:** https://ctb-gtfs.s3.eu-south-2.amazonaws.com/metrobilbao.zip
- **transfers.txt:** ❌ NO EXISTE
- **pathways.txt:** ❌ NO EXISTE

### Euskotren
- **URL GTFS:** https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfs_euskotren.zip
- **transfers.txt:** ✅ 13 transfers (internos)
- **pathways.txt:** ✅ 77KB

#### Contenido transfers.txt Euskotren:
```
from_stop_id,to_stop_id,transfer_type,min_transfer_time
ES:Euskotren:StopPlace:1468: (Atxuri) ↔ mismo, 60s
ES:Euskotren:StopPlace:1480: (Arriaga) ↔ ES:Euskotren:StopPlace:2577: (Casco Viejo), 120s
ES:Euskotren:StopPlace:1572: (Honduras, Vitoria) ↔ mismo, 60s
ES:Euskotren:StopPlace:2577: (Casco Viejo) ↔ ES:Euskotren:StopPlace:1480: (Arriaga), 120s
ES:Euskotren:StopPlace:2581: (Amara, San Sebastián) ↔ mismo, 60s
ES:Euskotren:StopPlace:2587: (Lemoa) ↔ mismo, 60s
ES:Euskotren:StopPlace:2595: (Sondika) ↔ mismo, 60s
ES:Euskotren:StopPlace:2624: (Herrera, San Sebastián) ↔ mismo, 60s
ES:Euskotren:StopPlace:2637: (Amorebieta) ↔ mismo, 30s
ES:Euskotren:StopPlace:2639: (Etxebarri) ↔ mismo, 60s
ES:Euskotren:StopPlace:2651: (Errekalde, San Sebastián) ↔ mismo, 60s
ES:Euskotren:StopPlace:2666: (Ermua) ↔ mismo, 60s
ES:Euskotren:StopPlace:2670: (Florida, Vitoria) ↔ mismo, 60s
```

**Nota:** Solo 1 par es entre estaciones diferentes (Arriaga ↔ Casco Viejo). El resto son cambios de andén internos.

### Funicular Artxanda
- **transfers.txt:** ❌ NO EXISTE

## 3. Correspondencias Multimodales Detectadas

### Por proximidad (<500m)

#### Metro Bilbao ↔ Euskotren
| Metro Bilbao | Euskotren | Distancia |
|--------------|-----------|-----------|
| METRO_BILBAO_7 (Abando) | Euskotren 1471 (Abando) | 86m |
| METRO_BILBAO_6 (Casco Viejo) | Euskotren 2577 (Casco Viejo) | 125m |
| METRO_BILBAO_10 (San Mamés) | Euskotren 1474 (Sabino Arana) | 128m |
| METRO_BILBAO_10 (San Mamés) | Euskotren 1470 (San Mamés) | 144m |

#### Metro Bilbao ↔ RENFE
| Metro Bilbao | RENFE | Distancia |
|--------------|-------|-----------|
| METRO_BILBAO_7 (Abando) | RENFE_05451 (Bilbao Concordia) | 167m |

#### Euskotren ↔ RENFE
| Euskotren | RENFE | Distancia |
|-----------|-------|-----------|
| Euskotren 1471 (Abando) | RENFE_05451 (Bilbao Concordia) | 98m |
| Euskotren 1480 (Arriaga) | RENFE_05451 (Bilbao Concordia) | 130m |
| Euskotren 1472 (Hospital) | RENFE_05455 (Basurto Hospital) | 209m |

#### Funicular ↔ Euskotren
| Funicular | Euskotren | Distancia |
|-----------|-----------|-----------|
| FUNICULAR_ARTXANDA_12 | Euskotren 2597 (Matiko) | 90m |

## 4. Estado Actual BD (después de limpieza)

```sql
-- 2026-01-31: Eliminadas 12 correspondencias manuales
DELETE FROM stop_correspondence
WHERE source != 'gtfs'
  AND (from_stop_id LIKE 'METRO_BILBAO_%' OR to_stop_id LIKE 'METRO_BILBAO_%'
    OR from_stop_id LIKE 'EUSKOTREN_%' OR to_stop_id LIKE 'EUSKOTREN_%'
    OR from_stop_id LIKE 'FUNICULAR_%' OR to_stop_id LIKE 'FUNICULAR_%');
-- DELETE 12
```

**Correspondencias actuales:** 0 (solo GTFS de Euskotren, que son internos)

## 5. Problema a Resolver

No existen correspondencias multimodales entre:
- Metro Bilbao ↔ Euskotren
- Metro Bilbao ↔ RENFE
- Euskotren ↔ RENFE
- Funicular Artxanda ↔ Euskotren

**Impacto:** El routing RAPTOR no puede calcular rutas multimodales en el País Vasco.

## 6. Solución Propuesta

1. Extraer datos de OSM para verificar intercambiadores
2. Crear correspondencias manuales verificadas
3. Poblar tabla stop_correspondence con source='manual_multimodal'
