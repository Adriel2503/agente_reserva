# Agent Reservas - MaravIA

Agente de IA conversacional especializado en gestión automatizada de reservas y turnos.

## Características

- **Procesamiento de lenguaje natural** con GPT-4o-mini/GPT-4o
- **Validación multicapa** de horarios (formato, disponibilidad, bloqueos)
- **Confirmación en tiempo real** con códigos de reserva
- **Memoria conversacional automática** (LangChain 1.2+ con InMemorySaver)
- **Observabilidad completa** (Prometheus metrics + logging centralizado)
- **Performance optimizado** (async/await + cache con TTL)

## Versión

**v2.0.0** - LangChain 1.2+ API Moderna

## Requisitos Previos

- Python 3.10 o superior
- OpenAI API Key
- Acceso a APIs MaravIA

## Inicio Rápido

### 1. Clonar e instalar

```bash
# Clonar repositorio
git clone <repository-url>
cd agent_reservas

# Crear entorno virtual
python -m venv venv_agent_reservas

# Activar entorno virtual
# Windows:
venv_agent_reservas\Scripts\activate
# Linux/Mac:
source venv_agent_reservas/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env con tus credenciales
# IMPORTANTE: Agregar tu OPENAI_API_KEY
```

### 3. Ejecutar servidor

```bash
python -m reservas.main
```

El servidor estará disponible en `http://localhost:8003`

## Variables de Entorno

| Variable | Requerido | Default | Descripción |
|----------|-----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ Sí | - | API Key de OpenAI |
| `OPENAI_MODEL` | ❌ No | `gpt-4o-mini` | Modelo de OpenAI a usar |
| `SERVER_HOST` | ❌ No | `0.0.0.0` | Host del servidor |
| `SERVER_PORT` | ❌ No | `8003` | Puerto del servidor |
| `LOG_LEVEL` | ❌ No | `INFO` | Nivel de logging (DEBUG\|INFO\|WARNING\|ERROR) |
| `LOG_FILE` | ❌ No | `""` | Archivo de log (vacío = solo stdout) |
| `OPENAI_TIMEOUT` | ❌ No | `90` | Timeout para llamadas a OpenAI (segundos) |
| `API_TIMEOUT` | ❌ No | `10` | Timeout para APIs externas (segundos) |
| `MAX_TOKENS` | ❌ No | `2048` | Máximo de tokens por respuesta |
| `SCHEDULE_CACHE_TTL_MINUTES` | ❌ No | `5` | Duración del cache de horarios (minutos) |

## Uso Básico

El agente se comunica mediante el protocolo MCP (Model Context Protocol). Expone una sola herramienta:

**Tool:** `chat`

**Parámetros:**
- `message` (string): Mensaje del usuario
- `session_id` (integer): ID único de sesión para memoria (int, no string)
- `context` (object): Configuración del agente
  - `context.config.id_empresa` (int, **requerido**): ID de la empresa
  - `context.config.personalidad` (string, opcional): Personalidad del agente
  - `context.config.agendar_usuario` (bool/int, opcional): Usuario que agenda (default: 1)
  - `context.config.agendar_sucursal` (bool/int, opcional): Agendar por sucursal (default: 0)
  - Otros parámetros opcionales (ver [API.md](docs/API.md))

**Ejemplo de request:**
```json
{
  "tool": "chat",
  "arguments": {
    "message": "Quiero reservar para mañana a las 2pm",
    "session_id": 12345,
    "context": {
      "config": {
        "id_empresa": 123,
        "personalidad": "amable y profesional",
        "agendar_usuario": 1,
        "agendar_sucursal": 0
      }
    }
  }
}
```

## Métricas

Métricas Prometheus disponibles en:
```
http://localhost:8003/metrics
```

Incluye:
- Latencia de respuestas
- Tasa de éxito/fallo de reservas
- Uso de cache
- Llamadas a APIs externas

## Documentación

- **[API Reference](docs/API.md)** - Referencia completa de la API
- **[Architecture](docs/ARCHITECTURE.md)** - Arquitectura y diseño del sistema
- **[Deployment](docs/DEPLOYMENT.md)** - Guía de despliegue

## Stack Tecnológico

- **LangChain 1.2+** - Framework de LLM con API moderna
- **LangGraph** - Gestión de memoria y grafos
- **OpenAI API** - Modelos GPT
- **FastMCP** - Servidor MCP sobre FastAPI
- **httpx** - Cliente HTTP async
- **Pydantic** - Validación de datos
- **Prometheus** - Métricas y observabilidad

## Arquitectura

```
ORQUESTADOR → MCP (HTTP) → Agent Reservas
                                ↓
                         LangChain Agent
                                ↓
                    ┌───────────┴───────────┐
                    ↓                       ↓
            check_availability      create_booking
                    ↓                       ↓
            (Valida horarios)      (Confirma reserva)
                    ↓                       ↓
                [APIs MaravIA]        [APIs MaravIA]
```

Ver [ARCHITECTURE.md](docs/ARCHITECTURE.md) para detalles completos.

## Desarrollo

### Estructura del proyecto

```
agent_reservas/
├── src/reservas/              # Código fuente
│   ├── main.py               # Servidor MCP (punto de entrada)
│   ├── validation.py         # Validadores Pydantic
│   ├── logger.py             # Sistema de logging
│   ├── metrics.py            # Métricas Prometheus
│   ├── agent/                # Lógica del agente
│   │   └── agent.py          # Agente LangChain con memoria
│   ├── tools/                # Herramientas del agente
│   │   └── tools.py          # check_availability, create_booking
│   ├── services/             # Servicios de negocio
│   │   ├── booking.py        # Confirmación de reservas (API)
│   │   ├── schedule_validator.py  # Validación de horarios
│   │   └── sucursales.py     # Gestión de sucursales
│   ├── config/               # Configuración
│   │   ├── config.py         # Variables de entorno
│   │   └── models.py         # Modelos Pydantic
│   └── prompts/              # Templates de prompts
│       ├── __init__.py       # Builder de prompts
│       └── reserva_system.j2 # Template Jinja2
├── docs/                     # Documentación
├── .env.example             # Ejemplo de configuración
└── requirements.txt         # Dependencias
```

### Ejecutar en modo DEBUG

```bash
LOG_LEVEL=DEBUG python -m reservas.main
```

## Mejoras Recientes (v2.0.0)

- ✅ Migración a LangChain 1.2+ API moderna
- ✅ Logging centralizado con formato consistente
- ✅ Performance async real con httpx (30x más rápido)
- ✅ Cache global con TTL thread-safe
- ✅ Validación de datos robusta con Pydantic
- ✅ Sistema completo de métricas Prometheus

Ver [MEJORAS_IMPLEMENTADAS.md](MEJORAS_IMPLEMENTADAS.md) para detalles.

## Limitaciones Conocidas

- **Memoria volátil**: Usa InMemorySaver (se pierde al reiniciar). Para producción con múltiples instancias, migrar a Redis o PostgreSQL.
- **Sin rate limiting**: Implementar antes de producción pública.
- **Sin tests automatizados**: En desarrollo.

## Licencia

Propiedad de MaravIA Team.

## Soporte

Para problemas o preguntas, contactar al equipo de desarrollo de MaravIA.
