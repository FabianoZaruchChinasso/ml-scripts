import warnings
from dataclasses import dataclass
from typing import List, Tuple

import pandas as pd
from sklearn.model_selection import LeaveOneGroupOut

MIN_SITES = 2
COMFORTABLE_SITES = 4


@dataclass
class Fold:
  X_train: pd.DataFrame
  X_test: pd.DataFrame
  y_train: pd.Series
  y_test: pd.Series
  train_sites: Tuple[str, ...]
  test_site: str
  train_site_ids: pd.Series


def assert_sites_disjoint(train_sites, test_sites) -> None:
  """Raise if any site appears on both sides of a split."""
  overlap = sorted(set(train_sites) & set(test_sites))
  if overlap:
    raise AssertionError(
      f'site leakage detected: {overlap} present in both train and test. '
      'This split would report an optimistic score.'
    )


def validate_site_count(site_ids: pd.Series) -> int:
  n_sites = site_ids.nunique()
  if n_sites < MIN_SITES:
    raise ValueError(
      f'leave-one-site-out needs at least {MIN_SITES} sites, found {n_sites}. '
      'Merge additional datasets or collect more sites.'
    )
  if n_sites < COMFORTABLE_SITES:
    warnings.warn(
      f'only {n_sites} sites available: per-site spread is uninterpretable '
      'and the generalisation estimate is unstable.',
      UserWarning,
      stacklevel=2,
    )
  return n_sites


def outer_logo_folds(X: pd.DataFrame, y: pd.Series, site_ids: pd.Series) -> List[Fold]:
  """Build one fold per site: train on all other sites, test on this one.

  Returns a list (not a generator) so every fold's disjointness has already
  been checked by the time this returns, and so the result can safely be
  iterated more than once.
  """
  validate_site_count(site_ids)
  splitter = LeaveOneGroupOut()
  folds = []
  for train_idx, test_idx in splitter.split(X, y, groups=site_ids):
    train_sites = tuple(sorted(site_ids.iloc[train_idx].unique()))
    test_sites = tuple(sorted(site_ids.iloc[test_idx].unique()))
    assert_sites_disjoint(train_sites, test_sites)
    folds.append(Fold(
      X_train=X.iloc[train_idx],
      X_test=X.iloc[test_idx],
      y_train=y.iloc[train_idx],
      y_test=y.iloc[test_idx],
      train_sites=train_sites,
      test_site=test_sites[0],
      train_site_ids=site_ids.iloc[train_idx],
    ))
  return folds


def inner_logo_splits(train_site_ids: pd.Series):
  """Positional (train, validation) index pairs for tuning within a fold.

  Returns a list so it can be passed directly as scikit-learn's `cv=`.
  """
  n_sites = train_site_ids.nunique()
  # Deliberately not calling validate_site_count: its COMFORTABLE_SITES warning
  # would fire on nearly every inner call (outer training subsets routinely have
  # fewer sites than the full pool) and just spam routine tuning runs. The real
  # data-limitation warning already happens once, at the outer level.
  if n_sites < MIN_SITES:
    raise ValueError(
      f'tuning needs at least {MIN_SITES} training sites, found {n_sites}. '
      'Run with --no-tune.'
    )
  placeholder = pd.DataFrame({'_': range(len(train_site_ids))})
  splits = list(LeaveOneGroupOut().split(placeholder, groups=train_site_ids))
  for train_idx, val_idx in splits:
    assert_sites_disjoint(train_site_ids.iloc[train_idx], train_site_ids.iloc[val_idx])
  return splits
