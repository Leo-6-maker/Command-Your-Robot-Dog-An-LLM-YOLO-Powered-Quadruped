# Task 5 integration and report review

Reviewed on **2 October 2026, Asia/Singapore** against `EE5112_MiniLab1.3 S1 AY2627.pdf`, pages 1-2 and 4-9. The official submission deadline is 4 October 2026; the supplied document does not specify the exact Canvas cut-off time.

## Integrated inputs

- `main` at `bd3c761`: teammate Task 1 PDF, preserved unchanged.
- `task3-improvements` at `00d9413`: corrected parsed `[CMD]` records, command rejection and demonstration guidance, protected fixed-batch output, fresh-frame navigation recovery and compact fixed evaluations.
- `bonus-multigoal-speech` at `0e3a66b`: depends on the improvements branch; adds local speech input, scene reset, orange-ball grounding and ordered multi-goal execution.
- Local `task5-report` integrates these inputs and revises report/packaging files. Navigation code was not changed during the new fixed batch. `environment.json` records runtime and asset hashes.

## Requirements and evidence

| Official requirement | Report location / evidence | Review status |
| --- | --- | --- |
| One group report, names and matriculation numbers, contribution split and AI declaration | Cover and section 7; source ownership map | Technical structure complete; actual fields still need team confirmation. |
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
| Three required terminal-visible videos and optional speech evidence | Section 7 media table; local recordings | Final human acceptance pending. |
| One reproducible local group ZIP with report/source/scene/prompts/videos | `prepare_submission.py` | Versioned source plus explicit local report/videos; optional `Video_Bonus.mp4` supported. Package not created while report fields and media remain unconfirmed. |

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

The package check uses temporary synthetic payloads, not the actual videos. Automated speech tests use controlled/mocked input and do not verify the physical microphone. The teammate's bonus README describes real speech/video demonstrations, but their raw media and logs were not available in this checkout. No statistical bonus success rate is claimed.

## Outstanding team information and media

| Item | Required action / available local reference |
| --- | --- |
| Group identity | Supply group index and every member's English name and matriculation number. |
| Contributions and AI use | Confirm actual Task 1-5 and bonus ownership, actual AI tools, code review and source ownership labels. |
| Video_Task2 | A historical offscreen clip exists at `../task2_runtime/task2/evidence/Video_Task2.mp4`; it does not establish final desktop-terminal acceptance. Supply/review the final clip. |
| Video_Task3 | Historical `../EE5112_MiniLab1_3_Task3_Submission/video/EE5112_MiniLab1_3_Task3_Demo.mp4` predates the corrected protocol and is not accepted as final. Supply/review the replacement. |
| Video_Task4 | Historical `task4_evidence/Video_Task4.mp4` and user clip `task4_evidence/video_clip_red_hidden_take01.mp4` remain local. Confirm which final recording covers both target demonstrations and the required log order. |
| Video_Bonus | Teammate README says microphone-audio video is held locally by that member. Obtain its local path and review `[STT]`, parsed plan, ordered execution and completion. |
| Final PDF / ZIP | Replace cover/declaration placeholders, remove the review-copy notice, rerender and visually review; then package the reviewed local media. |

Videos and ZIPs remain excluded from Git. The teammate's already-uploaded Task 1 PDF is a reference input, not an extra final group report. The single combined submission report is generated from `GROUP_REPORT_DRAFT.md`.
