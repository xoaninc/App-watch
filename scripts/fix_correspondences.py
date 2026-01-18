#!/usr/bin/env python3
"""Fix Madrid correspondences based on correct data."""

import sys
sys.path.insert(0, '/var/www/renfeserver')

from core.database import get_db
from sqlalchemy import text

db = next(get_db())

# Primero limpiar TODAS las correspondencias de Madrid (nucleo_id = 10)
print("Limpiando todas las correspondencias de Madrid...")
db.execute(text("""
    UPDATE gtfs_stops
    SET cor_metro = NULL, cor_cercanias = NULL, cor_ml = NULL, cor_tranvia = NULL
    WHERE nucleo_id = 10
"""))
db.commit()
print("Limpiadas todas las correspondencias")

# CERCANÍAS - correspondencias con Metro y ML
cercanias_correspondencias = [
    ("Aeropuerto T4", "L8", None, None),
    ("Alcorcón", "L12", None, None),
    ("Aluche", "L5", None, None),
    ("Aravaca", None, "ML2", None),
    ("Atocha", "L1", None, None),
    ("Chamartín", "L1,L10", None, None),
    ("Cuatro Vientos", "L10", None, None),
    ("Delicias", "L3", None, None),
    ("El Casar", "L3,L12", None, None),
    ("Embajadores", "L3,L5", None, None),
    ("Fuenlabrada", "L12", None, None),
    ("Fuente de la Mora", None, "ML1", None),
    ("Getafe-Centro", "L12", None, None),
    ("Laguna", "L6", None, None),
    ("Leganés", "L12", None, None),
    ("Méndez Álvaro", "L6", None, None),
    ("Mirasierra", "L9", None, None),
    ("Móstoles", "L12", None, None),
    ("Nuevos Ministerios", "L6,L8,L10", None, None),
    ("Parla", None, None, "Tranvía Parla"),
    ("Pirámides", "L5", None, None),
    ("Pitis", "L7", None, None),
    ("Príncipe Pío", "L6,L10,R", None, None),
    ("Sol", "L1,L2,L3", None, None),
    ("Vallecas", "L1", None, None),
    ("Vicálvaro", "L9", None, None),
    ("Villaverde Alto", "L3", None, None),
    ("Villaverde Bajo", "L3", None, None),
    ("San Cristóbal de los Ángeles", "L3", None, None),
    ("San Cristóbal Industrial", "L3", None, None),
    ("Pozuelo", None, "ML2", None),
]

print("\nActualizando correspondencias de Cercanías...")
for nombre, cor_metro, cor_ml, cor_tranvia in cercanias_correspondencias:
    result = db.execute(text("""
        UPDATE gtfs_stops
        SET cor_metro = :cm, cor_ml = :cml, cor_tranvia = :ct
        WHERE nucleo_id = 10
        AND id LIKE 'RENFE_%'
        AND name ILIKE :nombre
    """), {
        'cm': cor_metro,
        'cml': cor_ml,
        'ct': cor_tranvia,
        'nombre': f'%{nombre}%'
    })
    if result.rowcount > 0:
        print(f"  + {nombre}: Metro={cor_metro}, ML={cor_ml}, Tranvia={cor_tranvia}")
    else:
        print(f"  - {nombre}: No encontrado")

db.commit()

# METRO - correspondencias con Cercanías
# Solo las estaciones de Metro que tienen correspondencia REAL con Cercanías
metro_correspondencias = [
    ("METRO_285", "C1,C10"),  # Aeropuerto T-4
    ("METRO_211", "C5"),      # Alcorcón Central
    ("METRO_100", "C5"),      # Aluche
    ("METRO_16", "C1,C2,C3,C4,C5,C7,C8,C10"),  # Atocha
    ("METRO_189", "C1,C2,C3,C4,C7,C8,C10"),    # Chamartín
    ("METRO_288", "C2,C7,C8"),  # Coslada Central (L7B)
    ("METRO_203", "C5"),      # Cuatro Vientos
    ("METRO_44", "C1,C10"),   # Delicias
    ("METRO_228", "C3"),      # El Casar
    ("METRO_46", "C5"),       # Embajadores
    ("METRO_187", "C4"),      # Fuencarral
    ("METRO_221", "C5"),      # Fuenlabrada Central
    ("METRO_226", "C4"),      # Getafe Central
    ("METRO_219", "C5"),      # Hospital De Fuenlabrada
    ("METRO_216", "C5"),      # Hospital De Móstoles
    ("METRO_104", "C5"),      # Laguna
    ("METRO_235", "C5"),      # Leganés Central
    ("METRO_111", "C1,C5,C7,C10"),  # Méndez Álvaro
    ("METRO_326", "C3a,C7,C8"),     # Mirasierra
    ("METRO_214", "C5"),      # Móstoles Central
    ("METRO_120", "C1,C2,C3,C4,C7,C8,C10"),  # Nuevos Ministerios
    ("METRO_345", "C3a,C7,C8"),     # Paco De Lucía
    ("METRO_93", "C1,C10"),   # Pirámides
    ("METRO_154", "C3a,C7,C8"),     # Pitis
    ("METRO_127", "C1,C7,C10"),     # Príncipe Pío
    ("METRO_12", "C3,C4"),    # Sol
    ("METRO_25", "C2,C7,C8"), # Sierra De Guadalupe (cerca de Vallecas Cercanías)
    ("METRO_180", "C2,C7,C8"),# Vicálvaro
    ("METRO_273", "C4,C5"),   # Villaverde Alto
    ("METRO_271", "C3,C4"),   # Villaverde Bajo Cruce
    ("METRO_272", "C3"),      # San Cristóbal
]

print("\nActualizando correspondencias de Metro...")
for stop_id, cor_cercanias in metro_correspondencias:
    result = db.execute(text("""
        UPDATE gtfs_stops
        SET cor_cercanias = :cc
        WHERE id = :sid
    """), {
        'cc': cor_cercanias,
        'sid': stop_id
    })
    if result.rowcount > 0:
        print(f"  + {stop_id}: Cercanías={cor_cercanias}")
    else:
        print(f"  - {stop_id}: No encontrado")

db.commit()

# ML - correspondencias con Cercanías
ml_correspondencias = [
    ("ML_2", "C1,C10"),   # Fuente De La Mora
    ("ML_23", "C1,C7,C10"),  # Estación De Aravaca
    ("ML_16", "C1,C7,C10"),  # Pozuelo Oeste
]

print("\nActualizando correspondencias de ML...")
for stop_id, cor_cercanias in ml_correspondencias:
    result = db.execute(text("""
        UPDATE gtfs_stops
        SET cor_cercanias = :cc
        WHERE id = :sid
    """), {
        'cc': cor_cercanias,
        'sid': stop_id
    })
    if result.rowcount > 0:
        print(f"  + {stop_id}: Cercanías={cor_cercanias}")
    else:
        print(f"  - {stop_id}: No encontrado")

db.commit()

# Correspondencias internas de Metro (L7/L7B, L9/L9B, L10/L10B)
print("\nActualizando correspondencias internas de Metro...")
metro_interno = [
    ("METRO_286", "L7,L7B"),   # Estadio Metropolitano
    ("METRO_182", "L9,L9B"),   # Puerta De Arganda
    ("METRO_274", "L10,L10B"), # Tres Olivos
]

for stop_id, cor_metro in metro_interno:
    result = db.execute(text("""
        UPDATE gtfs_stops
        SET cor_metro = :cm
        WHERE id = :sid
    """), {
        'cm': cor_metro,
        'sid': stop_id
    })
    if result.rowcount > 0:
        print(f"  + {stop_id}: Metro={cor_metro}")

db.commit()

print("\n=== COMPLETADO ===")
