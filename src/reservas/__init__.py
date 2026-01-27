"""
Agente especializado en reservas - MaravIA

Sistema mejorado con:
- Logging centralizado
- Performance async (httpx)
- Cache global con TTL
- Validación de datos
- Métricas y observabilidad
"""

__version__ = "1.0.0"
__author__ = "MaravIA Team"

# Exportar funciones principales
from .agent import process_reserva_message
from .logger import get_logger, setup_logging
from .metrics import (
    track_chat_response,
    track_tool_execution,
    record_booking_success,
    record_booking_failure
)
from .validation import (
    validate_contact,
    validate_customer_name,
    validate_datetime,
    validate_booking_data
)

__all__ = [
    # Core
    "process_reserva_message",
    # Logging
    "get_logger",
    "setup_logging",
    # Metrics
    "track_chat_response",
    "track_tool_execution",
    "record_booking_success",
    "record_booking_failure",
    # Validation
    "validate_contact",
    "validate_customer_name",
    "validate_datetime",
    "validate_booking_data",
]
