# Task 4: YOLO object search and approach

## Method and integration

We used the Task 2 `object_lab` MJCF scene (`task2/assets/scene.xml` inside
`task2/EE5112_Task2_GitHub_Upload.zip`) and its quadruped locomotion skills.
The controller reads only the robot's onboard `dog_front_camera` RGB frames
(640 × 480, sampled at 10 Hz of simulation time). The shared camera has a
100° vertical field of view in both the Task 4 trial runner and the Task 3
interactive entry point. The browser display uses a rear overhead camera to
show the dog and objects; it does not feed the controller.

CPU YOLO11n supplies COCO class labels and bounding boxes at confidence ≥0.25.
For each box we convert its pixels to HSV, ignore pixels with saturation <70
or value <45, and label red or green when at least 35% of the remaining pixels
fall in the corresponding hue range (Pillow hue 0–255: red 0–14 or 242–255;
green 50–128). This simple class-plus-color rule suits the two same-class
chairs in our scene without a separate color model. It can fail when the chair
is heavily cropped, partially occluded, or affected by body pitch.

Task 3 parses the typed English command into a validated
`goto_object(class="chair", color="red"|"green")` action. The Task 4 callback
requests synchronized fresh camera/robot-pose snapshots from the Task 2
adapter. After three consecutive camera misses it rotates 30° and detects
again; after detection it turns toward the box center and advances through
completed 0.25 s motion skills. Close-range box width limits the final number
of short steps. A full search turn without a target, timeout, lost stopped-frame
target, or excessive final distance prints `[MISSION] status=FAIL reason=...`.
The mission wall-clock timeout is 120 s in the fixed evaluation; the GUI
demonstrations allow 180 s.

The robot first stops, then checks the target class **and** color on a fresh
onboard frame (C1). Only then does it read the Task 2 object center to compute
trunk-to-object planar distance and enforce d ≤0.80 m (C2). It prints one
`[FOUND] class=... color=... t=... d=...` line only after C1 and C2 pass (C3).
Object coordinates never steer the robot. The simulator's object-contact
records are checked after each trial.

## Fixed evaluation

All ten trials used controller commit `49af5ed`, one scene, one detector and
one parameter set. We varied requested color and robot start position/yaw;
180° starts deliberately face away from the target. These are structured
target trials that isolate navigation; the separate video verifies the real
English LLM-to-simulator path. The table's `d_eval` is the independent
post-mission snapshot distance in meters. C2 is decided from the live stopped
snapshot in each mission log, so a small difference between the two distances
does not change the verdict.

| Trial | Target | Start (x, y, yaw°) | Initial target detection | C1 class + color | d_eval (m) | Result |
|---|---|---|---|---|---:|---|
| 01 | green chair | (1, 1, 0) | yes | yes | 0.751 | success |
| 02 | red chair | (1, −1, 0) | yes | yes | 0.769 | success |
| 03 | green chair | (0.5, 1, 0) | yes | **no** | 0.702 | fail: target absent on stopped frame |
| 04 | red chair | (0.5, −1, 0) | yes | yes | 0.748 | success |
| 05 | green chair | (0, 0, 0) | no | yes | 0.749 | success |
| 06 | red chair | (0, 0, 0) | yes | yes | 0.758 | success |
| 07 | green chair | (1, 1, 180) | no | yes | 0.732 | success, initially hidden |
| 08 | red chair | (1, −1, 180) | no | yes | 0.759 | success, initially hidden |
| 09 | green chair | (1, 0, 30) | no | yes | 0.799 | success |
| 10 | red chair | (1, 0, −30) | no | yes | 0.813 | fail: stopped C2 d = 0.8195 m |

The stopped-frame target detection rate is **9/10 (90%)**. Grounding selected
the requested color on **9/9** stops with a target detection, or **9/10 (90%)**
of all trials. The full C1–C3 approach success rate is **8/10 (80%)**, with
**0/10 object-contact trials**. This detection rate is a task-level stopped
frame measure, not conventional mAP; we did not annotate every frame with
ground-truth boxes. Five starts had no initial target detection, including
the two 180° hidden starts. Trial 03 demonstrates why distance alone cannot
count as found: its d_eval was within 0.80 m, but C1 failed. Trial 10 detected
the correct chair yet missed C2 by 0.0195 m at the decision frame.

The exact raw evidence is in
[`task4_evidence/2026-09-30-benchmark-v7/`](task4_evidence/2026-09-30-benchmark-v7/):
`manifest.json`, per-trial logs, `result.json`, initial and stopped RGB images,
annotated detections, `summary.csv` and `summary.json`. The complete v6 batch
is also retained separately to show the terminal-step change and its earlier
7/10 result; no trials from the two code revisions are combined.

## Video and reproduction

[`task4_evidence/Video_Task4.mp4`](task4_evidence/Video_Task4.mp4) is a
104.375 s, 1920 × 1080, 8 fps desktop recording. The terminal remains visible
throughout both unaltered executions. The first command is `Go to the red
chair.` from a 180° start; it shows `[CMD]`, `[SEARCH]`, `[DETECT]`, `[FOUND]
... d=0.74 m`, and `[MISSION] status=SUCCESS`. The second is `Go to the green
chair.`; both red and green chair detections occur in that live log, and it
ends with `[FOUND] ... d=0.75 m` and `[MISSION] status=SUCCESS`. The video uses
the real Task 3 chat loop and DeepSeek `deepseek-chat` JSON planner; the API
key is read from `DEEPSEEK_API_KEY` in the environment and is not in the repo.
Task 3's separate report covers its OpenAI-versus-local-Qwen comparison.
The two original terminal logs and the final MP4 hash are in
[`task4_evidence/2026-09-30-video/`](task4_evidence/2026-09-30-video/).

On Windows, extract `task2/EE5112_Task2_GitHub_Upload.zip` beside this repo so
that `../task2_runtime/task2/task2/platform.py` exists. Install the packaged
Task 2 and Task 3 requirements under Python 3.12, then run from this repo:

```powershell
Expand-Archive .\task2\EE5112_Task2_GitHub_Upload.zip -DestinationPath ..\task2_runtime
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -e ..\task2_runtime\task2
.\.venv\Scripts\python.exe -m pip install -r ..\task2_runtime\task2\requirements-task2.txt -r task3\requirements-task3.txt pywin32
.\.venv\Scripts\python.exe -u run_task4_benchmark.py task4_evidence\new_fixed_batch
.\.venv\Scripts\python.exe summarize_task4_benchmark.py task4_evidence\new_fixed_batch
.\capture_task4_demo.ps1 -Color red -RunId red_new
.\capture_task4_demo.ps1 -Color green -RunId green_new
```

The measured Windows environment was Python 3.12.7, MuJoCo 3.14.0,
NumPy 2.5.2, ONNX Runtime 1.30.0, Ultralytics 8.3.111,
PyTorch 2.6.0+cpu and Pillow 10.4.0. The packaged Task 2 requirements may
install newer patch versions on another machine, so rerun the fixed batch
there before comparing outcomes.

The benchmark runs headlessly with structured targets; the capture scripts
open the live browser at <http://127.0.0.1:8765> and an interactive terminal.
They require a configured `DEEPSEEK_API_KEY`, Windows desktop access, and the
video helper packages `imageio-ffmpeg` and `pywin32`. A human can instead run
`run_task4_demo.ps1` and type the English command in its terminal. The final
video concatenates the two successful desktop clips in red-then-green order
without changing either execution.
