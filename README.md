# EE5112 MiniLab 1.3 — Command Your Robot Dog

One MuJoCo quadruped executes typed English commands. Task 2 supplies the robot, object scene, onboard camera, and motion skills. Task 3 parses English with an LLM and executes validated actions. Task 4 uses YOLO and color grounding to search for and approach a requested chair. All three tasks share the **same Task 2 platform and scene**.

| Component | Code and assets |
| --- | --- |
| Task 2 | [`task2/task2/`](task2/task2/), [`task2/eg/`](task2/eg/), [`task2/src/`](task2/src/), [`task2/task2/assets/`](task2/task2/assets/) |
| Task 3 | [`task3/`](task3/) (prompt, schema, validator, chat, executor, motion adapter) |
| Task 4 | [`task4.py`](task4.py), [`task3/task4_integration.py`](task3/task4_integration.py), [`task3/dual_view.py`](task3/dual_view.py) |
| Optional bonus | [Multi-goal missions and English speech input](BONUS_README.md) |
| Report and evaluation | [`GROUP_REPORT_DRAFT.md`](GROUP_REPORT_DRAFT.md), [`TASK4_REPORT_SECTION.md`](TASK4_REPORT_SECTION.md), [compact Task 4 receipts](task4_evidence/2026-10-02-benchmark-d6f0c7b/) |

The locomotion platform and resources derive from [`aoqianz/quadruped_mujoco`](https://github.com/aoqianz/quadruped_mujoco), inspected at commit `dd40180f1121a66373d261e64a9a09eb69b1b2a7`. Student A's Task 2 changes and provenance are documented in [`task2/README_TASK2_中文.md`](task2/README_TASK2_%E4%B8%AD%E6%96%87.md) and [`task2/task2/assets/PROVENANCE.txt`](task2/task2/assets/PROVENANCE.txt). The ONNX walking policy, robot/terrain resources, and YOLO11n weights are retained because they are needed to run the simulator. **Videos, raw clips, ZIP archives, generated reports, and raw trial image series are not stored on GitHub.** Compact report images and numerical receipts are retained.

## Install on Windows

Use Python 3.12 and PowerShell. From this repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -e .\task2
.\.venv\Scripts\python.exe -m pip install -r .\task2\requirements-task2.txt
.\.venv\Scripts\python.exe -m pip install -r .\task3\requirements-task3.txt
```

The shared scene is [`task2/task2/assets/scene.xml`](task2/task2/assets/scene.xml), with object centers in [`objects.json`](task2/task2/assets/objects.json). Task 4 steers only from the robot's `dog_front_camera` RGB frames; object centers are read only after stopping to calculate the final distance. No Task 2 ZIP or separately extracted sibling folder is needed.

The Windows Task 3 and Task 4 demo scripts use the text-only DeepSeek `deepseek-chat` endpoint. Set `DEEPSEEK_API_KEY` outside this repository before launching them; never commit or record the key. Check presence without printing it:

```powershell
if ([string]::IsNullOrWhiteSpace($env:DEEPSEEK_API_KEY)) { 'Missing DEEPSEEK_API_KEY' } else { 'DEEPSEEK_API_KEY is set' }
```

Task 3 also supports OpenAI, local Ollama/Qwen, and DashScope through [`task3/run.py`](task3/run.py); see [`task3/README.md`](task3/README.md) for provider details. The runnable Windows scripts below use DeepSeek as configured for this team's integrated demonstration.

## Run Tasks 2–4

Run one simulation at a time from the repository root. Keep the terminal visible in the Task 3 and Task 4 desktop recordings.

| Task | PowerShell command | Demonstration |
| --- | --- | --- |
| 2 | `.\run_task2_demo.ps1` | Open `http://127.0.0.1:8765`; show the object scene and onboard camera, then enter `m` and `k` for a timed move and a closed-loop `[TURN]`. |
| 3 | `.\run_task3_demo.ps1` | After `[CHAT] event=READY`, type `Move forward at speed 0.4 for one second, then turn left 45 degrees.`; wait for `[DONE]`, then show a rejected English request. |
| 4 | `.\run_task4_demo.ps1` | Open `http://127.0.0.1:8766/`; after `[CHAT] event=READY`, type `Go to the green chair.` or `Go to the red chair.`; wait for `[FOUND]`, `[MISSION]`, and `[DONE]`. |

The Task 4 browser shows rear overhead and onboard views together. During search and approach, the lower panel displays the **latest frame actually processed by YOLO**, annotated with yellow boxes and class/color/confidence labels. Before the first inference it displays the raw live camera; after a mission the last YOLO frame may remain on screen. These annotations do not affect navigation. Type `/quit` to end a Task 3 or Task 4 session. New logs go to ignored `runs/`; choose a fresh `-RunId` for every rerun.

For a Task 4 video covering an initially hidden target and red/green chair disambiguation, run these as two separate missions, typing the English request yourself at each `READY` prompt:

```powershell
.\run_task4_demo.ps1 -RunId "red_$(Get-Date -Format 'yyyyMMdd_HHmmss')" -StartX 1 -StartY -1 -StartYaw 180
# After READY: Go to the red chair.
# After SUCCESS: /quit
.\run_task4_demo.ps1 -RunId "green_$(Get-Date -Format 'yyyyMMdd_HHmmss')" -StartX 1 -StartY 1 -StartYaw 0
# After READY: Go to the green chair.
# After SUCCESS: /quit
```

These poses are demonstration choices, not guaranteed success. After submitting the command, let the robot move autonomously; do not steer it with the browser or keyboard.

## Evaluation

Task 4 marks a target as found only when **C1** a fresh stopped onboard frame detects the requested class and color, **C2** trunk-to-object planar distance is at most `0.80 m`, and **C3** `[FOUND] class=... color=... t=... d=...` is printed. The course requires at least ten trials across different objects and starts, including an initially hidden target and same-class color disambiguation.

The retained [current summary and per-trial logs/JSON](task4_evidence/2026-10-02-benchmark-d6f0c7b/) report **8/10 C1–C3 successes and 0/10 object-contact trials for controller commit `d6f0c7b` only**. Earlier batches are historical and are not mixed into this fixed evaluation. Historical video clips and raw frame images remain local, outside Git. See [`TASK4_REPORT_SECTION.md`](TASK4_REPORT_SECTION.md) for the method, ten-trial table, and failure analysis.

To evaluate a new committed controller revision, choose a new output directory:

```powershell
.\.venv\Scripts\python.exe run_task4_benchmark.py runs\benchmark_new
.\.venv\Scripts\python.exe summarize_task4_benchmark.py runs\benchmark_new
```

The benchmark refuses to run if its output directory already exists, preventing old trial receipts from being relabelled with a new commit. Always choose a fresh path for a new batch. The benchmark supplies structured targets to isolate navigation. A separate live English-command recording demonstrates the Task 3 LLM-to-Task 4 path. Review every trial's log, stopped frame, distance, and contact record before changing report metrics. `runs/` is local and ignored by Git.

## Course submission

The course submission is **separate from this GitHub repository**: a group PDF report, source and setup instructions, scene/object and prompt files, and three local videos named `Video_Task2.mp4`, `Video_Task3.mp4`, and `Video_Task4.mp4`. Task 3 and Task 4 videos must keep the terminal visible. Task 4's video must show typed English commands, `[CMD]`, `[SEARCH]`/`[DETECT]`, `[FOUND]`, and `[MISSION]` for two objects, including one initially hidden and one same-class color distinction.

[`GROUP_REPORT_DRAFT.md`](GROUP_REPORT_DRAFT.md) is editable, **not final**. The group must fill its index, identities, actual contributions, and AI usage; review each video; and update Task 4 metrics only from a fixed evaluation of the final controller. To render a review copy, install `Markdown==3.4.1` and `PyMuPDF==1.27.2.2`, then run `python render_group_report.py` with Edge or Chrome installed. After reviewing the final PDF and three videos, create the Canvas ZIP locally:

```powershell
.\.venv\Scripts\python.exe prepare_submission.py <group-index> --report <final-report.pdf> --video-task2 <Video_Task2.mp4> --video-task3 <Video_Task3.mp4> --video-task4 <Video_Task4.mp4>
```

The packager rejects unresolved identity/contribution placeholders and refuses to overwrite an existing ZIP. It creates `..\minilab_1.3_group_<index>.zip`. Do not add that ZIP or the videos to Git; submit the reviewed ZIP to Canvas.
