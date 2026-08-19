import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

CLASS_NAMES = ['bad', 'mid', 'good']


def safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
  """Mean absolute percentage error, expressed as a percentage."""
  mask = np.abs(y_true) > 1e-9
  if not np.any(mask):
    return float('nan')
  ratio = np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])
  return float(np.mean(ratio) * 100.0)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
  abs_err = np.abs(y_true - y_pred)
  return {
    'r2': float(r2_score(y_true, y_pred)),
    'rmse': float(mean_squared_error(y_true, y_pred) ** 0.5),
    'mae': float(mean_absolute_error(y_true, y_pred)),
    'mape_pct': safe_mape(y_true, y_pred),
    'p90_ae': float(np.percentile(abs_err, 90)),
  }


def quartile_thresholds(y_train: pd.Series):
  """Class boundaries derived from the TRAINING fold only."""
  q1, q3 = np.quantile(y_train, [0.25, 0.75])
  return float(q1), float(q3)


def apply_thresholds(y: pd.Series, t_low: float, t_high: float) -> pd.Series:
  if t_low == t_high:
    raise ValueError(
      f'thresholds collapsed to a single value ({t_low!r}): the training fold has no '
      'spread between its 25th and 75th percentiles, so a 3-class split is not possible. '
      'Adjust thresholds (--fixed-thresholds) or exclude the site.'
    )
  # right=False: bin edges are left-closed, so a value exactly on a boundary
  # belongs to the class above it (e.g. y == t_low is 'mid', not 'bad').
  labels = pd.cut(y, bins=(-np.inf, t_low, t_high, np.inf), labels=CLASS_NAMES, right=False)
  return labels.astype('category').cat.set_categories(CLASS_NAMES, ordered=True)


def assert_multiclass(y: pd.Series, context: str) -> None:
  """Raise a readable error when a fold collapses to one class."""
  present = [value for value in y.dropna().unique()]
  if len(present) < 2:
    raise ValueError(
      f'fold {context!r} contains only class {present}: a classifier cannot be '
      'trained or scored on it. Adjust thresholds (--fixed-thresholds) or exclude the site.'
    )


def assert_comparable_scales(y: pd.Series, group_ids: pd.Series, target: str) -> None:
  """Levanta erro quando a faixa inteira de um grupo fica abaixo do Q1 de outro.

  Dois grupos medindo a mesma grandeza física têm distribuições que se sobrepõem.
  Um grupo cujo MÁXIMO fica abaixo do primeiro quartil de outro está quase
  certamente registrado em outra unidade — o sintoma clássico de um dataset ter
  passado por `normalize` e o outro não.

  Isso importa mais na classificação: limiares de quartil calculados sobre escalas
  incompatíveis transformam o rótulo de classe num proxy de "de qual grupo veio
  esta linha", que o modelo infere trivialmente das features. Essa falha é
  silenciosa — diferente da regressão, onde aparece como um R² absurdo.
  """
  if len(y) != len(group_ids):
    raise ValueError(
      f'assert_comparable_scales recebeu y com {len(y)} linhas e group_ids com '
      f'{len(group_ids)} linhas — precisam ter o mesmo comprimento, alinhados '
      'posicionalmente (índices diferentes não são comparados por rótulo aqui).'
    )
  frame = pd.DataFrame({'y': y.to_numpy(), 'g': group_ids.to_numpy()})
  stats = frame.groupby('g')['y'].agg(maximum='max', q1=lambda values: values.quantile(0.25))
  for low in stats.index:
    for high in stats.index:
      if low == high:
        continue
      if stats.loc[low, 'maximum'] < stats.loc[high, 'q1']:
        raise ValueError(
          f'escalas incompatíveis para {target!r}: todo valor de {low!r} '
          f'(max={stats.loc[low, "maximum"]:.4f}) fica abaixo do primeiro quartil de '
          f'{high!r} (Q1={stats.loc[high, "q1"]:.4f}). Os grupos quase certamente estão '
          'em unidades diferentes — verifique se um dataset passou por normalize e o '
          'outro não.'
        )
