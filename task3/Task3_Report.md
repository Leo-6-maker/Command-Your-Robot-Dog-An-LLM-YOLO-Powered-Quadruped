# EE5112 MiniLab 1.3 — Task 3 Final Report

## 1. Deliverable summary

Task 3 converts an English terminal command into a validated JSON action plan and executes the
plan through the Task 2 quadruped platform. It also dispatches visual object-navigation actions to
the existing Task 4 controller. The implementation supports two interchangeable LLM providers:
OpenAI `gpt-4o-mini` and local `qwen2.5:7b` through Ollama.

Submitted material includes:

- Task 3 source code, JSON Schema and 102 automated tests;
- Task 2 motion-queue and Task 4 visual-navigation integration;
- a fixed 20-command benchmark for both LLMs;
- per-command latency, token, cost and failure records;
- a 1080p MP4 desktop demonstration and its verification metadata.

No API key, `.env` file, model weight or private credential is stored in Git.

## 2. System architecture

```text
English terminal command
        |
        v
local input policy
        |
        v
OpenAI planner OR Ollama/Qwen planner
        |
        v
JSON/schema validator -> explicit direction guard
        |
        v
sequential PlanExecutor
        |
        +---- move / turn / stop ----> Task2MotionAdapter ----> Task 2 queue
        |
        +---- goto_object -----------> Task4Integration ------> task4.py
                                                              |
                                                    onboard RGB camera only
```

LLM and robot work run in a command worker. The MuJoCo owner thread continuously calls
`platform.step()`, so inference, queue waits and Task 4 navigation never block physics updates.

## 3. Action contract and safety boundary

The model may emit only four action types:

| Action | Important limits |
|---|---|
| `move(vx, vy, wz, duration_s)` | velocities in `[-1, 1]`; duration in `(0, 60]` seconds |
| `turn(angle_deg)` | non-zero angle in `[-720, 720]` degrees |
| `goto_object(class, color)` | supported targets: red or green chair |
| `stop` | must be the only action in its plan |

OpenAI Structured Outputs and Ollama's schema format reduce malformed responses, but neither is
trusted. `validator.py` independently rejects missing/extra fields, wrong types, booleans used as
numbers, NaN/Infinity, duplicate JSON keys, unsafe ranges, empty accepted plans and actions in a
rejected plan.

The final runtime additionally compares explicit one-action direction words with numeric signs:
forward/backward use positive/negative `vx`, left/right translation uses positive/negative `vy`,
and left/right turns use positive/negative angles. A contradiction produces a visible `[GUARD]`
rejection and no motion. This was added after Qwen produced text saying “right” with `vy=+0.2`.

## 4. Terminal, context and execution

The asynchronous chat loop prints stable one-line evidence records:

```text
[INPUT] -> [LLM] -> [CMD] -> [PLAN] -> [EXEC] -> [DONE]
```

`[INPUT]` contains the sanitised user text. In accordance with the course log protocol, `[CMD]`
contains the parsed action calls and count, for example
`[CMD] actions=move(...),turn(...) n=2`. Rejections instead produce a stable record such as
`[CMD] rejected reason=unsupported_request`; `[PLAN]` is retained as additional validation detail
and does not replace the required `[CMD]` record.

Actions execute strictly in list order. A failure or cancellation stops the current action and
skips all remaining actions. Only an accepted plan whose execution ends in `SUCCESS` becomes the
next conversational context. This lets “Do that again, but slower” refer to the last successful
move without allowing a rejected or failed request to poison later commands.

## 5. Task 2 and Task 4 integration

Task 2's `move()` and `turn()` methods enqueue work and return immediately. `Task2MotionAdapter`
turns that interface into blocking worker-side operations by observing queue completion and closed-
loop turn result records. It never advances MuJoCo itself.

`Task4Integration` captures a synchronized onboard-camera, robot-position and simulation-time
snapshot immediately after `platform.step()`. `goto_object()` uses YOLO detections and image-space
feedback to steer. Object truth coordinates are read only after stopping to calculate the final C2
distance; they do not control navigation.

## 6. Two-model benchmark

Both providers received the same 20 independent cases at temperature zero: 10 basic commands,
5 paraphrases and 5 invalid/out-of-range requests. This planner-only benchmark did not move the
robot.

| Provider | Model | Overall | Basic | Paraphrase | Invalid | Mean latency | API cost |
|---|---|---:|---:|---:|---:|---:|---:|
| OpenAI | `gpt-4o-mini` | 15/20 (75%) | 9/10 | 1/5 | 5/5 | 1.096 s | $0.003601 |
| Ollama | `qwen2.5:7b` | 16/20 (80%) | 10/10 | 4/5 | 2/5 | 0.973 s | $0.000000 |

OpenAI was more conservative: it rejected all five invalid requests, but over-rejected safe
paraphrases. Qwen understood more valid wording but was weaker on safety limits. It clipped a
requested speed of 1.5 to 1.0 and emitted out-of-range duration/angle values in two cases. The
local numeric validator blocked the latter two. Qwen also reversed the sign of a rightward
paraphrase; the final direction guard blocks this class of runtime error.

The raw results and all failure records are in `evidence/step13_benchmark_results.json` and
`evidence/step13_benchmark.md`. The benchmark predates the direction guard deliberately: the table
measures each LLM's own understanding rather than post-processing accuracy.

## 7. Verification

Run all Task 3 tests from the repository root:

```bash
conda run -n ee5112-minilab python -m pytest -q task3
```

Current main-aligned result during the log-protocol revision:

```text
115 passed, 3 failed
```

The tests cover parsing, schema and semantic limits, direction consistency, provider boundaries,
context, cancellation, strict execution order, Task 2 completion, Task 4 callbacks, log sanitising,
benchmark scoring and cost calculations. All 40 log/chat/policy/executor tests pass. The three
remaining failures are inherited Task 4 final-redetection test mismatches in the current `main`
baseline and are tracked separately from this logging change.

## 8. Reproduction

The final local verification environment used Python 3.12.14, MuJoCo 3.14.0, NumPy 2.5.3,
Ultralytics 8.4.160, OpenAI Python 3.20.0 and Ollama 0.34.4. Task 3 pins only the additional
Python dependency it introduces; simulator and vision packages come from the Task 2 environment.

Install the Task 3 Python dependency in the existing Task 2 environment:

```bash
python -m pip install -r task3/requirements-task3.txt
```

For OpenAI:

```bash
export OPENAI_API_KEY="..."  # set locally; never commit it
python -m task3.run --provider openai --model gpt-4o-mini \
  --task2-root /path/to/task2-project --gui
```

For local Qwen:

```bash
ollama serve
ollama pull qwen2.5:7b       # first use only
python -m task3.run --provider ollama --model qwen2.5:7b \
  --task2-root /path/to/task2-project --gui
```

Enter `/quit` to cancel outstanding work and stop the integrated runtime safely.

## 9. Video evidence

The previous desktop recording predates the corrected `[INPUT]`/`[CMD]` protocol and is retained
only as historical evidence. It must be re-recorded after the remaining improvements are complete;
the final recording must visibly show parsed-action and rejected `[CMD]` records. Both providers
are evaluated with the common benchmark, so only one integrated provider demonstration is needed.

- File: `EE5112_MiniLab1_3_Task3_Demo.mp4`
- Format: H.264 MP4, 1920x1080, 30 FPS, 95.8 seconds
- SHA-256: `60286cd75e30b259b027c979f05546675a1a5cb6f65f1b407d9fe5bb06c28d0c`

The replacement MP4 will be uploaded separately to the course submission system and will not be
committed to the source repository. Recording commands and acceptance checks are in
`evidence/step15_video_script.md`.

## 10. Known limitations

- The explicit direction guard intentionally handles only unambiguous single-action commands;
  arbitrary multi-clause semantic equivalence remains an LLM/evaluation problem.
- A schema-valid model may still alter a requested magnitude, as Qwen did for speed 1.5. Runtime
  limits prevent unsafe values, but complete intent equivalence requires broader semantic checks.
- Local Qwen has no API fee but requires Ollama, model storage and suitable local compute.
- Visual navigation depends on onboard-camera visibility and detector quality; scene truth is not
  a fallback steering signal.

## 11. Evidence index

- `evidence/step10_pure_motion.md` — live movement and sequential-action checks
- `evidence/step11_task4_integration.md` — camera-only Task 4 integration
- `evidence/step12_local_qwen.md` — local provider setup and end-to-end run
- `evidence/step13_benchmark.md` — two-provider comparison and failure analysis
- `evidence/step13_benchmark_results.json` — machine-readable benchmark records
- `evidence/step14_tests_logs.md` — automated coverage and log contract
- `evidence/step15_video_script.md` — final video commands and technical verification
