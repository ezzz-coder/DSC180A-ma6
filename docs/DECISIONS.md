# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.
- 2026-11-25 Add `cnt_roll_28` (mean cnt over the 28 days before d; all inputs known before d). LAG_WARMUP 7 -> 28, train rows 348 -> 306. Valid R^2 ridge 0.6475 -> 0.6839 (+0.036), hgb 0.2185 -> 0.2415 (+0.023); on identical 306 train rows the feature alone adds +0.038 / +0.049. Keep. Decoupled cnt_lag_7/cnt_roll_7 windows from LAG_WARMUP so they stay 7-day.
- 2026-11-25 Add `RAW_SHA256` + `test_raw_file_is_unmodified`: fault 4 showed a Bash `cp` over data/raw/ bypasses the Edit/Write deny rules and the hook, and identity-preserving edits pass every other test. Checksum fails on any byte change. No effect on metrics.
- 2026-11-25 Test-set exposure: the starter's baseline test numbers were seen at setup (identical to the spec page), and the `agent/audit.py` run printed post-`cnt_roll_28` test numbers (ridge test R^2 0.6239, MAE 879.3). Seen after `cnt_roll_28` was chosen on validation; no feature, parameter or decision was chosen from them. The starter line "Test set touched once" is superseded by this one.
