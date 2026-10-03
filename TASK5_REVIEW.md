# Task 5 integration and report review

Requirements reviewed on **2 October 2026**; formal report and supplied video spot-check updated on **3 October 2026, Asia/Singapore** against `EE5112_MiniLab1.3 S1 AY2627.pdf`, pages 1-2 and 4-9. The official submission deadline is 4 October 2026; the supplied document does not specify the exact Canvas cut-off time.

## Integrated inputs

- `main` at `bd3c761`: teammate Task 1 PDF; subsequently retained locally and removed from Git tracking during final repository cleanup.
- `task3-improvements` at `00d9413`: corrected parsed `[CMD]` records, command rejection and demonstration guidance, protected fixed-batch output, fresh-frame navigation recovery and compact fixed evaluations.
- `bonus-multigoal-speech` at `0e3a66b`: depends on the improvements branch; adds local speech input, scene reset, orange-ball grounding and ordered multi-goal execution.
- Local `task5-report` integrates these inputs and revises report/packaging files. Navigation code was not changed during the new fixed batch. `environment.json` records runtime and asset hashes.

## Requirements and evidence

| Official requirement | Report location / evidence | Review status |
| --- | --- | --- |
| One group report, names and matriculation numbers, contribution split and AI declaration | Cover and section 7; source ownership map | Group 3, names, matriculation numbers and contributions supplied by the user; incorporated in the formal report and principal source-module headers. |
| Self-description of all five tasks | Section 1 task table; sections 2-7 | Included. |
| At least three language-to-robot approaches, including structured parsing and two named alternatives; output/cost/latency/use cases | Section 2: structured output, SayCan, Code as Policies; primary references | Included. Generic layered planning in the teammate PDF was supplemented rather than counted as a required named alternative. |
| Learned policy, sim-to-sim/sim-to-real and two-rate explanation | Sections 2 and 3; labelled command/observation/history/policy/remap/PD chain | Included; no claim of new training or physical deployment. |
| Native/browser, keyboard, three maps and three onboard cameras | Task 2 development report; section 3 | Historical development checks cited; not newly repeated here. |
| Camera rate, detectable scene with 3 objects / 2 COCO classes and two colours; screenshot | Section 3, Figure 1, scene/objects files | Included. |
| Timed move, actual-yaw turn and open-loop comparison | Section 3 and `task2/evidence/turn_comparison.csv` | Six rows checked; completion and later settling errors distinguished. |
| LLM parser, multi-step and paraphrase support, rejection, context, autonomous sequential execution | Section 4; planner/schema/validator/chat/executor source | Reviewed; context is the previous successful plan, not an unlimited transcript. |
| At least 20 utterances, 5 paraphrases and 5 invalid cases, two services, accuracy/latency/cost per call and failures | Section 4; `task3/evidence/step13_benchmark_results.json` | Recomputed 15/20 OpenAI and 16/20 Qwen; recorded latency and token-cost totals agree. |
| Camera-only navigation; exact C1-C3 and no-contact condition; ten varied starts and targets | Section 5; `task4_evidence/2026-10-02-task5-0e3a66b/` | New complete ten-trial batch; 8 successes, 8 mission C1 matches, 8 confirmed groundings, 0 contact trials. |
| Platform/version/dependencies/install/run commands, keys, scene and prompt paths | Section 7, root README and batch environment receipt | Included; API keys supplied only by environment. |
| Three required terminal-visible videos and optional speech evidence | Section 7 media table; local recordings | All four videos supplied locally and visually spot-checked; Task 3 closing tail removed in a separate reviewed copy. Final full playback/audio confirmation pending. |
| One reproducible local group ZIP with report/source/scene/prompts/videos | `prepare_submission.py` | Versioned source plus explicit local report/videos; optional `Video_Bonus.mp4` supported. All inputs available; local package built and checked after final source commit. Full playback/audio confirmation remains a team action before upload. |

## Verified measurements

The original parser data is dated 29 September 2026 and measures independent planner requests, not robot motion or the expanded bonus prompt. Its OpenAI cost is an estimate using recorded prices, not a new billing measurement. New API calls were not made for this review.

The older `d6f0c7b` navigation batch achieved 8/10 success and 9/10 mission C1 matches. The new Windows `0e3a66b` batch independently achieved 8/10 success and 8/10 mission C1 matches. Trials 03 and 07 failed the green-chair fresh stopped-frame check despite distances of 0.734 and 0.724 m. Five requested targets were initially undetected; hidden red trial 08 succeeded. No failed trial was retried or replaced in the batch.

The extra independently rendered post-mission frames match the target in 7/10 trials. Successful trial 01 loses the later detection, but offline inference on its saved last controller frame reproduces the logged green-chair boxes. Thus the mission C1 measure and the later frame measure are not interchangeable. `frame_review.json` records the offline figure checks. Raw trial frames remain in ignored `runs/2026-10-02-task5-0e3a66b/`; only two report figures and compact receipts are versioned.

Commands executed for this review:

```powershell
.\.venv\Scripts\python.exe -m pytest -q task3 task2/task2/test_skills.py
# 142 passed: 136 Task 3/4 checks + 6 Task 2 skill checks
.\.venv\Scripts\python.exe -u run_task4_benchmark.py runs\2026-10-02-task5-0e3a66b
.\.venv\Scripts\python.exe summarize_task4_benchmark.py runs\2026-10-02-task5-0e3a66b
.\.venv\Scripts\python.exe -m pytest -q test_prepare_submission.py
# 1 passed: placeholder rejection, optional bonus, tracked source selection and no overwrite
.\.venv\Scripts\python.exe -m pytest -q task3 task2/task2/test_skills.py test_prepare_submission.py
# Final combined check: 143 passed
py -3.12 render_group_report.py
```

The generated combined report has 15 pages. All rendered pages were visually reviewed: the ten-trial table stays on one page, both figures stay with their captions, references fit on the final page, and no text or figures overlap or extend outside the margins. The main text uses Times New Roman 12 pt with 1.5 spacing and one-inch margins; tables and code use smaller text for readability.

The package check uses temporary synthetic payloads, not the actual videos. Automated speech tests use controlled/mocked input and do not verify the physical microphone. The bonus video is now available locally; visible samples confirm two STT transcriptions, ordered plans, reset and successful completion. An AAC audio stream is present, but this review has not independently listened to the spoken audio or checked a separate raw log. No statistical bonus success rate is claimed.

## Supplied identities and current media

The user supplied Group 3 and the following contribution declaration in the edited report: SIYUAN WU (A0352422N), Task 1/2; ZIYAN WANG (A0352514L), Task 3, Task 4 optimisation and bonus; YU LIU (A0350716H), Task 4, integration/evaluation and group report. These entries were preserved. The AI declaration states OpenAI Codex; team members should add any other tools actually used.

| Item | Current status / required final action |
| --- | --- |
| Video_Task2 | `video/Video_Task2.mp4`, 22.1 s, 1280 x 672 at 10 fps, no audio track. Visual samples show the object scene, front RGB, 3 s move, 180-degree turn and `[TURN] final_error=1.93 deg status=SUCCESS`. It is a rendered scene with a visible log strip. |
| Video_Task3 | `video/Video_Task3.mp4`, 133.0 s, 2560 x 1440 at 30 fps, no audio track. Samples show context-based requests, a move/45-degree-turn two-action plan and rejection. The terminal closes around 131 s. A separate `video/Video_Task3_reviewed.mp4` preserves the first 129 s without re-encoding; original retained. Use the reviewed copy and play it through before final packaging. |
| Video_Bonus | `video/Video_bonus.mp4`, 150.0 s, 1920 x 1080 at 30 fps, AAC stereo audio. Samples at 30 and 96 s show STT and two-/four-action plans; final samples show green-chair FOUND, turn, timed move and DONE success. Listen to ensure the microphone contains intelligible English; two examples are not a statistical success-rate study. |
| Video_Task4 | `video/Video_Task4.mp4`, 299.9 s at 1920 x 1080. Visual samples show hidden-target search, red-chair FOUND at 0.79 m and green-chair FOUND at 0.76 m, both MISSION/DONE success; terminal and dual views remain visible in samples. Full playback still required. |
| Formal report | `GROUP_REPORT_DRAFT.md` is the editing source; `py -3.12 render_group_report.py --final` generates `GROUP_REPORT.pdf` and `.html`. Cover fields filled, review-copy notice removed, ownership linked to named members, 143-check total corrected. Task 4 recording now supplied; full media playback remains required before Canvas upload. |
| AI declaration | OpenAI Codex is declared for implementation, debugging, analysis, integration and report editing. Add other tools if teammates used them; do not invent tools. |
| Final archive | See `SUBMISSION.md` for the one-archive layout and Group 3 packaging command; upload only after full playback and team approval of declarations. The script refuses to overwrite an existing archive. |

Source ownership is marked in `task2/task2/__init__.py`, `task3/__init__.py` and `task4.py`; changes only add contributor information and do not change controller logic. Videos and ZIPs remain excluded from Git. The teammate's Task 1 PDF is preserved locally and removed from current Git tracking; the combined report is the only PDF in the submission ZIP. The formal report records experiments by their original runtime and dates; the supplied videos do not replace the fixed ten-trial navigation batch.

The formal PDF was regenerated and all 15 rendered pages visually checked on 3 October 2026. The ten-trial table and figure captions remain intact, with no clipped content or overlapping text. Draft-named PDF/HTML previews were refreshed to the same content for the existing IDE tabs. The reviewed Task 3 copy is 129.0 s; its final frame retains the terminal, accepted two-action completion and subsequent rejection.
