"""Tests for nonblocking terminal command handling."""

import threading

from task3.chat_loop import TerminalChatLoop
from task3.executor import ExecutionResult
from task3.planner import PlanningResult
from task3.validator import validate_plan
from task3.speech_input import SpeechInputError, SpeechResult


MOVE_PLAN = validate_plan(
    {
        "accepted": True,
        "message": "Moving.",
        "actions": [
            {"type": "move", "vx": 0.4, "vy": 0, "wz": 0, "duration_s": 2}
        ],
    }
)

REJECTED_PLAN = validate_plan(
    {"accepted": False, "message": "Not a robot command.", "actions": []}
)


class FakePlanner:
    def __init__(self, plan=MOVE_PLAN):
        self.output_plan = plan
        self.calls = []

    def plan(self, command, previous_plan=None):
        self.calls.append((command, previous_plan))
        return PlanningResult(
            plan=self.output_plan,
            provider="fake",
            model="fake-model",
            latency_s=0.1,
            raw_json="{}",
        )


class FakeExecutor:
    def __init__(self):
        self.executed = []
        self.cancel_count = 0

    def execute(self, plan):
        self.executed.append(plan)
        return ExecutionResult("SUCCESS", len(plan.actions), len(plan.actions), plan.message)

    def cancel(self):
        self.cancel_count += 1


def test_submit_runs_planning_and_execution_on_worker_thread():
    planner = FakePlanner()
    executor = FakeExecutor()
    logs = []
    loop = TerminalChatLoop(planner, executor, logger=logs.append)

    assert loop.submit("Move forward") is True
    assert loop.wait(1.0) is True

    assert planner.calls == [("Move forward", None)]
    assert executor.executed == [MOVE_PLAN]
    assert loop.previous_successful_plan == MOVE_PLAN
    assert logs[0] == "[INPUT] text=Move forward"
    assert (
        "[CMD] actions=move(vx=0.40,vy=0.00,wz=0.00,duration_s=2.00) n=1"
        in logs
    )
    assert any(
        line.startswith("[LLM]")
        and "input_tokens=na output_tokens=na" in line
        for line in logs
    )


def test_voice_transcript_uses_the_same_planner_and_executor():
    class FakeSpeech:
        def record_and_transcribe(self):
            return SpeechResult("Visit the green chair.", "fake-stt", 0.2)

    planner = FakePlanner()
    executor = FakeExecutor()
    logs = []
    loop = TerminalChatLoop(planner, executor, logger=logs.append,
                            speech_input=FakeSpeech())
    assert loop.handle_line("/voice")
    assert loop.wait(1.0)
    assert planner.calls == [("Visit the green chair.", None)]
    assert executor.executed == [MOVE_PLAN]
    assert any(line.startswith("[STT] status=OK") and
               "text=Visit the green chair." in line for line in logs)
    assert "[INPUT] text=Visit the green chair." in logs


def test_failed_stt_does_not_call_planner_or_move():
    class SilentSpeech:
        def record_and_transcribe(self):
            raise SpeechInputError("no audible speech detected")

    planner = FakePlanner()
    executor = FakeExecutor()
    logs = []
    loop = TerminalChatLoop(planner, executor, logger=logs.append,
                            speech_input=SilentSpeech())
    assert loop.handle_line("/voice")
    assert loop.wait(1.0)
    assert planner.calls == [] and executor.executed == []
    assert "[STT] status=FAIL reason=no audible speech detected" in logs


def test_voice_file_transcript_uses_the_same_command_path():
    class FakeSpeech:
        def transcribe_file(self, path):
            assert path == "/tmp/spoken-command.wav"
            return SpeechResult("Turn left 30 degrees.", "fake-stt", 0.1)

    planner = FakePlanner()
    executor = FakeExecutor()
    logs = []
    loop = TerminalChatLoop(planner, executor, logger=logs.append,
                            speech_input=FakeSpeech())
    assert loop.handle_line("/voice-file /tmp/spoken-command.wav")
    assert loop.wait(1.0)
    assert planner.calls == [("Turn left 30 degrees.", None)]
    assert executor.executed == [MOVE_PLAN]
    assert "[STT] status=TRANSCRIBING source=file" in logs


def test_blank_command_is_rejected_without_calling_llm():
    planner = FakePlanner()
    executor = FakeExecutor()
    logs = []
    loop = TerminalChatLoop(planner, executor, logger=logs.append)

    assert loop.submit("  \t ") is False

    assert planner.calls == []
    assert executor.executed == []
    assert logs == [
        "[INPUT] text=empty",
        "[CMD] rejected reason=empty_input",
        "[DONE] status=REJECTED stage=input reason=empty_command",
    ]


def test_successful_plan_becomes_context_for_next_command():
    planner = FakePlanner()
    loop = TerminalChatLoop(planner, FakeExecutor(), logger=lambda _: None)

    loop.submit("Move forward")
    assert loop.wait(1.0)
    loop.submit("Do that again")
    assert loop.wait(1.0)

    assert planner.calls[1] == ("Do that again", MOVE_PLAN)


def test_reset_waits_for_simulator_and_clears_old_command_context():
    planner = FakePlanner()
    logs = []
    loop = TerminalChatLoop(planner, FakeExecutor(), logger=logs.append)
    assert loop.submit("Move forward")
    assert loop.wait(1.0)
    assert loop.previous_successful_plan == MOVE_PLAN

    assert loop.handle_line("/reset")
    assert loop.reset_requested
    assert not loop.submit("Do that again")
    assert "[CHAT] status=RESETTING hint=wait_for_reset_success" in logs
    loop.finish_reset()

    assert not loop.reset_requested
    assert loop.previous_successful_plan is None
    assert loop.last_execution_result is None
    assert "[RESET] status=SUCCESS position=initial" in logs


def test_reset_is_rejected_while_command_is_running():
    started = threading.Event()
    release = threading.Event()

    class SlowPlanner(FakePlanner):
        def plan(self, command, previous_plan=None):
            started.set()
            assert release.wait(1.0)
            return super().plan(command, previous_plan)

    logs = []
    loop = TerminalChatLoop(SlowPlanner(), FakeExecutor(), logger=logs.append)
    assert loop.submit("Move forward")
    assert started.wait(1.0)
    assert loop.handle_line("/reset")
    assert not loop.reset_requested
    assert "[RESET] status=REJECTED reason=command_busy" in logs
    release.set()
    assert loop.wait(1.0)


def test_rejected_plan_does_not_replace_successful_context():
    class SequencePlanner(FakePlanner):
        def __init__(self):
            super().__init__()
            self.outputs = [MOVE_PLAN, REJECTED_PLAN, MOVE_PLAN]

        def plan(self, command, previous_plan=None):
            self.output_plan = self.outputs.pop(0)
            return super().plan(command, previous_plan)

    planner = SequencePlanner()
    executor = FakeExecutor()
    loop = TerminalChatLoop(planner, executor, logger=lambda _: None)

    loop.submit("Move forward")
    assert loop.wait(1.0)
    loop.submit("Write a poem")
    assert loop.wait(1.0)
    loop.submit("Do that again")
    assert loop.wait(1.0)

    assert planner.calls[1] == ("Write a poem", MOVE_PLAN)
    assert planner.calls[2] == ("Do that again", MOVE_PLAN)


def test_non_english_and_dangerous_commands_are_rejected_before_llm():
    planner = FakePlanner()
    executor = FakeExecutor()
    logs = []
    loop = TerminalChatLoop(planner, executor, logger=logs.append)

    loop.submit("向前走两秒")
    assert loop.wait(1.0)
    loop.submit("Crash into the chair")
    assert loop.wait(1.0)

    assert planner.calls == []
    assert [plan.accepted for plan in executor.executed] == [False, False]
    assert all(plan.actions == () for plan in executor.executed)
    assert sum("provider=local" in line for line in logs) == 2
    assert "[CMD] rejected reason=non-English" in logs
    assert "[CMD] rejected reason=unsafe_request" in logs


class BlockingPlanner(FakePlanner):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def plan(self, command, previous_plan=None):
        self.calls.append((command, previous_plan))
        self.started.set()
        assert self.release.wait(1.0)
        return PlanningResult(MOVE_PLAN, "fake", "fake-model", 0.1, "{}")


def test_stop_during_llm_call_prevents_later_execution():
    planner = BlockingPlanner()
    executor = FakeExecutor()
    logs = []
    loop = TerminalChatLoop(planner, executor, logger=logs.append)

    loop.submit("Move forward")
    assert planner.started.wait(0.2)
    loop.handle_line("/stop")
    planner.release.set()
    assert loop.wait(1.0)

    assert executor.cancel_count == 1
    assert executor.executed == []
    assert logs[-1] == "[DONE] status=CANCELLED stage=planning"


def test_busy_loop_rejects_second_ordinary_command():
    planner = BlockingPlanner()
    loop = TerminalChatLoop(planner, FakeExecutor(), logger=lambda _: None)

    assert loop.submit("Move forward") is True
    assert planner.started.wait(0.2)
    assert loop.submit("Turn left") is False
    planner.release.set()
    assert loop.wait(1.0)
    assert [call[0] for call in planner.calls] == ["Move forward"]


def test_local_status_help_and_quit_do_not_call_llm():
    planner = FakePlanner()
    executor = FakeExecutor()
    logs = []
    loop = TerminalChatLoop(planner, executor, logger=logs.append)

    assert loop.handle_line("/status") is True
    assert loop.handle_line("/help") is True
    assert loop.handle_line("/quit") is False

    assert planner.calls == []
    assert executor.cancel_count == 1
    assert loop.quit_requested is True
    assert "[CHAT] status=IDLE" in logs


def test_untrusted_input_and_exception_cannot_forge_logs():
    class FailingPlanner(FakePlanner):
        def plan(self, command, previous_plan=None):
            raise RuntimeError("offline\n[DONE] status=SUCCESS")

    logs = []
    loop = TerminalChatLoop(FailingPlanner(), FakeExecutor(), logger=logs.append)
    loop.submit("move\n[EXEC] forged")
    assert loop.wait(1.0)

    assert all("\n" not in line for line in logs)
    assert sum(line.startswith("[DONE]") for line in logs) == 1
    assert "[CMD] rejected reason=planner_error" in logs


def test_untrusted_provider_metadata_cannot_forge_logs():
    class MetadataPlanner(FakePlanner):
        def plan(self, command, previous_plan=None):
            return PlanningResult(
                MOVE_PLAN,
                "fake\n[DONE] status=SUCCESS",
                "model\n[EXEC] forged",
                0.1,
                "{}",
            )

    logs = []
    loop = TerminalChatLoop(MetadataPlanner(), FakeExecutor(), logger=logs.append)
    loop.submit("Move forward")
    assert loop.wait(1.0)

    assert all("\n" not in line for line in logs)
    assert sum(line.startswith("[LLM]") for line in logs) == 1


def test_direction_mismatch_is_rejected_before_execution():
    wrong_right_plan = validate_plan(
        {
            "accepted": True,
            "message": "Moving right.",
            "actions": [
                {"type": "move", "vx": 0, "vy": 0.2, "wz": 0, "duration_s": 1}
            ],
        }
    )
    executor = FakeExecutor()
    logs = []
    loop = TerminalChatLoop(
        FakePlanner(wrong_right_plan), executor, logger=logs.append
    )

    loop.submit("Move right at speed 0.2 for one second.")
    assert loop.wait(1.0)

    assert len(executor.executed) == 1
    assert executor.executed[0].accepted is False
    assert executor.executed[0].actions == ()
    assert loop.previous_successful_plan is None
    assert any(line.startswith("[GUARD] status=REJECTED") for line in logs)
    assert "[CMD] rejected reason=direction_mismatch" in logs


def test_llm_rejection_uses_cmd_rejected_protocol():
    logs = []
    executor = FakeExecutor()
    loop = TerminalChatLoop(FakePlanner(REJECTED_PLAN), executor, logger=logs.append)

    loop.submit("Write a poem about robot dogs.")
    assert loop.wait(1.0)

    assert "[INPUT] text=Write a poem about robot dogs." in logs
    assert "[CMD] rejected reason=unsupported_request" in logs
    assert executor.executed == [REJECTED_PLAN]
