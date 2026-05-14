"""Fixtures partagées pour les tests apicol."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

APICOL_ENV_VARS = ("APICOL_TYPE", "APICOL_KEY", "APICOL_MODEL", "APICOL_URL")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supprime toutes les variables APICOL_* pour un test isolé."""
    for var in APICOL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def mock_anthropic_sdk(mocker):  # type: ignore[no-untyped-def]
    """Patch anthropic.Anthropic et anthropic.AsyncAnthropic.

    Retourne un namespace avec .sync, .async_ (les instances mockées du SDK)
    et .response (la réponse par défaut renvoyée par messages.create).
    """
    fake_response = MagicMock()
    fake_response.id = "msg_test"
    fake_response.model = "claude-test"
    fake_response.content = [MagicMock(type="text", text="hello")]
    fake_response.usage = MagicMock(input_tokens=10, output_tokens=5)
    fake_response.stop_reason = "end_turn"

    sync_client = MagicMock()
    sync_client.messages.create.return_value = fake_response

    async_client = MagicMock()

    async def _async_create(**kwargs):  # type: ignore[no-untyped-def]
        return fake_response

    async_client.messages.create.side_effect = _async_create

    mocker.patch("anthropic.Anthropic", return_value=sync_client)
    mocker.patch("anthropic.AsyncAnthropic", return_value=async_client)

    ns = MagicMock()
    ns.sync = sync_client
    ns.async_ = async_client
    ns.response = fake_response
    return ns


@pytest.fixture
def mock_litellm(mocker):  # type: ignore[no-untyped-def]
    """Patch litellm.completion et litellm.acompletion.

    Retourne un namespace avec .sync_call, .async_call (les MagicMock)
    et .response (le dict OpenAI renvoyé par défaut).
    """
    response_dict = {
        "id": "chatcmpl-test",
        "model": "gpt-test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hello"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    sync_call = mocker.patch("litellm.completion", return_value=response_dict)

    async def _async_call(**kwargs):  # type: ignore[no-untyped-def]
        return response_dict

    async_call = mocker.patch("litellm.acompletion", side_effect=_async_call)

    ns = MagicMock()
    ns.sync_call = sync_call
    ns.async_call = async_call
    ns.response = response_dict
    return ns


@pytest.fixture
def mock_subprocess(mocker):  # type: ignore[no-untyped-def]
    """Patch subprocess.run et asyncio.create_subprocess_exec pour claude_cli.

    Retourne un namespace .sync_call, .async_call, .stdout (par défaut).
    """
    default_stdout = (
        '{"type": "result", "result": "hello from claude cli", "session_id": "test-session"}'
    )

    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = default_stdout
    completed.stderr = ""

    sync_call = mocker.patch("subprocess.run", return_value=completed)

    async_proc = MagicMock()
    async_proc.returncode = 0

    async def _communicate():  # type: ignore[no-untyped-def]
        return (default_stdout.encode(), b"")

    async_proc.communicate.side_effect = _communicate

    async def _create_subprocess(*args, **kwargs):  # type: ignore[no-untyped-def]
        return async_proc

    async_call = mocker.patch("asyncio.create_subprocess_exec", side_effect=_create_subprocess)

    ns = MagicMock()
    ns.sync_call = sync_call
    ns.async_call = async_call
    ns.stdout = default_stdout
    return ns


@pytest.fixture(autouse=True)
def reset_implicit_client_cache() -> Iterator[None]:
    """Vide les caches module-level des Clients implicites entre tests.

    Auto-use : appliqué à TOUS les tests pour éviter les fuites entre cases.
    """
    yield
    try:
        from apicol import _client  # type: ignore[import-not-found]
    except ImportError:
        return
    if hasattr(_client, "_IMPLICIT_SYNC_CACHE"):
        _client._IMPLICIT_SYNC_CACHE.clear()
    if hasattr(_client, "_IMPLICIT_ASYNC_CACHE"):
        _client._IMPLICIT_ASYNC_CACHE.clear()
