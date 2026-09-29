# Task 4 width-adaptive second evaluation

Fixed code revision and ten start poses: `manifest.json`. Raw images, logs,
contact observations and `result.json` remain in every trial directory.
Same Task 2 scene, 100° onboard camera and YOLO/HSV pipeline as the baseline.
The controller used the live chair box width to take an additional observed
step for narrow boxes or fewer terminal steps for wide boxes. Ground truth
was still used only after stopping for C2 evaluation.

| Trial | Target / pose | Final d (m) | Outcome |
|---|---|---:|---|
| 01 | green / 1,1,0 | 0.730 | success |
| 02 | red / 1,-1,0 | 0.754 | success |
| 03 | green / 0.5,1,0 | 0.718 | success |
| 04 | red / 0.5,-1,0 | 0.699 | success |
| 05 | green / 0,0,0 | 0.722 | success |
| 06 | red / 0,0,0 | 0.759 | success |
| 07 | green / 1,1,180 | 0.762 | full turn without a stopped match |
| 08 | red / 1,-1,180 | 0.564 | timeout during repeated search turns |
| 09 | green / 1,0,30 | 0.702 | stopped match missing |
| 10 | red / 1,0,-30 | 0.729 | timeout during repeated search turns |

Approach success **6/10 = 60%**; stopped-frame C1 target detection **6/7**
episodes that reached the visual stop; confirmed class/color grounding **6/7**
of those stops. No object contact was recorded in any trial. Trials 07, 08 and
10 demonstrate a separate control failure: once a near chair is near the image
edge, the bbox-centre steering can request roughly 30–45° turns and lose it
again. Trial 09 lost live detection after its terminal steps. The next fixed
version limits large turns on near frames and slightly reduces terminal motion
for medium-width boxes.

The `final_target_visible` field comes from a later *independent* logging
frame. For successes 03 and 05 it was false even though the controller's
earlier stopped frame had passed C1 and printed `[FOUND]`. This is an observed
near-distance perception limit, not a substitute for the C1 snapshot.
