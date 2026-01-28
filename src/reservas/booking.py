"""
Función para confirmar reserva en el endpoint real.
Versión mejorada con async httpx, logging y métricas.
"""

import httpx
from typing import Any, Dict

try:
    from .logger import get_logger
    from .metrics import track_api_call, record_booking_attempt, record_booking_success, record_booking_failure
    from . import config as app_config
except ImportError:
    from logger import get_logger
    from metrics import track_api_call, record_booking_attempt, record_booking_success, record_booking_failure
    import config as app_config

logger = get_logger(__name__)

AGENDAR_REUNIONES_ENDPOINT = "https://api.maravia.pe/servicio/n8n/ws_agendar_reunion.php"


async def confirm_booking(
    id_empresa: int,
    id_prospecto: str,
    nombre_completo: str,
    correo_o_telefono: str,
    fecha: str,
    hora: str,
    servicio: str,
    id_usuario: int,
    sucursal: str = None
) -> Dict[str, Any]:
    """
    Confirma una reserva en el endpoint real de MaravIA.
    
    Args:
        id_empresa: ID de la empresa
        id_prospecto: ID del prospecto/cliente
        nombre_completo: Nombre completo del cliente
        correo_o_telefono: Correo electrónico o teléfono del cliente
        fecha: Fecha en formato YYYY-MM-DD
        hora: Hora en formato HH:MM AM/PM
        servicio: Servicio/motivo de la reserva
        id_usuario: ID del usuario que agenda
        sucursal: (Opcional) Sucursal donde se realiza la reserva
    
    Returns:
        Dict con:
        - success: bool
        - codigo: str (código de reserva si success=True)
        - message: str (mensaje descriptivo)
        - error: str (si hubo error)
    """
    record_booking_attempt()
    
    try:
        payload = {
            "codOpe": "AGENDAR_REUNION",
            "id_empresa": id_empresa,
            "id_prospecto": id_prospecto,
            "nombre_completo": nombre_completo,
            "correo_electronico": correo_o_telefono,
            "fecha_cita": fecha,
            "hora_cita": hora,
            "servicio": servicio,
            "id_usuario": id_usuario
        }
        
        if sucursal:
            payload["sucursal"] = sucursal
        
        logger.info(f"[BOOKING] Confirmando reserva: {servicio} - {fecha} {hora} - {nombre_completo}")
        logger.debug(f"[BOOKING] Payload: {payload}")
        
        with track_api_call("agendar_reunion"):
            async with httpx.AsyncClient(timeout=app_config.API_TIMEOUT) as client:
                response = await client.post(
                    AGENDAR_REUNIONES_ENDPOINT,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                data = response.json()
        
        logger.debug(f"[BOOKING] Respuesta API: {data}")
        
        if data.get("success"):
            codigo = data.get("codigo_cita")
            if codigo:
                logger.info(f"[BOOKING] Reserva exitosa - Código: {codigo}")
                message = f"Reserva confirmada exitosamente. Código: {codigo}"
            else:
                logger.warning(f"[BOOKING] Reserva exitosa pero sin código de confirmación")
                message = "Reserva confirmada exitosamente"
            record_booking_success()
            
            return {
                "success": True,
                "codigo": codigo,
                "message": message,
                "error": None
            }
        else:
            error_msg = data.get("message", "Error desconocido")
            logger.warning(f"[BOOKING] Reserva fallida: {error_msg}")
            record_booking_failure("api_error")
            
            return {
                "success": False,
                "codigo": None,
                "message": "No se pudo confirmar la reserva",
                "error": error_msg
            }
    
    except httpx.TimeoutException:
        logger.error("[BOOKING] Timeout al confirmar reserva")
        record_booking_failure("timeout")
        return {
            "success": False,
            "codigo": None,
            "message": "La conexión tardó demasiado tiempo",
            "error": "timeout"
        }
    
    except httpx.HTTPStatusError as e:
        logger.error(f"[BOOKING] Error HTTP {e.response.status_code}: {e}")
        record_booking_failure(f"http_{e.response.status_code}")
        return {
            "success": False,
            "codigo": None,
            "message": f"Error del servidor ({e.response.status_code})",
            "error": str(e)
        }
    
    except httpx.RequestError as e:
        logger.error(f"[BOOKING] Error de conexión: {e}")
        record_booking_failure("connection_error")
        return {
            "success": False,
            "codigo": None,
            "message": "Error al conectar con el servidor",
            "error": str(e)
        }
    
    except Exception as e:
        logger.error(f"[BOOKING] Error inesperado: {e}", exc_info=True)
        record_booking_failure("unknown_error")
        return {
            "success": False,
            "codigo": None,
            "message": "Error inesperado al confirmar la reserva",
            "error": str(e)
        }


__all__ = ["confirm_booking"]
