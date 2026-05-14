"""Tests pour le backend claude_cli (subprocess wrapper)."""

from __future__ import annotations

import asyncio
import subprocess

import pytest

from apicol._backends import claude_cli as backend
from apicol._errors import BackendError, BackendUnavailableError


class TestFlattenMessagesToTranscript:
    def test_single_user(self) -> None:
        transcript = backend._flatten_messages_to_transcript([{"role": "user", "content": "Hello"}])
        assert "Human: Hello" in transcript

    def test_user_assistant_alternation(self) -> None:
        transcript = backend._flatten_messages_to_transcript(
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "How are you?"},
            ]
        )
        idx_hi = transcript.index("Hi")
        idx_hello = transcript.index("Hello")
        idx_how = transcript.index("How are you?")
        assert idx_hi < idx_hello < idx_how

    def test_system_prefixed(self) -> None:
        transcript = backend._flatten_messages_to_transcript(
            [
                {"role": "system", "content": "You are concise"},
                {"role": "user", "content": "Hi"},
            ]
        )
        assert "You are concise" in transcript.split("Human:", 1)[0]

    def test_content_blocks_flattened(self) -> None:
        transcript = backend._flatten_messages_to_transcript(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "part1"},
                        {"type": "text", "text": "part2"},
                    ],
                }
            ]
        )
        assert "part1" in transcript
        assert "part2" in transcript

    def test_empty_messages_raises(self) -> None:
        with pytest.raises(BackendError, match=r"empty|vide"):
            backend._flatten_messages_to_transcript([])


class TestCompleteSync:
    def test_invokes_claude_cli(self, mock_subprocess, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")
        result = backend.complete([{"role": "user", "content": "Hi"}])
        assert result["choices"][0]["message"]["content"] == "hello from claude cli"
        assert mock_subprocess.sync_call.called

    def test_passes_model_flag_when_provided(self, mock_subprocess, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")
        backend.complete([{"role": "user", "content": "Hi"}], model="opus-4-7")
        cmd = mock_subprocess.sync_call.call_args.args[0]
        assert "--model" in cmd
        assert "opus-4-7" in cmd

    def test_raises_unavailable_when_claude_not_in_path(self, mocker) -> None:
        mocker.patch("shutil.which", return_value=None)
        with pytest.raises(BackendUnavailableError, match="claude"):
            backend.complete([{"role": "user", "content": "Hi"}])

    def test_raises_backend_error_on_nonzero_exit(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")
        completed = mocker.MagicMock()
        completed.returncode = 1
        completed.stdout = ""
        completed.stderr = "oh no"
        mocker.patch("subprocess.run", return_value=completed)
        with pytest.raises(BackendError, match=r"oh no|exit"):
            backend.complete([{"role": "user", "content": "Hi"}])

    def test_raises_backend_error_on_timeout(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=120),
        )
        with pytest.raises(BackendError, match="timeout"):
            backend.complete([{"role": "user", "content": "Hi"}], timeout=120)

    def test_raises_backend_error_on_unparseable_json(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")
        completed = mocker.MagicMock()
        completed.returncode = 0
        completed.stdout = "not json"
        completed.stderr = ""
        mocker.patch("subprocess.run", return_value=completed)
        with pytest.raises(BackendError, match=r"parse|JSON"):
            backend.complete([{"role": "user", "content": "Hi"}])


class TestAcomplete:
    @pytest.mark.asyncio
    async def test_acomplete_invokes_claude_cli(self, mock_subprocess, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")
        result = await backend.acomplete([{"role": "user", "content": "Hi"}])
        assert result["choices"][0]["message"]["content"] == "hello from claude cli"

    @pytest.mark.asyncio
    async def test_acomplete_raises_unavailable_when_claude_not_in_path(self, mocker) -> None:
        mocker.patch("shutil.which", return_value=None)
        with pytest.raises(BackendUnavailableError, match="claude"):
            await backend.acomplete([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_acomplete_raises_on_nonzero_exit(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")

        async_proc = mocker.MagicMock()
        async_proc.returncode = 2
        async_proc.kill = mocker.MagicMock()

        async def _communicate() -> tuple[bytes, bytes]:
            return (b"", b"boom from cli")

        async def _wait() -> int:
            return 2

        async_proc.communicate.side_effect = _communicate
        async_proc.wait.side_effect = _wait

        async def _create_subprocess(*_args: object, **_kwargs: object) -> object:
            return async_proc

        mocker.patch("asyncio.create_subprocess_exec", side_effect=_create_subprocess)

        with pytest.raises(BackendError, match=r"boom from cli|exit code 2"):
            await backend.acomplete([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_acomplete_raises_on_timeout(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")

        async_proc = mocker.MagicMock()
        async_proc.returncode = 0
        async_proc.kill = mocker.MagicMock()

        async def _wait() -> int:
            return 0

        async_proc.wait.side_effect = _wait

        async def _create_subprocess(*_args: object, **_kwargs: object) -> object:
            return async_proc

        mocker.patch("asyncio.create_subprocess_exec", side_effect=_create_subprocess)

        # Force asyncio.wait_for to raise asyncio.TimeoutError without actually blocking.
        # Note : sur Python 3.10, asyncio.TimeoutError est une classe distincte de
        # TimeoutError built-in. Sur 3.11+ c'est un alias. Notre code source attrape
        # asyncio.TimeoutError ; il faut donc lever exactement cette exception ici.
        async def _raise_timeout(*_args: object, **_kwargs: object) -> None:
            raise asyncio.TimeoutError

        mocker.patch("asyncio.wait_for", side_effect=_raise_timeout)

        with pytest.raises(BackendError, match="timeout"):
            await backend.acomplete([{"role": "user", "content": "Hi"}], timeout=1)

        async_proc.kill.assert_called_once()


class TestParseClaudeOutputCoverage:
    """Cover the 'message' and 'unexpected format' branches of _parse_claude_output."""

    def test_message_dict_with_content_field(self, mock_subprocess, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")
        completed = mocker.MagicMock()
        completed.returncode = 0
        completed.stdout = '{"message": {"content": "hi from message dict"}}'
        completed.stderr = ""
        mocker.patch("subprocess.run", return_value=completed)

        result = backend.complete([{"role": "user", "content": "Hi"}])
        assert result["choices"][0]["message"]["content"] == "hi from message dict"

    def test_message_scalar_stringified(self, mock_subprocess, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")
        completed = mocker.MagicMock()
        completed.returncode = 0
        completed.stdout = '{"message": "raw scalar string"}'
        completed.stderr = ""
        mocker.patch("subprocess.run", return_value=completed)

        result = backend.complete([{"role": "user", "content": "Hi"}])
        assert result["choices"][0]["message"]["content"] == "raw scalar string"

    def test_unexpected_format_raises(self, mock_subprocess, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")
        completed = mocker.MagicMock()
        completed.returncode = 0
        completed.stdout = '{"random_key": 42}'
        completed.stderr = ""
        mocker.patch("subprocess.run", return_value=completed)

        with pytest.raises(BackendError, match=r"inattendu|random_key"):
            backend.complete([{"role": "user", "content": "Hi"}])

    def test_unexpected_format_non_dict_raises(self, mock_subprocess, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/local/bin/claude")
        completed = mocker.MagicMock()
        completed.returncode = 0
        completed.stdout = "[1, 2, 3]"  # valid JSON, but a list
        completed.stderr = ""
        mocker.patch("subprocess.run", return_value=completed)

        with pytest.raises(BackendError, match=r"inattendu|list"):
            backend.complete([{"role": "user", "content": "Hi"}])


class TestFlattenUnknownRole:
    """Cover the 'else: continue' branch for unknown roles."""

    def test_unknown_role_is_skipped(self) -> None:
        transcript = backend._flatten_messages_to_transcript(
            [
                {"role": "user", "content": "kept"},
                {"role": "tool", "content": "skipped"},
                {"role": "assistant", "content": "also kept"},
            ]
        )
        assert "kept" in transcript
        assert "also kept" in transcript
        assert "skipped" not in transcript
