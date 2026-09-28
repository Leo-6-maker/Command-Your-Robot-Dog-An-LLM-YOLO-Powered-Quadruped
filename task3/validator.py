"""Dependency-free semantic validation for Task 3 LLM action plans."""

from dataclasses import dataclass
import json
import math
from typing import Any, TypeAlias


MAX_ACTIONS = 8
MAX_MESSAGE_LENGTH = 300
SUPPORTED_OBJECTS = {"chair": {"red", "green"}}


class PlanValidationError(ValueError):
    """Raised when an LLM plan is unsafe or does not match the contract."""

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


@dataclass(frozen=True)
class MoveAction:
    vx: float
    vy: float
    wz: float
    duration_s: float


@dataclass(frozen=True)
class TurnAction:
    angle_deg: float


@dataclass(frozen=True)
class GotoObjectAction:
    class_name: str
    color: str


@dataclass(frozen=True)
class StopAction:
    pass


RobotAction: TypeAlias = MoveAction | TurnAction | GotoObjectAction | StopAction


@dataclass(frozen=True)
class CommandPlan:
    accepted: bool
    message: str
    actions: tuple[RobotAction, ...]


def _require_object(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PlanValidationError(path, "must be an object")
    if not all(isinstance(key, str) for key in value):
        raise PlanValidationError(path, "object keys must be strings")
    return value


def _require_exact_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    missing = sorted(expected - value.keys())
    extra = sorted(value.keys() - expected)
    if missing:
        raise PlanValidationError(path, f"missing fields: {', '.join(missing)}")
    if extra:
        raise PlanValidationError(path, f"unexpected fields: {', '.join(extra)}")


def _finite_number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanValidationError(path, "must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise PlanValidationError(path, "must be finite")
    return result


def _bounded_number(value: object, path: str, minimum: float, maximum: float) -> float:
    result = _finite_number(value, path)
    if not minimum <= result <= maximum:
        raise PlanValidationError(path, f"must be between {minimum:g} and {maximum:g}")
    return result


def _validate_action(raw: object, index: int) -> RobotAction:
    path = f"$.actions[{index}]"
    action = _require_object(raw, path)
    action_type = action.get("type")
    if not isinstance(action_type, str):
        raise PlanValidationError(f"{path}.type", "must be a string")

    if action_type == "move":
        _require_exact_keys(action, {"type", "vx", "vy", "wz", "duration_s"}, path)
        vx = _bounded_number(action["vx"], f"{path}.vx", -1.0, 1.0)
        vy = _bounded_number(action["vy"], f"{path}.vy", -1.0, 1.0)
        wz = _bounded_number(action["wz"], f"{path}.wz", -1.0, 1.0)
        duration_s = _bounded_number(
            action["duration_s"], f"{path}.duration_s", 0.0, 60.0
        )
        if duration_s == 0.0:
            raise PlanValidationError(f"{path}.duration_s", "must be greater than zero")
        if vx == vy == wz == 0.0:
            raise PlanValidationError(path, "move velocity cannot be all zero")
        return MoveAction(vx=vx, vy=vy, wz=wz, duration_s=duration_s)

    if action_type == "turn":
        _require_exact_keys(action, {"type", "angle_deg"}, path)
        angle_deg = _bounded_number(
            action["angle_deg"], f"{path}.angle_deg", -720.0, 720.0
        )
        if angle_deg == 0.0:
            raise PlanValidationError(f"{path}.angle_deg", "must be non-zero")
        return TurnAction(angle_deg=angle_deg)

    if action_type == "goto_object":
        _require_exact_keys(action, {"type", "class", "color"}, path)
        class_name = action["class"]
        color = action["color"]
        if not isinstance(class_name, str):
            raise PlanValidationError(f"{path}.class", "must be a string")
        if not isinstance(color, str):
            raise PlanValidationError(f"{path}.color", "must be a string")
        if class_name not in SUPPORTED_OBJECTS:
            raise PlanValidationError(f"{path}.class", "unsupported object class")
        if color not in SUPPORTED_OBJECTS[class_name]:
            raise PlanValidationError(f"{path}.color", "unsupported color for object class")
        return GotoObjectAction(class_name=class_name, color=color)

    if action_type == "stop":
        _require_exact_keys(action, {"type"}, path)
        return StopAction()

    raise PlanValidationError(
        f"{path}.type", "must be move, turn, goto_object, or stop"
    )


def validate_plan(raw: object) -> CommandPlan:
    """Validate untrusted decoded JSON and return an immutable typed plan."""
    plan = _require_object(raw, "$")
    _require_exact_keys(plan, {"accepted", "message", "actions"}, "$")

    accepted = plan["accepted"]
    if not isinstance(accepted, bool):
        raise PlanValidationError("$.accepted", "must be a boolean")

    message = plan["message"]
    if not isinstance(message, str):
        raise PlanValidationError("$.message", "must be a string")
    message = message.strip()
    if not message:
        raise PlanValidationError("$.message", "must not be blank")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise PlanValidationError(
            "$.message", f"must not exceed {MAX_MESSAGE_LENGTH} characters"
        )

    raw_actions = plan["actions"]
    if not isinstance(raw_actions, list):
        raise PlanValidationError("$.actions", "must be an array")
    if len(raw_actions) > MAX_ACTIONS:
        raise PlanValidationError("$.actions", f"must contain at most {MAX_ACTIONS} actions")
    if accepted and not raw_actions:
        raise PlanValidationError("$.actions", "accepted plans require at least one action")
    if not accepted and raw_actions:
        raise PlanValidationError("$.actions", "rejected plans must not contain actions")

    actions = tuple(_validate_action(action, index) for index, action in enumerate(raw_actions))
    if any(isinstance(action, StopAction) for action in actions) and len(actions) != 1:
        raise PlanValidationError("$.actions", "stop must be the only action in a plan")
    return CommandPlan(accepted=accepted, message=message, actions=actions)


def _reject_nonstandard_constant(value: str) -> None:
    raise PlanValidationError("$", f"invalid JSON number: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PlanValidationError("$", f"duplicate JSON field: {key}")
        result[key] = value
    return result


def parse_and_validate(text: str) -> CommandPlan:
    """Parse untrusted JSON text, rejecting duplicates, NaN/Inf, and unsafe plans."""
    if not isinstance(text, str):
        raise PlanValidationError("$", "LLM output must be text")
    try:
        raw = json.loads(
            text,
            parse_constant=_reject_nonstandard_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as exc:
        raise PlanValidationError("$", f"invalid JSON: {exc.msg}") from exc
    return validate_plan(raw)
