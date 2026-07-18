"""
agent/skill_router.py
Decide qué skills activar según el estado de la tarea.

Sin rutas hardcodeadas. Sin dependencia de config global.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any


# ──────────────────────────────────────────────────────────────
# Modelo de entrada
# ──────────────────────────────────────────────────────────────

@dataclass
class TaskContext:
    """
    Describe el pedido actual del usuario y el estado de la tarea.
    Lo construye el backend antes de invocar el router.
    """
    user_request: str

    # Artefactos de entrada
    target_files: List[str] = field(default_factory=list)
    target_symbols: List[str] = field(default_factory=list)
    traceback_text: Optional[str] = None
    config_files: List[str] = field(default_factory=list)

    # Intenciones detectadas
    wants_fix: bool = False
    wants_review: bool = False
    wants_usage_search: bool = False
    wants_dead_code_audit: bool = False
    wants_typo_fix: bool = False
    wants_config_validation: bool = False
    wants_impact_analysis: bool = False

    # Contexto de stack / lenguaje
    has_python_files: bool = False

    # Estado del flujo
    diagnosis_available: bool = False
    impact_analysis_available: bool = False
    explicit_edit_approval: bool = False

    # Metadatos opcionales
    extra: Dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────

class SkillRouter:
    """
    Recibe un TaskContext y devuelve la lista ordenada de skills a activar.
    """

    MAP_CHANGE_IMPACT      = "map_change_impact"
    AUDIT_PYTHON_MODULE    = "audit_python_module"
    ANALYZE_TRACEBACK      = "analyze_traceback"
    APPLY_LOCAL_FIX        = "apply_local_fix"
    FIND_SYMBOL_USAGE      = "find_symbol_usage"
    FIND_DEAD_CODE         = "find_dead_code"
    SAFE_TYPO_FIX          = "safe_typo_fix"
    VALIDATE_CONFIG_FILE   = "validate_config_file"

    def route(self, ctx: TaskContext) -> List[str]:
        skills: List[str] = []

        if ctx.traceback_text:
            self._add(skills, self.ANALYZE_TRACEBACK)

        if ctx.wants_usage_search or ctx.target_symbols:
            self._add(skills, self.FIND_SYMBOL_USAGE)

        if ctx.wants_dead_code_audit:
            self._add(skills, self.FIND_DEAD_CODE)

        if ctx.wants_config_validation or ctx.config_files:
            self._add(skills, self.VALIDATE_CONFIG_FILE)

        if (
            ctx.wants_impact_analysis
            or ctx.wants_fix
            or (ctx.target_files and not ctx.traceback_text and not ctx.wants_typo_fix)
        ):
            self._add(skills, self.MAP_CHANGE_IMPACT)

        if ctx.has_python_files and (ctx.wants_review or ctx.wants_fix or ctx.traceback_text):
            self._add(skills, self.AUDIT_PYTHON_MODULE)

        if ctx.wants_typo_fix:
            self._add(skills, self.SAFE_TYPO_FIX)

        if ctx.wants_fix and ctx.explicit_edit_approval and ctx.diagnosis_available:
            if not ctx.impact_analysis_available:
                self._add(skills, self.MAP_CHANGE_IMPACT)
            self._add(skills, self.APPLY_LOCAL_FIX)

        return self._normalize_order(skills)

    def _add(self, skills: List[str], name: str) -> None:
        if name not in skills:
            skills.append(name)

    def _normalize_order(self, skills: List[str]) -> List[str]:
        order = [
            self.ANALYZE_TRACEBACK,
            self.FIND_SYMBOL_USAGE,
            self.VALIDATE_CONFIG_FILE,
            self.FIND_DEAD_CODE,
            self.MAP_CHANGE_IMPACT,
            self.AUDIT_PYTHON_MODULE,
            self.SAFE_TYPO_FIX,
            self.APPLY_LOCAL_FIX,
        ]
        return [s for s in order if s in skills]


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def infer_python_presence(files: List[str]) -> bool:
    return any(Path(f).suffix.lower() == ".py" for f in files)


def infer_config_files(files: List[str]) -> List[str]:
    config_exts = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"}
    return [f for f in files if Path(f).suffix.lower() in config_exts or Path(f).name == ".env"]
