# Focused calibration before final ten trials

The same controller version passed the two previously troublesome starts:

| Start / target | C1/C3 | Independent final d | Contacts |
|---|---|---:|---:|
| (0.5, 1, 0°) / green chair | `[FOUND]`, success | 0.758 m | 0 |
| (1, -1, 180°) / red chair, initially hidden | `[SEARCH]`, `[FOUND]`, success | 0.752 m | 0 |

Full logs, `result.json` and onboard images are retained. These two trials
were used to select a controller change; they are excluded from the later
ten-trial success-rate denominator.
