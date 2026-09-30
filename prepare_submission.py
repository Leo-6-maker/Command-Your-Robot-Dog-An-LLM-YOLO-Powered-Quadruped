"""Package the reviewed group report, three videos, source, and current evidence."""

import argparse
from pathlib import Path
import zipfile

import fitz


root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("group_index", type=int)
parser.add_argument("--report", type=Path, required=True)
parser.add_argument("--video-task2", type=Path, required=True)
parser.add_argument("--video-task3", type=Path, required=True)
parser.add_argument("--video-task4", type=Path, required=True)
args = parser.parse_args()
if args.group_index < 1:
    parser.error("group_index must be positive")
for file in (args.report, args.video_task2, args.video_task3, args.video_task4):
    if not file.is_file():
        parser.error(f"missing file: {file}")
with fitz.open(args.report) as report:
    report_text = "\n".join(page.get_text() for page in report)
    if any(marker in report_text for marker in (
        "[TEAM TO FILL]", "[Student A]", "[Student B]", "[Student C]",
        "[insert actual", "[Review and fill", "[Each member must",
    )):
        parser.error("report still contains team identity or contribution placeholders")

destination = root.parent / f"minilab_1.3_group_{args.group_index}.zip"
if destination.exists():
    parser.error(f"package already exists: {destination}")
source_files = [
    *root.glob("*.py"), *root.glob("*.ps1"), *root.glob("*.md"),
    root / ".gitignore",
    *root.joinpath("task2").rglob("*"),
    *root.joinpath("task3").rglob("*"),
    *root.joinpath("report_assets").rglob("*"),
    *root.joinpath("task4_evidence/2026-09-30-benchmark-v8").rglob("*"),
]
with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.write(args.report, "Group_Report.pdf")
    for number, video in ((2, args.video_task2), (3, args.video_task3),
                          (4, args.video_task4)):
        archive.write(video, f"Video_Task{number}.mp4")
    for file in source_files:
        if file.is_file() and not any(part in ("__pycache__", ".pytest_cache")
                                      for part in file.parts):
            archive.write(file, "source/team_repo/" + file.relative_to(root).as_posix())
print(destination)
