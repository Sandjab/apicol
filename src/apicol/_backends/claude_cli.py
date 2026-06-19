"""Backend claude_cli — subprocess wrapper pour `claude -p`.

Dev only — pas pour une charge programmatique routée (cf. TOS Anthropic).

Aplatissement transcript-style des messages OpenAI vers un prompt unique,
invocation subprocess de `claude -p`, parsing du JSON de sortie en dict
format OpenAI minimal (usage=None).
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import uuid
from typing import Any

from apicol._errors import BackendError, BackendUnavailableError

DEFAULT_TIMEOUT = 120

_CLAUDE_NOT_FOUND_MSG = (
    "Le binaire 'claude' est introuvable dans PATH. "
    "Installer Claude Code : https://docs.anthropic.com/en/docs/claude-code"
)


def _ensure_claude_available() -> None:
    """Vérifie la présence du binaire `claude` dans PATH.

    Raises:
        BackendUnavailableError: Si `claude` introuvable.
    """
    if not shutil.which("claude"):
        raise BackendUnavailableError(_CLAUDE_NOT_FOUND_MSG)


def _flatten_messages_to_transcript(messages: list[dict[str, Any]]) -> str:
    """Aplatit des messages OpenAI en un prompt unique transcript-style.

    Raises:
        BackendError: Si messages est vide.
    """
    if not messages:
        raise BackendError("messages vide : impossible d'invoquer claude_cli.")

    parts: list[str] = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if isinstance(content, list):
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        else:
            text = str(content)

        if role == "system":
            parts.append(f"System: {text}")
        elif role == "user":
            parts.append(f"Human: {text}")
        elif role == "assistant":
            parts.append(f"Assistant: {text}")
        else:
            continue

    return "\n\n".join(parts)


def _build_command(prompt: str, model: str | None) -> list[str]:
    """Construit la commande claude -p à exécuter."""
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if model:
        cmd.extend(["--model", model])
    return cmd


def _parse_claude_output(stdout: str) -> dict[str, Any]:
    """Parse la sortie JSON de claude -p en dict format OpenAI minimal."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise BackendError(f"Impossible de parse le JSON claude_cli: {e}") from e

    if isinstance(data, dict) and "result" in data:
        content = data["result"]
    elif isinstance(data, dict) and "message" in data:
        msg = data["message"]
        content = msg["content"] if isinstance(msg, dict) and "content" in msg else str(msg)
    else:
        raise BackendError(
            f"Format JSON claude_cli inattendu : "
            f"{list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
        )

    return {
        "id": f"claude-cli-{uuid.uuid4().hex[:12]}",
        "model": "claude (cli)",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": None,
    }


def complete(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Invocation synchrone de `claude -p`.

    Dev only — ne pas utiliser pour une charge programmatique routée selon
    coût/dispo (enfreint les TOS Claude Pro/Max).

    Args:
        messages: Format OpenAI.
        model: Optionnel, passé en --model.
        timeout: Timeout subprocess en secondes (default 120).

    Returns:
        Dict format OpenAI minimal (usage=None).

    Raises:
        BackendUnavailableError: Si `claude` introuvable dans PATH.
        BackendError: Sur exit non-zéro, timeout, JSON output illisible.
    """
    _ensure_claude_available()

    prompt = _flatten_messages_to_transcript(messages)
    cmd = _build_command(prompt, model)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise BackendError(f"claude_cli timeout après {timeout}s") from e

    if result.returncode != 0:
        raise BackendError(f"claude_cli exit code {result.returncode}: {result.stderr.strip()}")

    return _parse_claude_output(result.stdout)


async def acomplete(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Pendant async de complete()."""
    _ensure_claude_available()

    prompt = _flatten_messages_to_transcript(messages)
    cmd = _build_command(prompt, model)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise BackendError(f"claude_cli timeout après {timeout}s") from e

    if proc.returncode != 0:
        raise BackendError(f"claude_cli exit code {proc.returncode}: {stderr.decode().strip()}")

    return _parse_claude_output(stdout.decode())
