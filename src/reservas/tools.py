"""
Tools internas del agente de reservas.
Estas tools son usadas por el LLM a través de function calling,
NO están expuestas directamente al orquestador.

Versión mejorada con logging, métricas, validación y runtime context (LangChain 1.2+).
"""

from typing import Any, Dict, Optional
from langchain.tools import tool, ToolRuntime

try:
    from .schedule_validator import ScheduleValidator
    from .booking import confirm_booking
    from .logger import get_logger
    from .metrics import track_tool_execution
    from .validation import validate_booking_data
except ImportError:
    from schedule_validator import ScheduleValidator
    from booking import confirm_booking
    from logger import get_logger
    from metrics import track_tool_execution
    from validation import validate_booking_data

logger = get_logger(__name__)


@tool
async def check_availability(
    service: str,
    date: str,
    time: Optional[str] = None,
    runtime: ToolRuntime = None
) -> str:
    """
    Consulta horarios disponibles para un servicio y fecha (y opcionalmente hora).
    
    Usa esta herramienta cuando el cliente pregunte por disponibilidad
    o cuando necesites verificar si una fecha/hora específica está libre.
    
    Si el cliente indicó una hora concreta (ej. "a las 2pm", "a las 14:00"), pásala en time
    para consultar disponibilidad exacta de ese slot (se usa CONSULTAR_DISPONIBILIDAD).
    Si no pasas time, se devuelven sugerencias para hoy/mañana (SUGERIR_HORARIOS).
    
    Args:
        service: Nombre del servicio (ej: "corte", "manicure", "consulta")
        date: Fecha en formato ISO (YYYY-MM-DD)
        time: Hora opcional en formato HH:MM AM/PM (ej. "2:00 PM") o 24h. Si el cliente dijo una hora concreta, pásala aquí.
        runtime: Runtime context automático (inyectado por LangChain)
    
    Returns:
        Texto con horarios disponibles o sugerencias
    
    Examples:
        >>> await check_availability("corte", "2026-01-27")
        "Horarios sugeridos: Lunes 27/01 - 09:00 AM, 10:00 AM, 02:00 PM..."
        >>> await check_availability("espacio para jugar", "2026-01-31", "2:00 PM")
        "El 2026-01-31 a las 2:00 PM está disponible. ¿Confirmamos la reserva?"
    """
    logger.info(f"[TOOL] check_availability - Servicio: {service}, Fecha: {date}, Hora: {time or 'no indicada'}")
    
    # Obtener configuración del runtime context
    ctx = runtime.context if runtime else None
    id_empresa = ctx.id_empresa if ctx else 1
    duracion_cita_minutos = ctx.duracion_cita_minutos if ctx else 60
    slots = ctx.slots if ctx else 60
    id_usuario = ctx.id_usuario if ctx else 1
    agendar_sucursal = ctx.agendar_sucursal if ctx else 0

    try:
        with track_tool_execution("check_availability"):
            # Crear validator con configuración
            validator = ScheduleValidator(
                id_empresa=id_empresa,
                duracion_cita_minutos=duracion_cita_minutos,
                slots=slots,
                es_reservacion=True,
                agendar_usuario=id_usuario,
                agendar_sucursal=agendar_sucursal
            )
            
            # Obtener recomendaciones. Si viene time, se consulta CONSULTAR_DISPONIBILIDAD para ese slot primero.
            recommendations = await validator.recommendation(
                fecha_solicitada=date,
                hora_solicitada=time.strip() if time and time.strip() else None,
            )
            
            if recommendations and recommendations.get("text"):
                logger.info(f"[TOOL] check_availability - Recomendaciones obtenidas")
                return recommendations["text"]
            else:
                logger.warning(f"[TOOL] check_availability - Sin recomendaciones, usando fallback")
                return f"Horarios disponibles para {service} el {date}. Consulta directamente para más detalles."
    
    except Exception as e:
        logger.error(f"[TOOL] check_availability - Error: {e}", exc_info=True)
        # Fallback a respuesta genérica
        return f"Horarios típicos disponibles:\n• Mañana: 09:00, 10:00, 11:00\n• Tarde: 14:00, 15:00, 16:00"


@tool
async def create_booking(
    service: str,
    date: str,
    time: str,
    customer_name: str,
    customer_contact: str,
    sucursal: Optional[str] = None,
    runtime: ToolRuntime = None
) -> str:
    """
    Crea una nueva reserva en el sistema con validación y confirmación real.
    
    Usa esta herramienta SOLO cuando tengas TODOS los datos necesarios:
    - Servicio
    - Fecha (formato YYYY-MM-DD)
    - Hora (formato HH:MM AM/PM)
    - Nombre del cliente
    - Teléfono del cliente
    - Sucursal: si hay una sola en la lista, pásala; si hay varias, usa la que el cliente eligió (nombre exacto de la lista).
    
    La herramienta validará el horario y creará la reserva en el sistema real.
    
    Args:
        service: Servicio reservado (ej: "Corte de cabello")
        date: Fecha de la reserva (YYYY-MM-DD)
        time: Hora de la reserva (HH:MM AM/PM)
        customer_name: Nombre completo del cliente
        customer_contact: Teléfono del cliente (9 dígitos, ej. 987654321)
        sucursal: Nombre de la sucursal (exactamente como en la lista inyectada). Una sola sucursal: úsala; varias: la que el cliente eligió.
        runtime: Runtime context automático (inyectado por LangChain)
    
    Returns:
        Mensaje de confirmación con código de reserva o mensaje de error
    
    Examples:
        >>> await create_booking("Corte", "2026-01-27", "02:00 PM", "Juan Pérez", "987654321", "Miraflores")
        "Reserva confirmada exitosamente. Código: RES-12345"
    """
    logger.info(f"[TOOL] create_booking - {service} | {date} {time} | {customer_name}")
    
    # Obtener configuración del runtime context
    ctx = runtime.context if runtime else None
    id_empresa = ctx.id_empresa if ctx else 1
    duracion_cita_minutos = ctx.duracion_cita_minutos if ctx else 60
    slots = ctx.slots if ctx else 60
    id_usuario = ctx.id_usuario if ctx else 1
    agendar_sucursal = ctx.agendar_sucursal if ctx else 0
    id_prospecto = ctx.id_prospecto if ctx else ""

    try:
        with track_tool_execution("create_booking"):
            # 1. VALIDAR datos de entrada
            logger.debug("[TOOL] create_booking - Validando datos de entrada")
            is_valid, error = validate_booking_data(
                service=service,
                date=date,
                time=time,
                customer_name=customer_name,
                customer_contact=customer_contact
            )
            
            if not is_valid:
                logger.warning(f"[TOOL] create_booking - Datos inválidos: {error}")
                return f"Datos inválidos: {error}\n\nPor favor verifica la información."
            
            # 2. VALIDAR horario con ScheduleValidator
            logger.debug("[TOOL] create_booking - Validando horario")
            validator = ScheduleValidator(
                id_empresa=id_empresa,
                duracion_cita_minutos=duracion_cita_minutos,
                slots=slots,
                es_reservacion=True,
                agendar_usuario=id_usuario,
                agendar_sucursal=agendar_sucursal
            )
            
            validation = await validator.validate(date, time)
            logger.debug(f"[TOOL] create_booking - Validación: {validation}")
            
            if not validation["valid"]:
                # Horario no válido, retornar error
                logger.warning(f"[TOOL] create_booking - Horario no válido: {validation['error']}")
                return f"{validation['error']}\n\nPor favor elige otra fecha u hora."
            
            # 3. CONFIRMAR booking en endpoint real (payload doc: titulo, fecha_inicio, fecha_fin, agendar_*)
            logger.debug("[TOOL] create_booking - Confirmando en API")
            id_prospecto_val = id_prospecto or (str(ctx.session_id) if ctx else "")
            booking_result = await confirm_booking(
                id_empresa=id_empresa,
                id_prospecto=id_prospecto_val,
                nombre_completo=customer_name,
                correo_o_telefono=customer_contact,
                fecha=date,
                hora=time,
                servicio=service,
                agendar_usuario=id_usuario,
                agendar_sucursal=agendar_sucursal,
                duracion_cita_minutos=duracion_cita_minutos,
                sucursal=sucursal.strip() if sucursal and sucursal.strip() else None,
            )
            
            logger.debug(f"[TOOL] create_booking - Resultado: {booking_result}")
            
            if booking_result["success"]:
                api_message = booking_result.get("message") or "Reserva confirmada exitosamente"
                logger.info(f"[TOOL] create_booking - Éxito")
                return f"""{api_message}

**Detalles:**
• Servicio: {service}
• Fecha: {date}
• Hora: {time}
• Nombre: {customer_name}

¡Te esperamos!"""
            else:
                error_msg = booking_result.get("error") or booking_result.get("message") or "No se pudo confirmar la reserva"
                logger.warning(f"[TOOL] create_booking - Fallo: {error_msg}")
                return f"{error_msg}\n\nPor favor intenta nuevamente."
    
    except Exception as e:
        logger.error(f"[TOOL] create_booking - Error inesperado: {e}", exc_info=True)
        return f"Error inesperado al crear la reserva: {str(e)}\n\nPor favor intenta nuevamente."


# Lista de todas las tools disponibles para el agente
AGENT_TOOLS = [
    check_availability,
    create_booking
]

__all__ = ["check_availability", "create_booking", "AGENT_TOOLS"]
