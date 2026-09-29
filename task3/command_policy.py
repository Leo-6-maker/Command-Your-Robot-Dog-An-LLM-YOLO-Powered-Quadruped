"""Provider-neutral local rejection rules for terminal commands."""

import re
import unicodedata

from .validator import CommandPlan, MoveAction, TurnAction


_DANGEROUS_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\battack\b",
        r"\bhurt\b",
        r"\binjure\b",
        r"\bhit\b",
        r"\bram\b",
        r"\bcrash\b",
        r"\bdestroy\b",
        r"\bdamage\b",
        r"\brun\s+over\b",
        r"\bknock\s+over\b",
    )
)


def local_rejection_reason(command: str) -> str | None:
    """Reject clear policy violations before any paid provider request.

    Ambiguous and unrelated English commands are intentionally left to the LLM;
    this local layer only handles cases that can be identified conservatively.
    """
    if not isinstance(command, str):
        raise TypeError("command must be text")
    if any(_is_non_ascii_letter(character) for character in command):
        return "Please enter the robot command in English."
    if any(pattern.search(command) for pattern in _DANGEROUS_PATTERNS):
        return "Unsafe or harmful robot commands are not allowed."
    return None


_TRANSLATION_DIRECTION = re.compile(
    r"\b(?:move|go|walk|step|slide|strafe)\s+"
    r"(?:(?:sideways|laterally)\s+)?"
    r"(?:(?:towards?|to)\s+)?(?:your\s+)?"
    r"(forward|forwards|backward|backwards|left|right)\b",
    re.IGNORECASE,
)
_TURN_DIRECTION = re.compile(r"\bturn\s+(left|right)\b", re.IGNORECASE)


def plan_consistency_reason(command: str, plan: CommandPlan) -> str | None:
    """Reject one-action plans that reverse an explicit user direction.

    Schema validation proves that velocities are safe numbers, but not that the
    numbers still mean what the user requested. Complex multi-action commands
    are deliberately left to the planner instead of guessing clause mappings.
    """
    if not plan.accepted or len(plan.actions) != 1:
        return None

    action = plan.actions[0]
    translation = _TRANSLATION_DIRECTION.search(command)
    if translation and isinstance(action, MoveAction):
        direction = translation.group(1).lower()
        expected_axis, expected_sign = {
            "forward": ("vx", 1),
            "forwards": ("vx", 1),
            "backward": ("vx", -1),
            "backwards": ("vx", -1),
            "left": ("vy", 1),
            "right": ("vy", -1),
        }[direction]
        actual = getattr(action, expected_axis)
        if actual == 0.0 or (actual > 0) != (expected_sign > 0):
            operator = ">0" if expected_sign > 0 else "<0"
            return (
                f"direction_mismatch command={direction} expected="
                f"{expected_axis}{operator} actual={actual:.2f}"
            )

    turn = _TURN_DIRECTION.search(command)
    if turn and isinstance(action, TurnAction):
        direction = turn.group(1).lower()
        expected_sign = 1 if direction == "left" else -1
        if (action.angle_deg > 0) != (expected_sign > 0):
            operator = ">0" if expected_sign > 0 else "<0"
            return (
                f"direction_mismatch command=turn_{direction} expected="
                f"angle_deg{operator} actual={action.angle_deg:.2f}"
            )
    return None


def _is_non_ascii_letter(character: str) -> bool:
    return ord(character) > 127 and unicodedata.category(character).startswith("L")
