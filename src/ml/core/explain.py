"""Explicações SHAP para o benchmark de regressão leave-one-site-out.

`shap` e `matplotlib` são importados dentro das funções, nunca no topo: uma
execução sem `--shap` não pode exigir nenhum dos dois (o venv12 não tem shap).

Todo modelo do benchmark é um `Pipeline` (`imputer` -> `scaler` opcional ->
`reg`), então o explainer recebe a matriz que o estimador final realmente vê,
enquanto a cor do beeswarm usa os valores pós-imputação e PRÉ-escala — assim a
barra de cores fica em unidades físicas (dBm, us, Mbps) também para o `mlp`.
`RobustScaler` é monótono por feature, então a ordem baixo->alto da cor se
mantém. Atenção: onde o valor original era NaN, a cor mostra a mediana imputada,
não o dado ausente.
"""

import os
from dataclasses import dataclass
from typing import Sequence, Tuple

import numpy as np
import pandas as pd

# Modelos com caminho exato via TreeExplainer; o resto cai no permutation.
TREE_MODELS = frozenset({'rf', 'extra_trees', 'hist_gb', 'XGB'})


@dataclass
class ShapConfig:
  """Parâmetros de uma execução SHAP (um objeto por run, não por fold)."""
  models: Tuple[str, ...]
  out_dir: str
  per_fold: bool = False
  max_samples: int = 300
  background: int = 100
  max_display: int = 20
  seed: int = 42

  def wants(self, model_name: str) -> bool:
    return model_name in self.models


def require_shap() -> None:
  """Falha cedo e com mensagem útil quando `--shap` roda sem a dependência.

  Sem isto o erro só apareceria como um WARNING por fold e por modelo, depois de
  todo o treinamento — dezenas de linhas para dizer 'falta um pacote'.
  """
  try:
    import shap  # noqa: F401
  except ImportError as error:
    raise ImportError(
      f'--shap exige o pacote shap, que não está neste interpretador ({error}). '
      'Instale com `pip install shap` (já está em requirements.txt).'
    ) from error


def resolve_shap_models(requested, available) -> Tuple[str, ...]:
  """Valida `--shap-models` contra as chaves de `build_models`.

  A ordem retornada é a de `available`, para que os gráficos saiam na mesma
  ordem em que os modelos são treinados.
  """
  available = list(available)
  if requested is None:
    return tuple(available)
  if not requested:
    raise ValueError(
      '--shap-models veio vazio: passe ao menos um modelo '
      f'entre {available}, ou omita a flag para explicar todos.'
    )
  unknown = [name for name in requested if name not in available]
  if unknown:
    raise ValueError(
      f'modelos desconhecidos em --shap-models: {unknown}. Disponíveis: {available}'
    )
  return tuple(name for name in available if name in requested)


def sample_rows(X_test: pd.DataFrame, max_samples: int, seed: int) -> pd.DataFrame:
  """Subamostra determinística das linhas de teste de um fold.

  A mesma semente é usada para todos os modelos, de propósito: todos são
  explicados sobre EXATAMENTE as mesmas linhas, então os beeswarms de modelos
  diferentes são comparáveis ponto a ponto. `max_samples=0` usa tudo.
  """
  if max_samples and len(X_test) > max_samples:
    return X_test.sample(n=max_samples, random_state=seed).sort_index()
  return X_test


def mean_abs_shap_frame(values, feature_names) -> pd.DataFrame:
  """Ranking de features por |SHAP| médio. Numpy puro — não importa shap."""
  values = np.asarray(values, dtype=float)
  if values.ndim != 2:
    raise ValueError(
      f'esperava uma matriz SHAP 2D (linhas x features), recebi shape {values.shape}'
    )
  feature_names = list(feature_names)
  if values.shape[1] != len(feature_names):
    raise ValueError(
      f'matriz SHAP tem {values.shape[1]} colunas mas vieram {len(feature_names)} '
      'nomes de feature — os nomes sairiam desalinhados das colunas.'
    )
  frame = pd.DataFrame({
    'feature': feature_names,
    'mean_abs_shap': np.abs(values).mean(axis=0),
  })
  frame = frame.sort_values('mean_abs_shap', ascending=False).reset_index(drop=True)
  frame.insert(0, 'rank', np.arange(1, len(frame) + 1))
  return frame


def _row_base_values(explanation) -> np.ndarray:
  """Base value por linha, mesmo quando o explainer devolveu um escalar."""
  base = np.asarray(explanation.base_values, dtype=float).ravel()
  n_rows = np.asarray(explanation.values).shape[0]
  if base.size == n_rows:
    return base
  if base.size == 1:
    return np.repeat(base, n_rows)
  raise ValueError(
    f'base_values tem {base.size} entradas para {n_rows} linhas — não dá para alinhar.'
  )


def concat_explanations(explanations: Sequence):
  """Empilha as Explanations dos folds num único objeto.

  Todos os folds predizem o mesmo alvo na mesma unidade (Mbps / ms), então os
  valores SHAP são comensuráveis e empilham. O que o gráfico resultante mostra é
  o efeito TÍPICO ENTRE SITES: cada bloco de linhas vem de um modelo diferente
  (um por fold), com seu próprio base value. O beeswarm plota apenas os valores,
  então isso não distorce a figura — mas não leia o gráfico como se fosse um
  único modelo.
  """
  import shap

  explanations = list(explanations)
  if not explanations:
    raise ValueError('concat_explanations recebeu uma lista vazia')
  feature_names = list(explanations[0].feature_names)
  for explanation in explanations[1:]:
    if list(explanation.feature_names) != feature_names:
      raise ValueError(
        'os folds têm listas de features diferentes — empilhar misturaria colunas'
      )
  return shap.Explanation(
    values=np.vstack([np.asarray(e.values) for e in explanations]),
    base_values=np.concatenate([_row_base_values(e) for e in explanations]),
    data=np.vstack([np.asarray(e.data) for e in explanations]),
    feature_names=feature_names,
  )


def _permutation_explanation(estimator, background: np.ndarray, model_input: np.ndarray, seed: int):
  """Fallback genérico: caro, mas funciona para qualquer estimador (ex.: mlp)."""
  import shap

  explainer = shap.PermutationExplainer(estimator.predict, background, seed=seed)
  # O permutation explainer precisa de pelo menos 2 * n_features + 1 avaliações
  # para uma passada completa de ida e volta.
  return explainer(model_input, max_evals=2 * model_input.shape[1] + 1, silent=True)


def explain_fold(fitted, X_train: pd.DataFrame, X_test: pd.DataFrame,
                 model_name: str, config: ShapConfig):
  """Explanation das linhas de teste (fora do site) de um fold já treinado."""
  import shap

  rows = sample_rows(X_test, config.max_samples, config.seed)
  estimator = fitted[-1]
  model_input = np.asarray(fitted[:-1].transform(rows), dtype=float)
  display = np.asarray(fitted[:1].transform(rows), dtype=float)
  feature_names = list(X_test.columns)

  explanation = None
  if model_name in TREE_MODELS:
    try:
      explainer = shap.TreeExplainer(estimator, feature_perturbation='tree_path_dependent')
      explanation = explainer(model_input, check_additivity=False)
    except Exception as error:
      # O suporte a HistGradientBoosting é a parte mais frágil entre versões do
      # shap; uma atualização não pode derrubar o benchmark inteiro.
      print(f'WARNING: TreeExplainer indisponível para {model_name!r} ({error}); '
            'usando o permutation explainer')

  if explanation is None:
    background_source = np.asarray(fitted[:-1].transform(X_train), dtype=float)
    background = shap.utils.sample(background_source, config.background, random_state=config.seed)
    explanation = _permutation_explanation(estimator, background, model_input, config.seed)

  return shap.Explanation(
    values=np.asarray(explanation.values, dtype=float),
    base_values=_row_base_values(explanation),
    data=display,
    feature_names=feature_names,
  )


def save_beeswarm(explanation, title: str, path: str, max_display: int = 20) -> None:
  """Escreve um beeswarm em PNG. Backend headless: isto é script de lote."""
  import matplotlib
  matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  import shap

  os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
  plt.figure()
  shap.plots.beeswarm(explanation, max_display=max_display, show=False)
  figure = plt.gcf()
  figure.suptitle(title, fontsize=11)
  figure.tight_layout()
  figure.savefig(path, dpi=150, bbox_inches='tight')
  plt.close(figure)
