"""Blocking Task 3 callbacks over Task 2's non-blocking motion queue.

The MuJoCo thread must keep calling ``Platform.step()``.  This adapter belongs
to the Task 3 command worker and never advances physics itself.
"""

from collections.abc import Callable, Mapping
import math
import threading
import time
from typing import Protocol


class MotionSkillsLike(Protocol):
    """The Task 2 ``MotionSkills`` surface used by this adapter."""

    results: list[dict[str, object]]

    @property
    def busy(self) -> bool: ...

    def move(self, vx: float, vy: float, wz: float, duration: float) -> None: ...

    def turn(self, angle_deg: float) -> None: ...

    def stop(self) -> None: ...


class PlatformLike(Protocol):
    skills: MotionSkillsLike


class Task2AdapterError(RuntimeError):
    """Base class for Task 2 integration failures."""


class PlatformBusyError(Task2AdapterError):
    """Raised instead of mixing a new plan with an existing motion queue."""


class MotionTimeoutError(Task2AdapterError):
    """Raised after cancelling an action that did not finish in wall-clock time."""


class MotionCancelledError(Task2AdapterError):
    """Raised in a waiting worker after another thread calls ``stop``."""


class TurnFailedError(Task2AdapterError):
    """Raised when Task 2 reports a closed-loop turn failure."""

    def __init__(self, result: Mapping[str, object]):
        self.result = dict(result)
        super().__init__(f"Task 2 turn failed: {self.result.get('status', 'unknown status')}")


class MissingTurnResultError(Task2AdapterError):
    """Raised when a turn becomes idle without producing a Task 2 result."""


class Task2MotionAdapter:
    """Expose blocking ``move``/``turn`` callbacks to the Task 3 worker.

    ``MotionSkills`` queues work immediately and finishes it only while the
    simulator thread calls ``Platform.step()``.  The adapter waits for the
    queue to become idle, observes turn result records, and turns cancellation
    or timeout into explicit failures that the future executor can log.
    """

    def __init__(
        self,
        platform: PlatformLike,
        *,
        poll_interval_s: float = 0.01,
        default_timeout_s: float = 180.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not math.isfinite(poll_interval_s) or poll_interval_s <= 0:
            raise ValueError("poll_interval_s must be finite and positive")
        if not math.isfinite(default_timeout_s) or default_timeout_s <= 0:
            raise ValueError("default_timeout_s must be finite and positive")
        self.platform = platform
        self.poll_interval_s = float(poll_interval_s)
        self.default_timeout_s = float(default_timeout_s)
        self._monotonic = monotonic
        self._sleep = sleep
        self._command_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._cancel_generation = 0

    def move(
        self,
        vx: float,
        vy: float,
        wz: float,
        duration_s: float,
        *,
        timeout_s: float | None = None,
    ) -> None:
        """Queue one timed move and return only after Task 2 becomes idle."""
        timeout = self._timeout_or_default(
            timeout_s,
            minimum=max(self.default_timeout_s, float(duration_s) * 5.0 + 10.0),
        )
        with self._command_lock:
            with self._state_lock:
                generation = self._claim_idle_platform("move")
                self.platform.skills.move(vx, vy, wz, duration_s)
            self._wait_until_idle("move", generation, timeout)

    def turn(
        self,
        angle_deg: float,
        *,
        timeout_s: float | None = None,
    ) -> dict[str, object]:
        """Queue a closed-loop turn and return its Task 2 result record."""
        timeout = self._timeout_or_default(
            timeout_s,
            minimum=max(self.default_timeout_s, abs(float(angle_deg)) / 8.0 * 5.0 + 10.0),
        )
        with self._command_lock:
            with self._state_lock:
                generation = self._claim_idle_platform("turn")
                result_count = len(self.platform.skills.results)
                self.platform.skills.turn(angle_deg)
            self._wait_until_idle("turn", generation, timeout)
            new_results = self.platform.skills.results[result_count:]
            if not new_results:
                raise MissingTurnResultError(
                    "Task 2 turn became idle without a result; do not report success"
                )
            result = dict(new_results[-1])
            if result.get("status") != "SUCCESS":
                raise TurnFailedError(result)
            return result

    def stop(self) -> None:
        """Cancel queued/active motion and wake waiting calls as cancelled."""
        with self._state_lock:
            self._cancel_generation += 1
            self.platform.skills.stop()

    def _claim_idle_platform(self, action_name: str) -> int:
        if self.platform.skills.busy:
            raise PlatformBusyError(
                f"cannot start {action_name}: Task 2 motion queue is already busy"
            )
        return self._cancel_generation

    def _wait_until_idle(
        self,
        action_name: str,
        generation: int,
        timeout_s: float,
    ) -> None:
        deadline = self._monotonic() + timeout_s
        while True:
            with self._state_lock:
                if generation != self._cancel_generation:
                    raise MotionCancelledError(f"{action_name} was cancelled")
                if not self.platform.skills.busy:
                    return
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                self.stop()
                raise MotionTimeoutError(
                    f"{action_name} exceeded {timeout_s:.2f} s wall-clock timeout"
                )
            self._sleep(min(self.poll_interval_s, remaining))

    def _timeout_or_default(self, value: float | None, *, minimum: float) -> float:
        if value is None:
            return minimum
        result = float(value)
        if not math.isfinite(result) or result <= 0:
            raise ValueError("timeout_s must be finite and positive")
        return result
