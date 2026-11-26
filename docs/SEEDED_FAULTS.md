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
