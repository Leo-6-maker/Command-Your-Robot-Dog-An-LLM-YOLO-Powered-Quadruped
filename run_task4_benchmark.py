"""Run the fixed Task 4 configuration on ten documented scene starts."""

import argparse
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

def build_manifest(revision: str) -> dict:
    """Describe one immutable batch before any trial starts."""
    return dict(
        code_revision=revision,
        camera_fovy_deg=CAMERA_FOVY_DEG,
        stop_box_height=STOP_BOX_HEIGHT,
        final_approach_steps=FINAL_APPROACH_STEPS,
        timeout_wall_s=120,
        trials=[
            dict(id=name, color=color, start=[x, y, yaw])
            for name, color, x, y, yaw in TRIALS
        ],
    )


def prepare_output_root(root: Path, manifest: dict) -> None:
    """Create a new batch directory without ever reusing old receipts."""
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(
            f"benchmark output already exists: {root}; choose a new path"
        ) from exc
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path("runs/task4_benchmark"),
        help="new output directory; an existing path is rejected",
    )
    args = parser.parse_args(argv)
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    try:
        prepare_output_root(args.output, build_manifest(revision))
    except FileExistsError as exc:
        parser.error(str(exc))

    complete = True
    for name, color, x, y, yaw in TRIALS:
        output = args.output / name
        command = [
            sys.executable,
            "-u",
            "run_task4_trial.py",
            "--task2-root",
            str(Path("task2")),
            "--color",
            color,
            "--start",
            str(x),
            str(y),
            str(yaw),
            "--timeout",
            "120",
            "--output",
            str(output),
        ]
        print(f"[BENCH] {name} starting", flush=True)
        with (args.output / f"{name}.log").open("w", encoding="utf-8") as log:
            try:
                process = subprocess.run(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=150,
                    check=False,
                )
                has_result = (output / "result.json").is_file()
                complete = complete and has_result
                print(
                    f"[BENCH] {name} exit={process.returncode} result={has_result}",
                    flush=True,
                )
            except subprocess.TimeoutExpired:
                has_result = (output / "result.json").is_file()
                complete = complete and has_result
                print(
                    f"[BENCH] {name} exceeded 150s result={has_result}; inspect log",
                    flush=True,
                )
    if not complete:
        print("[BENCH] incomplete batch; do not summarize or combine it", flush=True)
        return 1
    print(f"[BENCH] complete revision={revision} trials={len(TRIALS)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
