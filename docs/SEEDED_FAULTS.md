# Seeded faults (Exercise 2)

Run on 2026-11-25 against commit `b8d43da` (15 features incl. `cnt_roll_28`).
Agent: Claude Opus 5.5 (hosted), launched from the activated `.venv` so the
PostToolUse hook runs the pinned interpreter. The same agent seeded and fixed
each fault, so it knew the cause in advance: the turn counts below are a lower
bound, not what a blind agent would need.

Each fault was a single `Edit` to `src/features.py`. "Hook stderr" is what the
PostToolUse hook (`.claude/hooks/check_leakage.sh`, exit 2) sent back to the
agent immediately after that edit; it shows only the last 20 lines of pytest.
"make test" is the full suite run afterwards.

## Fault 1: forbidden column in `feature_columns`

Change:

```diff
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN - {"registered"}]
```

Hook stderr (fired on the edit):

```
Leakage tests failed after editing .../src/features.py:
    def test_no_forbidden_features(feats):
        ...
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'registered'}
E       assert not ({'atemp', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_28', 'cnt_roll_7', 'dayofweek', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests/test_leakage.py:31: AssertionError
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: forbidden columns in feature set: {'registered'}
1 failed, 9 passed in 0.38s
```

`make test`:

```
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 16 passed in 1.58s
```

Effect had it shipped: ridge valid R^2 0.6839 -> 0.9252 (validation only).

Turns to fix: 1 (revert the edit; hook silent afterwards).

## Fault 2: delete `.shift(1)` from `cnt_roll_7`

Change:

```diff
-    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(7).mean()
+    out["cnt_roll_7"] = out[TARGET].rolling(7).mean()
```

Hook stderr (fired on the edit):

```
Leakage tests failed after editing .../src/features.py:
    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4605.285714285715) == 4724.428571428572 ± 0.00472443
E             comparison failed
E             Obtained: 4605.285714285715
E             Expected: 4724.428571428572 ± 0.00472443

tests/test_leakage.py:57: AssertionError
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.float64(4605.285714285715) == 4724.428571428572 ± 0.00472443
1 failed, 9 passed in 0.33s
```

`make test`:

```
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 16 passed in 1.92s
```

Turns to fix: 1.

Caveat: the catching test checks one row (`iloc[200]`) inside an `if`. If
that row's window ever touched a missing day, the assertion would be skipped
and the test would pass vacuously. It caught this fault, but only by position.

## Fault 3: remove the `raise` in `encode_weather`

Change:

```diff
     if unknown:
-        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
+        pass
```

Hook stderr: **none. The hook did not fire.**

`make test`:

```
.................                                                        [100%]
17 passed in 1.76s
```

**No test went red.** The raw data contains only GOOD / MISTY / BAD, so the
unknown-label branch is never exercised. With the fault in place the encoder
silently maps an unseen label to NaN:

```
>>> encode_weather(pd.Series(['GOOD', 'STORMY', 'BAD'])).tolist()
[0.0, nan, 2.0]
```

and `build_features` would then `dropna()` those days without a word, the
failure the encoder's docstring warns about. The row-loss test in
`tests/test_contract.py` would only notice if the data itself contained a new
label. What would catch it: a unit test in `tests/test_leakage.py` (so the
hook runs it) that passes a series containing an unknown label to
`encode_weather` and asserts `ValueError`.

Turns to fix: 1 (restore the `raise`), but only because the agent knew the
fault was there; nothing in the tooling pointed to it.

## Fault 4: overwrite `data/raw/` with a Bash `cp`

Run by hand from the shell (the agent's own attempt at the `cp` was refused
by Claude Code's session-level permission check; the repo's
`.claude/settings.json` only denies `Write`/`Edit` on `data/raw/**`, so
under the starter's configuration a Bash `cp` is not blocked).

Change: a copy of the raw CSV with Hurricane Sandy's count (2012-10-29, a
test-set day) altered from 22 to 4000, written with pandas, then

```
cp "$S/bike_tampered.csv" data/raw/bike_daily.csv
```

Output:

```
Sandy before: [22]
== sha256 after cp
62d6b6a5e8db3f30b44e407210b533b4bb00980cfe9e17e3ec780fa85dca1945  data/raw/bike_daily.csv
 M data/raw/bike_daily.csv
python -m src.ingest
OK ingest: 728 rows, 2011-01-03 -> 2012-12-31
python -m src.features
OK features: 672 rows, 15 features -> features.parquet
python -m pytest tests/ -q
....F............                                                        [100%]
    def test_leakage_identity_holds(feats):
        """Documents *why* casual and registered are forbidden."""
>       assert (feats.casual + feats.registered == feats[TARGET]).all()
E       assert np.False_
FAILED tests/test_leakage.py::test_leakage_identity_holds - assert np.False_
1 failed, 16 passed in 1.47s
== restoring
a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc  data/raw/bike_daily.csv
```

Hook stderr: **none.** The PostToolUse hook matches only `Edit|Write`, and
only paths under `src/`; a Bash command that rewrites `data/raw/` is invisible
to it. `make data` also passed: `src/ingest.py` only checks required columns
and a 700-row minimum, and skips the download when the file exists.

A test did go red, but by accident. `test_leakage_identity_holds` exists to
document why `casual` and `registered` are forbidden, and it failed only
because this particular edit changed `cnt` without changing its components.
A tamper that preserved the identity (edit `casual` and `cnt` together, alter
`temp` or `hum`, drop a BAD-weather day, or swap in the 731-row UCI file with
its weather codes renamed) would pass all 17 tests and silently change every
reported number.

What would have caught it, in order of strength:

1. **A checksum test.** Store the expected sha256 of `data/raw/bike_daily.csv`
   (`a6bed1577f6e4de5...`) in `src/config.py` and assert it in
   `tests/test_contract.py`. Any byte-level change fails `make test`,
   whatever was edited and however it got there.
2. **A PreToolUse hook on `Bash`** that rejects (exit 2) commands writing to
   `data/raw/` (`cp`, `mv`, `>`, `tee`, `sed -i` ...). This stops the agent
   before the write instead of after, but pattern-matching shell is
   bypassable, so it complements the checksum rather than replacing it.
3. **Filesystem permissions**: `chmod a-w data/raw/bike_daily.csv`. Cheap,
   but a `cp` run by the owner can still be preceded by a `chmod`.

Restored with `git checkout -- data/raw/bike_daily.csv`; sha256 verified as
`a6bed1577f6e4de5...` afterwards.
