"""
Sucursales públicas: fetch desde API MaravIA y formateo para system prompt.
Misma API que agente_cliente (OBTENER_SUCURSALES_PUBLICAS).
"""

import json
import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

try:
    from ..config import config as app_config
except ImportError:
    from reservas.config import config as app_config

_DIAS = [
    ("Lunes", "horario_lunes"),
    ("Martes", "horario_martes"),
    ("Miércoles", "horario_miercoles"),
    ("Jueves", "horario_jueves"),
    ("Viernes", "horario_viernes"),
    ("Sábado", "horario_sabado"),
    ("Domingo", "horario_domingo"),
]


def format_sucursales_for_system_prompt(sucursales: List[Dict[str, Any]]) -> str:
    """
    Formatea la lista de sucursales para inyectar en el system prompt.
    Estructura clara: ## Sucursales, ### Sucursal N, Dirección, Ubicación (mapa), Horarios L-D.

    Args:
        sucursales: Lista con nombre, direccion, enlace_ubicacion, horario_lunes..horario_domingo.

    Returns:
        String listo para pegar en el system prompt.
    """
    if not sucursales:
        return "No hay sucursales disponibles."

    lineas = [
        "## Sucursales disponibles",
        "",
        "Usa esta información para responder sobre ubicaciones, direcciones y horarios. Incluye el enlace de ubicación cuando lo indiques.",
        "",
    ]
    for i, sucursal in enumerate(sucursales, 1):
        nombre = sucursal.get("nombre", "Sin nombre")
        direccion = sucursal.get("direccion", "Sin dirección")
        enlace = sucursal.get("enlace_ubicacion", "")
        lineas.append(f"### Sucursal {i}: {nombre}")
        lineas.append(f"- **Dirección:** {direccion}")
        if enlace:
            lineas.append(f"- **Ubicación (mapa):** {enlace}")
        lineas.append("- **Horarios:**")
        for dia_nombre, dia_key in _DIAS:
            horario = sucursal.get(dia_key, "")
            if horario:
                lineas.append(f"  - {dia_nombre}: {horario}")
        lineas.append("")
    return "\n".join(lineas).strip()


def fetch_sucursales_publicas(id_empresa: Optional[Any]) -> str:
    """
    Obtiene sucursales públicas desde la API y las devuelve formateadas para el system prompt.

    Args:
        id_empresa: ID de la empresa (int o str). Si es None, retorna mensaje por defecto.

    Returns:
        String formateado para el prompt o "No hay sucursales cargadas." si falla.
    """
    if id_empresa is None or id_empresa == "":
        return "No hay sucursales cargadas."

    payload_sucursales = {
        "codOpe": "OBTENER_SUCURSALES_PUBLICAS",
        "id_empresa": id_empresa,
    }
    logger.debug("[SUCURSALES] JSON enviado a ws_informacion_ia.php (OBTENER_SUCURSALES_PUBLICAS): %s", json.dumps(payload_sucursales, ensure_ascii=False, indent=2))
    try:
        response = requests.post(
            app_config.API_INFORMACION_URL,
            json=payload_sucursales,
            timeout=app_config.API_TIMEOUT,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            logger.warning("API sucursales no success: %s", data.get("error"))
            return "No hay sucursales cargadas."
        sucursales = data.get("sucursales", [])
        if not sucursales:
            return "No hay sucursales cargadas."
        return format_sucursales_for_system_prompt(sucursales)
    except requests.exceptions.Timeout:
        logger.warning("Timeout al obtener sucursales para system prompt")
        return "No hay sucursales cargadas."
    except requests.exceptions.RequestException as e:
        logger.warning("Error al obtener sucursales para system prompt: %s", e)
        return "No hay sucursales cargadas."
