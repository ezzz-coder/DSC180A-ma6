"""The tests that make the agent honest.

test_no_forbidden_features is the single most valuable test in this repo:
casual + registered == cnt exactly, so any model handed those columns
scores R^2 = 1.0 and looks brilliant while having learned nothing.
"""
import pandas as pd
import pytest

from src.config import FORBIDDEN, TARGET
from src.features import build_features, feature_columns
from src.ingest import load_raw


@pytest.fixture(scope="module")
def feats():
    return build_features(load_raw())


def test_leakage_identity_holds(feats):
    """Documents *why* casual and registered are forbidden."""
    assert (feats.casual + feats.registered == feats[TARGET]).all()


def test_no_forbidden_features(feats):
    """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
    construction, so this cannot discover a *new* leaky column. What it
    catches is someone editing feature_columns() or FORBIDDEN -- which is
    exactly the fault the Step 7 hook demonstrates."""
    cols = set(feature_columns(feats))
    assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"


def test_lags_are_true_calendar_lags(feats):
    """cnt_lag_1 for date d must equal cnt on d-1, in calendar days."""
    by_date = feats.set_index("dteday")[TARGET]
    checked = 0
    for date, lag in feats.set_index("dteday").cnt_lag_1.items():
        prev = date - pd.Timedelta(days=1)
        if prev in by_date.index:
            assert lag == pytest.approx(by_date[prev]), f"bad lag at {date.date()}"
            checked += 1
    assert checked > 600, "too few rows actually verified"


def test_lag_is_not_the_target(feats):
    assert not (feats.cnt_lag_1 == feats[TARGET]).all()


def test_rolling_mean_excludes_today(feats):
    """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
    by_date = feats.set_index("dteday")[TARGET]
    date = feats.dteday.iloc[200]
    window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
    if all(d in by_date.index for d in window):
        expected = sum(by_date[d] for d in window) / 7
        assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)


def test_roll_28_on_known_date(feats):
    """cnt_roll_28 on 2012-03-15 is the mean of cnt over 2012-02-16..2012-03-14,
    the 28 calendar days strictly before it. Hand-computed from the raw CSV:
    those days sum to 115349. Including today (cnt 6192) or dropping the
    shift(1) gives a different number."""
    row = feats.set_index("dteday").loc[pd.Timestamp("2012-03-15")]
    assert row.cnt_roll_28 == pytest.approx(115349 / 28)


def test_roll_28_never_spans_the_missing_day(feats):
    """2011-03-10 is absent from the mirror. Every date whose 28-day window
    contains it (2011-03-11..2011-04-07) must be dropped, not silently
    averaged over 27 days or over a row-shifted window."""
    poisoned = pd.date_range("2011-03-11", "2011-04-07")
    assert not feats.dteday.isin(poisoned).any()
    assert pd.Timestamp("2011-04-08") in set(feats.dteday)


def test_lag_7_is_seven_calendar_days(feats):
    """cnt_lag_7 must stay a 7-day lag when LAG_WARMUP grows for longer
    windows; the two used to share a constant."""
    by_date = feats.set_index("dteday")[TARGET]
    date = pd.Timestamp("2012-03-15")
    assert feats.set_index("dteday").cnt_lag_7[date] == by_date[date - pd.Timedelta(days=7)]


def test_no_missing_values(feats):
    assert feats[feature_columns(feats)].isna().sum().sum() == 0


def test_dates_are_sorted_and_unique(feats):
    assert feats.dteday.is_monotonic_increasing
    assert feats.dteday.is_unique
