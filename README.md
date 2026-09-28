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

Install `ultralytics` alongside the simulator dependencies before running YOLO. The default
weights are `yolo11n.pt`; Ultralytics downloads them on first model load if absent.
