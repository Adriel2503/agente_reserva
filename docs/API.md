# API Reference - Agent Reservas

Referencia de la API del agente especializado en reservas.

## Descripción General

El agente se comunica mediante **REST HTTP** (FastAPI). Expone un endpoint principal que maneja toda la lógica de conversación y reservas de forma autónoma.

**Protocolo**: HTTP REST
**Puerto**: 8003 (configurable)
**Base URL**: `http://localhost:8003`

---

## Endpoints

### POST /chat

Procesa mensajes del usuario y gestiona el flujo completo de reservas.

El agente internamente usa herramientas propias:
- `check_availability` - Consulta horarios disponibles
- `create_booking` - Crea reservas con validación
- `search_productos_servicios` - Busca en el catálogo de productos/servicios

**El gateway NO llama directamente a estas herramientas**, solo usa `/chat`.

---

## Request

```
POST /chat
Content-Type: application/json
```

```json
{
  "message": "Quiero reservar para mañana a las 2pm",
  "session_id": 12345,
  "context": {
    "config": {
      "id_empresa": 123,
      "personalidad": "amable y profesional",
      "duracion_cita_minutos": 60,
      "slots": 60,
      "agendar_usuario": 1,
      "agendar_sucursal": 0
    }
  }
}
```

### Parámetros del body

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `message` | string | ✅ Sí | Mensaje del usuario que quiere reservar |
| `session_id` | integer | ✅ Sí | ID único de sesión para memoria conversacional |
| `context` | object | ✅ Sí | Contexto de configuración |

### Parámetros de `context.config`

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `id_empresa` | integer | ✅ Sí | - | ID de la empresa en el sistema |
| `personalidad` | string | ❌ No | `"amable, profesional y eficiente"` | Personalidad del agente |
| `duracion_cita_minutos` | integer | ❌ No | `60` | Duración de la cita en minutos |
| `slots` | integer | ❌ No | `60` | Cantidad de slots disponibles |
| `agendar_usuario` | boolean/integer | ❌ No | `1` | Usuario que agenda (1=sí, 0=no) |
| `agendar_sucursal` | boolean/integer | ❌ No | `0` | Agendar por sucursal (1=sí, 0=no) |

---

## Response

```json
{
  "reply": "¡Perfecto! Para confirmar tu reserva necesito algunos datos. ¿Cuál es tu nombre completo?",
  "session_id": 12345,
  "metadata": null
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `reply` | string | Respuesta del agente en lenguaje natural |
| `session_id` | integer | Mismo `session_id` enviado en el request |
| `metadata` | object\|null | Datos adicionales (reservado para uso futuro) |

---

## Ejemplos de Uso

### Ejemplo 1: Inicio de conversación

**Request:**
```json
{
  "message": "Hola, quiero reservar",
  "session_id": 1001,
  "context": {
    "config": {
      "id_empresa": 123
    }
  }
}
```

**Response:**
```json
{
  "reply": "¡Hola! Estaré encantado de ayudarte con tu reserva. ¿Qué servicio deseas reservar?",
  "session_id": 1001,
  "metadata": null
}
```

---

### Ejemplo 2: Confirmación de reserva

**Request:**
```json
{
  "message": "Necesito corte de cabello para mañana a las 3pm, soy Juan Pérez, mi teléfono es 987654321",
  "session_id": 1002,
  "context": {
    "config": {
      "id_empresa": 123,
      "personalidad": "amigable y rápido"
    }
  }
}
```

**Response:**
```json
{
  "reply": "Reserva confirmada exitosamente\n\nDetalles:\n• Servicio: Corte de cabello\n• Fecha: 2026-01-29\n• Hora: 03:00 PM\n• Nombre: Juan Pérez\n\n¡Te esperamos!",
  "session_id": 1002,
  "metadata": null
}
```

---

### Ejemplo 3: Flujo conversacional (múltiples mensajes)

**Request 1:**
```json
{"message": "Quiero reservar", "session_id": 1004, "context": {"config": {"id_empresa": 123}}}
```
**Response 1:**
```json
{"reply": "¿Qué servicio deseas reservar?", "session_id": 1004, "metadata": null}
```

**Request 2 (misma sesión):**
```json
{"message": "Manicure", "session_id": 1004, "context": {"config": {"id_empresa": 123}}}
```
**Response 2:**
```json
{"reply": "Perfecto, manicure. ¿Para qué fecha necesitas la reserva?", "session_id": 1004, "metadata": null}
```

---

## Errores

Los errores se devuelven como respuestas normales con HTTP 200, dentro del campo `reply`:

### Context inválido (falta `id_empresa`)
```json
{"reply": "Error de configuración: Context missing required keys in config: ['id_empresa']", "session_id": 1, "metadata": null}
```

### Mensaje vacío
```json
{"reply": "No recibí tu mensaje. ¿Podrías repetirlo?", "session_id": 1, "metadata": null}
```

### Horario no disponible
```json
{"reply": "La hora seleccionada está fuera del horario de atención. El horario del lunes es de 09:00 AM a 06:00 PM. Por favor elige otra hora.", "session_id": 1, "metadata": null}
```

---

## Endpoints Auxiliares

### GET /health

Healthcheck para el gateway y balanceadores.

```
GET /health
→ 200 OK
{"status": "ok"}
```

### GET /metrics

Métricas en formato Prometheus.

```
GET /metrics
→ 200 OK (texto Prometheus)
```

Métricas principales disponibles:
```
agent_reservas_chat_requests_total
agent_reservas_booking_success_total
agent_reservas_booking_failed_total
agent_reservas_chat_response_duration_seconds
```

---

## Integración

### Python

```python
import httpx

async def chat(mensaje: str, session_id: int, id_empresa: int) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8003/chat",
            json={
                "message": mensaje,
                "session_id": session_id,
                "context": {
                    "config": {
                        "id_empresa": id_empresa,
                        "agendar_usuario": 1,
                        "agendar_sucursal": 0
                    }
                }
            }
        )
        data = response.json()
        return data["reply"]
```

### JavaScript

```javascript
async function chat(mensaje, sessionId, idEmpresa) {
  const response = await fetch('http://localhost:8003/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: mensaje,
      session_id: sessionId,
      context: {
        config: {
          id_empresa: idEmpresa,
          agendar_usuario: 1,
          agendar_sucursal: 0
        }
      }
    })
  });

  const data = await response.json();
  return data.reply;
}
```

---

## Notas Importantes

1. **Session ID único**: Cada usuario debe tener un `session_id` único (integer) para mantener el contexto conversacional.
2. **Memoria automática**: El agente recuerda la conversación usando `session_id`. No es necesario enviar historial manualmente.
3. **Validación multicapa**: El agente valida automáticamente formato de datos, horarios disponibles y disponibilidad real.
4. **Timeouts**: LLM 90s + APIs externas 10s.

---

## Ver también

- [ARCHITECTURE.md](ARCHITECTURE.md) - Arquitectura interna del sistema
- [DEPLOYMENT.md](DEPLOYMENT.md) - Guía de despliegue
