# Deployment: Núcleo System Migration

Esta guía describe los pasos para desplegar el sistema de núcleos en desarrollo y producción.

## Requisitos Previos

- PostgreSQL 16+ con PostGIS 3 instalado
- Python 3.10+
- Alembic para migraciones
- Virtualenv activado

## Fase 1: Development (Ambiente Local)

### Paso 1: Ejecutar Migraciones

```bash
cd /Users/juanmacias/Projects/renfeserver

# Verificar el estado actual
alembic current

# Ejecutar todas las migraciones pendientes (008, 009, 010, 011)
alembic upgrade head

# Verificar que se ejecutaron correctamente
alembic current
```

**Migraciones que se ejecutarán**:
- `008_create_nucleos_table.py` - Crea tabla `gtfs_nucleos` (12 redes regionales)
- `009_add_nucleo_to_stops.py` - Añade campos de núcleo a `gtfs_stops`
- `010_add_nucleo_to_routes.py` - Añade campos de núcleo a `gtfs_routes`
- `011_add_nucleo_to_provinces.py` - Añade mapeo núcleo a `spanish_provinces`

### Paso 2: Importar Datos de Renfe

```bash
# Descargar y importar datos de Renfe (estaciones y líneas)
python scripts/import_renfe_nucleos.py

# Output esperado:
# ✓ 12 nucleos created/updated
# ✓ 791 stations imported
# ✓ 69 lines imported
```

### Paso 3: Popular Stops con Datos Núcleo

```bash
# Actualizar stops existentes con información de núcleo
python scripts/populate_stops_nucleos.py

# Output esperado:
# Total stops processed: 1092
# Updated: ~1000+ (depende de matching)
# Unchanged: ~50
# Not found: ~30
```

### Paso 4: Popular Routes con Datos Núcleo

```bash
# Actualizar routes con información de núcleo
python scripts/populate_routes_nucleos.py

# Output esperado:
# Total routes processed: ~75
# Updated: ~70
# Not found: ~5
```

### Paso 5: Popular Mapeo Provincia-Núcleo

```bash
# Mapear provincias españolas a núcleos
python scripts/populate_province_nucleo_mapping.py

# Output esperado:
# Total provinces: 52
# Mapped: 14 (provincias con servicio Renfe)
# Not mapped: 38 (provincias sin servicio Renfe)
```

### Paso 6: Validación Completa

```bash
# Validar sistema de núcleos
python scripts/validate_nucleos.py

# Validar mapeo provincia-núcleo
python scripts/validate_province_nucleo_mapping.py

# Validar sistema de provincias (existente)
python scripts/validate_provinces.py
```

**Verifica que todos los checks pasen con ✓ PASS**

### Paso 7: Pruebas API

```bash
# Iniciar servidor
uvicorn main:app --reload --port 8000

# En otra terminal, probar endpoints

# Listar todos los núcleos
curl "http://localhost:8000/api/v1/gtfs/nucleos" | jq

# Obtener detalle de un núcleo (Madrid = id 10)
curl "http://localhost:8000/api/v1/gtfs/nucleos/10" | jq

# Obtener stops de Madrid
curl "http://localhost:8000/api/v1/gtfs/stops?nucleo_id=10&limit=10" | jq

# Obtener stops por coordenadas (Madrid)
curl "http://localhost:8000/api/v1/gtfs/stops/by-coordinates?lat=40.42&lon=-3.72&limit=10" | jq

# Obtener routes de Cataluña (Rodalies de Catalunya = id 50)
curl "http://localhost:8000/api/v1/gtfs/routes?nucleo_id=50" | jq
```

## Fase 2: Production (juanmacias.com:8002)

### Paso 0: Backup

```bash
# Conectar a servidor de producción
ssh user@juanmacias.com

# Backup de base de datos
BACKUP_FILE="/var/www/renfeserver/backups/db_$(date +%Y%m%d_%H%M%S).sql"
mkdir -p /var/www/renfeserver/backups
sudo -u postgres pg_dump renfeserver_prod > "$BACKUP_FILE"
echo "Backup created: $BACKUP_FILE"
```

### Paso 1: Deploy de Código

```bash
# En desarrollo, commit y push
cd /Users/juanmacias/Projects/renfeserver
git add -A
git commit -m "Implement Renfe nucleo system with province mapping"
git push origin main

# En producción, pull de cambios
ssh user@juanmacias.com
cd /var/www/renfeserver
git pull origin main
```

### Paso 2: Activar Virtualenv y Ejecutar Migraciones

```bash
# Activar virtualenv
source /var/www/renfeserver/.venv/bin/activate

# Ejecutar migraciones
cd /var/www/renfeserver
alembic upgrade head
```

### Paso 3: Importar Datos

```bash
# Importar nucleos desde Renfe
python scripts/import_renfe_nucleos.py

# Popular stops
python scripts/populate_stops_nucleos.py

# Popular routes
python scripts/populate_routes_nucleos.py

# Popular mapeo provincia-núcleo
python scripts/populate_province_nucleo_mapping.py
```

### Paso 4: Validaciones

```bash
# Ejecutar todas las validaciones
python scripts/validate_nucleos.py
python scripts/validate_province_nucleo_mapping.py
python scripts/validate_provinces.py

# Si todos los checks pasan:
echo "✓ All validations passed"
```

### Paso 5: Restart Service

```bash
# Reiniciar servicio FastAPI (gunicorn o systemd)
sudo systemctl restart renfe-api

# Verificar que el servicio está funcionando
sudo systemctl status renfe-api

# Ver logs
sudo journalctl -u renfe-api -f
```

### Paso 6: Verify in Production

```bash
# Probar endpoints en producción
curl "https://juanmacias.com:8002/api/v1/gtfs/nucleos" | jq '.[] | {id, name, stations_count, lines_count}'

# Verificar que los datos están correctos
curl "https://juanmacias.com:8002/api/v1/gtfs/nucleos/50" | jq '.name'
# Debería retornar: "Rodalies de Catalunya"
```

## Rollback (Si hay Problemas)

Si algo falla en producción, puedes hacer rollback:

```bash
# Revertir migraciones
cd /var/www/renfeserver
alembic downgrade 007

# Esto revierte:
# - 011_add_nucleo_to_provinces.py
# - 010_add_nucleo_to_routes.py
# - 009_add_nucleo_to_stops.py
# - 008_create_nucleos_table.py

# Restaurar backup de base de datos si es necesario
sudo -u postgres psql renfeserver_prod < /var/www/renfeserver/backups/db_YYYYMMDD_HHMMSS.sql

# Reiniciar servicio
sudo systemctl restart renfe-api
```

## Monitoreo Post-Deployment

Después del deployment, monitorear:

### 1. Logs de Aplicación

```bash
# En producción
sudo journalctl -u renfe-api -f --grep="ERROR"
```

### 2. Performance de Queries

```bash
# Conectar a base de datos
psql renfeserver_prod

-- Verificar índices
SELECT * FROM pg_indexes WHERE tablename LIKE 'gtfs_%' OR tablename = 'spanish_provinces';

-- Ver tamaño de tablas
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE tablename IN ('gtfs_nucleos', 'gtfs_stops', 'gtfs_routes', 'spanish_provinces')
ORDER BY pg_total_relation_size DESC;
```

### 3. Coverage Queries

```bash
-- Verificar cobertura de stops por núcleo
SELECT nucleo_name, COUNT(*) as stops
FROM gtfs_stops
WHERE nucleo_id IS NOT NULL
GROUP BY nucleo_name
ORDER BY stops DESC;

-- Verificar cobertura de routes por núcleo
SELECT nucleo_name, COUNT(*) as routes
FROM gtfs_routes
WHERE nucleo_id IS NOT NULL
GROUP BY nucleo_name
ORDER BY routes DESC;

-- Verificar cobertura de provincias
SELECT nucleo_name, COUNT(*) as provinces
FROM spanish_provinces
WHERE nucleo_id IS NOT NULL
GROUP BY nucleo_name
ORDER BY provinces DESC;
```

## Operaciones Posteriores

### Re-Popular Datos (Si cambian en Renfe)

```bash
# Con --force, re-importa todos los datos (sobrescribe existentes)
python scripts/import_renfe_nucleos.py
python scripts/populate_stops_nucleos.py --force
python scripts/populate_routes_nucleos.py --force
python scripts/populate_province_nucleo_mapping.py
```

### Sincronizar con Nuevas Provincias

Si se agregan nuevas provincias o núcleos:

```bash
# 1. Actualizar PROVINCE_NUCLEO_MAPPING en populate_province_nucleo_mapping.py
# 2. Ejecutar script
python scripts/populate_province_nucleo_mapping.py
# 3. Validar
python scripts/validate_province_nucleo_mapping.py
```

## Estadísticas Esperadas

Después del deployment completo, esperamos:

**Nucleos**: 12
- Madrid (id 10): ~95 stops, 13 routes
- Asturias (id 20): ~149 stops, 9 routes
- Sevilla (id 30): ~33 stops, 5 routes
- Cádiz (id 31): ~30 stops, 3 routes
- Málaga (id 32): ~23 stops, 2 routes
- Valencia (id 40): ~72 stops, 6 routes
- Murcia/Alicante (id 41): ~26 stops, 3 routes
- Rodalies de Catalunya (id 50): ~202 stops, 19 routes
- Bilbao (id 60): ~64 stops, 4 routes
- San Sebastián (id 61): ~30 stops, 1 route
- Cantabria (id 62): ~61 stops, 3 routes
- Zaragoza (id 70): ~6 stops, 1 route

**Total**: 791 stops, 69 routes en núcleos

**Provincias**:
- 14 provincias con servicio Renfe (mapeadas)
- 38 provincias sin servicio (sin mapeo)

## Troubleshooting

### Error: "PostGIS extension not available"
```bash
# En servidor, instalar PostGIS
sudo apt-get install -y postgresql-16-postgis-3

# Crear extensión como superuser
sudo -u postgres psql -d renfeserver_prod -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### Error: "No province found for coordinates"
- Verificar que `spanish_provinces` table tiene geometrías válidas
- Ejecutar: `python scripts/validate_provinces.py`
- Ejecutar: `python scripts/import_province_boundaries.py` si es necesario

### Error: "Foreign key constraint violated"
- Verificar que todas las migraciones completaron
- Verificar que `gtfs_nucleos` tabla existe con datos
- Ejecutar: `python scripts/import_renfe_nucleos.py`

### Slow queries
- Verificar que todos los índices se crearon
- Ejecutar ANALYZE en PostgreSQL
- Aumentar max_connections si es necesario

## Documentación Relacionada

- [PROVINCE_NUCLEO_MAPPING.md](./PROVINCE_NUCLEO_MAPPING.md) - Mapeo detallado
- [src/gtfs_bc/province/province_lookup.py](./src/gtfs_bc/province/province_lookup.py) - Funciones de búsqueda
- [adapters/http/api/gtfs/routers/query_router.py](./adapters/http/api/gtfs/routers/query_router.py) - API endpoints
