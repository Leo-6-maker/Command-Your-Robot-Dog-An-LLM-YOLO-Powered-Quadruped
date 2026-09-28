# EE5112 MiniLab 1.3

Team source for the MiniLab. The course simulator remains a separate upstream dependency:
[`aoqianz/quadruped_mujoco`](https://github.com/aoqianz/quadruped_mujoco).

The inspected upstream snapshot is commit `dd40180f1121a66373d261e64a9a09eb69b1b2a7`.
The example creates the onboard `dog_front_camera`; the course brief requires Task 3 and Task 4
to use the Task 2 platform and scene.

## Task 4 core

`task4.py` contains CPU YOLO class detection, red/green color grounding, annotated frames, and a
callback-driven `goto_object` controller. It assumes a fresh `CameraObservation` with the RGB
frame, trunk XY and simulation time from one snapshot. Motion callbacks must finish each action
before returning. Scene truth is used only after stopping to compute the planar distance for C2.

This core is prepared but is not yet connected to the simulator camera, Task 2 motion queue, or
Task 3 parser. The initial box-height stop threshold and color thresholds need calibration with
the final scene.

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

The module currently grounds red and green. Before calling the mission complete, calibrate the
visual stop threshold against C2 and evaluate at least 10 trials, including an initially hidden
target and same-class color disambiguation. Camera/motion integration, Task 3 dispatch, trial
results, and demo evidence are still open.

Install `ultralytics` alongside the simulator dependencies before running YOLO. The default
weights are `yolo11n.pt`; Ultralytics downloads them on first model load if absent.

To inspect a saved Task 2 camera frame before navigation integration:

```powershell
python task4.py path\to\camera_frame.png
```

This prints `[DETECT]` lines and saves `camera_frame_task4.png` beside the input. It checks the
perception path only; it is not a navigation trial.
