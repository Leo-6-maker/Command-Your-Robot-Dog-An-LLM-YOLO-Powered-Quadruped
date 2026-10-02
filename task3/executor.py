"""Sequential execution of validated Task 3 command plans."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import threading
from typing import Literal, Protocol

from .log_format import inline_value
from .task2_adapter import MotionCancelledError
from .validator import (
    CommandPlan,
    GotoObjectAction,
    MoveAction,
    RobotAction,
    StopAction,
    TurnAction,
)


ExecutionStatus = Literal["SUCCESS", "REJECTED", "FAIL", "CANCELLED"]


class MotionController(Protocol):
    """Blocking motion interface supplied by ``Task2MotionAdapter``."""

    def move(self, vx: float, vy: float, wz: float, duration_s: float) -> None: ...

    def turn(self, angle_deg: float) -> Mapping[str, object]: ...

    def stop(self) -> None: ...


class GotoObjectUnavailableError(RuntimeError):
    """Raised until the Task 4 callback has been connected."""


class GotoObjectMissionFailedError(RuntimeError):
    """Raised when Task 4 runs but does not reach the requested object."""


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    completed_actions: int
    total_actions: int
    message: str
    failed_step: int | None = None
    error_type: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "SUCCESS"


class PlanExecutor:
    """Run a validated plan in order and stop at the first failure.

    ``execute`` is intentionally blocking and must run in the future command
    worker, never in the MuJoCo physics thread. Concurrent calls are
    serialized so two LLM plans cannot interleave their robot actions.
    """

    def __init__(
        self,
        motion: MotionController,
        *,
        goto_object: Callable[[str, str], bool] | None = None,
        goto_object_multigoal: Callable[[str, str], bool] | None = None,
        logger: Callable[[str], None] = print,
    ):
        self.motion = motion
        self.goto_object = goto_object
        self.goto_object_multigoal = goto_object_multigoal
        self.log = logger
        self._execution_lock = threading.Lock()
        self._cancel_requested = threading.Event()

    def execute(self, plan: CommandPlan) -> ExecutionResult:
        """Execute one immutable, already-validated command plan."""
        if not isinstance(plan, CommandPlan):
            raise TypeError("execute expects a validated CommandPlan")

        with self._execution_lock:
            self._cancel_requested.clear()
            total = len(plan.actions)
            self.log(
                f"[PLAN] accepted={str(plan.accepted).lower()} actions={total} "
                f"message={inline_value(plan.message)}"
            )
            if not plan.accepted:
                self.log(
                    f"[DONE] status=REJECTED actions=0 reason={inline_value(plan.message)}"
                )
                return ExecutionResult(
                    status="REJECTED",
                    completed_actions=0,
                    total_actions=0,
                    message=plan.message,
                )

            completed = 0
            multi_goal = sum(isinstance(a, GotoObjectAction) for a in plan.actions) > 1
            for index, action in enumerate(plan.actions, start=1):
                try:
                    if self._cancel_requested.is_set():
                        raise MotionCancelledError("plan was cancelled")
                    self.log(_start_log(action, index, total))
                    completion = self._dispatch(action, multi_goal=multi_goal)
                    if (
                        isinstance(action, GotoObjectAction)
                        and index < total
                        and isinstance(plan.actions[index], GotoObjectAction)
                    ):
                        # Clear the reached object before searching for the
                        # next goal. This is bounded local motion, independent
                        # of scene truth and absent from one-goal missions.
                        self.log(f"[TRANSITION] after={index}/{total} retreat_s=1.50")
                        self.motion.move(-0.30, 0.0, 0.0, 1.50)
                    completed += 1
                    self.log(
                        f"[EXEC] step={index}/{total} type={_action_type(action)} "
                        f"status=SUCCESS{completion}"
                    )
                except MotionCancelledError as exc:
                    reason = inline_value(exc)
                    self.log(
                        f"[DONE] status=CANCELLED completed={completed}/{total} "
                        f"reason={reason}"
                    )
                    return ExecutionResult(
                        status="CANCELLED",
                        completed_actions=completed,
                        total_actions=total,
                        message=str(exc),
                        failed_step=index,
                        error_type=type(exc).__name__,
                    )
                except Exception as exc:
                    stop_error = self._stop_after_failure(action)
                    reason = inline_value(exc)
                    suffix = f" stop_error={inline_value(stop_error)}" if stop_error else ""
                    self.log(
                        f"[DONE] status=FAIL step={index}/{total} "
                        f"type={_action_type(action)} error={type(exc).__name__} "
                        f"reason={reason}{suffix}"
                    )
                    return ExecutionResult(
                        status="FAIL",
                        completed_actions=completed,
                        total_actions=total,
                        message=str(exc),
                        failed_step=index,
                        error_type=type(exc).__name__,
                    )

            self.log(f"[DONE] status=SUCCESS actions={completed}")
            return ExecutionResult(
                status="SUCCESS",
                completed_actions=completed,
                total_actions=total,
                message=plan.message,
            )

    def cancel(self) -> None:
        """Request cancellation from another thread and clear Task 2 motion."""
        self._cancel_requested.set()
        self.motion.stop()

    def _dispatch(self, action: RobotAction, *, multi_goal: bool = False) -> str:
        if isinstance(action, MoveAction):
            self.motion.move(action.vx, action.vy, action.wz, action.duration_s)
            return ""
        if isinstance(action, TurnAction):
            result = self.motion.turn(action.angle_deg)
            error = result.get("final_error_deg")
            return "" if error is None else f" final_error_deg={float(error):.2f}"
        if isinstance(action, GotoObjectAction):
            callback = (
                self.goto_object_multigoal
                if multi_goal and self.goto_object_multigoal is not None
                else self.goto_object
            )
            if callback is None:
                raise GotoObjectUnavailableError("Task 4 goto_object is not connected")
            if not callback(action.class_name, action.color):
                raise GotoObjectMissionFailedError(
                    f"could not reach {action.color} {action.class_name}"
                )
            return ""
        if isinstance(action, StopAction):
            self.motion.stop()
            return ""
        raise TypeError(f"unsupported validated action: {type(action).__name__}")

    def _stop_after_failure(self, action: RobotAction) -> Exception | None:
        if isinstance(action, StopAction):
            return None
        try:
            self.motion.stop()
        except Exception as exc:  # preserve the original action failure
            return exc
        return None


def _action_type(action: RobotAction) -> str:
    if isinstance(action, MoveAction):
        return "move"
    if isinstance(action, TurnAction):
        return "turn"
    if isinstance(action, GotoObjectAction):
        return "goto_object"
    if isinstance(action, StopAction):
        return "stop"
    return type(action).__name__


def _start_log(action: RobotAction, index: int, total: int) -> str:
    prefix = f"[EXEC] step={index}/{total} type={_action_type(action)}"
    if isinstance(action, MoveAction):
        return (
            f"{prefix} vx={action.vx:.2f} vy={action.vy:.2f} wz={action.wz:.2f} "
            f"duration_s={action.duration_s:.2f}"
        )
    if isinstance(action, TurnAction):
        return f"{prefix} angle_deg={action.angle_deg:.2f}"
    if isinstance(action, GotoObjectAction):
        return f"{prefix} class={action.class_name} color={action.color}"
    return prefix
