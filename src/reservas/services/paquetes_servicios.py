"""
Productos/Servicios/Paquetes: fetch desde API MaravIA y formateo para system prompt.
Usa ws_informacion_ia.php con codOpe OBTENER_PRODUCTOS_SERVICIOS_PAQUETES.
Servicios tipo 1 (tipo_producto=Servicio): nombre, precio_unitario por unidad_medida, descripción.
Servicios tipo 2 (tipo_producto=Paquete): nombre, total (precio), cantidad + unidad_medida (duración), descripción.
"""

import json
import re
import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

try:
    from ..config import config as app_config
except ImportError:
    from reservas.config import config as app_config

_DEFAULT_LIMIT = 10


def _clean_description(desc: Optional[str]) -> str:
    """
    Limpia la descripción: quita etiquetas HTML y normaliza espacios.
    Si queda vacío o es null, retorna "-".
    """
    if desc is None or not str(desc).strip():
        return "-"
    text = str(desc).strip()
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else "-"


def _format_precio(precio: Any) -> str:
    """Formatea precio o retorna '-' si null/vacío."""
    if precio is None or precio == "":
        return "-"
    try:
        return f"S/. {float(precio):.2f}"
    except (TypeError, ValueError):
        return "-"


def _format_servicio_tipo1(p: Dict[str, Any]) -> List[str]:
    """Formatea un ítem tipo Servicio (tipo 1): Nombre, Precio (precio_unitario por unidad_medida), Descripción."""
    lineas = []
    nombre = (p.get("nombre") or "").strip()
    lineas.append(f"### {nombre if nombre else '-'}")
    precio_str = _format_precio(p.get("precio_unitario"))
    unidad = (p.get("unidad_medida") or "Hora").strip().lower()
    if precio_str != "-":
        lineas.append(f"- **Precio:** {precio_str} por {unidad}")
    else:
        lineas.append("- **Precio:** -")
    desc = _clean_description(p.get("descripcion"))
    lineas.append(f"- **Descripción:** {desc}")
    lineas.append("- **Tipo:** 1")
    lineas.append("")
    return lineas


def _format_duracion(cantidad: Any, unidad_medida: Any) -> str:
    """Construye texto de duración: cantidad + unidad (ej. 4 horas, 1 día, 2 días)."""
    try:
        n = int(float(cantidad)) if cantidad not in (None, "") else 0
    except (TypeError, ValueError):
        return "0 horas"
    u = (unidad_medida or "Hora").strip().lower()
    if n == 1:
        return f"1 {u}"
    # Plural común en español: hora→horas, día→días
    if u == "hora":
        return f"{n} horas"
    if u == "día":
        return f"{n} días"
    return f"{n} {u}s" if not u.endswith("s") else f"{n} {u}"


def _format_servicio_tipo2(p: Dict[str, Any]) -> List[str]:
    """Formatea un ítem tipo Paquete (tipo 2): Nombre, Duración (cantidad + unidad_medida), Precio (total), Descripción."""
    lineas = []
    nombre = (p.get("nombre") or "").strip()
    lineas.append(f"### {nombre if nombre else '-'}")
    duracion_txt = _format_duracion(p.get("cantidad"), p.get("unidad_medida"))
    lineas.append(f"- **Duración:** {duracion_txt}")
    precio_str = _format_precio(p.get("total"))
    lineas.append(f"- **Precio:** {precio_str}")
    desc = _clean_description(p.get("descripcion"))
    lineas.append(f"- **Descripción:** {desc}")
    lineas.append("- **Tipo:** 2")
    lineas.append("")
    return lineas


def format_servicios_for_system_prompt(productos: List[Dict[str, Any]]) -> str:
    """
    Formatea la lista de productos para el system prompt.
    Separa Servicios (tipo 1) y Paquetes (tipo 2). Solo incluye visible_publico == 1.
    Cualquier campo null/vacío se muestra como "-".
    """
    if not productos:
        return "No hay servicios cargados."

    servicios = [p for p in productos if p.get("visible_publico") == 1 and (p.get("tipo_producto") or "").strip().lower() == "servicio"]
    paquetes = [p for p in productos if p.get("visible_publico") == 1 and (p.get("tipo_producto") or "").strip().lower() == "paquete"]

    lineas = [
        "## Información de servicios y productos",
        "",
        "Usa los nombres exactos de la lista para el parámetro `service`. Hay dos tipos:",
        "- **Servicios tipo 1:** el cliente elige cuántas horas quiere. Cuando elija uno tipo 1, pregúntale: \"¿Cuántas horas deseas?\"",
        "- **Servicios tipo 2:** tienen duración fija. No preguntes cuántas horas.",
        "",
    ]

    lineas.append("## Servicios tipo 1")
    lineas.append("")
    if servicios:
        for p in servicios:
            lineas.extend(_format_servicio_tipo1(p))
    else:
        lineas.append("(No hay servicios tipo 1 cargados.)")
        lineas.append("")

    lineas.append("## Servicios tipo 2")
    lineas.append("")
    if paquetes:
        for p in paquetes:
            lineas.extend(_format_servicio_tipo2(p))
    else:
        lineas.append("(No hay servicios tipo 2 cargados.)")
        lineas.append("")

    return "\n".join(lineas).strip()


def fetch_servicios_paquetes(id_empresa: Optional[Any], limit: int = _DEFAULT_LIMIT) -> str:
    """
    Obtiene productos/servicios/paquetes desde la API y los devuelve formateados para el system prompt.

    Args:
        id_empresa: ID de la empresa (int o str). Si es None, retorna mensaje por defecto.
        limit: Cantidad máxima de ítems a solicitar (default 10).

    Returns:
        String formateado para el prompt o "No hay servicios cargados." si falla.
    """
    if id_empresa is None or id_empresa == "":
        return "No hay servicios cargados."

    payload = {
        "codOpe": "OBTENER_PRODUCTOS_SERVICIOS_PAQUETES",
        "id_empresa": id_empresa,
        "limit": limit,
    }
    logger.debug(
        "[SERVICIOS] JSON enviado a ws_informacion_ia.php (OBTENER_PRODUCTOS_SERVICIOS_PAQUETES): %s",
        json.dumps(payload, ensure_ascii=False),
    )
    try:
        response = requests.post(
            app_config.API_INFORMACION_URL,
            json=payload,
            timeout=app_config.API_TIMEOUT,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            logger.warning("API productos/servicios no success: %s", data.get("error"))
            return "No hay servicios cargados."
        productos = data.get("productos", [])
        if not productos:
            return "No hay servicios cargados."
        return format_servicios_for_system_prompt(productos)
    except requests.exceptions.Timeout:
        logger.warning("Timeout al obtener servicios para system prompt")
        return "No hay servicios cargados."
    except requests.exceptions.RequestException as e:
        logger.warning("Error al obtener servicios para system prompt: %s", e)
        return "No hay servicios cargados."
