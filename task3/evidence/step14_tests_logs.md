# Step 14 evidence — automated tests and terminal logs

Date: 2026-09-29; final guard audit: 2026-09-30

## Scope

Step 14 added automated checks and made terminal evidence consistent. Four final direction-guard
tests were subsequently added after the Step 15 dry run exposed a schema-valid but reversed
lateral velocity.

## New automated coverage

The suite first increased from 79 to 98 tests. Those 19 additional cases cover:

- the exact 20-case benchmark composition (10 basic, 5 paraphrase, 5 invalid/out-of-range);
- semantic scoring, including the fact that `0` and `0.0` are equivalent but opposite direction signs are not;
- OpenAI cached/uncached/output token cost calculation;
- benchmark accuracy, latency, token and failure summaries;
- non-English and dangerous local rejection patterns;
- intentional provider handling of ASCII-only foreign text and unrelated English;
- terminal log newline collapse, length limits, provider metadata sanitising and missing metric formatting;
- exact accepted validator boundaries: speeds `-1`/`1`, duration `60`, and turns `-720`/`720`;
- execution order across `move -> goto_object -> turn`.

The final suite contains 102 tests. The four later cases verify that explicit right/left,
forward/backward and turn words agree with the generated action sign, that a mismatched plan is
converted to a rejection before reaching the motion executor, and that contextual/object-location
phrasing is not falsely classified as a direct lateral command.

An initial test assumed ASCII-only French could be identified locally. The implementation intentionally uses only conservative dependency-free checks, so ASCII-only language classification remains the LLM's responsibility. The test was corrected to preserve that boundary rather than introducing an unreliable local language detector.

## Log contract

Runtime output now uses stable one-line prefixes and `key=value` fields:

```text
[RUNTIME] event=START ...
[CHAT] event=READY ...
[INPUT] text=...
[LLM] provider=... model=... latency_s=... input_tokens=... output_tokens=... accepted=... actions=...
[CMD] actions=move(...),turn(...) n=2
[PLAN] accepted=... actions=... message=...
[EXEC] step=... type=... parameters/status=...
[DONE] status=... actions/stage/reason=...
[RUNTIME] event=STOP ...
```

Rejected input uses `[CMD] rejected reason=<stable_code>`, for example `non-English`,
`unsafe_request`, `unsupported_request`, `direction_mismatch` or `planner_error`. This separates
the original natural-language input from the parsed command semantics required by the course.

Provider token counts use `na` when unavailable and `0` only for a known zero, so missing telemetry is not confused with free or empty usage. Untrusted command, model and exception text is collapsed to one line before logging; tests verify that embedded text such as `[DONE] status=SUCCESS` cannot create a forged second event.

## Verification

Command:

```bash
conda run -n ee5112-minilab python -m pytest -q task3
```

Original Step 14 result:

```text
........................................................................ [ 70%]
..............................                                           [100%]
102 passed in 0.20s
```

`git diff --check` also completed without errors.

On 2026-10-02, four new protocol tests were added. The focused log/chat/policy/executor suite is
`40 passed`; the full main-aligned suite is `115 passed, 3 failed`, with all three failures inherited
from Task 4 final-redetection behavior and unrelated to the logging change.
