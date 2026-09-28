"""Task 3 natural-language command planning and execution."""

from .chat_loop import TerminalChatLoop, build_openai_chat_loop
from .executor import (
    ExecutionResult,
    GotoObjectMissionFailedError,
    GotoObjectUnavailableError,
    PlanExecutor,
)
from .planner import (
    IncompleteModelResponseError,
    MissingAPIKeyError,
    ModelRefusalError,
    OpenAIPlanner,
    PlannerAPIError,
    PlannerError,
    PlanningResult,
)
from .task2_adapter import (
    MissingTurnResultError,
    MotionCancelledError,
    MotionTimeoutError,
    PlatformBusyError,
    Task2AdapterError,
    Task2MotionAdapter,
    TurnFailedError,
)
from .validator import (
    CommandPlan,
    GotoObjectAction,
    MoveAction,
    PlanValidationError,
    StopAction,
    TurnAction,
    parse_and_validate,
    validate_plan,
)

__all__ = [
    "CommandPlan",
    "ExecutionResult",
    "GotoObjectAction",
    "GotoObjectMissionFailedError",
    "GotoObjectUnavailableError",
    "IncompleteModelResponseError",
    "MissingAPIKeyError",
    "ModelRefusalError",
    "MoveAction",
    "MissingTurnResultError",
    "MotionCancelledError",
    "MotionTimeoutError",
    "OpenAIPlanner",
    "PlanValidationError",
    "PlanExecutor",
    "PlannerAPIError",
    "PlannerError",
    "PlanningResult",
    "PlatformBusyError",
    "StopAction",
    "Task2AdapterError",
    "Task2MotionAdapter",
    "TerminalChatLoop",
    "TurnAction",
    "TurnFailedError",
    "build_openai_chat_loop",
    "parse_and_validate",
    "validate_plan",
]
