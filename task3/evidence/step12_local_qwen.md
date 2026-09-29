# Step 12 evidence — local Qwen provider

Date: 2026-09-29

## Scope

Step 12 adds a second LLM provider only. It does not run the 20-command benchmark from Step 13.

- Provider/runtime: local Ollama 0.34.4
- Selected model: `qwen2.5:7b`
- Hardware used: NVIDIA GeForce RTX 3070 Ti Laptop GPU
- Endpoint: `http://127.0.0.1:11434/api/chat`
- OpenAI key required: no
- OpenAI API charge: none

Both providers use the same system prompt, JSON action schema, local validator, successful-plan context rules, executor, Task 2 adapter and Task 4 callback. The model can only propose JSON; it never calls MuJoCo or Task 2 directly.

## Model selection check

`qwen3:4b-instruct` was tried first but incorrectly rejected the supported command `Move right at speed 0.2 for one second.`. It was not accepted as the Step 12 model.

`qwen2.5:7b` correctly produced:

```text
move(vx=0.0, vy=-0.2, wz=0.0, duration_s=1.0)
```

The initial right-turn check exposed an ambiguous sign choice, so the shared prompt was strengthened with explicit left/right examples. A repeat check then returned `turn(angle_deg=-90)` for `Turn right 90 degrees.`. This prompt fix applies to both OpenAI and Ollama.

Additional spot checks passed for forward movement, `goto_object(class="chair", color="green")`, and rejection of an unrelated poem request. These checks are model-selection smoke tests, not the Step 13 benchmark.

The rejected Qwen3 model was removed after selection, leaving only `qwen2.5:7b` (reported model size 4.7 GB).

## Real end-to-end execution

The Task 3 process was launched with `OPENAI_API_KEY` removed from its environment:

```bash
env -u OPENAI_API_KEY python -m task3.run \
  --provider ollama \
  --model qwen2.5:7b \
  --task2-root /path/to/task2-platform \
  --gui --duration 120 --port 8765
```

Terminal input and result:

```text
Move forward for one second.
[CMD] Move forward for one second.
[LLM] provider=ollama model=qwen2.5:7b latency_s=1.246 accepted=true actions=1
[PLAN] accepted=true actions=1 message=Moving forward for one second.
[EXEC] step=1/1 type=move vx=0.40 vy=0.00 wz=0.00 duration_s=1.00
[SKILL] move values=(0.4, 0.0, 0.0, 1.0) t=81.96
[MOVE] completed duration=1.00
[EXEC] step=1/1 type=move status=SUCCESS
[DONE] status=SUCCESS actions=1
```

This demonstrates the complete local path:

```text
English terminal command
  -> local qwen2.5:7b
  -> structured JSON
  -> local validator
  -> PlanExecutor
  -> Task 2 motion queue
  -> MuJoCo movement
```

## Safety and failure behavior

- Ollama receives the full JSON Schema through its structured-output `format` field.
- Temperature is zero and seed is fixed for repeatability.
- Returned JSON is still parsed and checked by the existing local validator.
- A missing or incomplete Ollama response is rejected before execution.
- Connection errors are surfaced as planner errors; there is no automatic fallback to OpenAI.
- Provider, model, latency, input tokens and output tokens use the same `PlanningResult` fields as OpenAI for the later Step 13 comparison.

## Automated verification

The Step 12 tests cover schema transmission, deterministic options, token accounting, local validation, incomplete responses, connection errors, turn direction wording, and operation without an OpenAI key.

```text
79 passed
```
