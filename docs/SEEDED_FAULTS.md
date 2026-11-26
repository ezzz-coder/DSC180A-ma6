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
