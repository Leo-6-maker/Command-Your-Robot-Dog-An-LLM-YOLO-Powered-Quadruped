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
from task4 import (CAMERA_FOVY_DEG, FINAL_APPROACH_STEPS, STOP_BOX_HEIGHT,
                   YoloColorDetector, annotate_frame, goto_object)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task2-root", type=Path, required=True)
    parser.add_argument("--class", dest="target_class", choices=("chair", "sports ball"),
                        default="chair")
    parser.add_argument("--color", choices=("green", "red", "orange"), default="green")
    parser.add_argument("--start", type=float, nargs=3, default=(0, 0, 0),
                        metavar=("X", "Y", "YAW_DEG"))
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--stop-box-height", type=float, default=STOP_BOX_HEIGHT)
    parser.add_argument("--final-steps", type=int, default=FINAL_APPROACH_STEPS)
    parser.add_argument("--camera-fovy", type=float, default=CAMERA_FOVY_DEG,
                        help="vertical FOV of the same onboard front camera")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gui", action="store_true", help="show live MuJoCo in the browser")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--start-delay", type=float, default=0, help="seconds to view before motion")
    parser.add_argument("--hold-open", type=float, default=0, help="seconds to view after the trial")
    args = parser.parse_args()
    if (args.target_class, args.color) not in {
        ("chair", "green"), ("chair", "red"), ("sports ball", "orange")
    }:
        parser.error("unsupported class/color pair")
    if not all(math.isfinite(v) for v in (*args.start, args.timeout)) or args.timeout <= 0:
        parser.error("start pose must be finite and timeout must be finite and positive")
    if any(not math.isfinite(v) or v < 0 for v in (args.start_delay, args.hold_open)):
        parser.error("viewing delays must be finite and nonnegative")
    if not 0 < args.camera_fovy < 180:
        parser.error("camera FOV must be in (0, 180)")
    args.output.mkdir(parents=True, exist_ok=False)
    assets = _task2_assets_dir(_import_task2(args.task2_root))
    from task2.platform import Platform

    detector = YoloColorDetector(weights=str(assets / "yolo11n.pt"))
    platform = Platform(gui=args.gui, port=args.port)
    bridge = None
    worker = None
    result = dict(target_class=args.target_class, target_color=args.color, start_pose=args.start,
                  timeout_wall_s=args.timeout, stop_box_height=args.stop_box_height,
                  final_approach_steps=args.final_steps, success=False)
    result["camera_fovy_deg"] = args.camera_fovy
    last_observation = None

    def recorded_mission(class_name, color, detector, get_observation, *callbacks, **options):
        def observe(after):
            nonlocal last_observation
            last_observation = get_observation(after)
            return last_observation
        return goto_object(class_name, color, detector, observe, *callbacks, **options,
                           stop_box_height=args.stop_box_height,
                           final_approach_steps=args.final_steps,
                           camera_fovy_deg=args.camera_fovy)
    try:
        with platform.runtime.model_lock:
            platform.model.camera("dog_front_camera").fovy[0] = args.camera_fovy
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
            return any(d.matches(args.target_class, args.color) for d in detections)

        result["initially_visible"] = save_frame("initial")
        if args.gui:
            print(f"[VIEW] http://localhost:{args.port} -- select dog_front_camera for robot vision", flush=True)
        view_until = time.monotonic() + args.start_delay
        while time.monotonic() < view_until and platform.runtime.is_running():
            step_started = time.monotonic()
            bridge.capture_after_step(platform.step())
            time.sleep(max(0, 0.005 - (time.monotonic() - step_started)))
        started = time.monotonic()
        start_sim = float(platform.data.time)
        print(f"[TRIAL] class={args.target_class} color={args.color} source=explicit_target start={args.start}")

        def mission():
            try:
                result["success"] = bridge.goto_object(args.target_class, args.color)
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
                print(f"[MISSION] status=FAIL reason={result['error']}")

        worker = threading.Thread(target=mission, name="task4-trial")
        worker.start()
        contacts = set()
        abort_reason = None
        while worker.is_alive():
            step_started = time.monotonic()
            bridge.capture_after_step(platform.step())
            if args.gui:
                time.sleep(max(0, 0.005 - (time.monotonic() - step_started)))
            for contact in platform.data.contact:
                bodies = [platform.model.body(int(platform.model.geom_bodyid[g])).name
                          for g in (contact.geom1, contact.geom2)]
                if any(any(obj in name for obj in ("green_chair", "red_chair", "orange_ball"))
                       for name in bodies):
                    contacts.add(tuple(bodies))
            if not platform.runtime.is_running() or time.monotonic() - started > args.timeout + 10:
                abort_reason = ("viewer_closed" if not platform.runtime.is_running()
                                else "trial_watchdog_timeout")
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
        if abort_reason is not None:
            result["error"] = abort_reason
            result["object_contacts"] = sorted(contacts)
            result["success"] = False
            (args.output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            return 1
        # Publish a new stopped frame for independent post-mission evidence.
        while not bridge.capture_after_step(platform.step()):
            pass
        result["final_target_visible"] = save_frame("final")
        result["final_distance_m"] = bridge.planar_distance_m(
            result["final"]["base_xy"], args.target_class, args.color
        )
        result["object_contacts"] = sorted(contacts)
        result["success"] = bool(result["success"] and not contacts and not result.get("error"))
        (args.output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[TRIAL] result={args.output / 'result.json'} success={result['success']}")
        if args.gui and args.hold_open:
            print(f"[VIEW] Trial finished; standing for {args.hold_open:g}s. Close Page exits.", flush=True)
            view_until = time.monotonic() + args.hold_open
            while time.monotonic() < view_until and platform.runtime.is_running():
                step_started = time.monotonic()
                platform.step()
                time.sleep(max(0, 0.005 - (time.monotonic() - step_started)))
        return 0 if result["success"] else 1
    finally:
        if bridge is not None:
            bridge.close()
        if worker is not None:
            worker.join(timeout=5)
        platform.close()


if __name__ == "__main__":
    raise SystemExit(main())
