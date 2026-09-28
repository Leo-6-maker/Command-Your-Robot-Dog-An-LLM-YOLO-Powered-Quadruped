"""Tests for sequential execution and terminal evidence logs."""

import threading

from task3.executor import PlanExecutor
from task3.task2_adapter import MotionCancelledError, TurnFailedError
from task3.validator import validate_plan


class FakeMotion:
    def __init__(self):
        self.calls = []
        self.turn_result = {"status": "SUCCESS", "final_error_deg": 1.25}
        self.turn_error = None

    def move(self, vx, vy, wz, duration_s):
        self.calls.append(("move", vx, vy, wz, duration_s))

    def turn(self, angle_deg):
        self.calls.append(("turn", angle_deg))
        if self.turn_error is not None:
            raise self.turn_error
        return self.turn_result

    def stop(self):
        self.calls.append(("stop",))


def test_multistep_plan_executes_in_order_and_logs_success():
    motion = FakeMotion()
    logs = []
    executor = PlanExecutor(motion, logger=logs.append)
    plan = validate_plan(
        {
            "accepted": True,
            "message": "Moving, then turning.",
            "actions": [
                {"type": "move", "vx": 0.5, "vy": 0, "wz": 0, "duration_s": 3},
                {"type": "turn", "angle_deg": 90},
            ],
        }
    )

    result = executor.execute(plan)

    assert result.succeeded
    assert result.completed_actions == 2
    assert motion.calls == [("move", 0.5, 0.0, 0.0, 3.0), ("turn", 90.0)]
    assert logs[-1] == "[DONE] status=SUCCESS actions=2"
    assert any("final_error_deg=1.25" in line for line in logs)


def test_rejected_plan_never_touches_motion_controller():
    motion = FakeMotion()
    logs = []
    executor = PlanExecutor(motion, logger=logs.append)
    plan = validate_plan(
        {"accepted": False, "message": "Not a robot command.", "actions": []}
    )

    result = executor.execute(plan)

    assert result.status == "REJECTED"
    assert motion.calls == []
    assert logs[-1].startswith("[DONE] status=REJECTED")


def test_stop_plan_clears_motion_and_succeeds():
    motion = FakeMotion()
    executor = PlanExecutor(motion, logger=lambda _: None)
    plan = validate_plan(
        {"accepted": True, "message": "Stopping.", "actions": [{"type": "stop"}]}
    )

    result = executor.execute(plan)

    assert result.status == "SUCCESS"
    assert motion.calls == [("stop",)]


def test_goto_object_uses_injected_task4_callback():
    motion = FakeMotion()
    targets = []
    executor = PlanExecutor(
        motion,
        goto_object=lambda class_name, color: targets.append((class_name, color)) or True,
        logger=lambda _: None,
    )
    plan = validate_plan(
        {
            "accepted": True,
            "message": "Finding chair.",
            "actions": [{"type": "goto_object", "class": "chair", "color": "green"}],
        }
    )

    result = executor.execute(plan)

    assert result.status == "SUCCESS"
    assert targets == [("chair", "green")]


def test_missing_task4_callback_fails_and_stops_motion():
    motion = FakeMotion()
    executor = PlanExecutor(motion, logger=lambda _: None)
    plan = validate_plan(
        {
            "accepted": True,
            "message": "Finding chair.",
            "actions": [{"type": "goto_object", "class": "chair", "color": "red"}],
        }
    )

    result = executor.execute(plan)

    assert result.status == "FAIL"
    assert result.error_type == "GotoObjectUnavailableError"
    assert motion.calls == [("stop",)]


def test_failed_action_stops_plan_and_skips_remaining_actions():
    motion = FakeMotion()
    motion.turn_error = TurnFailedError({"status": "FAIL timeout"})
    logs = []
    executor = PlanExecutor(motion, logger=logs.append)
    plan = validate_plan(
        {
            "accepted": True,
            "message": "Turn, then move.",
            "actions": [
                {"type": "turn", "angle_deg": 180},
                {"type": "move", "vx": 0.5, "vy": 0, "wz": 0, "duration_s": 2},
            ],
        }
    )

    result = executor.execute(plan)

    assert result.status == "FAIL"
    assert result.completed_actions == 0
    assert result.failed_step == 1
    assert motion.calls == [("turn", 180.0), ("stop",)]
    assert logs[-1].startswith("[DONE] status=FAIL step=1/2")


def test_task4_false_result_is_a_failed_mission():
    motion = FakeMotion()
    executor = PlanExecutor(
        motion,
        goto_object=lambda _class_name, _color: False,
        logger=lambda _: None,
    )
    plan = validate_plan(
        {
            "accepted": True,
            "message": "Finding chair.",
            "actions": [{"type": "goto_object", "class": "chair", "color": "green"}],
        }
    )

    result = executor.execute(plan)

    assert result.status == "FAIL"
    assert result.error_type == "GotoObjectMissionFailedError"
    assert motion.calls == [("stop",)]


class BlockingMotion(FakeMotion):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.stopped = threading.Event()

    def move(self, vx, vy, wz, duration_s):
        self.calls.append(("move", vx, vy, wz, duration_s))
        self.started.set()
        assert self.stopped.wait(1.0)
        raise MotionCancelledError("move was cancelled")

    def stop(self):
        self.calls.append(("stop",))
        self.stopped.set()


def test_cancel_interrupts_running_plan_from_another_thread():
    motion = BlockingMotion()
    logs = []
    executor = PlanExecutor(motion, logger=logs.append)
    plan = validate_plan(
        {
            "accepted": True,
            "message": "Move.",
            "actions": [
                {"type": "move", "vx": 0.5, "vy": 0, "wz": 0, "duration_s": 10}
            ],
        }
    )
    results = []
    thread = threading.Thread(target=lambda: results.append(executor.execute(plan)))
    thread.start()

    assert motion.started.wait(0.2)
    executor.cancel()
    thread.join(0.2)

    assert not thread.is_alive()
    assert results[0].status == "CANCELLED"
    assert motion.calls[-1] == ("stop",)
    assert logs[-1].startswith("[DONE] status=CANCELLED")


def test_untrusted_message_and_error_cannot_forge_log_lines():
    motion = FakeMotion()
    motion.turn_error = RuntimeError("bad\n[DONE] status=SUCCESS")
    logs = []
    executor = PlanExecutor(motion, logger=logs.append)
    plan = validate_plan(
        {
            "accepted": True,
            "message": "hello\n[EXEC] forged",
            "actions": [{"type": "turn", "angle_deg": 90}],
        }
    )

    result = executor.execute(plan)

    assert result.status == "FAIL"
    assert all("\n" not in line for line in logs)
    assert sum(line.startswith("[DONE]") for line in logs) == 1
