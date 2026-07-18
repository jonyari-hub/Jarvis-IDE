"""
config/config_loader.py
Carga, valida y persiste AgentConfig — v3.0

Cambios respecto a v2:
  - Providers válidos: openai | anthropic | google | nvidia (eliminados openrouter, local).
  - ModelConfig carga headers, timeout y extra_params.
  - merge_runtime_overrides soporta context_manager (add/remove/toggle de extra_items).
  - save_session / load_session: persistencia completa en .jarvis_session.json.
  - ContextManagerState se serializa/deserializa junto con el resto.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.config_schema import (
    AgentConfig,
    AgentBehaviorConfig,
    ContextItem,
    ContextManagerState,
    ModelConfig,
    ProjectPathsConfig,
    UIContextConfig,
    VALID_PROVIDERS,
    PROVIDER_DEFAULT_BASE_URLS,
)


# ──────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────

def _to_path(value: Optional[str]) -> Optional[Path]:
    if not value:
        return None
    return Path(value)


def _resolve_api_key(explicit_key: Optional[str], env_var: str) -> Optional[str]:
    if explicit_key:
        return explicit_key
    return os.environ.get(env_var) if env_var else None


_ENV_KEY_MAP: Dict[str, str] = {
    "openai":    "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google":    "GOOGLE_API_KEY",
    "nvidia":    "NVIDIA_API_KEY",
}


def _load_model_config(data: Dict[str, Any], role: str = "default") -> ModelConfig:
    provider = data.get("provider", "openai")
    env_var = _ENV_KEY_MAP.get(provider, "")
    resolved_key = _resolve_api_key(data.get("api_key"), env_var)

    return ModelConfig(
        provider=provider,
        model_name=data.get("model_name", ""),
        api_key=resolved_key,
        base_url=data.get("base_url") or None,   # "" → None
        temperature=float(data.get("temperature", 0.2)),
        max_tokens=int(data.get("max_tokens", 4000)),
        timeout=int(data.get("timeout", 120)),
        headers=dict(data.get("headers", {})),
        extra_params=dict(data.get("extra_params", {})),
        role=role,
    )


def _load_context_manager(data: Dict[str, Any]) -> ContextManagerState:
    items = [
        ContextItem(
            path=i.get("path", ""),
            label=i.get("label"),
            enabled=bool(i.get("enabled", True)),
            source_type=i.get("source_type", "file"),
        )
        for i in data.get("extra_items", [])
        if i.get("path")
    ]
    return ContextManagerState(
        project_enabled=bool(data.get("project_enabled", True)),
        obsidian_enabled=bool(data.get("obsidian_enabled", True)),
        extra_items=items,
    )


def _dump_model_config(m: ModelConfig) -> Dict[str, Any]:
    return {
        "provider": m.provider,
        "model_name": m.model_name,
        "api_key": m.api_key or "",
        "base_url": m.base_url or "",
        "temperature": m.temperature,
        "max_tokens": m.max_tokens,
        "timeout": m.timeout,
        "headers": m.headers,
        "extra_params": m.extra_params,
        "role": m.role,
    }


def _dump_context_manager(cm: ContextManagerState) -> Dict[str, Any]:
    return {
        "project_enabled": cm.project_enabled,
        "obsidian_enabled": cm.obsidian_enabled,
        "extra_items": [
            {
                "path": item.path,
                "label": item.label,
                "enabled": item.enabled,
                "source_type": item.source_type,
            }
            for item in cm.extra_items
        ],
    }


# ──────────────────────────────────────────────────────────────
# ConfigLoader
# ──────────────────────────────────────────────────────────────

class ConfigLoader:

    # ── Carga ──────────────────────────────────────────────────

    @staticmethod
    def load_from_json_file(path: str | Path) -> AgentConfig:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return ConfigLoader.load_from_dict(data)

    @staticmethod
    def load_from_dict(data: Dict[str, Any]) -> AgentConfig:
        model_data = data.get("model", {})
        model_secondary_data = data.get("model_secondary")
        paths_data = data.get("paths", {})
        behavior_data = data.get("behavior", {})
        ui_data = data.get("ui_context", {})
        ctx_data = data.get("context_manager", {})

        secondary = None
        if model_secondary_data:
            secondary = _load_model_config(
                model_secondary_data,
                role=model_secondary_data.get("role", "surgeon"),
            )

        cfg = AgentConfig(
            model=_load_model_config(
                model_data,
                role=model_data.get("role", "orchestrator"),
            ),
            model_secondary=secondary,
            paths=ProjectPathsConfig(
                project_root=_to_path(paths_data.get("project_root")),
                obsidian_vault=_to_path(paths_data.get("obsidian_vault")),
                skills_root=Path(paths_data.get("skills_root", "skills")),
                prompts_root=Path(paths_data.get("prompts_root", "prompts")),
                output_root=Path(paths_data.get("output_root", "outputs")),
                cache_root=Path(paths_data.get("cache_root", "cache")),
                logs_root=Path(paths_data.get("logs_root", "logs")),
                session_state_file=Path(
                    paths_data.get("session_state_file", ".jarvis_session.json")
                ),
            ),
            behavior=AgentBehaviorConfig(
                allow_obsidian=bool(behavior_data.get("allow_obsidian", True)),
                allow_code_editing=bool(behavior_data.get("allow_code_editing", False)),
                require_edit_approval=bool(behavior_data.get("require_edit_approval", True)),
                include_repo_tree=bool(behavior_data.get("include_repo_tree", True)),
                include_obsidian_context=bool(behavior_data.get("include_obsidian_context", True)),
                include_extra_context=bool(behavior_data.get("include_extra_context", True)),
                max_files_in_context=int(behavior_data.get("max_files_in_context", 8)),
                max_retries=int(behavior_data.get("max_retries", 3)),
                retry_delay_seconds=int(behavior_data.get("retry_delay_seconds", 10)),
                request_timeout_seconds=int(behavior_data.get("request_timeout_seconds", 120)),
            ),
            ui_context=UIContextConfig(
                current_project_name=ui_data.get("current_project_name"),
                notes=ui_data.get("notes"),
                session_id=ui_data.get("session_id"),
            ),
            context_manager=_load_context_manager(ctx_data),
            extra=data.get("extra", {}),
        )

        ConfigLoader._validate(cfg)
        return cfg

    @staticmethod
    def load_defaults() -> AgentConfig:
        return AgentConfig()

    # ── Persistencia de sesión ─────────────────────────────────

    @staticmethod
    def save_session(cfg: AgentConfig, path: Optional[str | Path] = None) -> Path:
        """
        Serializa AgentConfig completo (incluyendo context_manager) a JSON.
        No guarda api_key en disco por seguridad.
        Usa cfg.paths.session_state_file si path es None.
        """
        target = Path(path) if path else cfg.paths.session_state_file

        model_dict = _dump_model_config(cfg.model)
        model_dict["api_key"] = ""   # nunca persistir clave en disco

        secondary_dict = None
        if cfg.model_secondary:
            secondary_dict = _dump_model_config(cfg.model_secondary)
            secondary_dict["api_key"] = ""

        data: Dict[str, Any] = {
            "model": model_dict,
            "model_secondary": secondary_dict,
            "paths": {
                "project_root": str(cfg.paths.project_root or ""),
                "obsidian_vault": str(cfg.paths.obsidian_vault or ""),
                "skills_root": str(cfg.paths.skills_root),
                "prompts_root": str(cfg.paths.prompts_root),
                "output_root": str(cfg.paths.output_root),
                "cache_root": str(cfg.paths.cache_root),
                "logs_root": str(cfg.paths.logs_root),
                "session_state_file": str(cfg.paths.session_state_file),
            },
            "behavior": {
                "allow_obsidian": cfg.behavior.allow_obsidian,
                "allow_code_editing": cfg.behavior.allow_code_editing,
                "require_edit_approval": cfg.behavior.require_edit_approval,
                "include_repo_tree": cfg.behavior.include_repo_tree,
                "include_obsidian_context": cfg.behavior.include_obsidian_context,
                "include_extra_context": cfg.behavior.include_extra_context,
                "max_files_in_context": cfg.behavior.max_files_in_context,
                "max_retries": cfg.behavior.max_retries,
                "retry_delay_seconds": cfg.behavior.retry_delay_seconds,
                "request_timeout_seconds": cfg.behavior.request_timeout_seconds,
            },
            "ui_context": {
                "current_project_name": cfg.ui_context.current_project_name or "",
                "notes": cfg.ui_context.notes or "",
                "session_id": cfg.ui_context.session_id or "",
            },
            "context_manager": _dump_context_manager(cfg.context_manager),
            "extra": cfg.extra,
        }

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[ConfigLoader] Sesión guardada en: {target}")
        return target

    @staticmethod
    def load_session(path: str | Path) -> Optional[AgentConfig]:
        """
        Carga una sesión guardada. Retorna None si no existe o falla.
        Las api_key quedan vacías (el usuario las reingresa en la GUI).
        """
        p = Path(path)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return ConfigLoader.load_from_dict(data)
        except Exception as e:
            print(f"[ConfigLoader] No se pudo cargar sesión {p}: {e}")
            return None

    # ── Overrides en runtime ───────────────────────────────────

    @staticmethod
    def merge_runtime_overrides(base: AgentConfig, overrides: Dict[str, Any]) -> AgentConfig:
        """
        Aplica overrides planos desde la GUI sin tocar el JSON base.

        Claves de modelo (planas):
          provider, model_name, api_key, base_url, temperature, max_tokens,
          timeout, headers, extra_params

        Claves de rutas:
          project_root, obsidian_vault

        Claves de comportamiento:
          allow_code_editing, allow_obsidian, include_extra_context

        Claves de contexto (acciones sobre context_manager):
          context_add_item      → {"path": ..., "label": ...}
          context_remove_item   → {"path": ...}
          context_toggle_item   → {"path": ...}
          context_project_enabled  → bool
          context_obsidian_enabled → bool

        Modelo secundario:
          model_secondary → dict completo
        """
        # Rutas
        if "project_root" in overrides:
            base.paths.project_root = _to_path(overrides["project_root"])
        if "obsidian_vault" in overrides:
            base.paths.obsidian_vault = _to_path(overrides["obsidian_vault"])

        # Modelo principal
        if "provider" in overrides:
            base.model.provider = overrides["provider"]
        if "model_name" in overrides:
            base.model.model_name = overrides["model_name"]
        if "api_key" in overrides:
            base.model.api_key = overrides["api_key"]
        if "base_url" in overrides:
            base.model.base_url = overrides["base_url"] or None
        if "temperature" in overrides:
            base.model.temperature = float(overrides["temperature"])
        if "max_tokens" in overrides:
            base.model.max_tokens = int(overrides["max_tokens"])
        if "timeout" in overrides:
            base.model.timeout = int(overrides["timeout"])
        if "headers" in overrides:
            base.model.headers = dict(overrides["headers"])
        if "extra_params" in overrides:
            base.model.extra_params = dict(overrides["extra_params"])

        # Comportamiento
        if "allow_code_editing" in overrides:
            base.behavior.allow_code_editing = bool(overrides["allow_code_editing"])
        if "allow_obsidian" in overrides:
            base.behavior.allow_obsidian = bool(overrides["allow_obsidian"])
        if "include_extra_context" in overrides:
            base.behavior.include_extra_context = bool(overrides["include_extra_context"])

        # UI
        if "current_project_name" in overrides:
            base.ui_context.current_project_name = overrides["current_project_name"]
        if "session_id" in overrides:
            base.ui_context.session_id = overrides["session_id"]

        # Modelo secundario
        if "model_secondary" in overrides:
            sec = overrides["model_secondary"]
            if sec:
                base.model_secondary = _load_model_config(
                    sec, role=sec.get("role", "surgeon")
                )
            else:
                base.model_secondary = None

        # Context manager — operaciones
        if "context_add_item" in overrides:
            item_data = overrides["context_add_item"]
            base.context_manager.add_item(
                path=item_data.get("path", ""),
                label=item_data.get("label"),
            )
        if "context_remove_item" in overrides:
            base.context_manager.remove_item(overrides["context_remove_item"].get("path", ""))
        if "context_toggle_item" in overrides:
            base.context_manager.toggle_item(overrides["context_toggle_item"].get("path", ""))
        if "context_project_enabled" in overrides:
            base.context_manager.project_enabled = bool(overrides["context_project_enabled"])
        if "context_obsidian_enabled" in overrides:
            base.context_manager.obsidian_enabled = bool(overrides["context_obsidian_enabled"])

        return base

    # ── Validación ─────────────────────────────────────────────

    @staticmethod
    def _validate(cfg: AgentConfig) -> None:
        if cfg.model.provider not in VALID_PROVIDERS:
            raise ValueError(
                f"Provider desconocido: '{cfg.model.provider}'. "
                f"Valores válidos: {sorted(VALID_PROVIDERS)}"
            )
        if cfg.behavior.max_files_in_context < 1:
            raise ValueError("max_files_in_context debe ser >= 1")
        if cfg.behavior.request_timeout_seconds < 10:
            raise ValueError("request_timeout_seconds debe ser >= 10")
