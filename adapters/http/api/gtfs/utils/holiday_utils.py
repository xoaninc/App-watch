"""Spanish holiday utilities for schedule calculations.

Provides functions to check for national, regional (autonomous community),
and local (city) holidays in Spain, with support for province-specific lookups.
"""

from datetime import date, timedelta
from typing import Optional, Set
from zoneinfo import ZoneInfo

import holidays as holidays_lib

MADRID_TZ = ZoneInfo("Europe/Madrid")


# Mapping from province NAME to autonomous community code (for python-holidays)
# Province names match what's stored in gtfs_stops.province (from spanish_provinces.name)
# Community codes are ISO 3166-2:ES subdivision codes used by python-holidays
PROVINCE_NAME_TO_COMMUNITY = {
    # Andalucía (AN)
    "Almería": "AN",
    "Cádiz": "AN",
    "Córdoba": "AN",
    "Granada": "AN",
    "Huelva": "AN",
    "Jaén": "AN",
    "Málaga": "AN",
    "Sevilla": "AN",

    # Aragón (AR)
    "Huesca": "AR",
    "Teruel": "AR",
    "Zaragoza": "AR",

    # Asturias (AS)
    "Asturias": "AS",

    # Baleares (IB)
    "Baleares": "IB",
    "Illes Balears": "IB",

    # Canarias (CN)
    "Las Palmas": "CN",
    "Santa Cruz de Tenerife": "CN",

    # Cantabria (CB)
    "Cantabria": "CB",

    # Castilla-La Mancha (CM)
    "Albacete": "CM",
    "Ciudad Real": "CM",
    "Cuenca": "CM",
    "Guadalajara": "CM",
    "Toledo": "CM",

    # Castilla y León (CL)
    "Ávila": "CL",
    "Burgos": "CL",
    "León": "CL",
    "Palencia": "CL",
    "Salamanca": "CL",
    "Segovia": "CL",
    "Soria": "CL",
    "Valladolid": "CL",
    "Zamora": "CL",

    # Catalunya (CT)
    "Barcelona": "CT",
    "Girona": "CT",
    "Lleida": "CT",
    "Tarragona": "CT",

    # Extremadura (EX)
    "Badajoz": "EX",
    "Cáceres": "EX",

    # Galicia (GA)
    "A Coruña": "GA",
    "Lugo": "GA",
    "Ourense": "GA",
    "Pontevedra": "GA",

    # La Rioja (RI)
    "La Rioja": "RI",

    # Madrid (MD)
    "Madrid": "MD",

    # Murcia (MC)
    "Murcia": "MC",

    # Navarra (NC)
    "Navarra": "NC",

    # País Vasco (PV)
    "Álava": "PV",
    "Araba/Álava": "PV",
    "Vizcaya": "PV",
    "Bizkaia": "PV",
    "Guipúzcoa": "PV",
    "Gipuzkoa": "PV",

    # Valencia (VC)
    "Alicante": "VC",
    "Castellón": "VC",
    "Valencia": "VC",

    # Ceuta (CE)
    "Ceuta": "CE",

    # Melilla (ML)
    "Melilla": "ML",
}

# Mapping from province name to province code (for local_holidays table lookup)
# Province codes are generated as province_name[:3].upper() by import_province_boundaries.py
PROVINCE_NAME_TO_CODE = {
    # Andalucía
    "Almería": "ALM",
    "Cádiz": "CÁD",
    "Córdoba": "CÓR",
    "Granada": "GRA",
    "Huelva": "HUE",
    "Jaén": "JAÉ",
    "Málaga": "MÁL",
    "Sevilla": "SEV",
    # Aragón
    "Huesca": "HUE",  # Note: collision with Huelva
    "Teruel": "TER",
    "Zaragoza": "ZAR",
    # Asturias
    "Asturias": "AST",
    # Baleares
    "Baleares": "BAL",
    "Illes Balears": "ILL",
    # Canarias
    "Las Palmas": "LAS",
    "Santa Cruz de Tenerife": "SAN",
    # Cantabria
    "Cantabria": "CAN",
    # Castilla-La Mancha
    "Albacete": "ALB",
    "Ciudad Real": "CIU",
    "Cuenca": "CUE",
    "Guadalajara": "GUA",
    "Toledo": "TOL",
    # Castilla y León
    "Ávila": "ÁVI",
    "Burgos": "BUR",
    "León": "LEÓ",
    "Palencia": "PAL",
    "Salamanca": "SAL",
    "Segovia": "SEG",
    "Soria": "SOR",
    "Valladolid": "VAL",  # Note: collision with Valencia
    "Zamora": "ZAM",
    # Catalunya
    "Barcelona": "BAR",
    "Girona": "GIR",
    "Lleida": "LLE",
    "Tarragona": "TAR",
    # Extremadura
    "Badajoz": "BAD",
    "Cáceres": "CÁC",
    # Galicia
    "A Coruña": "ACO",
    "Lugo": "LUG",
    "Ourense": "OUR",
    "Pontevedra": "PON",
    # La Rioja
    "La Rioja": "LAR",
    # Madrid
    "Madrid": "MAD",
    # Murcia
    "Murcia": "MUR",
    # Navarra
    "Navarra": "NAV",
    # País Vasco
    "Álava": "ÁLA",
    "Araba/Álava": "ARA",
    "Vizcaya": "VIZ",
    "Bizkaia": "BIZ",
    "Guipúzcoa": "GUI",
    "Gipuzkoa": "GIP",
    # Valencia
    "Alicante": "ALI",
    "Castellón": "CAS",
    "Valencia": "VAL",
    # Ceuta y Melilla
    "Ceuta": "CEU",
    "Melilla": "MEL",
}


def get_holidays_for_province(province_name: str, year: int) -> Set[date]:
    """Get national + regional holidays for a province using python-holidays.

    Args:
        province_name: Province name (e.g., 'Madrid', 'Barcelona')
        year: Year to get holidays for

    Returns:
        Set of date objects for holidays
    """
    community = PROVINCE_NAME_TO_COMMUNITY.get(province_name)
    if community:
        es_holidays = holidays_lib.Spain(years=year, prov=community)
    else:
        # Fallback to national only if province not mapped
        es_holidays = holidays_lib.Spain(years=year)
    return set(es_holidays.keys())


def get_local_holidays(db, province_name: str, year: int) -> Set[date]:
    """Get local (city-specific) holidays from database.

    Args:
        db: Database session
        province_name: Province name (e.g., 'Madrid', 'Barcelona')
        year: Year to get holidays for

    Returns:
        Set of date objects for local holidays in this province
    """
    from src.gtfs_bc.holiday.infrastructure.models import LocalHolidayModel

    # Convert province name to code for database lookup
    province_code = PROVINCE_NAME_TO_CODE.get(province_name)
    if not province_code:
        return set()

    local = db.query(LocalHolidayModel).filter(
        LocalHolidayModel.province_code == province_code
    ).all()

    holidays_set = set()
    for h in local:
        try:
            holidays_set.add(date(year, h.month, h.day))
        except ValueError:
            # Invalid date (e.g., Feb 30)
            pass

    return holidays_set


def is_holiday_for_province(check_date: date, province_name: str, db=None) -> bool:
    """Check if date is a holiday for the given province.

    Checks national holidays, regional (autonomous community) holidays,
    and optionally local (city) holidays if db session is provided.

    Args:
        check_date: Date to check
        province_name: Province name (e.g., 'Madrid', 'Barcelona')
        db: Optional database session for local holiday lookup

    Returns:
        True if the date is a holiday, False otherwise
    """
    year = check_date.year

    # Check national + regional holidays
    holidays_set = get_holidays_for_province(province_name, year)
    if check_date in holidays_set:
        return True

    # Check local holidays if db provided
    if db:
        local = get_local_holidays(db, province_name, year)
        if check_date in local:
            return True

    return False


def is_pre_holiday_for_province(check_date: date, province_name: str, db=None) -> bool:
    """Check if a date is a pre-holiday (víspera) for the given province.

    A pre-holiday is the day before a holiday, when extended schedules apply.

    Args:
        check_date: Date to check
        province_name: Province name
        db: Optional database session for local holiday lookup

    Returns:
        True if tomorrow is a holiday for this province
    """
    tomorrow = check_date + timedelta(days=1)
    return is_holiday_for_province(tomorrow, province_name, db)


def get_effective_day_type_for_province(
    now,
    province_name: Optional[str] = None,
    db=None
) -> str:
    """Determine effective day type considering regional holidays.

    Args:
        now: Current datetime
        province_name: Province name for regional holiday lookup.
                      If None, uses Madrid defaults.
        db: Optional database session for local holiday lookup

    Returns:
        'weekday', 'friday', 'saturday', or 'sunday'

    Logic:
    - Sunday or holiday -> 'sunday'
    - Saturday -> 'saturday'
    - Friday or pre-holiday (víspera) -> 'friday' (extended hours)
    - Monday-Thursday -> 'weekday'
    """
    current_date = now.date()
    weekday = now.weekday()  # 0=Monday, 6=Sunday

    # Use province-aware holiday check if province provided
    if province_name:
        is_today_holiday = is_holiday_for_province(current_date, province_name, db)
        is_tomorrow_holiday = is_pre_holiday_for_province(current_date, province_name, db)
    else:
        # Fallback to Madrid (existing behavior)
        is_today_holiday = is_holiday(current_date)
        is_tomorrow_holiday = is_pre_holiday(current_date)

    # Check if today is a holiday -> use sunday schedule
    if is_today_holiday:
        return "sunday"

    # Sunday
    if weekday == 6:
        return "sunday"

    # Saturday
    if weekday == 5:
        return "saturday"

    # Friday or pre-holiday (víspera) -> extended hours
    if weekday == 4 or is_tomorrow_holiday:
        return "friday"

    # Monday-Thursday
    return "weekday"


# =============================================================================
# Legacy functions for backward compatibility
# These functions use Madrid as the default province
# =============================================================================

def get_spanish_holidays(year: int) -> set:
    """Get Spanish national and Madrid regional holidays for a given year.

    DEPRECATED: Use get_holidays_for_province() for province-aware lookups.

    Returns a set of date objects for holidays.
    """
    # Use python-holidays with Madrid region
    return get_holidays_for_province("Madrid", year)


def is_holiday(check_date: date) -> bool:
    """Check if a date is a holiday (using Madrid as reference).

    DEPRECATED: Use is_holiday_for_province() for province-aware lookups.
    """
    return is_holiday_for_province(check_date, "Madrid")


def is_pre_holiday(check_date: date) -> bool:
    """Check if a date is a pre-holiday (víspera de festivo).

    DEPRECATED: Use is_pre_holiday_for_province() for province-aware lookups.

    A pre-holiday is the day before a holiday, when extended
    (friday/saturday) schedules typically apply.
    """
    return is_pre_holiday_for_province(check_date, "Madrid")


def get_effective_day_type(now) -> str:
    """Determine the effective day type considering holidays and pre-holidays.

    DEPRECATED: Use get_effective_day_type_for_province() for province-aware lookups.

    Returns: 'weekday', 'friday', 'saturday', or 'sunday'

    Logic:
    - Sunday or holiday -> 'sunday'
    - Saturday -> 'saturday'
    - Friday or pre-holiday (víspera) -> 'friday' (extended hours)
    - Monday-Thursday -> 'weekday'
    """
    return get_effective_day_type_for_province(now, "Madrid")
