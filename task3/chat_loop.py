"""Asynchronous terminal chat loop for Task 3."""

from collections.abc import Callable
import threading
from typing import Protocol

from .command_policy import local_rejection_reason
from .executor import ExecutionResult, PlanExecutor
from .planner import OpenAIPlanner, PlanningResult
from .validator import CommandPlan, validate_plan


class PlannerLike(Protocol):
    def plan(
        self,
        command: str,
        previous_plan: CommandPlan | None = None,
    ) -> PlanningResult: ...


class ExecutorLike(Protocol):
    def execute(self, plan: CommandPlan) -> ExecutionResult: ...

    def cancel(self) -> None: ...


class TerminalChatLoop:
    """Read commands without running LLM or robot work on the simulator thread.

    Start ``run`` in a terminal thread while the main thread keeps calling
    ``Platform.step()``. Each accepted line starts one command worker. A second
    ordinary command is rejected while it is busy, but ``/stop`` remains
    immediately available.
    """

    def __init__(
        self,
        planner: PlannerLike,
        executor: ExecutorLike,
        *,
        logger: Callable[[str], None] = print,
        input_fn: Callable[[str], str] = input,
    ):
        self.planner = planner
        self.executor = executor
        self.log = logger
        self.input_fn = input_fn
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._cancel_requested = threading.Event()
        self._quit_requested = threading.Event()
        self._previous_successful_plan: CommandPlan | None = None

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._worker is not None and self._worker.is_alive()

    @property
    def previous_successful_plan(self) -> CommandPlan | None:
        with self._lock:
            return self._previous_successful_plan

    @property
    def quit_requested(self) -> bool:
        """Tell the simulator owner thread that the user entered ``/quit``."""
        return self._quit_requested.is_set()

    def submit(self, command: str) -> bool:
        """Start one LLM→validator→executor job; return False when already busy."""
        command = command.strip()
        if not command:
            self.log("[DONE] status=REJECTED stage=input reason=empty_command")
            return False
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                self.log("[CHAT] busy; use /stop or wait for [DONE]")
                return False
            self._cancel_requested.clear()
            self.log(f"[CMD] {_single_line(command)}")
            self._worker = threading.Thread(
                target=self._process_command,
                args=(command,),
                name="task3-command-worker",
                daemon=True,
            )
            self._worker.start()
            return True

    def cancel(self) -> None:
        """Cancel model-to-executor handoff and any action already in progress."""
        self._cancel_requested.set()
        self.executor.cancel()
        self.log("[CHAT] stop requested")

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for the current command; return True if it has finished."""
        with self._lock:
            worker = self._worker
        if worker is None:
            return True
        worker.join(timeout)
        return not worker.is_alive()

    def handle_line(self, line: str) -> bool:
        """Handle one terminal line; return False only when the loop should exit."""
        stripped = line.strip()
        local = stripped.lower()
        if local in {"/quit", "/exit"}:
            self._quit_requested.set()
            self.cancel()
            return False
        if local == "/stop":
            self.cancel()
            return True
        if local == "/status":
            self.log(f"[CHAT] status={'BUSY' if self.busy else 'IDLE'}")
            return True
        if local == "/help":
            self.log("[CHAT] commands: /status /stop /help /quit")
            return True
        self.submit(stripped)
        return True

    def run(self) -> None:
        """Run the interactive prompt; launch this method outside the sim thread."""
        self.log("[CHAT] Task 3 ready. Enter an English command; /help shows controls.")
        while True:
            try:
                line = self.input_fn("robot> ")
            except EOFError:
                self.cancel()
                break
            except KeyboardInterrupt:
                self.log("")
                self._quit_requested.set()
                self.cancel()
                break
            if not self.handle_line(line):
                break
        self.log("[CHAT] terminal loop closed")

    def _process_command(self, command: str) -> None:
        stage = "planning"
        try:
            local_reason = local_rejection_reason(command)
            if local_reason is not None:
                plan = validate_plan(
                    {"accepted": False, "message": local_reason, "actions": []}
                )
                self.log(
                    "[LLM] provider=local model=command-policy latency_s=0.000 "
                    "accepted=false actions=0"
                )
                self.executor.execute(plan)
                return
            with self._lock:
                previous_plan = self._previous_successful_plan
            planning = self.planner.plan(command, previous_plan)
            plan = planning.plan
            self.log(
                f"[LLM] provider={planning.provider} model={planning.model} "
                f"latency_s={planning.latency_s:.3f} accepted="
                f"{str(plan.accepted).lower()} actions={len(plan.actions)}"
            )
            if self._cancel_requested.is_set():
                self.log("[DONE] status=CANCELLED stage=planning")
                return
            stage = "execution"
            result = self.executor.execute(plan)
            if result.status == "SUCCESS" and plan.accepted:
                with self._lock:
                    self._previous_successful_plan = plan
        except Exception as exc:
            self.log(
                f"[DONE] status=ERROR stage={stage} "
                f"error={type(exc).__name__} reason={_single_line(exc)}"
            )


def build_openai_chat_loop(
    executor: PlanExecutor,
    *,
    model: str | None = None,
    logger: Callable[[str], None] = print,
) -> TerminalChatLoop:
    """Convenience constructor used by the future simulator entry point."""
    return TerminalChatLoop(OpenAIPlanner(model=model), executor, logger=logger)


def _single_line(value: object, limit: int = 500) -> str:
    text = " ".join(str(value).split())
    return (text or "unknown")[:limit]
