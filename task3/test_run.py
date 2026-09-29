"""Tests for the complete simulator owner loop without starting MuJoCo."""

from types import SimpleNamespace

import pytest

from task3.run import build_parser, main, run_simulation_loop


class FakePlatform:
    def __init__(self):
        self.data = SimpleNamespace(time=0.0)
        self.step_calls = 0

    def step(self):
        self.step_calls += 1
        self.data.time += 0.1
        return self.step_calls % 2 == 1


class FakeTask4:
    def __init__(self):
        self.fresh_values = []

    def capture_after_step(self, fresh):
        self.fresh_values.append(fresh)


class FakeViewer:
    def __init__(self):
        self.sync_calls = 0

    def is_running(self):
        return True

    def sync(self):
        self.sync_calls += 1


def test_owner_loop_steps_platform_and_publishes_camera_frames():
    platform = FakePlatform()
    task4 = FakeTask4()
    viewer = FakeViewer()

    steps = run_simulation_loop(
        platform,
        task4,
        viewer,
        duration_s=0.3,
        browser_only=False,
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    assert steps == 3
    assert platform.step_calls == 3
    assert task4.fresh_values == [True, False, True]
    assert viewer.sync_calls == 3


def test_browser_loop_paces_without_calling_native_sync():
    platform = FakePlatform()
    task4 = FakeTask4()
    viewer = FakeViewer()
    sleeps = []

    run_simulation_loop(
        platform,
        task4,
        viewer,
        duration_s=0.1,
        browser_only=True,
        pace_wall_clock=True,
        monotonic=lambda: 1.0,
        sleep=sleeps.append,
    )

    assert viewer.sync_calls == 0
    assert sleeps == [0.005]


def test_quit_request_stops_before_next_physics_step():
    platform = FakePlatform()
    chat = SimpleNamespace(quit_requested=True)

    steps = run_simulation_loop(
        platform,
        FakeTask4(),
        FakeViewer(),
        duration_s=10,
        browser_only=False,
        chat=chat,
    )

    assert steps == 0
    assert platform.step_calls == 0


def test_duration_must_be_positive_and_finite():
    for value in (0, -1, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="duration_s"):
            run_simulation_loop(
                FakePlatform(),
                FakeTask4(),
                FakeViewer(),
                duration_s=value,
                browser_only=False,
            )


def test_cli_modes_are_mutually_exclusive():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--gui", "--headless"])


def test_chat_mode_fails_before_simulator_when_api_key_is_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="OPENAI_API_KEY"):
        main(["--duration", "1"])


def test_ollama_mode_does_not_require_openai_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    parser = build_parser()
    args = parser.parse_args(["--provider", "ollama", "--duration", "1"])

    assert args.provider == "ollama"
    assert args.model is None
