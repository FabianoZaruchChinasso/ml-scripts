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


def format_shap_ranking(ranking: pd.DataFrame, target: str, top_n: int = 10) -> str:
  """Top features por |SHAP| médio, um bloco por modelo.

  Os valores estão na unidade do alvo (Mbps / ms): são o quanto a feature move a
  predição, não uma porcentagem.
  """
  if ranking is None or ranking.empty:
    return f'Sem ranking SHAP para {target} (nenhuma explicação foi concluída).'
  required = {'model', 'rank', 'feature', 'mean_abs_shap'}
  missing = sorted(required - set(ranking.columns))
  if missing:
    raise ValueError(f'ranking SHAP sem as colunas {missing}')
  lines = [f'Top {top_n} features por |SHAP| médio — {target} (unidade do alvo)']
  for model, group in ranking.groupby('model', sort=False):
    top = group.nsmallest(top_n, 'rank')[['rank', 'feature', 'mean_abs_shap']]
    lines.append(f'  model={model}')
    table = top.to_string(index=False, float_format=lambda x: f'{x:.5f}')
    lines.extend(f'  {line}' for line in table.splitlines())
  return '\n'.join(lines)
