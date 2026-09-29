# Step 10 — Pure-motion live demo

Date: 2026-09-29  
Mode: Task 2 browser GUI (`object_lab`)  
Planner: OpenAI `gpt-4o-mini` with Task 3 Structured Outputs and local validation  
Task 4 navigation: not invoked

| Case | English terminal input | Validated/executed result |
| --- | --- | --- |
| Forward | `Move forward at speed 0.4 for 2 seconds.` | `move(vx=0.4, vy=0, wz=0, duration_s=2)`; `SUCCESS` |
| Lateral | `Move left at speed 0.3 for 2 seconds.` | `move(vx=0, vy=0.3, wz=0, duration_s=2)`; `SUCCESS` |
| Turn | `Turn left 90 degrees.` | `turn(angle_deg=90)`; `SUCCESS`, final error `1.99 deg` |
| Sequence | `Move backward at speed 0.3 for 1 second, then turn right 45 degrees, then move right at speed 0.2 for 1 second.` | Three steps completed in order; right turn final error `-1.99 deg`; final lateral action used `vy=-0.2`; `SUCCESS` |
| Stop | Start `Move forward at speed 0.4 for 10 seconds.`, then enter `/stop` | Active move cancelled; `[DONE] status=CANCELLED` |
| Reject | `Write a poem about the moon.` | `accepted=false`, zero actions; `[DONE] status=REJECTED` |

## Issue found and corrected

The first sequence attempt mapped `move right` to positive `vy`, which contradicts the
Task 3 coordinate contract (`vy > 0` is left and `vy < 0` is right). The planner prompt was
clarified with explicit left/right sign rules and examples. After the change, the standalone
rightward command produced `vy=-0.2`, and the full three-step sequence produced the same
correct negative sign. The full Task 3 test suite then passed.

Reloading the browser panel while its previous polling requests were still open produced
transient server-side `BrokenPipeError` messages. The simulator, new page connection and
subsequent command execution continued normally; this was not an action or physics failure.
