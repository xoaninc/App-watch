# Mapeo Provincia → Núcleo

Este documento describe la relación entre provincias españolas y núcleos Renfe (redes regionales).

## Núcleos y sus Provincias

### Núcleo 10: Madrid
- **Provincias**: Madrid

### Núcleo 20: Asturias
- **Provincias**: Asturias

### Núcleo 30: Sevilla
- **Provincias**: Sevilla

### Núcleo 31: Cádiz
- **Provincias**: Cádiz

### Núcleo 32: Málaga
- **Provincias**: Málaga

### Núcleo 40: Valencia
- **Provincias**: Valencia

### Núcleo 41: Murcia/Alicante ⚠️
- **Provincias**:
  - Murcia
  - Alicante
- **Nota**: Este núcleo cubre 2 provincias de la región de Murcia y la comunidad autónoma de Valencia

### Núcleo 50: Rodalies de Catalunya ⚠️
- **Provincias**:
  - Barcelona
  - Tarragona
  - Lleida
  - Girona
- **Nota**: Este núcleo cubre las 4 provincias de Cataluña

### Núcleo 60: Bilbao
- **Provincias**: Vizcaya (Bizkaia)

### Núcleo 61: San Sebastián
- **Provincias**: Guipúzcoa (Gipuzkoa)

### Núcleo 62: Cantabria
- **Provincias**: Cantabria

### Núcleo 70: Zaragoza
- **Provincias**: Zaragoza

## Provincias sin Servicio Renfe (Sin Núcleo)

Las siguientes provincias no tienen servicio de Renfe y sus paradas/rutas no corresponden a ningún núcleo:

- Almería
- Ávila
- Badajoz
- Baleares
- Burgos
- Córdoba
- Cuenca
- Ciudad Real
- Guadalajara
- Huesca
- Jaén
- La Rioja
- Las Palmas
- León
- Lugo
- Navarra
- Ourense
- Palencia
- Pontevedra
- Salamanca
- Segovia
- Soria
- Teruel
- Toledo
- Valladolid
- Zamora
- Ceuta
- Melilla
- Tenerife (y otras islas)

## Estadísticas

- **Total Provincias Españolas**: 52 (incluyendo ciudades autónomas)
- **Provincias Mapeadas**: 14
- **Provincias con Renfe**: 14
- **Provincias sin Renfe**: 38
- **Núcleos**: 12

## Casos Especiales

### Murcia/Alicante (Núcleo 41)
Este núcleo es especial porque:
- Cubre 2 provincias distintas
- Murcia es una comunidad autónoma uniprovincial
- Alicante es provincia de la comunidad de Valencia
- Ambas se sirven desde el mismo núcleo Renfe

### Rodalies de Catalunya (Núcleo 50)
Este núcleo es especial porque:
- Cubre 4 provincias (todas de Cataluña)
- Barcelona: principal punto de conexión
- Tarragona, Lleida, Girona: ciudades secundarias
- Es el núcleo más completo con más estaciones (202) y líneas (19)

## Uso en la Base de Datos

Después de ejecutar la migración y el script de población:

```sql
-- Ver mapeo para una provincia específica
SELECT name, nucleo_id, nucleo_name FROM spanish_provinces WHERE name = 'Madrid';

-- Ver todas las provincias agrupadas por núcleo
SELECT nucleo_name, GROUP_CONCAT(name) as provinces
FROM spanish_provinces
WHERE nucleo_id IS NOT NULL
GROUP BY nucleo_name;

-- Ver provincias sin núcleo
SELECT name FROM spanish_provinces WHERE nucleo_id IS NULL;
```

## API Usage

### Obtener provincia y núcleo por coordenadas

```python
from src.gtfs_bc.province.province_lookup import get_province_and_nucleo_by_coordinates

# Coordenadas de Madrid
province, nucleo = get_province_and_nucleo_by_coordinates(db, 40.4168, -3.7038)
# Retorna: ('Madrid', 'Madrid')

# Coordenadas de Barcelona
province, nucleo = get_province_and_nucleo_by_coordinates(db, 41.3874, 2.1686)
# Retorna: ('Barcelona', 'Rodalies de Catalunya')

# Coordenadas de Murcia
province, nucleo = get_province_and_nucleo_by_coordinates(db, 37.9922, -1.1307)
# Retorna: ('Murcia', 'Murcia/Alicante')
```

## Referencias

- [Provincias españolas en Wikipedia](https://es.wikipedia.org/wiki/Provincias_de_Espa%C3%B1a)
- [Comunidades autónomas de España](https://es.wikipedia.org/wiki/Comunidades_aut%C3%B3nomas_de_Espa%C3%B1a)
- [Renfe Rodalies](https://www.renfe.com)
