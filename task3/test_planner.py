"""Tests for the provider boundary and trusted conversation context."""

import json
from types import SimpleNamespace

import pytest

from task3.planner import (
    IncompleteModelResponseError,
    MissingAPIKeyError,
    ModelRefusalError,
    OpenAIPlanner,
    PlannerAPIError,
    plan_to_dict,
)
from task3.validator import MoveAction, validate_plan


class FakeResponses:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def fake_client(raw_json, *, status="completed"):
    response = SimpleNamespace(
        id="resp_test",
        status=status,
        output_text=raw_json,
        usage=SimpleNamespace(input_tokens=21, output_tokens=17),
        output=[],
        incomplete_details="token limit" if status != "completed" else None,
    )
    return SimpleNamespace(responses=FakeResponses(response=response))


def test_openai_planner_uses_strict_schema_and_local_validation():
    raw = json.dumps(
        {
            "accepted": True,
            "message": "Moving forward.",
            "actions": [
                {"type": "move", "vx": 0.4, "vy": 0, "wz": 0, "duration_s": 2}
            ],
        }
    )
    client = fake_client(raw)
    clock = iter([10.0, 10.25])
    planner = OpenAIPlanner(
        client=client, model="test-model", monotonic=lambda: next(clock)
    )

    result = planner.plan("Move forward")

    assert result.plan.actions == (MoveAction(0.4, 0.0, 0.0, 2.0),)
    assert result.latency_s == 0.25
    assert result.input_tokens == 21
    assert result.output_tokens == 17
    call = client.responses.calls[0]
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True
    assert call["max_output_tokens"] == 1_000
    assert call["store"] is False


def test_previous_validated_plan_is_sent_as_context():
    previous = validate_plan(
        {
            "accepted": True,
            "message": "Moving.",
            "actions": [
                {"type": "move", "vx": 0.5, "vy": 0, "wz": 0, "duration_s": 3}
            ],
        }
    )
    client = fake_client(
        json.dumps(
            {
                "accepted": True,
                "message": "Repeating more slowly.",
                "actions": [
                    {
                        "type": "move",
                        "vx": 0.25,
                        "vy": 0,
                        "wz": 0,
                        "duration_s": 6,
                    }
                ],
            }
        )
    )
    planner = OpenAIPlanner(client=client)

    planner.plan("Do that again slower", previous)

    content = client.responses.calls[0]["input"][0]["content"]
    assert json.dumps(plan_to_dict(previous), separators=(",", ":")) in content


def test_invalid_provider_json_is_still_rejected_locally():
    client = fake_client(
        '{"accepted":true,"message":"unsafe","actions":'
        '[{"type":"turn","angle_deg":900}]}'
    )
    planner = OpenAIPlanner(client=client)

    with pytest.raises(ValueError, match="between -720 and 720"):
        planner.plan("Turn 900 degrees")


def test_incomplete_or_empty_response_is_rejected():
    with pytest.raises(IncompleteModelResponseError, match="incomplete"):
        OpenAIPlanner(client=fake_client("{}", status="incomplete")).plan("Move")
    with pytest.raises(IncompleteModelResponseError, match="no structured text"):
        OpenAIPlanner(client=fake_client("")).plan("Move")


def test_explicit_model_refusal_is_rejected():
    client = fake_client("")
    client.responses.response.output = [
        {"content": [{"type": "refusal", "refusal": "Cannot assist."}]}
    ]
    with pytest.raises(ModelRefusalError, match="Cannot assist"):
        OpenAIPlanner(client=client).plan("Move")


def test_provider_exception_is_wrapped():
    client = SimpleNamespace(responses=FakeResponses(error=TimeoutError("offline")))
    with pytest.raises(PlannerAPIError, match="TimeoutError"):
        OpenAIPlanner(client=client).plan("Move")


def test_missing_api_key_has_actionable_message(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError, match="OPENAI_API_KEY"):
        OpenAIPlanner()
