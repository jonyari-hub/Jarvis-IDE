"""
main.py
J.A.R.V.I.S. IDE Backend — FastAPI + WebSocket

Cambios respecto a la versión anterior:
  - Sin rutas hardcodeadas.
  - Sin claves de API en el código.
  - Cada sesión del pipeline construye un AgentConfig desde los parámetros del WS.
  - La GUI puede cambiar provider, modelo, claves, proyecto y vault por sesión.
  - ConfigLoader.merge_runtime_overrides aplica los overrides sin tocar el JSON base.
  - [NUEVO] Módulo de Memoria de Proyecto: registra cambios del agente en JSON/MD/Obsidian.
            Deshabilitado por default. El usuario lo activa desde la GUI.
"""
import os
import sys
import json
import time
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from config.config_loader import ConfigLoader
from config.config_schema import AgentConfig
from agent.agent_corrector import (
    fase_0_obsidian_mapper,
    fase_impact_analyzer,
    fase_surgical_editor,
    extraer_dependencias_python,
)
from agent.runtime_paths import build_runtime_paths
from project_memory import ProjectMemory, MemoryConfig, memory_from_dict, memory_config_to_dict

# ──────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────

app = FastAPI(title="JARVIS IDE API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config base cargada al arrancar (puede ser vacía, la GUI la completa)
_DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "default_agent_config.json"

def _load_base_config() -> AgentConfig:
    if _DEFAULT_CONFIG_PATH.exists():
        try:
            return ConfigLoader.load_from_json_file(_DEFAULT_CONFIG_PATH)
        except Exception as e:
            print(f"[main] No se pudo cargar config base: {e}. Usando defaults.")
    return ConfigLoader.load_defaults()

_base_config = _load_base_config()


# ──────────────────────────────────────────────────────────────
# Memoria de Proyecto — deshabilitada por default
# ──────────────────────────────────────────────────────────────

def _load_memory_config() -> ProjectMemory:
    """
    Intenta restaurar la config de memoria guardada en disco.
    Si no existe, devuelve una instancia deshabilitada (no-op).
    """
    cfg_path = Path("./jarvis_memory/config.json")
    if cfg_path.exists():
        try:
            saved = json.loads(cfg_path.read_text(encoding="utf-8"))
            mem = memory_from_dict(saved)
            print(f"[Memory] Config restaurada — modo: {saved.get('mode','json')}, "
                  f"habilitada: {saved.get('enabled', False)}")
            return mem
        except Exception as e:
            print(f"[Memory] No se pudo restaurar config: {e}. Usando defaults.")
    return ProjectMemory(MemoryConfig())   # deshabilitada

project_memory = _load_memory_config()


# ──────────────────────────────────────────────────────────────
# WebSocket manager
# ──────────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, event: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


def make_event(event_type: str, payload: dict = None, status: str = "running") -> dict:
    return {
        "type": event_type,
        "status": status,
        "ts": time.time(),
        "payload": payload or {},
    }


# ──────────────────────────────────────────────────────────────
# Helpers: construir AgentConfig desde el mensaje WS
# ──────────────────────────────────────────────────────────────

def _build_session_config(data: dict) -> AgentConfig:
    """
    Construye un AgentConfig para esta sesión.
    Los overrides vienen del mensaje WS enviado por la GUI.
    No modifica _base_config global.
    """
    import copy
    cfg = copy.deepcopy(_base_config)

    # Overrides planos que la GUI puede mandar
    overrides = {}

    if data.get("ruta_proyecto"):
        overrides["project_root"] = data["ruta_proyecto"]

    if data.get("ruta_obsidian"):
        overrides["obsidian_vault"] = data["ruta_obsidian"]

    if data.get("provider"):
        overrides["provider"] = data["provider"]

    if data.get("model_name"):
        overrides["model_name"] = data["model_name"]

    if data.get("api_key"):
        overrides["api_key"] = data["api_key"]

    if data.get("base_url"):
        overrides["base_url"] = data["base_url"]

    if data.get("allow_code_editing") is not None:
        overrides["allow_code_editing"] = data["allow_code_editing"]

    if data.get("session_id"):
        overrides["session_id"] = data["session_id"]

    # Contexto adicional (archivos adjuntos desde la GUI)
    if data.get("additional_context"):
        cfg.extra["additional_context"] = data["additional_context"]

    # Modelo secundario (cirujano) si la GUI lo manda
    if data.get("model_secondary"):
        overrides["model_secondary"] = data["model_secondary"]

    return ConfigLoader.merge_runtime_overrides(cfg, overrides)


# ──────────────────────────────────────────────────────────────
# Endpoints: filesystem
# ──────────────────────────────────────────────────────────────

class ProjectLoad(BaseModel):
    path: str

@app.post("/api/project/load")
async def load_project(body: ProjectLoad):
    root = Path(body.path)
    if not root.exists() or not root.is_dir():
        raise HTTPException(400, "Ruta inválida o no existe")
    tree = _build_tree(root, root)
    return {"ok": True, "tree": tree, "root": str(root)}


def _build_tree(path: Path, root: Path) -> dict:
    node = {
        "name": path.name,
        "path": str(path.relative_to(root)),
        "abs": str(path),
        "type": "dir" if path.is_dir() else "file",
        "ext": path.suffix if path.is_file() else None,
    }
    if path.is_dir():
        children = []
        try:
            for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
                if child.name.startswith(".") or child.name == "__pycache__":
                    continue
                children.append(_build_tree(child, root))
        except PermissionError:
            pass
        node["children"] = children
    return node


class FileRead(BaseModel):
    abs_path: str

@app.post("/api/file/read")
async def read_file(body: FileRead):
    p = Path(body.abs_path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "Archivo no encontrado")
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "content": content, "name": p.name, "path": str(p)}
    except Exception as e:
        raise HTTPException(500, str(e))


class FileSave(BaseModel):
    abs_path: str
    content: str

@app.post("/api/dialog/folder")
async def dialog_folder():
    """Abre un dialogo nativo del SO para elegir carpeta. Requiere tkinter."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Seleccionar carpeta")
        root.destroy()
        return {"ok": True, "path": path or ""}
    except Exception as e:
        raise HTTPException(500, f"Dialog no disponible: {e}")


@app.post("/api/file/save")
async def save_file(body: FileSave):
    p = Path(body.abs_path)
    try:
        p.write_text(body.content, encoding="utf-8")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


# ──────────────────────────────────────────────────────────────
# Endpoints: grafo Obsidian
# ──────────────────────────────────────────────────────────────

class ObsidianLoad(BaseModel):
    vault_path: str
    module_name: Optional[str] = None

@app.post("/api/graph/load")
async def load_graph(body: ObsidianLoad):
    import re
    vault = Path(body.vault_path)
    if not vault.exists():
        raise HTTPException(400, "Vault no existe")

    nodes, edges = [], []
    for f in vault.rglob("*.md"):
        stem = f.stem
        nodes.append({"id": stem, "label": stem, "path": str(f)})
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            for lnk in re.findall(r'\[\[([^\]]+)\]\]', content):
                edges.append({"source": stem, "target": lnk.split("|")[0].strip()})
        except Exception:
            pass

    module_note = None
    if body.module_name:
        note_path = vault / f"{body.module_name}.md"
        if note_path.exists():
            module_note = note_path.read_text(encoding="utf-8", errors="replace")

    return {"ok": True, "nodes": nodes, "edges": edges, "module_note": module_note}


# ──────────────────────────────────────────────────────────────
# Endpoint: actualizar config en runtime (desde la GUI)
# ──────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    overrides: dict

@app.post("/api/config/update")
async def update_config(body: ConfigUpdate):
    """
    La GUI puede actualizar la config base sin reiniciar el proceso.
    Los cambios afectan a las próximas sesiones WS.
    """
    global _base_config
    try:
        _base_config = ConfigLoader.merge_runtime_overrides(_base_config, body.overrides)
        from agent.llm_client_factory import invalidate_client_cache
        invalidate_client_cache()
        return {"ok": True, "message": "Configuración actualizada"}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/config/schema")
async def get_config_schema():
    """Retorna la config actual (sin claves sensibles) para que la GUI la muestre."""
    import copy
    cfg_dict = {
        "model": {
            "provider": _base_config.model.provider,
            "model_name": _base_config.model.model_name,
            "api_key": "***" if _base_config.model.api_key else "",
            "base_url": _base_config.model.base_url or "",
            "temperature": _base_config.model.temperature,
            "max_tokens": _base_config.model.max_tokens,
            "role": _base_config.model.role,
        },
        "paths": {
            "project_root": str(_base_config.paths.project_root or ""),
            "obsidian_vault": str(_base_config.paths.obsidian_vault or ""),
            "skills_root": str(_base_config.paths.skills_root),
            "prompts_root": str(_base_config.paths.prompts_root),
        },
        "behavior": {
            "allow_obsidian": _base_config.behavior.allow_obsidian,
            "allow_code_editing": _base_config.behavior.allow_code_editing,
            "require_edit_approval": _base_config.behavior.require_edit_approval,
            "max_retries": _base_config.behavior.max_retries,
        },
    }
    return cfg_dict


# ──────────────────────────────────────────────────────────────
# Endpoints: Memoria de Proyecto
# ──────────────────────────────────────────────────────────────

class MemoryConfigRequest(BaseModel):
    enabled: bool = False
    mode: str = "json"
    memory_dir: str = "./jarvis_memory"
    obsidian_folder: str = ""
    create_per_file_notes: bool = True
    obsidian_tag: str = "jarvis-ide"


@app.get("/api/memory/config")
async def get_memory_config():
    """Devuelve la config actual de memoria de proyecto."""
    return {
        "ok": True,
        "config": memory_config_to_dict(project_memory.config),
        "message": "Config actual",
    }


@app.post("/api/memory/config")
async def update_memory_config(req: MemoryConfigRequest):
    """
    Actualiza la config de memoria en runtime.
    Persiste la config en disco para sobrevivir reinicios.
    Si se habilita o cambia el modo, reinicia el módulo preservando el historial.
    """
    global project_memory

    new_cfg = MemoryConfig(
        enabled=req.enabled,
        mode=req.mode,
        memory_dir=req.memory_dir,
        obsidian_folder=req.obsidian_folder,
        create_per_file_notes=req.create_per_file_notes,
        obsidian_tag=req.obsidian_tag,
    )

    # Preservar historial en memoria al reiniciar
    old_entries = project_memory._entries[:]
    project_memory = ProjectMemory(new_cfg)
    project_memory._entries = old_entries

    # Persistir en disco para sobrevivir reinicios
    try:
        cfg_dir = Path(req.memory_dir)
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / "config.json"
        cfg_path.write_text(
            json.dumps(memory_config_to_dict(new_cfg), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[Memory] No se pudo persistir config: {e}")

    estado = "habilitada" if req.enabled else "deshabilitada"
    return {
        "ok": True,
        "config": memory_config_to_dict(new_cfg),
        "message": f"Memoria {estado} — modo: {req.mode}",
    }


@app.get("/api/memory/history")
async def get_memory_history(file_path: Optional[str] = None):
    """Devuelve el historial de cambios. Filtrable por archivo."""
    return {
        "ok": True,
        "entries": project_memory.get_history(file_path or ""),
        "summary": project_memory.get_summary(),
    }


@app.get("/api/memory/summary")
async def get_memory_summary():
    """Resumen rápido: cuántos cambios, qué archivos se tocaron."""
    return {"ok": True, **project_memory.get_summary()}


# ──────────────────────────────────────────────────────────────
# WebSocket: pipeline del agente
# ──────────────────────────────────────────────────────────────

@app.websocket("/ws/agent")
async def agent_ws(ws: WebSocket):
    await manager.connect(ws)

    async def emit(event_type: str, payload: dict = None, status: str = "running"):
        await ws.send_json(make_event(event_type, payload, status))

    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action")

            if action == "run_pipeline":
                await _run_pipeline_ws(data, emit)
            elif action == "ping":
                await ws.send_json({"type": "pong"})
            elif action == "update_config":
                # La GUI puede mandar overrides en cualquier momento
                overrides = data.get("overrides", {})
                global _base_config
                _base_config = ConfigLoader.merge_runtime_overrides(_base_config, overrides)
                await emit("log", {"message": "Configuración actualizada por la GUI."})

    except WebSocketDisconnect:
        manager.disconnect(ws)


async def _run_pipeline_ws(data: dict, emit) -> None:
    """Pipeline completo con eventos WS en tiempo real."""
    archivo = data.get("archivo", "")
    problema = data.get("problema", "")
    esperado = data.get("esperado", "Funcionamiento correcto")
    sintomas = data.get("sintomas", "")

    # Construir config de sesión desde los parámetros del mensaje
    try:
        cfg = _build_session_config(data)
    except Exception as e:
        await emit("task_failed", {"message": f"Config inválida: {e}"}, "error")
        return

    # ── Modo standalone: si no hay project_root pero hay archivo, usar su carpeta ──
    if not cfg.paths.project_root and archivo:
        archivo_path = Path(archivo)
        if archivo_path.is_absolute() and archivo_path.exists():
            cfg.paths.project_root = archivo_path.parent
            print(f"[Pipeline] Modo standalone — project_root inferido: {cfg.paths.project_root}")

    rp = build_runtime_paths(cfg)

    await emit("task_received", {
        "archivo": archivo,
        "problema": problema,
        "message": f"Tarea recibida: {archivo} | provider: {cfg.model.provider} | modelo: {cfg.model.model_name}",
    })

    loop = asyncio.get_event_loop()

    # ── Fase 0: obsidian_mapper ──────────────────────────────
    await emit("log", {"message": "Indexando proyecto y vault de Obsidian..."})
    try:
        mapa = await loop.run_in_executor(
            None, lambda: fase_0_obsidian_mapper(cfg, rp, archivo_objetivo=archivo)
        )
        await emit("graph_node_loaded", {
            "mapa": mapa,
            "message": (
                f"Proyecto indexado: {mapa.get('total_modulos_codigo', 0)} módulos, "
                f"{mapa.get('total_notas_memoria', 0)} notas"
            ),
        })
    except Exception as e:
        await emit("log", {"message": f"[Mapper] Error: {e}"})
        mapa = {}

    # ── Leer archivo objetivo ────────────────────────────────
    await emit("file_read", {"file": archivo, "message": f"Leyendo {archivo}..."})
    codigo_actual = None
    try:
        found = rp.find_file_in_project(archivo)
        if found:
            codigo_actual = found.read_text(encoding="utf-8", errors="replace")
            await emit("file_read", {
                "file": archivo,
                "message": f"Archivo leído ({len(codigo_actual)} chars)",
                "preview": codigo_actual[:200],
            })
    except Exception as e:
        await emit("log", {"message": f"[FileRead] {e}"})

    # Dependencias
    if codigo_actual:
        import re
        imports_found = list(set(re.findall(
            r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)', codigo_actual, re.MULTILINE
        )))
        if imports_found:
            await emit("dependency_found", {
                "deps": imports_found,
                "message": f"Dependencias detectadas: {', '.join(imports_found)}",
            })

    # ── Fase 1: impact_analyzer ──────────────────────────────
    await emit("log", {
        "message": f"Enviando análisis a {cfg.model.provider}/{cfg.model.model_name} (Orquestador)..."
    })
    try:
        diagnostico = await loop.run_in_executor(
            None, lambda: fase_impact_analyzer(problema, esperado, sintomas, mapa, cfg)
        )
    except Exception as e:
        await emit("task_failed", {"message": f"Error en orquestador: {e}"}, "error")
        return

    if not diagnostico:
        await emit("task_failed", {
            "message": f"El orquestador ({cfg.model.provider}/{cfg.model.model_name}) no respondió. "
                       "Verificá las credenciales o la quota."
        }, "error")
        return

    await emit("impact_detected", {
        "diagnostico": diagnostico,
        "message": "Diagnóstico de impacto recibido",
    })

    # ── Fase 2: surgical_editor ──────────────────────────────
    surgeon = cfg.get_surgeon_model()
    await emit("log", {
        "message": f"Aplicando corrección quirúrgica con {surgeon.provider}/{surgeon.model_name}..."
    })
    try:
        parche_ok = await loop.run_in_executor(
            None, lambda: fase_surgical_editor(archivo, diagnostico, cfg, rp)
        )
        if parche_ok:
            await emit("patch_generated", {
                "file": archivo,
                "message": f"Parche aplicado en {archivo}. Backup .bak generado.",
            })

            # ── Registrar en Memoria de Proyecto ────────────
            # Solo si está habilitada — si no, record_change() es un no-op
            try:
                backup_path = str(Path(archivo).with_suffix(Path(archivo).suffix + ".bak"))
                nota_path = project_memory.record_change(
                    file_path=archivo,
                    description=diagnostico[:300] if diagnostico else "",
                    change_type="fix" if sintomas else "edit",
                    lines_changed=0,      # se puede mejorar calculando el diff
                    agent_task=problema,
                    backup_path=backup_path,
                )
                if nota_path:
                    await emit("log", {"message": f"[Memory] Cambio registrado → {nota_path}"})
            except Exception as mem_err:
                # La memoria nunca debe romper el pipeline
                print(f"[Memory] Error al registrar cambio: {mem_err}")

        else:
            await emit("log", {"message": f"Sin cambios en {archivo} (o sin respuesta del cirujano)."})
    except Exception as e:
        await emit("task_failed", {"message": f"Error en cirujano: {e}"}, "error")
        return

    await emit("graph_update_suggested", {
        "message": "Grafo de Obsidian actualizado con nuevas dependencias detectadas",
    })

    await emit("task_completed", {
        "message": "Pipeline finalizado correctamente.",
        "archivo": archivo,
    }, "success")


# ──────────────────────────────────────────────────────────────
# Frontend estático
# ──────────────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent / "gui"

@app.get("/")
async def serve_frontend():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse(
        "<h1>Frontend no encontrado.</h1>"
        "<p>Colocá index.html en la carpeta <code>gui/</code>.</p>"
    )

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "provider": _base_config.model.provider,
        "model": _base_config.model.model_name,
        "project_root": str(_base_config.paths.project_root or ""),
        "memory_enabled": project_memory.config.enabled,
        "memory_mode": project_memory.config.mode,
    }
