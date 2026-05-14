"""Fixtures et skipping pour les tests d'intégration."""

from __future__ import annotations

import os
import shutil

import pytest


@pytest.fixture(autouse=True)
def skip_if_no_anthropic_key(request: pytest.FixtureRequest) -> None:
    """Skip les tests Anthropic live sans clé."""
    if request.node.get_closest_marker("anthropic_live") and not os.environ.get(
        "ANTHROPIC_API_KEY"
    ):
        pytest.skip("ANTHROPIC_API_KEY non défini")


@pytest.fixture(autouse=True)
def skip_if_no_openai_key(request: pytest.FixtureRequest) -> None:
    """Skip les tests OpenAI live sans clé."""
    if request.node.get_closest_marker("openai_live") and not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY non défini")


@pytest.fixture(autouse=True)
def skip_if_no_claude_cli(request: pytest.FixtureRequest) -> None:
    """Skip les tests claude_cli si binaire absent."""
    if request.node.get_closest_marker("requires_claude_cli") and not shutil.which("claude"):
        pytest.skip("binaire 'claude' absent du PATH")
