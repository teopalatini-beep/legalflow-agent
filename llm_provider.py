"""Capa de abstracción de proveedor LLM.

Mínima a propósito: lo único que necesita el pipeline es "dado un system prompt
y un user prompt, devolveme un JSON". Cualquier proveedor que implemente
`complete_json` se puede enchufar sin reescribir los pasos del agente.

Hoy hay una sola implementación real (Claude/Anthropic). Para sumar otro
proveedor (p. ej. Cursor de nuevo, u OpenAI) se crea otra clase con el mismo
método y se la elige en `get_provider`. Nada más.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Protocol, runtime_checkable

DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"


class LLMError(RuntimeError):
    """Error de proveedor LLM (config faltante, respuesta inválida, etc.)."""


def extraer_json(texto: str) -> Dict[str, Any]:
    """Parsea JSON tolerando texto/fences alrededor."""
    texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", texto, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as err:
                raise LLMError("El modelo devolvió JSON malformado.") from err
        raise LLMError("El modelo no devolvió JSON.")


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete_json(
        self, *, system: str, user: str, model: str, max_tokens: int = 2048
    ) -> Dict[str, Any]:
        ...


class AnthropicProvider:
    """Proveedor Claude vía SDK oficial `anthropic`.

    Usa structured output por prefill: se fuerza al modelo a empezar la
    respuesta con `{`, de modo que devuelva sólo JSON. Es portable entre
    versiones del SDK y no depende de features beta.
    """

    name = "claude"

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = DEFAULT_CLAUDE_MODEL,
    ) -> None:
        try:
            import anthropic
        except ImportError as err:  # pragma: no cover
            raise LLMError(
                "Falta dependencia 'anthropic'. Instalá con: pip install anthropic"
            ) from err
        key = (api_key or os.getenv("ANTHROPIC_API_KEY", "")).strip()
        if not key:
            raise LLMError("Falta ANTHROPIC_API_KEY en el entorno.")
        self._client = anthropic.Anthropic(api_key=key)
        self.default_model = default_model

    def resolve_model(self, model: str) -> str:
        """Si pasan un modelo Claude válido lo respeta; sino usa el default."""
        candidate = (model or "").strip().lower()
        return model if candidate.startswith("claude") else self.default_model

    def complete_json(
        self, *, system: str, user: str, model: str, max_tokens: int = 2048
    ) -> Dict[str, Any]:
        resolved = self.resolve_model(model)
        try:
            message = self._client.messages.create(
                model=resolved,
                max_tokens=max_tokens,
                system=system,
                messages=[
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": "{"},
                ],
            )
        except Exception as err:  # red de seguridad; la API tira varios tipos
            raise LLMError(f"Error llamando a Claude ({resolved}): {err}") from err

        text_parts = [
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text"
        ]
        raw = "{" + "".join(text_parts)
        return extraer_json(raw)


def get_provider(
    prefer: str = "claude", default_model: str = DEFAULT_CLAUDE_MODEL
) -> Optional[LLMProvider]:
    """Devuelve un proveedor listo, o None si no está configurado.

    None significa "no hay LLM disponible" → el caller debe caer al modo demo.
    """
    if prefer in {"claude", "anthropic", "sdk"}:
        try:
            return AnthropicProvider(default_model=default_model)
        except LLMError:
            return None
    return None
