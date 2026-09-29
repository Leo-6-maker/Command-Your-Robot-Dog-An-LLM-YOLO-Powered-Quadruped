# Fixed ten-trial Task 4 evaluation (v6)

Code revision: `eb18698617c6e188a5e879266da885170ad2bc67`.
All ten cases use the same Task 2 object lab, front RGB camera at 100 degrees,
YOLO11n plus HSV color, 0.97 box-height trigger, four-step maximum terminal
approach, and 120-second wall timeout. The start pose and requested chair color
are specified in `manifest.json`; no object coordinates enter navigation.

`summary.csv` and `summary.json` are computed from each trial's original log,
`result.json`, and Task 2 object metadata after the mission. The raw logs and
initial/final camera images are retained beside each result.

Result: **7/10 mission successes**, **10/10 stopped-frame class/color matches**,
**10/10 color-grounded stops**, and **0/10 object-contact trials**. Both colors
and initially hidden targets are represented. Trial 08 found the hidden red
chair. Trials 07, 09 and 10 detected the correct chair at the stop but failed
the 0.80 m C2 limit: C2 distances in their mission logs are 0.8108, 0.8032
and 0.8099 m respectively. They remain failures; post-mission snapshot
distances in `summary.csv` are independent measurements and do not override
the stopped-frame decision.

The live GUI/LLM recording is a separate execution mode. Its first working
capture on this revision (`runs/task4_demo_red_hidden_03.log`) reached the red
chair but lost the YOLO chair class at close range, so that recording is not
used as a successful demonstration. Terminal-step calibration was subsequently
revised and is evaluated as a separate code revision.
