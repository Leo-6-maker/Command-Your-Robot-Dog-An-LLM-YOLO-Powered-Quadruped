# Step 15 — Task 3 desktop-video script

Status: recording setup prepared; do not mark Step 15 complete until the saved video is checked.

## Required visible evidence

- Keep the real terminal and MuJoCo GUI visible side by side.
- Type every robot request in English in the terminal.
- Keep each `[CMD]`, `[LLM]`, `[PLAN]`, `[EXEC]`, and final `[DONE]` line visible long enough to read.
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
- Every English input has one `[CMD]` line and ends in a visible `[DONE]` line.
- Robot movement is visible for all four accepted commands.
- The poem request is visibly rejected and causes no motion.
- No API key, billing page, unrelated notification, or private information is visible.
- The video plays from beginning to end and its file size is non-zero.
