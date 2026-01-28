# 🚀 Migración a LangChain 1.2+ API Moderna

**Fecha:** 27 de enero de 2026  
**Versión:** 1.0.0 → 2.0.0  
**Status:** ✅ Completado

---

## 📊 Resumen de Cambios

Se migró de **LangChain 0.3.x** (API deprecada) a **LangChain 1.2+** (API moderna).

### **Antes:**
- API: `create_openai_functions_agent` + `AgentExecutor`
- Memoria: Manual con `memory.py`
- Prompts: `ChatPromptTemplate` complejos
- Invocación: `.ainvoke({"input": ..., "chat_history": ...})`

### **Ahora:**
- API: `create_agent` (todo en uno)
- Memoria: Automática con `checkpointer` (InMemorySaver)
- Prompts: String simple
- Invocación: `.invoke({"messages": [...]})`

---

## 🔧 Cambios Técnicos Detallados

### 1. **requirements.txt**

```diff
# ANTES:
- langchain==0.3.7
- langchain-core==0.3.17
- langchain-openai==0.2.8

# AHORA:
+ langchain>=1.2.0
+ langchain-openai>=0.3.0
+ langgraph>=0.2.0
+ langgraph-checkpoint>=0.2.0
```

### 2. **agent.py** - Simplificación masiva

#### Imports:
```diff
# ANTES:
- from langchain.agents import create_openai_functions_agent, AgentExecutor
- from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
- from langchain_openai import ChatOpenAI

# AHORA:
+ from langchain.agents import create_agent
+ from langchain.chat_models import init_chat_model
+ from langgraph.checkpoint.memory import InMemorySaver
+ from dataclasses import dataclass
```

#### Creación del agente:
```diff
# ANTES (complejo - 30+ líneas):
- prompt = ChatPromptTemplate.from_messages([...])
- agent = create_openai_functions_agent(llm, tools, prompt)
- executor = AgentExecutor(agent, tools, verbose=True, max_iterations=5)

# AHORA (simple - 10 líneas):
+ model = init_chat_model(f"openai:{model_name}", ...)
+ agent = create_agent(
+     model=model,
+     tools=AGENT_TOOLS,
+     system_prompt=system_prompt_string,
+     checkpointer=_checkpointer
+ )
```

#### Invocación:
```diff
# ANTES:
- result = await executor.ainvoke({
-     "input": message,
-     "chat_history": chat_history
- })
- response_text = result["output"]

# AHORA:
+ result = agent.invoke(
+     {"messages": [{"role": "user", "content": message}]},
+     config={"configurable": {"thread_id": session_id}},
+     context=agent_context
+ )
+ response_text = result["messages"][-1].content
```

### 3. **tools.py** - Runtime Context

```diff
# ANTES (parámetros explícitos):
- @tool
- async def create_booking(
-     service: str,
-     date: str,
-     ...,
-     id_empresa: int = 1,
-     session_id: str = ""
- )

# AHORA (runtime context inyectado):
+ @tool
+ async def create_booking(
+     service: str,
+     date: str,
+     ...,
+     runtime: ToolRuntime = None  # ← Context automático
+ )
+     ctx = runtime.context
+     id_empresa = ctx.id_empresa
+     session_id = ctx.session_id
```

### 4. **memory.py** - Ya no necesario

```diff
# ANTES: Memoria manual
- from .memory import add_turn, get_history
- history = get_history(session_id, limit=4)
- add_turn(session_id, message, response)

# AHORA: Memoria automática
+ # El checkpointer maneja todo automáticamente
+ # Solo pasamos thread_id en config
```

### 5. **main.py** - Sin cambios funcionales

El endpoint `chat` sigue igual externamente, pero internamente usa la nueva API.

---

## 📈 Beneficios de la Migración

### **Código más limpio:**
- **Antes:** ~450 líneas en agent.py
- **Ahora:** ~150 líneas en agent.py
- **Reducción:** 67% menos código

### **Memoria automática:**
- ✅ Sin gestión manual de historial
- ✅ Persistencia automática con thread_id
- ✅ Menos bugs potenciales

### **API moderna:**
- ✅ Mejor soporte y documentación
- ✅ Integración con LangGraph
- ✅ Streaming nativo
- ✅ Middleware extensible

### **Runtime Context:**
- ✅ Tools reciben contexto automáticamente
- ✅ No más parámetros explícitos (id_empresa, session_id)
- ✅ Más limpio y mantenible

---

## 🧪 Testing

### **1. Limpiar dependencias viejas:**
```bash
cd c:\Users\ariel\Documents\AI_YOU\marav_ia\agent_reservas
pip uninstall langchain-text-splitters -y
```

### **2. Instalar nuevas dependencias:**
```bash
pip install -r requirements.txt --upgrade
```

### **3. Ejecutar como servidor HTTP:**
```bash
cd src
python -m reservas.main
```

**Debería ver:**
```
🚀 INICIANDO AGENTE RESERVAS - MaravIA
📍 Host: 0.0.0.0:8003
🤖 Modelo: gpt-4o-mini
```

### **4. Verificar versiones:**
```bash
pip show langchain langchain-openai langgraph
```

**Versiones esperadas:**
- langchain: ≥ 1.2.7
- langchain-core: ≥ 1.2.7
- langchain-openai: ≥ 1.1.7
- langgraph: ≥ 1.0.7

---

## 🔌 Conexión entre Servicios

### **Agente Reservas (HTTP Server):**
```python
# Se ejecuta en: http://localhost:8003
mcp.run(transport="http", host="0.0.0.0", port=8003)
```

### **Orquestador (HTTP Client):**
```python
# Llama al agente vía HTTP POST
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8003/tools/call",
        json={
            "name": "chat",
            "arguments": {
                "message": "Quiero reservar",
                "session_id": "user-123",
                "context": {"config": {"id_empresa": 1}}
            }
        }
    )
    result = response.json()
```

### **Endpoint del agente:**
- **URL:** `http://localhost:8003`
- **Tool:** `chat`
- **Método:** POST `/tools/call`

---

## ⚠️ Breaking Changes

### **Para el orquestador:**
✅ **No hay cambios necesarios**. El endpoint `chat` sigue con la misma firma.

### **Para desarrollo:**
- ❌ `create_openai_functions_agent` removido
- ❌ `AgentExecutor` removido
- ❌ `ChatPromptTemplate` con placeholders removido
- ❌ Memoria manual removida

---

## 🔄 Rollback Plan (si hay problemas)

Si la migración falla, revertir a LangChain 0.3.x:

```bash
# requirements.txt:
langchain==0.3.7
langchain-core==0.3.17
langchain-openai==0.2.8
# NO incluir langgraph
```

Y restaurar `agent.py` de git:
```bash
git checkout HEAD -- src/reservas/agent.py
```

---

## 📚 Referencias

- [LangChain 1.2 Docs](https://docs.langchain.com/oss/python/langchain/overview)
- [create_agent API](https://docs.langchain.com/oss/python/langchain/agents)
- [Tools con Runtime Context](https://docs.langchain.com/oss/python/langchain/tools)
- [Checkpointer y Memoria](https://docs.langchain.com/oss/python/langchain/short-term-memory)

---

**Migrado por:** AI Assistant  
**Revisado por:** Pendiente
