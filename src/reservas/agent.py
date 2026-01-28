"""
Lógica del agente especializado en reservas usando LangChain 1.2+ API moderna.
Versión mejorada con logging, métricas, configuración centralizada y memoria automática.
"""

from typing import Any, Dict
from dataclasses import dataclass

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver

try:
    from . import config as app_config
    from .models import ReservaConfig
    from .tools import AGENT_TOOLS
    from .logger import get_logger
    from .metrics import track_chat_response, track_llm_call, record_chat_error, chat_requests_total
    from .prompts import build_reserva_system_prompt
except ImportError:
    import config as app_config
    from models import ReservaConfig
    from tools import AGENT_TOOLS
    from logger import get_logger
    from metrics import track_chat_response, track_llm_call, record_chat_error, chat_requests_total
    from prompts import build_reserva_system_prompt

logger = get_logger(__name__)

# Checkpointer global para memoria automática
_checkpointer = InMemorySaver()

# Cache del agente
_agent = None

@dataclass
class AgentContext:
    """
    Esquema de contexto runtime para el agente.
    Este contexto se inyecta en las tools que lo necesiten.
    """
    id_empresa: int
    duracion_cita_minutos: int = 60
    slots: int = 60
    id_usuario: int = 1
    session_id: str = ""


def _validate_context(context: Dict[str, Any]) -> None:
    """
    Valida que el contexto tenga los parámetros requeridos.
    
    Args:
        context: Contexto con configuración del bot
    
    Raises:
        ValueError: Si faltan parámetros requeridos
    """
    config_data = context.get("config", {})
    required_keys = ["id_empresa"]
    missing = [k for k in required_keys if k not in config_data or config_data[k] is None]
    
    if missing:
        raise ValueError(f"Context missing required keys in config: {missing}")
    
    logger.debug(f"[AGENT] Context validated: id_empresa={config_data.get('id_empresa')}")


def _get_agent(config: Dict[str, Any]):
    """
    Obtiene o crea el agente con la API moderna de LangChain 1.2+.
    
    Args:
        config: Diccionario con configuración del agente (personalidad, etc.)
    
    Returns:
        Agente configurado con tools y checkpointer
    """
    global _agent
    
    # Recrear agent cada vez para tener configuración actualizada
    # (en producción, podrías cachear por configuración)
    
    logger.info(f"[AGENT] Creando agente con LangChain 1.2+ API")
    
    # Inicializar modelo
    model = init_chat_model(
        f"openai:{app_config.OPENAI_MODEL}",
        api_key=app_config.OPENAI_API_KEY,
        temperature=0.4,  
        max_tokens=app_config.MAX_TOKENS,
        timeout=app_config.OPENAI_TIMEOUT,
    )
    
    # Construir system prompt usando template Jinja2
    system_prompt = build_reserva_system_prompt(
        config=config,
        history=None  # Por ahora sin historial, se agregará cuando implementemos límite de memoria
    )
    
    # Crear agente con API moderna
    _agent = create_agent(
        model=model,
        tools=AGENT_TOOLS,
        system_prompt=system_prompt,
        checkpointer=_checkpointer  # Memoria automática
    )
    
    logger.info(f"[AGENT] Agente creado - Tools: {len(AGENT_TOOLS)}, Checkpointer: InMemorySaver")
    
    return _agent


def _prepare_agent_context(context: Dict[str, Any], session_id: str) -> AgentContext:
    """
    Prepara el contexto runtime para inyectar a las tools del agente.
    
    Args:
        context: Contexto del orquestador
        session_id: ID de sesión
    
    Returns:
        AgentContext configurado
    """
    config_data = context.get("config", {})
    
    return AgentContext(
        id_empresa=config_data.get("id_empresa", 1),
        duracion_cita_minutos=config_data.get("duracion_cita_minutos", 60),
        slots=config_data.get("slots", 60),
        id_usuario=config_data.get("agendar_usuario", 1),
        session_id=session_id
    )


async def process_reserva_message(
    message: str,
    session_id: str,
    context: Dict[str, Any]
) -> str:
    """
    Procesa un mensaje del cliente sobre reservas usando LangChain 1.2+ Agent.
    
    El agente tiene acceso a tools internas:
    - check_availability: Consulta horarios disponibles
    - create_booking: Crea reserva con validación real
    
    La memoria es automática gracias al checkpointer (InMemorySaver).
    
    Args:
        message: Mensaje del cliente
        session_id: ID de sesión para tracking y memoria
        context: Contexto adicional (config del bot, id_empresa, etc.)
    
    Returns:
        Respuesta del agente especializado
    """
    # Validación de entrada
    if not message or not message.strip():
        return "No recibí tu mensaje. ¿Podrías repetirlo?"
    
    if not session_id:
        raise ValueError("session_id es requerido")
    
    # Registrar request
    chat_requests_total.labels(session_id=session_id).inc()
    
    # Validar contexto
    try:
        _validate_context(context)
    except ValueError as e:
        logger.error(f"[AGENT] Error de contexto: {e}")
        record_chat_error("context_error")
        return f"Error de configuración: {str(e)}"
    
    config_data = context.get("config", {})
    reserva_config = ReservaConfig(**config_data)
    
    if "personalidad" not in config_data or not config_data.get("personalidad"):
        config_data["personalidad"] = reserva_config.personalidad or "amable, profesional y eficiente"
    
    try:
        agent = _get_agent(config_data)
    except Exception as e:
        logger.error(f"[AGENT] Error creando agent: {e}", exc_info=True)
        record_chat_error("agent_creation_error")
        return "Disculpa, tuve un problema de configuración. ¿Podrías intentar nuevamente?"
    
    agent_context = _prepare_agent_context(context, session_id)
    
    config = {
        "configurable": {
            "thread_id": session_id
        }
    }
    try:
        logger.info(f"[AGENT] Invocando agent - Session: {session_id}, Message: {message[:100]}...")
        
        with track_chat_response():
            with track_llm_call():
                result = agent.invoke(
                    {
                        "messages": [
                            {"role": "user", "content": message}
                        ]
                    },
                    config=config,
                    context=agent_context
                )
        
        messages = result.get("messages", [])
        if messages:
            last_message = messages[-1]
            response_text = last_message.content if hasattr(last_message, 'content') else str(last_message)
        else:
            response_text = "Lo siento, no pude procesar tu solicitud."
        
        logger.info(f"[AGENT] Respuesta generada: {response_text[:200]}...")
    
    except Exception as e:
        logger.error(f"[AGENT] Error al ejecutar agent: {e}", exc_info=True)
        record_chat_error("agent_execution_error")
        return "Disculpa, tuve un problema al procesar tu mensaje. ¿Podrías intentar nuevamente?"
    
    return response_text
