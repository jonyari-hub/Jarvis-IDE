"""
project_memory.py — Módulo de Memoria de Proyecto para Jarvis-IDE
=================================================================
Guarda un historial de todos los cambios que el agente aplica.
Funciona en tres modos:
  - "json"     → guarda en <memory_dir>/jarvis_memory.json  (default)
  - "markdown" → guarda en <memory_dir>/CHANGELOG.md
  - "obsidian" → guarda en la bóveda de Obsidian (carpeta configurable)

Si está deshabilitado (enabled=False), no hace nada y no rompe nada.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional


# ─────────────────────────────────────────────
# Config del módulo
# ─────────────────────────────────────────────

@dataclass
class MemoryConfig:
    enabled: bool = False
    mode: Literal["json", "markdown", "obsidian"] = "json"

    # Para modo json / markdown: carpeta donde guardar (relativa al proyecto o absoluta)
    memory_dir: str = "./jarvis_memory"

    # Para modo obsidian: ruta absoluta de la carpeta dentro de la bóveda
    # Ej: "C:/Users/Jony/Obsidian/MiVault/Jarvis-IDE/Cambios"
    obsidian_folder: str = ""

    # Si True, además del changelog global también crea una nota por cada archivo modificado
    create_per_file_notes: bool = True

    # Tag para las notas de Obsidian (aparece como #jarvis-ide en el grafo)
    obsidian_tag: str = "jarvis-ide"


# ─────────────────────────────────────────────
# Entrada de cambio
# ─────────────────────────────────────────────

@dataclass
class ChangeEntry:
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    file_path: str = ""
    change_type: str = "edit"          # edit | fix | refactor | create | delete
    description: str = ""
    lines_changed: int = 0
    agent_task: str = ""               # El mensaje original del usuario
    backup_path: str = ""


# ─────────────────────────────────────────────
# Motor principal
# ─────────────────────────────────────────────

class ProjectMemory:
    """
    Instanciá una vez en main.py y pasala al pipeline.
    Si config.enabled es False, todos los métodos son no-ops.
    """

    def __init__(self, config: MemoryConfig):
        self.config = config
        self._entries: list[ChangeEntry] = []

        if config.enabled:
            self._setup_dirs()
            self._load_existing()

    # ── Setup ──────────────────────────────────

    def _setup_dirs(self):
        cfg = self.config
        if cfg.mode in ("json", "markdown"):
            Path(cfg.memory_dir).mkdir(parents=True, exist_ok=True)
        elif cfg.mode == "obsidian":
            if cfg.obsidian_folder:
                Path(cfg.obsidian_folder).mkdir(parents=True, exist_ok=True)
            else:
                # Si no hay carpeta de Obsidian configurada, cae a json
                self.config.mode = "json"
                Path(cfg.memory_dir).mkdir(parents=True, exist_ok=True)

    def _load_existing(self):
        """Carga entradas previas del JSON si existe (para no perder historial entre sesiones)."""
        if self.config.mode == "json":
            p = Path(self.config.memory_dir) / "jarvis_memory.json"
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    self._entries = [ChangeEntry(**e) for e in data.get("changes", [])]
                except Exception:
                    self._entries = []

    # ── API pública ────────────────────────────

    def record_change(
        self,
        file_path: str,
        description: str,
        change_type: str = "edit",
        lines_changed: int = 0,
        agent_task: str = "",
        backup_path: str = "",
    ) -> Optional[str]:
        """
        Registra un cambio. Devuelve la ruta de la nota creada (o None si está deshabilitado).
        Llama a este método desde agent_corrector.py después de aplicar cada patch.
        """
        if not self.config.enabled:
            return None

        entry = ChangeEntry(
            file_path=file_path,
            change_type=change_type,
            description=description,
            lines_changed=lines_changed,
            agent_task=agent_task,
            backup_path=backup_path,
        )
        self._entries.append(entry)

        mode = self.config.mode
        if mode == "json":
            return self._save_json(entry)
        elif mode == "markdown":
            return self._save_markdown(entry)
        elif mode == "obsidian":
            return self._save_obsidian(entry)

    def get_history(self, file_path: str = "") -> list[dict]:
        """
        Devuelve el historial. Si se pasa file_path, filtra por ese archivo.
        Útil para mostrar en la GUI el log de la sesión.
        """
        entries = self._entries
        if file_path:
            entries = [e for e in entries if e.file_path == file_path]
        return [asdict(e) for e in entries]

    def get_summary(self) -> dict:
        """Resumen rápido para mostrar en la titlebar o panel."""
        files_touched = list({e.file_path for e in self._entries})
        return {
            "total_changes": len(self._entries),
            "files_touched": files_touched,
            "last_change": asdict(self._entries[-1]) if self._entries else None,
        }

    # ── Backends de guardado ───────────────────

    def _save_json(self, entry: ChangeEntry) -> str:
        p = Path(self.config.memory_dir) / "jarvis_memory.json"
        data = {
            "project": str(Path(self.config.memory_dir).resolve()),
            "last_updated": datetime.now().isoformat(),
            "changes": [asdict(e) for e in self._entries],
        }
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(p)

    def _save_markdown(self, entry: ChangeEntry) -> str:
        p = Path(self.config.memory_dir) / "CHANGELOG.md"

        # Si no existe, crear cabecera
        if not p.exists():
            p.write_text(
                "# Jarvis-IDE — Historial de Cambios\n\n"
                "_Generado automáticamente. No editar manualmente._\n\n---\n\n",
                encoding="utf-8",
            )

        # Formatear nueva entrada
        dt = datetime.fromisoformat(entry.timestamp)
        block = (
            f"## {dt.strftime('%Y-%m-%d %H:%M')} — `{Path(entry.file_path).name}`\n\n"
            f"- **Tipo:** {entry.change_type}\n"
            f"- **Archivo:** `{entry.file_path}`\n"
            f"- **Líneas modificadas:** {entry.lines_changed}\n"
            f"- **Tarea:** {entry.agent_task or '—'}\n"
            f"- **Descripción:** {entry.description}\n"
            + (f"- **Backup:** `{entry.backup_path}`\n" if entry.backup_path else "")
            + "\n---\n\n"
        )

        # Insertar después de la cabecera (las más recientes arriba)
        existing = p.read_text(encoding="utf-8")
        split_marker = "---\n\n"
        idx = existing.find(split_marker)
        if idx != -1:
            new_content = existing[: idx + len(split_marker)] + block + existing[idx + len(split_marker) :]
        else:
            new_content = existing + block

        p.write_text(new_content, encoding="utf-8")
        return str(p)

    def _save_obsidian(self, entry: ChangeEntry) -> str:
        folder = Path(self.config.obsidian_folder)
        tag = self.config.obsidian_tag
        dt = datetime.fromisoformat(entry.timestamp)

        # 1. Actualizar _CHANGELOG.md global en la bóveda
        changelog = folder / "_CHANGELOG.md"
        if not changelog.exists():
            changelog.write_text(
                f"# Jarvis-IDE — Changelog\n\n"
                f"Tags: #{tag}\n\n---\n\n",
                encoding="utf-8",
            )

        file_name = Path(entry.file_path).name
        note_slug = f"{dt.strftime('%Y-%m-%d')}_{file_name.replace('.', '_')}"
        link = f"[[{note_slug}]]"

        log_line = (
            f"- {dt.strftime('%Y-%m-%d %H:%M')} · `{file_name}` · {entry.change_type} · {link}\n"
        )

        existing = changelog.read_text(encoding="utf-8")
        split_marker = "---\n\n"
        idx = existing.find(split_marker)
        if idx != -1:
            new_content = existing[: idx + len(split_marker)] + log_line + existing[idx + len(split_marker) :]
        else:
            new_content = existing + log_line

        changelog.write_text(new_content, encoding="utf-8")

        # 2. Nota individual por archivo (si está habilitado)
        note_path = folder / f"{note_slug}.md"
        if self.config.create_per_file_notes:
            if note_path.exists():
                # Agregar nueva entrada a la nota existente
                note_content = note_path.read_text(encoding="utf-8")
                note_content += (
                    f"\n## {dt.strftime('%H:%M')} — {entry.change_type}\n\n"
                    f"**Tarea:** {entry.agent_task or '—'}\n\n"
                    f"**Descripción:** {entry.description}\n\n"
                    f"**Líneas modificadas:** {entry.lines_changed}\n\n"
                    + (f"**Backup:** `{entry.backup_path}`\n\n" if entry.backup_path else "")
                )
            else:
                note_content = (
                    f"---\n"
                    f"tags: [{tag}]\n"
                    f"fecha: {dt.strftime('%Y-%m-%d')}\n"
                    f"archivo: {entry.file_path}\n"
                    f"---\n\n"
                    f"# {file_name} — {dt.strftime('%Y-%m-%d')}\n\n"
                    f"## {dt.strftime('%H:%M')} — {entry.change_type}\n\n"
                    f"**Tarea:** {entry.agent_task or '—'}\n\n"
                    f"**Descripción:** {entry.description}\n\n"
                    f"**Líneas modificadas:** {entry.lines_changed}\n\n"
                    + (f"**Backup:** `{entry.backup_path}`\n\n" if entry.backup_path else "")
                )
            note_path.write_text(note_content, encoding="utf-8")

        return str(note_path if self.config.create_per_file_notes else changelog)


# ─────────────────────────────────────────────
# Helpers para main.py
# ─────────────────────────────────────────────

def memory_from_dict(d: dict) -> ProjectMemory:
    """Crea un ProjectMemory desde un dict de config (para cargarlo desde JSON/env)."""
    cfg = MemoryConfig(
        enabled=d.get("enabled", False),
        mode=d.get("mode", "json"),
        memory_dir=d.get("memory_dir", "./jarvis_memory"),
        obsidian_folder=d.get("obsidian_folder", ""),
        create_per_file_notes=d.get("create_per_file_notes", True),
        obsidian_tag=d.get("obsidian_tag", "jarvis-ide"),
    )
    return ProjectMemory(cfg)


def memory_config_to_dict(cfg: MemoryConfig) -> dict:
    return asdict(cfg)
