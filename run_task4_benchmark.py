"""Run the fixed Task 4 configuration on ten documented scene starts."""

import json
from pathlib import Path
import subprocess
import sys

from task4 import CAMERA_FOVY_DEG, FINAL_APPROACH_STEPS, STOP_BOX_HEIGHT


TRIALS = [
    ("01_green_aligned", "green", 1, 1, 0),
    ("02_red_aligned", "red", 1, -1, 0),
    ("03_green_offset", "green", .5, 1, 0),
    ("04_red_offset", "red", .5, -1, 0),
    ("05_green_center", "green", 0, 0, 0),
    ("06_red_center", "red", 0, 0, 0),
    ("07_green_hidden", "green", 1, 1, 180),
    ("08_red_hidden", "red", 1, -1, 180),
    ("09_green_angled", "green", 1, 0, 30),
    ("10_red_angled", "red", 1, 0, -30),
]
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("task4_evidence/2026-09-30-benchmark")
ROOT.mkdir(parents=True, exist_ok=True)
revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
manifest = dict(code_revision=revision, camera_fovy_deg=CAMERA_FOVY_DEG,
                stop_box_height=STOP_BOX_HEIGHT, final_approach_steps=FINAL_APPROACH_STEPS,
                timeout_wall_s=120, trials=[dict(id=name, color=color, start=[x,y,yaw])
                                           for name,color,x,y,yaw in TRIALS])
(ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
for name, color, x, y, yaw in TRIALS:
    output = ROOT / name
    if (output / "result.json").exists():
        print(f"[BENCH] {name} existing result, skipping", flush=True)
        continue
    command = [sys.executable, "-u", "run_task4_trial.py", "--task2-root",
               str(Path("../task2_runtime/task2")), "--color", color,
               "--start", str(x), str(y), str(yaw), "--timeout", "120",
               "--output", str(output)]
    print(f"[BENCH] {name} starting", flush=True)
    with (ROOT / f"{name}.log").open("w", encoding="utf-8") as log:
        try:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=150, check=False)
            print(f"[BENCH] {name} exit={process.returncode} result={(output / 'result.json').exists()}",
                  flush=True)
        except subprocess.TimeoutExpired:
            print(f"[BENCH] {name} exceeded 150s; inspect log", flush=True)
