# Task 4 fixed-configuration baseline

Code commit `43605b02dc5e6d6e4365627efa0fedb86bbd2593`. The ten predeclared
objects and starting poses are in `manifest.json`. Each trial has the raw
terminal log, `result.json`, onboard RGB frames and detector annotations.
The target was explicitly supplied to this navigation test harness, so these
trials do not test LLM parsing or form a Video_Task4 submission.

Configuration: Task 2 object-lab scene, dog_front_camera, 100° vertical FOV,
YOLO11n, red/green HSV grounding, 0.97 height threshold, four short final
steps, 120 s wall timeout. Ground-truth positions were read only after stopping.

| Trial | Target | Start x,y,yaw | C1 stop match | Final distance m | Result |
|---|---|---|---|---:|---|
| 01 | green chair | 1,1,0 | no | 0.707 | fail: close crop |
| 02 | red chair | 1,-1,0 | yes | 0.870 | fail: too far |
| 03 | green chair | 0.5,1,0 | no stop match | 0.753 | fail: full-turn search; final camera faces red chair |
| 04 | red chair | 0.5,-1,0 | yes | 0.940 | fail: too far |
| 05 | green chair | 0,0,0 | yes | 0.771 | success |
| 06 | red chair | 0,0,0 | no | 0.642 | fail: close crop |
| 07 | green chair | 1,1,180 | yes | 0.917 | fail: too far |
| 08 | red chair | 1,-1,180 | yes | 0.720 | success |
| 09 | green chair | 1,0,30 | yes | 0.720 | success |
| 10 | red chair | 1,0,-30 | no | 0.671 | fail: close crop |

**Approach success:** 3/10 = 30%. **Stopped-frame target detection:**
6/9 = 66.7%; the nine trials that stopped near a chair had a visibly present
target in the saved onboard frame, inspected manually. Trial 03 exhausted its
search turn and its final frame shows the red chair, so it is outside this
stopped-frame denominator. **Grounding:** all 6 stop frames with a matching
class/color detection were closer to the commanded chair than the other chair;
6/9 stopped episodes had confirmed correct grounding. All three successful
trials had no reported object contact. These are episode-level measures on
this small, deliberately varied set, not a COCO mAP estimate.

Failure analysis: four fixed short steps were too few for narrow chair boxes
(02, 04, 07), but caused near chairs to fill/crop the frame (01, 06, 10).
Trial 03 lost the requested target during repeated large search turns. The
controller was subsequently changed to use **live box width** to choose a
bounded number of terminal steps; the next trial set is kept separately.
