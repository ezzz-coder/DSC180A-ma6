# Bikeshare demand capstone

Daily Capital Bikeshare counts, 2011-2012. We forecast `cnt` (total daily
rides) from calendar, weather, and lagged-demand features.

## Commands
- `make data` - download raw CSV and assert its shape
- `make features` - build `data/processed/features.parquet`
- `make train` - fit models, write `reports/metrics.json`
- `make test` - pytest; run this before claiming anything works
- `make all` - the three pipeline stages in order; reproduces the committed
  `reports/metrics.json` byte-for-byte (headline numbers)
- `python -m src.train --target ratio [--test]` - Exercise 4 ratio target,
  writes `reports/metrics_ratio.json`; never overwrites `metrics.json`
- Run everything from the activated `.venv`: the Makefile and the hook call
  bare `python`, and without the pinned packages the hook reports a false red

## Non-negotiable rules
- **Never** put `casual` or `registered` in a feature set:
  `casual + registered == cnt` exactly. `src/config.py` lists these and the
  other excluded columns (`cnt_2d_bfr`, raw time indexes) with the reason
  for each. Derive feature lists from `FORBIDDEN`; never hand-type them.
- A new raw column must be classified in `src/config.py` (`FORBIDDEN`,
  `RAW_FEATURE_COLS`, `SOURCE_COLS` or `UNUSED_COLS`) before it is used.
- **Never** split this data randomly. Use `src.train.temporal_split`.
  Train = 2011, valid = H1 2012, test = H2 2012. Never tune on test:
  do not print or read test metrics while iterating, and log any exposure
  in `docs/DECISIONS.md`.
- Any new lag or rolling feature must be built on a gap-free calendar
  index (`src.features.reindex_to_calendar`) and must `.shift(1)` before
  it aggregates. Add a test for it in `tests/test_leakage.py`. Write
  window lengths literally (7, 28); `LAG_WARMUP` is the longest window,
  never a lag. Raising it must not change an existing feature.
- **Never** write to `data/raw/`, from any tool including Bash. Its sha256 is
  pinned in `RAW_SHA256`; if it changes, `git checkout` it, do not re-pin.
- Report the mean baseline **and** the persistence baseline (yesterday's
  count) alongside every model. A negative R^2 is a finding, not a bug
  to hide.

## Skills
- `/new-feature <description>` - add a feature, test first.
- `/seed-fault <description>` - break `src/`, record hook + test output,
  restore, append to `docs/SEEDED_FAULTS.md`.

## Style
- Standard library, pandas, scikit-learn only. No new dependencies
  without asking. Versions are pinned in `requirements.txt`.
- Modules are runnable: `python -m src.<module>` prints a one-line `OK ...`
  summary.
- Paths and constants live in `src/config.py`. Nothing is hardcoded twice.

## Gotchas
- The mirror in `DATA_URL` is missing 2011-03-10. It is NOT the UCI file:
  728 rows from 2011-01-03, not 731 from 2011-01-01.
- `weather` uses the labels `GOOD` / `MISTY` / `BAD`, not the UCI codes 1-4.
- Ridership grew ~65% from 2011 to 2012, so tree models trained on 2011
  cannot extrapolate to 2012. That is the headline result, not an error.
- 2012-10-29 (Hurricane Sandy, 22 rides) is in the test set. Expect it in
  any residual plot.
