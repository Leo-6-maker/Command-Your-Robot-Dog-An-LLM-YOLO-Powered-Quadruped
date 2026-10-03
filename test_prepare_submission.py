"""The Canvas package accepts only a reviewed PDF and versioned source."""

from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import fitz


def test_reviewed_package_and_optional_bonus(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    script = repo / "prepare_submission.py"
    shutil.copy(Path(__file__).resolve().parent / script.name, script)
    (repo / "chapter.md").write_text("[TEAM TO FILL] reference template")
    (repo / "untracked.zip").write_bytes(b"exclude this local archive")
    (repo / "local_clip.mp4").write_bytes(b"exclude this local clip")
    for name in ("reference.pdf", "old.zip", "tracked_clip.mp4", ".env"):
        (repo / name).write_bytes(b"exclude even if tracked")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "add", "prepare_submission.py", "chapter.md"], cwd=repo, check=True)
    subprocess.run(["git", "add", "reference.pdf", "old.zip", "tracked_clip.mp4", ".env"],
                   cwd=repo, check=True)
    videos = []
    for name in ("task2", "task3", "task4", "bonus"):
        path = tmp_path / f"{name}.mp4"
        path.write_bytes(b"test video payload")
        videos.extend([f"--video-{name}", str(path)])
    pdf = tmp_path / "report.pdf"

    def write_pdf(text):
        with fitz.open() as report:
            report.new_page().insert_text((72, 72), text)
            report.save(pdf)

    command = [sys.executable, str(script), "1", "--report", str(pdf), *videos]
    write_pdf("[TEAM TO FILL]")
    rejected = subprocess.run(command, capture_output=True, text=True)
    assert rejected.returncode != 0 and "placeholders" in rejected.stderr
    assert not (tmp_path / "minilab_1.3_group_1.zip").exists()

    write_pdf("Reviewed group report: identities and contributions confirmed.")
    subprocess.run(command, check=True, capture_output=True)
    with zipfile.ZipFile(tmp_path / "minilab_1.3_group_1.zip") as archive:
        names = set(archive.namelist())
        assert names == {
            "Group_Report.pdf", "Video_Task2.mp4", "Video_Task3.mp4",
            "Video_Task4.mp4", "Video_Bonus.mp4",
            "source/team_repo/prepare_submission.py", "source/team_repo/chapter.md",
        }
    overwrite = subprocess.run(command, capture_output=True, text=True)
    assert overwrite.returncode != 0 and "already exists" in overwrite.stderr
