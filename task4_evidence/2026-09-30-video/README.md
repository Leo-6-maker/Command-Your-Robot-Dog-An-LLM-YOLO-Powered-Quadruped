# Task 4 desktop video receipt

`../Video_Task4.mp4` is the successful red-hidden GUI mission followed by the
successful green-chair GUI mission, joined without altering the source frames.
It is 1920 × 1080, 8 fps, 835 frames (104.375 s), H.264, with the live MuJoCo
browser and actual interactive Task 3 terminal visible throughout.

The original terminal output is retained as `red_hidden.log` and
`green_aligned.log`. Both calls used the real `deepseek-chat` planner through
Task 3's validator and executor. Red was requested from `(1, -1, 180°)` and
found at 0.74 m after search; green was requested from `(1, 1, 0°)` and found
at 0.75 m. The source desktop clips were `video_clip_red_hidden_04.mp4`
(530 frames) and `video_clip_green_aligned_02.mp4` (305 frames). They were
concatenated in that order with ffmpeg's concat demuxer and `-c copy`.

SHA-256 of `../Video_Task4.mp4`:
`389d013fb9188b0d7f505b6fd341db8c09a7ff3d9710b48597862ed7ed441058`.

Earlier local recording attempts that did not complete C1–C3 remain separate
from this submitted video and are excluded from its success claim. The fixed
ten-trial rate is reported in `../2026-09-30-benchmark-v7/`, independently
of which demonstrations were selected for this video.
