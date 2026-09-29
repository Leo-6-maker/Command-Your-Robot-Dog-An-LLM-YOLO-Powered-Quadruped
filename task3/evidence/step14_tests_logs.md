# Step 14 evidence — automated tests and terminal logs

Date: 2026-09-29

## Scope

Step 14 adds automated checks and makes terminal evidence consistent. It does not record the Step 15 demonstration video.

## New automated coverage

The suite increased from 79 to 98 tests. The 19 additional cases cover:

- the exact 20-case benchmark composition (10 basic, 5 paraphrase, 5 invalid/out-of-range);
- semantic scoring, including the fact that `0` and `0.0` are equivalent but opposite direction signs are not;
- OpenAI cached/uncached/output token cost calculation;
- benchmark accuracy, latency, token and failure summaries;
- non-English and dangerous local rejection patterns;
- intentional provider handling of ASCII-only foreign text and unrelated English;
- terminal log newline collapse, length limits, provider metadata sanitising and missing metric formatting;
- exact accepted validator boundaries: speeds `-1`/`1`, duration `60`, and turns `-720`/`720`;
- execution order across `move -> goto_object -> turn`.

An initial test assumed ASCII-only French could be identified locally. The implementation intentionally uses only conservative dependency-free checks, so ASCII-only language classification remains the LLM's responsibility. The test was corrected to preserve that boundary rather than introducing an unreliable local language detector.

## Log contract

Runtime output now uses stable one-line prefixes and `key=value` fields:

```text
[RUNTIME] event=START ...
[CHAT] event=READY ...
[CMD] text=...
[LLM] provider=... model=... latency_s=... input_tokens=... output_tokens=... accepted=... actions=...
[PLAN] accepted=... actions=... message=...
[EXEC] step=... type=... parameters/status=...
[DONE] status=... actions/stage/reason=...
[RUNTIME] event=STOP ...
```

Provider token counts use `na` when unavailable and `0` only for a known zero, so missing telemetry is not confused with free or empty usage. Untrusted command, model and exception text is collapsed to one line before logging; tests verify that embedded text such as `[DONE] status=SUCCESS` cannot create a forged second event.

## Verification

Command:

```bash
conda run -n ee5112-minilab python -m pytest -q task3
```

Result:

```text
........................................................................ [ 73%]
..........................                                               [100%]
98 passed in 0.21s
```

`git diff --check` also completed without errors.
