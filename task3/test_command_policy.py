"""Tests for provider-neutral rejection before an LLM call."""

import pytest

from task3.command_policy import local_rejection_reason


@pytest.mark.parametrize(
    "command",
    [
        "向前走两秒",
        "Crash into the chair",
        "RUN OVER that object",
        "Please damage the robot",
    ],
)
def test_clear_non_english_or_dangerous_commands_are_rejected(command):
    assert local_rejection_reason(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        "Move forward for two seconds",
        "Turn right 45 degrees",
        "Go to the green chair",
        "Write a poem about robot dogs",
        # ASCII-only foreign text is intentionally left for the LLM to classify.
        "Avancez pendant deux secondes",
    ],
)
def test_safe_or_semantically_ambiguous_english_reaches_the_llm(command):
    assert local_rejection_reason(command) is None
