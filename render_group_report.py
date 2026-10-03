"""Render the editable group report draft to PDF on Windows with Edge/Chrome."""

import argparse
from pathlib import Path
import subprocess
import tempfile

import fitz
import markdown


root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--final", action="store_true", help="write GROUP_REPORT.html and GROUP_REPORT.pdf")
args = parser.parse_args()
source = root / "GROUP_REPORT_DRAFT.md"
stem = "GROUP_REPORT" if args.final else "GROUP_REPORT_DRAFT"
html_path = root / f"{stem}.html"
pdf_path = root / f"{stem}.pdf"
browser = next((path for path in (
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
) if path.exists()), None)
if browser is None:
    raise SystemExit("Edge or Chrome is required to render the report PDF")

report = source.read_text(encoding="utf-8").lstrip("\ufeff")
report = report.replace(
    "```mermaid\nflowchart LR\n A[Motion queue / keyboard] --> B[46-D observation x 6 frames] --> C[ONNX 50 Hz] --> D[Rear-leg remap] --> E[PD 200 Hz] --> F[MuJoCo] --> B\n```",
    '<div class="pipeline">Motion queue / keyboard &rarr; 46-D observation &times; 6 frames &rarr; ONNX policy (50 Hz) &rarr; Rear-leg remap &rarr; PD control (200 Hz) &rarr; MuJoCo &rarr; observation</div>',
)
body = markdown.markdown(report, extensions=["tables", "fenced_code"])
css = """@page {size:A4; margin:1in}
body{font-family:'Times New Roman',serif;font-size:12pt;line-height:1.5;color:#111}
h1{font-size:17pt;line-height:1.2;margin:18pt 0 10pt}
h2{font-size:14pt;line-height:1.2;margin:14pt 0 7pt}
h1,h2,h3{break-after:avoid} .pagebreak{break-after:page}
h3{font-size:12pt} p{margin:0 0 8pt}
table{border-collapse:collapse;width:100%;font-size:10pt;line-height:1.2;margin:9pt 0;break-inside:avoid}
th,td{border:1px solid #777;padding:3pt 4pt;vertical-align:top}
img{max-width:100%;max-height:2.8in;display:block;margin:auto}
.figure{break-inside:avoid} .figure-pair{display:flex;gap:8pt;break-inside:avoid}
.figure-pair img{width:48%;height:2.2in;object-fit:contain}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:9pt;line-height:1.2}
code{overflow-wrap:anywhere} .pipeline{border:1px solid #555;padding:8pt;text-align:center;font-size:10pt;line-height:1.5}
blockquote{border-left:3px solid #999;margin:8pt 0;padding:4pt 10pt}
tr{break-inside:avoid}"""
html_path.write_text(
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    + css + "</style></head><body>" + body + "</body></html>", encoding="utf-8"
)
with tempfile.TemporaryDirectory(prefix="ee5112_report_") as profile:
    rendered_pdf = Path(profile) / "report.pdf"
    subprocess.run([
        str(browser), "--headless=new", "--disable-gpu", "--no-sandbox",
        f"--user-data-dir={profile}", "--no-pdf-header-footer",
        f"--print-to-pdf={rendered_pdf}", html_path.as_uri(),
    ], check=True, capture_output=True, timeout=60)
    if not rendered_pdf.is_file():
        raise SystemExit("Browser did not produce the report PDF")
    with fitz.open(rendered_pdf) as report_pdf:
        for index, page in enumerate(report_pdf, start=1):
            page.insert_textbox(
                fitz.Rect(72, page.rect.height - 48, page.rect.width - 72, page.rect.height - 28),
                f"EE5112 MiniLab 1.3 | {index} / {len(report_pdf)}",
                fontsize=9, fontname="tiro", align=1,
            )
        report_pdf.set_metadata({"title": "EE5112 MiniLab 1.3 - Group Report"})
        report_pdf.save(pdf_path)
print(pdf_path)
