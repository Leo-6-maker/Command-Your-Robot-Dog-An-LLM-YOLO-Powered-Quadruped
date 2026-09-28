"""Tests for blocking Task 3 callbacks over the Task 2 queue contract."""

import threading

import pytest

from task3.task2_adapter import (
    MissingTurnResultError,
    MotionCancelledError,
    MotionTimeoutError,
    PlatformBusyError,
    Task2MotionAdapter,
    TurnFailedError,
)


class FakeSkills:
    def __init__(self):
        self.busy = False
        self.results = []
        self.queued = threading.Event()
        self.moves = []
        self.turns = []
        self.stop_calls = 0

    def move(self, vx, vy, wz, duration):
        self.moves.append((vx, vy, wz, duration))
        self.busy = True
        self.queued.set()

    def turn(self, angle_deg):
        self.turns.append(angle_deg)
        self.busy = True
        self.queued.set()

    def stop(self):
        self.stop_calls += 1
        self.busy = False


class FakePlatform:
    def __init__(self):
        self.skills = FakeSkills()


def _background_call(function):
    result = []
    errors = []

    def target():
        try:
            result.append(function())
        except Exception as exc:  # captured for assertion in the test thread
            errors.append(exc)

    thread = threading.Thread(target=target)
    thread.start()
    return thread, result, errors


def test_move_blocks_until_simulation_completes_queue():
    platform = FakePlatform()
    adapter = Task2MotionAdapter(platform, poll_interval_s=0.001)
    thread, result, errors = _background_call(
        lambda: adapter.move(0.5, 0.0, 0.0, 3.0, timeout_s=1.0)
    )

    assert platform.skills.queued.wait(0.2)
    assert thread.is_alive()
    assert platform.skills.moves == [(0.5, 0.0, 0.0, 3.0)]
    platform.skills.busy = False
    thread.join(0.2)

    assert not thread.is_alive()
    assert result == [None]
    assert errors == []


def test_adapter_refuses_to_mix_with_existing_queue():
    platform = FakePlatform()
    platform.skills.busy = True
    adapter = Task2MotionAdapter(platform)

    with pytest.raises(PlatformBusyError, match="already busy"):
        adapter.move(0.5, 0.0, 0.0, 1.0)
    assert platform.skills.moves == []


def test_move_timeout_cancels_task2_queue():
    platform = FakePlatform()
    adapter = Task2MotionAdapter(platform, poll_interval_s=0.001)

    with pytest.raises(MotionTimeoutError, match="wall-clock timeout"):
        adapter.move(0.5, 0.0, 0.0, 1.0, timeout_s=0.01)
    assert platform.skills.stop_calls == 1
    assert platform.skills.busy is False


def test_external_stop_marks_waiting_move_as_cancelled():
    platform = FakePlatform()
    adapter = Task2MotionAdapter(platform, poll_interval_s=0.001)
    thread, _, errors = _background_call(
        lambda: adapter.move(0.5, 0.0, 0.0, 2.0, timeout_s=1.0)
    )

    assert platform.skills.queued.wait(0.2)
    adapter.stop()
    thread.join(0.2)

    assert len(errors) == 1
    assert isinstance(errors[0], MotionCancelledError)
    assert platform.skills.stop_calls == 1


def test_successful_turn_returns_new_result_record():
    platform = FakePlatform()
    platform.skills.results.append({"status": "OLD"})
    adapter = Task2MotionAdapter(platform, poll_interval_s=0.001)
    thread, result, errors = _background_call(
        lambda: adapter.turn(90.0, timeout_s=1.0)
    )

    assert platform.skills.queued.wait(0.2)
    expected = {
        "target_deg": 90.0,
        "final_error_deg": 1.2,
        "duration": 4.5,
        "status": "SUCCESS",
    }
    platform.skills.results.append(expected)
    platform.skills.busy = False
    thread.join(0.2)

    assert errors == []
    assert result == [expected]


def test_failed_turn_is_not_reported_as_success():
    platform = FakePlatform()
    adapter = Task2MotionAdapter(platform, poll_interval_s=0.001)
    thread, _, errors = _background_call(
        lambda: adapter.turn(180.0, timeout_s=1.0)
    )

    assert platform.skills.queued.wait(0.2)
    platform.skills.results.append({"target_deg": 180.0, "status": "FAIL timeout"})
    platform.skills.busy = False
    thread.join(0.2)

    assert len(errors) == 1
    assert isinstance(errors[0], TurnFailedError)


def test_turn_without_result_is_an_integration_error():
    platform = FakePlatform()
    adapter = Task2MotionAdapter(platform, poll_interval_s=0.001)
    thread, _, errors = _background_call(
        lambda: adapter.turn(45.0, timeout_s=1.0)
    )

    assert platform.skills.queued.wait(0.2)
    platform.skills.busy = False
    thread.join(0.2)

    assert len(errors) == 1
    assert isinstance(errors[0], MissingTurnResultError)


@pytest.mark.parametrize(
    ("keyword", "value"),
    [("poll_interval_s", 0), ("default_timeout_s", -1)],
)
def test_invalid_adapter_timing_is_rejected(keyword, value):
    with pytest.raises(ValueError):
        Task2MotionAdapter(FakePlatform(), **{keyword: value})


def test_invalid_explicit_timeout_is_rejected_before_queueing():
    platform = FakePlatform()
    adapter = Task2MotionAdapter(platform)

    with pytest.raises(ValueError, match="timeout_s"):
        adapter.move(0.5, 0.0, 0.0, 1.0, timeout_s=float("nan"))
    assert platform.skills.moves == []
