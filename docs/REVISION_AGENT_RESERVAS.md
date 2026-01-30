# Revisión del Agente de Reservas (agent_reservas)

## Resumen

El agente está bien estructurado, alineado con la documentación n8n (AGENDAR_REUNION) y con el flujo MaravIA (orquestador → agente reservas → tools → API). Se revisaron: agent.py, booking.py, tools.py, validation.py, schedule_validator.py, prompts, sucursales.py, config, main.py, models.

---

## Lo que está bien

- **Payload AGENDAR_REUNION**: booking.py envía codOpe, titulo, fecha_inicio, fecha_fin, id_prospecto, agendar_usuario, agendar_sucursal, sucursal (opcional). Coincide con la doc n8n.
- **Contexto del orquestador**: id_empresa, agendar_usuario, agendar_sucursal se reciben y se convierten a int (1/0) en AgentContext; el identificador del prospecto es el **session_id** que envía el orquestador (no se envía id_prospecto en config). Las tools usan ese contexto y pasan session_id como id_prospecto a confirm_booking.
- **Sucursal**: Parámetro opcional en create_booking; la IA lo rellena (una sucursal → automático; varias → preguntar). Se envía en el payload cuando hay valor.
- **System prompt**: Inyecta fecha/hora Perú, lista de sucursales (API), instrucciones claras para sucursal y para las tools.
- **Validación**: validation.py valida servicio, fecha, hora, nombre, contacto (email/teléfono peruano).
- **ScheduleValidator**: Cache TTL, SUGERIR_HORARIOS para hoy/mañana, OBTENER_HORARIO_REUNIONES para otras fechas; validate() para comprobar slot antes de confirmar.
- **MCP**: Una sola tool `chat` expuesta al orquestador; contexto requerido documentado.
- **Manejo de errores**: booking.py captura timeout, HTTP, RequestError; tools devuelven mensajes claros al usuario.

---

## Mejoras menores aplicadas / sugeridas

1. **main.py (chat docstring)**: Se documenta el contexto que espera el agente (id_empresa, agendar_usuario, agendar_sucursal, etc.). El orquestador no envía id_prospecto; el agente usa solo session_id como identificador del prospecto.
2. **reserva_system.j2**: Se aclara el caso “no hay sucursales” (no exigir sucursal) y se añade un paso en el flujo de captura para “si hay varias sucursales y no ha elegido”.
3. **booking.py**: Si se quiere un mensaje más claro cuando la hora tiene formato inválido, se puede capturar ValueError en confirm_booking y devolver `{"success": False, "error": "Formato de fecha u hora inválido"}`; actualmente el Exception genérico en tools ya devuelve un mensaje amigable.

---

## Comportamiento esperado end-to-end

1. Orquestador envía message, session_id, context (config con id_empresa, agendar_usuario, agendar_sucursal, personalidad, etc.). No envía id_prospecto; el agente usa session_id como identificador del prospecto.
2. Agente construye el system prompt (fecha Perú, sucursales desde API, instrucciones).
3. Usuario conversa; la IA usa check_availability cuando pide disponibilidad y create_booking cuando tiene todos los datos (incluida sucursal si aplica).
4. create_booking valida datos, valida horario con ScheduleValidator, llama a confirm_booking con id_prospecto=session_id, agendar_usuario, agendar_sucursal, sucursal (nombre), etc.
5. booking.py arma fecha_inicio/fecha_fin, titulo, y envía el JSON al endpoint; el vendedor recibe la reserva con sucursal cuando se indicó.

---

## Archivos clave

| Archivo | Rol |
|--------|-----|
| agent.py | AgentContext, _prepare_agent_context, process_reserva_message |
| booking.py | confirm_booking, payload AGENDAR_REUNION, _build_fecha_inicio_fin |
| tools.py | check_availability, create_booking (sucursal opcional), uso de ctx |
| prompts/reserva_system.j2 | Instrucciones, sucursales, flujo de captura |
| prompts/__init__.py | build_reserva_system_prompt, fecha Perú, fetch_sucursales_publicas |
| schedule_validator.py | Horarios, validate, recommendation (SUGERIR_HORARIOS) |
| sucursales.py | fetch_sucursales_publicas, format_sucursales_for_system_prompt |
| validation.py | validate_booking_data, ContactInfo, BookingDateTime |
| main.py | MCP tool chat, process_reserva_message |
