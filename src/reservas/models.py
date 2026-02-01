"""
Modelos Pydantic para request/response del agente de reservas.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request para el endpoint de chat."""
    
    message: str = Field(..., description="Mensaje del cliente")
    session_id: int = Field(..., description="ID de sesión único (int, unificado con orquestador)")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Contexto adicional (configuración del bot, etc.)"
    )


class ChatResponse(BaseModel):
    """Response del endpoint de chat."""
    
    reply: str = Field(..., description="Respuesta del agente")
    session_id: int = Field(..., description="ID de sesión (int)")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata adicional (intent detectado, acción realizada, etc.)"
    )


class ReservaConfig(BaseModel):
    """Configuración mínima del agente de reservas."""
    
    personalidad: str = Field(
        default="amable, profesional y eficiente",
        description="Personalidad del agente"
    )
