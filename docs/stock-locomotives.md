# Supported stock locomotives

This test edition supports only A-23, A-26, C-25, D-46, F-71, G-25, K-35, P-18, T-17 and T-22. Reading 6-Chime is excluded. The shared supported list is `stock.STEAM`; the complete historical 21-loco reference remains in `src/rr2dv/stock_locos.json`, recording identifiers, source facts, reviewed defaults, measurements and source fingerprints. Reference entries for excluded engines do not enable conversion.

The app validates this table before using it. Each record includes its evidence and basis. When installed source files do not match the recorded fingerprints, the app identifies the game build as unknown and avoids applying fingerprint-dependent measurements.

The table informs review defaults and measured geometry. User-reviewed values and source definitions remain authoritative when they disagree with a suggestion.


## Current source scope — 3 October 2026

The ten-locomotive restriction from commit `5cf87ecf18706989e451ddc780ea79ccdf6208fc` is promoted to main and the testing branch (`claude/unity-crash-message`). Source version remains `0.4.7+fixed.1`. Supported: A-23, A-26, C-25, D-46, F-71, G-25, K-35, P-18, T-17 and T-22. Reading 6-Chime is excluded. The complete stock tuning/catalogue reference is retained; its presence does not enable excluded conversions.

The published `v0.4.7` tag remains at `b5e7dfc`, before this restriction. Its existing downloads still represent the 21-locomotive edition. This integration does not rebuild or retag any release. Do not describe the restriction as shipped in v0.4.7. Earlier dated all-fleet reports below are historical evidence, not the current support list.
