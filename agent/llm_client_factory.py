"""
agent/llm_client_factory.py
Crea el cliente LLM correcto según el provider definido en ModelConfig — v3.0

Cambios respecto a v2:
  - Providers soportados: openai | anthropic | google | nvidia.
    Eliminados: openrouter, local.
  - Google usa la interfaz OpenAI-compatible de la API de Gemini.
  - NVIDIA usa la interfaz OpenAI-compatible de NVIDIA NIM.
  - base_url se resuelve desde ModelConfig.effective_base_url(), no hardcodeada aquí.
  - ModelConfig.headers y ModelConfig.extra_params se aplican en cada llamada.
  - ModelConfig.timeout se usa como timeout propio del modelo.
  - Nueva función: test_connection() — verifica credenciales y conectividad.
  - _call_openai_compatible pasa extra_params al endpoint.
"""
from __future__ import annotations

import json
import time
from typing import Optional

import requests

from config.config_schema import ModelConfig


# ──────────────────────────────────────────────────────────────
# Cache de clientes lazy (uno por identidad de ModelConfig)
# ──────────────────────────────────────────────────────────────

_client_cache: dict[str, object] = {}


def _cache_key(model_cfg: ModelConfig) -> str:
    return (
        f"{model_cfg.provider}::"
        f"{model_cfg.api_key}::"
        f"{model_cfg.effective_base_url()}::"
        f"{model_cfg.role}"
    )


def get_openai_compatible_client(model_cfg: ModelConfig):
    """
    Retorna un cliente openai.OpenAI apuntando al provider configurado.
    Compatible con: openai, google, nvidia (todos usan interfaz OpenAI).
    La base_url se resuelve desde model_cfg.effective_base_url().
    """
    from openai import OpenAI

    key = _cache_key(model_cfg)
    if key in _client_cache:
        return _client_cache[key]

    base_url = model_cfg.effective_base_url()
    api_key = model_cfg.api_key or "no-key"

    # Headers adicionales definidos en ModelConfig.headers
    default_headers = dict(model_cfg.headers) if model_cfg.headers else {}

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        default_headers=default_headers if default_headers else None,
        timeout=float(model_cfg.timeout),
    )
    _client_cache[key] = client
    return client


def get_anthropic_client(model_cfg: ModelConfig):
    """
    Retorna un cliente anthropic.Anthropic.
    Solo para provider='anthropic'.
    """
    import anthropic

    key = _cache_key(model_cfg)
    if key in _client_cache:
        return _client_cache[key]

    client = anthropic.Anthropic(
        api_key=model_cfg.api_key or "",
        timeout=float(model_cfg.timeout),
    )
    _client_cache[key] = client
    return client


def invalidate_client_cache() -> None:
    """Limpia el cache de clientes. Llamar cuando la GUI cambia credenciales."""
    _client_cache.clear()


# ──────────────────────────────────────────────────────────────
# Llamada unificada a chat completions
# ──────────────────────────────────────────────────────────────

def call_chat(
    model_cfg: ModelConfig,
    messages: list[dict],
    system_prompt: Optional[str] = None,
) -> Optional[str]:
    """
    Llamada a chat completions independiente del provider.

    - anthropic → SDK Anthropic propio.
    - openai / google / nvidia → SDK OpenAI-compatible.

    Retorna el texto de la respuesta o None si falla.
    """
    if model_cfg.provider == "anthropic":
        return _call_anthropic(model_cfg, messages, system_prompt)
    return _call_openai_compatible(model_cfg, messages, system_prompt)


def _call_openai_compatible(
    model_cfg: ModelConfig,
    messages: list[dict],
    system_prompt: Optional[str],
) -> Optional[str]:
    """Llamada via SDK OpenAI-compatible. Aplica extra_params del ModelConfig."""
    client = get_openai_compatible_client(model_cfg)

    full_messages: list[dict] = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    # Parámetros base + extra_params del modelo (top_p, seed, etc.)
    params: dict = {
        "model": model_cfg.model_name,
        "messages": full_messages,
        "temperature": model_cfg.temperature,
        "max_tokens": model_cfg.max_tokens,
    }
    params.update(model_cfg.extra_params)

    try:
        completion = client.chat.completions.create(**params)
        if not completion.choices or not completion.choices[0].message.content:
            return None
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLMClient] Error ({model_cfg.provider}/{model_cfg.model_name}): {e}")
        return None


def _call_anthropic(
    model_cfg: ModelConfig,
    messages: list[dict],
    system_prompt: Optional[str],
) -> Optional[str]:
    """Llamada via SDK Anthropic. Aplica extra_params del ModelConfig."""
    try:
        client = get_anthropic_client(model_cfg)
        kwargs: dict = {
            "model": model_cfg.model_name,
            "max_tokens": model_cfg.max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        kwargs.update(model_cfg.extra_params)

        response = client.messages.create(**kwargs)
        if not response.content:
            return None
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[LLMClient/Anthropic] Error: {e}")
        return None


# ──────────────────────────────────────────────────────────────
# Llamada directa via requests (sin SDK)
# ──────────────────────────────────────────────────────────────

def call_chat_raw(
    model_cfg: ModelConfig,
    messages: list[dict],
    system_prompt: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Optional[str]:
    """
    Llamada HTTP directa a /chat/completions.
    Usa model_cfg.effective_base_url() y aplica model_cfg.headers.
    """
    base_url = model_cfg.effective_base_url()
    url = f"{base_url}/chat/completions"
    effective_timeout = timeout or model_cfg.timeout

    full_messages: list[dict] = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    headers: dict = {
        "Authorization": f"Bearer {model_cfg.api_key or ''}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    headers.update(model_cfg.headers)   # headers custom del modelo

    payload: dict = {
        "model": model_cfg.model_name,
        "messages": full_messages,
        "temperature": model_cfg.temperature,
        "max_tokens": model_cfg.max_tokens,
        "stream": False,
    }
    payload.update(model_cfg.extra_params)

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=effective_timeout)
        if response.status_code != 200:
            print(f"[LLMClient/raw] HTTP {response.status_code}: {response.text[:300]}")
            return None
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.Timeout:
        print(f"[LLMClient/raw] Timeout ({effective_timeout}s) — {model_cfg.provider}/{model_cfg.model_name}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"[LLMClient/raw] Respuesta inesperada: {e}")
        return None
    except Exception as e:
        print(f"[LLMClient/raw] Error: {e}")
        return None


# ──────────────────────────────────────────────────────────────
# test_connection — validación de credenciales y conectividad
# ──────────────────────────────────────────────────────────────

def test_connection(model_cfg: ModelConfig) -> dict:
    """
    Verifica la conexión con el provider configurado.

    Retorna un dict con:
      ok: bool
      error_type: None | "api_key" | "model" | "base_url" | "network" | "unknown"
      message: str  — mensaje legible para mostrar en la GUI
      provider: str
      model_name: str
      base_url: str
    """
    result = {
        "ok": False,
        "error_type": None,
        "message": "",
        "provider": model_cfg.provider,
        "model_name": model_cfg.model_name,
        "base_url": model_cfg.effective_base_url(),
    }

    if not model_cfg.api_key:
        result["error_type"] = "api_key"
        result["message"] = "❌ API Key no configurada."
        return result

    if not model_cfg.model_name:
        result["error_type"] = "model"
        result["message"] = "❌ Nombre del modelo no especificado."
        return result

    # Usamos un mensaje mínimo para no consumir tokens innecesariamente
    test_messages = [{"role": "user", "content": "ping"}]

    try:
        if model_cfg.provider == "anthropic":
            response = _test_anthropic(model_cfg, test_messages)
        else:
            response = _test_openai_compatible(model_cfg, test_messages)

        if response is not None:
            result["ok"] = True
            result["message"] = (
                f"✅ Conexión exitosa con {model_cfg.provider} "
                f"({model_cfg.model_name}) — {model_cfg.effective_base_url()}"
            )
        else:
            result["error_type"] = "unknown"
            result["message"] = (
                "❌ El provider no devolvió respuesta. "
                "Verificá el modelo y la Base URL."
            )
    except _AuthError as e:
        result["error_type"] = "api_key"
        result["message"] = f"❌ API Key inválida o sin permisos: {e}"
    except _ModelNotFoundError as e:
        result["error_type"] = "model"
        result["message"] = f"❌ Modelo inexistente o sin acceso: {e}"
    except _NetworkError as e:
        result["error_type"] = "network"
        result["message"] = f"❌ Error de red / Base URL incorrecta: {e}"
    except Exception as e:
        result["error_type"] = "unknown"
        result["message"] = f"❌ Error desconocido: {e}"

    return result


# ── Excepciones internas para clasificar errores ──────────────

class _AuthError(Exception): pass
class _ModelNotFoundError(Exception): pass
class _NetworkError(Exception): pass


def _test_openai_compatible(model_cfg: ModelConfig, messages: list[dict]) -> Optional[str]:
    """Prueba la conexión usando el SDK OpenAI-compatible."""
    try:
        client = get_openai_compatible_client(model_cfg)
        completion = client.chat.completions.create(
            model=model_cfg.model_name,
            messages=messages,
            max_tokens=5,
            temperature=0,
        )
        if completion.choices and completion.choices[0].message.content:
            return completion.choices[0].message.content.strip()
        return ""
    except Exception as e:
        err_str = str(e).lower()
        if any(k in err_str for k in ("401", "authentication", "api key", "unauthorized", "invalid_api_key")):
            raise _AuthError(str(e)) from e
        if any(k in err_str for k in ("404", "model_not_found", "does not exist", "no such model")):
            raise _ModelNotFoundError(str(e)) from e
        if any(k in err_str for k in ("connection", "timeout", "network", "refused", "unreachable")):
            raise _NetworkError(str(e)) from e
        raise


def _test_anthropic(model_cfg: ModelConfig, messages: list[dict]) -> Optional[str]:
    """Prueba la conexión usando el SDK Anthropic."""
    try:
        client = get_anthropic_client(model_cfg)
        response = client.messages.create(
            model=model_cfg.model_name,
            max_tokens=5,
            messages=messages,
        )
        if response.content:
            return response.content[0].text.strip()
        return ""
    except Exception as e:
        err_str = str(e).lower()
        if any(k in err_str for k in ("401", "authentication_error", "api key", "invalid x-api-key")):
            raise _AuthError(str(e)) from e
        if any(k in err_str for k in ("404", "not_found", "no such model")):
            raise _ModelNotFoundError(str(e)) from e
        if any(k in err_str for k in ("connection", "timeout", "network")):
            raise _NetworkError(str(e)) from e
        raise


# ──────────────────────────────────────────────────────────────
# Retry wrapper genérico
# ──────────────────────────────────────────────────────────────

def call_with_retry(
    model_cfg: ModelConfig,
    messages: list[dict],
    system_prompt: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: int = 10,
    use_raw: bool = False,
    timeout: Optional[int] = None,
) -> Optional[str]:
    """
    Envuelve call_chat o call_chat_raw con lógica de retry configurable.
    Los valores de max_retries y retry_delay deben venir de AgentBehaviorConfig.
    El timeout usa model_cfg.timeout si no se especifica.
    """
    effective_timeout = timeout or model_cfg.timeout

    for attempt in range(max_retries):
        print(
            f"[LLMClient] Intento {attempt + 1}/{max_retries} "
            f"({model_cfg.provider}/{model_cfg.model_name})"
        )

        if use_raw:
            result = call_chat_raw(model_cfg, messages, system_prompt, timeout=effective_timeout)
        else:
            result = call_chat(model_cfg, messages, system_prompt)

        if result:
            return result

        if attempt < max_retries - 1:
            print(f"[LLMClient] Sin respuesta. Esperando {retry_delay}s antes de reintentar...")
            time.sleep(retry_delay)

    print(
        f"[LLMClient] Agotados {max_retries} intentos para "
        f"{model_cfg.provider}/{model_cfg.model_name}."
    )
    return None
