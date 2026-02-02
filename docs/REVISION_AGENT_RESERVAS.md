# Revisión del Agente de Reservas (agent_reservas)

## Resumen

El agente está bien estructurado, alineado con la documentación n8n (AGENDAR_REUNION) y con el flujo MaravIA (orquestador → agente reservas → tools → API). Se revisaron: agent/agent.py, services/booking.py, tools/tools.py, validation.py, services/schedule_validator.py, prompts, services/sucursales.py, config, main.py, models.

---

## Lo que está bien

- **Payload AGENDAR_REUNION**: booking.py envía codOpe, titulo, fecha_inicio, fecha_fin, id_prospecto (int), agendar_usuario, agendar_sucursal, sucursal (opcional). Coincide con la doc n8n.
- **Contexto del orquestador**: id_empresa, agendar_usuario, agendar_sucursal se reciben y se convierten a int (1/0) en AgentContext; el identificador del prospecto es el **session_id** (int) que envía el orquestador. Las tools usan ese contexto y pasan session_id como id_prospecto a confirm_booking.
- **Sucursal**: Parámetro opcional en create_booking; la IA lo rellena (una sucursal → automático; varias → preguntar). Se envía en el payload cuando hay valor.
- **System prompt**: Inyecta fecha/hora Perú (America/Lima), lista de sucursales (API), instrucciones claras para sucursal y para las tools.
- **Validación**: validation.py valida servicio, fecha, hora, nombre, contacto (email/teléfono peruano).
- **ScheduleValidator**: Cache TTL, SUGERIR_HORARIOS para hoy/mañana, OBTENER_HORARIO_REUNIONES para otras fechas; validate() para comprobar slot antes de confirmar.
- **check_availability**: Acepta parámetro `time` opcional. Si viene hora, usa CONSULTAR_DISPONIBILIDAD para ese slot; si no, usa SUGERIR_HORARIOS.
- **MCP**: Una sola tool `chat` expuesta al orquestador; contexto requerido documentado.
- **Manejo de errores**: booking.py captura timeout, HTTP, RequestError; tools devuelven mensajes claros al usuario.

---

## Cambios recientes (v2.0.0+)

1. **session_id ahora es int**: Antes era string, ahora es int (unificado con orquestador).
2. **id_prospecto = session_id**: Se usa el mismo valor para ambos campos (int).
3. **Nuevo parámetro `time` en check_availability**: Permite consultar disponibilidad de un slot específico.
4. **Nuevo parámetro `sucursal` en create_booking**: Para indicar la sucursal cuando hay múltiples.
5. **SUGERIR_HORARIOS**: Nuevo codOpe para obtener sugerencias de horarios para hoy/mañana.
6. **Payload booking actualizado**: Usa titulo, fecha_inicio, fecha_fin en lugar de fecha_cita, hora_cita.
7. **agendar_usuario y agendar_sucursal**: Nuevos flags en el contexto del agente.
8. **Zona horaria Perú**: Se usa ZoneInfo("America/Lima") para fechas.

---

## Comportamiento esperado end-to-end

1. Orquestador envía message, session_id (int), context (config con id_empresa, agendar_usuario, agendar_sucursal, personalidad, etc.). No envía id_prospecto; el agente usa session_id como identificador del prospecto.
2. Agente construye el system prompt (fecha Perú, sucursales desde API, instrucciones).
3. Usuario conversa; la IA usa check_availability cuando pide disponibilidad y create_booking cuando tiene todos los datos (incluida sucursal si aplica).
4. create_booking valida datos, valida horario con ScheduleValidator, llama a confirm_booking con id_prospecto=session_id, agendar_usuario, agendar_sucursal, sucursal (nombre), duracion_cita_minutos, etc.
5. booking.py construye fecha_inicio/fecha_fin, titulo, y envía el JSON al endpoint; el vendedor recibe la reserva con sucursal cuando se indicó.

---

## Archivos clave

| Archivo | Rol |
|--------|-----|
| agent/agent.py | AgentContext (session_id int), _prepare_agent_context, process_reserva_message |
| services/booking.py | confirm_booking, payload AGENDAR_REUNION, _build_fecha_inicio_fin |
| tools/tools.py | check_availability (con time opcional), create_booking (con sucursal opcional), uso de ctx |
| prompts/reserva_system.j2 | Instrucciones, sucursales, flujo de captura |
| prompts/__init__.py | build_reserva_system_prompt, fecha Perú, fetch_sucursales_publicas |
| services/schedule_validator.py | Horarios, validate, recommendation (SUGERIR_HORARIOS, CONSULTAR_DISPONIBILIDAD) |
| services/sucursales.py | fetch_sucursales_publicas, format_sucursales_for_system_prompt |
| validation.py | validate_booking_data, ContactInfo, BookingDateTime |
| main.py | MCP tool chat, process_reserva_message |
| config/config.py | Variables de entorno, URLs de APIs |

---

## Endpoints API utilizados

| Endpoint | codOpe | Propósito |
|----------|--------|-----------|
| ws_informacion_ia.php | OBTENER_HORARIO_REUNIONES | Horarios de atención por día |
| ws_informacion_ia.php | OBTENER_SUCURSALES_PUBLICAS | Lista de sucursales |
| ws_agendar_reunion.php | CONSULTAR_DISPONIBILIDAD | Verificar slot disponible |
| ws_agendar_reunion.php | SUGERIR_HORARIOS | Sugerencias para hoy/mañana |
| ws_agendar_reunion.php | AGENDAR_REUNION | Confirmar reserva |

---

**Última actualización:** 2026-02-02
