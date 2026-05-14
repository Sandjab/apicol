"""PBT : invariants de la traduction OpenAI->Anthropic."""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from apicol._backends import anthropic as backend

text_content = st.text(min_size=0, max_size=200)
text_block = st.fixed_dictionaries({"type": st.just("text"), "text": text_content})
content_strategy = st.one_of(text_content, st.lists(text_block, min_size=1, max_size=4))

user_or_assistant_msg = st.fixed_dictionaries(
    {"role": st.sampled_from(["user", "assistant"]), "content": content_strategy}
)
system_msg = st.fixed_dictionaries({"role": st.just("system"), "content": text_content})


def _extract_all_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


@given(
    msgs=st.lists(user_or_assistant_msg, min_size=1, max_size=6),
    model=st.sampled_from(["claude-sonnet-4-6", "claude-opus-4-7"]),
)
@settings(max_examples=80)
def test_no_system_message_means_no_system_kwarg(msgs: list[dict[str, Any]], model: str) -> None:
    payload = backend._openai_to_anthropic(msgs, model=model)
    assert payload.get("system") in (None, "")


@given(
    sys_msgs=st.lists(system_msg, min_size=1, max_size=3),
    user_msgs=st.lists(user_or_assistant_msg, min_size=1, max_size=4),
    model=st.sampled_from(["claude-sonnet-4-6", "claude-opus-4-7"]),
)
@settings(max_examples=80)
def test_system_messages_always_extracted(
    sys_msgs: list[dict[str, Any]],
    user_msgs: list[dict[str, Any]],
    model: str,
) -> None:
    payload = backend._openai_to_anthropic(sys_msgs + user_msgs, model=model)
    assert payload["system"] is not None
    assert all(m["role"] != "system" for m in payload["messages"])


@given(
    msgs=st.lists(user_or_assistant_msg, min_size=1, max_size=5),
    model=st.sampled_from(["claude-sonnet-4-6", "claude-opus-4-7"]),
)
@settings(max_examples=80)
def test_user_assistant_order_preserved(msgs: list[dict[str, Any]], model: str) -> None:
    payload = backend._openai_to_anthropic(msgs, model=model)
    in_roles = [m["role"] for m in msgs]
    out_roles = [m["role"] for m in payload["messages"]]
    assert in_roles == out_roles


@given(
    msgs=st.lists(user_or_assistant_msg, min_size=1, max_size=4),
    model=st.sampled_from(["claude-sonnet-4-6", "claude-opus-4-7"]),
)
@settings(max_examples=60)
def test_textual_content_invariant(msgs: list[dict[str, Any]], model: str) -> None:
    payload = backend._openai_to_anthropic(msgs, model=model)
    in_text = "".join(_extract_all_text(m["content"]) for m in msgs)
    out_text = "".join(_extract_all_text(m["content"]) for m in payload["messages"])
    assert in_text == out_text


@given(msgs=st.lists(user_or_assistant_msg, min_size=1, max_size=3))
def test_reasoning_effort_none_means_no_thinking(
    msgs: list[dict[str, Any]],
) -> None:
    payload = backend._openai_to_anthropic(msgs, model="claude-sonnet-4-6", reasoning_effort=None)
    assert "thinking" not in payload


@given(
    msgs=st.lists(user_or_assistant_msg, min_size=1, max_size=3),
    effort=st.sampled_from(["low", "medium", "high"]),
)
def test_opus_4_7_always_adaptive_regardless_of_effort(
    msgs: list[dict[str, Any]], effort: str
) -> None:
    payload = backend._openai_to_anthropic(msgs, model="claude-opus-4-7", reasoning_effort=effort)
    assert payload["thinking"] == {"type": "adaptive"}
