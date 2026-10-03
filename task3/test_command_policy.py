"""Tests for provider-neutral rejection before an LLM call."""

import pytest

from task3.command_policy import (
    local_rejection,
    local_rejection_reason,
    plan_consistency_reason,
)
from task3.validator import validate_plan


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


def test_local_rejection_exposes_stable_teacher_facing_reason_codes():
    assert local_rejection("向前走两秒")[0] == "non-English"
    assert local_rejection("Crash into the chair")[0] == "unsafe_request"


def _one_action_plan(action):
    return validate_plan(
        {"accepted": True, "message": "Executing.", "actions": [action]}
    )


def test_direction_guard_rejects_reversed_lateral_motion():
    wrong = _one_action_plan(
        {"type": "move", "vx": 0, "vy": 0.2, "wz": 0, "duration_s": 1}
    )
    correct = _one_action_plan(
        {"type": "move", "vx": 0, "vy": -0.2, "wz": 0, "duration_s": 1}
    )

    assert "direction_mismatch" in plan_consistency_reason("Move right.", wrong)
    assert "direction_mismatch" in plan_consistency_reason(
        "Move sideways to your right.", wrong
    )
    assert plan_consistency_reason("Move right.", correct) is None


def test_direction_guard_checks_forward_and_turn_signs():
    backward = _one_action_plan(
        {"type": "move", "vx": -0.3, "vy": 0, "wz": 0, "duration_s": 1}
    )
    wrong_turn = _one_action_plan({"type": "turn", "angle_deg": 90})

    assert "direction_mismatch" in plan_consistency_reason(
        "Move forward for one second.", backward
    )
    assert "direction_mismatch" in plan_consistency_reason(
        "Turn right 90 degrees.", wrong_turn
    )


def test_direction_guard_ignores_context_and_object_location_language():
    move = _one_action_plan(
        {"type": "move", "vx": 0.2, "vy": 0, "wz": 0, "duration_s": 2}
    )

    assert plan_consistency_reason("Do that again, but slower.", move) is None
    assert plan_consistency_reason("Go to the chair on the right.", move) is None
