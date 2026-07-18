"""
agent/context_builder.py
Construye el prompt final que va al LLM.

Cambios respecto a la versión anterior:
  - system_base_path viene de RuntimePaths, no de un string hardcodeado.
  - SkillLoader recibe RuntimePaths, no una raíz fija.
  - BuildContextInput acepta opcionalmente un AgentConfig para derivar rutas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from agent.runtime_paths import RuntimePaths
from agent.skill_loader import SkillLoader, SkillDefinition
from agent.skill_router import TaskContext


# ──────────────────────────────────────────────────────────────
# Modelos de datos de entrada
# ──────────────────────────────────────────────────────────────

@dataclass
class FileArtifact:
    path: str
    content: str


@dataclass
class AnalysisArtifacts:
    """Resultados previos opcionales producidos por el pipeline."""
    impact_summary: Optional[str] = None
    diagnosis_summary: Optional[str] = None
    traceback_summary: Optional[str] = None
    symbol_usage_summary: Optional[str] = None
    dead_code_summary: Optional[str] = None
    config_validation_summary: Optional[str] = None


@dataclass
class BuildContextInput:
    task: TaskContext
    active_skills: List[str]
    runtime_paths: RuntimePaths                  # ← viene de build_runtime_paths(cfg)

    # Archivos concretos a inyectar
    files: List[FileArtifact] = field(default_factory=list)

    # Resultados previos
    analysis: AnalysisArtifacts = field(default_factory=AnalysisArtifacts)

    # Árbol del repo (texto plano)
    repo_tree_text: Optional[str] = None

    # Notas extra desde la GUI
    extra_notes: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# Builder
# ──────────────────────────────────────────────────────────────

class ContextBuilder:
    """Construye el prompt final para el LLM."""

    def __init__(self, skill_loader: SkillLoader):
        self.skill_loader = skill_loader

    def build(self, ctx: BuildContextInput) -> str:
        rp = ctx.runtime_paths

        # Prompt base desde RuntimePaths (no hardcodeado)
        system_base_path = rp.system_base_prompt_path()
        system_base = self._read_text_file_safe(system_base_path)

        skill_defs = self.skill_loader.load_many(ctx.active_skills)

        sections: List[str] = []

        sections.append(self._section("SYSTEM_BASE", system_base.strip()))
        sections.append(self._section("TASK", self._render_task(ctx.task)))
        sections.append(self._section("OPERATIONAL_STATE", self._render_operational_state(ctx.task)))
        sections.append(self._section("ACTIVE_SKILLS", self._render_skills(skill_defs)))

        prior = self._render_prior_analysis(ctx.analysis)
        if prior:
            sections.append(self._section("PRIOR_ANALYSIS", prior))

        if ctx.task.traceback_text:
            sections.append(self._section("TRACEBACK", ctx.task.traceback_text.strip()))

        if ctx.repo_tree_text:
            sections.append(self._section("REPO_TREE", ctx.repo_tree_text.strip()))

        if ctx.files:
            sections.append(self._section("FILES", self._render_files(ctx.files)))

        if ctx.extra_notes:
            sections.append(self._section("EXTRA_NOTES", ctx.extra_notes.strip()))

        sections.append(self._section("FINAL_INSTRUCTIONS", self._final_instructions()))

        return "\n\n".join(sections)

    # ──────────────────────────────────────────────────────────
    # Renderers
    # ──────────────────────────────────────────────────────────

    def _render_task(self, task: TaskContext) -> str:
        lines = [
            f"user_request: {task.user_request}",
            f"target_files: {task.target_files or []}",
            f"target_symbols: {task.target_symbols or []}",
            f"config_files: {task.config_files or []}",
            f"wants_fix: {task.wants_fix}",
            f"wants_review: {task.wants_review}",
            f"wants_usage_search: {task.wants_usage_search}",
            f"wants_dead_code_audit: {task.wants_dead_code_audit}",
            f"wants_typo_fix: {task.wants_typo_fix}",
            f"wants_config_validation: {task.wants_config_validation}",
            f"wants_impact_analysis: {task.wants_impact_analysis}",
            f"has_python_files: {task.has_python_files}",
        ]
        return "\n".join(lines)

    def _render_operational_state(self, task: TaskContext) -> str:
        lines = [
            f"diagnosis_available: {task.diagnosis_available}",
            f"impact_analysis_available: {task.impact_analysis_available}",
            f"explicit_edit_approval: {task.explicit_edit_approval}",
        ]
        return "\n".join(lines)

    def _render_skills(self, skill_defs: List[SkillDefinition]) -> str:
        chunks = []
        for skill in skill_defs:
            chunks.append(
                f"--- SKILL: {skill.name} ---\n"
                f"path: {skill.path}\n\n"
                f"{skill.content.strip()}"
            )
        return "\n\n".join(chunks)

    def _render_prior_analysis(self, analysis: AnalysisArtifacts) -> str:
        parts = []
        mapping = [
            ("impact_summary",            "[impact_summary]"),
            ("diagnosis_summary",         "[diagnosis_summary]"),
            ("traceback_summary",         "[traceback_summary]"),
            ("symbol_usage_summary",      "[symbol_usage_summary]"),
            ("dead_code_summary",         "[dead_code_summary]"),
            ("config_validation_summary", "[config_validation_summary]"),
        ]
        for attr, label in mapping:
            val = getattr(analysis, attr)
            if val:
                parts.append(f"{label}\n{val.strip()}")
        return "\n\n".join(parts)

    def _render_files(self, files: List[FileArtifact]) -> str:
        chunks = []
        for f in files:
            chunks.append(f"--- FILE: {f.path} ---\n{f.content.rstrip()}")
        return "\n\n".join(chunks)

    def _final_instructions(self) -> str:
        return (
            "Use the active skills as operating procedures, not as decorative text.\n"
            "Respect their limits, validations, and expected output sections.\n"
            "Do not edit files unless an editing skill is active and explicit_edit_approval is true.\n"
            "Prefer minimal, verifiable reasoning grounded in the provided files and prior analysis.\n"
            "If the provided context is insufficient, say exactly what is missing instead of inventing details."
        )

    # ──────────────────────────────────────────────────────────
    # Utils
    # ──────────────────────────────────────────────────────────

    def _read_text_file_safe(self, path: Path) -> str:
        """Lee el archivo o retorna un placeholder si no existe."""
        if not path.exists():
            return f"[system_base.md no encontrado en {path}]"
        return path.read_text(encoding="utf-8")

    def _section(self, title: str, body: str) -> str:
        return f"===== {title} =====\n{body}"
