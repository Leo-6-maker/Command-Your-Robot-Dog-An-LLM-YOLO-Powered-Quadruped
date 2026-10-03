"""Task 3 planning and execution. Task 3/bonus lead: ZIYAN WANG (A0352514L)."""

from .chat_loop import TerminalChatLoop, build_ollama_chat_loop, build_openai_chat_loop
from .command_policy import local_rejection_reason
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
    OllamaPlanner,
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
    "OllamaPlanner",
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
    "build_ollama_chat_loop",
    "load_object_positions",
    "local_rejection_reason",
    "parse_and_validate",
    "validate_plan",
]
