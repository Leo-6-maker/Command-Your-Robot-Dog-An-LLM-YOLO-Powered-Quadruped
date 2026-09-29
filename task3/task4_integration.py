"""Thread-safe wiring between Task 2 snapshots, Task 3, and ``task4.py``."""

from collections.abc import Callable, Mapping
import json
import math
from pathlib import Path
import threading
import time
from typing import Any, Protocol

import numpy as np

from task4 import CameraObservation, YoloColorDetector, goto_object

from .task2_adapter import Task2MotionAdapter


ObjectKey = tuple[str, str]
ObjectPositions = Mapping[ObjectKey, tuple[float, float]]


class CameraFrameLike(Protocol):
    rgb: object
    sim_time: float
    sequence: int


class CameraLike(Protocol):
    def latest(self) -> CameraFrameLike | None: ...


class PlatformDataLike(Protocol):
    qpos: object


class Task4PlatformLike(Protocol):
    camera: CameraLike | None
    data: PlatformDataLike


class CameraFrameTimeoutError(TimeoutError):
    """Raised when the simulator stops producing fresh onboard frames."""


class Task4IntegrationClosedError(RuntimeError):
    """Raised when a waiting mission outlives the simulator integration."""


class UnknownSceneObjectError(LookupError):
    """Raised when final-distance evaluation has no matching scene object."""


class Task4Integration:
    """Provide the callbacks required by ``task4.goto_object``.

    ``capture_after_step`` must run on the MuJoCo owner thread immediately
    after ``Platform.step()`` reports a fresh camera frame. ``goto_object`` is
    the blocking callback injected into ``PlanExecutor`` and runs on Task 3's
    command worker.
    """

    def __init__(
        self,
        platform: Task4PlatformLike,
        motion: Task2MotionAdapter,
        object_positions: ObjectPositions,
        *,
        detector: YoloColorDetector | None = None,
        weights: str = "yolo11n.pt",
        camera_wait_timeout_s: float = 5.0,
        mission_timeout_s: float = 60.0,
        mission: Callable[..., bool] = goto_object,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        if not math.isfinite(camera_wait_timeout_s) or camera_wait_timeout_s <= 0:
            raise ValueError("camera_wait_timeout_s must be finite and positive")
        if not math.isfinite(mission_timeout_s) or mission_timeout_s <= 0:
            raise ValueError("mission_timeout_s must be finite and positive")
        self.platform = platform
        self.motion = motion
        self.detector = detector or YoloColorDetector(weights=weights)
        self.object_positions = _normalise_positions(object_positions)
        self.camera_wait_timeout_s = float(camera_wait_timeout_s)
        self.mission_timeout_s = float(mission_timeout_s)
        self._mission = mission
        self._monotonic = monotonic
        self._condition = threading.Condition()
        self._latest: CameraObservation | None = None
        self._latest_sequence = -1
        self._motion_frame_sequence = -1
        self._closed = False

    def capture_after_step(self, fresh_camera_frame: bool) -> bool:
        """Publish an atomic RGB/base/time snapshot from the simulation thread."""
        if not fresh_camera_frame:
            return False
        camera = self.platform.camera
        if camera is None:
            raise RuntimeError("Task 2 Platform was created with camera=False")
        frame = camera.latest()
        if frame is None:
            return False
        sequence = int(frame.sequence)
        qpos = np.asarray(self.platform.data.qpos)
        if qpos.ndim != 1 or qpos.size < 2:
            raise ValueError("platform.data.qpos must contain base x and y")
        base_xy = (float(qpos[0]), float(qpos[1]))
        if not all(math.isfinite(value) for value in (*base_xy, float(frame.sim_time))):
            raise ValueError("camera snapshot contains non-finite pose or time")
        rgb = np.asarray(frame.rgb)
        if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
            raise ValueError("camera frame must be an HxWx3 uint8 RGB array")
        observation = CameraObservation(
            rgb_frame=rgb.copy(),
            base_xy=base_xy,
            sim_time=float(frame.sim_time),
        )
        with self._condition:
            if self._closed:
                return False
            if sequence <= self._latest_sequence:
                return False
            self._latest_sequence = sequence
            self._latest = observation
            self._condition.notify_all()
        return True

    def get_observation(self, after_sim_time: float | None) -> CameraObservation:
        """Wait for the first captured frame newer than ``after_sim_time``."""
        deadline = self._monotonic() + self.camera_wait_timeout_s
        with self._condition:
            while True:
                if self._closed:
                    raise Task4IntegrationClosedError("Task 4 integration is closed")
                observation = self._latest
                if (
                    observation is not None
                    and self._latest_sequence > self._motion_frame_sequence
                    and (after_sim_time is None or observation.sim_time > after_sim_time + 1e-9)
                ):
                    return observation
                remaining = deadline - self._monotonic()
                if remaining <= 0:
                    raise CameraFrameTimeoutError(
                        "no fresh Task 2 camera frame; is Platform.step() still running?"
                    )
                self._condition.wait(remaining)

    def planar_distance_m(
        self,
        base_xy: tuple[float, float],
        class_name: str,
        color: str,
    ) -> float:
        """Read scene truth only for Task 4's final C2 evaluation."""
        key = (class_name.strip().casefold(), color.strip().casefold())
        try:
            object_xy = self.object_positions[key]
        except KeyError as exc:
            raise UnknownSceneObjectError(f"no scene position for {color} {class_name}") from exc
        return math.hypot(object_xy[0] - base_xy[0], object_xy[1] - base_xy[1])

    def goto_object(self, class_name: str, color: str) -> bool:
        """Blocking callback passed directly to ``PlanExecutor``."""
        return self._mission(
            class_name,
            color,
            self.detector,
            self.get_observation,
            self.move,
            self.turn,
            self.stop,
            self.planar_distance_m,
            timeout_s=self.mission_timeout_s,
        )

    def _discard_motion_frame(self) -> None:
        # A frame newer than the previous detection can still predate this action's
        # completion. Wait for the simulation owner to publish another snapshot.
        with self._condition:
            self._motion_frame_sequence = self._latest_sequence

    def move(self, vx: float, vy: float, wz: float, duration: float) -> None:
        self.motion.move(vx, vy, wz, duration)
        self._discard_motion_frame()

    def turn(self, angle_deg: float) -> None:
        self.motion.turn(angle_deg)
        self._discard_motion_frame()

    def stop(self) -> None:
        self.motion.stop()
        self._discard_motion_frame()

    def close(self) -> None:
        """Wake camera waiters and stop any motion during simulator shutdown."""
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        self.motion.stop()


def load_object_positions(path: str | Path) -> dict[ObjectKey, tuple[float, float]]:
    """Load Task 2's evaluation-only ``assets/objects.json`` safely."""
    source_path = Path(path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load Task 2 objects file: {source_path}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("objects"), list):
        raise ValueError("objects file must contain an objects array")
    positions: dict[ObjectKey, tuple[float, float]] = {}
    for index, item in enumerate(raw["objects"]):
        if not isinstance(item, dict):
            raise ValueError(f"objects[{index}] must be an object")
        class_name = item.get("coco_class")
        color = item.get("color")
        position = item.get("position")
        if (
            not isinstance(class_name, str)
            or not isinstance(color, str)
            or not isinstance(position, list)
            or len(position) < 2
        ):
            raise ValueError(f"objects[{index}] has invalid class, color, or position")
        key = (class_name.strip().casefold(), color.strip().casefold())
        if key in positions:
            raise ValueError(f"duplicate scene object: {color} {class_name}")
        positions[key] = (_finite_float(position[0], index), _finite_float(position[1], index))
    return positions


def _normalise_positions(
    positions: ObjectPositions,
) -> dict[ObjectKey, tuple[float, float]]:
    result: dict[ObjectKey, tuple[float, float]] = {}
    for raw_key, raw_xy in positions.items():
        if (
            not isinstance(raw_key, tuple)
            or len(raw_key) != 2
            or not all(isinstance(value, str) for value in raw_key)
            or not isinstance(raw_xy, tuple)
            or len(raw_xy) != 2
        ):
            raise ValueError("object positions must map (class, color) to (x, y)")
        key = (raw_key[0].strip().casefold(), raw_key[1].strip().casefold())
        if key in result:
            raise ValueError(f"duplicate object position: {key}")
        x, y = float(raw_xy[0]), float(raw_xy[1])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError(f"object position must be finite: {key}")
        result[key] = (x, y)
    return result


def _finite_float(value: Any, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"objects[{index}] position must contain numbers")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"objects[{index}] position must be finite")
    return result
