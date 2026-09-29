"""YOLO class detection and red/green grounding for Task 4.

Input frames are RGB uint8 images from ``dog_front_camera``. Camera capture,
motion skills, and the Task 3 command parser stay outside this module.
"""

import argparse
from dataclasses import dataclass
import math
from pathlib import Path
import time
from typing import Callable

import numpy as np
from PIL import Image


# Candidate calibration shared by both entry points; formal multi-pose trials pending.
CAMERA_FOVY_DEG = 100.0
STOP_BOX_HEIGHT = 0.97
FINAL_APPROACH_STEPS = 4


@dataclass(frozen=True)
class Detection:
    class_name: str
    color: str
    confidence: float
    bbox: tuple[int, int, int, int]
    frame_width: int
    frame_height: int

    @property
    def center_x(self) -> float:
        return (self.bbox[0] + self.bbox[2]) / 2

    def matches(self, class_name: str, color: str) -> bool:
        return (
            self.class_name.casefold() == class_name.strip().casefold()
            and self.color.casefold() == color.strip().casefold()
        )

    def log_line(self) -> str:
        x1, y1, x2, y2 = self.bbox
        return (
            f"[DETECT] class={self.class_name} color={self.color} "
            f"conf={self.confidence:.2f} bbox=[{x1},{y1},{x2},{y2}]"
        )


@dataclass(frozen=True)
class CameraObservation:
    rgb_frame: np.ndarray
    base_xy: tuple[float, float]
    sim_time: float


def _box_color(
    rgb_frame: np.ndarray,
    bbox: tuple[int, int, int, int],
    min_share: float,
) -> str:
    x1, y1, x2, y2 = bbox
    hsv = np.asarray(Image.fromarray(rgb_frame[y1:y2, x1:x2]).convert("HSV"))
    hue, saturation, value = hsv.transpose(2, 0, 1)
    visible = (saturation >= 70) & (value >= 45)
    hue = hue[visible]
    if hue.size == 0:
        return "unknown"

    # ponytail: support the required red/green pair; add hue bins if the scene uses more colors.
    # Pillow stores HSV hue on 0..255; red wraps across both ends of that range.
    red = (hue <= 14) | (hue >= 242)
    green = (hue >= 50) & (hue <= 128)
    red_share = np.count_nonzero(red) / hue.size
    green_share = np.count_nonzero(green) / hue.size
    if red_share >= min_share and red_share > green_share:
        return "red"
    if green_share >= min_share:
        return "green"
    return "unknown"


class YoloColorDetector:
    """Detect COCO classes and ground the two colors needed for chair disambiguation."""

    def __init__(
        self,
        weights: str = "yolo11n.pt",
        confidence: float = 0.25,
        min_color_share: float = 0.35,
    ):
        if not 0.0 <= confidence <= 1.0 or not 0.0 <= min_color_share <= 1.0:
            raise ValueError("confidence and min_color_share must be in [0, 1]")
        from ultralytics import YOLO

        self.model = YOLO(weights)
        self.confidence = confidence
        self.min_color_share = min_color_share

    def detect(self, rgb_frame: np.ndarray) -> list[Detection]:
        if (
            not isinstance(rgb_frame, np.ndarray)
            or rgb_frame.ndim != 3
            or rgb_frame.shape[2] != 3
            or rgb_frame.shape[0] == 0
            or rgb_frame.shape[1] == 0
            or rgb_frame.dtype != np.uint8
        ):
            raise ValueError("rgb_frame must be an HxWx3 uint8 RGB array")

        height, width = rgb_frame.shape[:2]
        result = self.model.predict(
            source=Image.fromarray(np.ascontiguousarray(rgb_frame)),
            conf=self.confidence,
            device="cpu",
            verbose=False,
        )[0]
        detections = []
        if result.boxes is None:
            return detections

        for box, class_id, confidence in zip(
            result.boxes.xyxy.cpu().numpy(),
            result.boxes.cls.cpu().numpy(),
            result.boxes.conf.cpu().numpy(),
        ):
            x1, y1, x2, y2 = box
            bbox = (
                max(0, int(np.floor(x1))),
                max(0, int(np.floor(y1))),
                min(width, int(np.ceil(x2))),
                min(height, int(np.ceil(y2))),
            )
            if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                continue

            detection = Detection(
                class_name=result.names[int(class_id)],
                color=_box_color(rgb_frame, bbox, self.min_color_share),
                confidence=float(confidence),
                bbox=bbox,
                frame_width=width,
                frame_height=height,
            )
            print(detection.log_line())
            detections.append(detection)

        return detections


def annotate_frame(rgb_frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
    """Return an RGB frame with class, color and confidence labels."""
    image = Image.fromarray(rgb_frame.copy())
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        label = f"{detection.class_name} {detection.color} {detection.confidence:.2f}"
        draw.rectangle(detection.bbox, outline=(0, 255, 0), width=2)
        draw.text((x1, max(0, y1 - 14)), label, fill=(0, 255, 0))
    return np.asarray(image)


def goto_object(
    class_name: str,
    color: str,
    detector: YoloColorDetector,
    get_observation: Callable[[float | None], CameraObservation],
    move: Callable[[float, float, float, float], None],
    turn: Callable[[float], None],
    stop: Callable[[], None],
    planar_distance_m: Callable[[tuple[float, float], str, str], float],
    *,
    timeout_s: float = 60.0,
    scan_step_deg: float = 30.0,
    misses_before_search: int = 3,
    stop_box_height: float = STOP_BOX_HEIGHT,
    final_approach_steps: int = FINAL_APPROACH_STEPS,
    center_tolerance: float = 0.06,
    camera_fovy_deg: float = CAMERA_FOVY_DEG,
) -> bool:
    """Search, align and approach using injected Task 2 inputs.

    ``get_observation(after_sim_time)`` waits for a newer RGB frame, trunk XY
    and sim time captured from one simulation snapshot. ``move`` and ``turn``
    complete before returning, and ``stop`` clears queued motion. Scene truth
    is read only after stopping to verify/log C2; it never steers. Call from
    the Task 3 command worker, not from the physics loop.
    """
    if timeout_s <= 0 or not 0 < scan_step_deg <= 360 or misses_before_search < 1:
        raise ValueError("timeout_s, scan_step_deg or misses_before_search is invalid")
    if (
        not 0 < stop_box_height < 1
        or not 0 < center_tolerance < 0.5
    ):
        raise ValueError(
            "stop_box_height and center_tolerance must be fractions in (0, 1)"
        )
    if not isinstance(final_approach_steps, int) or not 0 <= final_approach_steps <= 20:
        raise ValueError("final_approach_steps must be an integer in [0, 20]")
    if not 0 < camera_fovy_deg < 180:
        raise ValueError("camera_fovy_deg must be in (0, 180)")

    target_class, target_color = class_name.strip().casefold(), color.strip().casefold()
    started = time.monotonic()
    start_sim_time = None
    last_sim_time = None
    scanned_deg = 0.0
    misses = 0
    near_steps = 0

    def fail(reason: str) -> bool:
        print(f"[MISSION] status=FAIL reason={reason}")
        return False

    try:
        while time.monotonic() - started < timeout_s:
            observation = get_observation(last_sim_time)
            last_sim_time = observation.sim_time
            if start_sim_time is None:
                start_sim_time = observation.sim_time
            detections = detector.detect(observation.rgb_frame)
            targets = [d for d in detections if d.matches(target_class, target_color)]
            if not targets:
                misses += 1
                if misses < misses_before_search:
                    continue
                misses = 0
                if scanned_deg >= 360.0:
                    return fail("full_turn_without_detection")
                angle = min(scan_step_deg, 360.0 - scanned_deg)
                print(f"[SEARCH] target={target_color}_{target_class} rotating={angle:.0f}deg")
                turn(angle)
                scanned_deg += angle
                continue

            scanned_deg = 0.0
            misses = 0
            # A larger low-confidence duplicate can include background and send
            # the final turn away from the chair. Prefer the detector's confidence.
            target = max(targets, key=lambda detection: detection.confidence)
            x1, y1, x2, y2 = target.bbox
            offset_x = target.center_x - target.frame_width / 2
            focal_px = target.frame_height / (
                2 * math.tan(math.radians(camera_fovy_deg) / 2)
            )
            height_share = (y2 - y1) / target.frame_height
            if abs(offset_x) > center_tolerance * target.frame_width:
                angle = -math.degrees(math.atan2(offset_x, focal_px))
                if height_share >= 0.75:
                    angle = max(-12.0, min(12.0, angle))
                turn(angle)
                # Turning changes the box size: judge stopping from a new frame.
                continue
            # ponytail: the terminal steps retain the teammate's scene calibration;
            # success still requires a fresh class/color detection after stopping.
            if height_share >= stop_box_height:
                width_share = (x2 - x1) / target.frame_width
                # Height saturates when the chair meets the image borders. Width
                # still separates the too-far and nearly-cropped cases in this scene.
                if width_share < 0.42:
                    if near_steps >= 8:
                        stop()
                        return fail("visual_proximity_unreliable")
                    move(0.20, 0.0, 0.0, 0.25)
                    near_steps += 1
                    continue
                terminal_steps = min(final_approach_steps,
                                     0 if width_share > 0.58 else
                                     2 if width_share > 0.44 else final_approach_steps)
                if terminal_steps:
                    print(f"[APPROACH] final_visual_steps={terminal_steps}")
                for _ in range(terminal_steps):
                    move(0.20, 0.0, 0.0, 0.25)

                stop()
                # The first stopped frame can still catch body pitch settling.
                # Stay stopped and require a live match within three fresh frames.
                for _ in range(3):
                    final_observation = get_observation(last_sim_time)
                    last_sim_time = final_observation.sim_time
                    final_targets = [
                        d for d in detector.detect(final_observation.rgb_frame)
                        if d.matches(target_class, target_color)
                    ]
                    if final_targets:
                        break
                if not final_targets:
                    return fail("target_not_visible_at_stop")
                distance = planar_distance_m(
                    final_observation.base_xy, target_class, target_color
                )
                if not math.isfinite(distance) or distance < 0:
                    return fail("distance_unavailable")
                if distance > 0.80:
                    return fail(
                        f"visual_stop_outside_0.80m distance_m={distance:.4f}"
                    )

                elapsed = final_observation.sim_time - start_sim_time
                print(
                    f"[FOUND] class={target_class} color={target_color} "
                    f"t={elapsed:.1f} s d={distance:.2f} m"
                )
                print("[MISSION] status=SUCCESS")
                return True

            move(0.25, 0.0, 0.0, 0.25)

        return fail("timeout")
    finally:
        stop()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Task 4 YOLO/color grounding on one RGB frame"
    )
    parser.add_argument("image", type=Path, help="saved RGB frame from the onboard camera")
    parser.add_argument("--weights", default="yolo11n.pt")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    with Image.open(args.image) as source:
        rgb_frame = np.asarray(source.convert("RGB"))
    detections = YoloColorDetector(weights=args.weights).detect(rgb_frame)
    output = args.output or args.image.with_name(f"{args.image.stem}_task4.png")
    Image.fromarray(annotate_frame(rgb_frame, detections)).save(output)
    print(f"[FRAME] output={output} detections={len(detections)}")


if __name__ == "__main__":
    main()
