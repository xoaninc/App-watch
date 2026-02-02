# Estaciones Pendientes de Revisión - PROXIMIDAD

Listado de estaciones que requieren verificación adicional o presentan anomalías en la asignación de vías.

Fecha: 2026-02-01

---

## CÓRDOBA

### 1. Alcolea de Córdoba (50413) - ✅ VERIFICADA

**Resultado**: Vía 1 (apeadero de vía única)

**Verificación 2026-02-02**:
- Funciona como apeadero de vía única
- **Vía 1** para todos los servicios PROXIMIDAD

---

### 2. Córdoba Central → Villarrubia - Vía variable (6/8)

**Observación**: Desde Córdoba Central, los trenes a Villarrubia salen de Vía 6 o Vía 8 (variable según tren)

**Ejemplos**:
- Tren 13206 → Vía 8
- Tren 13208 → Vía 6

**Prioridad**: BAJA - Documentado, patrón variable pero funcional

---

### 3. Villarrubia de Córdoba (50502) - ✅ VERIFICADA

- **Vía 1**: Córdoba (norte)
- **Vía 2**: Sur / Sevilla
- Es cabecera de línea

### 4. El Higuerón (50501) - ✅ VERIFICADA

- **Vía 1**: Vía única

---

## CASTILLA Y LEÓN

### ✅ COMPLETADO

Todas las estaciones principales de la línea PROXIMIDAD Medina del Campo - Valladolid - Palencia han sido verificadas:

| Estación | Código | Estado |
|----------|--------|--------|
| Palencia | 14100 | ✅ Verificada |
| Corcos-Aguilarejo | 10603 | ✅ Verificada |
| Cabezón de Pisuerga | 10602 | ✅ Verificada |
| Valladolid Campo Grande | 10600 | ✅ Verificada |
| Valladolid Universidad | 10610 | ✅ Verificada |
| Matapozuelos | 10502 | ✅ Verificada |
| Viana | 10504 | ✅ Verificada |
| Medina del Campo | 10500 | ✅ Verificada |

### Observación: Medina del Campo - Vías múltiples

**Situación**: Usa varias vías (1, 3, 5) para PROXIMIDAD

- Vía 1: Algunos trenes hacia Valladolid
- Vía 3: Hacia Salamanca
- Vía 5: Mayoría hacia Valladolid/Palencia

**Prioridad**: BAJA - documentado, patrón complejo pero funcional

### Estación sin servicio PROXIMIDAD

| Estación | Código | Notas |
|----------|--------|-------|
| Grijota | 15001 | Solo REGIONAL EXPRES, no tiene PROXIMIDAD |

---

## MURCIA

### 1. Murcia del Carmen (61200) - ✅ VERIFICADA

**Resultado**: Vía 11 para PROXIMIDAD hacia Cartagena

**Verificación 2026-02-02**:
- URL correcta: `/w/61200-murcia-carmen` (sin "del")
- PROXIMIDAD 14510 → Cartagena - **Vía 11**
- Misma vía que Cercanías C1 hacia Alicante

---

### 2. Estaciones intermedias Murcia-Cartagena

| Estación | Código | Estado | Prioridad |
|----------|--------|--------|-----------|
| Murcia del Carmen | 61200 | ✅ Verificada (Vía 11) | - |
| Balsicas-Mar Menor | 61303 | ✅ Verificada (Vía 1/2) | - |
| Cartagena | 61307 | ✅ Verificada (Vía 2/3) | - |

**Nota**: Faltan estaciones intermedias por documentar (Alcantarilla, etc.)

---

---

## MÁLAGA

### ✅ COMPLETADO

| Estación | Código | Estado |
|----------|--------|--------|
| Málaga María Zambrano | 54413 | ✅ Verificada (Vía 10/11) |
| El Chorro-Caminito del Rey | 54403 | ✅ Verificada (Vía 1/2) |
| Álora | 54405 | ✅ Verificada (Vía 1) |

**Verificación 2026-02-02**: Álora usa Vía 1 para todos los servicios (C2 Cercanías y PROXIMIDAD)

---

## MADRID / TOLEDO

### ✅ COMPLETADO

Estaciones principales verificadas y documentadas:

| Estación | Código | Estado | Base de datos |
|----------|--------|--------|---------------|
| Madrid-Atocha Cercanías | 18000 | ⏳ Vía pendiente | ✅ RENFE_18000 |
| Leganés | 35001 | ✅ Verificada (Vía 1/2) | ✅ RENFE_35001 |
| Fuenlabrada | 35002 | ✅ Verificada (Vía 1/3/4) | ✅ RENFE_35002 |
| Humanes | 35012 | ✅ Verificada (Vía 1/2) | ✅ RENFE_35012 |
| Illescas | 35005 | ✅ Verificada (Vía 1) | ✅ RENFE_35005 |

### 1. Madrid-Atocha Cercanías (18000) - PRIORIDAD BAJA

**Problema**: Vía PROXIMIDAD no verificada

**Situación**:
- Origen de todos los PROXIMIDAD hacia Illescas
- Estación muy grande con múltiples vías
- No se ha determinado qué vía específica usan los PROXIMIDAD

**Acción**: Verificar en ADIF bajo filtro "AV / Media distancia"

---

## Leyenda de Prioridades

- **ALTA**: Anomalía que puede afectar a la funcionalidad de la app
- **MEDIA**: Inconsistencia que debería resolverse pero no bloquea
- **BAJA**: Información faltante esperada/normal, solo documentación
