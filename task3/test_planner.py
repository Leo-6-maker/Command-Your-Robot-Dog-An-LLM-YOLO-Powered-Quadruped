"""Tests for the provider boundary and trusted conversation context."""

import json
from types import SimpleNamespace

import pytest

from task3.planner import (
    IncompleteModelResponseError,
    MissingAPIKeyError,
    ModelRefusalError,
    OllamaPlanner,
    OpenAIPlanner,
    PlannerAPIError,
    SYSTEM_PROMPT,
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


def test_system_prompt_defines_lateral_direction_signs_unambiguously():
    assert "move left means vy > 0" in SYSTEM_PROMPT
    assert "move right" in SYSTEM_PROMPT
    assert "vy=-0.2" in SYSTEM_PROMPT


def test_system_prompt_defines_turn_direction_signs_unambiguously():
    assert '"Turn left 90 degrees." means turn(angle_deg=90)' in SYSTEM_PROMPT
    assert '"Turn right 90 degrees."' in SYSTEM_PROMPT
    assert "turn(angle_deg=-90)" in SYSTEM_PROMPT


def test_system_prompt_explicitly_accepts_both_scene_chairs():
    assert 'goto_object(class="chair", color="green")' in SYSTEM_PROMPT
    assert 'goto_object(class="chair", color="red")' in SYSTEM_PROMPT
    assert "Never reject a request merely because its target is green" in SYSTEM_PROMPT


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
    assert client.responses.calls[0]["store"] is False


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


def test_ollama_planner_uses_schema_zero_temperature_and_local_validation():
    calls = []

    def requester(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {
            "done": True,
            "model": "qwen2.5:7b",
            "message": {
                "content": json.dumps(
                    {
                        "accepted": True,
                        "message": "Moving right.",
                        "actions": [
                            {
                                "type": "move",
                                "vx": 0,
                                "vy": -0.2,
                                "wz": 0,
                                "duration_s": 1,
                            }
                        ],
                    }
                )
            },
            "prompt_eval_count": 120,
            "eval_count": 30,
        }

    clock = iter([5.0, 5.4])
    planner = OllamaPlanner(
        model="qwen2.5:7b",
        host="http://localhost:11434/",
        requester=requester,
        monotonic=lambda: next(clock),
    )

    result = planner.plan("Move right at speed 0.2 for one second")

    assert result.provider == "ollama"
    assert result.model == "qwen2.5:7b"
    assert result.plan.actions == (MoveAction(0.0, -0.2, 0.0, 1.0),)
    assert result.input_tokens == 120
    assert result.output_tokens == 30
    assert result.latency_s == pytest.approx(0.4)
    url, payload, timeout = calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert payload["format"]["additionalProperties"] is False
    assert payload["options"] == {"temperature": 0, "seed": 42}
    assert "Required JSON schema" in payload["messages"][0]["content"]
    assert timeout == 120.0


def test_ollama_planner_rejects_incomplete_and_wraps_connection_errors():
    incomplete = OllamaPlanner(
        requester=lambda _url, _payload, _timeout: {
            "done": False,
            "message": {"content": "{}"},
        }
    )
    with pytest.raises(IncompleteModelResponseError, match="incomplete"):
        incomplete.plan("Move forward")

    def offline(_url, _payload, _timeout):
        raise ConnectionError("offline")

    with pytest.raises(PlannerAPIError, match="Ollama request failed"):
        OllamaPlanner(requester=offline).plan("Move forward")
