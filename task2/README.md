# Task 2 — Platform, scene, camera and motion skills

[Download the complete Task 2 package](EE5112_Task2_GitHub_Upload.zip). The archive preserves all 123 files and their directory structure: source code, robot/terrain resources, ONNX and YOLO weights, custom scene, report, evaluation results and demo video.

## Run

Extract the archive into a separate working directory. Inside its `task2/` folder, follow `README_TASK2_中文.md`. With Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-task2.txt
MUJOCO_GL=egl python -m task2.run --gui --duration 600
```

Open http://localhost:8765. M triggers a timed move; K triggers a closed-loop 180-degree turn.

## Contents and status

- `task2/`: platform, camera, motion skills, scene builder, verification and evaluation scripts.
- `task2/assets/`: scene MJCF, object centres and YOLO11n weights.
- `eg/` and `src/`: course platform resources from aoqianz/quadruped_mujoco, commit dd40180f1121a66373d261e64a9a09eb69b1b2a7.
- `Task2_Report.pdf` and `.md`: report chapter; fill in the student identity before submission.
- `evidence/`: detection images, turn comparison, logs and Video_Task2.mp4. The included video is an offscreen recording with synchronized log text. A desktop recording with the actual terminal visible still needs to be supplied.

Task 2 uses a nonblocking motion queue. The existing Task 4 callbacks expect blocking completion and a synchronized RGB/pose snapshot, so integration requires an adapter; it is not already connected.

This upload adds only this Task 2 directory. The existing root README, .gitignore and task4.py are unchanged.
