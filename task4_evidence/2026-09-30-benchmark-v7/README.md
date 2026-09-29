# Task 4 fixed ten-trial evaluation (final controller)

Controller revision: `49af5eddeb61b9db25b2967f75a4b7fa954502e8`.
The ten starts and target colors are fixed in `manifest.json`. Every trial uses
the same Task 2 object-lab scene, `dog_front_camera` at 100-degree vertical FOV,
CPU YOLO11n plus HSV color grounding, 0.97 visual box-height trigger, at most
four calibrated terminal short steps, and a 120-second wall timeout. Object
coordinates are used only after stopping for C2 and later evaluation.

Results computed from the raw logs, JSON receipts, images and the Task 2
object metadata are in `summary.csv` and `summary.json`: **8/10 successes**,
**9/10 stopped-frame target class/color detections**, **9/10 grounded stops**,
and **0/10 object-contact trials**. The hidden green and hidden red starts both
succeeded. Trial 03 reached 0.702 m in the independent post-mission snapshot
but was correctly failed because no matching target was detected in its
stopped frames (C1). Trial 10 saw the red chair at the stop but its C2 distance
was 0.8195 m, above the 0.80 m limit. The last post-mission snapshot distance
in `summary.csv` can differ slightly from the C2 value in the mission log.

The associated genuine Task 3/LLM GUI recording is `../Video_Task4.mp4`; it
contains a successful initially hidden red-chair mission followed by a green
chair mission. Committed terminal receipts are in `../2026-09-30-video/`.
