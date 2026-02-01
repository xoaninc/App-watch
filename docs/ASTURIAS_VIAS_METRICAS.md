# Vias por Defecto - Red de Ancho Metrico de Asturias

## Contexto

La red de Cercanias de Asturias (nucleo 20T) tiene dos tipos de lineas:

### Ancho Iberico (1.668 mm) - CON datos RT
- **C1**: Gijon - Puente de los Fierros
- **C2**: Oviedo - El Entrego / Gijon
- **C3**: Llamaquique - San Juan de Nieva

Estas lineas **SI tienen datos de vias en tiempo real** del visor de RENFE (`tiempo-real.renfe.com`), por lo que NO necesitan vias por defecto.

### Ancho Metrico (1.000 mm) - SIN datos RT
- **C4**: Gijon - Cudillero / Candas - Aviles
- **C5**: Gijon - Pola de Laviana / El Berron - Norena
- **C5a/C5A**: El Berron - Oviedo / Gijon - Oviedo
- **C6**: Oviedo - L'Infiestu / Nava - El Berron / Gijon - Pola Siero
- **C7**: Gijon - San Esteban / Oviedo - Trubia
- **C8**: Ablaña - Collanzo

Estas lineas **NO tienen datos de vias en tiempo real**, por lo que necesitamos configurar vias por defecto.

## Fuente de Datos

Las vias por defecto se obtienen de la web de ADIF:
```
https://www.adif.es/w/{codigo}-{nombre}
```

Ejemplo: https://www.adif.es/w/05245-cudillero

## Archivo de Configuracion

Los datos se guardan en: `data/asturias_default_platforms.json`

## Revision Completa (2026-02-01)

Se han revisado **TODAS** las estaciones de las lineas metricas usando la web de ADIF.

### Resumen por Linea

| Linea | Estaciones | Via Unica | Multiples Vias |
|-------|------------|-----------|----------------|
| C4 | 29 | 21 | 8 |
| C5 | 22 | 14 | 8 |
| C5a/C6 | 17 | 9 | 8 |
| C7 | 20 | 15 | 5 |
| C8 | 18 | 17 | 1 |
| **Total** | **112** | **76** | **36** |

**Nota**: Algunas estaciones son compartidas entre líneas (Gijón, Oviedo, Avilés, Veriña, La Corredoria, El Berrón, Noreña, Pravia, Ablaña, La Pereda Riosa).

### Patrones de Vias Especiales

#### Patron FEVE (vias 1, 3)
Estaciones antiguas FEVE con anden central (isla):
- Via 1: Lado del edificio principal
- Via 2: Via de paso sin anden (mercancias)
- Via 3: Anden isla secundario

Estaciones con este patron:
- Trubia (C7)
- Grado (C7)
- Trasona (C4)
- Lieres (C6)

#### Patrones No Consecutivos
- **Piedras Blancas** (C4): vias 1, 5
- **Soto del Barco** (C4): vias 1, 4
- **El Berron** (C5/C5a/C6): vias 5, 7
- **Norena** (C5/C5a): vias 5, 7
- **Pola de Siero** (C6): vias 3, 4 (vias 1-2 deposito)

#### Vias con Sufijo
- **La Felguera-Langreo** (C5): vias 1A, 2A

### Estaciones NO encontradas en ADIF

Todas las estaciones verificadas.

### Vias especiales verificadas

**Via 2 unica (no via 1):**
- Muros del Nalon (05243) - C4
- Soto Udrion (05308) - C7

### URLs especiales de ADIF

Algunas estaciones requieren formatos especiales en la URL:
- `centro-transportes` (sin "de")
- `la-carrera-siero` (sin "de")
- `fuente-santa-nava` (sin "de")
- `el-entrego-oscura` (no "la oscura")
- `infiesto-apd` (abreviado)
- `la-argañosa-lavap.` (con ñ, abreviado)
- `sta.maría-de-grado` (abreviado sta.)
- `muros-nalón` (con tilde)
- `santiago-monte` (sin "del")
- `soto-udrión` (con tilde)
- `peñaflor-de-grado` (con ñ)
- `san-ranón` (con tilde)
- `san-román` (con tilde)
- `baíña` (con tilde)

## Detalle por Linea

### C4: Gijon - Cudillero / Candas - Aviles

| Codigo | Estacion | Vias | Notas |
|--------|----------|------|-------|
| 15410 | Gijon-Sanz Crespo | 1, 2, 3 | Compartida con C1-C3 |
| 15400 | Veriña | 1, 3 | Compartida C1/C4. Via 1 Gijon, via 3 Cudillero |
| 05203 | Tremanes Carreno | 1 | Via unica |
| 05207 | Abono Apeadero | 1 | Via unica |
| 05208 | Xivares | 1 | Via unica |
| 05209 | Perlora | 1, 2 | Dos vias |
| 05210 | Candas Apeadero | 1 | Via unica |
| 05211 | Candas | 1, 3 | Terminal ramal |
| 05213 | Regueral | 1 | Via unica |
| 05215 | Zanzabornin | 1 | Via unica |
| 05216 | Gudin Laminacion | 1 | Via unica |
| 05217 | Trasona | 1, 3 | Patron FEVE |
| 05219 | Llaranes | 1 | Via unica |
| 05220 | Cristaleria | 1 | Via unica |
| 05221 | Aviles Apeadero | 1 | Via unica |
| 16403 | Aviles | 1 | Compartida iberico/metrico |
| 05224 | Raices | 1 | Via unica |
| 05225 | Salinas | 1 | Via unica |
| 05227 | Piedras Blancas | 1, 5 | Patron especial |
| 05229 | Vegarrozadas | 1 | Via unica |
| 05231 | Santiago del Monte | 1 | Via unica |
| 05232 | El Parador | 1 | Via unica |
| 05233 | Soto del Barco | 1, 4 | Patron especial |
| 05235 | Riberas | 1 | Via unica |
| 05237 | Penaullan | 1 | Via unica |
| 05239 | Santianes | 1 | Via unica |
| 05241 | Los Cabos | 1 | Via unica |
| 05243 | Muros del Nalon | 2 | Via 2 unica |
| 05244 | El Pito Pinera | 1 | Via unica |
| 05245 | Cudillero | 1 | Terminal |
| 05325 | Pravia | 1, 2, 3 | Nudo C4/C7 |

### C5: Gijon - Pola de Laviana

| Codigo | Estacion | Vias | Notas |
|--------|----------|------|-------|
| 05403 | Tremanes-Langreo | 1 | Via unica |
| 05405 | Sotiello | 1 | Via unica |
| 05407 | Pinzales | 1 | Via unica |
| 05409 | Aguda | 1 | Via unica |
| 05410 | Xixun | 1, 2 | Via 2 Gijon, via 1 Laviana |
| 05411 | La Florida | 1, 2 | Via 1 Laviana, via 2 Gijon |
| 05412 | Puente Buracos | 1 | Via unica |
| 05413 | Norena | 5, 7 | Via 5 Gijon, via 7 Laviana |
| 05416 | Valdesoto | 1, 2 | Via 1 Gijon, via 2 Laviana |
| 05417 | Carbayin | 1, 2 | Dos vias |
| 05420 | Curuxona | 1 | Via unica |
| 05421 | Tuilla | 1, 2 | Dos vias |
| 05426 | La Felguera-Langreo | 1A, 2A | Vias con sufijo |
| 05427 | Sama Los Llerones | 1A, 2A | Mismo patron que La Felguera |
| 05431 | Ciaño Escobio | 1 | Via unica |
| 05432 | San Vicente | 1 | Via unica |
| 05435 | Carrocera | 1 | Via unica |
| 05436 | San Martin | 1 | Via unica |
| 05437 | Sotrondio | 1 | Via unica |
| 05439 | Blimea | 1 | Via unica |
| 05441 | Barredos | 1 | Via unica |
| 05443 | Laviana | 1 | Terminal |

### C6: Oviedo - Infiesto

| Codigo | Estacion | Vias | Notas |
|--------|----------|------|-------|
| 15211 | Oviedo | 1 (C5a/C6), 2 (C7) | Compartida iberico/metrico |
| 15217 | La Corredoria | 1, 2 | Compartida C1/C3/C6. Via 1 Infiesto, via 2 Oviedo |
| 05504 | Parque Principado | 1, 2 | Via 1 El Berron, via 2 Oviedo |
| 05505 | Colloto | 1, 2 | Via 1 El Berron, via 2 Oviedo |
| 05507 | Meres | 1, 2 | Via 1 El Berron, via 2 Oviedo |
| 05508 | Fonciello | 1, 2 | Via 1 Infiesto, via 2 Oviedo |
| 05509 | El Berron | 5, 7 | Nudo principal |
| 05513 | Pola de Siero | 3, 4 | Vias 1-2 deposito |
| 05515 | Los Corros | 1 | Via unica |
| 05517 | Lieres | 1, 3 | Patron FEVE |
| 05521 | El Remedio | 1 | Via unica |
| 05522 | Llames | 1 | Via unica |
| 05523 | Nava | 1, 2, 3 | Nudo importante |
| 05527 | Ceceda | 1 | Via unica |
| 05529 | Carancos | 1 | Via unica |
| 05531 | Pintueles | 1 | Via unica |
| 05533 | Infiesto | 1, 2 | Dos vias |

### C7: Oviedo - Trubia / San Esteban

| Codigo | Estacion | Vias | Notas |
|--------|----------|------|-------|
| 05300 | Vallobin | 1 | Via unica |
| 05301 | La Arganosa-Lavapies | 1 | Via unica |
| 05302 | Las Campas | 1 | Via unica |
| 05303 | Las Mazas | 1 | Via unica |
| 05304 | San Claudio | 1, 2 | Via 1 Trubia, via 2 Oviedo |
| 05306 | San Pedro de Nora | 1 | Via unica |
| 05308 | Soto Udrion | 2 | Via 2 unica |
| 05311 | Trubia | 1, 3 | Patron FEVE |
| 05313 | Sta. Maria de Grado | 1 | Via unica |
| 05315 | Vega de Anzo | 1 | Via unica |
| 05316 | Penaflor de Grado | 1 | Via unica |
| 05317 | Grado | 1, 3 | Patron FEVE |
| 05319 | Sandiche | 1 | Via unica |
| 05320 | Aces | 1 | Via unica |
| 05321 | San Roman | 1 | Via unica |
| 05323 | Beifar | 1 | Via unica |
| 05327 | San Ranon | 1 | Via unica |
| 05325 | Pravia | 1, 2 | Nudo C4/C7 |
| 05329 | San Esteban de Pravia | 1 | Terminal |

### C8: Ablaña - Collanzo

| Codigo | Estacion | Vias | Notas |
|--------|----------|------|-------|
| 15205 | Ablaña | 1 | Compartida C1/C8 |
| 15206 | La Pereda Riosa | 1 | Compartida C1/C8 |
| 05369 | Mieres Vasco | 4 | Intercambio con C1 |
| 05361 | Baiña | 1 | Via unica |
| 05371 | Caudalia | 1 | Via unica |
| 05373 | Figaredo | 1 | Via unica |
| 05375 | Ujo Taruelo | 1 | Via unica |
| 05376 | Santa Cruz | 1 | Via unica |
| 05377 | Caborana | 1 | Via unica |
| 05379 | Moreda de Aller | 1 | Via unica |
| 05380 | San Antonio | 1 | Via unica |
| 05381 | Oyanco | 1 | Via unica |
| 05382 | Corigos | 1 | Via unica |
| 05383 | Piñeres | 1 | Via unica |
| 05384 | Santa Ana-Soto | 1 | Via unica |
| 05385 | Cabañaquinta | 1 | Via unica |
| 05387 | Levinco | 1 | Via unica |
| 05389 | Collanzo | 1 | Terminal |

## Correspondencias FEVE / Iberico

Estaciones cercanas entre redes metrica (FEVE) e iberica que permiten transbordo a pie:

| Metrica (FEVE) | Iberica | Distancia | Tiempo |
|----------------|---------|-----------|--------|
| RENFE_5369 Mieres Vasco (C8) | RENFE_15203 Mieres Puente (C1) | 641m | ~8min |
| RENFE_5426 La Felguera Nuevo Langreo (C5) | RENFE_16008 La Felguera (C2) | 485m | ~6min |
| RENFE_5433 El Entrego La Oscura (C5) | RENFE_16011 El Entrego (C2) | 1216m | ~15min |
| RENFE_5431 Ciaño Escobio (C5) | RENFE_16010 Ciaño (C2) | 1071m | ~13min |

*Distancias calculadas con OSRM (OpenStreetMap).*

## Notas sobre URLs de ADIF

Las URLs de ADIF requieren formatos especificos:
- Tildes: `el-berrón`, `candás`, `avilés`, `noreña`
- Abreviaturas: `s.-esteban-de-pravia` (con punto)
- Sufijos: `la-felguera-langreo`

## Historial

- **2026-02-02**: Añadida linea C8 y correspondencias
  - Añadida linea C8 completa (18 estaciones)
  - Mieres Vasco usa via 4 (intercambio con C1)
  - Documentadas correspondencias FEVE/Iberico con distancias OSM
  - Corregido nombre "Ciañu" → "Ciaño Escobio" en BD
  - Corregido Aviles-CIM → Aviles en stop_route_sequence para C3
  - Total: 112 estaciones documentadas

- **2026-02-01**: Revision completa de TODAS las estaciones metricas
  - Revisadas 94 estaciones via web de ADIF
  - Identificados 4 patrones FEVE (vias 1,3)
  - Identificados patrones especiales no consecutivos
  - Añadidas estaciones compartidas: Veriña, La Corredoria, El Parador
  - Actualizado JSON con 94 estaciones
