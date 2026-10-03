# Step 11 — Task 4 integration evidence

> Historical log note: this run predates the 2026-10-02 protocol correction. The current runtime
> prints the raw sentence as `[INPUT] text=...` and the parsed navigation action as
> `[CMD] goto_object class=chair color=green`.

Date: 2026-09-29

## Wiring checked

- Task 3 validates `goto_object(class, color)` and passes it to `PlanExecutor`.
- `Task4Integration` supplies `task4.goto_object()` with atomic onboard RGB, base XY,
  simulation time, and blocking Task 2 motion callbacks.
- MuJoCo stepping and camera capture remain on the main thread.
- Object truth coordinates are read only after visual stop for the final C2 distance
  evaluation; they are never used for steering or approach control.

## Camera-only smoke test

Before motion, the real Task 2 onboard camera and YOLO detected:

```text
[DETECT] class=chair color=green conf=0.68 bbox=[169,107,250,226]
[DETECT] class=chair color=red conf=0.57 bbox=[390,107,462,225]
[DETECT] class=sports ball color=red conf=0.46 bbox=[296,189,339,232]
[STEP11-CAMERA] fresh=True sim_time=1.905 detections=3
[STEP11-CAMERA] robot motion command issued: no
```

## End-to-end command

Command entered in the real terminal chat loop:

```text
Go to the green chair.
```

Successful terminal result:

```text
[CMD] Go to the green chair.
[LLM] provider=openai model=gpt-4o-mini latency_s=1.231 accepted=true actions=1
[PLAN] accepted=true actions=1 message=Command accepted.
[EXEC] step=1/1 type=goto_object class=chair color=green
[APPROACH] final_visual_steps=7
[FOUND] class=chair color=green t=17.1 s d=0.69 m
[MISSION] status=SUCCESS
[EXEC] step=1/1 type=goto_object status=SUCCESS
[DONE] status=SUCCESS actions=1
```

The final distance was 0.69 m, inside the required 0.80 m bound. The browser view
showed the robot stopped beside the green chair.

## Calibration and regression coverage

- Explicit prompt examples prevent the LLM from incorrectly rejecting the supported
  green chair.
- The close-range target selection uses the largest matching YOLO box, avoiding a
  smaller overlapping box with higher confidence.
- Once the chair fills 88% of the image height, Task 4 performs one final visual
  alignment and seven fixed low-speed 0.25 s steps. This avoids relying on a
  classification after the chair is cropped by the camera frame.
- Failed final-distance logs include the measured distance for reproducible tuning.
- Full automated result: `75 passed`.
