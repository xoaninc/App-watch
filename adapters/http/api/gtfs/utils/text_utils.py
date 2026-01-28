"""Text normalization utilities for GTFS data."""

from typing import Optional


# Spanish articles and prepositions that should remain lowercase (except at start)
SPANISH_LOWERCASE_WORDS = {
    'de', 'del', 'la', 'las', 'los', 'el', 'y', 'e', 'o', 'u', 'a',
    'al', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'entre',
}


def normalize_headsign(text: Optional[str]) -> Optional[str]:
    """Normalize headsign to Title Case for display.

    GTFS data from some operators (Metro Madrid, etc.) has headsigns in ALL CAPS.
    This function converts them to proper Title Case for better readability.

    Examples:
        "PUERTA DEL SUR" -> "Puerta del Sur"
        "TRES OLIVOS" -> "Tres Olivos"
        "AEROPUERTO T-4" -> "Aeropuerto T-4"
        "Hospital 12 de Octubre" -> "Hospital 12 de Octubre" (unchanged, already mixed case)

    Args:
        text: The headsign text to normalize

    Returns:
        Normalized headsign in Title Case, or original if already mixed case
    """
    if not text:
        return text

    # If already has mixed case (both upper and lower), don't modify
    # This preserves headsigns that are already properly formatted
    has_upper = any(c.isupper() for c in text)
    has_lower = any(c.islower() for c in text)
    if has_upper and has_lower:
        return text

    # Convert ALL CAPS to Title Case
    words = text.lower().split()
    result = []

    for i, word in enumerate(words):
        # First word always capitalized
        if i == 0:
            result.append(word.capitalize())
        # Spanish articles/prepositions stay lowercase
        elif word in SPANISH_LOWERCASE_WORDS:
            result.append(word)
        # Handle hyphenated words (e.g., "T-4" -> "T-4")
        elif '-' in word:
            parts = word.split('-')
            capitalized_parts = [p.capitalize() if p.isalpha() else p.upper() for p in parts]
            result.append('-'.join(capitalized_parts))
        else:
            result.append(word.capitalize())

    return ' '.join(result)
