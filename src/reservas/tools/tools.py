"""
Tools internas del agente de reservas.
Estas tools son usadas por el LLM a través de function calling,
NO están expuestas directamente al orquestador.

Versión mejorada con logging, métricas, validación y runtime context (LangChain 1.2+).
"""

from typing import Any, Dict, Optional
from langchain.tools import tool, ToolRuntime

try:
    from ..services.schedule_validator import ScheduleValidator
    from ..services.booking import confirm_booking
    from ..logger import get_logger
    from ..metrics import track_tool_execution
    from ..validation import validate_booking_data
except ImportError:
    from reservas.services.schedule_validator import ScheduleValidator
    from reservas.services.booking import confirm_booking
    from reservas.logger import get_logger
    from reservas.metrics import track_tool_execution
    from reservas.validation import validate_booking_data

logger = get_logger(__name__)


@tool
async def check_availability(
    service: str,
    date: str,
    time: Optional[str] = None,
    duracion: int = 1,
    runtime: ToolRuntime = None
) -> str:
    """
    Consulta horarios disponibles para un servicio y fecha (y opcionalmente hora de inicio).
    La duración siempre va en HORAS (tipo 1 = horas que el cliente quiere, tipo 2 = duración del paquete, ej. 3).
    La tool calcula fecha_fin = fecha_inicio + duracion para las APIs.

    Usa esta herramienta cuando el cliente pregunte por disponibilidad
    o cuando necesites verificar si una fecha/hora específica está libre.

    Si el cliente indicó una hora concreta (hora de inicio), pásala en time
    para consultar disponibilidad exacta de ese slot (CONSULTAR_DISPONIBILIDAD).
    Si no pasas time, se devuelven sugerencias para hoy/mañana (SUGERIR_HORARIOS).

    Args:
        service: Nombre del servicio (uno de la lista inyectada en el prompt)
        date: Fecha en formato YYYY-MM-DD
        time: Hora de INICIO opcional en formato HH:MM AM/PM. Si el cliente dijo una hora, pásala aquí.
        duracion: Duración en HORAS (entero; tipo 1 = horas que eligió el cliente; tipo 2 = duración del paquete, ej. 3). Default 1.
        runtime: Runtime context automático (inyectado por LangChain)

    Returns:
        Texto con horarios disponibles o sugerencias
    """
    logger.debug(f"[TOOL] check_availability - Servicio: {service}, Fecha: {date}, Hora: {time or 'no indicada'}, Duracion: {duracion}h")
    
    # Obtener configuración del runtime context
    ctx = runtime.context if runtime else None
    id_empresa = ctx.id_empresa if ctx else 1
    duracion_cita_minutos = (duracion * 60) if duracion else 60
    slots = ctx.slots if ctx else 60
    agendar_usuario = ctx.agendar_usuario if ctx else 1
    agendar_sucursal = ctx.agendar_sucursal if ctx else 0

    try:
        with track_tool_execution("check_availability"):
            validator = ScheduleValidator(
                id_empresa=id_empresa,
                duracion_cita_minutos=duracion_cita_minutos,
                slots=slots,
                es_reservacion=True,
                agendar_usuario=agendar_usuario,
                agendar_sucursal=agendar_sucursal
            )
            
            recommendations = await validator.recommendation(
                fecha_solicitada=date,
                hora_solicitada=time.strip() if time and time.strip() else None,
                duracion_horas=duracion,
            )
            
            if recommendations and recommendations.get("text"):
                logger.debug(f"[TOOL] check_availability - Recomendaciones obtenidas")
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
    duracion: int,
    customer_name: str,
    customer_contact: str,
    sucursal: str,
    runtime: ToolRuntime = None
) -> str:
    """
    Crea una nueva reserva en el sistema con validación y confirmación real.
    time es la HORA DE INICIO; duracion es la duración en HORAS (tipo 1 = horas que eligió el cliente, tipo 2 = duración del paquete, ej. 3).
    La tool calcula fecha_fin = fecha_inicio + duracion para las APIs.

    Usa esta herramienta SOLO cuando tengas TODOS los datos necesarios:
    - Servicio, Fecha, Hora (inicio), Duración (horas), Nombre, Teléfono, Sucursal (incluir siempre).

    Args:
        service: Servicio reservado (nombre exacto de la lista)
        date: Fecha de la reserva (YYYY-MM-DD)
        time: Hora de INICIO (HH:MM AM/PM)
        duracion: Duración en HORAS (entero; tipo 1 = horas que dijo el cliente; tipo 2 = duración del paquete, ej. 3)
        customer_name: Nombre completo del cliente
        customer_contact: Teléfono del cliente (9 dígitos)
        sucursal: Nombre exacto de la sucursal de la lista o "No hay sucursal" si no hay sucursales. Incluir siempre este parámetro.
        runtime: Runtime context automático (inyectado por LangChain)

    Returns:
        Mensaje de confirmación o error
    """
    logger.debug(f"[TOOL] create_booking - {service} | {date} {time} | duracion={duracion}h | {customer_name}")
    
    ctx = runtime.context if runtime else None
    id_empresa = ctx.id_empresa if ctx else 1
    duracion_cita_minutos = (duracion * 60) if duracion else 60
    slots = ctx.slots if ctx else 60
    agendar_usuario = ctx.agendar_usuario if ctx else 1
    agendar_sucursal = ctx.agendar_sucursal if ctx else 0
    id_prospecto = ctx.id_prospecto if ctx else 0

    try:
        with track_tool_execution("create_booking"):
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
            
            logger.debug("[TOOL] create_booking - Validando horario")
            validator = ScheduleValidator(
                id_empresa=id_empresa,
                duracion_cita_minutos=duracion_cita_minutos,
                slots=slots,
                es_reservacion=True,
                agendar_usuario=agendar_usuario,
                agendar_sucursal=agendar_sucursal
            )
            
            validation = await validator.validate(date, time, duracion_horas=duracion)
            logger.debug(f"[TOOL] create_booking - Validación: {validation}")
            
            if not validation["valid"]:
                logger.warning(f"[TOOL] create_booking - Horario no válido: {validation['error']}")
                return f"{validation['error']}\n\nPor favor elige otra fecha u hora."
            
            logger.debug("[TOOL] create_booking - Confirmando en API")
            id_prospecto_val = id_prospecto or (ctx.session_id if ctx else 0)
            booking_result = await confirm_booking(
                id_empresa=id_empresa,
                id_prospecto=id_prospecto_val,
                nombre_completo=customer_name,
                correo_o_telefono=customer_contact,
                fecha=date,
                hora=time,
                servicio=service,
                agendar_usuario=agendar_usuario,
                agendar_sucursal=agendar_sucursal,
                duracion_horas=duracion,
                sucursal=(sucursal.strip() or "No hay sucursal"),
            )
            
            logger.debug(f"[TOOL] create_booking - Resultado: {booking_result}")
            
            if booking_result["success"]:
                api_message = booking_result.get("message") or "Reserva confirmada exitosamente"
                logger.info(f"[TOOL] create_booking - Éxito")
                return f"""{api_message}

Detalles:
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
