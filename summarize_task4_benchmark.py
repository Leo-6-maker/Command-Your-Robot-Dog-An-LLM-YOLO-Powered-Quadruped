"""Turn raw Task 4 trial receipts into a reproducible evaluation table."""

import csv
import json
import math
from pathlib import Path
import re
import sys

from task3.task4_integration import load_object_positions

root = Path(sys.argv[1])
objects_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "task2/task2/assets/objects.json")
positions = load_object_positions(objects_file)
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
rows = []
for trial in manifest["trials"]:
    name = trial["id"]
    result = json.loads((root / name / "result.json").read_text(encoding="utf-8"))
    log = (root / (name + ".log")).read_text(encoding="utf-8")
    failure = re.findall(r"\[MISSION\] status=FAIL reason=([^\r\n]+)", log)
    found = re.search(r"\[FOUND\] class=chair color=(green|red) t=([\d.]+) s d=([\d.]+) m", log)
    stopped = bool(found or "visual_stop_outside_0.80m" in log or
                   "target_not_visible_at_stop" in log)
    c1 = bool(found or "visual_stop_outside_0.80m" in log)
    own_distance = result.get("final_distance_m")
    base = result.get("final", {}).get("base_xy")
    other_color = "red" if trial["color"] == "green" else "green"
    other_xy = positions[("chair", other_color)]
    other_distance = math.hypot(base[0] - other_xy[0], base[1] - other_xy[1]) if base else None
    grounded = bool(c1 and own_distance is not None and other_distance is not None
                    and own_distance < other_distance)
    row = dict(trial=name, color=trial["color"], start_pose=trial["start"],
               initially_detected=result.get("initially_visible"),
               stopped=stopped, c1_target_detected=c1, grounded=grounded,
               found_logged=bool(found), success=result["success"],
               final_distance_m=own_distance, object_contacts=len(result.get("object_contacts", [])),
               failure=failure[-1] if failure else result.get("error", ""))
    rows.append(row)

with (root / "summary.csv").open("w", encoding="utf-8", newline="") as output:
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
stopped = sum(row["stopped"] for row in rows)
matches = sum(row["c1_target_detected"] for row in rows)
grounded = sum(row["grounded"] for row in rows)
successes = sum(row["success"] for row in rows)
summary = dict(code_revision=manifest["code_revision"], trials=len(rows),
               stopped_attempts=stopped, c1_matches=matches,
               confirmed_grounding=grounded, successes=successes,
               object_contact_trials=sum(bool(row["object_contacts"]) for row in rows))
(root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
