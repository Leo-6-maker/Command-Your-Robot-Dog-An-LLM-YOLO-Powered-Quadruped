"""Student C: one real Task 2/4 trial with a supplied target (no LLM call).

This is calibration/evaluation, not a replacement for the typed-command video.
"""

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import threading
import time

from PIL import Image

from task3.run import _import_task2, _task2_assets_dir
from task3.task2_adapter import Task2MotionAdapter
from task3.task4_integration import Task4Integration, load_object_positions
from task4 import YoloColorDetector, annotate_frame, goto_object


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task2-root", type=Path, required=True)
    parser.add_argument("--color", choices=("green", "red"), default="green")
    parser.add_argument("--start", type=float, nargs=3, default=(0, 0, 0),
                        metavar=("X", "Y", "YAW_DEG"))
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--stop-box-height", type=float, default=0.88)
    parser.add_argument("--final-steps", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not all(math.isfinite(v) for v in (*args.start, args.timeout)) or args.timeout <= 0:
        parser.error("start pose must be finite and timeout must be finite and positive")
    args.output.mkdir(parents=True, exist_ok=False)
    assets = _task2_assets_dir(_import_task2(args.task2_root))
    from task2.platform import Platform

    detector = YoloColorDetector(weights=str(assets / "yolo11n.pt"))
    platform = Platform()
    bridge = None
    worker = None
    result = dict(target_class="chair", target_color=args.color, start_pose=args.start,
                  timeout_wall_s=args.timeout, stop_box_height=args.stop_box_height,
                  final_approach_steps=args.final_steps, success=False)
    last_observation = None

    def recorded_mission(class_name, color, detector, get_observation, *callbacks, **options):
        def observe(after):
            nonlocal last_observation
            last_observation = get_observation(after)
            return last_observation
        return goto_object(class_name, color, detector, observe, *callbacks, **options,
                           stop_box_height=args.stop_box_height,
                           final_approach_steps=args.final_steps)
    try:
        x, y, yaw = args.start
        half_angle = math.radians(yaw) / 2
        platform.config["simulation"]["initial_position"] = [x, y, 0.42]
        platform.config["simulation"]["initial_quaternion"] = [
            math.cos(half_angle), 0, 0, math.sin(half_angle)
        ]
        platform.reset()
        bridge = Task4Integration(
            platform, Task2MotionAdapter(platform), load_object_positions(assets / "objects.json"),
            detector=detector, mission_timeout_s=args.timeout,
            mission=recorded_mission,
        )
        for _ in range(400):
            bridge.capture_after_step(platform.step())

        def save_frame(label):
            observation = bridge.get_observation(None)
            detections = detector.detect(observation.rgb_frame)
            Image.fromarray(observation.rgb_frame).save(args.output / f"{label}.png")
            Image.fromarray(annotate_frame(observation.rgb_frame, detections)).save(
                args.output / f"{label}_annotated.png"
            )
            result[label] = dict(sim_time=observation.sim_time, base_xy=observation.base_xy,
                                 detections=[asdict(d) for d in detections])
            return any(d.matches("chair", args.color) for d in detections)

        result["initially_visible"] = save_frame("initial")
        started = time.monotonic()
        start_sim = float(platform.data.time)
        print(f"[TRIAL] class=chair color={args.color} source=explicit_target start={args.start}")

        def mission():
            try:
                result["success"] = bridge.goto_object("chair", args.color)
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
                print(f"[MISSION] status=FAIL reason={result['error']}")

        worker = threading.Thread(target=mission, name="task4-trial")
        worker.start()
        contacts = set()
        while worker.is_alive():
            bridge.capture_after_step(platform.step())
            for contact in platform.data.contact:
                bodies = [platform.model.body(int(platform.model.geom_bodyid[g])).name
                          for g in (contact.geom1, contact.geom2)]
                if any(any(obj in name for obj in ("green_chair", "red_chair", "orange_ball"))
                       for name in bodies):
                    contacts.add(tuple(bodies))
            if time.monotonic() - started > args.timeout + 10:
                result["error"] = "trial_watchdog_timeout"
                bridge.close()
                break
        worker.join(timeout=5)
        if worker.is_alive():
            raise RuntimeError("mission worker did not stop after cancellation")
        result["elapsed_wall_s"] = time.monotonic() - started
        result["elapsed_sim_s"] = float(platform.data.time) - start_sim
        if last_observation is not None:
            Image.fromarray(last_observation.rgb_frame).save(args.output / "last_controller_frame.png")
            result["last_controller_snapshot"] = dict(
                sim_time=last_observation.sim_time, base_xy=last_observation.base_xy
            )
        if result.get("error") == "trial_watchdog_timeout":
            result["success"] = False
            (args.output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            return 1
        # Publish a new stopped frame for independent post-mission evidence.
        while not bridge.capture_after_step(platform.step()):
            pass
        result["final_target_visible"] = save_frame("final")
        result["final_distance_m"] = bridge.planar_distance_m(
            result["final"]["base_xy"], "chair", args.color
        )
        result["object_contacts"] = sorted(contacts)
        result["success"] = bool(result["success"] and not contacts and not result.get("error"))
        (args.output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[TRIAL] result={args.output / 'result.json'} success={result['success']}")
        return 0 if result["success"] else 1
    finally:
        if bridge is not None:
            bridge.close()
        if worker is not None:
            worker.join(timeout=5)
        platform.close()


if __name__ == "__main__":
    raise SystemExit(main())
