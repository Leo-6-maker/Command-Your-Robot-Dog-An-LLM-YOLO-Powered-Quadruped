"""Package the reviewed group report, three videos, source, and current evidence."""

import argparse
from pathlib import Path
import subprocess
import zipfile

import fitz


root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("group_index", type=int)
parser.add_argument("--report", type=Path, required=True)
parser.add_argument("--video-task2", type=Path, required=True)
parser.add_argument("--video-task3", type=Path, required=True)
parser.add_argument("--video-task4", type=Path, required=True)
parser.add_argument("--video-bonus", type=Path, help="optional reviewed speech/multi-goal video")
args = parser.parse_args()
if args.group_index < 1:
    parser.error("group_index must be positive")
videos = [("Task2", args.video_task2), ("Task3", args.video_task3), ("Task4", args.video_task4)]
if args.video_bonus is not None:
    videos.append(("Bonus", args.video_bonus))
for file in (args.report, *(video for _, video in videos)):
    if not file.is_file():
        parser.error(f"missing file: {file}")
with fitz.open(args.report) as report:
    report_text = "\n".join(page.get_text() for page in report)
    placeholders = (
        "[TEAM TO FILL]", "[Student A]", "[Student B]", "[Student C]",
        "[insert actual", "[Review and fill", "[Each member must",
    )
    if any(marker in report_text for marker in placeholders):
        parser.error("report still contains team identity or contribution placeholders")

destination = root.parent / f"minilab_1.3_group_{args.group_index}.zip"
if destination.exists():
    parser.error(f"package already exists: {destination}")
try:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
except (OSError, subprocess.CalledProcessError):
    parser.error("package from a Git checkout so only versioned source is included")
source_files = [root / name.decode("utf-8") for name in tracked.split(b"\0") if name]
with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.write(args.report, "Group_Report.pdf")
    for label, video in videos:
        archive.write(video, f"Video_{label}.mp4")
    for file in source_files:
        if file.is_file() and not any(part in ("__pycache__", ".pytest_cache")
                                      for part in file.parts):
            archive.write(file, "source/team_repo/" + file.relative_to(root).as_posix())
print(destination)
