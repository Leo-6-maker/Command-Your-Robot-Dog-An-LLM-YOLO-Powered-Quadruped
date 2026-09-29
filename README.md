# EE5112 MiniLab 1.3

Team source for the MiniLab. The course simulator remains a separate upstream dependency:
[`aoqianz/quadruped_mujoco`](https://github.com/aoqianz/quadruped_mujoco).

The inspected upstream snapshot is commit `dd40180f1121a66373d261e64a9a09eb69b1b2a7`.
The example creates the onboard `dog_front_camera`; the course brief requires Task 3 and Task 4
to use the Task 2 platform and scene.

## Task 3 — completed LLM command interface

Task 3 is implemented in [`task3/`](task3/README.md). It provides:

- a four-action JSON contract (`move`, `turn`, `goto_object`, and `stop`);
- OpenAI Structured Outputs and local Ollama/Qwen planners;
- independent schema, numeric safety, and explicit-direction consistency checks;
- a non-blocking terminal chat loop and sequential Task 2 action adapter;
- integration with `task4.py` for camera-only `goto_object` navigation;
- 102 automated tests and a fixed 20-command two-model benchmark.

The final Task 3 report is [`task3/Task3_Report.md`](task3/Task3_Report.md). The recorded
desktop demonstration uses local `qwen2.5:7b`; OpenAI and Qwen are compared separately with the
same benchmark cases, so the video does not need to duplicate the complete demonstration for
both providers.

## Task 4 core

`task4.py` contains CPU YOLO class detection, red/green color grounding, annotated frames, and a
callback-driven `goto_object` controller. It assumes a fresh `CameraObservation` with the RGB
frame, trunk XY and simulation time from one snapshot. Motion callbacks must finish each action
before returning. Scene truth is used only after stopping to compute the planar distance for C2.

The Task 4 core is connected to the simulator camera, Task 2 motion adapter and Task 3 executor
through `task3/task4_integration.py`. The integrated controller uses onboard images for steering;
scene truth is consulted only after stopping to calculate the final C2 distance.

## Assumed Task 2 / Task 3 interface

Task 3 should dispatch its validated `goto_object` action to `goto_object()` from its command
worker. Inject these Task 2 callbacks:

- `get_observation(after_sim_time)` returns a newer onboard RGB frame, trunk XY and simulation
  time from one snapshot.
- `move(vx, vy, wz, duration_s)` completes the timed move before returning; `turn(angle_deg)`
  completes the closed-loop turn; `stop()` clears queued motion.
- `planar_distance_m(base_xy, class_name, color)` reads the matching object's center from the
  Task 2 scene config. The controller calls it only after stopping and visually re-detecting the
  target; it must not use that position to steer.

The module currently grounds red and green chairs. Integration behavior and the camera-only smoke
test are recorded in [`task3/evidence/step11_task4_integration.md`](task3/evidence/step11_task4_integration.md).

Install `ultralytics` alongside the simulator dependencies before running YOLO. The default
weights are `yolo11n.pt`; Ultralytics downloads them on first model load if absent.

To inspect a saved Task 2 camera frame before navigation integration:

```powershell
python task4.py path\to\camera_frame.png
```

This prints `[DETECT]` lines and saves `camera_frame_task4.png` beside the input. It checks the
perception path only; it is not a navigation trial.
