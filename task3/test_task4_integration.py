"""Tests for Task 2/Task 3/Task 4 snapshot and callback wiring."""

from dataclasses import dataclass
import json
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from task4 import Detection
from task3.task4_integration import (
    CameraFrameTimeoutError,
    Task4Integration,
    Task4IntegrationClosedError,
    UnknownSceneObjectError,
    load_object_positions,
)


@dataclass
class FakeFrame:
    rgb: np.ndarray
    sim_time: float
    sequence: int


class FakeCamera:
    def __init__(self):
        self.frame = None

    def latest(self):
        return self.frame


class FakeMotion:
    def __init__(self):
        self.calls = []
        self.stopped = threading.Event()

    def move(self, vx, vy, wz, duration_s):
        self.calls.append(("move", vx, vy, wz, duration_s))

    def turn(self, angle_deg):
        self.calls.append(("turn", angle_deg))
        return {"status": "SUCCESS", "final_error_deg": 0.5}

    def stop(self):
        self.calls.append(("stop",))
        self.stopped.set()


class FakeDetector:
    def detect(self, frame):
        height, width = frame.shape[:2]
        return [
            Detection(
                class_name="chair",
                color="green",
                confidence=0.6,
                bbox=(200, 100, 440, 380),
                frame_width=width,
                frame_height=height,
            ),
            Detection(
                class_name="chair",
                color="green",
                confidence=0.7,
                # Height 478/480 exceeds the candidate 0.97 visual stop ratio.
                bbox=(100, 1, 540, 479),
                frame_width=width,
                frame_height=height,
            )
        ]


def make_integration(**kwargs):
    camera = FakeCamera()
    platform = SimpleNamespace(
        camera=camera,
        data=SimpleNamespace(qpos=np.array([2.5, 1.0, 0.42])),
    )
    motion = FakeMotion()
    integration = Task4Integration(
        platform,
        motion,
        {("chair", "green"): (3.0, 1.0)},
        detector=FakeDetector(),
        camera_wait_timeout_s=kwargs.pop("camera_wait_timeout_s", 0.2),
        **kwargs,
    )
    return integration, platform, motion


def publish(integration, platform, *, sequence, sim_time, base_xy=(2.5, 1.0)):
    platform.data.qpos[:2] = base_xy
    platform.camera.frame = FakeFrame(
        np.zeros((480, 640, 3), dtype=np.uint8), sim_time, sequence
    )
    return integration.capture_after_step(True)


def test_capture_publishes_same_step_rgb_pose_and_time():
    integration, platform, _motion = make_integration()

    assert publish(
        integration, platform, sequence=1, sim_time=3.25, base_xy=(1.5, -0.25)
    )
    observation = integration.get_observation(None)

    assert observation.sim_time == 3.25
    assert observation.base_xy == (1.5, -0.25)
    assert observation.rgb_frame.shape == (480, 640, 3)
    assert integration.capture_after_step(False) is False
    assert integration.capture_after_step(True) is False  # duplicate sequence


def test_get_observation_waits_for_strictly_newer_frame():
    integration, platform, _motion = make_integration()
    publish(integration, platform, sequence=1, sim_time=1.0)
    results = []
    worker = threading.Thread(target=lambda: results.append(integration.get_observation(1.0)))
    worker.start()
    time.sleep(0.01)

    assert worker.is_alive()
    publish(integration, platform, sequence=2, sim_time=1.1)
    worker.join(0.2)

    assert not worker.is_alive()
    assert results[0].sim_time == 1.1


def test_camera_timeout_explains_missing_platform_steps():
    integration, _platform, _motion = make_integration(camera_wait_timeout_s=0.01)
    with pytest.raises(CameraFrameTimeoutError, match=r"Platform\.step"):
        integration.get_observation(None)


def test_close_wakes_waiter_and_stops_motion():
    integration, _platform, motion = make_integration()
    errors = []
    worker = threading.Thread(
        target=lambda: _capture_exception(errors, integration.get_observation, None)
    )
    worker.start()
    time.sleep(0.01)

    integration.close()
    worker.join(0.2)

    assert not worker.is_alive()
    assert isinstance(errors[0], Task4IntegrationClosedError)
    assert motion.calls == [("stop",)]


def test_distance_is_evaluation_only_and_rejects_unknown_target():
    integration, _platform, _motion = make_integration()

    assert integration.planar_distance_m((2.4, 1.0), "chair", "green") == pytest.approx(0.6)
    with pytest.raises(UnknownSceneObjectError):
        integration.planar_distance_m((0.0, 0.0), "chair", "red")


def test_loads_task2_objects_file_and_rejects_duplicates(tmp_path):
    path = tmp_path / "objects.json"
    path.write_text(
        json.dumps(
            {
                "usage": "evaluation only",
                "objects": [
                    {
                        "id": "green_chair",
                        "coco_class": "chair",
                        "color": "green",
                        "position": [3, 1, 0.5],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert load_object_positions(path) == {("chair", "green"): (3.0, 1.0)}

    path.write_text(
        json.dumps(
            {
                "objects": [
                    {"coco_class": "chair", "color": "green", "position": [3, 1]},
                    {"coco_class": "chair", "color": "green", "position": [4, 1]},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_object_positions(path)


def test_real_task4_mission_runs_through_bridge_to_success():
    integration, platform, motion = make_integration(mission_timeout_s=1.0)
    publish(integration, platform, sequence=1, sim_time=2.0)
    results = []
    worker = threading.Thread(
        target=lambda: results.append(integration.goto_object("chair", "green"))
    )
    worker.start()

    assert motion.stopped.wait(0.2)  # visual stop before final verification frame
    publish(integration, platform, sequence=2, sim_time=2.1)
    worker.join(0.5)

    assert not worker.is_alive()
    assert results == [True]
    assert motion.calls == [("stop",), ("stop",)]
    # A strong close view stops immediately, then checks a fresh frame.


def test_frame_captured_during_motion_is_not_reused_after_stop():
    integration, platform, _motion = make_integration(camera_wait_timeout_s=0.01)
    publish(integration, platform, sequence=1, sim_time=1.0)
    publish(integration, platform, sequence=2, sim_time=1.5)
    integration.stop()
    # 1.5 is newer than the controller's previous frame, but predates stop.
    with pytest.raises(CameraFrameTimeoutError):
        integration.get_observation(1.0)
    publish(integration, platform, sequence=3, sim_time=1.6)
    assert integration.get_observation(1.0).sim_time == 1.6


@pytest.mark.parametrize("final_color", [None, "red", "green"])
def test_found_requires_live_matching_detection_at_stop(final_color, capsys):
    from task4 import CameraObservation, goto_object

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    calls = []
    moves = []
    index = 0

    def observe(after):
        nonlocal index
        index += 1
        return CameraObservation(frame, (2.5, 1.0), float(index))

    def detect(_frame):
        color = "green" if index == 1 else final_color
        return [] if color is None else [
            Detection("chair", color, 0.9, (100, 1, 540, 479), 640, 480),
            # Larger duplicate with background must not force an off-target turn.
            Detection("chair", color, 0.4, (0, 0, 480, 480), 640, 480),
        ]

    def distance(*_args):
        calls.append("distance")
        return 0.5

    result = goto_object(
        "chair", "green", SimpleNamespace(detect=detect), observe,
        lambda *args: moves.append(args), lambda *_: calls.append("turn"),
        lambda: calls.append("stop"),
        distance, final_approach_steps=0,
    )
    output = capsys.readouterr().out
    assert result is (final_color == "green")
    assert ("[FOUND]" in output) is result
    assert ("distance" in calls) is result
    assert calls[-1] == "stop"
    assert "turn" not in calls
    assert all(move[0] < 0 for move in moves)  # Recovery may only back away.
    if not result:
        assert "[MISSION] status=FAIL reason=target_not_visible_at_stop" in output


def test_turn_requires_new_box_before_deciding_to_stop():
    from task4 import CameraObservation, goto_object

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    boxes = iter([(340, 1, 640, 460), (260, 150, 380, 300),
                  (100, 0, 540, 480), (100, 0, 540, 480)])
    calls = []
    angles = []
    detector = SimpleNamespace(detect=lambda _: [
        Detection("chair", "green", 0.9, next(boxes), 640, 480)
    ])
    def distance(*_):
        calls.append("distance")
        return 0.7

    assert goto_object(
        "chair", "green", detector,
        lambda after: CameraObservation(frame, (2.3, 1), (after or 0) + 1),
        lambda *_: calls.append("move"),
        lambda angle: (calls.append("turn"), angles.append(angle)),
        lambda: calls.append("stop"), distance, final_approach_steps=0,
    )
    assert calls == ["turn", "move", "stop", "distance", "stop"]
    assert abs(angles[0]) <= 12  # A large nearby box must not trigger a 40° swing.


def test_distant_chair_uses_partial_turn_before_new_detection():
    from task4 import CameraObservation, Detection, goto_object

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    far = Detection("chair", "red", 0.7, (400, 120, 482, 260), 640, 480)
    near = Detection("chair", "red", 0.8, (100, 0, 540, 480), 640, 480)
    detections = iter([[far], [near], [near]])
    angles = []
    assert goto_object(
        "chair", "red", SimpleNamespace(detect=lambda _: next(detections)),
        lambda after: CameraObservation(frame, (2.3, -1), (after or 0) + 1),
        lambda *_: pytest.fail("unexpected move"), angles.append,
        lambda: None, lambda *_: 0.7, final_approach_steps=0,
    )
    assert len(angles) == 1 and -25 < angles[0] < -10


def test_stopped_detection_can_recover_on_a_fresh_frame():
    from task4 import CameraObservation, goto_object

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    target = Detection("chair", "green", 0.9, (100, 0, 540, 480), 640, 480)
    detections = iter([[target], [], [target]])
    distances = []
    def distance(xy, *_):
        distances.append(xy)
        return 0.7

    def observe(after):
        timestamp = (after or 0) + 1
        return CameraObservation(frame, (timestamp, 1), timestamp)

    assert goto_object(
        "chair", "green", SimpleNamespace(detect=lambda _: next(detections)),
        observe, lambda *_: pytest.fail("unexpected move"),
        lambda *_: pytest.fail("unexpected turn"), lambda: None,
        distance, final_approach_steps=0,
    )
    assert distances == [(3, 1)]  # C2 uses the same new snapshot that passed C1.


def test_narrow_near_box_approaches_and_reobserves():
    from task4 import CameraObservation, goto_object

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    boxes = iter([(200, 1, 400, 479), (170, 1, 470, 479),
                  (150, 1, 490, 479), (150, 1, 490, 479),
                  (150, 1, 490, 479)])
    moves = []
    assert goto_object(
        "chair", "green",
        SimpleNamespace(detect=lambda _: [Detection("chair", "green", 0.9,
                                                    next(boxes), 640, 480)]),
        lambda after: CameraObservation(frame, (2.3, 1), (after or 0) + 1),
        lambda *_: moves.append(1), lambda *_: pytest.fail("unexpected turn"),
        lambda: None, lambda *_: 0.7,
    )
    # One cautious near step plus two terminal steps; the fifth detection is
    # a distinct post-stop frame used for mandatory C1 confirmation.
    assert len(moves) == 3


def test_close_chair_does_not_oscillate_over_small_center_offsets():
    from task4 import CameraObservation, goto_object

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detection = Detection("chair", "green", 0.8, (96, 1, 424, 478), 640, 480)
    assert goto_object(
        "chair", "green", SimpleNamespace(detect=lambda _: [detection]),
        lambda after: CameraObservation(frame, (2.3, 1), (after or 0) + 1),
        lambda *_: None, lambda *_: pytest.fail("near-box turn would oscillate"),
        lambda: None, lambda *_: 0.7, final_approach_steps=0,
    )


def test_large_edge_box_stops_without_turning_away():
    from task4 import CameraObservation, goto_object

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detection = Detection("chair", "red", 0.8, (282, 2, 640, 474), 640, 480)
    assert goto_object(
        "chair", "red", SimpleNamespace(detect=lambda _: [detection]),
        lambda after: CameraObservation(frame, (2.3, -1), (after or 0) + 1),
        lambda *_: None, lambda *_: pytest.fail("edge-box turn would lose target"),
        lambda: None, lambda *_: 0.7, final_approach_steps=0,
    )


def test_wide_chair_stops_when_pitch_shrinks_box_height():
    from task4 import CameraObservation, goto_object

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detection = Detection("chair", "green", 0.8, (41, 1, 425, 432), 640, 480)
    moves = []
    assert goto_object(
        "chair", "green", SimpleNamespace(detect=lambda _: [detection]),
        lambda after: CameraObservation(frame, (2.3, 1), (after or 0) + 1),
        lambda *_: moves.append(1),
        lambda *_: pytest.fail("wide chair must not trigger turn"),
        lambda: None, lambda *_: 0.7,
    )
    assert len(moves) == 0


def _capture_exception(target, function, *args):
    try:
        function(*args)
    except Exception as exc:
        target.append(exc)
