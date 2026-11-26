"""Guard rails on the ingest contract and the trained model's behaviour."""
import hashlib

import pandas as pd
import pytest
from sklearn.metrics import r2_score

from src.config import (
    FORBIDDEN,
    LAG_WARMUP,
    RAW,
    RAW_FEATURE_COLS,
    RAW_SHA256,
    SOURCE_COLS,
    TARGET,
    UNUSED_COLS,
)
from src.features import build_features, feature_columns, reindex_to_calendar
from src.ingest import load_raw
from src.train import MODELS, temporal_split


@pytest.fixture(scope="module")
def raw():
    return load_raw().sort_values("dteday").reset_index(drop=True)


@pytest.fixture(scope="module")
def feats(raw):
    return build_features(raw)


def test_raw_file_is_unmodified():
    """data/raw/bike_daily.csv is immutable. The Edit/Write deny rules and the
    PostToolUse hook do not cover Bash, so a `cp` or `sed -i` can replace it
    silently; most such edits pass every other test. Checks the bytes on disk,
    not anything load_raw() derives from them."""
    digest = hashlib.sha256(RAW.read_bytes()).hexdigest()
    assert digest == RAW_SHA256, (
        f"{RAW.name} changed: sha256 {digest[:16]}..., expected {RAW_SHA256[:16]}... "
        "Restore it with `git checkout -- data/raw/bike_daily.csv`."
    )


def test_every_raw_column_is_classified(raw, feats):
    """Every column in the raw CSV must be dteday or sit in exactly one of
    FORBIDDEN / RAW_FEATURE_COLS / SOURCE_COLS / UNUSED_COLS in src/config.py.
    A new column in the data fails here until someone decides what it is,
    instead of feature_columns() picking it up because it happens to be
    numeric."""
    classes = [FORBIDDEN, RAW_FEATURE_COLS, SOURCE_COLS, UNUSED_COLS]
    unclassified = [c for c in raw.columns if c != "dteday" and not any(c in s for s in classes)]
    assert not unclassified, f"raw columns not classified in src/config.py: {unclassified}"

    overlap = [c for c in raw.columns if sum(c in s for s in classes) > 1]
    assert not overlap, f"raw columns in more than one class: {overlap}"

    # The raw columns that reach the model must be exactly the declared ones.
    used_raw = set(feature_columns(feats)) & set(raw.columns)
    assert used_raw == RAW_FEATURE_COLS, (
        f"raw columns used as features {sorted(used_raw)} != RAW_FEATURE_COLS {sorted(RAW_FEATURE_COLS)}"
    )


def test_calendar_is_complete_before_lagging(raw):
    """The reindexed frame must have no gaps, or the lags are wrong."""
    grid = reindex_to_calendar(raw)
    assert set(grid.dteday.diff().dropna().dt.days.unique()) == {1}


def test_only_expected_rows_are_dropped(raw, feats):
    """Rows may only vanish for the lag warm-up or downstream of a genuinely
    absent day -- never because an encoder produced a silent NaN.

    Accounting: the first LAG_WARMUP days have no complete history. Each
    absent calendar day m costs the LAG_WARMUP rows after it (cnt_lag_1 is
    NaN on m+1, cnt_roll_7 is NaN on m+1..m+7, cnt_lag_7 on m+7; their
    union is 7 rows). Day m itself was never in `raw`, so it is not a loss.
    The bound is exact for the current feature set; add a longer lag and
    LAG_WARMUP in src/config.py must grow with it.
    """
    full = pd.date_range(raw.dteday.min(), raw.dteday.max(), freq="D")
    missing_days = len(full) - len(raw)
    allowed_loss = LAG_WARMUP + LAG_WARMUP * missing_days
    lost = len(raw) - len(feats)
    assert lost <= allowed_loss, f"lost {lost} rows; expected at most {allowed_loss}"


def test_beats_the_mean_baseline(feats):
    """A model that cannot beat predicting the training mean is not a result."""
    cols = feature_columns(feats)
    train, _, test = temporal_split(feats)
    ridge = MODELS["ridge"]
    ridge.fit(train[cols], train[TARGET])
    assert r2_score(test[TARGET], ridge.predict(test[cols])) > 0.4


def test_persistence_baseline_is_reported():
    """The baseline that matters for a lag-driven model is 'yesterday again'.
    It must be in the comparison, whatever its score."""
    assert "baseline_persistence" in MODELS
