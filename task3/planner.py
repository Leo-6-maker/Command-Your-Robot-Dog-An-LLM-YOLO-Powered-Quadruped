"""OpenAI-backed natural-language planner for Task 3."""

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
import time
from typing import Any, Protocol

from .schema import openai_response_format
from .validator import (
    CommandPlan,
    GotoObjectAction,
    MoveAction,
    StopAction,
    TurnAction,
    parse_and_validate,
)


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
MAX_COMMAND_LENGTH = 1_000
MAX_OUTPUT_TOKENS = 1_000

SYSTEM_PROMPT = """You convert English robot-dog commands into one JSON action plan.

Follow these rules exactly:
- Accept only safe, relevant commands written in English. Reject non-English, unrelated,
  ambiguous, impossible, harmful, or unsupported requests with accepted=false and actions=[].
- Never silently clamp an unsafe value. Reject it instead.
- Supported actions are move, turn, goto_object, and stop, exactly as defined by the schema.
- Coordinates: vx positive=forward, vx negative=backward; vy positive=left,
  vy negative=right; wz positive=counter-clockwise.
- Prefer turn for requested angles. Positive angles turn left/counter-clockwise and negative
  angles turn right/clockwise. If direction is given without an angle, use 90 degrees.
- For a vague movement without speed or duration, use speed magnitude 0.4 for 2 seconds.
- An explicitly requested non-zero speed whose components remain within [-1, 1] is valid;
  0.4 is a default, not a minimum speed.
- goto_object supports only a red chair or green chair.
- Preserve the user's requested order in multi-step commands.
- stop must be the only action in its plan.
- A previous successful plan may be supplied for contextual phrases such as "do that again".
  With no applicable previous plan, reject context-dependent input. "Again" repeats the plan.
  Words such as "slowly" or "faster" that directly modify a new explicit movement are not
  contextual by themselves; only references such as "that", "again", or "the same" require
  a previous plan.
  For "again slower" applied to move actions, halve nonzero velocities and double duration
  to preserve approximate distance, but reject if this exceeds schema limits. A turn action
  has no speed parameter, so reject requests to turn slower rather than pretending to comply.
- Keep message non-blank, short, and in English. Return only data matching the supplied JSON schema.

Interpretation examples:
- "Move forward slowly for two seconds." with previous plan null is a complete new command:
  accept move(vx=0.2, vy=0, wz=0, duration_s=2).
- "Move forward at speed 0.3 for two seconds." is valid: accept move with vx=0.3.
- "Do that again, but slower." with a previous move(vx=0.4, duration_s=2) means
  move(vx=0.2, duration_s=4); preserve other velocity signs and halve magnitudes.
- "Do that again." with previous plan null is contextual and must be rejected.
- Requests to write, answer questions, attack, collide with, or damage something must be rejected.
"""


class ResponsesClient(Protocol):
    def create(self, **kwargs: object) -> object: ...


class OpenAIClientLike(Protocol):
    responses: ResponsesClient


class PlannerError(RuntimeError):
    """Base class for errors before a plan reaches the executor."""


class MissingAPIKeyError(PlannerError):
    """Raised when no OpenAI API credential is available."""


class PlannerAPIError(PlannerError):
    """Raised when the provider request fails."""


class IncompleteModelResponseError(PlannerError):
    """Raised when the provider returns no complete structured output."""


class ModelRefusalError(PlannerError):
    """Raised when the provider explicitly refuses the request."""


@dataclass(frozen=True)
class PlanningResult:
    plan: CommandPlan
    provider: str
    model: str
    latency_s: float
    raw_json: str
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class OpenAIPlanner:
    """Translate one English command into a locally validated command plan."""

    def __init__(
        self,
        *,
        model: str | None = None,
        client: OpenAIClientLike | None = None,
        timeout_s: float = 30.0,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.model = model or os.getenv("TASK3_OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self.timeout_s = float(timeout_s)
        self._monotonic = monotonic
        self._client = client or _default_openai_client()

    def plan(
        self,
        command: str,
        previous_plan: CommandPlan | None = None,
    ) -> PlanningResult:
        """Call Structured Outputs, then enforce the independent local validator."""
        if not isinstance(command, str):
            raise TypeError("command must be text")
        command = command.strip()
        if not command:
            raise ValueError("command must not be blank")
        if len(command) > MAX_COMMAND_LENGTH:
            raise ValueError(f"command must not exceed {MAX_COMMAND_LENGTH} characters")

        context = (
            json.dumps(plan_to_dict(previous_plan), separators=(",", ":"))
            if previous_plan is not None
            else "null"
        )
        user_input = (
            "Current English command:\n"
            f"{command}\n\n"
            "Previous successful validated plan (JSON or null):\n"
            f"{context}"
        )
        started = self._monotonic()
        try:
            response = self._client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=[{"role": "user", "content": user_input}],
                text={"format": openai_response_format()},
                max_output_tokens=MAX_OUTPUT_TOKENS,
                timeout=self.timeout_s,
                store=False,
            )
        except Exception as exc:
            raise PlannerAPIError(
                f"OpenAI request failed ({type(exc).__name__}): {exc}"
            ) from exc
        latency_s = self._monotonic() - started

        status = getattr(response, "status", None)
        if status not in (None, "completed"):
            detail = getattr(response, "incomplete_details", None)
            raise IncompleteModelResponseError(
                f"OpenAI response status is {status}: {detail or 'no details'}"
            )
        refusal = _find_refusal(response)
        if refusal is not None:
            raise ModelRefusalError(f"OpenAI refused the command: {refusal}")
        raw_json = getattr(response, "output_text", None)
        if not isinstance(raw_json, str) or not raw_json.strip():
            raise IncompleteModelResponseError(
                "OpenAI returned no structured text (it may have refused)"
            )

        plan = parse_and_validate(raw_json)
        usage = getattr(response, "usage", None)
        return PlanningResult(
            plan=plan,
            provider="openai",
            model=self.model,
            latency_s=latency_s,
            raw_json=raw_json,
            response_id=_optional_str(getattr(response, "id", None)),
            input_tokens=_optional_int(getattr(usage, "input_tokens", None)),
            output_tokens=_optional_int(getattr(usage, "output_tokens", None)),
        )


def plan_to_dict(plan: CommandPlan) -> dict[str, Any]:
    """Serialize only trusted typed plans for provider-neutral conversation context."""
    actions: list[dict[str, Any]] = []
    for action in plan.actions:
        if isinstance(action, MoveAction):
            actions.append(
                {
                    "type": "move",
                    "vx": action.vx,
                    "vy": action.vy,
                    "wz": action.wz,
                    "duration_s": action.duration_s,
                }
            )
        elif isinstance(action, TurnAction):
            actions.append({"type": "turn", "angle_deg": action.angle_deg})
        elif isinstance(action, GotoObjectAction):
            actions.append(
                {"type": "goto_object", "class": action.class_name, "color": action.color}
            )
        elif isinstance(action, StopAction):
            actions.append({"type": "stop"})
        else:  # CommandPlan can only contain the validator's closed action union.
            raise TypeError(f"unsupported action: {type(action).__name__}")
    return {"accepted": plan.accepted, "message": plan.message, "actions": actions}


def _default_openai_client() -> OpenAIClientLike:
    if not os.getenv("OPENAI_API_KEY"):
        raise MissingAPIKeyError(
            "OPENAI_API_KEY is not set; export it in the terminal before starting Task 3"
        )
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise PlannerError(
            "the openai package is missing; install task3/requirements-task3.txt"
        ) from exc
    return OpenAI()


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _find_refusal(response: object) -> str | None:
    """Find the explicit refusal content used by the Responses API."""
    output = _field(response, "output")
    if not isinstance(output, list):
        return None
    for item in output:
        content = _field(item, "content")
        if not isinstance(content, list):
            continue
        for part in content:
            if _field(part, "type") == "refusal":
                refusal = _field(part, "refusal")
                return str(refusal or "no reason supplied")
    return None


def _field(value: object, name: str) -> object:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)
