"""AI-based alert classifier using Groq."""
import instructor
import logging
import json
from datetime import datetime, time
from typing import Optional, Dict, Tuple
from groq import Groq
from zoneinfo import ZoneInfo

from core.config import Settings
from src.gtfs_bc.realtime.domain.schemas.ai_status import AlertAnalysis

logger = logging.getLogger(__name__)

# Cache global: {route_id: (AlertAnalysis, timestamp)}
_analysis_cache: Dict[str, Tuple[AlertAnalysis, datetime]] = {}

# Cache para alertas individuales: {alert_id: AlertAnalysis}
_alert_cache: Dict[str, AlertAnalysis] = {}

# Horarios de análisis (6am y 6pm hora española)
ANALYSIS_HOURS = [time(6, 0), time(18, 0)]
MADRID_TZ = ZoneInfo("Europe/Madrid")


class AIAlertClassifier:
    """Clasificador de alertas usando Groq AI con caché temporal."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        # Parchear el cliente de Groq con instructor para salida estructurada
        self.client = instructor.from_groq(
            Groq(api_key=settings.GROQ_API_KEY),
            mode=instructor.Mode.JSON
        )
    
    def _should_reanalyze(self, route_id: str) -> bool:
        """Determina si es hora de reanalizar (6am o 6pm hora española)."""
        if route_id not in _analysis_cache:
            return True
        
        now = datetime.now(MADRID_TZ)
        _, last_analysis = _analysis_cache[route_id]
        
        # Si es del mismo día y ya pasamos la última ventana de análisis, no reanalizar
        if last_analysis.date() == now.date():
            last_hour = last_analysis.time()
            # Ya analizamos hoy después de las 6am y antes de las 6pm
            if time(6, 0) <= last_hour < time(18, 0) and now.time() < time(18, 0):
                return False
            # Ya analizamos hoy después de las 6pm
            if last_hour >= time(18, 0):
                return False
        
        # Verificar si estamos en ventana de análisis (±30min de 6am o 6pm)
        current_time = now.time()
        for target_hour in ANALYSIS_HOURS:
            # Ventana de 30 minutos antes y después
            start = time(target_hour.hour - 1 if target_hour.hour > 0 else 23, 30)
            end = time(target_hour.hour, 30)
            
            if start <= current_time <= end:
                return True
        
        return False
    
    def analyze_alerts(
        self, 
        route_id: str,
        alerts: list,
        force: bool = False
    ) -> AlertAnalysis:
        """
        Analiza las alertas de una ruta usando Groq AI.
        
        Args:
            route_id: ID de la ruta
            alerts: Lista de objetos Alert con description_text y header_text
            force: Forzar análisis ignorando caché
            
        Returns:
            AlertAnalysis con el estado de la línea
        """
        # Verificar caché
        if not force and not self._should_reanalyze(route_id):
            cached_analysis, _ = _analysis_cache[route_id]
            logger.info(f"[AIClassifier] Using cached analysis for {route_id}")
            return cached_analysis
        
        # Si no hay alertas, línea normal
        if not alerts:
            analysis = AlertAnalysis(
                is_line_open=True,
                status="NORMAL",
                reason="Sin incidencias reportadas",
                affected_segments=None,
                severity="INFO"
            )
            _analysis_cache[route_id] = (analysis, datetime.now(MADRID_TZ))
            return analysis
        
        # Construir texto combinado de todas las alertas
        alert_texts = []
        for alert in alerts:
            header = alert.header_text or ""
            desc = alert.description_text or ""
            if header or desc:
                alert_texts.append(f"Título: {header}\nDescripción: {desc}")
        
        combined_text = "\n\n---\n\n".join(alert_texts[:10])  # Máximo 10 alertas
        
        prompt = f"""Analiza estas alertas de transporte público y determina el estado de la línea.

Alertas:
{combined_text}

Clasifica el estado en:
- NORMAL: Servicio normal, solo avisos informativos
- DELAYS: Demoras pero circulación activa
- PARTIAL_SUSPENSION: Algunos trenes/tramos suspendidos
- FULL_SUSPENSION: Línea completamente cerrada
- FACILITY_ISSUE: Solo problemas de instalaciones (ascensores, etc.)

Devuelve JSON con: is_line_open (bool), status, reason (breve), affected_segments (lista de estaciones si aplica), severity (INFO/WARNING/CRITICAL)"""

        try:
            logger.info(f"[AIClassifier] Analyzing {len(alerts)} alerts for {route_id}")
            
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",  # 128k context window
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un experto en transporte. Analiza alertas y clasifica el estado. Responde SOLO con JSON válido."
                    },
                    {"role": "user", "content": prompt},
                ],
                response_model=AlertAnalysis,
                max_tokens=500,
                temperature=0.1,  # Baja temperatura para respuestas consistentes
            )
            
            # Cachear resultado
            _analysis_cache[route_id] = (response, datetime.now(MADRID_TZ))
            logger.info(f"[AIClassifier] {route_id}: {response.status} - {response.reason}")
            
            return response
            
        except Exception as e:
            logger.error(f"[AIClassifier] Error analyzing alerts for {route_id}: {e}")
            # Fallback seguro
            fallback = AlertAnalysis(
                is_line_open=True,
                status="NORMAL",
                reason=f"Error de análisis IA: {str(e)[:100]}",
                affected_segments=None,
                severity="INFO"
            )
            _analysis_cache[route_id] = (fallback, datetime.now(MADRID_TZ))
            return fallback
    
    def analyze_single_alert(self, alert_id: str, header_text: str, description_text: str) -> AlertAnalysis:
        """Analiza una alerta individual para enriquecimiento.
        
        Args:
            alert_id: ID único de la alerta
            header_text: Texto del encabezado (puede estar vacío)
            description_text: Descripción de la alerta
            
        Returns:
            AlertAnalysis con clasificación individual
        """
        # Check cache first
        cache_key = f"{alert_id}_{hash(description_text)}"
        if cache_key in _alert_cache:
            logger.debug(f"[AIClassifier] Cache hit for alert {alert_id}")
            return _alert_cache[cache_key]
        
        # Construir prompt para alerta individual
        alert_text = f"{header_text}\n{description_text}" if header_text else description_text
        
        prompt = f"""Analiza esta alerta de transporte público individual.

Alerta: {alert_text}

Clasifica:
- status: NORMAL, DELAYS, PARTIAL_SUSPENSION, FULL_SUSPENSION, o FACILITY_ISSUE
- severity: INFO, WARNING, o CRITICAL
- Genera un summary breve (max 60 caracteres) para mostrar como título
- Extrae affected_segments (estaciones mencionadas) si aplica

Devuelve JSON con: is_line_open, status, reason (summary), affected_segments (lista), severity"""

        try:
            logger.info(f"[AIClassifier] Analyzing individual alert {alert_id}")
            
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",  # 128k context window
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un experto en transporte. Analiza alertas y genera resúmenes concisos. Responde SOLO con JSON válido."
                    },
                    {"role": "user", "content": prompt},
                ],
                response_model=AlertAnalysis,
                max_tokens=300,
                temperature=0.1,
            )
            
            # Cache result
            _alert_cache[cache_key] = response
            logger.info(f"[AIClassifier] Alert {alert_id}: {response.severity} - {response.reason}")
            
            return response
            
        except Exception as e:
            logger.error(f"[AIClassifier] Error analyzing alert {alert_id}: {e}")
            # Fallback: usar descripción como summary
            return AlertAnalysis(
                is_line_open=True,
                status="NORMAL",
                reason=description_text[:60] if description_text else "Sin descripción",
                affected_segments=None,
                severity="INFO"
            )
    
    def clear_cache(self, route_id: Optional[str] = None):
        """Limpia el caché (todo o solo una ruta)."""
        if route_id:
            _analysis_cache.pop(route_id, None)
            logger.info(f"[AIClassifier] Cleared cache for {route_id}")
        else:
            _analysis_cache.clear()
            logger.info("[AIClassifier] Cleared all cache")
