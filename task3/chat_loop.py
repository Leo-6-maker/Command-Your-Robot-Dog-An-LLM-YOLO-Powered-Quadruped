"""Asynchronous terminal chat loop for Task 3."""

from collections.abc import Callable
import threading
from typing import Protocol

from .command_policy import local_rejection, plan_consistency_reason
from .executor import ExecutionResult, PlanExecutor
from .log_format import command_log, inline_value, optional_count
from .planner import CompatibleChatPlanner, OllamaPlanner, OpenAIPlanner, PlanningResult
from .validator import CommandPlan, validate_plan
from .speech_input import LocalSpeechInput, SpeechInputError


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
        speech_input: LocalSpeechInput | None = None,
    ):
        self.planner = planner
        self.executor = executor
        self.log = logger
        self.input_fn = input_fn
        self.speech_input = speech_input
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._cancel_requested = threading.Event()
        self._quit_requested = threading.Event()
        self._reset_requested = threading.Event()
        self._previous_successful_plan: CommandPlan | None = None
        self._last_execution_result: ExecutionResult | None = None

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

    @property
    def last_execution_result(self) -> ExecutionResult | None:
        with self._lock:
            return self._last_execution_result

    @property
    def reset_requested(self) -> bool:
        return self._reset_requested.is_set()

    def request_reset(self) -> bool:
        """Ask the simulator owner to reset only when no command is running."""
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                self.log("[RESET] status=REJECTED reason=command_busy")
                return False
            if self._reset_requested.is_set():
                self.log("[RESET] status=PENDING")
                return False
            self._reset_requested.set()
            self.log("[RESET] status=REQUESTED")
            return True

    def finish_reset(self, *, error: Exception | None = None) -> None:
        """Called by the simulator thread after resetting physics and camera."""
        with self._lock:
            if error is None:
                self._previous_successful_plan = None
                self._last_execution_result = None
                self._cancel_requested.clear()
                self.log("[RESET] status=SUCCESS position=initial")
            else:
                self.log(
                    f"[RESET] status=FAIL error={type(error).__name__} "
                    f"reason={inline_value(error, limit=300)}"
                )
            self._reset_requested.clear()

    def submit(self, command: str) -> bool:
        """Start one LLM→validator→executor job; return False when already busy."""
        command = command.strip()
        if not command:
            self.log("[INPUT] text=empty")
            rejected = validate_plan(
                {"accepted": False, "message": "The command is empty.", "actions": []}
            )
            self.log(command_log(rejected, rejection_reason="empty_input"))
            self.log("[DONE] status=REJECTED stage=input reason=empty_command")
            return False
        with self._lock:
            if self._reset_requested.is_set():
                self.log("[CHAT] status=RESETTING hint=wait_for_reset_success")
                return False
            if self._worker is not None and self._worker.is_alive():
                self.log("[CHAT] status=BUSY hint=/stop")
                return False
            self._cancel_requested.clear()
            self._last_execution_result = None
            self.log(f"[INPUT] text={inline_value(command, limit=500)}")
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
        self.log("[CHAT] event=STOP_REQUESTED")

    def submit_voice(self, audio_file: str | None = None) -> bool:
        """Transcribe on a worker, then use the same planner and executor path."""
        if self.speech_input is None:
            self.log("[STT] status=UNAVAILABLE hint=enable_voice_input")
            return False
        with self._lock:
            if self._reset_requested.is_set():
                self.log("[CHAT] status=RESETTING hint=wait_for_reset_success")
                return False
            if self._worker is not None and self._worker.is_alive():
                self.log("[CHAT] status=BUSY hint=/stop")
                return False
            self._cancel_requested.clear()
            self._last_execution_result = None
            self._worker = threading.Thread(
                target=self._process_voice, args=(audio_file,),
                name="task3-voice-worker", daemon=True,
            )
            self._worker.start()
            return True

    def _process_voice(self, audio_file: str | None) -> None:
        try:
            if audio_file is None:
                self.log("[STT] status=RECORDING")
                result = self.speech_input.record_and_transcribe()
            else:
                self.log("[STT] status=TRANSCRIBING source=file")
                result = self.speech_input.transcribe_file(audio_file)
            self.log(
                f"[STT] status=OK model={inline_value(result.model, limit=80)} "
                f"latency_s={result.latency_s:.3f} text={inline_value(result.text, limit=500)}"
            )
            if self._cancel_requested.is_set():
                self.log("[DONE] status=CANCELLED stage=stt")
                return
            self.log(f"[INPUT] text={inline_value(result.text, limit=500)}")
            self._process_command(result.text)
        except SpeechInputError as exc:
            self.log(f"[STT] status=FAIL reason={inline_value(exc, limit=500)}")
            self.log("[DONE] status=REJECTED stage=stt")
        except Exception as exc:
            self.log(
                f"[STT] status=ERROR error={type(exc).__name__} "
                f"reason={inline_value(exc, limit=500)}"
            )
            self.log("[DONE] status=ERROR stage=stt")

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
            status = "RESETTING" if self.reset_requested else "BUSY" if self.busy else "IDLE"
            self.log(f"[CHAT] status={status}")
            return True
        if local == "/help":
            self.log("[CHAT] event=HELP commands=/status,/stop,/reset,/voice,/voice-file,/help,/quit")
            return True
        if local == "/reset":
            self.request_reset()
            return True
        if local == "/voice":
            self.submit_voice()
            return True
        if local.startswith("/voice-file "):
            self.submit_voice(stripped[len("/voice-file "):].strip())
            return True
        self.submit(stripped)
        return True

    def run(self) -> None:
        """Run the interactive prompt; launch this method outside the sim thread."""
        self.log("[CHAT] event=READY input=english hint=/help")
        while True:
            try:
                line = self.input_fn("robot> ")
            except EOFError:
                self.cancel()
                break
            except KeyboardInterrupt:
                self._quit_requested.set()
                self.cancel()
                break
            if not self.handle_line(line):
                break
        self.log("[CHAT] event=CLOSED")

    def _process_command(self, command: str) -> None:
        stage = "planning"
        command_logged = False
        try:
            local_result = local_rejection(command)
            if local_result is not None:
                reason_code, local_reason = local_result
                plan = validate_plan(
                    {"accepted": False, "message": local_reason, "actions": []}
                )
                self.log(
                    "[LLM] provider=local model=command-policy latency_s=0.000 "
                    "input_tokens=0 output_tokens=0 accepted=false actions=0"
                )
                self.log(command_log(plan, rejection_reason=reason_code))
                command_logged = True
                result = self.executor.execute(plan)
                with self._lock:
                    self._last_execution_result = result
                return
            with self._lock:
                previous_plan = self._previous_successful_plan
            planning = self.planner.plan(command, previous_plan)
            plan = planning.plan
            self.log(
                f"[LLM] provider={inline_value(planning.provider, limit=40)} "
                f"model={inline_value(planning.model, limit=100)} "
                f"latency_s={planning.latency_s:.3f} "
                f"input_tokens={optional_count(planning.input_tokens)} "
                f"output_tokens={optional_count(planning.output_tokens)} accepted="
                f"{str(plan.accepted).lower()} actions={len(plan.actions)}"
            )
            if self._cancel_requested.is_set():
                cancelled = validate_plan(
                    {"accepted": False, "message": "Planning was cancelled.", "actions": []}
                )
                self.log(command_log(cancelled, rejection_reason="cancelled"))
                command_logged = True
                self.log("[DONE] status=CANCELLED stage=planning")
                return
            consistency_reason = plan_consistency_reason(command, plan)
            if consistency_reason is not None:
                self.log(
                    "[GUARD] status=REJECTED "
                    f"reason={inline_value(consistency_reason, limit=500)}"
                )
                plan = validate_plan(
                    {
                        "accepted": False,
                        "message": (
                            "The generated action contradicted the requested "
                            "direction, so it was not executed."
                        ),
                        "actions": [],
                    }
                )
                rejection_reason = "direction_mismatch"
            else:
                rejection_reason = "unsupported_request"
            self.log(command_log(plan, rejection_reason=rejection_reason))
            command_logged = True
            stage = "execution"
            result = self.executor.execute(plan)
            with self._lock:
                self._last_execution_result = result
            if result.status == "SUCCESS" and plan.accepted:
                with self._lock:
                    self._previous_successful_plan = plan
        except Exception as exc:
            if not command_logged and stage == "planning":
                failed = validate_plan(
                    {"accepted": False, "message": "Command planning failed.", "actions": []}
                )
                self.log(command_log(failed, rejection_reason="planner_error"))
            self.log(
                f"[DONE] status=ERROR stage={stage} "
                f"error={type(exc).__name__} reason={inline_value(exc, limit=500)}"
            )


def build_openai_chat_loop(
    executor: PlanExecutor,
    *,
    model: str | None = None,
    logger: Callable[[str], None] = print,
) -> TerminalChatLoop:
    """Convenience constructor used by the future simulator entry point."""
    return TerminalChatLoop(OpenAIPlanner(model=model), executor, logger=logger)


def build_ollama_chat_loop(
    executor: PlanExecutor,
    *,
    model: str | None = None,
    host: str | None = None,
    logger: Callable[[str], None] = print,
) -> TerminalChatLoop:
    """Build a chat loop backed by a local Ollama model."""
    return TerminalChatLoop(
        OllamaPlanner(model=model, host=host), executor, logger=logger
    )


def build_qwen_cloud_chat_loop(
    executor: PlanExecutor, *, model: str | None = None,
    logger: Callable[[str], None] = print,
) -> TerminalChatLoop:
    return TerminalChatLoop(CompatibleChatPlanner(model=model or "qwen-plus"),
                            executor, logger=logger)


def build_deepseek_chat_loop(
    executor: PlanExecutor, *, model: str | None = None,
    logger: Callable[[str], None] = print,
) -> TerminalChatLoop:
    return TerminalChatLoop(CompatibleChatPlanner(
        model=model or "deepseek-chat", host="https://api.deepseek.com",
        provider="deepseek", credential_env="DEEPSEEK_API_KEY",
    ), executor, logger=logger)
