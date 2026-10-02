# Step 15 — Task 3 desktop-video script

Status: **replacement required after the 2026-10-02 log-protocol correction**. The previous
recording was technically valid but used `[CMD]` for raw input text. It is retained only as a
superseded artifact and must not be submitted as the final Task 3 video.

## Superseded artifact

- Submission file: `EE5112_MiniLab1_3_Task3_Demo.mp4`
- Saved at: `/home/ziyan/Videos/Screencasts/EE5112_MiniLab1_3_Task3_Demo.mp4`
- Source retained: `Screencast From 2026-09-30 00-18-54.webm`
- Video: H.264 (`avc1`), 1920x1080, 30 FPS, `yuv420p`
- Duration: 95.8 seconds
- Size: 8,631,630 bytes
- Audio: none (the demonstration evidence is terminal text and simulator video)
- SHA-256: `60286cd75e30b259b027c979f05546675a1a5cb6f65f1b407d9fe5bb06c28d0c`

## Required visible evidence

- Keep the real terminal and MuJoCo GUI visible side by side.
- Type every robot request in English in the terminal.
- Keep each `[INPUT]`, `[LLM]`, parsed `[CMD]`, `[PLAN]`, `[EXEC]`, and final `[DONE]` line visible long enough to read.
- Show successful movement, turning, a multi-turn context command, and one rejected request.
- Do not expose an API key or the external key file.

The prepared demo uses local `qwen2.5:7b`, so no key or paid API request appears in the recording.

## Recording order

Start the GNOME desktop recorder only after the terminal shows `[CHAT] event=READY` and the browser shows `SIM LIVE`. Enter one command at a time and wait for `[DONE]` before continuing.

1. Explicit forward motion:

   ```text
   Move forward at speed 0.6 for two seconds.
   ```

2. Successful-context reference:

   ```text
   Do that again, but slower.
   ```

3. Closed-loop turn:

   ```text
   Turn left 90 degrees.
   ```

4. Lateral direction/sign demonstration (the stronger two-second command is easier to see):

   ```text
   Move left at speed 0.4 for two seconds.
   ```

5. Required rejection example:

   ```text
   Write a poem about robot dogs.
   ```

   The correct ending is `[DONE] status=REJECTED`; no `[EXEC]` action should follow this plan.

6. End the chat cleanly:

   ```text
   /quit
   ```

Stop the desktop recorder after `[CHAT] event=CLOSED` and `[RUNTIME] event=STOP` are visible.

## GNOME recorder

Use `Ctrl+Alt+Shift+R` to start recording the desktop and use the same shortcut to stop. If the shortcut is disabled on this GNOME installation, press `Print Screen`, switch to video recording, select the full screen, and start recording from the screenshot overlay.

## Acceptance check after recording

- Both windows remain readable at normal playback size.
- Every English input has one `[INPUT]` line, one parsed/rejected `[CMD]` line and a visible `[DONE]` line.
- Accepted commands show `[CMD] actions=... n=...`; the rejected request shows `[CMD] rejected reason=...`.
- Robot movement is visible for all four accepted commands.
- The poem request is visibly rejected and causes no motion.
- No API key, billing page, unrelated notification, or private information is visible.
- The video plays from beginning to end and its file size is non-zero.
