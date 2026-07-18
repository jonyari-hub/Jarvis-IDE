"""
agent/runtime_paths.py
Resuelve y valida las rutas en tiempo de ejecución a partir de AgentConfig.

El resto del sistema solo habla con RuntimePaths, nunca con strings o
rutas hardcodeadas. Esto permite que la GUI cambie el proyecto sin
reiniciar el proceso.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config.config_schema import AgentConfig


@dataclass
class RuntimePaths:
    """
    Rutas ya resueltas y validadas.
    Si project_root es None el agente puede arrancar pero no leerá código.
    Si obsidian_vault es None se omite toda la lógica de Obsidian.
    """
    project_root: Optional[Path]
    obsidian_vault: Optional[Path]
    skills_root: Path
    prompts_root: Path
    output_root: Path
    cache_root: Path
    logs_root: Path

    # ── conveniencias ──────────────────────────────────────────

    def obsidian_modules_dir(self) -> Optional[Path]:
        """Subcarpeta 'modulos' dentro del vault (convención del sistema)."""
        if self.obsidian_vault is None:
            return None
        return self.obsidian_vault

    def ensure_output_dirs(self) -> None:
        """Crea los directorios de salida si no existen. Llama antes del pipeline."""
        for d in (self.output_root, self.cache_root, self.logs_root):
            d.mkdir(parents=True, exist_ok=True)

    def find_file_in_project(self, filename: str) -> Optional[Path]:
        """
        Busca filename en cualquier nivel dentro de project_root.
        Si filename es una ruta absoluta válida, la retorna directamente.
        Si no hay project_root, intenta resolverlo como ruta absoluta.
        Retorna la primera coincidencia o None.
        """
        # Si es ruta absoluta existente, usarla directamente
        candidate = Path(filename)
        if candidate.is_absolute() and candidate.exists():
            return candidate

        # Si hay project_root, buscar recursivamente
        if self.project_root and self.project_root.exists():
            matches = list(self.project_root.rglob(filename))
            matches = [m for m in matches if "__pycache__" not in str(m)]
            if matches:
                return matches[0]

        # Fallback: buscar relativo al CWD
        cwd_candidate = Path.cwd() / filename
        if cwd_candidate.exists():
            return cwd_candidate

        return None

    def iter_python_files(self):
        """Generador de todos los .py del proyecto (excluye __pycache__)."""
        if not self.project_root or not self.project_root.exists():
            return
        for path in self.project_root.rglob("*.py"):
            if "__pycache__" not in str(path):
                yield path

    def obsidian_note_path(self, module_name: str) -> Optional[Path]:
        """Retorna la ruta de la nota .md para un módulo dado, o None si no hay vault."""
        vault_dir = self.obsidian_modules_dir()
        if vault_dir is None:
            return None
        return vault_dir / f"{module_name}.md"

    def skills_path(self, skill_name: str) -> Path:
        """Retorna la ruta esperada de un skill .md."""
        return self.skills_root / f"{skill_name}.md"

    def system_base_prompt_path(self) -> Path:
        """Retorna la ruta del prompt base del sistema."""
        return self.prompts_root / "system_base.md"


def build_runtime_paths(cfg: AgentConfig) -> RuntimePaths:
    """
    Punto de entrada único para construir RuntimePaths desde AgentConfig.
    Valida la existencia de rutas críticas si están definidas.
    """
    rp = RuntimePaths(
        project_root=cfg.paths.project_root,
        obsidian_vault=cfg.paths.obsidian_vault if cfg.behavior.allow_obsidian else None,
        skills_root=cfg.paths.skills_root,
        prompts_root=cfg.paths.prompts_root,
        output_root=cfg.paths.output_root,
        cache_root=cfg.paths.cache_root,
        logs_root=cfg.paths.logs_root,
    )

    _warn_missing(rp)
    return rp


def _warn_missing(rp: RuntimePaths) -> None:
    """
    Emite advertencias (print) si rutas configuradas no existen en disco.
    No lanza excepción para no bloquear el arranque de la GUI.
    """
    if rp.project_root and not rp.project_root.exists():
        print(f"[RuntimePaths] Advertencia: project_root no existe: {rp.project_root}")

    if rp.obsidian_vault and not rp.obsidian_vault.exists():
        print(f"[RuntimePaths] Advertencia: obsidian_vault no existe: {rp.obsidian_vault}")

    if not rp.skills_root.exists():
        print(f"[RuntimePaths] Advertencia: skills_root no existe: {rp.skills_root}")

    if not rp.prompts_root.exists():
        print(f"[RuntimePaths] Advertencia: prompts_root no existe: {rp.prompts_root}")
