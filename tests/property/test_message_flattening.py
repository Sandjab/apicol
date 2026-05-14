"""PBT : invariants du transcript-style flattening."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from apicol._backends import claude_cli as backend
from apicol._errors import BackendError

text_content = st.text(min_size=1, max_size=80)
user_assistant_msg = st.fixed_dictionaries(
    {"role": st.sampled_from(["user", "assistant"]), "content": text_content}
)


@given(msgs=st.lists(user_assistant_msg, min_size=1, max_size=8))
@settings(max_examples=80)
def test_all_textual_content_present_in_transcript(msgs: list[dict]) -> None:
    transcript = backend._flatten_messages_to_transcript(msgs)
    for msg in msgs:
        assert msg["content"] in transcript


@given(msgs=st.lists(user_assistant_msg, min_size=1, max_size=8))
@settings(max_examples=80)
def test_role_markers_in_correct_order(msgs: list[dict]) -> None:
    transcript = backend._flatten_messages_to_transcript(msgs)
    indices = []
    cursor = 0
    for msg in msgs:
        marker = "Human:" if msg["role"] == "user" else "Assistant:"
        idx = transcript.find(marker, cursor)
        assert idx >= 0
        indices.append(idx)
        cursor = idx + len(marker)
    assert indices == sorted(indices)


def test_empty_list_raises() -> None:
    with pytest.raises(BackendError):
        backend._flatten_messages_to_transcript([])
