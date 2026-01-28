"""
Servidor MCP del agente especializado en reservas.
Usa FastMCP para exponer herramientas según el protocolo MCP.

Versión mejorada con logging, métricas y observabilidad.
"""

import logging
from typing import Any, Dict
from fastmcp import FastMCP
from prometheus_client import make_asgi_app

try:
    from . import config as app_config
    from .agent import process_reserva_message
    from .logger import setup_logging, get_logger
    from .metrics import initialize_agent_info
except ImportError:
    import config as app_config
    from agent import process_reserva_message
    from logger import setup_logging, get_logger
    from metrics import initialize_agent_info

# Configurar logging antes de cualquier otra cosa
log_level = getattr(logging, app_config.LOG_LEVEL.upper(), logging.INFO)
setup_logging(
    level=log_level,
    log_file=app_config.LOG_FILE if app_config.LOG_FILE else None
)

logger = get_logger(__name__)

# Inicializar información del agente para métricas
initialize_agent_info(model=app_config.OPENAI_MODEL, version="2.0.0")

# Inicializar servidor MCP
mcp = FastMCP(
    name="Agente Reservas - MaravIA",
    instructions="Agente especializado en gestión de reservas, turnos y citas con LangChain 1.2+ Agent"
)


@mcp.tool()
async def chat(
    message: str,
    session_id: str,
    context: Dict[str, Any] | None = None
) -> str:
    """
    Agente especializado en gestión de reservas con LangChain 1.2+ Agent.
    
    Esta es la ÚNICA herramienta que el orquestador debe llamar.
    Internamente, el agente usa tools propias para:
    - Consultar disponibilidad de horarios (check_availability)
    - Crear reservas con validación real (create_booking)
    
    El agente maneja la conversación completa de forma autónoma,
    decidiendo cuándo usar cada tool según el contexto.
    La memoria es automática gracias al checkpointer (InMemorySaver).
    
    Args:
        message: Mensaje del cliente que quiere reservar
        session_id: ID de sesión único para tracking y memoria
        context: Contexto adicional requerido:
            - config.id_empresa (int, requerido): ID de la empresa
            - config.duracion_cita_minutos (int, opcional): Duración en minutos (default: 60)
            - config.slots (int, opcional): Slots disponibles (default: 60)
            - config.agendar_usuario (int, opcional): ID usuario que agenda (default: 1)
            - config.personalidad (str, opcional): Personalidad del agente
    
    Returns:
        Respuesta del agente especializado en reservas
    
    Examples:
        >>> context = {
        ...     "config": {
        ...         "id_empresa": 123,
        ...         "personalidad": "amable y profesional"
        ...     }
        ... }
        >>> await chat("Quiero reservar un turno", "session-123", context)
        "¡Perfecto! ¿Para qué servicio deseas reservar?"
    """
    if context is None:
        context = {}
    
    logger.info(f"[MCP] Mensaje recibido - Session: {session_id}, Length: {len(message)} chars")
    logger.debug(f"[MCP] Message: {message[:100]}...")
    logger.debug(f"[MCP] Context keys: {list(context.keys())}")
    
    try:
        reply = await process_reserva_message(
            message=message,
            session_id=session_id,
            context=context
        )
        
        logger.info(f"[MCP] ✅ Respuesta generada - Length: {len(reply)} chars")
        logger.debug(f"[MCP] Reply: {reply[:200]}...")
        return reply
    
    except ValueError as e:
        error_msg = f"Error de configuración: {str(e)}"
        logger.error(f"[MCP] ❌ {error_msg}")
        return error_msg
    
    except Exception as e:
        error_msg = f"Error procesando mensaje: {str(e)}"
        logger.error(f"[MCP] ❌ {error_msg}", exc_info=True)
        return error_msg


# Endpoint de métricas para Prometheus (opcional)
metrics_app = make_asgi_app()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO AGENTE RESERVAS - MaravIA")
    logger.info("=" * 60)
    logger.info(f"📍 Host: {app_config.SERVER_HOST}:{app_config.SERVER_PORT}")
    logger.info(f"🤖 Modelo: {app_config.OPENAI_MODEL}")
    logger.info(f"⏱️  Timeout LLM: {app_config.OPENAI_TIMEOUT}s")
    logger.info(f"⏱️  Timeout API: {app_config.API_TIMEOUT}s")
    logger.info(f"💾 Cache TTL: {app_config.SCHEDULE_CACHE_TTL_MINUTES} min")
    logger.info(f"📊 Log Level: {app_config.LOG_LEVEL}")
    logger.info("-" * 60)
    logger.info("🔧 Tool expuesta al orquestador: chat")
    logger.info("🛠️  Tools internas del agente:")
    logger.info("   - check_availability (consulta horarios)")
    logger.info("   - create_booking (crea reservas)")
    logger.info("-" * 60)
    logger.info("📈 Métricas disponibles en /metrics (Prometheus)")
    logger.info("=" * 60)
    
    # Ejecutar servidor MCP
    try:
        mcp.run(
            transport="http",  # HTTP para conectar servicios separados
            host=app_config.SERVER_HOST,
            port=app_config.SERVER_PORT
        )
    except KeyboardInterrupt:
        logger.info("\n👋 Servidor detenido por el usuario")
    except Exception as e:
        logger.critical(f"❌ Error crítico en el servidor: {e}", exc_info=True)
        raise
