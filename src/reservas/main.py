"""
Servidor HTTP del agente especializado en reservas.
Usa FastAPI para exponer endpoints REST.

Versión 3.0.0 - Migrado de FastMCP a FastAPI puro.
"""

import logging
import uvicorn
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

try:
    from .config import config as app_config
    from .agent import process_reserva_message
    from .logger import setup_logging, get_logger
    from .metrics import initialize_agent_info
    from .config.models import ChatRequest, ChatResponse
except ImportError:
    from reservas.config import config as app_config
    from reservas.agent import process_reserva_message
    from reservas.logger import setup_logging, get_logger
    from reservas.metrics import initialize_agent_info
    from reservas.config.models import ChatRequest, ChatResponse

# Configurar logging antes de cualquier otra cosa
log_level = getattr(logging, app_config.LOG_LEVEL.upper(), logging.INFO)
setup_logging(
    level=log_level,
    log_file=app_config.LOG_FILE if app_config.LOG_FILE else None
)

logger = get_logger(__name__)

# Inicializar información del agente para métricas
initialize_agent_info(model=app_config.OPENAI_MODEL, version="3.0.0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("INICIANDO AGENTE RESERVAS - MaravIA")
    logger.info("=" * 60)
    logger.info(f"Host: {app_config.SERVER_HOST}:{app_config.SERVER_PORT}")
    logger.info(f"Modelo: {app_config.OPENAI_MODEL}")
    logger.info(f"Timeout LLM: {app_config.OPENAI_TIMEOUT}s")
    logger.info(f"Timeout API: {app_config.API_TIMEOUT}s")
    logger.info(f"Cache TTL: {app_config.SCHEDULE_CACHE_TTL_MINUTES} min")
    logger.info(f"Log Level: {app_config.LOG_LEVEL}")
    logger.info("-" * 60)
    logger.info("Endpoints disponibles:")
    logger.info("  POST /chat     (agente de reservas)")
    logger.info("  GET  /health   (healthcheck)")
    logger.info("  GET  /metrics  (Prometheus)")
    logger.info("=" * 60)
    yield
    logger.info("Servidor detenido.")


app = FastAPI(
    title="Agente Reservas - MaravIA",
    description="Agente conversacional especializado en gestión de reservas y turnos.",
    version="3.0.0",
    lifespan=lifespan,
)

# Montar métricas Prometheus en /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Endpoint principal del agente de reservas.

    Recibe el mensaje del cliente junto con la sesión y el contexto de configuración.
    El agente maneja la conversación completa de forma autónoma, usando tools internas
    para consultar disponibilidad y crear reservas.

    El campo `context.config.id_empresa` es obligatorio.
    """
    logger.info(f"[HTTP] POST /chat - Session: {request.session_id}, Length: {len(request.message)} chars")
    logger.debug(f"[HTTP] Message: {request.message[:100]}...")
    logger.debug(f"[HTTP] Context keys: {list(request.context.keys())}")

    try:
        reply = await process_reserva_message(
            message=request.message,
            session_id=request.session_id,
            context=request.context,
        )
        logger.info(f"[HTTP] Respuesta generada - Length: {len(reply)} chars")
        logger.debug(f"[HTTP] Reply: {reply[:200]}...")
        return ChatResponse(reply=reply, session_id=request.session_id)

    except ValueError as e:
        error_msg = f"Error de configuración: {str(e)}"
        logger.error(f"[HTTP] {error_msg}")
        return ChatResponse(reply=error_msg, session_id=request.session_id)

    except Exception as e:
        error_msg = f"Error procesando mensaje: {str(e)}"
        logger.error(f"[HTTP] {error_msg}", exc_info=True)
        return ChatResponse(reply=error_msg, session_id=request.session_id)


@app.get("/health")
async def health() -> JSONResponse:
    """Healthcheck para el gateway y orquestadores."""
    return JSONResponse(content={"status": "ok"})


if __name__ == "__main__":
    try:
        uvicorn.run(
            app,
            host=app_config.SERVER_HOST,
            port=app_config.SERVER_PORT,
        )
    except KeyboardInterrupt:
        logger.info("\nServidor detenido por el usuario")
    except Exception as e:
        logger.critical(f"Error crítico en el servidor: {e}", exc_info=True)
        raise
