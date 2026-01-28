"""
Agente especializado en reservas - MaravIA

🚀 Versión 2.0.0 - LangChain 1.2+ API Moderna

Sistema mejorado con:
- ✨ LangChain 1.2+ API moderna con create_agent
- 🧠 Memoria automática con checkpointer
- 🔧 Runtime context para tools
- 📊 Logging centralizado
- ⚡ Performance async (httpx)
- 💾 Cache global con TTL
- ✅ Validación de datos con Pydantic
- 📈 Métricas y observabilidad (Prometheus)
"""

__version__ = "2.0.0"
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
