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
from .task4_integration import (
    CameraFrameTimeoutError,
    Task4Integration,
    Task4IntegrationClosedError,
    UnknownSceneObjectError,
    load_object_positions,
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
    "CameraFrameTimeoutError",
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
    "Task4Integration",
    "Task4IntegrationClosedError",
    "TerminalChatLoop",
    "TurnAction",
    "TurnFailedError",
    "UnknownSceneObjectError",
    "build_openai_chat_loop",
    "load_object_positions",
    "parse_and_validate",
    "validate_plan",
]
