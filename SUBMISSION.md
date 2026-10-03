# Group 3 submission

## Canvas: one archive

The official brief (pages 1 and 9, Task 5) requires **one** `minilab_1.3_group_3.zip`, uploaded to **Student Submission: MiniLab 1.3** on Canvas. It does not provide a GitHub-link-only option. The deadline in the brief is **4 October 2026**; check Canvas for the actual cut-off time and upload-size limit.

```text
minilab_1.3_group_3.zip
├── Group_Report.pdf
├── Video_Task2.mp4
├── Video_Task3.mp4
├── Video_Task4.mp4
├── Video_Bonus.mp4
└── source/
    └── team_repo/
        ├── README.md, dependency files and run scripts
        ├── task2/   platform, policy, robot meshes, maps and object scene
        ├── task3/   planner, schema/prompts, executor and speech input
        ├── task4.py
        ├── report_assets/
        └── evaluation evidence and report source
```

The videos and source go directly into this single archive. Separate video ZIPs or code ZIPs are unnecessary. Include only the combined final report as a PDF; individual Task 1/2/3 reference reports are not additional submitted PDFs.

## GitHub: source and reproducibility

GitHub stores source, setup/run instructions, necessary policy/YOLO weights, robot/scene assets, prompts/schema, report Markdown, figure assets and compact evaluation records. Local videos, PDF outputs, ZIPs, environment credentials, virtual environments and raw trial images stay excluded. Removing a reference PDF from the current tree does not erase earlier Git history.

Repository: [Command Your Robot Dog](https://github.com/Leo-6-maker/Command-Your-Robot-Dog-An-LLM-YOLO-Powered-Quadruped).

The repository link may be included in the report or Canvas comments as supporting information. It does **not** replace the required ZIP, report or videos unless the teaching team explicitly permits an alternative.

## Current local deliverables

| Submitted archive name | Local input | Review |
| --- | --- | --- |
| Group_Report.pdf | `GROUP_REPORT.pdf` | Combined 15-page report; Group 3 identities/contributions filled. |
| Video_Task2.mp4 | `video/Video_Task2.mp4` | Scene, RGB, move and turn completion visible in samples. |
| Video_Task3.mp4 | `video/Video_Task3_reviewed.mp4` | First 129 s of original; terminal-closing tail excluded, original preserved. |
| Video_Task4.mp4 | `video/Video_Task4.mp4` | Approximately 300 s; samples show hidden-red search and red/green FOUND/SUCCESS. |
| Video_Bonus.mp4 | `video/Video_bonus.mp4` | STT, two speech-driven plans, reset and completion visible; audio track present. |

Before uploading, play all final videos through, listen to bonus audio, verify readable terminal evidence, and have the team confirm contributions and all AI tools actually used. File presence and archive integrity are separate from full media acceptance.

## Build locally

From the repository root, after committing the source/document changes:

```powershell
py -3.12 render_group_report.py --final
py -3.12 prepare_submission.py 3 --report .\GROUP_REPORT.pdf --video-task2 .\video\Video_Task2.mp4 --video-task3 .\video\Video_Task3_reviewed.mp4 --video-task4 .\video\Video_Task4.mp4 --video-bonus .\video\Video_bonus.mp4
```

Output: `..\minilab_1.3_group_3.zip`. The packager includes Git-tracked source and explicitly supplied report/videos, rejects identity placeholders and missing files, excludes extra PDFs/archives/media/`.env` from the source tree, and refuses to overwrite an existing ZIP. Preserve or rename an old archive before rebuilding.

Upload that archive to Canvas. Keep the final ZIP and a copy of the Canvas submission receipt locally.
