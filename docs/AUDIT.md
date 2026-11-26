# Audit (Exercise 3)

## Teammate repo: `/leakage-auditor`

- Repo: https://github.com/lukkrim/bikeshare-open
- Audited: diff `8554787` (their unmodified starter) .. `3ace5e2` (HEAD on 2026-11-25),
  `src/`, `tests/`, `Makefile`
- Auditor: `.claude/agents/leakage-auditor.md` from this repo, unmodified,
  model `inherit` = Claude Opus 5.5 (hosted). It read and ran their code with
  the pinned packages; it modified no files (`git status` clean afterwards).

### Auditor output (verbatim)

> All five checks pass for the diff 8554787..3ace5e2 in /Users/edward/Desktop/UCSD/FA26/DSC180A/ma6/samson-repo/bikeshare-open, so there are no findings. I checked each one by running their code with the pinned venv, and no files in either repo were changed:
>
> - **Target leakage:** the 15 features include no forbidden column and nothing calculated from `cnt` on the same day.
> - **Temporal ordering:** `cnt_roll_7` and `cnt_roll_28` both shift by one day before averaging, and `cnt_lag_7` now uses `WEEK`, not `LAG_WARMUP`. The split is by date (306/182/184 rows), and the scaler sits inside the ridge pipeline, which is fitted on 2011 only.
> - **Calendar gaps:** lags and rolling means are built after filling in every calendar day. Their tests compare every row against the raw counts by date.
> - **Silent row loss:** 56 rows are dropped, exactly the tested bound (28 warm-up days plus 28 after the missing 2011-03-10). An unknown weather label raises an error instead of being dropped.
> - **Baselines:** `reports/metrics.json` reports both the mean and the persistence baseline next to every model, and the numbers reproduce exactly.
>
> I also reran the ridge-vs-persistence bootstrap. On validation I got their interval exactly. On test I got [+0.012, +0.248] against their [+0.003, +0.259]; it excludes 0 either way, including with 7-day blocks, so their conclusion holds.

### My verdict

I agree with all five of the auditor's passes. I confirmed the ones I could
check by reading their code: `cnt_lag_7`, `cnt_roll_7` and `cnt_roll_28` are
built with `shift(WEEK)` / `shift(1).rolling(...)` after `reindex_to_calendar`;
the split in `src/train.py:56-63` is by `TRAIN_END` / `VALID_END` dates; the
feature set is filtered through `FORBIDDEN`. The claim that `metrics.json`
reproduces exactly is the auditor's; I did not rerun their pipeline myself. I
add one finding the auditor surfaced but did not flag, because it changes a
reported number: the paired-bootstrap interval for ridge minus persistence on
test (DECISIONS.md, "Audit fix 1": `[+0.003, +0.259]`, "2000 resamples,
seed 0") cannot be regenerated from the repo, since no bootstrap code is
committed anywhere in `src/`, `tests/` or the `Makefile`. An independent
re-implementation gave `[+0.012, +0.248]`. Their conclusion survives (both
intervals exclude 0), but it rests on a lower bound of +0.003, so how the
interval was computed decides whether ridge's edge is "just" significant.
Minimal fix: commit the bootstrap as a script or a `make` target and cite
its output. Nothing else in their diff changes a number.

## Own repo: `agent/audit.py`

`reports/audit.jsonl`: `AUDIT_MODEL=claude-opus-5-5 python agent/audit.py . --out reports/audit.jsonl`
on 2026-11-25. Leakage none, 0 flagged; its five findings are addressed in REPORT.md.
