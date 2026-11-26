"""Stage 3: temporal split, fit, evaluate, write metrics.

Two baselines and two models, on purpose.

  baseline_mean         predict the 2011 average for every day
  baseline_persistence  predict yesterday's count (cnt_lag_1)
  ridge                 standardised linear model on the audited features
  hgb                   gradient-boosted trees on the same features

The mean baseline shows what "the distribution moved" costs. Persistence
is the baseline that actually matters: ridge's features are dominated by
lagged demand, so if it cannot beat "yesterday again" it has learned
nothing worth reporting. The booster is there because it fails, and the
reason it fails is the headline result.

Run: python -m src.train
     python -m src.train --target ratio          (Exercise 4, validation only)
     python -m src.train --target ratio --test   (Exercise 4, final, once)
"""
import argparse
import json

import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import (
    METRICS,
    METRICS_RATIO,
    PROCESSED,
    RATIO_DENOM,
    TARGET,
    TRAIN_END,
    VALID_END,
)
from src.features import feature_columns


class PersistenceBaseline(BaseEstimator, RegressorMixin):
    """Predict a single lagged column unchanged. Nothing is fit."""

    def __init__(self, column: str = "cnt_lag_1"):
        self.column = column

    def fit(self, X, y=None):
        if self.column not in X.columns:
            raise ValueError(f"persistence baseline needs column {self.column!r}")
        return self

    def predict(self, X):
        return X[self.column].to_numpy(dtype=float)


class RatioTarget(BaseEstimator, RegressorMixin):
    """Fit `model` on cnt / X[denom] and predict model(X) * X[denom].

    Exercise 4. A tree cannot predict outside the range of its training
    targets, and 2012 is ~65% busier than 2011. Relative demand (today vs
    the trailing 28-day mean) is roughly stationary across years, so a tree
    can learn it. `denom` is a lagged feature (shift(1) before rolling), so
    the rescaling uses only information available before the day.
    """

    def __init__(self, model, denom: str = RATIO_DENOM):
        self.model = model
        self.denom = denom

    def fit(self, X, y):
        self.model_ = clone(self.model).fit(X, y / X[self.denom])
        return self

    def predict(self, X):
        return self.model_.predict(X) * X[self.denom].to_numpy(dtype=float)


MODELS = {
    "baseline_mean": DummyRegressor(strategy="mean"),
    "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
    "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
}


def temporal_split(df: pd.DataFrame):
    """Split by date, never at random. A random split on a time series
    puts tomorrow in train and today in test."""
    train = df[df.dteday <= TRAIN_END]
    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
    test = df[df.dteday > VALID_END]
    return train, valid, test


def fit_and_score(target: str = "raw", with_test: bool = True) -> dict:
    """target="ratio" wraps ridge and hgb in RatioTarget; the two baselines
    are never transformed. with_test=False scores validation only."""
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)
    splits = [("valid", valid)] + ([("test", test)] if with_test else [])

    results = {
        "target": target,
        "n_features": len(cols),
        "features": cols,
        "n_train": len(train),
        "n_valid": len(valid),
        "n_test": len(test),
    }
    for name, model in MODELS.items():
        if target == "ratio" and not name.startswith("baseline_"):
            model = RatioTarget(model)
        model.fit(train[cols], train[TARGET])
        results[name] = {
            split: {
                "r2": round(float(r2_score(part[TARGET], model.predict(part[cols]))), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], model.predict(part[cols]))), 1),
            }
            for split, part in splits
        }
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["raw", "ratio"], default="raw")
    ap.add_argument("--test", action="store_true",
                    help="with --target ratio: also score test (final run only)")
    ns = ap.parse_args()

    if ns.target == "raw":
        res, out = fit_and_score(), METRICS
    else:
        res, out = fit_and_score("ratio", with_test=ns.test), METRICS_RATIO
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=2))
