"""
Sistema de memoria del agente de reservas.
Guarda historial de conversación por session_id.

Versión mejorada con logging y métricas.
"""

import threading
from typing import Dict, List
from datetime import datetime

try:
    from .logger import get_logger
    from .metrics import update_memory_stats
except ImportError:
    from logger import get_logger
    from metrics import update_memory_stats

logger = get_logger(__name__)

# Storage en memoria (dict simple - para MVP)
# NOTA: Con protección básica contra race conditions. Para producción migrar a Redis
_RESERVA_MEMORY: Dict[str, List[Dict]] = {}
_MEMORY_LOCK = threading.Lock()


def add_turn(session_id: str, user_message: str, response: str):
    """
    Agrega un turno a la memoria del agente de reservas.
    
    Args:
        session_id: ID de la sesión/usuario
        user_message: Mensaje del usuario
        response: Respuesta del agente
    """
    with _MEMORY_LOCK:
        if session_id not in _RESERVA_MEMORY:
            _RESERVA_MEMORY[session_id] = []
        
        _RESERVA_MEMORY[session_id].append({
            "user": user_message,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Mantener solo últimos 4 turnos
        _RESERVA_MEMORY[session_id] = _RESERVA_MEMORY[session_id][-4:]
        
        # Actualizar métricas
        total_sessions = len(_RESERVA_MEMORY)
        total_turns = sum(len(turns) for turns in _RESERVA_MEMORY.values())
        update_memory_stats(total_sessions, total_turns)
        
        logger.debug(f"[MEMORY] Guardado turno para {session_id}. Turnos: {len(_RESERVA_MEMORY[session_id])}")


def get_history(session_id: str, limit: int = 4) -> List[Dict]:
    """
    Obtiene los últimos N turnos de una sesión.
    
    Args:
        session_id: ID de la sesión/usuario
        limit: Cantidad máxima de turnos a retornar
    
    Returns:
        Lista de turnos (dict con user, response)
    """
    with _MEMORY_LOCK:
        history = _RESERVA_MEMORY.get(session_id, [])
        return history[-limit:]


def clear(session_id: str):
    """
    Limpia la memoria de una sesión.
    
    Args:
        session_id: ID de la sesión/usuario
    """
    with _MEMORY_LOCK:
        if session_id in _RESERVA_MEMORY:
            del _RESERVA_MEMORY[session_id]
            
            # Actualizar métricas
            total_sessions = len(_RESERVA_MEMORY)
            total_turns = sum(len(turns) for turns in _RESERVA_MEMORY.values())
            update_memory_stats(total_sessions, total_turns)
            
            logger.info(f"[MEMORY] Limpiada memoria de {session_id}")


def get_stats():
    """Retorna estadísticas de uso de memoria (debug)"""
    with _MEMORY_LOCK:
        return {
            "total_sessions": len(_RESERVA_MEMORY),
            "sessions": {
                session_id: len(turns)
                for session_id, turns in _RESERVA_MEMORY.items()
            }
        }


__all__ = ["add_turn", "get_history", "clear", "get_stats"]
