# Asignación de Vías - PROXIMIDAD

Documentación de las vías asignadas a servicios PROXIMIDAD en cada estación.
Fuente: ADIF Salidas y Llegadas (https://www.adif.es/viajeros/estaciones)

Fecha: 2026-02-01

---

## CÓRDOBA

| Estación | Código ADIF | Vía | Destinos |
|----------|-------------|-----|----------|
| **Córdoba Central (Julio Anguita)** | 50500 | 5 | Campus Universitario de Rabanales |
| | | 6 | Palma del Río, Villa del Río, Alcolea de Córdoba |
| | | 6/8 | Villarrubia de Córdoba (variable según tren) |
| **Palma del Río** | 50506 | 3 | Todos los PROXIMIDAD |
| **Posadas** | 50504 | 3 | Todos los PROXIMIDAD |
| **Villa del Río** | 50407 | 2 | Todos |
| **Campus Universitario de Rabanales** | 50417 | 1 | Vía única |

| **Alcolea de Córdoba** | 50413 | 1 | Vía única (apeadero) |

| **Villarrubia de Córdoba** | 50502 | 1 | Córdoba (norte) |
| | | 2 | Sur / Sevilla |

| **El Higuerón** | 50501 | 1 | Vía única |

---

## CASTILLA Y LEÓN

### Línea Medina del Campo - Valladolid - Palencia

| Estación | Código ADIF | Vía | Destinos |
|----------|-------------|-----|----------|
| **Palencia** | 14100 | 1 | Valladolid, Medina del Campo (sur) |
| **Grijota** | 15001 | - | Sin servicios PROXIMIDAD directos |
| **Corcos-Aguilarejo** | 10603 | 1 | Palencia (norte) |
| | | 2 | Valladolid, Medina del Campo (sur) |
| **Cabezón de Pisuerga** | 10602 | 1 | Palencia (norte) |
| | | 2 | Valladolid, Medina del Campo (sur) |
| **Valladolid Campo Grande** | 10600 | 4 | Palencia (norte) |
| | | 5 | Medina del Campo, Salamanca (sur) |
| **Valladolid Universidad** | 10610 | 1 | Vía única |
| **Matapozuelos** | 10502 | 1 | Valladolid (norte) |
| | | 2 | Medina del Campo, Salamanca (sur) |
| **Viana** | 10504 | 1 | Valladolid (norte) |
| | | 4 | Salamanca (sur) |
| **Medina del Campo** | 10500 | 1 | Algunos hacia Valladolid |
| | | 3 | Salamanca |
| | | 5 | Mayoría hacia Valladolid/Palencia |

### Observaciones

- La línea PROXIMIDAD conecta Palencia - Valladolid - Medina del Campo
- Patrón general: Vía 1 hacia norte (Palencia), Vía 2 hacia sur (Medina)
- En Valladolid Campo Grande cambia: Vía 4 norte, Vía 5 sur
- Grijota no tiene servicios PROXIMIDAD directos (solo REGIONAL EXPRES)

---

## MÁLAGA

### Línea Málaga - El Chorro - Caminito del Rey

| Estación | Código ADIF | Vía | Destinos |
|----------|-------------|-----|----------|
| **Málaga María Zambrano** | 54413 | 10 | Álora, El Chorro (C2/PROXIMIDAD norte) |
| | | 11 | Málaga Centro-Alameda (C2) |
| **El Chorro-Caminito del Rey** | 54403 | 1 | Málaga María Zambrano (sur) |
| | | 2 | Álora, Sevilla (norte) |
| **Álora** | 54405 | 1 | Todos (C2 y PROXIMIDAD) |

### Observaciones

- La línea PROXIMIDAD está integrada con Cercanías C2
- Álora usa Vía 1 para todos los servicios (C2 y PROXIMIDAD hacia El Chorro/Málaga)
- El Chorro también tiene trenes RF-MD (Media Distancia) compartidos con PROXIMIDAD
- El servicio "Compartido: Proximidad" indica que MD y PROXIMIDAD usan el mismo tren

---

## MURCIA

### Línea Murcia - Cartagena

| Estación | Código ADIF | Vía | Destinos |
|----------|-------------|-----|----------|
| **Murcia del Carmen** | 61200 | 11 | Cartagena (PROXIMIDAD) |
| **Balsicas-Mar Menor** | 61303 | 1 | Murcia (norte) |
| | | 2 | Cartagena (sur) |
| **Cartagena** | 61307 | 2 | Murcia del Carmen |
| | | 3 | Murcia del Carmen (alternativa) |

### Observaciones

- Murcia del Carmen: URL correcta es `/w/61200-murcia-carmen` (sin "del")
- **Vía 11**: PROXIMIDAD hacia Cartagena (misma vía que Cercanías C1 a Alicante)
- Cartagena usa Vía 2 y 3 para PROXIMIDAD hacia Murcia

---

## MADRID / TOLEDO

### Línea Madrid Atocha - Fuenlabrada - Humanes - Illescas

| Estación | Código ADIF | Vía | Destinos |
|----------|-------------|-----|----------|
| **Madrid-Atocha Cercanías** | 18000 | - | Origen de todos los PROXIMIDAD (verificar vía específica) |
| **Leganés** | 35001 | 1 | Madrid Atocha Cercanías (norte) |
| | | 2 | Illescas, Fuenlabrada (sur) |
| **Fuenlabrada** | 35002 | 1 | Madrid Atocha Cercanías (norte) |
| | | 3/4 | Illescas (sur, variable según tren) |
| **Humanes** | 35012 | 1 | Fuenlabrada, Madrid Atocha (norte) |
| | | 2 | Illescas (sur) |
| **Illescas** | 35005 | 1 | Todos los PROXIMIDAD |

### Observaciones

- La línea PROXIMIDAD conecta: Madrid Atocha → Leganés → Fuenlabrada → Humanes → Illescas
- Fuenlabrada y Humanes también tienen **Cercanías C5** (línea separada hacia Móstoles El Soto)
- En Fuenlabrada, la vía hacia Illescas es variable (Vía 3 o 4 según tren)
- Servicio "Compartido: Proximidad" indica que REGIONAL y PROXIMIDAD usan el mismo tren
- **Base de datos**: Todos los stops verificados en producción (RENFE_18000, RENFE_35001, RENFE_35002, RENFE_35005, RENFE_35012)

---

## Leyenda

- **Vía única**: Estación/apeadero con una sola vía, no requiere asignación
- **Variable**: La vía puede cambiar según el tren/horario
