from dataclasses import dataclass
from typing import Optional


@dataclass
class Network:
    """Represents a Cercanías network (e.g., Madrid, Barcelona, etc.)."""

    code: str  # Network code (e.g., "10T" for Madrid)
    name: str  # Network name (e.g., "Cercanías Madrid")
    city: str  # Main city (e.g., "Madrid")
    region: str  # Region/community (e.g., "Comunidad de Madrid")
    color: str  # Primary brand color (hex without #)
    text_color: str  # Text color for contrast (hex without #)
    logo_url: Optional[str] = None  # URL to network logo
    wikipedia_url: Optional[str] = None  # Wikipedia article URL
    description: Optional[str] = None  # Short description


__all__ = ["Network"]
