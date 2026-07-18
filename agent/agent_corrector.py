"""
agent/agent_corrector.py
Pipeline cognitivo autónomo J.A.R.V.I.S.

CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
  - Sin rutas hardcodeadas.
  - Sin claves de API en el código.
  - Sin dependencia de un vault o proyecto fijo.
  - Todo viene de AgentConfig → RuntimePaths.
  - El cliente LLM se construye via llm_client_factory según el provider configurado.
  - Las fases son funciones puras que reciben config y paths como parámetros.
"""
from __future__ import annotations

import os
import re
import json
import time
from pathlib import Path
from typing import Optional

from config.config_schema import AgentConfig
from agent.runtime_paths import RuntimePaths, build_runtime_paths
from agent.llm_client_factory import call_with_retry, call_chat_raw


# ──────────────────────────────────────────────────────────────
# Extracción local (sin IA, sin red)
# ──────────────────────────────────────────────────────────────

def extraer_dependencias_python(contenido_codigo: str) -> list[str]:
    """Extrae imports del código Python para actualizar el grafo."""
    patron = re.compile(r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)', re.MULTILINE)
    return list(set(patron.findall(contenido_codigo)))


def obtener_nombres_proyecto(rp: RuntimePaths) -> set[str]:
    """Retorna el conjunto de stems .py del proyecto actual."""
    nombres: set[str] = set()
    for path in rp.iter_python_files():
        nombres.add(path.stem)
    return nombres


def limpiar_codigo_markdown(texto_ia: str) -> str:
    """Extrae el bloque de código más grande de una respuesta markdown."""
    bloques = re.findall(r'```(?:python)?\s*\n?(.*?)```', texto_ia, re.DOTALL | re.IGNORECASE)
    if bloques:
        return max(bloques, key=len).strip()
    return texto_ia.strip().strip('`').strip()


# ──────────────────────────────────────────────────────────────
# Gestión de memoria Obsidian (dinámica, sin rutas fijas)
# ──────────────────────────────────────────────────────────────

def leer_contexto_obsidian(nombre_modulo: str, rp: RuntimePaths) -> str:
    """Lee la nota .md de Obsidian para el módulo dado."""
    nota = rp.obsidian_note_path(nombre_modulo)
    if nota and nota.exists():
        return nota.read_text(encoding="utf-8")
    return f"Módulo '{nombre_modulo}' no documentado / cobertura parcial del vault."


def actualizar_nota_obsidian(
    nombre_modulo: str,
    ruta_relativa: Path,
    codigo_actual: str,
    rp: RuntimePaths,
) -> None:
    """Reescribe la nota de Obsidian con el estado actual del módulo."""
    nota_path = rp.obsidian_note_path(nombre_modulo)
    if nota_path is None:
        return   # Obsidian desactivado en esta sesión

    descripcion_previa = "Módulo en ejecución dentro del sistema autónomo."
    if nota_path.exists():
        try:
            texto = nota_path.read_text(encoding="utf-8")
            match = re.search(r"## Responsabilidad\n(.*?)\n\n##", texto, re.DOTALL)
            if match:
                descripcion_previa = match.group(1).strip()
        except Exception:
            pass

    deps_crudas = extraer_dependencias_python(codigo_actual)
    nombres_validos = obtener_nombres_proyecto(rp)
    deps_filtradas = sorted(
        d for d in deps_crudas if d in nombres_validos and d != nombre_modulo
    )

    md = f"# Módulo: {nombre_modulo}\n\n"
    md += f"**Ruta local en disco:** `{ruta_relativa}`\n\n"
    md += f"## Responsabilidad\n{descripcion_previa}\n\n"
    md += "## Dependencias e Interconexiones\n"

    if deps_filtradas:
        for dep in deps_filtradas:
            md += f"- Relacionado con: [[{dep}]]\n"
    else:
        md += "- No se detectaron dependencias locales directas.\n"

    nota_path.parent.mkdir(parents=True, exist_ok=True)
    nota_path.write_text(md, encoding="utf-8")
    print(f"[Grafo Sync] Nota Obsidian actualizada: {nota_path.name}")


# ──────────────────────────────────────────────────────────────
# FASE 0 — Indexador de arquitectura (obsidian_mapper)
# ──────────────────────────────────────────────────────────────

def fase_0_obsidian_mapper(
    cfg: AgentConfig,
    rp: RuntimePaths,
    archivo_objetivo: Optional[str] = None,
) -> dict:
    """
    Escanea el proyecto y el vault de Obsidian.
    Pre-sincroniza la nota del archivo objetivo si se especifica.
    Retorna el mapa estructural que se pasa a las fases siguientes.
    """
    print("[Fase 0] Ejecutando obsidian_mapper...")

    archivos_codigo: set[str] = set()

    # ── Modo standalone: sin project_root, devolver mapa vacío y continuar ──
    if not rp.project_root or not rp.project_root.exists():
        print(f"[Mapper] Sin project_root — modo standalone (archivo suelto / adjunto).")
        return {
            "cobertura_parcial_vault_modulos_no_documentados": [],
            "documentacion_desfasada_modulos_pendientes": [],
            "total_modulos_codigo": 0,
            "total_notas_memoria": 0,
            "mode": "standalone",
        }

    for py_path in rp.iter_python_files():
        stem = py_path.stem
        archivos_codigo.add(stem)

        if archivo_objetivo and py_path.name == archivo_objetivo:
            try:
                cod = py_path.read_text(encoding="utf-8")
                rel = py_path.relative_to(rp.project_root)
                actualizar_nota_obsidian(stem, rel, cod, rp)
            except Exception as e:
                print(f"[Mapper] No se pudo pre-sincronizar {py_path.name}: {e}")

    notas_obsidian: set[str] = set()
    vault_dir = rp.obsidian_modules_dir()
    if vault_dir and vault_dir.exists():
        for archivo in vault_dir.iterdir():
            if archivo.suffix == ".md":
                notas_obsidian.add(archivo.stem)

    cobertura_parcial = archivos_codigo - notas_obsidian
    doc_desfasada = notas_obsidian - archivos_codigo

    return {
        "cobertura_parcial_vault_modulos_no_documentados": sorted(cobertura_parcial),
        "documentacion_desfasada_modulos_pendientes": sorted(doc_desfasada),
        "total_modulos_codigo": len(archivos_codigo),
        "total_notas_memoria": len(notas_obsidian),
    }


# ──────────────────────────────────────────────────────────────
# FASE 1 — Orquestador cognitivo (impact_analyzer)
# ──────────────────────────────────────────────────────────────

def fase_impact_analyzer(
    problema: str,
    esperado: str,
    sintomas: str,
    mapa_estructural: dict,
    cfg: AgentConfig,
) -> Optional[str]:
    """
    Genera el diagnóstico de impacto usando el modelo orquestador.
    Funciona con cualquier provider configurado en cfg.
    """
    print(f"[Fase 1] Ejecutando impact_analyzer con {cfg.model.provider}/{cfg.get_orchestrator_model().model_name}...")

    # Modo standalone: indicarlo en el prompt
    modo = mapa_estructural.get("mode", "project")
    contexto_proyecto = (
        json.dumps(mapa_estructural, indent=2)
        if modo != "standalone"
        else "Sin proyecto cargado — modo archivo suelto / adjunto."
    )

    # Contexto adicional (archivos adjuntos desde la GUI)
    archivos_adicionales = cfg.extra.get("additional_context", [])
    bloque_adicional = ""
    if archivos_adicionales:
        bloque_adicional = "\n\n# ARCHIVOS ADICIONALES DE CONTEXTO:\n"
        for af in archivos_adicionales:
            bloque_adicional += f"\n--- {af.get('name','archivo')} ---\n{af.get('content','')[:2000]}\n"

    prompt = (
        "Actuás como el Orquestador Central y Arquitecto del sistema de IA modular.\n"
        "Tu tarea es recibir un problema reportado, cruzarlo con el contexto disponible "
        "y generar un diagnóstico de impacto técnico riguroso.\n\n"
        f"# CONTEXTO DEL PROYECTO:\n{contexto_proyecto}\n"
        f"{bloque_adicional}\n"
        f"# ENTRADA DEL PROBLEMA:\n"
        f"- Problema reportado: {problema}\n"
        f"- Comportamiento esperado: {esperado}\n"
        f"- Síntomas observados / logs / traceback: {sintomas}\n\n"
        "Responde con este formato exacto obligatorio:\n"
        "# 1. Diagnóstico\n- problema\n- causa raíz\n- evidencia encontrada\n"
        "- módulos afectados\n- decisión de corrección\n\n"
        "# 2. Mapa de impacto\nLista de módulos:\n"
        "- módulo origen\n- módulos dependientes directos\n- módulos dependientes indirectos"
    )

    orchestrator_model = cfg.get_orchestrator_model()
    behavior = cfg.behavior

    return call_with_retry(
        model_cfg=orchestrator_model,
        messages=[{"role": "user", "content": prompt}],
        max_retries=behavior.max_retries,
        retry_delay=behavior.retry_delay_seconds,
        timeout=behavior.request_timeout_seconds,
    )


# ──────────────────────────────────────────────────────────────
# FASE 2 — Ejecutor quirúrgico de código (surgical_editor)
# ──────────────────────────────────────────────────────────────

def fase_surgical_editor(
    nombre_modulo_archivo: str,
    diagnostico_orquestador: str,
    cfg: AgentConfig,
    rp: RuntimePaths,
) -> bool:
    """
    Aplica la corrección quirúrgica sobre el archivo objetivo.
    Retorna True si se aplicó un parche, False si no hubo cambios o falló.
    """
    print(f"[Fase 2] Ejecutando surgical_editor sobre '{nombre_modulo_archivo}'...")

    ruta_codigo = rp.find_file_in_project(nombre_modulo_archivo)
    if not ruta_codigo:
        print(f"[Cirujano] Archivo '{nombre_modulo_archivo}' no encontrado en {rp.project_root}")
        return False

    nombre_sin_ext = ruta_codigo.stem

    try:
        codigo_actual = ruta_codigo.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[Cirujano] No se pudo leer '{nombre_modulo_archivo}': {e}")
        return False

    contexto_obsidian = leer_contexto_obsidian(nombre_sin_ext, rp)
    surgeon_model = cfg.get_surgeon_model()

    system_prompt = (
        "Eres un Agente Experto en Ingeniería de Software y Corrección Quirúrgica de Código.\n"
        "Modo de edición: PARCHE QUIRÚRGICO.\n\n"
        "REGLAS INQUEBRANTABLES:\n"
        "1. NO elimines, resumas, condenses ni reescribas partes del código que funcionan.\n"
        "2. NO quites funciones, clases, variables ni comentarios existentes.\n"
        "3. NO devuelvas versiones parciales.\n"
        "4. Tu única tarea es corregir errores reales (sintácticos, lógicos o de ejecución).\n"
        "5. Si el código NO requiere corrección, devuélvelo exactamente idéntico al original.\n"
        "6. Debes devolver el archivo COMPLETO.\n"
        "7. SEGURIDAD: En caso de KeyError, usa .get() o try/except para proteger el estado homeostático.\n"
        "8. Devuelve SOLO el código de programación limpio."
    )

    user_content = (
        f"# ORDEN DIRECTA DEL ORQUESTADOR:\n{diagnostico_orquestador}\n\n"
        f"# CONTEXTO ASOCIADO EN OBSIDIAN:\n{contexto_obsidian}\n\n"
        f"# ARCHIVO OBJETIVO A PARCHEAR:\n'{nombre_modulo_archivo}'\n\n"
        f"Código Actual:\n{codigo_actual}"
    )

    behavior = cfg.behavior
    respuesta = call_with_retry(
        model_cfg=surgeon_model,
        messages=[{"role": "user", "content": user_content}],
        system_prompt=system_prompt,
        max_retries=behavior.max_retries,
        retry_delay=behavior.retry_delay_seconds,
        timeout=behavior.request_timeout_seconds,
    )

    if not respuesta:
        print("[Cirujano] Sin respuesta del modelo. Abortando.")
        return False

    codigo_corregido = limpiar_codigo_markdown(respuesta)

    if not codigo_corregido or len(codigo_corregido) < 10:
        print("[Cirujano] Respuesta demasiado corta o vacía. Abortando escritura.")
        return False

    if codigo_corregido.strip() == codigo_actual.strip():
        print(f"[Cirujano] Sin cambios necesarios en '{nombre_modulo_archivo}'.")
        return False

    # Backup antes de escribir
    ruta_backup = ruta_codigo.with_suffix(".py.bak")
    ruta_backup.write_text(codigo_actual, encoding="utf-8")
    print(f"[Cirujano] Backup creado: {ruta_backup.name}")

    ruta_codigo.write_text(codigo_corregido, encoding="utf-8")
    print(f"[Cirujano] Parche aplicado exitosamente en '{nombre_modulo_archivo}'.")

    # Sincronizar nota de Obsidian
    if rp.project_root:
        try:
            rel = ruta_codigo.relative_to(rp.project_root)
            actualizar_nota_obsidian(nombre_sin_ext, rel, codigo_corregido, rp)
        except ValueError:
            pass  # ruta fuera del proyecto, se omite

    return True


# ──────────────────────────────────────────────────────────────
# Pipeline coordinado
# ──────────────────────────────────────────────────────────────

def ejecutar_pipeline_coordinado(
    archivo_objetivo: str,
    problema: str,
    esperado: str,
    sintomas: str,
    cfg: AgentConfig,
) -> dict:
    """
    Punto de entrada único del pipeline.
    Retorna un dict con el resultado de cada fase para que el backend lo emita por WS.
    """
    print("=" * 70)
    print(f"INICIANDO PIPELINE — provider: {cfg.model.provider} | proyecto: {cfg.paths.project_root}")
    print("=" * 70)

    rp = build_runtime_paths(cfg)
    rp.ensure_output_dirs()

    resultado = {
        "ok": False,
        "mapa": None,
        "diagnostico": None,
        "parche_aplicado": False,
        "archivo": archivo_objetivo,
    }

    # Fase 0
    mapa = fase_0_obsidian_mapper(cfg, rp, archivo_objetivo=archivo_objetivo)
    resultado["mapa"] = mapa

    # Fase 1
    diagnostico = fase_impact_analyzer(problema, esperado, sintomas, mapa, cfg)
    if not diagnostico:
        resultado["error"] = "El orquestador no pudo computar el diagnóstico."
        print(f"[Pipeline] Abortado: {resultado['error']}")
        return resultado

    resultado["diagnostico"] = diagnostico
    print("\n" + "-" * 50)
    print("DIAGNÓSTICO EMITIDO POR EL ORQUESTADOR:")
    print("-" * 50)
    print(diagnostico[:800])
    print("-" * 50 + "\n")

    # Fase 2
    parche_ok = fase_surgical_editor(archivo_objetivo, diagnostico, cfg, rp)
    resultado["parche_aplicado"] = parche_ok
    resultado["ok"] = True

    print("=" * 70)
    print("PIPELINE FINALIZADO CORRECTAMENTE.")
    print("=" * 70)

    return resultado
