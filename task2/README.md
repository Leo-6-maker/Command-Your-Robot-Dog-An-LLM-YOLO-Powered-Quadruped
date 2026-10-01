# Task 2 — shared quadruped platform

This directory now contains the Task 2 source directly. No Task 2 ZIP or sibling runtime checkout is required. The adapted platform and scene are in `task2/`; the course locomotion runtime and robot resources are in `eg/` and `src/`. The ONNX walking policy and YOLO11n weights are retained as runtime inputs. Their origin is recorded in [`task2/assets/PROVENANCE.txt`](task2/assets/PROVENANCE.txt).

From the repository root on Windows, follow the [root installation and integrated demo instructions](../README.md). To run Task 2 alone after installation:

```powershell
cd task2
..\.venv\Scripts\python.exe -m task2.run --gui --duration 600
```

Open `http://127.0.0.1:8765`. Enter `m` for a timed move and `k` for a closed-loop 180-degree turn. The browser can select the object lab scene and the onboard front, rear overhead, and top cameras. The root [`run_task2_demo.ps1`](../run_task2_demo.ps1) runs the same demonstration.

The authored objects and their evaluation-only centers are in [`task2/assets/scene.xml`](task2/assets/scene.xml) and [`task2/assets/objects.json`](task2/assets/objects.json). Task 3 and Task 4 import this exact platform. The [Chinese implementation guide](README_TASK2_%E4%B8%AD%E6%96%87.md) and [`Task2_Report.md`](Task2_Report.md) explain the camera, 50 Hz ONNX policy, 200 Hz MuJoCo/PD loop, motion queue, and turn evaluation. Compact report evidence is under `evidence/`; generated logs and videos stay local and are not committed.
