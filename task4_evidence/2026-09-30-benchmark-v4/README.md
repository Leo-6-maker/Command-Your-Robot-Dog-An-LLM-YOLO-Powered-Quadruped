# Interrupted near-object calibration

This run was stopped after trial 03 reproduced a target-loss regression:
the chair stayed large in the image, but continued small turns eventually
removed it from view. Trials 01, 02, 03 and 04 have complete receipts;
trial 05 has only partial files from when the run was stopped. This is not a
ten-trial evaluation and must not be combined with other code versions.

The next controller revision stops turning once a sufficiently large live
matching chair box is in view, then checks C1/C2/C3 at the stop. Trial 03
and the hidden red target were rerun as focused calibration before another
fixed ten-trial run.
