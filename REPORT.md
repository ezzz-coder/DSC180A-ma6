# Bikeshare demand: report

## Results

Validation = H1 2012 (182 days), unchanged by the feature. "Before" is the
starter pipeline (14 features, 348 train rows); "after" adds `cnt_roll_28`
(15 features, 306 train rows, `LAG_WARMUP` 28). "After" rows are
`reports/metrics.json` from `make clean && make all` on the final code
(reproduced byte-for-byte). "Before" rows are the unmodified starter, whose
test numbers match the published reference. Post-feature test columns were
scored once, in the final run, after all feature and transformation choices
were fixed (see DECISIONS.md for every point at which test numbers were seen).

| model | features | valid R² | valid MAE | test R² | test MAE |
|---|---|---|---|---|---|
| baseline_mean | before | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_persistence | before | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | before | 0.6475 | 832.9 | 0.5833 | 947.1 |
| hgb | before | 0.2185 | 1296.6 | -0.4975 | 1972.6 |
| baseline_mean | after | -0.6894 | 1877.3 | -1.7717 | 2659.6 |
| baseline_persistence | after | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | after | 0.6839 | 777.5 | 0.6239 | 879.3 |
| hgb | after | 0.2415 | 1296.6 | -0.46 | 1952.4 |

The mean baseline moves only because dropping January 2011 raises the training
mean. On identical training rows, `cnt_roll_28` alone moves ridge valid R²
0.6462 -> 0.6839 and hgb 0.1929 -> 0.2415.

### Batch audit of this repo

`agent/audit.py` (Claude Opus 5.5, `reports/audit.jsonl`) found no leakage and
flagged nothing. It listed five findings, none fixed:
(1) `test_beats_the_mean_baseline` gates `make test` on test-set R² > 0.4. It
rejected nothing during this work, since every change was chosen on validation.
It stays as a starter test, and its use of test is disclosed here.
(2) Weather features are same-day observations: accepted. Model scores are an
upper bound under perfect weather knowledge, which is the core of Exercise 5.
(3) `test_rolling_mean_excludes_today` checks one row inside an `if`: accepted
as a known weakness (see docs/SEEDED_FAULTS.md, fault 2). `cnt_roll_28` has its
own exact-value test.
(4) DECISIONS.md quotes ridge 0.583: that is the starter's line, which the
assignment requires keeping; later lines supersede it.
(5) The Makefile uses bare `python`: reproduction assumes the activated `.venv`,
as the README says.

## Headline finding

A tree model trained on 2011 cannot forecast 2012. Ridership grew ~65%, and a
gradient-boosted tree can only predict values it saw in training, so raw hgb
scores test R² -0.46 (MAE 1952) with a bias of -1783 rides a day: worse than
yesterday's count (persistence, R² 0.5099, MAE 840.1) and barely better than
the 2011 mean (R² -1.77). Ridge, whose lag coefficients scale with the level,
reaches test R² 0.6239 but loses to persistence on MAE (879.3 against 840.1),
because it inherits a -427 bias from its training year. Modelling relative
demand (`cnt / cnt_roll_28`) removes that bias for the tree and makes it the
best model on test (R² 0.6392, MAE 744.2, bias +21), so the problem was the
target's level, not the model class. The added feature, `cnt_roll_28`, raised
ridge's validation R² from 0.6475 to 0.6839 (+0.036, chosen on validation; test
0.5833 -> 0.6239).

## Exercise 4: target transformation

**Diagnosis (validation).** Ridge beats gradient boosting because ridership
grew ~65% from 2011 to 2012 and a tree cannot predict outside the range of its
training targets. 71 of the 182 validation days exceed the busiest day of 2011
(6043); hgb never predicts above 5639 and under-predicts by 1204 rides a day on
average. Ridge, whose lag coefficients scale with the level, reaches 7145 with
a bias of -396.

**Transformation.** Fit on relative demand, `cnt / cnt_roll_28`, and multiply
the prediction back by `cnt_roll_28` (`RatioTarget` in `src/train.py`, run with
`python -m src.train --target ratio`). The baselines are not transformed. The
ratio is close to stationary across years: 0.15-2.00 in 2011 training,
0.17-1.85 in H1 2012 validation, so the tree now interpolates instead of
extrapolating.

| model | target | valid R² | valid MAE | valid bias | test R² | test MAE |
|---|---|---|---|---|---|---|
| ridge | raw | 0.6839 | 777.5 | -396 | 0.6239 | 879.3 |
| ridge | ratio | 0.4039 | 1069.0 | -862 | -0.5069 | 1844.7 |
| hgb | raw | 0.2415 | 1296.6 | -1204 | -0.46 | 1952.4 |
| hgb | ratio | 0.6754 | 732.4 | +53 | 0.6392 | 744.2 |
| persistence | — | 0.4507 | 900.6 | -18 | 0.5099 | 840.1 |

With the ratio, hgb competes: within 0.01 R² of raw ridge, and better on MAE.
The transformation does not help every model: ridge gets worse, because its
lag features stay in raw counts and a linear model cannot learn the division
that converts them to a ratio. The fair comparison is each model on the target
that suits it: hgb on the ratio against ridge on the raw count.

**Defensible, not just a way to win.** Every input is known before the day:
`cnt_roll_28` is built with `shift(1).rolling(28)` on the calendar index and
tested in `tests/test_leakage.py`. It uses no forbidden column and no time
index, and it was chosen on validation only. It also has a reason beyond the
score: relative demand (a Saturday versus the recent level) carries over to
a busier year in a way absolute demand does not. The cost is that it leans on
the recent level, so it will lag sudden shifts. Hurricane Sandy (2012-10-29)
and the days after it are in the test set, which is where that shows.

**Test set.** Scored once, at the end, after all feature and transformation
choices were fixed (`python -m src.train --target ratio --test`, written to
`reports/metrics_ratio.json`). The validation result held: ratio hgb reaches
test R² 0.6392 / MAE 744.2 with bias +21, ahead of raw ridge (0.6239 / 879.3,
bias -427) and of persistence (0.5099 / 840.1). Raw hgb's test bias is -1783.
The expected weakness also showed: on Hurricane Sandy (2012-10-29, 22 rides) the
ratio model predicted 3630, no better than anything else, because a
28-day level cannot see a storm coming.

## Exercise 5: ridge vs persistence

Ridge is not worth deploying over "yesterday again" as it stands. Its
advantage is real on paper but concentrated on exactly the days it cannot
honestly claim. On validation, ridge's MAE is 777.5 against persistence's 900.6
(paired bootstrap of the difference: +123, 95% CI [+22, +235]). On a typical day,
though, it is no better: median error 665 against 638, closer on only 52% of
days. The whole gain comes from the days when yesterday is a bad guide. On
persistence's worst 10% of days ridge's MAE is 1608 against 2904, and it is off
by more than 2000 rides on 6 days against 18. Those are weather shocks and
holiday rebounds, and ridge sees same-day *observed* weather (temp, hum,
windspeed, weather_severity), which a deployed forecast would only have as a
forecast. So the days that make its R² look good are an upper bound under
perfect weather knowledge. Meanwhile it carries a bias that persistence does
not: anchored to its 2011 training year, it under-predicts by 396 rides a day
on validation (persistence: -18). That bias grows with distance from training,
and on test (H2 2012) it is -427 against persistence's +16. That is why
ridge's R² edge on test (0.6239 against 0.5099) comes with an MAE loss (879.3
against 840.1). On test, ridge's median error is 806 against 506, it is closer
on only 43% of days, and the MAE difference has a 95% CI of [-145, +70], which
includes zero. It still wins on persistence's worst 10% of days (1751 against 2909). Persistence is free, unbiased
and needs no upkeep. Ridge would be worth revisiting only if it were retrained
with forecast weather and recalibrated on recent data, and it still beat
persistence after that.

## Attribution

Claude Opus 5.5 (hosted, via Claude Code), not the local Ollama `bikeshare-coder`; one model throughout, no switch.

**Agent-generated:**
- the `cnt_roll_28` code and its three tests, through `/new-feature`
- the separation of `cnt_lag_7`/`cnt_roll_7` from `LAG_WARMUP`
- seeding and reverting the three faults, and drafting `docs/SEEDED_FAULTS.md`
- the raw-data sha256 test
- the `/leakage-auditor` run and the `agent/audit.py` run
- the `RatioTarget` wrapper and `--target ratio` flag
- every validation diagnostic and bootstrap
- first drafts of the DECISIONS.md lines, the AUDIT.md verdict and this report

**My decisions** (each traced to a DECISIONS.md line or commit):
- which feature to add (`cnt_roll_28`, from options the agent proposed) and keeping it
- implementing the sha256 catch for fault 4
- not fixing batch-audit findings 1 and 3 (answered above instead)
- using the ratio transformation and not the leaky year-mean contrast
- judging the transformation defensible
- the Exercise 5 position (not worth deploying as it stands, the agent's recommended side, which I chose)
- when to look at the test set: once, at the end, apart from the exposures recorded in DECISIONS.md
- the commit structure, including one commit per seeded fault

I ran the fault-4 `cp` myself after the agent's attempt was blocked.
