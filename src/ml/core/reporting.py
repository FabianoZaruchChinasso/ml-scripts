import pandas as pd


def format_fold_plan(train_sites_per_fold, test_site_per_fold, group_level='site') -> str:
  """Render exactly which sites train and test each fold.

  This output is what makes site leakage visible without a code audit.
  """
  if len(train_sites_per_fold) != len(test_site_per_fold):
    raise ValueError(
      f'fold data mismatch: {len(train_sites_per_fold)} train entries '
      f'but {len(test_site_per_fold)} test entries'
    )
  lines = [f'Fold plan (leave-one-{group_level}-out):']
  for index, (train_sites, test_site) in enumerate(zip(train_sites_per_fold, test_site_per_fold)):
    lines.append(f'  fold {index}: train={list(train_sites)} test={test_site}')
  return '\n'.join(lines)


def format_per_site_table(results: pd.DataFrame, metric: str) -> str:
  """Per-site scores plus spread. Never report a bare mean."""
  try:
    pivot = results.pivot(index='model', columns='test_site', values=metric)
  except ValueError as error:
    if 'duplicate' in str(error).lower():
      raise ValueError(
        'duplicate (model, test_site) combination in results — '
        'each model should appear at most once per site'
      ) from error
    raise
  summary = pivot.copy()
  summary['n'] = pivot.notna().sum(axis=1)
  summary['mean'] = pivot.mean(axis=1)
  summary['min'] = pivot.min(axis=1)
  summary['max'] = pivot.max(axis=1)
  n_sites = pivot.shape[1]
  header = f'Per-site {metric} (n_sites={n_sites}; spread matters more than the mean)'
  return f'{header}\n' + summary.to_string(float_format=lambda x: f'{x:.5f}')
