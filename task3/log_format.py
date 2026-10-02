"""Small helpers for single-line, machine-readable Task 3 terminal logs."""

from .validator import (
    CommandPlan,
    GotoObjectAction,
    MoveAction,
    StopAction,
    TurnAction,
)


def inline_value(value: object, *, limit: int = 300) -> str:
    """Collapse untrusted text so it cannot forge a second terminal event."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    text = " ".join(str(value).split())
    return (text or "unknown")[:limit]


def optional_count(value: int | None) -> str:
    """Render provider metrics consistently when a count is unavailable."""
    return "na" if value is None else str(value)


def command_log(plan: CommandPlan, *, rejection_reason: str = "unsupported_request") -> str:
    """Render the teacher-facing parsed-command record.

    ``[INPUT]`` owns raw user text. ``[CMD]`` is reserved for the validated
    robot command or a stable rejection reason.
    """
    if not isinstance(plan, CommandPlan):
        raise TypeError("command_log expects a validated CommandPlan")
    if not plan.accepted:
        return f"[CMD] rejected reason={inline_value(rejection_reason, limit=80)}"
    # Match the Task 4 reference transcript exactly for its normal one-target
    # command while preserving the ordered action-list form required by Task 3.
    if len(plan.actions) == 1 and isinstance(plan.actions[0], GotoObjectAction):
        action = plan.actions[0]
        return (
            f"[CMD] goto_object class={action.class_name} color={action.color}"
        )
    actions = ",".join(_action_call(action) for action in plan.actions)
    return f"[CMD] actions={actions} n={len(plan.actions)}"


def _action_call(action: object) -> str:
    if isinstance(action, MoveAction):
        return (
            f"move(vx={action.vx:.2f},vy={action.vy:.2f},wz={action.wz:.2f},"
            f"duration_s={action.duration_s:.2f})"
        )
    if isinstance(action, TurnAction):
        return f"turn(angle_deg={action.angle_deg:.2f})"
    if isinstance(action, GotoObjectAction):
        return f"goto_object(class={action.class_name},color={action.color})"
    if isinstance(action, StopAction):
        return "stop()"
    raise TypeError(f"unsupported validated action: {type(action).__name__}")
