# Windows Task 3 end-to-end multi-step receipt

> Historical note: this receipt predates the 2026-10-02 course-log correction and therefore uses
> `[CMD]` for raw input text. The current runtime uses `[INPUT]` for raw text and `[CMD]` only for
> parsed actions or a stable rejection reason. This receipt must not be used as final video proof.

On 2026-09-30, the integrated `task3.run` headless entry point used the real DeepSeek `deepseek-chat` planner, Task 2 scene and motion skills. The typed English command was:

> Move forward at speed 0.4 for one second, then turn left 45 degrees.

The terminal printed `accepted=true actions=2`, `[EXEC] step=1/2 type=move`, `[MOVE] completed duration=1.00`, `[EXEC] step=2/2 type=turn angle_deg=45.00`, `[TURN] target=45.0 deg final_error=1.92 deg status=SUCCESS`, and `[DONE] status=SUCCESS actions=2`. A second typed request, `Write a poem about robot dogs.`, produced `[DONE] status=REJECTED actions=0`. The raw log is `task3/evidence/windows_multistep_receipt.log`; no API key was printed.

This verifies the software path but does not substitute for the required terminal-visible Video_Task3. Re-record that video with the same two-action command and a rejected request.
