"""
Lógica del agente especializado en reservas usando LangChain Agent con tools.
Versión mejorada con logging, métricas y configuración centralizada.
"""

from typing import Any, Dict, Optional

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor

try:
    from . import config as app_config
    from .models import ReservaConfig
    from .memory import add_turn, get_history
    from .tools import AGENT_TOOLS
    from .logger import get_logger
    from .metrics import track_chat_response, track_llm_call, record_chat_error, chat_requests_total
except ImportError:
    import config as app_config
    from models import ReservaConfig
    from memory import add_turn, get_history
    from tools import AGENT_TOOLS
    from logger import get_logger
    from metrics import track_chat_response, track_llm_call, record_chat_error, chat_requests_total

logger = get_logger(__name__)

_llm: Optional[ChatOpenAI] = None
_agent_executor: Optional[AgentExecutor] = None


def _validate_context(context: Dict[str, Any]) -> None:
    """
    Valida que el contexto tenga los parámetros requeridos.
    
    Args:
        context: Contexto con configuración del bot
    
    Raises:
        ValueError: Si faltan parámetros requeridos
    """
    required_keys = ["id_empresa"]
    missing = [k for k in required_keys if k not in context or context[k] is None]
    
    if missing:
        raise ValueError(f"Context missing required keys: {missing}")
    
    logger.debug(f"[AGENT] Context validated: id_empresa={context.get('id_empresa')}")


def _build_agent_prompt(personalidad: str) -> ChatPromptTemplate:
    """
    Construye el prompt para el agente con memoria y tools.
    
    Args:
        personalidad: Personalidad del agente
    
    Returns:
        ChatPromptTemplate configurado
    """
    system_template = f"""Eres un asistente especializado en **gestión de reservas**.

## Tu Personalidad
{personalidad}

## Tu Función
Ayudar al cliente a completar una reserva capturando la información necesaria:
1. **Servicio/Actividad**: ¿Qué quiere reservar?
2. **Fecha**: ¿Para qué día?
3. **Hora**: ¿A qué hora?
4. **Datos del cliente**: Nombre y contacto (teléfono o email)

## Herramientas Disponibles
Tienes acceso a estas herramientas para ayudarte:

1. **check_availability(service, date)**: Consulta horarios disponibles
   - Úsala cuando el cliente pregunte por disponibilidad
   - Úsala cuando necesites verificar si una fecha está libre

2. **create_booking(service, date, time, customer_name, customer_contact, session_id)**: Crea una reserva
   - Úsala SOLO cuando tengas TODOS los datos necesarios
   - La herramienta validará el horario y creará la reserva real
   - Retorna un código de confirmación

## Flujo de Trabajo
1. **Saluda** de forma {personalidad}
2. **Pregunta** por los datos que faltan (uno a la vez)
3. **Usa check_availability** si el cliente pregunta o necesitas verificar
4. **Confirma** los datos con el cliente antes de crear la reserva
5. **Usa create_booking** cuando tengas todo confirmado
6. **Proporciona** el código de reserva al cliente

## Reglas Importantes
- Sé **conversacional** y natural
- **Una pregunta a la vez** para no abrumar
- **Brevedad**: Máximo 3-4 oraciones por respuesta
- **Confirma** todos los datos antes de llamar a create_booking
- Si el cliente da múltiples datos juntos, úsalos todos
- **NO inventes** códigos de reserva, solo usa el que retorna create_booking

## Ejemplos

**Usuario:** "Quiero reservar"
**Tú:** "¡Perfecto! ¿Qué servicio deseas reservar?"

**Usuario:** "Corte de cabello para mañana"
**Tú:** Llamas check_availability("corte", "2026-01-28")
Luego: "Tenemos disponibilidad mañana. ¿A qué hora te gustaría?"

**Usuario:** "A las 3pm, soy Juan 987654321"
**Tú:** "Perfecto Juan. Confirmo tu reserva de corte para mañana a las 3pm?"

**Usuario:** "Sí"
**Tú:** Llamas create_booking("corte", "2026-01-28", "03:00 PM", "Juan", "987654321", session_id)
Luego proporcionas el código que retornó la herramienta"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{{input}}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])
    
    return prompt


def _format_history_for_agent(history: list) -> list:
    """
    Convierte el historial de memoria a formato de mensajes de LangChain.
    
    Args:
        history: Lista de turnos de conversación
    
    Returns:
        Lista de mensajes (HumanMessage, AIMessage)
    """
    messages = []
    for turn in history:
        messages.append(HumanMessage(content=turn["user"]))
        messages.append(AIMessage(content=turn["response"]))
    return messages


def _extract_data_from_history_OLD(history: list, current_message: str) -> Dict[str, Optional[str]]:
    """
    Extrae datos de reserva del historial de conversación.
    Mejorado para entender fechas naturales y más formatos.
    
    Returns:
        Dict con: servicio, fecha, hora, nombre, contacto, sucursal
    """
    # Combinar todo el historial en un texto
    all_text = ""
    for turn in history:
        all_text += f"{turn['user']} {turn['response']} "
    all_text += current_message
    
    datos = {
        "servicio": None,
        "fecha": None,
        "hora": None,
        "nombre": None,
        "contacto": None,
        "sucursal": None
    }
    
    # ===== FECHA MEJORADA =====
    # 1. Buscar formato ISO (YYYY-MM-DD)
    fecha_match = re.search(r'\d{4}-\d{2}-\d{2}', all_text)
    if fecha_match:
        datos["fecha"] = fecha_match.group(0)
    # 2. Buscar fechas naturales con dateparser (si está disponible)
    elif parse_date:
        palabras_fecha = ["mañana", "hoy", "pasado", "próximo", "siguiente", "lunes", "martes", 
                         "miércoles", "jueves", "viernes", "sábado", "domingo"]
        for palabra in palabras_fecha:
            if palabra in all_text.lower():
                # Extraer contexto alrededor de la palabra
                idx = all_text.lower().find(palabra)
                contexto = all_text[max(0, idx-10):min(len(all_text), idx+30)]
                fecha_parsed = parse_date(contexto, languages=['es'], settings={'PREFER_DATES_FROM': 'future'})
                if fecha_parsed:
                    datos["fecha"] = fecha_parsed.strftime("%Y-%m-%d")
                    break
    
    # ===== HORA MEJORADA =====
    # Buscar múltiples formatos de hora
    hora_patterns = [
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',  # 3:00 PM
        r'(\d{1,2}\s*(?:AM|PM|am|pm))',         # 3 PM
        r'(?:a\s+las|las)\s+(\d{1,2})(?::(\d{2}))?',  # "a las 3" o "las 3:30"
    ]
    
    for pattern in hora_patterns:
        hora_match = re.search(pattern, all_text, re.IGNORECASE)
        if hora_match:
            if pattern == hora_patterns[2]:  # Caso "a las 3"
                hora_num = hora_match.group(1)
                minutos = hora_match.group(2) or "00"
                # Asumir PM si es hora de servicio típica (9-20)
                hora_int = int(hora_num)
                if hora_int < 8:  # Probablemente PM
                    periodo = "PM"
                elif hora_int >= 12:
                    periodo = "PM" if hora_int < 24 else "AM"
                else:
                    periodo = "AM"
                datos["hora"] = f"{hora_num}:{minutos} {periodo}"
            else:
                hora_str = hora_match.group(1)
                # Normalizar formato
                if ':' not in hora_str and any(x in hora_str.upper() for x in ['AM', 'PM']):
                    hora_str = hora_str.replace('AM', ':00 AM').replace('PM', ':00 PM')
                    hora_str = hora_str.replace('am', ':00 AM').replace('pm', ':00 PM')
                datos["hora"] = hora_str.strip()
            break
    
    # ===== NOMBRE MEJORADO =====
    # Buscar después de palabras clave
    nombre_patterns = [
        r'(?:me llamo|mi nombre es|soy)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
        r'nombre[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
    ]
    for pattern in nombre_patterns:
        nombre_match = re.search(pattern, all_text, re.IGNORECASE)
        if nombre_match:
            nombre = nombre_match.group(1).strip()
            if len(nombre) > 2:  # Evitar nombres muy cortos
                datos["nombre"] = nombre
                break
    
    # ===== TELÉFONO MEJORADO (validado) =====
    telefono_match = re.search(r'9\d{8}', all_text)
    if telefono_match:
        telefono = telefono_match.group(0)
        # Validar que sea válido (9 dígitos empezando con 9)
        if len(telefono) == 9 and telefono[0] == '9':
            datos["contacto"] = telefono
    
    # ===== EMAIL MEJORADO (validado) =====
    if not datos["contacto"]:  # Solo si no hay teléfono
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', all_text)
        if email_match:
            email = email_match.group(0)
            # Validación básica
            if '@' in email and '.' in email.split('@')[1]:
                datos["contacto"] = email
    
    # ===== SERVICIO MEJORADO =====
    servicio_patterns = [
        r'(?:servicio|reservar)\s+(?:de|para)?\s*([a-záéíóúñ\s]+?)(?:\.|,|para|el|en|$)',
        r'(?:quiero|necesito)\s+(?:un|una)?\s*([a-záéíóúñ\s]+?)(?:\.|,|para|el|en|$)',
    ]
    for pattern in servicio_patterns:
        servicio_match = re.search(pattern, all_text, re.IGNORECASE)
        if servicio_match:
            servicio = servicio_match.group(1).strip()
            # Filtrar palabras no deseadas
            palabras_filtrar = ['reservar', 'quiero', 'necesito', 'turno', 'cita']
            servicio_limpio = ' '.join([
                palabra for palabra in servicio.split() 
                if palabra.lower() not in palabras_filtrar
            ])
            if len(servicio_limpio) > 3:  # Evitar palabras muy cortas
                datos["servicio"] = servicio_limpio.title()
                break
    
    # ===== SUCURSAL =====
    sucursal_match = re.search(r'sucursal\s+([a-záéíóúñ]+)', all_text, re.IGNORECASE)
    if sucursal_match:
        datos["sucursal"] = sucursal_match.group(1).capitalize()
    
    return datos


def _detect_confirmation_OLD(response_text: str) -> bool:
    """
    Detecta si la respuesta del LLM indica una confirmación de reserva.
    
    Busca palabras clave como "confirmada", "reserva exitosa", etc.
    """
    keywords = [
        "reserva confirmada",
        "confirmado exitosamente",
        "ha sido confirmada",
        "reserva exitosa",
        "agendado correctamente",
        "todo listo",
        "confirmación exitosa"
    ]
    
    response_lower = response_text.lower()
    return any(keyword in response_lower for keyword in keywords)


def _get_llm() -> ChatOpenAI:
    """Lazy init del LLM (OpenAI) con configuración centralizada."""
    global _llm
    if _llm is None:
        key = app_config.OPENAI_API_KEY
        if not key:
            raise ValueError("OPENAI_API_KEY no configurada")
        
        logger.info(f"[LLM] Inicializando ChatOpenAI - Model: {app_config.OPENAI_MODEL}, Timeout: {app_config.OPENAI_TIMEOUT}s")
        
        _llm = ChatOpenAI(
            api_key=key,
            model=app_config.OPENAI_MODEL,
            temperature=0.7,  # Más creativo que el orquestador
            max_tokens=app_config.MAX_TOKENS,
            request_timeout=app_config.OPENAI_TIMEOUT,
        )
    return _llm


def _get_agent_executor(context: Dict[str, Any]) -> AgentExecutor:
    """
    Lazy init del Agent Executor con tools.
    
    Args:
        context: Contexto con configuración del bot
    
    Returns:
        AgentExecutor configurado con tools
    """
    global _agent_executor
    
    # Recrear agent cada vez para tener personalidad actualizada
    # (en producción, podrías cachear por personalidad)
    llm = _get_llm()
    
    # Extraer config
    reserva_config = ReservaConfig(**context.get("config", {}))
    personalidad = reserva_config.personalidad or "amable, profesional y eficiente"
    
    # Construir prompt
    prompt = _build_agent_prompt(personalidad)
    
    # Crear agente con tools
    agent = create_openai_functions_agent(
        llm=llm,
        tools=AGENT_TOOLS,
        prompt=prompt
    )
    
    # Crear executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=AGENT_TOOLS,
        verbose=True,  # Para debug
        handle_parsing_errors=True,
        max_iterations=5,  # Máximo 5 iteraciones de tool calling
        return_intermediate_steps=False
    )
    
    return agent_executor


async def process_reserva_message(
    message: str,
    session_id: str,
    context: Dict[str, Any]
) -> str:
    """
    Procesa un mensaje del cliente sobre reservas usando LangChain Agent.
    
    El agente tiene acceso a tools internas:
    - check_availability: Consulta horarios disponibles
    - create_booking: Crea reserva con validación real
    
    Args:
        message: Mensaje del cliente
        session_id: ID de sesión para tracking
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
    
    # 1. CARGAR HISTORIAL de esta sesión
    history = get_history(session_id, limit=4)
    logger.debug(f"[AGENT] Historial cargado: {len(history)} turnos")
    
    # Formatear historial para el agente
    chat_history = _format_history_for_agent(history)
    
    # 2. OBTENER AGENT EXECUTOR
    try:
        agent_executor = _get_agent_executor(context)
    except Exception as e:
        logger.error(f"[AGENT] Error creando agent: {e}", exc_info=True)
        record_chat_error("agent_creation_error")
        return "Disculpa, tuve un problema de configuración. ¿Podrías intentar nuevamente?"
    
    # 3. PREPARAR INPUT para el agent
    # Inyectar parámetros de contexto que las tools necesitarán
    
    # Extraer config del contexto (viene del orquestador)
    config_data = context.get("config", {})
    
    agent_input = {
        "input": message,
        "chat_history": chat_history,
        # Pasar contexto a las tools a través de config
        "id_empresa": config_data.get("id_empresa", 1),
        "duracion_cita_minutos": config_data.get("duracion_cita_minutos", 60),
        "slots": config_data.get("slots", 60),
        "id_usuario": config_data.get("agendar_usuario", 1),
        "session_id": session_id
    }
    
    # 4. EJECUTAR AGENT
    try:
        logger.info(f"[AGENT] Invocando agent con input: {message[:100]}...")
        
        with track_chat_response():
            with track_llm_call():
                result = await agent_executor.ainvoke(agent_input)
        
        response_text = result["output"]
        logger.info(f"[AGENT] ✅ Respuesta generada: {response_text[:200]}...")
    
    except Exception as e:
        logger.error(f"[AGENT] ❌ Error al ejecutar agent: {e}", exc_info=True)
        record_chat_error("agent_execution_error")
        return "Disculpa, tuve un problema al procesar tu mensaje. ¿Podrías intentar nuevamente?"
    
    # 5. GUARDAR en memoria
    add_turn(session_id, message, response_text)
    
    return response_text
