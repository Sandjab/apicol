# Streaming (sync + async) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter une voie de streaming `stream()`/`astream()` (méthodes Client/AsyncClient + fonctions globales) yieldant des dicts au format OpenAI chunk, pour les 3 backends routables, sans toucher au contrat de `chat()`.

**Architecture:** Méthodes dédiées en miroir du chemin `chat()`. `openai-compatible` et `litellm` font du pass-through de chunks OpenAI (`.model_dump()`) ; `anthropic` utilise un codec localisé (`messages.stream()` → `.text_stream` + `.get_final_message()`). Un garde `reject_chat_stream` centralisé interdit `stream=True` sur `chat()`. Le routage passe de 2 à 4 callables.

**Tech Stack:** Python 3.10+, SDK `anthropic` (sync+async), SDK `openai` (sync+async), `litellm`, `pytest` + `pytest-asyncio` + `pytest-mock`, `mypy --strict`, `ruff`.

**Conventions projet (rappel) :** imports SDK par module (`import anthropic` puis `anthropic.Anthropic`, jamais `from anthropic import Anthropic`) pour la mockabilité ; erreurs custom via `_errors`, jamais `raise Exception` ; type hints obligatoires sur les signatures publiques ; tests unitaires mockent les SDKs (pas d'appel réseau).

**Commande de test de référence :** `.venv/bin/python -m pytest <chemin> -v`. Lint/types : `.venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests && .venv/bin/mypy --strict src`.

---

## File Structure

| Fichier | Rôle | Action |
|---|---|---|
| `src/apicol/_backends/__init__.py` | utilitaires partagés backends (`resolve_model`, **`reject_chat_stream`**) | Modifier |
| `src/apicol/_backends/openai_compatible.py` | + `stream`/`astream` (pass-through), garde `reject_chat_stream` dans complete/acomplete | Modifier |
| `src/apicol/_backends/litellm.py` | + `stream`/`astream` (pass-through), garde | Modifier |
| `src/apicol/_backends/anthropic.py` | + `stream`/`astream` (codec), garde, **retrait du garde stream de `_openai_to_anthropic`** | Modifier |
| `src/apicol/_route.py` | `pick_backend` → 4-tuple + types `StreamCallable`/`AStreamCallable` | Modifier |
| `src/apicol/_client.py` | `Client.stream` / `AsyncClient.stream` + stockage callables | Modifier |
| `src/apicol/__init__.py` | globales `stream`/`astream` + `__all__` | Modifier |
| `pyproject.toml` | version → `0.3.0` | Modifier |
| `tests/unit/test_*_backend.py` | tests stream/astream + garde par backend | Modifier |
| `tests/unit/test_route.py` | 4-tuple | Modifier |
| `tests/unit/test_client.py` | méthodes stream | Modifier |
| `tests/unit/test_global_wrappers.py` | globales stream/astream | Modifier |
| `SPEC.md`, `ARCHITECTURE.md`, `README.md`, `CHANGELOG.md`, `docs/prd/BACKLOG.md`, `CLAUDE.md` | doc | Modifier |

Signatures fixées (cohérence inter-tâches) :

```python
# _backends/__init__.py
def reject_chat_stream(kwargs: dict[str, Any]) -> None: ...

# chaque backend
def stream(messages: list[dict[str, Any]], config: Config, **kwargs: Any) -> Iterator[dict[str, Any]]: ...
async def astream(messages: list[dict[str, Any]], config: Config, **kwargs: Any) -> AsyncIterator[dict[str, Any]]: ...

# _route.py
StreamCallable = Callable[..., Iterator[dict[str, Any]]]
AStreamCallable = Callable[..., AsyncIterator[dict[str, Any]]]
def pick_backend(config: Config) -> tuple[SyncCallable, AsyncCallable, StreamCallable, AStreamCallable]: ...

# _client.py
def stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> Iterator[dict[str, Any]]: ...        # Client
def stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[dict[str, Any]]: ...   # AsyncClient (retourne l'async generator, méthode non-async)

# __init__.py (globales)
def stream(messages: list[dict[str, Any]], **kwargs: Any) -> Iterator[dict[str, Any]]: ...
def astream(messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[dict[str, Any]]: ...
```

---

## Task 1: Garde `reject_chat_stream` centralisé

**Files:**
- Modify: `src/apicol/_backends/__init__.py`
- Test: `tests/unit/test_errors.py` (ou nouveau `tests/unit/test_backends_common.py`)

- [ ] **Step 1: Write the failing test**

Créer `tests/unit/test_backends_common.py` :

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_backends_common.py -v`
Expected: FAIL — `ImportError: cannot import name 'reject_chat_stream'`

- [ ] **Step 3: Implement**

Dans `src/apicol/_backends/__init__.py`, ajouter `NotSupportedError` à l'import existant et la fonction :

```python
from apicol._errors import BackendError, NotSupportedError
```

```python
def reject_chat_stream(kwargs: dict[str, Any]) -> None:
    """Interdit stream=True sur le chemin chat()/complete().

    Le streaming passe par stream()/astream(), pas par un kwarg de chat().

    Raises:
        NotSupportedError: Si kwargs contient stream truthy.
    """
    if kwargs.get("stream"):
        raise NotSupportedError(
            "stream=True n'est pas supporté sur chat() ; utiliser stream()/astream()."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_backends_common.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/apicol/_backends/__init__.py tests/unit/test_backends_common.py
git commit -m "feat(stream): reject_chat_stream guard helper"
```

---

## Task 2: Brancher le garde dans les 3 backends + retirer le garde local Anthropic

**Files:**
- Modify: `src/apicol/_backends/anthropic.py`, `src/apicol/_backends/openai_compatible.py`, `src/apicol/_backends/litellm.py`
- Test: `tests/unit/test_anthropic_backend.py` (adapter), `tests/unit/test_openai_compatible_backend.py`, `tests/unit/test_litellm_backend.py`

- [ ] **Step 1: Adapter le test Anthropic existant + ajouter les tests garde**

Dans `tests/unit/test_anthropic_backend.py`, **remplacer** `test_stream_kwarg_raises_not_supported` (qui teste `_openai_to_anthropic`) par un test au niveau `complete` :

```python
def test_chat_stream_kwarg_raises_not_supported(self) -> None:
    from apicol._config import Config
    cfg = Config(backend="anthropic", api_key="k", model="claude-sonnet-4-6")
    with pytest.raises(NotSupportedError, match="stream"):
        backend.complete([{"role": "user", "content": "hi"}], cfg, stream=True)
```

Dans `tests/unit/test_openai_compatible_backend.py` et `tests/unit/test_litellm_backend.py`, ajouter (adapter le nom du module `backend` importé dans chaque fichier) :

```python
def test_chat_stream_kwarg_raises_not_supported(self) -> None:
    from apicol._config import Config
    cfg = Config(backend="openai-compatible", api_key="k", model="gpt-5")  # litellm: backend="litellm", model="gpt-5"
    with pytest.raises(NotSupportedError, match="stream"):
        backend.complete([{"role": "user", "content": "hi"}], cfg, stream=True)
```

S'assurer que `NotSupportedError` est importé dans les deux fichiers de test openai/litellm :
```python
from apicol._errors import NotSupportedError
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_openai_compatible_backend.py -k stream tests/unit/test_litellm_backend.py -k stream -v`
Expected: FAIL (les backends openai/litellm ne rejettent pas encore `stream=True` ; ils tenteraient un appel SDK mocké/réel)

- [ ] **Step 3: Implémenter le garde dans complete/acomplete des 3 backends**

`anthropic.py` — importer le garde et l'appeler en tête de `complete` et `acomplete` ; **retirer** le garde stream de `_openai_to_anthropic` :

```python
from apicol._backends import resolve_model, reject_chat_stream
```

Dans `_openai_to_anthropic`, **supprimer** les deux lignes :
```python
    if stream:
        raise NotSupportedError("stream=True n'est pas encore supporté (cf. roadmap v0.3).")
```
(garder le rejet `tools` et `role='tool'`). Retirer aussi le paramètre `stream: bool = False` de la signature de `_openai_to_anthropic` (il est désormais absorbé par `**kwargs` et ignoré côté payload).

En tête de `complete` et `acomplete` :
```python
    reject_chat_stream(kwargs)
    model = resolve_model(config, kwargs)
```

`openai_compatible.py` et `litellm.py` — importer et appeler en tête de `complete`/`acomplete` :
```python
from apicol._backends import resolve_model, reject_chat_stream
```
```python
def complete(messages, config, **kwargs):
    reject_chat_stream(kwargs)
    ...
```
(idem `acomplete` ; pour ces 2 backends, `_build_call_kwargs` est appelé ensuite — placer `reject_chat_stream(kwargs)` AVANT l'appel à `_build_call_kwargs`).

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (les anciens 161 + nouveaux tests garde ; aucun échec de `test_stream_kwarg_*` résiduel)

- [ ] **Step 5: Lint/types + Commit**

```bash
.venv/bin/ruff check src tests && .venv/bin/ruff format src tests && .venv/bin/mypy --strict src
git add src/apicol/_backends tests/unit
git commit -m "feat(stream): centralise le garde stream=True sur chat() (3 backends)"
```

---

## Task 3: `openai_compatible.stream` / `astream`

**Files:**
- Modify: `src/apicol/_backends/openai_compatible.py`
- Test: `tests/unit/test_openai_compatible_backend.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestOpenAICompatibleStream:
    def test_stream_yields_openai_chunks(self, mocker) -> None:
        from apicol._config import Config

        class FakeChunk:
            def __init__(self, content): self._c = content
            def model_dump(self): return {"choices": [{"index": 0, "delta": {"content": self._c}, "finish_reason": None}]}

        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.return_value = iter([FakeChunk("Hel"), FakeChunk("lo")])
        mocker.patch("openai.OpenAI", return_value=fake_client)

        cfg = Config(backend="openai-compatible", api_key="k", model="gpt-5")
        chunks = list(backend.stream([{"role": "user", "content": "hi"}], cfg))

        assert [c["choices"][0]["delta"]["content"] for c in chunks] == ["Hel", "lo"]
        # stream=True a bien été demandé au SDK
        assert fake_client.chat.completions.create.call_args.kwargs["stream"] is True

    async def test_astream_yields_openai_chunks(self, mocker) -> None:
        from apicol._config import Config

        class FakeChunk:
            def __init__(self, content): self._c = content
            def model_dump(self): return {"choices": [{"index": 0, "delta": {"content": self._c}, "finish_reason": None}]}

        async def agen():
            for c in [FakeChunk("A"), FakeChunk("B")]:
                yield c

        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.return_value = agen()
        mocker.patch("openai.AsyncOpenAI", return_value=fake_client)

        cfg = Config(backend="openai-compatible", api_key="k", model="gpt-5")
        out = [c["choices"][0]["delta"]["content"] async for c in backend.astream([{"role": "user", "content": "hi"}], cfg)]
        assert out == ["A", "B"]
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/unit/test_openai_compatible_backend.py -k Stream -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'stream'`

- [ ] **Step 3: Implement**

Ajouter en tête de `openai_compatible.py` :
```python
from collections.abc import AsyncIterator, Iterator
```

```python
def stream(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> Iterator[dict[str, Any]]:
    """Streaming synchrone via le SDK OpenAI (pass-through de chunks OpenAI)."""
    client = openai.OpenAI(**_build_client_kwargs(config))
    call_kwargs = _build_call_kwargs(messages, config, **kwargs)
    call_kwargs["stream"] = True
    try:
        for chunk in client.chat.completions.create(**call_kwargs):
            yield chunk.model_dump()
    except openai.APIError as e:
        raise BackendError(f"OpenAI-compatible API error: {e}") from e


async def astream(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> AsyncIterator[dict[str, Any]]:
    """Pendant async de stream()."""
    client = openai.AsyncOpenAI(**_build_client_kwargs(config))
    call_kwargs = _build_call_kwargs(messages, config, **kwargs)
    call_kwargs["stream"] = True
    try:
        async for chunk in await client.chat.completions.create(**call_kwargs):
            yield chunk.model_dump()
    except openai.APIError as e:
        raise BackendError(f"OpenAI-compatible API error: {e}") from e
```

Note: le SDK OpenAI async renvoie un awaitable qui résout en async iterator quand `stream=True` ; d'où `async for chunk in await client.chat.completions.create(...)`. Le mock du test fournit directement un async generator, donc adapter le mock si nécessaire pour renvoyer un objet awaitable — alternativement, wrapper: si le test échoue sur `await`, faire que le mock retourne un coroutine via `mocker.AsyncMock(return_value=agen())`. Préférer dans le test : `fake_client.chat.completions.create = mocker.AsyncMock(return_value=agen())`.

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/unit/test_openai_compatible_backend.py -k Stream -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/apicol/_backends/openai_compatible.py tests/unit/test_openai_compatible_backend.py
git commit -m "feat(stream): openai-compatible stream/astream"
```

---

## Task 4: `litellm.stream` / `astream`

**Files:**
- Modify: `src/apicol/_backends/litellm.py`
- Test: `tests/unit/test_litellm_backend.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestLiteLLMStream:
    def test_stream_yields_openai_chunks(self, mocker) -> None:
        from apicol._config import Config

        class FakeChunk:
            def __init__(self, content): self._c = content
            def model_dump(self): return {"choices": [{"index": 0, "delta": {"content": self._c}, "finish_reason": None}]}

        mocker.patch("litellm.completion", return_value=iter([FakeChunk("X"), FakeChunk("Y")]))
        cfg = Config(backend="litellm", api_key="k", model="gpt-5")
        chunks = list(backend.stream([{"role": "user", "content": "hi"}], cfg))
        assert [c["choices"][0]["delta"]["content"] for c in chunks] == ["X", "Y"]

    async def test_astream_yields_openai_chunks(self, mocker) -> None:
        from apicol._config import Config

        class FakeChunk:
            def __init__(self, content): self._c = content
            def model_dump(self): return {"choices": [{"index": 0, "delta": {"content": self._c}, "finish_reason": None}]}

        async def agen():
            for c in [FakeChunk("P"), FakeChunk("Q")]:
                yield c

        mocker.patch("litellm.acompletion", mocker.AsyncMock(return_value=agen()))
        cfg = Config(backend="litellm", api_key="k", model="gpt-5")
        out = [c["choices"][0]["delta"]["content"] async for c in backend.astream([{"role": "user", "content": "hi"}], cfg)]
        assert out == ["P", "Q"]
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/unit/test_litellm_backend.py -k Stream -v`
Expected: FAIL — pas d'attribut `stream`

- [ ] **Step 3: Implement**

Ajouter en tête de `litellm.py` :
```python
from collections.abc import AsyncIterator, Iterator
```

```python
def stream(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> Iterator[dict[str, Any]]:
    """Streaming synchrone via LiteLLM (pass-through de chunks OpenAI-compatibles)."""
    call_kwargs = _build_call_kwargs(messages, config, **kwargs)
    call_kwargs["stream"] = True
    try:
        for chunk in litellm.completion(**call_kwargs):
            yield chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk)
    except litellm.exceptions.APIError as e:
        raise BackendError(f"LiteLLM API error: {e}") from e
    except litellm.exceptions.BadRequestError as e:
        raise BackendError(f"LiteLLM bad request: {e}") from e


async def astream(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> AsyncIterator[dict[str, Any]]:
    """Pendant async de stream()."""
    call_kwargs = _build_call_kwargs(messages, config, **kwargs)
    call_kwargs["stream"] = True
    try:
        async for chunk in await litellm.acompletion(**call_kwargs):
            yield chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk)
    except litellm.exceptions.APIError as e:
        raise BackendError(f"LiteLLM API error: {e}") from e
    except litellm.exceptions.BadRequestError as e:
        raise BackendError(f"LiteLLM bad request: {e}") from e
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/unit/test_litellm_backend.py -k Stream -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/apicol/_backends/litellm.py tests/unit/test_litellm_backend.py
git commit -m "feat(stream): litellm stream/astream"
```

---

## Task 5: `anthropic.stream` / `astream` (codec)

**Files:**
- Modify: `src/apicol/_backends/anthropic.py`
- Test: `tests/unit/test_anthropic_backend.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestAnthropicStream:
    def _fake_stream_cm(self, mocker, texts, stop_reason="end_turn"):
        """Construit un context manager mockant client.messages.stream(...)."""
        cm = mocker.MagicMock()
        cm.__enter__.return_value = cm
        cm.__exit__.return_value = False
        cm.text_stream = iter(texts)
        final = mocker.MagicMock()
        final.stop_reason = stop_reason
        final.usage = mocker.MagicMock(input_tokens=3, output_tokens=5)
        cm.get_final_message.return_value = final
        return cm

    def test_stream_maps_text_then_final_chunk(self, mocker) -> None:
        from apicol._config import Config
        fake_client = mocker.MagicMock()
        fake_client.messages.stream.return_value = self._fake_stream_cm(mocker, ["Hel", "lo"])
        mocker.patch("anthropic.Anthropic", return_value=fake_client)

        cfg = Config(backend="anthropic", api_key="k", model="claude-sonnet-4-6")
        chunks = list(backend.stream([{"role": "user", "content": "hi"}], cfg))

        text = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
        assert text == "Hello"
        assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
        assert chunks[-1]["usage"]["total_tokens"] == 8
```

(version async `test_astream_*` : `__aenter__`/`__aexit__`, `text_stream` async generator, `get_final_message` en `AsyncMock`.)

```python
    async def test_astream_maps_text_then_final_chunk(self, mocker) -> None:
        from apicol._config import Config

        async def atext():
            for t in ["A", "B"]:
                yield t

        cm = mocker.MagicMock()
        cm.__aenter__.return_value = cm
        cm.__aexit__.return_value = False
        cm.text_stream = atext()
        final = mocker.MagicMock(stop_reason="end_turn", usage=mocker.MagicMock(input_tokens=1, output_tokens=1))
        cm.get_final_message = mocker.AsyncMock(return_value=final)

        fake_client = mocker.MagicMock()
        fake_client.messages.stream.return_value = cm
        mocker.patch("anthropic.AsyncAnthropic", return_value=fake_client)

        cfg = Config(backend="anthropic", api_key="k", model="claude-sonnet-4-6")
        out = [c async for c in backend.astream([{"role": "user", "content": "hi"}], cfg)]
        assert "".join(c["choices"][0]["delta"].get("content", "") for c in out) == "AB"
        assert out[-1]["choices"][0]["finish_reason"] == "stop"
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/unit/test_anthropic_backend.py -k Stream -v`
Expected: FAIL — pas d'attribut `stream`

- [ ] **Step 3: Implement**

Ajouter en tête de `anthropic.py` :
```python
from collections.abc import AsyncIterator, Iterator
```

Ajouter deux helpers de construction de chunk (réutilisent `_STOP_REASON_MAP` existant) :

```python
def _text_delta_chunk(model: str, text: str) -> dict[str, Any]:
    return {
        "model": model,
        "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
    }


def _final_chunk(model: str, stop_reason: str | None, usage: Any) -> dict[str, Any]:
    chunk: dict[str, Any] = {
        "model": model,
        "choices": [
            {"index": 0, "delta": {}, "finish_reason": _STOP_REASON_MAP.get(stop_reason, "stop")}
        ],
    }
    if usage is not None:
        it = getattr(usage, "input_tokens", 0)
        ot = getattr(usage, "output_tokens", 0)
        chunk["usage"] = {"prompt_tokens": it, "completion_tokens": ot, "total_tokens": it + ot}
    return chunk
```

Puis les deux fonctions de streaming :

```python
def stream(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> Iterator[dict[str, Any]]:
    """Streaming synchrone Anthropic : events -> chunks format OpenAI (texte seulement)."""
    model = resolve_model(config, kwargs)
    payload = _openai_to_anthropic(messages, model=model, **kwargs)
    client = anthropic.Anthropic(api_key=config.api_key, base_url=config.base_url)
    try:
        with client.messages.stream(**payload) as s:
            for text in s.text_stream:
                yield _text_delta_chunk(model, text)
            final = s.get_final_message()
        yield _final_chunk(model, final.stop_reason, final.usage)
    except anthropic.APIError as e:
        raise BackendError(f"Anthropic API error: {e}") from e


async def astream(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> AsyncIterator[dict[str, Any]]:
    """Pendant async de stream()."""
    model = resolve_model(config, kwargs)
    payload = _openai_to_anthropic(messages, model=model, **kwargs)
    client = anthropic.AsyncAnthropic(api_key=config.api_key, base_url=config.base_url)
    try:
        async with client.messages.stream(**payload) as s:
            async for text in s.text_stream:
                yield _text_delta_chunk(model, text)
            final = await s.get_final_message()
        yield _final_chunk(model, final.stop_reason, final.usage)
    except anthropic.APIError as e:
        raise BackendError(f"Anthropic API error: {e}") from e
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/unit/test_anthropic_backend.py -k Stream -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/apicol/_backends/anthropic.py tests/unit/test_anthropic_backend.py
git commit -m "feat(stream): anthropic stream/astream codec"
```

---

## Task 6: Routage — `pick_backend` → 4-tuple

**Files:**
- Modify: `src/apicol/_route.py`
- Test: `tests/unit/test_route.py`

- [ ] **Step 1: Write the failing test**

Adapter/ajouter dans `tests/unit/test_route.py` :

```python
def test_pick_backend_returns_four_callables() -> None:
    from apicol._config import Config
    from apicol._route import pick_backend
    cfg = Config(backend="anthropic", api_key="k", model="claude-sonnet-4-6")
    result = pick_backend(cfg)
    assert len(result) == 4
    complete, acomplete, stream, astream = result
    assert all(callable(x) for x in (complete, acomplete, stream, astream))
```

Les tests existants de `test_route.py` qui font `sync, async = pick_backend(cfg)` devront être mis à jour en `*_, = pick_backend(cfg)` ou `complete, acomplete, _stream, _astream = pick_backend(cfg)` — adapter chacun.

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/unit/test_route.py -v`
Expected: FAIL — unpacking 2 vs 4 / longueur != 4

- [ ] **Step 3: Implement**

Dans `_route.py`, ajouter les types et étendre chaque `case` :

```python
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

SyncCallable = Callable[..., dict[str, Any]]
AsyncCallable = Callable[..., Awaitable[dict[str, Any]]]
StreamCallable = Callable[..., Iterator[dict[str, Any]]]
AStreamCallable = Callable[..., AsyncIterator[dict[str, Any]]]


def pick_backend(
    config: Config,
) -> tuple[SyncCallable, AsyncCallable, StreamCallable, AStreamCallable]:
    """Retourne (complete, acomplete, stream, astream) pour un Config validé."""
    match config.backend:
        case "anthropic":
            return (
                anthropic_backend.complete,
                anthropic_backend.acomplete,
                anthropic_backend.stream,
                anthropic_backend.astream,
            )
        case "openai-compatible":
            return (
                openai_compatible_backend.complete,
                openai_compatible_backend.acomplete,
                openai_compatible_backend.stream,
                openai_compatible_backend.astream,
            )
        case "litellm":
            return (
                litellm_backend.complete,
                litellm_backend.acomplete,
                litellm_backend.stream,
                litellm_backend.astream,
            )
        case _:  # pragma: no cover
            raise ConfigError(
                f"_route ne peut pas dispatcher backend={config.backend!r}. "
                "Cette erreur signale un bug d'invariant : Config aurait dû "
                "rejeter ce backend en amont."
            )
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/unit/test_route.py -v`
Expected: PASS

- [ ] **Step 5: Commit** (la suite globale est cassée tant que Task 7 n'est pas faite : `_client` unpacke encore 2 valeurs — Tasks 6+7 forment une paire, committer après Task 7 si besoin de garder vert)

```bash
git add src/apicol/_route.py tests/unit/test_route.py
git commit -m "feat(stream): pick_backend retourne 4 callables"
```

---

## Task 7: `Client.stream` / `AsyncClient.stream` + stockage callables

**Files:**
- Modify: `src/apicol/_client.py`
- Test: `tests/unit/test_client.py`

- [ ] **Step 1: Write the failing test**

```python
def test_client_stream_dispatches(mocker) -> None:
    import apicol
    cfg_call = mocker.MagicMock(return_value=iter([{"choices": [{"index": 0, "delta": {"content": "hi"}, "finish_reason": None}]}]))
    client = apicol.Client(backend="anthropic", api_key="k", model="claude-sonnet-4-6")
    object.__setattr__(client, "_stream_callable", cfg_call)
    chunks = list(client.stream([{"role": "user", "content": "x"}]))
    assert chunks[0]["choices"][0]["delta"]["content"] == "hi"
    cfg_call.assert_called_once()
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/unit/test_client.py -k stream -v`
Expected: FAIL — `AttributeError: 'Client' object has no attribute 'stream'`

- [ ] **Step 3: Implement**

Dans `_client.py`, ajouter l'import :
```python
from collections.abc import AsyncIterator, Iterator
```

Ajouter les champs aux deux dataclasses (après `_async_callable`) :
```python
    _stream_callable: StreamCallable = field(init=False, repr=False, compare=False)
    _astream_callable: AStreamCallable = field(init=False, repr=False, compare=False)
```
et l'import depuis `_route` :
```python
from apicol._route import AStreamCallable, AsyncCallable, StreamCallable, SyncCallable, pick_backend
```

Dans les deux `__init__`, remplacer l'unpacking et ajouter les setattr :
```python
        sync_cb, async_cb, stream_cb, astream_cb = pick_backend(cfg)
        object.__setattr__(self, "config", cfg)
        object.__setattr__(self, "_sync_callable", sync_cb)
        object.__setattr__(self, "_async_callable", async_cb)
        object.__setattr__(self, "_stream_callable", stream_cb)
        object.__setattr__(self, "_astream_callable", astream_cb)
```

Ajouter la méthode à `Client` :
```python
    def stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Streaming synchrone — dispatche vers le backend résolu. Yield des chunks format OpenAI.

        Le générateur lève à l'itération (pas à l'appel) ; les erreurs SDK sont
        wrappées en BackendError.
        """
        return self._stream_callable(messages, self.config, **kwargs)
```

Ajouter la méthode à `AsyncClient` (méthode non-async qui retourne l'async generator) :
```python
    def stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        """Pendant async de Client.stream(). À consommer avec `async for`."""
        return self._astream_callable(messages, self.config, **kwargs)
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (route + client réconciliés)

- [ ] **Step 5: Lint/types + Commit**

```bash
.venv/bin/ruff check src tests && .venv/bin/ruff format src tests && .venv/bin/mypy --strict src
git add src/apicol/_route.py src/apicol/_client.py tests/unit/test_route.py tests/unit/test_client.py
git commit -m "feat(stream): Client/AsyncClient.stream + routage 4-tuple"
```

---

## Task 8: Fonctions globales `stream` / `astream` + `__all__`

**Files:**
- Modify: `src/apicol/__init__.py`
- Test: `tests/unit/test_global_wrappers.py`

- [ ] **Step 1: Write the failing test**

```python
def test_global_stream_uses_implicit_client(mocker, monkeypatch) -> None:
    import apicol
    monkeypatch.setenv("APICOL_TYPE", "anthropic")
    monkeypatch.setenv("APICOL_KEY", "k")
    monkeypatch.setenv("APICOL_MODEL", "claude-sonnet-4-6")
    fake = mocker.MagicMock(return_value=iter([{"choices": [{"index": 0, "delta": {"content": "z"}, "finish_reason": None}]}]))
    mocker.patch("apicol._client.Client.stream", lambda self, messages, **kw: fake(messages, **kw))
    out = list(apicol.stream([{"role": "user", "content": "x"}]))
    assert out[0]["choices"][0]["delta"]["content"] == "z"


def test_stream_astream_in_all() -> None:
    import apicol
    assert "stream" in apicol.__all__
    assert "astream" in apicol.__all__
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/unit/test_global_wrappers.py -k stream -v`
Expected: FAIL — `module 'apicol' has no attribute 'stream'`

- [ ] **Step 3: Implement**

Dans `__init__.py`, ajouter l'import de typing pour les itérateurs :
```python
from collections.abc import AsyncIterator, Iterator
```

Ajouter les deux globales (après `achat`) :
```python
def stream(messages: list[dict[str, Any]], **kwargs: Any) -> Iterator[dict[str, Any]]:
    """Streaming synchrone via le backend configuré par env vars.

    Yield des dicts au format OpenAI chunk. Voir Client.stream pour la sémantique.
    """
    return _get_implicit_sync_client().stream(messages, **kwargs)


def astream(messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
    """Pendant async de stream(). À consommer avec `async for`."""
    return _get_implicit_async_client().stream(messages, **kwargs)
```

Ajouter `"astream"` et `"stream"` dans `__all__` (respecter l'ordre alphabétique existant : `astream` après `anthropic_client`/`achat`, `stream` avant lui ou selon tri — placer `"astream"` et `"stream"` aux bons rangs et laisser `ruff` (règle RUF022 si activée) ou trier manuellement).

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Lint/types + Commit**

```bash
.venv/bin/ruff check src tests && .venv/bin/ruff format src tests && .venv/bin/mypy --strict src
git add src/apicol/__init__.py tests/unit/test_global_wrappers.py
git commit -m "feat(stream): fonctions globales stream/astream"
```

---

## Task 9: Documentation + version 0.3.0

**Files:**
- Modify: `pyproject.toml`, `SPEC.md`, `ARCHITECTURE.md`, `README.md`, `CHANGELOG.md`, `docs/prd/BACKLOG.md`, `CLAUDE.md`

- [ ] **Step 1: Bump version**

`pyproject.toml` : `version = "0.2.0"` → `version = "0.3.0"`.

- [ ] **Step 2: SPEC.md**

- Tableau de compatibilité, ligne `Streaming` : remplacer `❌ v0.3` par `✅ (stream/astream)` pour anthropic, openai-compatible, litellm ; laisser `❌` pour la colonne claude_cli.
- Ajouter une section décrivant `stream()`/`astream()` (méthodes + globales), le format des chunks (dict OpenAI chunk), la sémantique générateur (lève à l'itération), et la note best-effort sur `usage`.

- [ ] **Step 3: ARCHITECTURE.md — décision D12**

Ajouter :
```markdown
### D12 — Streaming via méthodes dédiées (amende D7)

`stream()`/`astream()` dédiées (pas `stream=True` sur `chat()`) ; chunks au
format OpenAI (best-effort) ; codec events→chunks localisé dans le backend
Anthropic ; openai-compatible et litellm en pass-through. Le garde `stream=True`
sur `chat()` est centralisé (`reject_chat_stream`). **Supersede D7** (« pas de
streaming en v0.1 ») : la lingua franca OpenAI rend l'unification réaliste.
```
Et annoter D7 comme « superseded par D12 ».

- [ ] **Step 4: README.md**

- Section Statut : retirer « Streaming … reporté à v0.3 », indiquer streaming livré en v0.3.0 ; badge version → v0.3.0.
- Section « Hors périmètre » : retirer la ligne streaming (ou la déplacer en « supporté »).
- Ajouter un exemple `stream()` et un exemple `astream()` (reprendre l'Exemple bout-en-bout du PRD-005).

- [ ] **Step 5: CHANGELOG.md**

Ajouter sous `## [Unreleased]` (ou créer `## [0.3.0] - <date>`):
```markdown
### Added
- Streaming (PRD-005) : `stream()`/`astream()` (méthodes Client/AsyncClient +
  fonctions globales) yieldant des chunks au format OpenAI, pour les backends
  anthropic, openai-compatible et litellm. Codec events→chunks pour Anthropic ;
  pass-through pour les deux autres.

### Changed
- Garde `stream=True` sur `chat()` centralisé et étendu aux 3 backends
  (`reject_chat_stream`) ; lève `NotSupportedError` pointant vers `stream()`.
- ARCHITECTURE : D12 amende D7.
```

- [ ] **Step 6: BACKLOG.md**

- Ajouter PRD-005 dans « Validés (implémentés) » avec version v0.3.0.
- Dans « Idées non encore PRD-isées » : retirer la ligne streaming ; renommer « PRD-005 envisagé » (litellm optionnel) en « PRD-006 envisagé ».

- [ ] **Step 7: CLAUDE.md**

- Section « État actuel » : reste à faire → retirer streaming, mettre à jour version v0.3.0, statut PRD-005 implémenté.

- [ ] **Step 8: Vérification finale globale**

Run:
```bash
.venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests && .venv/bin/mypy --strict src && .venv/bin/python -m pytest -q
```
Expected: ruff/format/mypy clean ; tous tests PASS (anciens + nouveaux stream).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "docs(stream): SPEC/ARCHITECTURE(D12)/README/CHANGELOG/BACKLOG + bump 0.3.0"
```

---

## Self-Review (effectué)

**1. Couverture du PRD-005 :**
- Surface `stream`/`astream` (méthodes + globales) → Tasks 7, 8 ✓
- Format dict OpenAI chunk → Tasks 3, 4, 5 (tests vérifient `choices[0].delta.content`) ✓
- 3 backends routables, claude_cli exclu → Tasks 3-5 (aucune tâche claude_cli) ✓
- Best-effort (structure + finish_reason final ; usage si dispo) → Task 5 `_final_chunk` ✓
- Codec Anthropic à la frontière → Task 5 ✓
- Garde `stream=True` généralisé → Tasks 1, 2 ✓
- Routage 4-tuple + types → Task 6 ✓
- Erreurs wrappées BackendError, lève à l'itération → Tasks 3-5 (try/except), docstrings Task 7 ✓
- D12 amende D7, doc, v0.3.0 → Task 9 ✓

**2. Placeholders :** aucun « TODO/TBD ». Les notes sur le mock async (Task 3) donnent la solution concrète (`AsyncMock(return_value=agen())`).

**3. Type consistency :** `stream`/`astream` (jamais `stream_complete`), `Iterator`/`AsyncIterator[dict[str, Any]]`, `StreamCallable`/`AStreamCallable`, `reject_chat_stream`, `_text_delta_chunk`/`_final_chunk`, `_stream_callable`/`_astream_callable` — homogènes des Tasks 1 à 8.

**Risque connu à valider en exécution :** la forme exacte du SDK async OpenAI/LiteLLM (`await client...create(...)` renvoyant un async-iterator). Les tests de Tasks 3-4 fixent l'interface via `AsyncMock`; ajuster le `await` si le SDK installé diffère.
