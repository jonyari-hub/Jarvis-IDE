"""
config/config_schema.py
Modelo de configuración central del agente J.A.R.V.I.S. — v3.0

Cambios respecto a v2:
  - ModelConfig ampliado: headers, timeout propio, extra_params.
  - Providers reducidos a: openai | anthropic | google | nvidia.
  - ProjectPathsConfig agrega session_state_file para persistencia.
  - AgentConfig agrega context_manager (ContextManagerState).
  - ContextManagerState gestiona las tres fuentes de contexto:
      1. project_root  2. obsidian_vault  3. extra_items (nueva)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List


# ──────────────────────────────────────────────────────────────
# Providers válidos (reducido a los 4 oficiales)
# ──────────────────────────────────────────────────────────────

VALID_PROVIDERS = {"openai", "anthropic", "google", "nvidia"}

# Base URLs por defecto — sobreescribibles en ModelConfig.base_url
PROVIDER_DEFAULT_BASE_URLS: Dict[str, str] = {
    "openai":    "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "google":    "https://generativelanguage.googleapis.com/v1beta/openai",
    "nvidia":    "https://integrate.api.nvidia.com/v1",
}


# ──────────────────────────────────────────────────────────────
# ModelConfig
# ──────────────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    """
    Configuración desacoplada de proveedor + modelo.

    Cada instancia es un objeto completo con todo lo necesario para crear
    el cliente LLM. La base_url se toma de PROVIDER_DEFAULT_BASE_URLS si
    no se especifica una custom, evitando que quede hardcodeada en el factory.
    """
    provider: str = "openai"           # openai | anthropic | google | nvidia
    model_name: str = ""
    api_key: Optional[str] = None
    base_url: Optional[str] = None     # None → usar default del provider
    temperature: float = 0.2
    max_tokens: int = 4000
    timeout: int = 120                 # timeout propio de este modelo (segundos)
    headers: Dict[str, str] = field(default_factory=dict)       # headers HTTP adicionales
    extra_params: Dict[str, Any] = field(default_factory=dict)  # top_p, seed, etc.
    role: str = "default"              # default | orchestrator | surgeon

    def effective_base_url(self) -> str:
        """Retorna la base_url efectiva: custom si existe, o el default del provider."""
        if self.base_url:
            return self.base_url.rstrip("/")
        return PROVIDER_DEFAULT_BASE_URLS.get(self.provider, "").rstrip("/")


# ──────────────────────────────────────────────────────────────
# ContextItem — elemento de la tercera fuente de contexto
# ──────────────────────────────────────────────────────────────

@dataclass
class ContextItem:
    """
    Archivo o documento de la fuente 'Información adicional'.
    Puede ser .py, .md, .pdf, .txt, etc.
    """
    path: str                          # ruta absoluta
    label: Optional[str] = None        # nombre display (se infiere del path si es None)
    enabled: bool = True
    source_type: str = "file"          # file | snippet

    def display_label(self) -> str:
        return self.label or Path(self.path).name


# ──────────────────────────────────────────────────────────────
# ContextManagerState
# ──────────────────────────────────────────────────────────────

@dataclass
class ContextManagerState:
    """
    Estado del administrador de contexto. Se persiste en disco junto con
    la configuración del proyecto para restaurar el estado entre sesiones.

    Fuentes:
      1. project_root   → resuelto por ProjectPathsConfig
      2. obsidian_vault → resuelto por ProjectPathsConfig
      3. extra_items    → lista gestionada aquí
    """
    project_enabled: bool = True
    obsidian_enabled: bool = True
    extra_items: List[ContextItem] = field(default_factory=list)

    def active_extra_items(self) -> List[ContextItem]:
        return [item for item in self.extra_items if item.enabled]

    def add_item(self, path: str, label: Optional[str] = None) -> ContextItem:
        """Agrega un ítem si no existe ya. Retorna el ítem (nuevo o existente)."""
        existing = next((i for i in self.extra_items if i.path == path), None)
        if existing:
            return existing
        item = ContextItem(path=path, label=label)
        self.extra_items.append(item)
        return item

    def remove_item(self, path: str) -> bool:
        before = len(self.extra_items)
        self.extra_items = [i for i in self.extra_items if i.path != path]
        return len(self.extra_items) < before

    def toggle_item(self, path: str) -> Optional[bool]:
        """Alterna enabled. Retorna el nuevo estado o None si no existe."""
        for item in self.extra_items:
            if item.path == path:
                item.enabled = not item.enabled
                return item.enabled
        return None


# ──────────────────────────────────────────────────────────────
# ProjectPathsConfig
# ──────────────────────────────────────────────────────────────

@dataclass
class ProjectPathsConfig:
    """Rutas de trabajo. Todas son opcionales o tienen defaults seguros."""
    project_root: Optional[Path] = None
    obsidian_vault: Optional[Path] = None
    skills_root: Path = field(default_factory=lambda: Path("skills"))
    prompts_root: Path = field(default_factory=lambda: Path("prompts"))
    output_root: Path = field(default_factory=lambda: Path("outputs"))
    cache_root: Path = field(default_factory=lambda: Path("cache"))
    logs_root: Path = field(default_factory=lambda: Path("logs"))
    # Archivo de estado persistente del proyecto (rutas + contexto + config)
    session_state_file: Path = field(default_factory=lambda: Path(".jarvis_session.json"))


# ──────────────────────────────────────────────────────────────
# AgentBehaviorConfig
# ──────────────────────────────────────────────────────────────

@dataclass
class AgentBehaviorConfig:
    """Flags de comportamiento del agente."""
    allow_obsidian: bool = True
    allow_code_editing: bool = False
    require_edit_approval: bool = True
    include_repo_tree: bool = True
    include_obsidian_context: bool = True
    include_extra_context: bool = True      # activar/desactivar tercera fuente
    max_files_in_context: int = 8
    max_retries: int = 3
    retry_delay_seconds: int = 10
    request_timeout_seconds: int = 120


# ──────────────────────────────────────────────────────────────
# UIContextConfig
# ──────────────────────────────────────────────────────────────

@dataclass
class UIContextConfig:
    """Metadatos que la GUI puede adjuntar a la sesión."""
    current_project_name: Optional[str] = None
    notes: Optional[str] = None
    session_id: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# AgentConfig — modelo raíz
# ──────────────────────────────────────────────────────────────

@dataclass
class AgentConfig:
    """
    Configuración completa de una sesión del agente J.A.R.V.I.S.

    La GUI construye este objeto y lo pasa al backend.
    El backend lo convierte en RuntimePaths + clientes LLM.
    Nada en el código usa rutas o claves directamente.
    """
    model: ModelConfig = field(default_factory=ModelConfig)
    model_secondary: Optional[ModelConfig] = None

    paths: ProjectPathsConfig = field(default_factory=ProjectPathsConfig)
    behavior: AgentBehaviorConfig = field(default_factory=AgentBehaviorConfig)
    ui_context: UIContextConfig = field(default_factory=UIContextConfig)
    context_manager: ContextManagerState = field(default_factory=ContextManagerState)

    extra: Dict[str, Any] = field(default_factory=dict)

    # ── Selección de modelo ────────────────────────────────────

    def get_orchestrator_model(self) -> ModelConfig:
        if self.model.role == "orchestrator":
            return self.model
        if self.model_secondary and self.model_secondary.role == "orchestrator":
            return self.model_secondary
        return self.model

    def get_surgeon_model(self) -> ModelConfig:
        if self.model_secondary and self.model_secondary.role == "surgeon":
            return self.model_secondary
        if self.model.role == "surgeon":
            return self.model
        return self.model

    # ── Contexto unificado ─────────────────────────────────────

    def get_active_extra_context_paths(self) -> List[Path]:
        """Retorna los paths activos de la tercera fuente de contexto."""
        if not self.behavior.include_extra_context:
            return []
        return [
            Path(item.path)
            for item in self.context_manager.active_extra_items()
            if Path(item.path).exists()
        ]
