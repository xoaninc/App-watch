"""AI-based alert analysis schemas."""
from typing import Optional, List
from pydantic import BaseModel, Field


class AlertAnalysis(BaseModel):
    """AI analysis result for a transit alert."""
    
    is_line_open: bool = Field(
        description="True si la línea está operativa, False si está completamente suspendida"
    )
    
    status: str = Field(
        description="Estado de la línea: NORMAL, DELAYS, PARTIAL_SUSPENSION, FULL_SUSPENSION, FACILITY_ISSUE"
    )
    
    reason: str = Field(
        description="Explicación breve del estado (ej: 'Demoras de 20-40 minutos', 'Ascensor fuera de servicio')"
    )
    
    affected_segments: Optional[List[str]] = Field(
        default=None,
        description="Tramos afectados si es suspensión parcial (ej: ['Utrera', 'Lora del Río'])"
    )
    
    severity: str = Field(
        default="INFO",
        description="Nivel de severidad: INFO, WARNING, CRITICAL"
    )
