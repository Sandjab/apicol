"""Tests des utilitaires partagés _backends (resolve_model, reject_chat_stream)."""

from __future__ import annotations

import pytest

from apicol._backends import reject_chat_stream
from apicol._errors import NotSupportedError


def test_reject_chat_stream_raises_when_stream_true() -> None:
    with pytest.raises(NotSupportedError, match="stream"):
        reject_chat_stream({"stream": True})


def test_reject_chat_stream_noop_when_absent() -> None:
    reject_chat_stream({})  # ne lève pas


def test_reject_chat_stream_noop_when_falsy() -> None:
    reject_chat_stream({"stream": False})  # ne lève pas
