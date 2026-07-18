# J.A.R.V.I.S. IDE — v3.0

## Qué cambió respecto a v3.0

| Antes | Después |
|---|---|
| Modal "Run Agent" lanzaba el pipeline | El **chat ES el punto de entrada** — escribís y el agente analiza |
| Sin soporte de archivos adicionales | Tres fuentes de contexto: proyecto + bóveda + adjuntos |
| Provider hardcodeado o con URL fija | 4 providers con Base URL auto-cargada y validación de conexión |
| Sin modelos locales integrados | Selector Ollama + instalador directo desde la titlebar |
| Sin dialog nativo del OS | Botón 📁 abre `tkinter.filedialog` para navegar carpetas |
| Fase 0 bloqueaba sin `project_root` | Modo standalone: funciona con archivo suelto o solo adjuntos |
| Archivos adjuntos no llegaban al LLM | `additional_context` se inyecta en el prompt del orquestador |
| Sandbox como toggle | Sandbox embebido siempre visible en el área central |
| Descargas no disponibles | Descargar código HTML y ZIP desde la titlebar |
## Memoria de Proyecto [NUEVO]

El nuevo módulo de memoria permite rastrear todos los cambios realizados por el agente.

- **Modos de guardado:**
  - `json`: Guarda un registro estructurado (`jarvis_memory.json`).
  - `markdown`: Crea un `CHANGELOG.md` legible.
  - `obsidian`: Integra cambios directamente en tu bóveda (citas automáticas, notas por archivo y etiquetas).
- **Control:**
  - Habilitado/deshabilitado desde la GUI.
  - Preserva el historial entre sesiones.
  - Genera backups automáticos (`.bak`) de cada archivo modificado.

---

## Estructura

```
project/
├─ config/
│  ├─ config_schema.py          ← dataclasses: AgentConfig, ModelConfig, etc.
│  ├─ config_loader.py          ← carga desde JSON, dict o env; merge de overrides
│  └─ default_agent_config.json ← config base vacía (la GUI la completa)
│
├─ agent/
│  ├─ runtime_paths.py          ← resuelve rutas; acepta rutas absolutas y modo standalone
│  ├─ llm_client_factory.py     ← cliente LLM por provider (lazy, cacheado)
│  ├─ agent_corrector.py        ← pipeline: mapper → impact_analyzer → surgical_editor
│  ├─ skill_router.py           ← decide qué skills activar por TaskContext
│  ├─ skill_loader.py           ← carga skills .md desde RuntimePaths
│  └─ context_builder.py        ← construye el prompt final para el LLM
│
├─ gui/
│  └─ index.html                ← frontend completo (chat, sandbox, gestor, modelos)
│
├─ skills/                      ← archivos .md de skills
├─ prompts/
│  └─ system_base.md            ← prompt base del sistema
├─ outputs/                     ← archivos de salida (creados en runtime)
├─ cache/
├─ logs/
└─ main.py                      ← FastAPI + WebSocket + endpoints de dialog y contexto
```

---

## Instalación

```bash
pip install fastapi uvicorn openai anthropic requests
```

Para modelos locales (Ollama):
```bash
# Windows
set OLLAMA_ORIGINS=*
ollama serve

# macOS / Linux
export OLLAMA_ORIGINS=*
ollama serve
```

---

## Arrancar

```bash
uvicorn main:app --reload --port 8000
```

Luego abrí `http://localhost:8000` en el browser.

---

## Flujo de trabajo

### 1. Configurar el proveedor LLM (una vez)

Presioná **LLM Config** en la titlebar:

- Elegí el provider: **OpenAI / Anthropic / Google / NVIDIA**
- La Base URL se carga automáticamente (podés modificarla)
- Ingresá el nombre del modelo y la API Key
- Opcionalmente activá un **modelo cirujano** diferente al orquestador
- Usá **Probar conexión** para validar antes de guardar

### 2. Cargar contexto (opcional pero recomendado)

| Fuente | Cómo cargarlo |
|---|---|
| **Proyecto** | Ingresá la ruta o presioná 📁 para navegar → se carga el árbol de archivos |
| **Bóveda Obsidian** | Ingresá la ruta o presioná 📁 en el panel derecho → carga el grafo de módulos |
| **Archivos adicionales** | Presioná 📎 al lado del chat → archivos fuera del proyecto (PDFs, specs, módulos sueltos) |

### 3. Chatear con el agente

Escribís en el chat y presionás Enter. El agente:

1. Toma tu mensaje como descripción del problema
2. Detecta automáticamente si mencionás un `.py`
3. Combina proyecto + bóveda + adjuntos como contexto
4. Ejecuta el pipeline: `Mapper → Impact Analyzer → Surgical Editor`
5. Aplica el parche y guarda backup `.bak`

No necesitás abrir ningún modal para ejecutar. El chat ES el punto de entrada.

### 4. Config Pipeline (opcional)

Presioná **Config Pipeline** para pre-configurar:
- Archivo objetivo específico
- Descripción del problema
- Comportamiento esperado
- Logs / traceback

Guardá con el botón **Guardar** — el chat usará esa config en el próximo envío.

---

## Modelos locales (Ollama)

En la titlebar tenés integrado el gestor de Ollama:

```
Local: [ selector de modelos ]  [🔄]    [ nombre del modelo ]  [🚀 Instalar]
```

- El selector se llena automáticamente con los modelos instalados
- Si seleccionás un modelo local, el pipeline lo usa en lugar del provider cloud
- El instalador hace `POST /api/pull` a Ollama directamente
- Si Ollama no está corriendo, aparece un toast de aviso

---

## Sandbox

El área central oscura ES el sandbox. Muestra el ícono `</>` cuando está vacío.

- Cuando el agente genera código HTML/CSS/JS, se renderiza ahí automáticamente
- Al abrir un archivo del explorador, el editor Monaco ocupa ese espacio
- Al cerrar todos los tabs, el sandbox vuelve a ser visible
- Botón **Nueva pestaña** abre el contenido del sandbox en una pestaña nueva

---

## Descarga de archivos

Desde la titlebar:

| Botón | Función |
|---|---|
| **Descargar Código** | Descarga el HTML del sandbox como `jarvis_output.html` |
| **ZIP** | Empaqueta sandbox + adjuntos + tabs abiertos en `jarvis_proyecto.zip` |

---

## Modo standalone (sin proyecto)

Si no cargás un proyecto pero adjuntás archivos o pasás una ruta absoluta de archivo:

- La Fase 0 (Mapper) devuelve un mapa vacío y continúa sin interrumpir
- El pipeline infiere `project_root` como la carpeta del archivo objetivo
- El orquestador recibe el modo `standalone` en su contexto y ajusta el análisis
- Los archivos adjuntos se inyectan directamente en el prompt

---

## Providers soportados

| Provider | Base URL por defecto |
|---|---|
| `openai` | `https://api.openai.com/v1` |
| `anthropic` | `https://api.anthropic.com` |
| `google` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `nvidia` | `https://integrate.api.nvidia.com/v1` |
| `local` | `http://localhost:11434/v1` (Ollama) |

---

## Endpoints del backend

| Método | Ruta | Función |
|---|---|---|
| `POST` | `/api/project/load` | Carga árbol de archivos del proyecto |
| `POST` | `/api/file/read` | Lee un archivo del proyecto |
| `POST` | `/api/file/save` | Guarda un archivo editado |
| `POST` | `/api/graph/load` | Carga el grafo de nodos de Obsidian |
| `POST` | `/api/dialog/folder` | Abre dialog nativo del OS para elegir carpeta |
| `POST` | `/api/config/update` | Actualiza la config del agente en runtime |
| `GET`  | `/api/config/schema` | Retorna la config activa (sin claves sensibles) |
| `WS`   | `/ws/agent` | WebSocket del pipeline principal |

---

## Skills disponibles

| Skill | Cuándo se activa |
|---|---|
| `analyze_traceback` | Hay un traceback en la tarea |
| `find_symbol_usage` | Búsqueda de símbolo pedida |
| `validate_config_file` | Hay archivos de config |
| `find_dead_code` | Auditoría de código muerto |
| `map_change_impact` | Fix o análisis de impacto |
| `audit_python_module` | Archivos .py + fix/review |
| `safe_typo_fix` | Corrección tipográfica solicitada |
| `apply_local_fix` | Fix + aprobación explícita + diagnóstico previo |

Colocá los archivos `.md` en la carpeta `skills/`.

---

## Variables de entorno (alternativa a la GUI)

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export NVIDIA_API_KEY=nvapi-...
export OLLAMA_ORIGINS=*
```
## 📜 Licencia y Contribuciones

🆓 **Proyecto de código abierto.** Puedes usarlo, estudiarlo, modificarlo y distribuirlo libremente respetando los términos de su licencia.

🧪 **Probado en un entorno de desarrollo específico.** Dependiendo de tu sistema operativo, hardware, versiones de software o configuración, puede requerir pequeños ajustes o adaptaciones para funcionar correctamente.

🛠️ **Base para futuras mejoras.** Este proyecto está pensado como una base funcional sobre la que puedes desarrollar nuevas características, optimizaciones o adaptaciones según tus necesidades.

🤝 **Las contribuciones son bienvenidas.** Si corriges errores, mejoras el código o agregas nuevas funcionalidades, será un gusto recibir un Pull Request o que compartas tu versión con la comunidad.

ℹ️ **Compatibilidad.** Se realizaron pruebas básicas de funcionamiento, pero la compatibilidad final dependerá del entorno en el que se ejecute.

---

## 🚀 Apoyá el Proyecto

Si este proyecto te resultó útil y querés colaborar para que siga creciendo, tu apoyo ayuda a dedicar más tiempo al mantenimiento, corrección de errores y desarrollo de nuevas funcionalidades.

- ⭐ Dar una estrella al repositorio.

### 🇦🇷 Desde Argentina

- 🍋 **Lemon Tag:** `jnyary`
- 💳 **Alias / CVU:** `endeble.tacana.LEMON`

### 🌎 Otras formas de colaborar

- ❤️ **GitHub Sponsors:** https://github.com/sponsors/jonyari-hub

❤️ ¡Gracias por formar parte de la comunidad y ayudar a que este proyecto siga creciendo!
