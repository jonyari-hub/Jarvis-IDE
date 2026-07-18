"""
agent/skill_loader.py
Carga skills desde archivos .md.
La raíz de búsqueda viene de RuntimePaths, nunca hardcodeada.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from agent.runtime_paths import RuntimePaths


@dataclass
class SkillDefinition:
    name: str
    path: Path
    content: str


class SkillLoader:
    """
    Carga skills desde archivos .md dentro de RuntimePaths.skills_root.
    Incluye cache en memoria para no releer disco en cada llamada.
    """

    def __init__(self, rp: RuntimePaths):
        self.skills_root = rp.skills_root
        if not self.skills_root.exists():
            raise FileNotFoundError(f"skills_root no encontrado: {self.skills_root}")
        self._cache: Dict[str, SkillDefinition] = {}

    def load_skill(self, skill_name: str) -> SkillDefinition:
        if skill_name in self._cache:
            return self._cache[skill_name]

        skill_path = self._find_skill_file(skill_name)
        if skill_path is None:
            raise FileNotFoundError(f"Skill '{skill_name}' no encontrada en {self.skills_root}")

        content = skill_path.read_text(encoding="utf-8")
        self._basic_validate(skill_name, content, skill_path)

        skill = SkillDefinition(name=skill_name, path=skill_path, content=content)
        self._cache[skill_name] = skill
        return skill

    def load_many(self, skill_names: List[str]) -> List[SkillDefinition]:
        return [self.load_skill(name) for name in skill_names]

    def invalidate_cache(self) -> None:
        """Útil si el usuario cambia la skills_root en la GUI."""
        self._cache.clear()

    def _find_skill_file(self, skill_name: str) -> Optional[Path]:
        matches = list(self.skills_root.rglob(f"{skill_name}.md"))
        return matches[0] if matches else None

    def _basic_validate(self, skill_name: str, content: str, path: Path) -> None:
        lowered = content.lower()
        required = [
            f"# skill: {skill_name}".lower(),
            "## objective",
            "## when_to_activate",
            "## required_inputs",
            "## allowed_tools",
            "## procedure",
            "## validations",
            "## expected_output",
            "## limits",
        ]
        missing = [m for m in required if m not in lowered]
        if missing:
            raise ValueError(
                f"Skill {path} faltan secciones: {', '.join(missing)}"
            )
