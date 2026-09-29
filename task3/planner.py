"""OpenAI-backed natural-language planner for Task 3."""

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
import time
from typing import Any, Protocol
from urllib.request import Request, urlopen

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
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
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
- Direction words must preserve those signs exactly: move left means vy > 0 and move right
  means vy < 0. Never use positive vy for a rightward command.
- Prefer turn for requested angles. Positive angles turn left/counter-clockwise and negative
  angles turn right/clockwise. If direction is given without an angle, use 90 degrees.
- For a vague movement without speed or duration, use speed magnitude 0.4 for 2 seconds.
- An explicitly requested non-zero speed whose components remain within [-1, 1] is valid;
  0.4 is a default, not a minimum speed.
- goto_object supports exactly two scene targets: red chair AND green chair. Both colors are
  valid and equally supported. Never reject a request merely because its target is green.
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
- "Move left at speed 0.3 for two seconds." means move(vx=0, vy=0.3, wz=0,
  duration_s=2), while "Move right at speed 0.2 for one second." means
  move(vx=0, vy=-0.2, wz=0, duration_s=1).
- "Turn left 90 degrees." means turn(angle_deg=90), while "Turn right 90 degrees."
  means turn(angle_deg=-90). Never use a positive angle for a right turn.
- "Do that again, but slower." with a previous move(vx=0.4, duration_s=2) means
  move(vx=0.2, duration_s=4); preserve other velocity signs and halve magnitudes.
- "Do that again." with previous plan null is contextual and must be rejected.
- "Go to the green chair." is valid: accept goto_object(class="chair", color="green").
- "Go to the red chair." is valid: accept goto_object(class="chair", color="red").
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

        user_input = _planner_user_input(command, previous_plan)
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


OllamaRequester = Callable[[str, dict[str, Any], float], dict[str, Any]]


class OllamaPlanner:
    """Translate commands with a local Ollama model, then validate locally."""

    def __init__(
        self,
        *,
        model: str | None = None,
        host: str | None = None,
        timeout_s: float = 120.0,
        requester: OllamaRequester | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.model = model or os.getenv("TASK3_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.host = (host or os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)).rstrip("/")
        if not self.host.startswith(("http://", "https://")):
            raise ValueError("Ollama host must start with http:// or https://")
        self.timeout_s = float(timeout_s)
        self._requester = requester or _ollama_post_json
        self._monotonic = monotonic

    def plan(
        self,
        command: str,
        previous_plan: CommandPlan | None = None,
    ) -> PlanningResult:
        if not isinstance(command, str):
            raise TypeError("command must be text")
        command = command.strip()
        if not command:
            raise ValueError("command must not be blank")
        if len(command) > MAX_COMMAND_LENGTH:
            raise ValueError(f"command must not exceed {MAX_COMMAND_LENGTH} characters")

        from .schema import load_action_plan_schema

        schema = load_action_plan_schema()
        grounded_prompt = (
            SYSTEM_PROMPT
            + "\n\nRequired JSON schema:\n"
            + json.dumps(schema, separators=(",", ":"))
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": grounded_prompt},
                {
                    "role": "user",
                    "content": _planner_user_input(command, previous_plan),
                },
            ],
            "format": schema,
            "stream": False,
            "options": {"temperature": 0, "seed": 42},
            "keep_alive": "5m",
        }
        started = self._monotonic()
        try:
            response = self._requester(
                f"{self.host}/api/chat", payload, self.timeout_s
            )
        except Exception as exc:
            raise PlannerAPIError(
                f"Ollama request failed ({type(exc).__name__}): {exc}"
            ) from exc
        latency_s = self._monotonic() - started

        if not isinstance(response, dict) or response.get("done") is False:
            raise IncompleteModelResponseError("Ollama returned an incomplete response")
        message = response.get("message")
        raw_json = message.get("content") if isinstance(message, dict) else None
        if not isinstance(raw_json, str) or not raw_json.strip():
            raise IncompleteModelResponseError("Ollama returned no structured text")

        plan = parse_and_validate(raw_json)
        response_model = response.get("model")
        return PlanningResult(
            plan=plan,
            provider="ollama",
            model=response_model if isinstance(response_model, str) else self.model,
            latency_s=latency_s,
            raw_json=raw_json,
            input_tokens=_optional_int(response.get("prompt_eval_count")),
            output_tokens=_optional_int(response.get("eval_count")),
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


def _planner_user_input(
    command: str,
    previous_plan: CommandPlan | None,
) -> str:
    context = (
        json.dumps(plan_to_dict(previous_plan), separators=(",", ":"))
        if previous_plan is not None
        else "null"
    )
    return (
        "Current English command:\n"
        f"{command}\n\n"
        "Previous successful validated plan (JSON or null):\n"
        f"{context}"
    )


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


def _ollama_post_json(
    url: str,
    payload: dict[str, Any],
    timeout_s: float,
) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_s) as response:
        body = json.load(response)
    if not isinstance(body, dict):
        raise TypeError("Ollama response body must be a JSON object")
    return body


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
