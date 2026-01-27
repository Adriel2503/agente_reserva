"""
Prompts del agente de reservas. Builder del system prompt.
"""

from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parent
_DEFAULTS: Dict[str, Any] = {
    "personalidad": "amable, profesional y eficiente",
}


def _apply_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica valores por defecto a la configuración."""
    out = dict(_DEFAULTS)
    for k, v in config.items():
        if v is not None and v != "" and v != []:
            out[k] = v
    return out


def build_reserva_system_prompt(
    config: Dict[str, Any],
    history: List[Dict] = None
) -> str:
    """
    Construye el system prompt del agente de reservas.
    
    Args:
        config: Diccionario con nombre_negocio, servicios, horarios, etc.
                Puede venir de ReservaConfig.model_dump() o similar.
        history: Lista de turnos previos [{"user": "...", "response": "..."}]
    
    Returns:
        System prompt formateado con historial.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(disabled_extensions=()),
    )
    template = env.get_template("reserva_system.j2")
    
    variables = _apply_defaults(config)
    
    # Agregar historial
    variables["history"] = history or []
    variables["has_history"] = bool(history)
    
    return template.render(**variables)


__all__ = ["build_reserva_system_prompt"]
