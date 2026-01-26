"""Spanish holiday utilities for schedule calculations."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

MADRID_TZ = ZoneInfo("Europe/Madrid")


def get_spanish_holidays(year: int) -> set:
    """Get Spanish national and Madrid regional holidays for a given year.

    Returns a set of date objects for holidays.
    """
    holidays = set()

    # National holidays (fiestas nacionales)
    holidays.add(date(year, 1, 1))    # Año Nuevo
    holidays.add(date(year, 1, 6))    # Epifanía del Señor (Reyes)
    holidays.add(date(year, 5, 1))    # Día del Trabajador
    holidays.add(date(year, 8, 15))   # Asunción de la Virgen
    holidays.add(date(year, 10, 12))  # Fiesta Nacional de España
    holidays.add(date(year, 11, 1))   # Todos los Santos
    holidays.add(date(year, 12, 6))   # Día de la Constitución
    holidays.add(date(year, 12, 8))   # Inmaculada Concepción
    holidays.add(date(year, 12, 25))  # Navidad

    # Madrid regional holidays
    holidays.add(date(year, 5, 2))    # Día de la Comunidad de Madrid
    holidays.add(date(year, 5, 15))   # San Isidro (Madrid capital)
    holidays.add(date(year, 11, 9))   # Almudena (Madrid capital)

    # Easter (variable dates) - using Anonymous Gregorian algorithm
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter_sunday = date(year, month, day)

    # Jueves Santo (Thursday before Easter)
    holidays.add(easter_sunday - timedelta(days=3))
    # Viernes Santo (Friday before Easter)
    holidays.add(easter_sunday - timedelta(days=2))

    return holidays


def is_holiday(check_date: date) -> bool:
    """Check if a date is a holiday."""
    holidays = get_spanish_holidays(check_date.year)
    return check_date in holidays


def is_pre_holiday(check_date: date) -> bool:
    """Check if a date is a pre-holiday (víspera de festivo).

    A pre-holiday is the day before a holiday, when extended
    (friday/saturday) schedules typically apply.
    """
    tomorrow = check_date + timedelta(days=1)
    return is_holiday(tomorrow)


def get_effective_day_type(now) -> str:
    """Determine the effective day type considering holidays and pre-holidays.

    Returns: 'weekday', 'friday', 'saturday', or 'sunday'

    Logic:
    - Sunday or holiday -> 'sunday'
    - Saturday -> 'saturday'
    - Friday or pre-holiday (víspera) -> 'friday' (extended hours)
    - Monday-Thursday -> 'weekday'
    """
    current_date = now.date()
    weekday = now.weekday()  # 0=Monday, 6=Sunday

    # Check if today is a holiday -> use sunday schedule
    if is_holiday(current_date):
        return "sunday"

    # Sunday
    if weekday == 6:
        return "sunday"

    # Saturday
    if weekday == 5:
        return "saturday"

    # Friday or pre-holiday (víspera) -> extended hours
    if weekday == 4 or is_pre_holiday(current_date):
        return "friday"

    # Monday-Thursday
    return "weekday"
