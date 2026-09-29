"""Unit tests for the Task 3 untrusted-plan boundary."""

import json
import math

import pytest

from task3.schema import load_action_plan_schema, openai_response_format
from task3.validator import (
    GotoObjectAction,
    MoveAction,
    PlanValidationError,
    StopAction,
    TurnAction,
    parse_and_validate,
    validate_plan,
)


def test_valid_multistep_plan_becomes_typed_actions():
    plan = validate_plan(
        {
            "accepted": True,
            "message": "Moving, then turning.",
            "actions": [
                {"type": "move", "vx": 0.5, "vy": 0, "wz": 0, "duration_s": 3},
                {"type": "turn", "angle_deg": 90},
                {"type": "goto_object", "class": "chair", "color": "green"},
            ],
        }
    )

    assert plan.accepted is True
    assert plan.message == "Moving, then turning."
    assert plan.actions == (
        MoveAction(vx=0.5, vy=0.0, wz=0.0, duration_s=3.0),
        TurnAction(angle_deg=90.0),
        GotoObjectAction(class_name="chair", color="green"),
    )


def test_valid_rejection_has_no_actions():
    plan = validate_plan(
        {"accepted": False, "message": "Enter a safe English robot command.", "actions": []}
    )
    assert plan.accepted is False
    assert plan.actions == ()


def test_valid_stop_plan():
    plan = validate_plan(
        {"accepted": True, "message": "Stopping.", "actions": [{"type": "stop"}]}
    )
    assert plan.actions == (StopAction(),)


@pytest.mark.parametrize(
    ("mutation", "error_path"),
    [
        ({"accepted": "yes", "message": "ok", "actions": []}, "$.accepted"),
        ({"accepted": True, "message": "ok", "actions": []}, "$.actions"),
        (
            {
                "accepted": False,
                "message": "no",
                "actions": [{"type": "stop"}],
            },
            "$.actions",
        ),
        ({"accepted": False, "message": "   ", "actions": []}, "$.message"),
        (
            {"accepted": False, "message": "no", "actions": [], "debug": True},
            "$",
        ),
    ],
)
def test_invalid_plan_level_semantics_are_rejected(mutation, error_path):
    with pytest.raises(PlanValidationError, match=rf"^{error_path.replace('$', r'\$')}"):
        validate_plan(mutation)


@pytest.mark.parametrize(
    "action",
    [
        {"type": "move", "vx": 1.1, "vy": 0, "wz": 0, "duration_s": 1},
        {"type": "move", "vx": True, "vy": 0, "wz": 0, "duration_s": 1},
        {"type": "move", "vx": 0, "vy": 0, "wz": 0, "duration_s": 1},
        {"type": "move", "vx": 0.5, "vy": 0, "wz": 0, "duration_s": 0},
        {"type": "move", "vx": 0.5, "vy": 0, "wz": 0, "duration_s": math.inf},
        {"type": "turn", "angle_deg": 0},
        {"type": "turn", "angle_deg": 721},
        {"type": "goto_object", "class": "sports ball", "color": "orange"},
        {"type": "goto_object", "class": "chair", "color": "blue"},
        {"type": "stop", "reason": "extra field"},
        {"type": "dance"},
    ],
)
def test_unsafe_actions_are_rejected(action):
    with pytest.raises(PlanValidationError):
        validate_plan({"accepted": True, "message": "go", "actions": [action]})


def test_stop_must_be_the_only_action():
    with pytest.raises(PlanValidationError, match="stop must be the only action"):
        validate_plan(
            {
                "accepted": True,
                "message": "unsafe sequence",
                "actions": [
                    {"type": "stop"},
                    {"type": "move", "vx": 0.5, "vy": 0, "wz": 0, "duration_s": 1},
                ],
            }
        )


def test_more_than_eight_actions_are_rejected():
    with pytest.raises(PlanValidationError, match="at most 8"):
        validate_plan(
            {
                "accepted": True,
                "message": "too many",
                "actions": [{"type": "stop"}] * 9,
            }
        )


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        '{"accepted":false,"accepted":true,"message":"x","actions":[]}',
        '{"accepted":true,"message":"x","actions":[{"type":"turn","angle_deg":NaN}]}',
    ],
)
def test_invalid_json_text_is_rejected(text):
    with pytest.raises(PlanValidationError):
        parse_and_validate(text)


def test_schema_is_strict_and_openai_ready():
    schema = load_action_plan_schema()
    response_format = openai_response_format()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"accepted", "message", "actions"}
    assert schema["properties"]["message"]["minLength"] == 1
    assert schema["properties"]["message"]["maxLength"] == 300
    assert all(
        variant["additionalProperties"] is False
        for variant in schema["properties"]["actions"]["items"]["anyOf"]
    )
    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True
    assert json.dumps(response_format["schema"])
