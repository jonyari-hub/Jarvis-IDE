"""agent package — pipeline, routing, context, and LLM client."""
from agent.runtime_paths import RuntimePaths, build_runtime_paths
from agent.skill_router import SkillRouter, TaskContext, infer_python_presence, infer_config_files
from agent.skill_loader import SkillLoader, SkillDefinition
from agent.context_builder import ContextBuilder, BuildContextInput, FileArtifact, AnalysisArtifacts
from agent.llm_client_factory import call_chat, call_with_retry, invalidate_client_cache
from agent.agent_corrector import ejecutar_pipeline_coordinado

__all__ = [
    "RuntimePaths", "build_runtime_paths",
    "SkillRouter", "TaskContext", "infer_python_presence", "infer_config_files",
    "SkillLoader", "SkillDefinition",
    "ContextBuilder", "BuildContextInput", "FileArtifact", "AnalysisArtifacts",
    "call_chat", "call_with_retry", "invalidate_client_cache",
    "ejecutar_pipeline_coordinado",
]
