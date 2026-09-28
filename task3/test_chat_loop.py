"""Tests for nonblocking terminal command handling."""

import threading

from task3.chat_loop import TerminalChatLoop
from task3.executor import ExecutionResult
from task3.planner import PlanningResult
from task3.validator import validate_plan


MOVE_PLAN = validate_plan(
    {
        "accepted": True,
        "message": "Moving.",
        "actions": [
            {"type": "move", "vx": 0.4, "vy": 0, "wz": 0, "duration_s": 2}
        ],
    }
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
    assert logs[0] == "[CMD] Move forward"
    assert any(line.startswith("[LLM]") for line in logs)


def test_successful_plan_becomes_context_for_next_command():
    planner = FakePlanner()
    loop = TerminalChatLoop(planner, FakeExecutor(), logger=lambda _: None)

    loop.submit("Move forward")
    assert loop.wait(1.0)
    loop.submit("Do that again")
    assert loop.wait(1.0)

    assert planner.calls[1] == ("Do that again", MOVE_PLAN)


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
