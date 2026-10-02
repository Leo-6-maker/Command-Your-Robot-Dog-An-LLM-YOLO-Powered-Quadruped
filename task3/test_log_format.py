"""Tests for terminal log sanitising and provider metric formatting."""

import pytest

from task3.log_format import command_log, inline_value, optional_count
from task3.validator import validate_plan


def test_inline_value_collapses_newlines_whitespace_and_empty_text():
    assert inline_value("bad\n[DONE]   status=SUCCESS") == "bad [DONE] status=SUCCESS"
    assert inline_value(" \t ") == "unknown"
    assert inline_value("abcdef", limit=3) == "abc"


def test_inline_value_requires_positive_limit():
    with pytest.raises(ValueError, match="positive"):
        inline_value("x", limit=0)


def test_optional_count_uses_na_only_when_metric_is_missing():
    assert optional_count(None) == "na"
    assert optional_count(0) == "0"
    assert optional_count(42) == "42"


def test_command_log_formats_validated_actions_in_teacher_protocol():
    plan = validate_plan(
        {
            "accepted": True,
            "message": "Move and turn.",
            "actions": [
                {"type": "move", "vx": 0.4, "vy": 0, "wz": 0, "duration_s": 2},
                {"type": "turn", "angle_deg": 45},
            ],
        }
    )

    assert command_log(plan) == (
        "[CMD] actions=move(vx=0.40,vy=0.00,wz=0.00,duration_s=2.00),"
        "turn(angle_deg=45.00) n=2"
    )


def test_command_log_formats_object_stop_and_rejection():
    goto_plan = validate_plan(
        {
            "accepted": True,
            "message": "Find it.",
            "actions": [{"type": "goto_object", "class": "chair", "color": "green"}],
        }
    )
    stop_plan = validate_plan(
        {"accepted": True, "message": "Stopping.", "actions": [{"type": "stop"}]}
    )
    rejected = validate_plan(
        {"accepted": False, "message": "Unsupported.", "actions": []}
    )

    assert command_log(goto_plan) == (
        "[CMD] actions=goto_object(class=chair,color=green) n=1"
    )
    assert command_log(stop_plan) == "[CMD] actions=stop() n=1"
    assert command_log(rejected) == "[CMD] rejected reason=unsupported_request"
    assert command_log(rejected, rejection_reason="non-English") == (
        "[CMD] rejected reason=non-English"
    )
