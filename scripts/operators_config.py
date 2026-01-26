#!/usr/bin/env python3
"""Configuration for all transit operators to import.

Each operator has:
- Basic metadata (name, city, region, etc.)
- GTFS source configuration (URL, auth method)
- GTFS-RT configuration if available
- Route type and colors

Usage:
    from scripts.operators_config import OPERATORS, get_operator

    # Get all operators
    for op in OPERATORS.values():
        print(op.name)

    # Get specific operator
    tmb = get_operator('tmb_metro')
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum


class AuthMethod(Enum):
    """Authentication method for GTFS/API access."""
    NONE = "none"           # Direct download, no auth needed
    API_KEY = "api_key"     # Requires API key in URL params
    SESSION = "session"     # Requires browser session/cookie
    MANUAL = "manual"       # Must be downloaded manually (NAP, etc.)


class GTFSRTFormat(Enum):
    """Format of GTFS-RT feed."""
    PROTOBUF = "protobuf"   # Standard GTFS-RT protobuf format
    JSON = "json"           # JSON format (Renfe, FGC)
    CUSTOM_API = "custom"   # Custom API (TMB iMetro)


@dataclass
class GTFSRTConfig:
    """Configuration for GTFS-RT realtime feeds."""
    format: GTFSRTFormat
    vehicle_positions_url: Optional[str] = None
    trip_updates_url: Optional[str] = None
    alerts_url: Optional[str] = None
    # For custom APIs
    custom_endpoint: Optional[str] = None


@dataclass
class OperatorConfig:
    """Configuration for a transit operator."""
    # Identifier
    code: str                    # Unique code (e.g., "tmb_metro", "metro_bilbao")

    # Basic info
    name: str                    # Display name
    city: str                    # Main city
    region: str                  # Region/community
    country: str = "ES"          # Country code

    # Visual
    color: str = "333333"        # Primary color (hex without #)
    text_color: str = "FFFFFF"   # Text color for contrast
    logo_url: Optional[str] = None
    wikipedia_url: Optional[str] = None

    # GTFS source
    gtfs_url: Optional[str] = None
    auth_method: AuthMethod = AuthMethod.NONE
    api_id: Optional[str] = None
    api_key: Optional[str] = None

    # Route info
    route_type: int = 1          # 0=Tram, 1=Metro, 2=Rail, 3=Bus
    agency_id: Optional[str] = None
    agency_name: Optional[str] = None
    agency_url: Optional[str] = None

    # Nucleo assignment (for grouping in the app)
    nucleo_id: Optional[int] = None

    # GTFS-RT configuration
    gtfs_rt: Optional[GTFSRTConfig] = None

    # Additional metadata
    notes: Optional[str] = None


# =============================================================================
# OPERATOR CONFIGURATIONS
# =============================================================================

OPERATORS: Dict[str, OperatorConfig] = {}

# -----------------------------------------------------------------------------
# 1. METRO DE MÁLAGA
# -----------------------------------------------------------------------------
OPERATORS['metro_malaga'] = OperatorConfig(
    code='metro_malaga',
    name='Metro de Málaga',
    city='Málaga',
    region='Andalucía',
    color='E30613',
    gtfs_url=None,  # URL outdated, needs manual download
    auth_method=AuthMethod.MANUAL,
    notes='Download from NAP: https://nap.transportes.gob.es/Files/Detail/1296 (requires login)',
    route_type=1,
    agency_id='METRO_MALAGA',
    agency_name='Metro de Málaga',
    agency_url='https://www.metromalaga.es',
    nucleo_id=32,  # Málaga Cercanías nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Metro_de_M%C3%A1laga',
)

# -----------------------------------------------------------------------------
# 2. METRO BILBAO
# -----------------------------------------------------------------------------
OPERATORS['metro_bilbao'] = OperatorConfig(
    code='metro_bilbao',
    name='Metro Bilbao',
    city='Bilbao',
    region='País Vasco',
    color='E30613',
    gtfs_url='https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfs_metro_bilbao.zip',
    auth_method=AuthMethod.NONE,
    route_type=1,
    agency_id='METRO_BILBAO',
    agency_name='Metro Bilbao',
    agency_url='https://www.metrobilbao.eus',
    nucleo_id=31,  # Bilbao nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Metro_de_Bilbao',
    gtfs_rt=GTFSRTConfig(
        format=GTFSRTFormat.PROTOBUF,
        vehicle_positions_url='https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfsrt_metro_bilbao_vehicle_positions.pb',
        trip_updates_url='https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfsrt_metro_bilbao_trip_updates.pb',
        alerts_url='https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfsrt_metro_bilbao_alerts.pb',
    ),
)

# Note: Metro Málaga URL is outdated - needs verification
# Original: https://datosabiertos.malaga.eu/recursos/transporte/EMT/gtfs/google_transit.zip

# -----------------------------------------------------------------------------
# 3. METRO DE VALENCIA (Metrovalencia / FGV)
# -----------------------------------------------------------------------------
OPERATORS['metro_valencia'] = OperatorConfig(
    code='metro_valencia',
    name='Metrovalencia',
    city='Valencia',
    region='Comunidad Valenciana',
    color='E30613',
    gtfs_url=None,  # Must download from NAP
    auth_method=AuthMethod.MANUAL,
    route_type=1,
    agency_id='METROVALENCIA',
    agency_name='Ferrocarrils de la Generalitat Valenciana',
    agency_url='https://www.metrovalencia.es',
    nucleo_id=60,  # Valencia nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Metrovalencia',
    notes='GTFS from NAP. Real-time: Valencia OpenData API',
    gtfs_rt=GTFSRTConfig(
        format=GTFSRTFormat.CUSTOM_API,
        custom_endpoint='https://geoportal.valencia.es/geoportal-services/api/v1/salidas-metro.json',
    ),
)

# -----------------------------------------------------------------------------
# 4. METRO DE GRANADA
# -----------------------------------------------------------------------------
OPERATORS['metro_granada'] = OperatorConfig(
    code='metro_granada',
    name='Metro de Granada',
    city='Granada',
    region='Andalucía',
    color='E30613',
    gtfs_url=None,  # Must download from NAP
    auth_method=AuthMethod.MANUAL,
    route_type=1,
    agency_id='METRO_GRANADA',
    agency_name='Metro de Granada',
    agency_url='https://www.metropolitanogranada.es',
    nucleo_id=33,  # Granada nucleo (created for metro)
    wikipedia_url='https://es.wikipedia.org/wiki/Metro_de_Granada',
    notes='Download from NAP: https://nap.transportes.gob.es/Files/Detail/1370 (requires login)',
)

# -----------------------------------------------------------------------------
# 5. METRO BARCELONA (TMB)
# -----------------------------------------------------------------------------
OPERATORS['tmb_metro'] = OperatorConfig(
    code='tmb_metro',
    name='Metro de Barcelona',
    city='Barcelona',
    region='Cataluña',
    color='E30613',
    gtfs_url='https://api.tmb.cat/v1/static/datasets/gtfs.zip',
    auth_method=AuthMethod.API_KEY,  # Requires app_id and app_key
    api_id='e76ae269',
    api_key='291c7f8027c5e684e010e6a54e76428c',
    route_type=1,
    agency_id='TMB_METRO',
    agency_name='Transports Metropolitans de Barcelona',
    agency_url='https://www.tmb.cat',
    nucleo_id=50,  # Barcelona nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Metro_de_Barcelona',
    gtfs_rt=GTFSRTConfig(
        format=GTFSRTFormat.CUSTOM_API,
        custom_endpoint='https://api.tmb.cat/v1/imetro/estacions',
    ),
)

# -----------------------------------------------------------------------------
# 6. FGC (Ferrocarrils de la Generalitat de Catalunya)
# -----------------------------------------------------------------------------
OPERATORS['fgc'] = OperatorConfig(
    code='fgc',
    name='Ferrocarrils de la Generalitat de Catalunya',
    city='Barcelona',
    region='Cataluña',
    color='F26522',
    gtfs_url='https://www.fgc.cat/google/google_transit.zip',
    auth_method=AuthMethod.NONE,
    route_type=2,  # Suburban rail
    agency_id='FGC',
    agency_name='FGC',
    agency_url='https://www.fgc.cat',
    nucleo_id=50,  # Barcelona nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Ferrocarriles_de_la_Generalitat_de_Catalu%C3%B1a',
    gtfs_rt=GTFSRTConfig(
        format=GTFSRTFormat.PROTOBUF,
        vehicle_positions_url='https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/vehicle-positions-gtfs_realtime/files/d286964db2d107ecdb1344bf02f7b27b',
        trip_updates_url='https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/trip-updates-gtfs_realtime/files/735985017f62fd33b2fe46e31ce53829',
        alerts_url='https://dadesobertes.fgc.cat/api/explore/v2.1/catalog/datasets/alerts-gtfs_realtime/files/02f92ddc6d2712788903e54468542936',
    ),
)

# -----------------------------------------------------------------------------
# 7. EUSKOTREN
# -----------------------------------------------------------------------------
OPERATORS['euskotren'] = OperatorConfig(
    code='euskotren',
    name='Euskotren',
    city='Bilbao',
    region='País Vasco',
    color='009640',
    gtfs_url='https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfs_euskotren.zip',
    auth_method=AuthMethod.NONE,
    route_type=2,  # Suburban rail
    agency_id='EUSKOTREN',
    agency_name='Euskotren',
    agency_url='https://www.euskotren.eus',
    nucleo_id=31,  # Bilbao nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Euskotren',
    gtfs_rt=GTFSRTConfig(
        format=GTFSRTFormat.PROTOBUF,
        vehicle_positions_url='https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfsrt_euskotren_vehicle_positions.pb',
        trip_updates_url='https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfsrt_euskotren_trip_updates.pb',
        alerts_url='https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfsrt_euskotren_alerts.pb',
    ),
)

# -----------------------------------------------------------------------------
# 8. TRAM BARCELONA (TRAMBAIX + TRAMBESOS)
# -----------------------------------------------------------------------------
OPERATORS['tram_barcelona'] = OperatorConfig(
    code='tram_barcelona',
    name='TRAM Barcelona',
    city='Barcelona',
    region='Cataluña',
    color='00A650',
    gtfs_url='https://www.tram.cat/documents/20124/260748/google_transit_tram.zip',
    auth_method=AuthMethod.NONE,
    route_type=0,  # Tram
    agency_id='TRAM_BCN',
    agency_name='TRAM',
    agency_url='https://www.tram.cat',
    nucleo_id=50,  # Barcelona nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Tranv%C3%ADa_de_Barcelona',
    notes='Trambaix lines. For Trambesòs use tram_barcelona_besos',
)

OPERATORS['tram_barcelona_besos'] = OperatorConfig(
    code='tram_barcelona_besos',
    name='TRAM Barcelona Besòs',
    city='Barcelona',
    region='Cataluña',
    color='00A650',
    gtfs_url='https://www.tram.cat/documents/20124/260749/google_transit_tram_besos.zip',
    auth_method=AuthMethod.NONE,
    route_type=0,  # Tram
    agency_id='TRAM_BCN_BESOS',
    agency_name='TRAM',
    agency_url='https://www.tram.cat',
    nucleo_id=50,  # Barcelona nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Tranv%C3%ADa_de_Barcelona',
    notes='Trambesòs lines',
)

# -----------------------------------------------------------------------------
# 9. TRAM ALICANTE
# -----------------------------------------------------------------------------
OPERATORS['tram_alicante'] = OperatorConfig(
    code='tram_alicante',
    name='TRAM Alicante',
    city='Alicante',
    region='Comunidad Valenciana',
    color='E30613',
    gtfs_url=None,  # Old URL 404. Must download from NAP (requires login)
    auth_method=AuthMethod.MANUAL,
    route_type=0,  # Tram/Light rail
    agency_id='TRAM_ALICANTE',
    agency_name='TRAM Metropolitano de Alicante',
    agency_url='https://www.tramalacant.es',
    nucleo_id=61,  # Murcia/Alicante nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/TRAM_Metropolitano_de_Alicante',
    notes='Download from NAP: https://nap.transportes.gob.es/Files/Detail/966 (requires login)',
)

# -----------------------------------------------------------------------------
# 10. METROTENERIFE
# -----------------------------------------------------------------------------
OPERATORS['metro_tenerife'] = OperatorConfig(
    code='metro_tenerife',
    name='Metrotenerife',
    city='Santa Cruz de Tenerife',
    region='Canarias',
    color='E30613',
    gtfs_url='https://metrotenerife.com/transit/google_transit.zip',
    auth_method=AuthMethod.NONE,
    route_type=0,  # Light rail/tram
    agency_id='METRO_TENERIFE',
    agency_name='Metrotenerife',
    agency_url='https://www.metrotenerife.com',
    nucleo_id=80,  # Tenerife nucleo (created for metro)
    wikipedia_url='https://es.wikipedia.org/wiki/Tranv%C3%ADa_de_Tenerife',
)

# -----------------------------------------------------------------------------
# 11. TRANVÍA DE ZARAGOZA
# -----------------------------------------------------------------------------
OPERATORS['tranvia_zaragoza'] = OperatorConfig(
    code='tranvia_zaragoza',
    name='Tranvía de Zaragoza',
    city='Zaragoza',
    region='Aragón',
    color='009640',
    gtfs_url=None,  # Must download from NAP
    auth_method=AuthMethod.MANUAL,
    route_type=0,  # Tram
    agency_id='TRANVIA_ZARAGOZA',
    agency_name='Tranvías de Zaragoza',
    agency_url='https://www.tranviasdezaragoza.es',
    nucleo_id=40,  # Zaragoza nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Tranv%C3%ADa_de_Zaragoza',
    notes='Download from NAP: https://nap.transportes.gob.es/Files/Detail/1394 (requires login)',
)

# -----------------------------------------------------------------------------
# 12. TRANVÍA DE MURCIA
# -----------------------------------------------------------------------------
OPERATORS['tranvia_murcia'] = OperatorConfig(
    code='tranvia_murcia',
    name='Tranvía de Murcia',
    city='Murcia',
    region='Región de Murcia',
    color='E30613',
    gtfs_url=None,  # Must download from NAP
    auth_method=AuthMethod.MANUAL,
    route_type=0,  # Tram
    agency_id='TRANVIA_MURCIA',
    agency_name='Tranvía de Murcia',
    agency_url='https://www.tranviademurcia.es',
    nucleo_id=61,  # Murcia/Alicante nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Tranv%C3%ADa_de_Murcia',
    notes='Download from NAP: https://nap.transportes.gob.es/Files/Detail/1371 (requires login)',
)

# -----------------------------------------------------------------------------
# 13. SFM MALLORCA (Serveis Ferroviaris de Mallorca)
# -----------------------------------------------------------------------------
OPERATORS['sfm_mallorca'] = OperatorConfig(
    code='sfm_mallorca',
    name='SFM Mallorca',
    city='Palma',
    region='Illes Balears',
    color='005192',
    gtfs_url=None,  # Must download from NAP and filter trains
    auth_method=AuthMethod.MANUAL,
    route_type=2,  # Rail
    agency_id='SFM_MALLORCA',
    agency_name='Serveis Ferroviaris de Mallorca',
    agency_url='https://www.tib.org',
    nucleo_id=81,  # Mallorca nucleo
    wikipedia_url='https://es.wikipedia.org/wiki/Serveis_Ferroviaris_de_Mallorca',
    notes='Download from NAP: https://nap.transportes.gob.es/Files/Detail/1071 (requires login). Filter for trains (T1, T2, T3) and metro (M1)',
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_operator(code: str) -> Optional[OperatorConfig]:
    """Get operator configuration by code."""
    return OPERATORS.get(code)


def get_operators_by_region(region: str) -> List[OperatorConfig]:
    """Get all operators in a region."""
    return [op for op in OPERATORS.values() if op.region == region]


def get_operators_with_gtfs_rt() -> List[OperatorConfig]:
    """Get all operators that have GTFS-RT feeds."""
    return [op for op in OPERATORS.values() if op.gtfs_rt is not None]


def get_operators_by_auth_method(method: AuthMethod) -> List[OperatorConfig]:
    """Get operators by authentication method."""
    return [op for op in OPERATORS.values() if op.auth_method == method]


def get_auto_importable_operators() -> List[OperatorConfig]:
    """Get operators that can be imported automatically (no manual download)."""
    return [
        op for op in OPERATORS.values()
        if op.auth_method in (AuthMethod.NONE, AuthMethod.API_KEY)
        and op.gtfs_url is not None
    ]


# =============================================================================
# SUMMARY
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("TRANSIT OPERATORS CONFIGURATION")
    print("=" * 70)

    print(f"\nTotal operators: {len(OPERATORS)}")

    print("\n--- By Auth Method ---")
    for method in AuthMethod:
        ops = get_operators_by_auth_method(method)
        print(f"{method.value}: {len(ops)} - {[op.code for op in ops]}")

    print("\n--- With GTFS-RT ---")
    rt_ops = get_operators_with_gtfs_rt()
    for op in rt_ops:
        print(f"  {op.code}: {op.gtfs_rt.format.value}")

    print("\n--- Auto-importable ---")
    auto_ops = get_auto_importable_operators()
    print(f"Can be imported automatically: {len(auto_ops)}")
    for op in auto_ops:
        print(f"  - {op.name}")

    print("\n--- Require Manual Download (NAP) ---")
    manual_ops = get_operators_by_auth_method(AuthMethod.MANUAL)
    for op in manual_ops:
        print(f"  - {op.name}: {op.notes}")
